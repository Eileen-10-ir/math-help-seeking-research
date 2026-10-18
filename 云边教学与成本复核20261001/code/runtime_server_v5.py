"""v5 review prototype; frozen v4 data/state/code preserved. Keys remain memory-only."""
from pathlib import Path
import sys,json,re,threading,copy,hashlib,argparse
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE.parent/'数学主线严谨重跑20260930/code'))
import runtime_server as legacy
from common import LAB,ACK
from runtime_state_v4 import State,advance
from cloud_gateway import CloudGateway,CloudConfig
from evidence_runtime import TASKS
from routing_v5 import support,ROUTING_VERSION
from routing_v4 import HIGH_REPLY,support as frozen_support
legacy.support=support  # Only this new process uses v5; v4 source/runtime stay unchanged.

class ReviewService(legacy.Service):
 def __init__(self,db,engineering=False,gateway=None):
  super().__init__(db,engineering,gateway);self.engineering=engineering
  self.protocol_path=BASE/'data/E13_cost_guidance_protocol_v2.json';self.protocol=json.loads(self.protocol_path.read_text(encoding='utf-8'))
  self.protocol_sha=hashlib.sha256(self.protocol_path.read_bytes()).hexdigest();self.bench_path=Path(db).parent/'E13_actual_api_records.json'
  self.bench=json.loads(self.bench_path.read_text(encoding='utf-8')) if self.bench_path.exists() else {}
 def benchmark(self,payload):
  cases={c['id']:c for c in self.protocol['cases']};cid=payload.get('case_id');arm=payload.get('arm');block=payload.get('block')
  if cid not in cases or arm not in self.protocol['arms'] or type(block) is not int or block not in [1,2] or payload.get('protocol_sha256')!=self.protocol_sha:
   raise legacy.APIError(400,'实验请求不符合冻结协议')
  key=f'{cid}:{arm}:{block}'
  with self.lock:
   if key in self.bench:return {'record':self.bench[key],'duplicate':True}
   if not self.gateway.public()['configured']:raise legacy.APIError(409,'需要先在本机配置API；尚未进行实验调用')
   case=cases[cid];text=case['text'];labels=LAB if case['stage']=='first' else LAB+[ACK]
   scores=dict(zip(labels,map(float,self.models['first' if case['stage']=='first' else 'following'].probs([text],labels)[0])))
   state=State(risk=1,evidence_turns=1,events=1,risks=[1],last_evidence_level='high') if case['prior_high'] else State()
   result=advance(state,text,scores,self.state_config);history=[]
   if case['prior_high']:history=[{'text':'直接给我这道题的最终答案。','support':{'status':'local_success','text':HIGH_REPLY}}]
   if arm=='C':reply=support(text,case['task'],TASKS[case['task']],result,self.gateway,history)
   elif result['observed_event']!='question':reply=frozen_support(text,case['task'],TASKS[case['task']],{**result,'eligible':False},self.gateway,history)
   elif arm=='D':reply=support(text,case['task'],TASKS[case['task']],{**result,'eligible':True,'decision_level':'high'},self.gateway,history)
   else:reply=frozen_support(text,case['task'],TASKS[case['task']],{**result,'eligible':True,'decision_level':'low' if arm=='A' else 'medium','history_high_protection':False},self.gateway,history)
   record={'source':'engineered_fixed_case_API_benchmark_not_student','case_id':cid,'arm':arm,'block':block,'text':text,'task_id':case['task'],
    'protocol_sha256':self.protocol_sha,'model_version':self.card['model_version'],'state_rule_version':self.card['rule_version'],'support_policy_version':ROUTING_VERSION,
    'initial_state_constructed':case['prior_high'],'analysis_same_across_arms':result,'support':reply,'human_math_quality':None,'human_hint_utility':None,'human_answer_leakage':None}
   self.bench[key]=record;self.bench_path.write_text(json.dumps(self.bench,ensure_ascii=False,indent=2),encoding='utf-8')
   return {'record':record,'duplicate':False}

def handler(service,port):
 Parent=legacy.make_handler(service,port)
 class Handler(Parent):
  def do_GET(self):
   try:
    self.validate()
    if self.path=='/api/config':return self.send(200,{'tasks':TASKS,'cutoff':service.state_config['cutoff'],'mu':service.state_config['lambda'],
     'state_config':service.state_config,'cloud':service.gateway.public(),'routing_version':ROUTING_VERSION,'model_card':service.card,
     'hint_bridge_policy':'明确方法求助可获受限云提示，依赖状态保持；不改判中/低类','protocol_sha256':service.protocol_sha})
    if self.path in ['/','/app.js','/styles.css']:
     name,mime={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/styles.css':('styles.css','text/css; charset=utf-8')}[self.path]
     return self.send(200,(BASE/'app'/name).read_bytes(),mime)
    if self.path=='/api/benchmark-records':return self.send(200,{'protocol_sha256':service.protocol_sha,'records':list(service.bench.values()),'source':'engineering_API_benchmark'})
    return super().do_GET()
   except legacy.APIError as e:self.send(e.status,{'error':e.message})
  def do_POST(self):
   if self.path not in ['/api/cloud-config','/api/benchmark-case']:return super().do_POST()
   try:
    n=int(self.headers.get('Content-Length','0'));raw=self.rfile.read(n) if 0<n<=20000 else b'';self.validate()
    if not self.headers.get('Content-Type','').startswith('application/json') or not 0<n<=20000:raise legacy.APIError(400,'需要有效JSON输入')
    p=json.loads(raw)
    if not isinstance(p,dict):raise legacy.APIError(400,'输入格式错误')
    if self.path=='/api/benchmark-case':return self.send(200,service.benchmark(p))
    key=p.get('api_key','')
    if not isinstance(key,str) or not re.fullmatch(r'sk-[A-Za-z0-9_-]{16,200}',key):raise legacy.APIError(400,'密钥格式不符合官方接口；请在本机重新输入')
    if service.engineering:raise legacy.APIError(403,'工程假API验收不接收真实密钥')
    with service.lock:service.gateway=CloudGateway(CloudConfig(api_key=key))
    key=None;p.clear();raw=b''
    return self.send(200,{'configured':True,'cloud':service.gateway.public(),'saved_to_disk':False,'connection_verified':False})
   except legacy.APIError as e:self.send(e.status,{'error':e.message})
   except (ValueError,TypeError,UnicodeError):self.send(400,{'error':'输入格式错误'})
 return Handler

def main():
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8767);p.add_argument('--db',default=str(BASE/'runtime/operator.sqlite3'));args=p.parse_args()
 service=ReviewService(args.db);server=legacy.ThreadingHTTPServer(('127.0.0.1',args.port),handler(service,args.port))
 print(f'v5 hint review: http://127.0.0.1:{args.port}/ | cloud configured: {service.gateway.public()["configured"]}',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:server.server_close()
if __name__=='__main__':main()
