"""Loopback UI, local classification and auditable DeepSeek three-path support."""
from common import OUT,Classifier,sha,LAB,ACK,F
from evidence_runtime import TASKS
from runtime_state_v4 import State,advance,RULE_VERSION
from routing_v4 import support,ROUTING_VERSION,MEDIUM_SUFFIX
from cloud_gateway import CloudGateway
from dataclasses import asdict
from pathlib import Path
from http.server import ThreadingHTTPServer as BaseThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from datetime import datetime,timezone,timedelta
import json,joblib,sqlite3,threading,uuid,time,argparse,sys,os,socket
from contextlib import contextmanager

class ThreadingHTTPServer(BaseThreadingHTTPServer):
 # Windows SO_REUSEADDR can allow two listeners with different loaded rule versions.
 allow_reuse_address=False
 def server_bind(self):
  if os.name=='nt':self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
  super().server_bind()

class APIError(Exception):
 def __init__(self,status,message):self.status=status;self.message=message

class Service:
 def __init__(self,db,engineering=False,gateway=None):
  self.card=json.loads((OUT/'data/runtime_model_card.json').read_text(encoding='utf-8'))
  artifact=OUT/'data/runtime_models_v1.joblib'
  assert sha(artifact)==self.card['artifact_sha256']
  assert sha(OUT/'data/anonymous_samples_snapshot.json')==self.card['snapshot_sha256']
  assert self.card['rule_version']==RULE_VERSION
  self.state_config=json.loads((OUT/'data/runtime_state_config_v4.json').read_text(encoding='utf-8'))
  assert self.card['state_config_sha256']==sha(OUT/'data/runtime_state_config_v4.json') and self.state_config['rule_version']==RULE_VERSION
  self.gateway=gateway or CloudGateway()
  if engineering and not self.gateway.config.engineering and self.gateway.config.api_key:raise ValueError('Engineering service may not spend external API credits')
  self.models=joblib.load(artifact);self.lock=threading.RLock();self.db=Path(db);self.db.parent.mkdir(exist_ok=True);self.source='automated_engineering_check' if engineering else 'operator_entered_live'
  with self.connect() as c:
   c.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, task_id TEXT NOT NULL, model_version TEXT NOT NULL, rule_version TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL, version INTEGER NOT NULL)')
   c.execute('CREATE TABLE IF NOT EXISTS turns (session_id TEXT NOT NULL, turn INTEGER NOT NULL, request_id TEXT NOT NULL, record TEXT NOT NULL, PRIMARY KEY(session_id,turn), UNIQUE(session_id,request_id), FOREIGN KEY(session_id) REFERENCES sessions(id))')
   if 'recording_context' not in [r['name'] for r in c.execute('PRAGMA table_info(sessions)')]:c.execute("ALTER TABLE sessions ADD COLUMN recording_context TEXT NOT NULL DEFAULT 'operator_entered_live'")
  # Warm both pipelines without creating a participant or session.
  self.models['first'].probs(['请教我第一步的方法']);self.models['following'].probs(['我试了一步，请检查依据'],LAB+[ACK])
 @contextmanager
 def connect(self):
  c=sqlite3.connect(self.db,timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
  try:
   with c:yield c
  finally:c.close()
 def now(self):return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
 def new(self,payload):
  task=payload.get('task_id','free')
  if task not in TASKS:raise APIError(400,'请选择支持的数学任务')
  sid=uuid.uuid4().hex
  with self.lock,self.connect() as c:
   c.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?)',(sid,task,self.card['model_version'],RULE_VERSION,json.dumps(asdict(State())),self.now(),0,self.source))
  return self.get(sid)
 def get(self,sid):
  if not isinstance(sid,str) or not __import__('re').fullmatch(r'[0-9a-f]{32}',sid):raise APIError(400,'无效会话编号')
  with self.lock,self.connect() as c:
   s=c.execute('SELECT * FROM sessions WHERE id=?',(sid,)).fetchone()
   if not s:raise APIError(404,'会话不存在，请新建')
   records=[json.loads(r['record']) for r in c.execute('SELECT record FROM turns WHERE session_id=? ORDER BY turn',(sid,))]
  return {'session_id':sid,'task_id':s['task_id'],'task':TASKS[s['task_id']],'created_at':s['created_at'],'version':s['version'],
   'model_version':s['model_version'],'rule_version':s['rule_version'],'records':records,'state':json.loads(s['state']),
   'recording_context':s['recording_context'],'source':s['recording_context'],'scope':'现场操作者或工程检查输入；身份与学生年级未验证，不自动计为研究被试或教育效果证据'}
 def submit(self,payload):
  sid=payload.get('session_id');text=payload.get('text');rid=payload.get('request_id');version=payload.get('expected_version')
  if not isinstance(text,str) or not text.strip():raise APIError(400,'请输入数学问题、尝试或回应')
  text=text.strip()
  if len(text)>2000:raise APIError(400,'每条输入最多2000字')
  if not isinstance(rid,str) or not __import__('re').fullmatch(r'[A-Za-z0-9_-]{8,80}',rid):raise APIError(400,'缺少有效提交编号')
  if isinstance(version,bool) or not isinstance(version,int) or version<0:raise APIError(400,'无效会话版本')
  # Serializes inference + state mutation. This prototype has one local instructor session workload.
  with self.lock,self.connect() as c:
   session=self.get(sid)
   if session['model_version']!=self.card['model_version'] or session['rule_version']!=RULE_VERSION:raise APIError(409,'模型或规则已更新，请新建会话')
   duplicate=c.execute('SELECT record FROM turns WHERE session_id=? AND request_id=?',(sid,rid)).fetchone()
   if duplicate:
    previous=json.loads(duplicate['record'])
    if previous['text']!=text:raise APIError(409,'同一提交编号不能用于不同文本')
    return {'session':session,'duplicate':True,'record':previous}
   if version!=session['version']:raise APIError(409,'会话已有新回合，请刷新后重试')
   t0=time.perf_counter();index=session['version'];state=State(**session['state'])
   model=self.models['first' if index==0 else 'following'];labels=LAB if index==0 else LAB+[ACK]
   t1=time.perf_counter();p=model.probs([text],labels)[0];scores=dict(zip(labels,map(float,p)));inference_ms=(time.perf_counter()-t1)*1000
   preceding=session['records'][-1]['support'] if session['records'] else None
   result=advance(state,text,scores,self.state_config,previous_support=preceding['text'] if preceding else None)
   result['lexical_clues']=[{'name':name,'matches':list(dict.fromkeys(p for key in keys for p in F._INTENT_PATTERNS[key] if p in text))[:4]} for name,keys in [
    ('索答或完整过程词句',['ask_direct_answer','ask_full_solution']),('方法或提示词句',['ask_method','ask_hint']),
    ('尝试或思路词句',['has_attempt','has_reasoning']),('具体卡点词句',['has_specific_stuck_point']),('拒绝代答词句',['explicit_dont_give_answer'])]]
   executed=support(text,session['task_id'],session['task'],result,self.gateway,session['records'])
   record={'turn':index+1,'text':text,'entered_at':self.now(),'source':session['recording_context'],'task_id':session['task_id'],
    'model_stage':'R1_three_class' if index==0 else 'R3_four_class','model_version':self.card['model_version'],'rule_version':RULE_VERSION,
    'request_id':rid,'previous_executed_support':preceding,'analysis':result,'support':executed,
    'timing':{'model_ms':inference_ms,'analysis_and_support_ms':(time.perf_counter()-t0)*1000},
    'history_used':'累计状态；R3分类器只读当前文本，上一条实际支持用于明确复述检查和审计'}
   c.execute('INSERT INTO turns VALUES (?,?,?,?)',(sid,index+1,rid,json.dumps(record,ensure_ascii=False)))
   c.execute('UPDATE sessions SET state=?,version=? WHERE id=?',(json.dumps(asdict(state),ensure_ascii=False),index+1,sid));c.commit()
   return {'session':self.get(sid),'record':record,'duplicate':False}

