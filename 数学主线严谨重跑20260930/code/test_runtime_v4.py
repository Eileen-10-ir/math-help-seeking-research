"""Real loopback HTTP requests to isolated mock API; never calls a paid provider."""
from common import *
from runtime_server import Service,ThreadingHTTPServer,make_handler
from cloud_gateway import CloudConfig,CloudGateway
from routing_v4 import HIGH_REPLY,MEDIUM_SUFFIX,support
from runtime_state_v4 import State,advance
from http.server import BaseHTTPRequestHandler
from urllib.request import urlopen,Request
from urllib.error import HTTPError
import threading,tempfile,uuid,subprocess,time

def run():
 checks={};requests=[];temp=Path(__import__('tempfile').mkdtemp(prefix='math_v4_engineering_'))
 class Mock(BaseHTTPRequestHandler):
  def do_POST(self):
   payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append(payload)
   if any('ENGINEER_TIMEOUT' in m['content'] for m in payload['messages']):time.sleep(.15)
   if any('ENGINEER_HTTP_ERROR' in m['content'] for m in payload['messages']):
    self.send_response(429);self.end_headers();self.wfile.write(b'private-error-test-key');return
   content=json.dumps({'id':'engineering-response','model':'engineering-deepseek-flash','choices':[{'message':{'content':'工程假API回应：已收到你的数学问题。'},'finish_reason':'stop'}],'usage':{'prompt_tokens':20,'completion_tokens':12,'total_tokens':32}},ensure_ascii=False).encode()
   self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(content)));self.end_headers()
   try:self.wfile.write(content)
   except OSError:pass
  def log_message(self,*args):pass
 mock=ThreadingHTTPServer(('127.0.0.1',0),Mock);mt=threading.Thread(target=mock.serve_forever,daemon=True);mt.start()
 gateway=CloudGateway(CloudConfig(endpoint=f'http://127.0.0.1:{mock.server_port}/chat/completions',api_key='private-error-test-key',provider='本机工程假API',engineering=True,timeout=2))
 service=Service(temp/'engineering.sqlite3',engineering=True,gateway=gateway);handler=make_handler(service,0)
 server=ThreadingHTTPServer(('127.0.0.1',0),handler);handler.allowed_hosts={f'127.0.0.1:{server.server_port}',f'localhost:{server.server_port}'};handler.log_message=lambda *args:None
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url=f'http://127.0.0.1:{server.server_port}'
 def call(path,payload=None,status=200,origin=None):
  headers={'Content-Type':'application/json'}
  if origin:headers['Origin']=origin
  req=Request(url+path,data=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None,headers=headers)
  try:
   with urlopen(req,timeout=10) as r:code=r.status;result=json.loads(r.read())
  except HTTPError as e:code=e.code;result=json.loads(e.read())
  assert code==status,(path,code,result);return result
 def turn(s,text,rid=None,version=None,status=200):
  return call('/api/turns',{'session_id':s['session_id'],'text':text,'request_id':rid or uuid.uuid4().hex,'expected_version':s['version'] if version is None else version},status)
 try:
  state=State();cfg=service.state_config;p={'high':.1,'medium':.8,'low':.1};a=advance(state,'请说明方法',p,cfg)
  assert a['single_risk']==p['high'] and a['single_risk_source']=='raw_model_p_high';checks['raw_p_high_not_legacy_anchors']=True
  n=len(requests);high=advance(State(),'直接给我最终答案，我先写(x-2)(x-3)=0',{'high':.8,'medium':.1,'low':.1},cfg)
  h=support('直接给我最终答案，我先写(x-2)(x-3)=0','quadratic',{'question':'解方程x²−5x+6=0'},high,gateway,[])
  assert h['text']==HIGH_REPLY and h['route_executed']=='edge_fixed' and len(requests)==n;checks['high_fixed_no_cloud_no_math_bypass']=True
  medium=support('请解释方法','free',{},a,gateway,[])
  assert medium['status']=='success' and medium['route_executed']=='cloud_constrained' and requests[-1]['messages'][-1]['content']=='请解释方法\n\n'+MEDIUM_SUFFIX
  checks['medium_exact_suffix_real_HTTP_request']=True
  low=advance(State(),'什么是因式分解？',p,cfg);l=support('什么是因式分解？','free',{},low,gateway,[])
  assert l['route_executed']=='cloud_direct' and requests[-1]['messages'][-1]['content']=='什么是因式分解？' and not l['edge_suffix'];checks['low_original_prompt_direct_cloud']=True
  absent=support('什么是因式分解？','free',{},low,CloudGateway(CloudConfig()),[])
  assert absent['status']=='not_configured' and absent['external_cloud_attempts']==0 and absent['route_executed']=='cloud_unavailable';checks['not_configured_never_fakes_cloud_answer']=True
  err=support('ENGINEER_HTTP_ERROR','free',{},low,gateway,[])
  assert err['status']=='http_error' and err['http_status']==429 and 'private-error-test-key' not in json.dumps(err);checks['cloud_error_recorded_no_secret_no_auto_retry']=True
  timeout_gateway=CloudGateway(CloudConfig(endpoint=gateway.config.endpoint,api_key='private-error-test-key',provider='本机工程假API',engineering=True,timeout=.05))
  timed=support('ENGINEER_TIMEOUT','free',{},low,timeout_gateway,[])
  assert timed['status']=='network_error' and timed['engineering_api_attempts']==1 and timed['external_cloud_attempts']==0;checks['timeout_recorded_without_retry_or_fake_reply']=True
  s=call('/api/sessions',{},201);other=call('/api/sessions',{},201);rid=uuid.uuid4().hex
  ms=call('/api/sessions',{'task_id':'quadratic'},201);ms=turn(ms,'请教我第一步的方法')['session']
  mr=ms['records'][-1];assert mr['analysis']['decision_level']=='medium' and mr['support']['route_executed']=='cloud_constrained' and requests[-1]['messages'][-1]['content']=='请教我第一步的方法\n\n'+MEDIUM_SUFFIX
  checks['trained_classifier_HTTP_medium_route']=True
  s=turn(s,'什么是因式分解？',rid)['session'];before=len(requests);again=turn(s,'什么是因式分解？',rid,version=0)
  assert again['duplicate'] and len(requests)==before
  turn(s,'换一个文本',rid,status=409);turn(s,'请提示',version=0,status=409);checks['idempotent_paid_path_and_stale_guard']=True
  s=turn(s,'好的')['session'];assert s['state']['risk']==0 and s['records'][-1]['support']['external_cloud_attempts']==0
  s=turn(s,'2或3')['session'];assert s['state']['risk']==0 and not s['records'][-1]['analysis']['risk_updated'];checks['ACK_answer_only_keep_state_and_zero_API']=True
  s=turn(s,'我先写出(x-2)(x-3)=0，请检查这一步。')['session']
  assert s['records'][-1]['support']['route_executed']=='cloud_direct'
  messages=requests[-1]['messages'];assert any(m['role']=='assistant' and m['content']==s['records'][0]['support']['text'] for m in messages)
  checks['actual_previous_support_in_cloud_context']=True
  export=call('/api/export?id='+s['session_id']);assert export['records']==s['records'] and 'private-error-test-key' not in json.dumps(export,ensure_ascii=False)
  assert export['source']=='automated_engineering_check' and all(r['support']['external_cloud_attempts']==0 for r in export['records']);checks['export_audit_and_mock_provenance']=True
  assert call('/api/session?id='+other['session_id'])['version']==0;checks['sessions_isolated']=True
  turn(s,'',status=400);call('/api/sessions',{'task_id':'free'},403,origin='https://example.invalid');checks['invalid_input_and_foreign_origin']=True
  state=State();advance(state,'直接给我答案',p,cfg);assert state.risk==1
  q=advance(state,'我先写出3x=15，请检查依据。',p,cfg);assert state.risk==.5 and q['history_high_protection']
  q=advance(state,'我先写出3x=15，请检查依据。',p,cfg);assert state.risk==.25 and q['decision_level']=='low';checks['EWMA_history_protection_and_release']=True
  state=State();d=advance(state,'不要给我答案，但是直接给我最终答案。',p,cfg);assert not d['eligible'] and state.risk is None
  d=advance(state,'请提示方法',p,cfg,previous_support='请提示方法');assert not d['eligible'];checks['conflict_and_exact_copy_hold']=True
  try:
   second=ThreadingHTTPServer(('127.0.0.1',server.server_port),handler);second.server_close();raise AssertionError('duplicate bind allowed')
  except OSError:checks['exclusive_binding']=True
  node=Path('C:/Users/iridescent/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
  r=subprocess.run([str(node),str(OUT/'code/qa_runtime_v4.cjs'),url],capture_output=True,text=True,encoding='utf-8',timeout=120)
  print(r.stdout,flush=True)
  if r.returncode:raise RuntimeError(r.stderr)
  write_json('results/v4_HTTP云边验收.json',{'passed':True,'checks':checks,'source':'automated_engineering_check','API_provider_tested':'isolated loopback mock, not DeepSeek live',
   'engineering_requests':len(requests),'external_paid_calls':0,'new_real_students':0,'cloud_instruction_compliance_validated':False})
  print(f'{len(checks)} v4 checks and browser passed; no external paid calls.',flush=True)
 finally:server.shutdown();server.server_close();mock.shutdown();mock.server_close();thread.join(3);mt.join(3)
if __name__=='__main__':run()
