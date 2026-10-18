"""User-defined edge / constrained-cloud / direct-cloud policy."""
HIGH_REPLY='这次先不提供答案。请写出你已经尝试的一步，或指出具体卡住的概念与位置；补充后我们再继续。'
VERIFY_REPLY='请补充你想问的内容、已有尝试或这一步的理由，这样才能确定需要哪种支持。'
ACK_REPLY='收到。你可以继续写下一步或提出新的具体问题；这条确认不改变已有状态。'
MEDIUM_SUFFIX='请不要直接给出最终答案或完整代做解答；请给我详细的分步思路与必要提示，先说明可以尝试的下一步，并邀请我写出自己的尝试。'
ROUTING_VERSION='edge-cloud-three-path-v4-20260930'

def support(text,task_id,task,result,gateway,history):
 level=result['decision_level'];base={'routing_version':ROUTING_VERSION,'grade_used_for_routing':level,'history_high_protection':result['history_high_protection'],
  'edge_suffix':'','original_prompt':text,'messages_sent':[],'external_cloud_attempts':0,'external_cloud_successes':0,'engineering_api_attempts':0,'cloud_calls':0,'mathematical_check':None}
 if not result['eligible']:
  return {**base,'text':ACK_REPLY if result['observed_event']=='ack' else VERIFY_REPLY,'tier':'证据核实','provider':'edge_fixed_template','route_requested':'edge_verify','route_executed':'edge_verify','status':'local_success'}
 if level=='high':
  return {**base,'text':HIGH_REPLY,'tier':'固定规范引导','provider':'edge_fixed_template','route_requested':'edge_fixed','route_executed':'edge_fixed','status':'local_success'}
 suffix=MEDIUM_SUFFIX if level=='medium' else '';outgoing=text+('\n\n'+suffix if suffix else '')
 system='你是一位数学学习辅导老师。根据学生的问题和已有对话提供准确、适合学习者理解的数学反馈。'
 if task_id!='free':system+=' 当前数学题目：'+task['question']
 messages=[{'role':'system','content':system}]
 # Only actually supplied support enters history; cloud failure notices are not model answers.
 for r in history[-8:]:
  messages.append({'role':'user','content':r['text']})
  if r['support']['status'] in ['local_success','success']:messages.append({'role':'assistant','content':r['support']['text']})
 messages.append({'role':'user','content':outgoing});cloud=gateway.request(messages);path='cloud_constrained' if suffix else 'cloud_direct'
 return {**base,**cloud,'edge_suffix':suffix,'original_prompt':text,'outgoing_current_prompt':outgoing,'tier':'限制模板＋云端' if suffix else '直接云端支持',
  'route_requested':path,'route_executed':path if cloud['status']=='success' else 'cloud_unavailable',
  'cloud_calls':cloud['external_cloud_attempts'],'scope':'中类模板已发送不等于云模型遵从；教学效果未验证'}