def make_handler(service,port):
 class Handler(BaseHTTPRequestHandler):
  allowed_hosts={f'127.0.0.1:{port}',f'localhost:{port}'}
  def validate(self):
   if self.headers.get('Host') not in self.allowed_hosts:raise APIError(403,'仅允许本机地址')
   origin=self.headers.get('Origin')
   if origin and origin not in {f'http://{h}' for h in self.allowed_hosts}:raise APIError(403,'来源不匹配')
  def send(self,status,data,kind='application/json; charset=utf-8',filename=None):
   content=json.dumps(data,ensure_ascii=False).encode('utf-8') if isinstance(data,(dict,list)) else data
   self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(content)))
   self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
   self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
   if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
   self.end_headers();self.wfile.write(content)
  def do_GET(self):
   try:
    self.validate();u=urlparse(self.path);q=parse_qs(u.query)
    if u.path=='/api/health':return self.send(200,{'ready':True,'model_version':service.card['model_version'],'rule_version':RULE_VERSION,'cloud_enabled':service.gateway.public()['configured'],'cloud':service.gateway.public()})
    if u.path=='/api/config':return self.send(200,{'tasks':TASKS,'cutoff':service.state_config['cutoff'],'mu':service.state_config['lambda'],'state_config':service.state_config,'cloud':service.gateway.public(),'routing_version':ROUTING_VERSION,'medium_suffix':MEDIUM_SUFFIX,'model_card':service.card,
        'offline_reference':{'r1_macro_f1':.655,'r3_macro_f1':.611,'r3_high_recall':.314,'n_students':47}})
    if u.path in ['/api/session','/api/export']:
     sid=q.get('id',[''])[0];s=service.get(sid)
     return self.send(200,s,filename=f'math_session_{sid[:8]}.json' if u.path=='/api/export' else None)
    assets={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/styles.css':('styles.css','text/css; charset=utf-8')}
    if u.path not in assets:raise APIError(404,'页面不存在')
    name,mime=assets[u.path];return self.send(200,(OUT/'app'/name).read_bytes(),mime)
   except APIError as e:self.send(e.status,{'error':e.message})
   except Exception as e:print(type(e).__name__,str(e),file=sys.stderr,flush=True);self.send(500,{'error':'服务异常，请查看本机运行日志'})
  def do_POST(self):
   try:
    try:n=int(self.headers.get('Content-Length','0'))
    except ValueError:raise APIError(400,'无效请求长度')
    # Consume a bounded body before rejecting its origin; otherwise Windows may
    # reset the connection with unread request bytes and hide the 403 response.
    raw=self.rfile.read(n) if 0<n<=20000 else b''
    self.validate()
    if not self.headers.get('Content-Type','').startswith('application/json'):raise APIError(415,'需要JSON输入')
    if not 0<n<=20000:raise APIError(413,'请求为空或过长')
    try:payload=json.loads(raw)
    except (ValueError,UnicodeError):raise APIError(400,'无效JSON')
    if not isinstance(payload,dict):raise APIError(400,'请求格式错误')
    if self.path=='/api/sessions':return self.send(201,service.new(payload))
    if self.path=='/api/turns':return self.send(200,service.submit(payload))
    raise APIError(404,'接口不存在')
   except APIError as e:self.send(e.status,{'error':e.message})
   except Exception as e:print(type(e).__name__,str(e),file=sys.stderr,flush=True);self.send(500,{'error':'服务异常，请查看本机运行日志'})
  def log_message(self,format,*args):print(self.log_date_time_string(),format%args,flush=True)
 return Handler

def main():
 p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);p.add_argument('--db',default=str(OUT/'runtime/现场会话记录.sqlite3'));p.add_argument('--engineering-check',action='store_true');args=p.parse_args()
 if not 1024<=args.port<=65535:raise ValueError('Use an unprivileged port')
 service=Service(args.db,args.engineering_check);server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(service,args.port))
 print(f'Math prototype ready: http://127.0.0.1:{args.port}/ | cloud configured: {service.gateway.public()["configured"]}',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:server.server_close()
if __name__=='__main__':main()
