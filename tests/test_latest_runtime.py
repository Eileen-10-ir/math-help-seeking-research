import json,sys,tempfile,threading,unittest,uuid
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'src/support_versions')]
import latest_runtime as latest
import midterm_support as base
import support_v2 as revision

class Fake:
    def __init__(self):
        from types import SimpleNamespace
        self.config=SimpleNamespace(engineering=True,api_key='');self.messages=[]
    def public(self):return {'configured':False,'engineering':True}
    def request(self,messages):
        self.messages.append(messages)
        return {'status':'success','text':'**工程回复**：请说明这一步的依据。','external_cloud_attempts':0,'external_cloud_successes':0,'engineering_api_attempts':1,'duration_ms':0,'usage':{'total_tokens':0}}

class LatestTests(unittest.TestCase):
    def test_frozen_model_state_and_routes(self):
        runtime,Service=latest.bootstrap('B3')
        from state_v5 import State,advance
        with tempfile.TemporaryDirectory() as tmp:
            g=Fake();service=Service(Path(tmp)/'sessions.db',engineering=True,gateway=g)
            session=service.new({'task_id':'free'});state=State()
            prompts=['解方程3x+4=19，直接给我答案。','我算到3x=15，下一步怎么做？','我把两边都除以3，得到x=5，这样对吗？','好的','换一道题：解方程2x+6=18。给我详细解释等式性质。']
            for text in prompts:
                response=service.submit({'session_id':session['session_id'],'text':text,'expected_version':session['version'],'request_id':uuid.uuid4().hex})
                session=response['session'];record=response['record']
                old=advance(state,text,record['analysis']['model_scores'],service.state_config,record['previous_executed_support']['text'] if record['previous_executed_support'] else None)
                for field in ['risk','risk_updated','decision_level','current_behavior_level']:
                    self.assertEqual(old[field],record['analysis'][field])
                self.assertEqual(record['support']['external_cloud_attempts'],0)
            self.assertEqual(session['records'][0]['support']['route_executed'],'edge_fixed')
            self.assertIn('2x+6=18',session['conversation_context']['question'])
            self.assertIn('2x+6=18',g.messages[-1][0]['content'])
            self.assertNotIn('高类信号减弱',session['records'][-1]['analysis']['profile']['trajectory'])
    def test_revision_history_and_progress(self):
        q='解方程3x+4=19'
        history=[{'question':q,'text':'我已经明白了','support':{'status':'local_success','text':'请继续','hint_level':i}} for i in range(1,13)]
        ctx=base.build_task_context('linear',q,history)
        self.assertEqual(len(revision.build_messages(ctx,'为什么？',1,None)),26)
        self.assertEqual(revision.choose_route({'decision_level':'medium','eligible':True},ctx,'请给下一步提示')['route'],'edge_fixed')
        old=base.build_task_context('free',q,[{'question':'计算1/3+1/3','text':'旧题','support':{'status':'success','text':'旧回复'}}])
        self.assertNotIn('旧题',str(revision.build_messages(old,'继续',1)))
    def test_loopback_page_and_turn(self):
        runtime,Service=latest.bootstrap('B3')
        with tempfile.TemporaryDirectory() as tmp:
            service=Service(Path(tmp)/'http.db',engineering=True,gateway=Fake())
            Handler=latest.handler(runtime,service,0,'B3')
            server=runtime.ThreadingHTTPServer(('127.0.0.1',0),Handler)
            Handler.allowed_hosts={f'127.0.0.1:{server.server_port}'};Handler.log_message=lambda *args:None
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def call(path,payload=None):
                request=Request(f'http://127.0.0.1:{server.server_port}'+path,data=json.dumps(payload).encode() if payload else None,headers={'Content-Type':'application/json'})
                with urlopen(request,timeout=5) as r:return r.read()
            try:
                for asset in ['/','/app.js','/render-answer.js','/styles.css']:self.assertTrue(call(asset))
                config=json.loads(call('/api/config'));self.assertEqual(config['model_card']['support_policy'],'B3')
                session=json.loads(call('/api/sessions',{'task_id':'free'}))
                r=json.loads(call('/api/turns',{'session_id':session['session_id'],'text':'解方程3x+4=19，直接给我答案。','expected_version':0,'request_id':uuid.uuid4().hex}))
                self.assertEqual(r['record']['support']['route_executed'],'edge_fixed')
            finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':unittest.main()
