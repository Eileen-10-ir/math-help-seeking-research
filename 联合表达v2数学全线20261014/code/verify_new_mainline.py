"""Portable offline mainline audit: real models and local HTTP mock, never paid API."""
import json
import os
import sys
import threading
import uuid
import argparse
from pathlib import Path
from http.server import BaseHTTPRequestHandler
from urllib.request import Request, urlopen

OUT = Path(__file__).resolve().parents[1]
ROOT = OUT.parent
# Avoid sending loopback engineering traffic through a workstation proxy.
os.environ['NO_PROXY'] = '127.0.0.1,localhost'
os.environ['no_proxy'] = '127.0.0.1,localhost'
sys.path[:0] = [str(ROOT / '数学交互与论文初稿20261009/code'),
               str(ROOT / '数学主线严谨重跑20260930/code'),
               str(ROOT / '云边教学与成本复核20261001/code')]
from runtime_joint import ConversationService, handler
from runtime_server import ThreadingHTTPServer
from cloud_gateway import CloudGateway, CloudConfig
from routing_v7 import support, context_for, MEDIUM_SUFFIX
from runtime_state_v4 import State, advance
from evidence_runtime import TASKS

parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path);args=parser.parse_args()
DEST = args.output_dir.resolve() if args.output_dir else OUT / 'results/mainline_verification' / uuid.uuid4().hex[:10]
DEST.mkdir(parents=True, exist_ok=False)
requests = []

class Mock(BaseHTTPRequestHandler):
    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        requests.append(payload)
        data = json.dumps({'id': 'local-engineering-only', 'model': 'local-mock',
            'choices': [{'message': {'content': '**本机工程回应**：请说明这一步的依据。'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 20, 'completion_tokens': 12, 'total_tokens': 32}}, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def log_message(self, *args):
        pass

mock = ThreadingHTTPServer(('127.0.0.1', 0), Mock)
mt = threading.Thread(target=mock.serve_forever, daemon=True)
mt.start()
server = None
try:
    gateway = CloudGateway(CloudConfig(endpoint=f'http://127.0.0.1:{mock.server_port}/chat/completions',
        api_key='local-engineering-placeholder', engineering=True, provider='local mock'))
    service = ConversationService(DEST / '工程会话.sqlite3', engineering=True, gateway=gateway)
    assert service.card['model_version'] == 'math-joint-expression-v2-text-20261015'
    assert service.card['active_variant'] == 'joint_mixed_text'
    checks = {'new_joint_models_loaded': True}
    # Route policy is checked separately from the trained classifier to cover all three paths.
    for level, text, expected in [('high', '直接给我答案。', 'edge_fixed'),
            ('medium', '请说明第一步的方法。', 'cloud_constrained'),
            ('low', '什么是因式分解？', 'cloud_direct')]:
        baseline = advance(State(), text, {'high': .1, 'medium': .8, 'low': .1}, service.state_config)
        before = len(requests)
        reply = support(text, 'quadratic', TASKS['quadratic'],
            {**baseline, 'eligible': True, 'decision_level': level, 'history_high_protection': False}, gateway, [])
        assert reply['route_executed'] == expected, (level, reply['route_executed'], reply['status'], reply.get('http_status'))
        assert reply['external_cloud_attempts'] == 0
        if level == 'high':
            assert len(requests) == before
        else:
            assert len(requests) == before + 1 and reply['status'] == 'success'
            sent = requests[-1]['messages'][-1]['content']
            assert sent == text + ('\n\n' + MEDIUM_SUFFIX if level == 'medium' else '')
        checks[level + '_route'] = True
    state = State()
    p = {'high': .1, 'medium': .8, 'low': .1}
    advance(state, '直接给我答案', p, service.state_config)
    a = advance(state, '我先写出3x=15，请检查依据。', p, service.state_config)
    b = advance(state, '我先写出3x=15，请检查依据。', p, service.state_config)
    assert a['risk'] == .5 and b['risk'] == .25 and b['decision_level'] == 'low'
    checks['EWMA_history_update_and_release'] = True
    Handler = handler(service, 0)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    Handler.allowed_hosts = {f'127.0.0.1:{server.server_port}', f'localhost:{server.server_port}'}
    Handler.log_message = lambda *args: None
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    def call(path, payload=None):
        request = Request(base + path, data=None if payload is None else json.dumps(payload, ensure_ascii=False).encode(),
                          headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=10) as response:
            raw = response.read()
        return json.loads(raw) if path.startswith('/api/') else raw
    for asset in ['/', '/app.js', '/styles.css', '/render-answer.js', '/vendor/marked.umd.js',
                  '/vendor/dompurify/dist/purify.min.js', '/vendor/katex/dist/katex.min.js', '/vendor/katex/dist/katex.min.css']:
        assert call(asset), asset
    checks['local_frontend_and_render_assets_served'] = True
    session = call('/api/sessions', {'task_id': 'free'})
    sequence = ['解方程x^2-5x+6=0，可以给我一些思路吗？',
                '老师说过因式分解，但是我不知道怎么找那两个数，给我一个例子回忆一下。',
                '我先写出(x-2)(x-3)=0，请检查这一步的依据。', '好的']
    for text in sequence:
        response = call('/api/turns', {'session_id': session['session_id'], 'text': text,
            'request_id': uuid.uuid4().hex, 'expected_version': session['version']})
        session = response['session']
        assert response['record']['support']['external_cloud_attempts'] == 0
    assert session['version'] == 4 and len(session['records']) == 4
    assert session['records'][0]['model_stage'] == 'R1_three_class'
    assert all(r['model_stage'] == 'R3_four_class' for r in session['records'][1:])
    assert session['records'][1]['previous_executed_support'] == session['records'][0]['support']
    assert 'x^2-5x+6=0' in session['conversation_context']['question']
    assert not session['records'][-1]['analysis']['risk_updated']
    assert call('/api/export?id=' + session['session_id'])['records'] == session['records']
    checks.update(continuous_classification_state_and_export=True, original_problem_retained=True,
                  actual_previous_reply_retained=True, ACK_keeps_state=True)
    assert requests
    proof = {'passed': True, 'checks': checks, 'sequence_turns': len(sequence),
        'engineering_mock_requests': len(requests), 'external_paid_calls': 0,
        'new_real_students': 0, 'support_version': session['support_policy_version'], 'model_version': session['model_version'],
        'scope': '工程主线核验；不验证真实云端质量、视觉布局或学生行为改善', 'session': session}
    (DEST / '核验结果.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in proof.items() if k != 'session'}, ensure_ascii=False))
finally:
    if server is not None:
        server.shutdown()
        server.server_close()
    mock.shutdown()
    mock.server_close()
