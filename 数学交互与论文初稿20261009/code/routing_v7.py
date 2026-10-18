"""Local support corrections only; v6 inference, state and three grade routes retained."""
import re
from routing_v6 import support as previous_support, context_for, MEDIUM_SUFFIX
from evidence_runtime import TASKS

ROUTING_VERSION = 'conversation-support-v7-20261014'

def local_concept_reply(text, hint_id):
    if hint_id == 'triangle' and re.search(r'高.{0,5}(?:是什么|什么意思)|高是什么意思|什么是.{0,4}高', text):
        return ('三角形的高是从一个顶点到对边所在直线的垂直距离；垂足也可能在对边的延长线上。'
                '先选定底边，再找与它垂直的线段。你可以说明为什么图上的斜边不能直接当作这条底的高。',
                'triangle_height_definition_fixed_v1')
    if hint_id == 'linear' and re.search(r'为什么|理由|依据', text):
        return ('等式两边原本相等，对两边同时减去同一个数，相等关系仍成立。'
                '这里减4是为了消去左边的常数项。请先写出两边都减4后的式子。',
                'linear_equality_reason_fixed_v1')
    return None

def support(text, task_id, task, result, gateway, history):
    record = previous_support(text, task_id, task, result, gateway, history)
    context = context_for(task_id, history, text)
    hint_id = context['hint_task_id']
    record['routing_version'] = ROUTING_VERSION
    if record['route_requested'] == 'edge_fixed':
        concept = local_concept_reply(text, hint_id)
        if concept:
            record.update(text=concept[0], fixed_template_id=concept[1],
                          fixed_template_source='versioned local bank; no cloud generation')
    elif record['route_requested'] == 'edge_verify' and result['observed_event'] != 'ack' and not record.get('mathematical_check'):
        concept = local_concept_reply(text, hint_id)
        if concept:
            reply, template = concept
        elif hint_id in TASKS and hint_id != 'free':
            reply = ('题目已保留。' + TASKS[hint_id]['hint'] +
                     '你可以问这一步的理由，或给出自己想到的一步；当前求助等级仍待确认。')
            template = 'ungraded_task_starter_' + hint_id + '_v1'
        else:
            reply = ('我会沿用已有题目。请选一个你现在需要的帮助：解释某个概念、提供起步思路，或检查已有步骤。'
                     '如果缺少关键题目条件，请补充那一个条件即可。')
            template = 'ungraded_context_clarification_fixed_v1'
        record.update(text=reply, fixed_template_id=template,
                      support_policy='ungraded_local_support_not_measured_improvement',
                      fixed_template_source='versioned local bank; no cloud generation')
    if record['route_requested'] in ('edge_fixed', 'edge_verify'):
        assert record['external_cloud_attempts'] == 0
    return record
