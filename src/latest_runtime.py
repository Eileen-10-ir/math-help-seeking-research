"""Demand-aware B3 support on the frozen, regression-tested recognition/state pipeline."""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'src/support_versions')]
from run import WORK,CURRENT,sync_sources
from conversation_memory import EvidenceMemory
import midterm_support as base
import support_v2 as revised

def context_for(task_id,task,history,text=''):
    question=task.get('question','') if task_id!='free' else ''
    memory=EvidenceMemory.from_records(history,current=text,question=question)
    active=memory.view()['active_problem']
    actual=active['text'] if active else ''
    # Every claim still points to the original utterance. No inferred student step is inserted.
    return base.build_task_context(task_id,actual,history,source='recorded_current_problem')

def bootstrap(policy='B3'):
    if policy not in ['B3','revision']:raise ValueError('Unknown support policy')
    sync_sources();sys.path.insert(0,str(WORK/CURRENT/'code'))
    import runtime_current as runtime
    import runtime_server as legacy
    from state_v5 import advance as frozen_advance
    def audited_advance(*args,**kwargs):
        result=frozen_advance(*args,**kwargs)
        state=args[0]
        result['profile']={'description':'已接纳求助信号的累计记录，不是心理依赖测量',
            'trajectory':'已记录 '+str(state.evidence_turns)+' 次有效更新；请结合轨迹查看',
            'valid_updates':state.evidence_turns,'values':list(state.risks),
            'change_from_first':None if not state.risks else state.risks[-1]-state.risks[0]}
        return result
    def support(text,task_id,task,analysis,gateway,history):
        ctx=context_for(task_id,task,history,text)
        result=base.execute_optimized_support(text,analysis,ctx,gateway,'B3') if policy=='B3' else revised.execute(text,analysis,ctx,gateway)
        result.update(state_measurement_eligible=analysis['eligible'],grade_used_for_routing=analysis['decision_level'],classifier_context_used=False,
            conversation_context={'question':ctx.question,'source':ctx.source},support_policy=policy)
        return result
    legacy.support=support;legacy.advance=audited_advance
    class Service(runtime.ConversationService):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs)
            self.card={**self.card,'model_version':self.card['model_version']+'+support-'+policy+'-20261118',
                'recognizer_changed':False,'support_policy':policy,'parameter_search_promoted':False}
        def get(self,sid):
            session=super().get(sid)
            ctx=context_for(session['task_id'],session['task'],session['records'])
            session['conversation_context']={'question':ctx.question,'source':ctx.source}
            session['support_policy_version']=policy+'-20261118'
            return session
    return runtime,Service

def handler(runtime,service,port,policy):
    Parent=runtime.handler(service,port)
    class Handler(Parent):
        def do_GET(self):
            if self.path in ['/','/app.js']:
                try:
                    self.validate()
                    filename='index.html' if self.path=='/' else 'app.js'
                    body=(ROOT/'web'/filename).read_text(encoding='utf-8')
                    if filename=='index.html':
                        body=body.replace('高类本地固定引导；中类追加限制模板再调用云端；低类直接云端。明确方法求助但等级待确认时，也可提供受限提示，状态不更新。模板已发送不代表模型一定遵从。',
                            '当前使用需求感知支持：结合求助等级、当前需求和本地处理能力，选择本地提示、步骤核验或受约束云端解释。高类直接索答先给本地起步支持；中低类按已有尝试控制帮助范围，执行位置不与等级一一绑定。模板已发送不代表模型一定遵从。')
                    else:
                        body=body.replace('历史高信号保护仍生效；即使本轮求助方式改变，也可能继续走纯边缘。','历史高信号保护仍影响帮助范围；实际执行路径还取决于当前需求和本地能力。')
                        old="(state.evidence_turns<3?`累计趋势待更多有效记录（已有${state.evidence_turns}条，工程展示规则至少3条）；本轮检测结果已在上方显示。`:`本会话系统状态：${a.profile.trajectory}。这是程序估计，不能推出学习效果。`)"
                        new="(`已接纳 ${state.evidence_turns} 次有效更新。${a?.profile?.trajectory||'尚无有效状态记录'}。轨迹不直接代表学习效果。`)"
                        body=body.replace(old,new)
                    return self.send(200,body.encode('utf-8'),'text/html; charset=utf-8' if filename=='index.html' else 'text/javascript; charset=utf-8')
                except runtime.legacy.APIError as e:return self.send(e.status,{'error':e.message})
            if self.path=='/api/config':
                try:
                    self.validate()
                    from evidence_runtime import TASKS
                    return self.send(200,{'tasks':TASKS,'cutoff':service.state_config['cutoff'],'state_config':service.state_config,
                        'cloud':service.gateway.public(),'model_card':service.card,'routing_version':policy+'-20261118',
                        'medium_suffix':base.CONSTRAINED_SUFFIX,'protocol_scope':'demand-aware support; recognition/state retained'})
                except runtime.legacy.APIError as e:return self.send(e.status,{'error':e.message})
            return super().do_GET()
    return Handler

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8771);p.add_argument('--db',type=Path,required=True)
    p.add_argument('--policy',choices=['B3','revision'],default='B3');a=p.parse_args()
    assert 1024<=a.port<=65535
    from scripts.api_config import load_api_key
    load_api_key();runtime,Service=bootstrap(a.policy)
    a.db.parent.mkdir(parents=True,exist_ok=True);service=Service(a.db)
    server=runtime.ThreadingHTTPServer(('127.0.0.1',a.port),handler(runtime,service,a.port,a.policy))
    print(json.dumps({'url':f'http://127.0.0.1:{a.port}/','model':service.card['model_version'],'support':a.policy},ensure_ascii=False),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
