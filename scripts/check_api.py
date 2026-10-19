"""Read-only configuration status; --probe explicitly performs at most one small call."""
from pathlib import Path
import argparse,sys,json,os,uuid
from api_config import ROOT,load_api_key

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--probe',action='store_true',help='明确执行一次真实小请求，不自动重试');a=p.parse_args()
    source=load_api_key()
    sys.path.insert(0,str(ROOT/'src/frozen_core/数学主线严谨重跑20260930/code'))
    from cloud_gateway import CloudConfig,CloudGateway
    card=ROOT/'.private/workspace/数学共同主线定版20261018/data/runtime_model_card.json'
    model=json.loads(card.read_text(encoding='utf-8'))['cloud_alias'] if card.exists() else CloudConfig().model
    gateway=CloudGateway(CloudConfig(api_key=os.environ.get('MATH_DEEPSEEK_API_KEY',''),model=model))
    report={'key_configured':source!='not_configured','configuration_source':source,'cloud':gateway.public(),
        'connection_verified':False,'external_cloud_attempts':0,'secret_printed':False}
    if a.probe and report['key_configured']:
        response=gateway.request([{'role':'user','content':'这是一条接口连通性测试，请只回答1+1的数值。'}])
        report.update(connection_verified=response['status']=='success',status=response['status'],
            external_cloud_attempts=response['external_cloud_attempts'],model_returned=response.get('model_returned'),
            usage=response.get('usage'),duration_ms=response['duration_ms'])
        dest=ROOT/'.private/api_checks'/('probe_'+uuid.uuid4().hex+'.json');dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    elif a.probe:report['status']='not_configured_no_request'
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if a.probe and not report['connection_verified']:raise SystemExit(2)
