"""Candidate service, loaded only in a separate process; frozen core is unchanged."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from run import WORK, CURRENT, sync_sources
from conversation_memory import EvidenceMemory, persist_memory
from memory_support import make_support, VERSION, CONTINUATION_VERSION, REFINED_VERSION


def bootstrap(mode='graph', continuation_help=False, refined_guidance=False):
    sync_sources()
    sys.path.insert(0,str(WORK/CURRENT/'code'))
    import runtime_current as runtime
    import runtime_server as legacy
    from routing_v8 import support as previous_support
    legacy.support = make_support(previous_support, mode=mode, continuation_help=continuation_help,refined_guidance=refined_guidance)

    class MemoryService(runtime.ConversationService):
        def get(self, sid):
            session = super().get(sid)
            question = session['task'].get('question','') if session['task_id']!='free' else ''
            memory = EvidenceMemory.from_records(session['records'], question=question)
            session['evidence_memory'] = memory.export()
            active = memory.view()['active_problem']
            session['conversation_context'] = {'question':active['text'] if active else '', 'source':'evidence_memory_current_problem'}
            session['support_policy_version'] = REFINED_VERSION if refined_guidance else CONTINUATION_VERSION if continuation_help else VERSION
            return session

        def submit(self, payload):
            response = super().submit(payload)
            session = response['session']
            question = session['task'].get('question','') if session['task_id']!='free' else ''
            memory = EvidenceMemory.from_records(session['records'], question=question)
            persist_memory(self.db,session['session_id'],session['version'],memory)
            return response

    return runtime, MemoryService


def make_handler(runtime, service, port, mode='graph', continuation_help=False, refined_guidance=False):
    base = runtime.handler(service,port)
    class Handler(base):
        def do_GET(self):
            if self.path in ('/comparison','/previous-comparison'):
                try:
                    self.validate()
                    locations={'/comparison':ROOT.parents[1]/'连续辅导故障修复20261022/七轮连续对话对照.html',
                        '/previous-comparison':ROOT.parents[1]/'对话记忆实现与验证20261022/新旧回复对照.html'}
                    path=locations[self.path]
                    if not path.is_file():return self.send(404,{'error':'本机尚未生成这份开发对照报告'})
                    body=path.read_text(encoding='utf-8').replace('../Git协作准备20261018/数学项目代码仓库/web/','/')
                    return self.send(200,body.encode('utf-8'),'text/html; charset=utf-8')
                except runtime.legacy.APIError as e:return self.send(e.status,{'error':e.message})
            if self.path=='/comparison-render.js':
                try:
                    self.validate()
                    return self.send(200,(ROOT/'web/comparison-render.js').read_bytes(),'text/javascript; charset=utf-8')
                except runtime.legacy.APIError as e:return self.send(e.status,{'error':e.message})
            if self.path=='/app.js':
                try:
                    self.validate()
                    body=(WORK/CURRENT/'app/app.js').read_bytes()+b'\n'+(ROOT/'web/memory-extension.js').read_bytes()
                    return self.send(200,body,'text/javascript; charset=utf-8')
                except runtime.legacy.APIError as e:return self.send(e.status,{'error':e.message})
            if self.path=='/api/config':
                try:
                    self.validate()
                    from evidence_runtime import TASKS
                    from routing_v8 import MEDIUM_SUFFIX
                    from memory_support import REFINED_SUFFIX
                    return self.send(200,{'tasks':TASKS,'state_config':service.state_config,
                         'cloud':service.gateway.public(),'model_card':service.card,
                         'routing_version':REFINED_VERSION if refined_guidance else CONTINUATION_VERSION if continuation_help else VERSION,
                         'medium_suffix':REFINED_SUFFIX if refined_guidance else MEDIUM_SUFFIX,'candidate_memory_mode':mode,
                         'continuation_help':continuation_help,'refined_guidance':refined_guidance})
                except runtime.legacy.APIError as e:return self.send(e.status,{'error':e.message})
            return super().do_GET()
    return Handler


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--port',type=int,default=8772)
    p.add_argument('--db',type=Path,required=True)
    p.add_argument('--mode',choices=['recent','summary','graph'],default='graph')
    p.add_argument('--continuation-help',action='store_true')
    p.add_argument('--refined-guidance',action='store_true')
    a=p.parse_args()
    assert 1024<=a.port<=65535
    from scripts.api_config import load_api_key
    load_api_key()
    runtime, Service = bootstrap(a.mode,a.continuation_help,a.refined_guidance)
    service = Service(a.db)
    server=runtime.ThreadingHTTPServer(('127.0.0.1',a.port),make_handler(runtime,service,a.port,a.mode,a.continuation_help,a.refined_guidance))
    print(json.dumps({'url':f'http://127.0.0.1:{a.port}/','memory_mode':a.mode,
                      'continuation_help':a.continuation_help,'classifier_changed':False,
                      'state_changed':False,'cloud_configured':service.gateway.public()['configured']},ensure_ascii=False),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
