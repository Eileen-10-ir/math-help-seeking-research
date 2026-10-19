"""Parameter spec -> versioned expression. No original student text enters render()."""
import re
import sys
import itertools
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / '数学主线严谨重跑20260930/code'), str(ROOT / 'G0_G1严谨对照20261014/code')]
from controlled_text import tasks as g0_tasks
from g1_generator import REQ, LEARN, TRIED
from common import F, B

VERSION = 'joint-expression-v2-20261014'
WITHIN_TASK_REASON = [
    '这道题为什么要用{concept}？请讲清楚起步思路。',
    '请解释{concept}在这道题中的用法，我还没有具体做法。',
    '这道题运用{concept}的依据是什么，应该怎么开始？',
    '我想了解这道题用{concept}时先考虑什么。',
    '能说明这道题使用{concept}的思路和理由吗？',
    '请带我理解这道题中{concept}的起步方法。',
]

def interpret_behavior(text, level):
    """Interpret existing overall labels; evidence metadata is not a new human label."""
    if level == 'low':
        if re.search(r'我会写|我会做|我能自己完成|我已经会', text):
            kind = 'autonomous_statement'
        elif re.search(r'知道|判断|因式分解|我的思路|我先|我写', text):
            kind = 'step_feedback' if re.search(r'我.{0,25}(?:写成|得到|算出).{0,30}[=＝]', text) else 'method_clue_local_help'
        else:
            kind = 'autonomy_declared_request'
    elif level == 'medium':
        kind = 'concept_or_reason_help' if re.search(r'为什么|依据|原理|什么意思|概念', text) else 'method_help'
    else:
        kind = 'full_solution_request' if re.search(r'完整|过程|步骤|解答|解这|怎么写', text) else 'answer_request'
    # Full source text is retained in the registry so another reviewer can contest the interpretation.
    return {'behavior_type': kind, 'basis': 'existing_final_label_plus_visible_text_interpretation',
            'independent_human_review': 'pending'}

def task_components(task_code):
    letter = task_code[0]
    index = int(task_code[1:])
    source = next(t for t in g0_tasks([index]) if t['task_id'].startswith(letter + '_'))
    q = source['task']
    if letter == 'q':
        a, b = index + 2, index + 4
        components = {'concept': '因式分解', 'focus': f'怎样找到和为−{a+b}、积为{a*b}的两个数',
                      'clue': '我想到用因式分解，要先找两个合适的数',
                      'step': f'我先写成(x−{a})(x−{b})=0', 'next': '为什么乘积为零时可以分别考虑两个因式'}
    elif letter == 'l':
        k, x = index % 5 + 2, index + 3
        components = {'concept': '等式的性质', 'focus': '两边应该先作什么相同的运算',
                      'clue': '我想到等式两边可以同时减去同一个数',
                      'step': f'我先把两边都减4，写成{k}x={k*x}', 'next': '怎样把x的系数变成1'}
    elif letter == 'f':
        d = index + 5
        components = {'concept': '同分母分数相加', 'focus': '相加时分母是否应该改变',
                      'clue': '我发现分母相同，想到先把分子相加',
                      'step': f'我先写成(2+3)/{d}=5/{d}', 'next': '为什么分母保持不变'}
    else:
        b, h = index + 4, index + 6
        components = {'concept': '三角形面积公式', 'focus': '底乘高之后为什么还要除以2',
                      'clue': '我想到先用底乘高，再考虑与平行四边形的关系',
                      'step': f'我先算底乘高：{b}×{h}={b*h}', 'next': '为什么还需要除以2'}
    return {'question': q, **components}

def make_spec(old_row, behavior_type):
    import json
    decode = lambda value: json.loads(value) if isinstance(value, str) else value
    a, l, s, p = decode(old_row['profile'])
    level = old_row['final_level']
    source_behavior_type = behavior_type
    if level == 'high':
        behavior_type = 'answer_request' if a == 1 else 'full_solution_request'
    elif level == 'medium':
        behavior_type = 'method_help' if a == 3 else 'concept_or_reason_help'
    special = behavior_type in ('autonomous_statement', 'autonomy_declared_request', 'method_clue_local_help')
    participation = {'autonomous_statement': 'autonomous_statement',
                     'autonomy_declared_request': 'autonomy_declaration',
                     'method_clue_local_help': 'method_clue'}.get(behavior_type,
                       {1: 'none_displayed', 3: 'claimed_attempt', 4: 'method_clue', 5: 'math_step'}[p])
    help_scope = 'none' if behavior_type == 'autonomous_statement' else (
        'method_with_answer_refusal' if behavior_type == 'autonomy_declared_request' else
        'local_feedback' if level == 'low' else 'method_or_reason' if level == 'medium' else
        'final_answer' if a == 1 else 'full_solution')
    return {'version': VERSION, 'seed': int(old_row['seed']), 'fold': int(old_row['fold']),
            'synthetic_row': int(old_row['synthetic_row']), 'parent_id': old_row['parent_id'],
            'parent_student_id': old_row['parent_student_id'], 'final_level_candidate': level,
            'target_ALSP_mean': decode(old_row['target_profile']), 'configuration_anchors': [a, l, s, p],
            'tau': float(old_row['tau']), 'source_behavior_type': source_behavior_type,
            'behavior_type': behavior_type, 'help_scope': help_scope,
            'learning_goal': {1: 'task_completion', 3: 'understand_current', 5: 'transfer'}[l],
            'participation_form': participation,
            'information_layout': {1: 'deictic', 2: 'topic', 3: 'problem_or_local_context', 5: 'problem_with_focus'}[s],
            'task_code': old_row['task_id'], 'style': int(old_row['surface_family'].split('_')[-1]),
            'participation_conditioned_on_behavior_type': special,
            'score_status': 'engineering_anchors_not_actual_human_scores', 'human_review': 'pending'}

