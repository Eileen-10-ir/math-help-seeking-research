"""Separate uncertainty in state measurement from access to bounded method hints."""
from routing_v4 import HIGH_REPLY,VERIFY_REPLY,ACK_REPLY,MEDIUM_SUFFIX,support as old_support
from evidence_runtime import behavioral_evidence
import re
ROUTING_VERSION='edge-cloud-hint-bridge-v5.1-20261002'

def hint_bridge(text,result):
 if result['eligible'] or result['observed_event']!='question':return False
 cue=behavioral_evidence(text)
 if cue and (cue.get('conflict') or cue.get('level')=='high'):return False
 if any('复述' in reason for reason in result['hold_reasons']):return False
 return bool(re.search(r'思路|方法|提示|第一步|怎么开始|如何开始|不知道.{0,12}(?:怎么|如何).{0,8}(?:写|做|开始)',text))

def support(text,task_id,task,result,gateway,history):
 bridge=hint_bridge(text,result)
 high_fixed=result['decision_level']=='high' or (bridge and result['risk'] is not None and result['risk']>=result['history_high_threshold'])
 # An aid policy override does not rewrite the inference or update the student's state.
 action={**result,'eligible':True,'decision_level':'high' if high_fixed else 'medium','history_high_protection':high_fixed} if bridge else result
 record=old_support(text,task_id,task,action,gateway,history)
 record.update(routing_version=ROUTING_VERSION,grade_used_for_routing=result['decision_level'],
  support_policy='history_high_fixed_starter' if bridge and high_fixed else 'ungraded_constrained_hint' if bridge else 'graded_or_local_evidence',
  state_measurement_eligible=result['eligible'],hint_bridge_used=bridge,
  policy_reason='方法求助且历史高信号：本地固定起步提示，状态保持' if bridge and high_fixed else '明确求助方法但依赖证据未足：提供受限云提示，保持状态，不改判中/低类' if bridge else '按本轮综合等级或回应事件处理')
 if high_fixed:
  starter=task['hint'] if task_id!='free' else '先写出题目要求求什么，再选出一个已知条件；可以从辨认题目中的量开始。'
  record['text']='先给你一个起步提示：'+starter+' 不要求先写出正确答案。你可以尝试一个小步骤，或指出提示里哪一处还不明白。'
  record['tier']='本地固定起步提示';record['fixed_template_id']='starter_'+task_id+'_v1';record['fixed_template_source']='declared task hint bank, no cloud generation'
 elif bridge:record['tier']='等级待确认 · 受限起步提示'
 return record
