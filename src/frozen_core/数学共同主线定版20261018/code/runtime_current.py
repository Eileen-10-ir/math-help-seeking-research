"""One isolated current process; historical runtime sources are preserved."""
import sys,os,json,argparse
from pathlib import Path
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
sys.path[:0]=[str(OUT/'code'),str(ROOT/'数学交互与论文初稿20261009/code'),
    str(ROOT/'数学主线严谨重跑20260930/code'),str(ROOT/'云边教学与成本复核20261001/code')]
import route_models
import runtime_server_v6 as v6
import runtime_server as legacy
from state_v5 import State,advance,RULE_VERSION
from routing_v7 import support,ROUTING_VERSION
from cloud_gateway import CloudGateway,CloudConfig
legacy.OUT=OUT;legacy.State=State;legacy.advance=advance;legacy.RULE_VERSION=RULE_VERSION;legacy.support=support
v6.BASE=OUT;v6.ROUTING_VERSION=ROUTING_VERSION

class ConversationService(v6.ConversationService):
    def __init__(self,db,engineering=False,gateway=None):
        if gateway is None:
            card=json.loads((OUT/'data/runtime_model_card.json').read_text(encoding='utf-8'))
            gateway=CloudGateway(CloudConfig(api_key=os.environ.get('MATH_DEEPSEEK_API_KEY',''),model=card['cloud_alias']))
        super().__init__(db,engineering,gateway)

handler=v6.handler
ThreadingHTTPServer=legacy.ThreadingHTTPServer
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8771);p.add_argument('--db',type=Path,required=True);a=p.parse_args()
    assert 1024<=a.port<=65535
    a.db.parent.mkdir(parents=True,exist_ok=True)
    service=ConversationService(a.db);server=ThreadingHTTPServer(('127.0.0.1',a.port),handler(service,a.port))
    print(f"http://127.0.0.1:{a.port}/ | {service.card['model_version']}",flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
