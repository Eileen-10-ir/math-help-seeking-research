"""Isolated new-model continuous server; archived services are not changed."""
from pathlib import Path
import sys, argparse
OUT=Path(__file__).resolve().parents[1]; ROOT=OUT.parent
sys.path[:0]=[str(ROOT/'数学交互与论文初稿20261009/code'),str(ROOT/'数学主线严谨重跑20260930/code'),
             str(ROOT/'云边教学与成本复核20261001/code')]
import runtime_server_v6 as v6
import runtime_server as legacy
from routing_v7 import support, ROUTING_VERSION
legacy.OUT=OUT
legacy.support=support
v6.BASE=OUT
v6.ROUTING_VERSION=ROUTING_VERSION
ConversationService=v6.ConversationService
handler=v6.handler
ThreadingHTTPServer=legacy.ThreadingHTTPServer

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8770)
    parser.add_argument('--db',default=str(OUT/'runtime/新联合模型会话.sqlite3'));args=parser.parse_args()
    if not 1024<=args.port<=65535:raise ValueError('Use an unprivileged port')
    Path(args.db).parent.mkdir(parents=True,exist_ok=True)
    service=ConversationService(args.db);server=ThreadingHTTPServer(('127.0.0.1',args.port),handler(service,args.port))
    print(f"New joint-expression model: http://127.0.0.1:{args.port}/ | {service.card['model_version']} | cloud configured: {service.gateway.public()['configured']}",flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