def render(spec):
    assert not any(k in spec for k in ('original_prompt', 'prompt_text', 'source_text'))
    a, l, s, p = spec['configuration_anchors']
    t = task_components(spec['task_code'])
    style = spec['style']
    request_style = spec.get('request_style', style)
    participation_style = spec.get('participation_style', style)
    learning_style = spec.get('learning_style', style)
    level = spec['final_level_candidate']
    kind = spec['behavior_type']
    parts = []
    if s == 1:
        parts.append('这题。')
    elif s == 2:
        parts.append('关于' + t['concept'] + '。')
    elif not (level == 'low' and s == 3):
        parts.append(t['question'] + '。')
    if s == 5 and kind != 'autonomous_statement':
        parts.append('我不明白' + (t['next'] if spec['participation_form'] == 'math_step' else t['focus']) + '。')
    form = spec['participation_form']
    if form == 'autonomous_statement':
        parts.append(['这道题我能自己完成。', '我已经会做这道题了。', '这题我可以自己写出来。'][participation_style % 3])
    elif form == 'autonomy_declaration':
        parts.append(['我想自己把这道题做出来。', '我希望由自己完成后面的解题。', '我想自己继续做这题。'][participation_style % 3])
    elif form == 'claimed_attempt':
        parts.append(TRIED[participation_style])
    elif form == 'method_clue':
        parts.append(t['clue'] + '，但不确定' + t['focus'] + '。')
    elif form == 'math_step':
        parts.append(t['step'] + '，接着想弄清楚' + t['next'] + '。')
    if kind == 'autonomous_statement':
        pass
    elif kind == 'autonomy_declared_request':
        parts.append(['不要直接给我答案，请教我从哪里开始。',
                      '不要替我算出结果，能提供一点解题思路吗？',
                      '结果我自己算，请给我方法上的提示。'][request_style % 3])
    elif level == 'medium' and a == 4:
        parts.append(WITHIN_TASK_REASON[request_style].format(**t))
    else:
        parts.append(REQ[(level, a)][request_style].format(**t))
    parts.append(LEARN[l][learning_style])
    return ''.join(parts), t['question']

def realize_unique(spec, seen):
    """Choose equivalent wording using training-view duplicates only, not test texts."""
    initial = spec['style']
    for offset, (r, p, l) in enumerate(itertools.product(range(6), repeat=3)):
        spec['request_style'] = (initial + r) % 6
        spec['participation_style'] = (initial + p) % 6
        spec['learning_style'] = (initial + l) % 6
        text, question = render(spec)
        key = B.safe_mask(F.normalize_prompt(text))
        if key not in seen:
            seen.add(key)
            spec['source_style'] = initial
            spec['equivalent_rewording_for_training_dedup'] = offset != 0
            return text, question, key
    raise RuntimeError('同义表达池不足；不以重复文本凑数，必须显式调整实验预算或另立表达版本')

def sample_and_render(training_calibration, behavior_by_id, quotas, seed, tau=1.0, fold=0):
    """Reusable generator. Inputs are training metadata only; no original prompt accepted.

    Quotas are an explicit training-design setting, not an estimate of population frequency.
    """
    from g1_generator import generate
    ids = {r['sample_id'] for r in training_calibration}
    assert ids <= set(behavior_by_id)
    assert all('prompt_text' not in r and 'source_text' not in r for r in training_calibration)
    sampled = generate(training_calibration, quotas, seed, mode='ALSP', tau=tau)
    seen, output = set(), []
    for i, row in enumerate(sampled):
        original = dict(row, seed=seed, fold=fold, synthetic_row=i)
        spec = make_spec(original, behavior_by_id[row['parent_id']])
        text, question, key = realize_unique(spec, seen)
        output.append({'spec': spec, 'prompt_text': text, 'question': question, 'masked_feature_key': key,
                       'human_review': 'pending'})
    assert len(output) == sum(quotas.values())
    return output
