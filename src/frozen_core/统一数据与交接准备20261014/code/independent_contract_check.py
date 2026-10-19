"""Parse actual evidence and arithmetic; do not import the renderer or its phrase bank."""
import re

def evidence(pattern, text):
    m = re.search(pattern, text)
    return {'span': m.group(), 'start': m.start(), 'end': m.end()} if m else None

def inspect_text(text, question=''):
    negative = evidence(r'(?:不要|不用|别|不需要|不想要).{0,8}(?:答案|结果|解答|做完)|结果我自己算', text)
    # A request in a negative clause is not counted as a positive demand.
    clauses = re.split(r'[。！？；]', text)
    positive = [c for c in clauses if not re.search(r'不要|不用|别|不需要|不想要|结果我自己算', c)]
    active = '。'.join(positive)
    full = evidence(r'完整|全部|从头到尾|从第一步到最后|每一步|整道题.{0,12}(?:推导|步骤|答案)|推导和计算', active)
    answer = evidence(r'最终答案|最后答案|最终结果|最后的结果|答案是多少|得数|(?:直接|替我|帮我|把).{0,12}(?:结果|答案)', active)
    method = evidence(r'方法|思路|提示|用法|怎么起步|从哪里开始|先考虑|怎样运用|怎么用', text)
    concept = evidence(r'原理|依据|理由|道理|是什么意思|成立|为什么', text)
    local = evidence(r'核对|检查|这一环|这一步|这一小步|只.{0,8}(?:提示|帮助|解释|理解|指出)|给我方法上的提示', text)
    autonomy = evidence(r'我想自己|由自己完成|我自己算|我自己继续|后续我自己做|结果我自己算|剩下的我自己算', text)
    statement = evidence(r'我能自己完成|我已经会做|我可以自己写出来', text)
    claim = evidence(r'想过|想了(?!解)|考虑过|试过思考|试着想|试着分析', text)
    clue = evidence(r'我想到|我发现', text)
    step = evidence(r'我先.{0,50}[=＝×]|我.{0,10}写成.{0,30}[=＝]', text)
    denies_steps = evidence(r'没有.{0,6}(?:具体步骤|写出式子|列出计算|推导)|没有可展示的步骤|还没.{0,8}(?:步骤|式子|计算|推导)', text)
    goal = {
        'task_completion': evidence(r'完成作业|结果填上|交这份作业|交上去|交掉|完成这题|完成任务|作业做完|完成这道作业', text),
        'understand_current': evidence(r'弄明白这道题|理解这题|学会当前|知道这道题|思路弄懂|这道题的道理|学会这一题|明白本题', text),
        'transfer': evidence(r'通用方法|类似题|举一反三|共同的规律|同类题|同类型题|迁移|规律', text),
    }
    math = []
    norm = text.replace('−', '-').replace('－', '-').replace('＝', '=')
    qnorm = question.replace('−', '-').replace('－', '-').replace('＝', '=')
    q = re.search(r'x²-(\d+)x\+(\d+)=0', qnorm)
    pair = re.search(r'\(x-(\d+)\)\(x-(\d+)\)=0', norm)
    if pair:
        a, b = map(int, pair.groups())
        ok = bool(q and a + b == int(q[1]) and a * b == int(q[2]))
        math.append({'kind': 'factorization_against_question', 'span': pair.group(), 'correct': ok})
    qlin = re.search(r'(\d+)x\+4=(\d+)', qnorm)
    lin = re.search(r'两边都减4，写成(\d+)x=(\d+)', norm)
    if lin:
        ok = bool(qlin and int(lin[1]) == int(qlin[1]) and int(lin[2]) == int(qlin[2]) - 4)
        math.append({'kind': 'linear_transform_against_question', 'span': lin.group(), 'correct': ok})
    frac = re.search(r'\(2\+3\)/(\d+)=5/(\d+)', norm)
    qfrac = re.search(r'2/(\d+)\+3/(\d+)', qnorm)
    if frac:
        ok = bool(qfrac and int(frac[1]) == int(frac[2]) == int(qfrac[1]) == int(qfrac[2]))
        math.append({'kind': 'fraction_addition_against_question', 'span': frac.group(), 'correct': ok})
    mul = re.search(r'(\d+)×(\d+)=(\d+)', norm)
    qtri = re.search(r'底(\d+)厘米高(\d+)厘米', qnorm)
    if mul:
        ok = int(mul[1]) * int(mul[2]) == int(mul[3])
        if qtri:
            ok = ok and int(mul[1]) == int(qtri[1]) and int(mul[2]) == int(qtri[2])
        math.append({'kind': 'multiplication_against_question', 'span': mul.group(), 'correct': ok})
    return {'request': {'answer': answer, 'full': full, 'method': method, 'concept': concept,
                        'local': local, 'answer_refusal': negative, 'autonomy': autonomy, 'statement': statement},
            'participation': {'claimed': claim, 'clue': clue, 'step': step, 'denies_steps': denies_steps},
            'learning_goal': goal, 'math_assertions': math}

def check_contract(spec, text, question):
    found = inspect_text(text, question)
    r = found['request']
    p = found['participation']
    failed = []
    scope = spec['help_scope']
    if scope == 'final_answer' and (not r['answer'] or r['answer_refusal']):
        failed.append('help_scope_mismatch')
    if scope == 'full_solution' and (not r['full'] or r['answer_refusal']):
        failed.append('help_scope_mismatch')
    if scope == 'method_or_reason' and not (r['method'] or r['concept']):
        failed.append('help_scope_mismatch')
    if scope == 'local_feedback' and not (r['local'] or r['concept']):
        failed.append('help_scope_mismatch')
    if scope == 'method_with_answer_refusal' and not (r['answer_refusal'] and r['autonomy'] and r['method']):
        failed.append('autonomy_request_mismatch')
    if scope == 'none' and (r['answer'] or r['full'] or not r['statement']):
        failed.append('statement_scope_mismatch')
    if scope in ('local_feedback', 'method_with_answer_refusal', 'method_or_reason') and (r['full'] or r['answer']):
        failed.append('unrequested_full_answer_or_scope_conflict')
    form = spec['participation_form']
    if form == 'none_displayed' and (p['claimed'] or p['clue'] or p['step']):
        failed.append('participation_mismatch')
    if form == 'claimed_attempt' and (not p['claimed'] or p['step']):
        failed.append('participation_mismatch')
    if form == 'method_clue' and not p['clue']:
        failed.append('participation_mismatch')
    if form == 'math_step' and not p['step']:
        failed.append('participation_mismatch')
    if form == 'autonomy_declaration' and (not r['autonomy'] or p['step']):
        failed.append('participation_mismatch')
    if p['step'] and p['denies_steps']:
        failed.append('contradictory_participation')
    if not found['learning_goal'][spec['learning_goal']]:
        failed.append('learning_goal_mismatch')
    layout = spec['information_layout']
    if layout == 'deictic' and not text.startswith('这题。'):
        failed.append('information_layout_mismatch')
    if layout == 'topic' and not text.startswith('关于'):
        failed.append('information_layout_mismatch')
    if layout == 'problem_with_focus':
        if question not in text or (spec['behavior_type'] != 'autonomous_statement' and '我不明白' not in text):
            failed.append('information_layout_mismatch')
    if any(not row['correct'] for row in found['math_assertions']):
        failed.append('mathematical_error')
    return {'status': 'pass' if not failed else 'reject', 'failures': failed, 'evidence': found,
            'scope': 'categorical_expression_contract_not_ALSP_human_score_validation'}
