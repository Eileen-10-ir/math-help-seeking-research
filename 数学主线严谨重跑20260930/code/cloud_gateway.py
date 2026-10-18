"""Bounded DeepSeek Chat Completions adapter. Secret is never in public records."""
from dataclasses import dataclass,field
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError,URLError
from urllib.parse import urlparse
import os,json,time,socket

class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

@dataclass
class CloudConfig:
 endpoint:str='https://api.deepseek.com/chat/completions'
 model:str='deepseek-flash'
 api_key:str=field(default='',repr=False)
 timeout:float=30.
 max_tokens:int=768
 provider:str='DeepSeek'
 engineering:bool=False

class CloudGateway:
 def __init__(self,config=None):
  self.config=config or CloudConfig(api_key=os.environ.get('MATH_DEEPSEEK_API_KEY',''),model=os.environ.get('MATH_DEEPSEEK_MODEL','deepseek-flash'),endpoint=os.environ.get('MATH_DEEPSEEK_ENDPOINT','https://api.deepseek.com/chat/completions'))
  c=self.config;u=urlparse(c.endpoint)
  allowed=(u.scheme=='https' and u.hostname=='api.deepseek.com' and u.path in ['/chat/completions','/v1/chat/completions'] and u.port in [None,443])
  if c.engineering:allowed=allowed or (u.scheme=='http' and u.hostname=='127.0.0.1')
  if not allowed or u.username or u.password or u.query or u.fragment:raise ValueError('Cloud endpoint must be the official DeepSeek HTTPS chat endpoint; loopback is for engineering tests only')
  if not 0<c.timeout<=60 or not 1<=c.max_tokens<=4096:raise ValueError('Invalid bounded cloud configuration')
 def public(self):
  c=self.config;return {'configured':bool(c.api_key),'provider':c.provider,'model_requested':c.model,'endpoint':c.endpoint,
   'thinking':'disabled','temperature':.2,'max_tokens':c.max_tokens,'timeout_seconds':c.timeout,'engineering':c.engineering,
   'status':'ready_to_attempt_not_connection_verified' if c.api_key else 'not_configured'}
 def request(self,messages):
  c=self.config;record={'provider':c.provider,'model_requested':c.model,'model_returned':None,'endpoint':c.endpoint,'messages_sent':messages,
   'external_cloud_attempts':0,'external_cloud_successes':0,'engineering_api_attempts':0,'status':'not_configured','duration_ms':0.,'usage':None,
   'request_parameters':{'thinking':{'type':'disabled'},'temperature':.2,'max_tokens':c.max_tokens,'stream':False}}
  if not c.api_key:return {**record,'text':'这一回合应调用云端，但尚未配置API密钥，因此没有发送请求或生成云端回答。请配置后新建会话继续。'}
  record['engineering_api_attempts' if c.engineering else 'external_cloud_attempts']=1
  payload={'model':c.model,'messages':messages,**record['request_parameters']};req=Request(c.endpoint,data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+c.api_key},method='POST')
  t=time.perf_counter()
  try:
   with build_opener(NoRedirect).open(req,timeout=c.timeout) as response:
    raw=response.read(2_000_001)
   if len(raw)>2_000_000:raise ValueError('oversized response')
   data=json.loads(raw);choice=data['choices'][0];reply=choice['message']['content']
   if not isinstance(reply,str) or not reply.strip():raise ValueError('empty text response')
   record.update(status='success',text=reply,model_returned=data.get('model'),usage=data.get('usage'),finish_reason=choice.get('finish_reason'),request_id=data.get('id'))
   if not c.engineering:record['external_cloud_successes']=1
  except HTTPError as e:
   record.update(status='http_error',http_status=e.code,text=f'云端请求返回HTTP {e.code}，本回合未获得有效回答。未自动重试，也未替换为本地题解。')
  except (URLError,TimeoutError,socket.timeout):record.update(status='network_error',text='云端网络请求失败或超时。本回合未获得有效回答；未自动重试。')
  except (ValueError,KeyError,IndexError,TypeError):record.update(status='invalid_response',text='云端返回格式异常，本回合未获得有效文本回答；未自动重试。')
  record['duration_ms']=(time.perf_counter()-t)*1000
  return record
