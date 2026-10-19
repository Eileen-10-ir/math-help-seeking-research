"""Independent v6 operator service; does not mutate v5 or its E13 protocol."""
from pathlib import Path
import sys, json, argparse, re, mimetypes
BASE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(BASE/'code'), str(BASE.parent/'数学主线严谨重跑20260930/code'),
               str(BASE.parent/'云边教学与成本复核20261001/code')]
import runtime_server as legacy
from runtime_server_v5 import ReviewService, handler as v5_handler
from routing_v6 import support, ROUTING_VERSION, context_for
from evidence_runtime import TASKS
legacy.support = support

class ConversationService(ReviewService):
    def get(self, sid):
        session = super().get(sid)
        session['conversation_context'] = context_for(session['task_id'], session['records'])
        session['support_policy_version'] = ROUTING_VERSION
        return session
    def benchmark(self, payload):
        raise legacy.APIError(403, '新版交互支持不属于冻结E13协议；请使用原v5实验服务')

def handler(service, port):
    Parent = v5_handler(service, port)
    class Handler(Parent):
        def send(self, status, data, kind='application/json; charset=utf-8', filename=None):
            # KaTeX uses inline layout styles; scripts still require local files and cannot run inline.
            content = json.dumps(data, ensure_ascii=False).encode() if isinstance(data, (dict, list)) else data
            self.send_response(status)
            for name, value in [('Content-Type', kind), ('Content-Length', str(len(content))),
                ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
                ('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'")]:
                self.send_header(name, value)
            if filename: self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.end_headers(); self.wfile.write(content)
        def do_GET(self):
            try:
                self.validate()
                if self.path == '/api/config':
                    return self.send(200, {'tasks':TASKS, 'cutoff':service.state_config['cutoff'],
                        'state_config':service.state_config, 'cloud':service.gateway.public(),
                        'routing_version':ROUTING_VERSION, 'model_card':service.card,
                        'medium_suffix':__import__('routing_v6').MEDIUM_SUFFIX,
                        'protocol_scope':'v6 operator prototype; frozen E13 remains v5.1'})
                if self.path in ['/', '/app.js', '/styles.css', '/render-answer.js'] or self.path.startswith('/vendor/'):
                    relative = 'index.html' if self.path == '/' else self.path.lstrip('/')
                    path = (BASE/'app'/relative).resolve()
                    if not path.is_relative_to((BASE/'app').resolve()) or not path.is_file():
                        raise legacy.APIError(404, '页面不存在')
                    mime = mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
                    return self.send(200, path.read_bytes(), mime)
                return super().do_GET()
            except legacy.APIError as e:
                self.send(e.status, {'error':e.message})
    return Handler

def main():
    p=argparse.ArgumentParser(); p.add_argument('--port', type=int, default=8768)
    p.add_argument('--db', default=str(BASE/'runtime/operator.sqlite3')); args=p.parse_args()
    service=ConversationService(args.db)
    server=legacy.ThreadingHTTPServer(('127.0.0.1', args.port), handler(service, args.port))
    print(f'Math conversation v6: http://127.0.0.1:{args.port}/ | cloud configured: {service.gateway.public()["configured"]}', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
if __name__ == '__main__': main()
