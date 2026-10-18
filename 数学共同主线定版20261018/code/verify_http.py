"""Actual loopback HTTP and route checks; isolated mock cannot spend API credits."""
import sys,os,json,argparse,threading,uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler
from urllib.request import Request,urlopen
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
sys.path.insert(0,str(OUT/'code'))
os.environ['NO_PROXY']='127.0.0.1,localhost';os.environ['no_proxy']='127.0.0.1,localhost'
from runtime_current import ConversationService,handler,ThreadingHTTPServer
from cloud_gateway import CloudGateway,CloudConfig
from state_v5 import State,advance,RULE_VERSION
from routing_v7 import support,MEDIUM_SUFFIX
from evidence_runtime import TASKS

def main(dest):
    dest.mkdir(parents=True,exist_ok=False);requests=[]
    class Mock(BaseHTTPRequestHandler):
        def do_POST(self):
            payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append(payload)
            body=json.dumps({'model':'isolated-engineering-mock','choices':[{'message':{'content':'**工程提示**：先说明这一步的依据。'},'finish_reason':'stop'}],
                'usage':{'prompt_tokens':20,'completion_tokens':12,'total_tokens':32}},ensure_ascii=False).encode()
            self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def log_message(self,*args):pass
    mock=ThreadingHTTPServer(('127.0.0.1',0),Mock);threading.Thread(target=mock.serve_forever,daemon=True).start();server=None
    try:
        gateway=CloudGateway(CloudConfig(endpoint=f'http://127.0.0.1:{mock.server_port}/chat/completions',api_key='isolated-placeholder',engineering=True))
        service=ConversationService(dest/'工程会话.sqlite3',engineering=True,gateway=gateway)
        assert service.card['model_version']=='math-joint-v2-state5-20261018' and service.state_config['rule_version']==RULE_VERSION
        checks={}
        # Test state-generated levels through the real support module, then force only
        # medium once to exercise its wire suffix independently of classifier correctness.
        for text,wanted in [('直接给我答案。','high'),('什么是因式分解？','low')]:
            a=advance(State(),text,{'high':.1,'medium':.8,'low':.1},service.state_config)
            assert a['decision_level']==wanted
            reply=support(text,'quadratic',TASKS['quadratic'],a,gateway,[])
            assert reply['route_executed']==('edge_fixed' if wanted=='high' else 'cloud_direct')
            assert reply['external_cloud_attempts']==0;checks[wanted+'_actual_state_route']=True
        a=advance(State(),'请提供起步思路。',{'high':.1,'medium':.8,'low':.1},service.state_config)
        reply=support('请提供起步思路。','quadratic',TASKS['quadratic'],a,gateway,[])
        assert reply['route_executed']=='cloud_constrained' and requests[-1]['messages'][-1]['content']=='请提供起步思路。\n\n'+MEDIUM_SUFFIX
        checks['medium_suffix_transmitted']=True
        state=State();advance(state,'直接给我答案。',{'high':.8,'medium':.1,'low':.1},service.state_config)
        a=advance(state,'我先写出(x-2)(x-3)=0，请检查这一步的依据。',{'high':.1,'medium':.2,'low':.7},service.state_config)
        assert a['decision_level']=='low'
        assert abs(a['risk']-.35)<1e-12;checks['new_evidence_updates_and_releases']=True
        state=State();advance(state,'直接给我答案。',{'high':.8,'medium':.1,'low':.1},service.state_config)
        a=advance(state,'请分析当前这一步的思路。',{'high':.49,'medium':.51,'low':0.},service.state_config)
        b=advance(state,'请解释当前这一步的依据。',{'high':.49,'medium':.51,'low':0.},service.state_config)
        assert a['decision_level']=='high' and b['risk']>.5 and b['decision_level']=='medium' and b['history_release_applied']
        checks['history_release_without_risk_reset']=True
        Handler=handler(service,0);server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        Handler.allowed_hosts={f'127.0.0.1:{server.server_port}',f'localhost:{server.server_port}'};Handler.log_message=lambda *args:None
        threading.Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}'
        def call(path,payload=None):
            req=Request(base+path,data=None if payload is None else json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json'})
            with urlopen(req,timeout=10) as response:raw=response.read()
            return json.loads(raw) if path.startswith('/api/') else raw
        for asset in ['/','/app.js','/render-answer.js','/styles.css','/vendor/marked.umd.js','/vendor/katex/dist/katex.min.js','/vendor/dompurify/dist/purify.min.js']:
            assert call(asset)
        config=call('/api/config');assert config['state_config']['stage_cutoffs']=={'R1':.45,'R3':.5}
        session=call('/api/sessions',{'task_id':'free'})
        sequence=['解方程x^2-5x+6=0，可以给我一些思路吗？',
            '老师说过因式分解，但是我不知道怎么找那两个数，给我一个例子回忆一下。',
            '我先写出(x-2)(x-3)=0，请检查这一步的依据。','好的',
            '这一步为什么可以分别令两个因式为零？']
        for text in sequence:
            answer=call('/api/turns',{'session_id':session['session_id'],'text':text,'request_id':uuid.uuid4().hex,'expected_version':session['version']})
            session=answer['session'];assert answer['record']['support']['external_cloud_attempts']==0
        records=session['records'];assert len(records)==5
        assert records[0]['model_stage']=='R1_three_class' and all(r['model_stage']=='R3_four_class' for r in records[1:])
        assert records[1]['previous_executed_support']==records[0]['support']
        assert 'x^2-5x+6=0' in session['conversation_context']['question']
        assert not records[3]['analysis']['risk_updated'] and records[3]['analysis']['risk']==records[2]['analysis']['risk']
        assert records[2]['analysis']['decision_level']=='low'
        assert all('non_high_evidence_streak' in r['analysis'] for r in records)
        assert call('/api/export?id='+session['session_id'])['records']==records
        # Idempotence also holds after new State serialization and deserialization.
        duplicate=call('/api/turns',{'session_id':session['session_id'],'text':sequence[-1],'request_id':records[-1]['request_id'],'expected_version':4})
        assert duplicate['duplicate'] and duplicate['session']['version']==5
        checks.update(frontend_local_resources=True,continuous_five_turn_HTTP=True,problem_retained=True,
            actual_history_retained=True,ACK_keeps_state=True,new_state_serialization=True,idempotent_submission=True,export=True)
        proof={'passed':True,'checks':checks,'model':service.card['model_version'],'state_rule':RULE_VERSION,
            'paid_calls':0,'mock_requests':len(requests),'new_students':0,'session':session,
            'scope':'engineering HTTP validation, not real cloud quality or student behavior'}
        (dest/'HTTP验收.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in proof.items() if k!='session'},ensure_ascii=False))
    finally:
        if server:server.shutdown();server.server_close()
        mock.shutdown();mock.server_close()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();main(a.output_dir)
