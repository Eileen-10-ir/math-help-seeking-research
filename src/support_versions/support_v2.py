"""Demand-aware support revision. B2/B3/B4 remain unchanged in midterm_support.
This is an engineering candidate; human quality superiority is not assumed.
"""
import re
from dataclasses import replace
import midterm_support as base
from continuity import local_revision
VERSION='edutrace-demand-support-20261118'
STUCK=re.compile(r'还是不会|仍然不会|还是不懂|仍不理解|没看懂|没有看懂|不明白|不知道.*(?:怎么|如何)|不会.*(?:继续|下一步)|没(?:有)?思路')
PROGRESS=re.compile(r'我(?:已经)?(?:懂了|明白了|会了)|这一步解决了')

def task_history(context):
    """Only use the suffix belonging to the current explicit question."""
    result=[]
    for item in reversed(context.history):
        q=item.get('question') or (item.get('support') or {}).get('task_context',{}).get('question')
        if q and q!=context.question:break
        result.append(item)
    return tuple(reversed(result))

def unresolved_streak(context,text):
    n=0
    for t in reversed([str(h.get('text','')) for h in task_history(context)]+[text]):
        if PROGRESS.search(t) or not STUCK.search(t):break
        n+=1
    return n

def choose_route(analysis,context,text,unresolved_limit=2):
    if unresolved_limit not in (1,2,3):raise ValueError('unresolved_limit must be 1, 2 or 3')
    same=replace(context,history=task_history(context))
    d=base.choose_route(analysis,same,text,'B3')
    streak=unresolved_streak(same,text)
    # Remove ONLY the old count-based exhaustion decision; retain genuine context.
    if d['route_reason']=='local_scaffold_exhausted' and streak<unresolved_limit:
        fallback=base.choose_route(analysis,replace(same,history=()),text,'B3')
        d.update(route=fallback['route'],route_reason=fallback['route_reason'])
    elif streak>=unresolved_limit and d['route_reason'] not in {'high_direct_answer_control','deterministic_local_verification'}:
        d.update(route='cloud_constrained',route_reason='explicit_unresolved_streak')
    return {**d,'unresolved_streak':streak,'unresolved_limit':unresolved_limit,'policy_version':VERSION}

def build_messages(context,text,hint_level,history_limit=8):
    if history_limit is not None and history_limit<0:raise ValueError('negative history limit')
    history=task_history(context)
    history=history if history_limit is None else history[-history_limit:] if history_limit else ()
    ctx=replace(context,history=())
    messages=base.build_cloud_messages(ctx,text,True,hint_level)[:1]
    for item in history:
        user_text=str(item.get('text','')).strip()
        support=item.get('support') or {}
        if user_text:messages.append({'role':'user','content':user_text})
        if support.get('status') in {'local_success','success'} and support.get('text'):
            messages.append({'role':'assistant','content':str(support['text'])})
    messages.append({'role':'user','content':text})
    messages[0]['content']=messages[0]['content'].replace('小学数学学习辅导老师','中小学数学学习辅导老师')
    # Single copy of the constraint in system; the user text remains exactly theirs.
    messages[-1]['content']=text
    return messages

def execute(text,analysis,context,gateway,unresolved_limit=2,history_limit=8):
    ctx=replace(context,history=task_history(context))
    decision=choose_route(analysis,ctx,text,unresolved_limit)
    route=decision['route']
    if route.startswith('edge'):
        result=base.execute_optimized_support(text,analysis,ctx,gateway,'B3',forced_route=route)
        revision=local_revision(ctx,text,route)
        if revision:
            result.update(text=revision[1],continuity_revision=revision[0],fixed_template_id=VERSION+'-local-revision')
        result.update(route_reason=decision['route_reason'],routing_version=VERSION,decision_diagnostics=decision)
        return result
    messages=build_messages(ctx,text,decision['next_hint_level'],history_limit)
    cloud=gateway.request(messages)
    return {**cloud,'routing_version':VERSION,'optimization_version':'demand_support_revision',
            'route_requested':route,'route_executed':route if cloud.get('status')=='success' else 'cloud_unavailable',
            'route_reason':decision['route_reason'],'decision_diagnostics':decision,'messages_sent':messages,
            'task_context':ctx.as_dict(),'hint_level':None,'tier':'受约束云端支持',
            'cloud_calls':cloud.get('external_cloud_attempts',0),'mathematical_check':None}
