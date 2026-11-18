"""Evidence-linked conversational memory. No grading, mastery inference or API calls.

Extraction is conservative and rule based. Every exported claim carries a role,
event identifier and literal source span; original utterances remain available.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path

VERSION = 'evidence-memory-v2-connected-20261022'
ACK = re.compile(r'^(?:好的?|好哒|明白了?|懂了|知道了|谢谢(?:老师)?|收到|嗯+|ok)[！!。,.，\s]*$', re.I)
EQUATION = re.compile(r'[0-9a-zA-Z²³^+−*/()\-\s]+[=＝][0-9a-zA-Z²³^+−*/()\-\s]+')
HELP = re.compile(r'为什么|怎么|如何|不(?:懂|明白|理解|会)|不知道|卡在|对吗|对吧|核对|检查|确认|提示|思路|方法|下一步|接下来|告诉我|给我')
OPERATION = re.compile(r'两边|同(?:时)?(?:加|减|乘|除)|除以|乘以|移项|通分|约分|因式分解|配方|代入|展开|合并同类项')
OWN = re.compile(r'我(?:已|已经|自己)?(?:算|写|得到|试|做|用|想|认为)|我的(?:答案|步骤|想法)|得到|算得')
QUOTE = re.compile(r'你(?:刚才)?(?:说|写|给|算)|照抄|复制|复述|照着你的|按照你的')
REVISE = re.compile(r'更正|改成|刚才.{0,12}(?:错|不对)|不是.{0,16}(?:而是|应该)|撤回')
SWITCH = re.compile(r'换(?:一)?(?:个|道)?题|换到|另一(?:道|个)题|新题|下一题|现在(?:算|做|解)')
RETURN = re.compile(r'回到(?:上一题|刚才(?:那|的)?题|第[一二三四五\d]+题)|继续上一题')
NEW_PROBLEM = re.compile(r'解(?:这个)?方程|题目[是：:]|题干[是：:]|计算[：:]|求(?:解|[a-zA-Z])|三角形|函数|概率')


def canonical(text):
    return re.sub(r'\s+', '', text).replace('−', '-').replace('²', '^2').replace('＝', '=')


def quoted_span(text):
    """Return an exact evidence span; never synthesize mathematical content."""
    return {'start': 0, 'end': len(text), 'quote': text}


class EvidenceMemory:
    def __init__(self, question='', question_source='operator_task'):
        self.nodes = []
        self.edges = []
        self.events = []
        self.active = None
        self.visits = []
        self.flags = []
        if question:
            self._problem(question, 'task:0', question_source)

    def _node(self, kind, text, event, role, **extra):
        node = {'id': f'n{len(self.nodes)+1}', 'kind': kind, 'text': text,
                'source_event': event, 'role': role, 'evidence': quoted_span(text),
                'status': 'reported_not_verified', 'active': True, **extra}
        self.nodes.append(node)
        return node

    def _edge(self, source, target, relation, event):
        self.edges.append({'source': source, 'target': target, 'relation': relation,
                           'source_event': event, 'basis': 'explicit_text_or_record_order'})

    def _problem(self, text, event, source):
        p = self._node('problem', text, event, 'student' if event.startswith('u') else 'operator', source=source)
        p['problem_id'] = p['id']
        self.active = p['id']
        self.visits.append(p['id'])
        return p

    def ingest(self, text, role, turn, status='success'):
        eid = ('u' if role == 'student' else 'a') + str(turn)
        existing = next((e for e in self.events if e['id'] == eid), None)
        if existing:
            if existing['text'] != text or existing['role'] != role:
                raise ValueError('An event identifier cannot refer to two utterances')
            return
        event = {'id': eid, 'role': role, 'text': text, 'turn': turn, 'status': status}
        self.events.append(event)
        if role == 'assistant':
            if status not in ('success', 'local_success'):
                return
            if self.active:
                node = self._node('delivered_support', text, eid, role, problem_id=self.active)
                self._edge(node['id'], self.active, 'supports_problem', eid)
            return
        if role != 'student':
            raise ValueError('Unsupported conversational role')

        is_ack = bool(ACK.fullmatch(text.strip()))
        switch = bool(SWITCH.search(text))
        returning = bool(RETURN.search(text))
        if returning:
            distinct = list(dict.fromkeys(self.visits))
            target = None
            number = re.search(r'第([一二三四五\d]+)题', text)
            if number:
                digits = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5}
                raw = number[1]
                index = int(raw) if raw.isdigit() else digits.get(raw, 0)
                if 1 <= index <= len(distinct): target = distinct[index-1]
            elif len(self.visits) >= 2:
                target = next((p for p in reversed(self.visits[:-1]) if p != self.active), None)
            if target:
                self.active = target
                self.visits.append(target)
            else:
                self.flags.append({'event': eid, 'kind': 'unresolved_problem_reference'})
                self.active = None
        elif switch:
            self._problem(text, eid, 'explicit_new_problem')
            if not (EQUATION.search(text) or NEW_PROBLEM.search(text)):
                self.flags.append({'event': eid, 'kind': 'new_problem_details_missing'})
        elif not self.active and not is_ack and (EQUATION.search(text) or NEW_PROBLEM.search(text)):
            self._problem(text, eid, 'first_explicit_problem')
        elif self.active and NEW_PROBLEM.search(text) and EQUATION.search(text) and not OWN.search(text):
            old = next(n for n in self.nodes if n['id'] == self.active)
            current_eq = [canonical(m[0]) for m in EQUATION.finditer(text)]
            old_eq = [canonical(m[0]) for m in EQUATION.finditer(old['text'])]
            if current_eq != old_eq:
                self._problem(text, eid, 'explicit_problem_request')

        event['problem_id'] = self.active
        kind = 'acknowledgement' if is_ack else 'student_utterance'
        if not is_ack and (OPERATION.search(text) or OWN.search(text) or EQUATION.search(text)):
            # A bare original question is a task statement, not a claimed attempt.
            is_original = any(n['kind']=='problem' and n['source_event']==eid for n in self.nodes)
            if not is_original or OWN.search(text):
                kind = 'student_contribution'
        quote = bool(QUOTE.search(text))
        if not quote and kind == 'student_contribution' and not OWN.search(text):
            prior = [n for n in self.nodes if n['kind']=='delivered_support' and n.get('problem_id')==self.active]
            equations = [canonical(m[0]) for m in EQUATION.finditer(text)]
            quote = bool(equations) and all(any(eq in canonical(n['text']) for n in prior) for eq in equations)
        if quote and not is_ack:
            kind = 'reported_or_quoted_support'
        node = self._node(kind, text, eid, role, problem_id=self.active,
                          independent_work_claimed=bool(OWN.search(text)) and not quote)
        if self.active:
            self._edge(node['id'], self.active, 'about_problem', eid)
        if not is_ack and HELP.search(text):
            need = self._node('help_request', text, eid, role, problem_id=self.active,
                              status='request_not_confirmed_resolved')
            self._edge(need['id'], node['id'], 'expressed_in', eid)
        previous = [n for n in self.nodes[:-1] if n['source_event']!=eid and n.get('problem_id')==self.active]
        support = next((n for n in reversed(previous) if n['kind']=='delivered_support'), None)
        if support and self.active:
            self._edge(node['id'], support['id'], 'follows_support_not_causal', eid)
        prior_step=next((n for n in reversed(previous) if n['kind']=='student_contribution' and n['active']),None)
        if prior_step and not is_ack and (HELP.search(text) or OPERATION.search(text)):
            self._edge(node['id'],prior_step['id'],'continues_prior_student_step',eid)
            self.edges[-1]['basis']='same_problem_latest_visible_step_pointer_not_proven_reasoning'
        if REVISE.search(text):
            older = next((n for n in reversed(previous) if n['kind']=='student_contribution' and n['active']), None)
            if older:
                older['active'] = False
                self._edge(node['id'], older['id'], 'explicit_revision', eid)

    @classmethod
    def from_records(cls, records, current='', question=''):
        mem = cls(question)
        for i, record in enumerate(records, 1):
            turn = record.get('turn', i)
            mem.ingest(record['text'], 'student', turn)
            support = record.get('support', {})
            if support.get('text'):
                mem.ingest(support['text'], 'assistant', turn, support.get('status', 'unknown'))
        if current:
            mem.ingest(current, 'student', len(records)+1)
        return mem

    def view(self):
        nodes = [n for n in self.nodes if n.get('problem_id')==self.active and self.active]
        problem = next((n for n in nodes if n['kind']=='problem'), None)
        active = [n for n in nodes if n['active']]
        def newest(kind):
            return next((n for n in reversed(active) if n['kind']==kind), None)
        return {'version': VERSION, 'active_problem': problem,
                'student_contributions': [n for n in active if n['kind']=='student_contribution'],
                'latest_student': next((n for n in reversed(active) if n['role']=='student' and n['kind'] not in ('problem','help_request','acknowledgement')), None),
                'latest_request': newest('help_request'), 'latest_support': newest('delivered_support'),
                'quoted_support': [n for n in active if n['kind']=='reported_or_quoted_support'],
                'connections': [e for e in self.edges if e['relation']=='continues_prior_student_step'
                                and any(n['id']==e['source'] for n in active)],
                'flags': self.flags, 'mastery': 'not_inferred', 'grading_effect': 'none'}

    def export(self):
        return {'version': VERSION, 'active_problem_id': self.active,
                'events': self.events, 'nodes': self.nodes, 'edges': self.edges,
                'flags': self.flags, 'view': self.view()}

    def validate(self):
        source = {e['id']: e for e in self.events}
        node_ids = {n['id'] for n in self.nodes}
        errors = []
        for n in self.nodes:
            if n['source_event']=='task:0': continue
            e = source.get(n['source_event'])
            if not e or n['role'] != e['role'] or n['evidence']['quote'] != e['text'][n['evidence']['start']:n['evidence']['end']]:
                errors.append({'node': n['id'], 'error': 'unsupported_or_wrong_role'})
        for e in self.edges:
            if e['source'] not in node_ids or e['target'] not in node_ids or e['source_event'] not in source:
                errors.append({'edge': e, 'error': 'missing_source'})
        return errors


def memory_messages(memory, records, current, mode='graph', budget=2600):
    """Same character budget for all three modes; report actual provider tokens.

    Character budget is an engineering cap, not a token estimate or equal-token
    claim. Graph and chronological-summary extraction both use zero API calls.
    """
    if mode not in ('recent', 'summary', 'graph'): raise ValueError(mode)
    if budget < 300: raise ValueError('Context budget too small')
    t0 = time.perf_counter()
    lines = []
    if mode == 'recent':
        # Legacy control retains its first anchor and eight most recent turns.
        first = next((e['text'] for e in memory.events if e['role']=='student' and (EQUATION.search(e['text']) or NEW_PROBLEM.search(e['text']))), '')
        if first: lines.append('最初题目/原话：'+first)
        for r in records[-8:]:
            lines.append('学生：'+r['text'])
            if r.get('support',{}).get('status') in ('success','local_success'):
                lines.append('实际助手：'+r['support']['text'])
    elif mode == 'summary':
        # A structured recency baseline, deliberately without topic/edge retrieval.
        for n in memory.nodes:
            if n['active'] and n['kind'] in ('problem','student_contribution','help_request','delivered_support','reported_or_quoted_support'):
                lines.append(f"[{n['source_event']}|{n['role']}|{n['kind']}] {n['text']}")
    else:
        v = memory.view()
        relevant = [v['active_problem'], *v['student_contributions'], *v['quoted_support'], v['latest_support'], v['latest_request'], v['latest_student']]
        seen = set()
        for n in relevant:
            if n and n['id'] not in seen:
                seen.add(n['id'])
                lines.append(f"[{n['source_event']}|{n['role']}|{n['kind']}|仅原话未验证] {n['text']}")
        lookup={n['id']:n for n in memory.nodes}
        for edge in v['connections'][-4:]:
            source,target=lookup[edge['source']],lookup[edge['target']]
            lines.append(f"关系线索：学生{source['source_event']}的追问接续本题学生{target['source_event']}展示的步骤；"
                         '这是同题最近步骤的指向线索，不是已经理解或推理正确的证明。')
        if v['flags']: lines.append('不确定项：'+json.dumps(v['flags'], ensure_ascii=False))
    # Keep first task and the newest fitting items, rather than cutting an equation.
    selected = []
    first = lines[0] if lines else ''
    remaining = budget - min(len(first), budget)
    if first: selected.append(first[:budget])
    tail = []
    for line in reversed(lines[1:]):
        if len(line)+1 <= remaining:
            tail.append(line); remaining -= len(line)+1
    selected += list(reversed(tail))
    content = '\n'.join(selected)
    return content, {'memory_version': VERSION, 'memory_mode': mode, 'budget_characters': budget,
                     'context_characters': len(content), 'build_ms': (time.perf_counter()-t0)*1000,
                     'construction_api_calls': 0, 'evidence_validation_errors': memory.validate()}


def context_interpretation(memory, current):
    """Diagnostic candidate only: does not assign a dependency grade or mutate it."""
    v = memory.view()
    direct = re.search(r'直接.{0,8}(?:给|说|告诉|报).{0,8}答案|帮我(?:写|做)完整|完整(?:答案|解答|过程)', current)
    check = re.search(r'对吗|对吧|是否正确|核对|检查|所以.{0,20}[?？]', current)
    candidate = bool(EQUATION.search(current) or re.search(r'答案(?:是|为)|算出|得到',current))
    own_prior = [n for n in v['student_contributions'] if n['source_event'] != ('u'+str(len([e for e in memory.events if e['role']=='student']))) ]
    evidence = [n['source_event'] for n in own_prior]
    if direct: kind = 'direct_answer_request'
    elif check and candidate and v['quoted_support'] and v['latest_student'] and v['latest_student']['kind']=='reported_or_quoted_support': kind = 'checking_reported_answer'
    elif check and candidate and evidence: kind = 'result_check_with_prior_student_process'
    elif check and candidate: kind = 'result_check_process_not_established'
    elif OPERATION.search(current) and v['active_problem']: kind = 'step_submission_or_question'
    elif HELP.search(current) and v['active_problem']: kind = 'followup_help'
    elif ACK.fullmatch(current.strip()): kind = 'acknowledgement'
    else: kind = 'needs_clarification'
    return {'kind': kind, 'related_student_events': evidence, 'changes_grade': False,
            'changes_state': False, 'candidate_not_human_label': True}


def persist_memory(db, session_id, version, memory):
    """Derived graph is rebuildable from original turns; never edit those turns."""
    with closing(sqlite3.connect(Path(db))) as c, c:
        c.execute('CREATE TABLE IF NOT EXISTS evidence_memory (session_id TEXT PRIMARY KEY, turn_version INTEGER NOT NULL, memory_version TEXT NOT NULL, graph_json TEXT NOT NULL)')
        c.execute('INSERT INTO evidence_memory VALUES (?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET turn_version=excluded.turn_version,memory_version=excluded.memory_version,graph_json=excluded.graph_json WHERE excluded.turn_version>=evidence_memory.turn_version',
                  (session_id, version, VERSION, json.dumps(memory.export(), ensure_ascii=False)))
