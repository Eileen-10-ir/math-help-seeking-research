"""Conversation support v6; frozen classifiers and state update remain unchanged."""
import re
from routing_v4 import support as original_support, MEDIUM_SUFFIX
from evidence_runtime import behavioral_evidence, mathematical_evidence, TASKS

ROUTING_VERSION = 'conversation-support-v6-20261009'

def context_for(task_id, history, current=''):
    texts = [r['text'] for r in history] + ([current] if current else [])
    if task_id != 'free':
        return {'question': TASKS[task_id]['question'], 'hint_task_id': task_id,
                'source': 'operator_selected_task', 'anchor_turn': 0}
    # Retain the first explicit mathematical problem even after the recent-message window.
    anchor = next(((i + 1, t) for i, t in enumerate(texts)
                   if re.search(r'[=＝]|三角形|分数|方程|面积|几何|函数|概率', t)),
                  (1, texts[0]) if texts else (0, ''))
    normalized = re.sub(r'\s', '', anchor[1]).replace('−', '-').replace('－', '-').replace('²', '^2')
    known = 'quadratic' if re.search(r'x(?:\^2|2)-5x\+6[=＝]0', normalized, re.I) else 'free'
    return {'question': anchor[1][:2000], 'hint_task_id': known,
            'source': 'operator_original_text_for_tutoring_only', 'anchor_turn': anchor[0]}

def wants_hint(text, result):
    if result['eligible'] or result['observed_event'] != 'question':
        return False
    cue = behavioral_evidence(text)
    if cue and (cue.get('conflict') or cue.get('level') == 'high'):
        return False
    if any('复述' in r for r in result['hold_reasons']):
        return False
    return bool(re.search(r'思路|方法|提示|第一步|怎么开始|如何开始|例子|举例|因式分解|'
                          r'(?:怎么|如何)(?:才能)?(?:找|选|列|拆|分解|判断|理解)|'
                          r'不知道.{0,12}(?:怎么|如何).{0,8}(?:写|做|开始|找)|'
                          r'卡在|不明白|不理解|为什么|接下来|下一步', text))

def fixed_hint(text, context):
    hint_id = context['hint_task_id']
    if hint_id == 'quadratic' and re.search(r'两个|数字|因数|怎么找|因式分解|例子|举例', text):
        return ('先用另一组系数回忆方法：$(x+1)(x+4)=x^2+5x+4$，'
                '所以括号里的两个数，和对应一次项系数，积对应常数项。'
                '回到你的题目，先写出“两个数的和与积各应是多少”，再列出因数对核对符号。'), 'quadratic_factor_example_v2'
    if hint_id != 'free':
        return TASKS[hint_id]['hint'] + ' 你可以只试一个小步骤，或者指出哪句话不明白。', 'starter_' + hint_id + '_v2'
    if re.search(r'因式分解|因数|两个数字', text):
        return ('因式分解可以先从展开回忆：$(x+a)(x+b)=x^2+(a+b)x+ab$。'
                '例如 $(x+1)(x+4)=x^2+5x+4$。请对照前面的题目，只找出需要匹配的和与积。'), 'factor_general_example_v1'
    return ('沿用前面的题目，我们先处理你现在卡住的一步。'
            '可以选择一个小目标：辨认要求求什么、列出一个已知条件，或指出上一条提示中不明白的词。'
            '不需要重复整道题，也不要求先写出正确答案。'), 'generic_conversation_starter_v2'

def support(text, task_id, task, result, gateway, history):
    context = context_for(task_id, history, text)
    bridge = wants_hint(text, result)
    high = result['decision_level'] == 'high' or (
        bridge and result['risk'] is not None and result['risk'] >= result['history_high_threshold'])
    action = {**result, 'eligible': True, 'decision_level': 'high' if high else 'medium',
              'history_high_protection': high} if bridge else result
    # A retained background affects tutoring only; it is never appended to classifier input.
    tutoring_task = {**task, 'question': context['question'] +
        '。后续消息可能只说卡点或步骤，请结合实际对话连续回应，不要求重复整道题。'}
    record = original_support(text, 'retained_context' if context['question'] else task_id,
                              tutoring_task, action, gateway, history)
    record.update(routing_version=ROUTING_VERSION, hint_bridge_used=bridge,
                  state_measurement_eligible=result['eligible'], grade_used_for_routing=result['decision_level'],
                  conversation_context=context, classifier_context_used=False,
                  support_policy='history_high_fixed_starter' if high else
                  'ungraded_constrained_hint' if bridge else 'graded_or_local_evidence',
                  policy_reason='保留实际题目背景辅助连续回应；依赖识别仍只读本轮文本，弱证据保持状态')
    if high:
        reply, template = fixed_hint(text, context)
        record.update(text=reply, tier='本地固定起步提示', fixed_template_id=template,
                      fixed_template_source='versioned local hint bank; no cloud generation')
    elif bridge:
        record['tier'] = '等级待确认 · 受限方法提示'
    elif not result['eligible'] and result['observed_event'] != 'ack':
        check = mathematical_evidence(text, context['hint_task_id'])
        record['mathematical_check'] = check
        record['text'] = check['message'] if check else (
            '我会沿用前面的题目。请继续说你目前卡在哪个概念或步骤；'
            '例如“怎么找因数对”或“为什么这一步成立”，不必重发完整题目。')
    return record
