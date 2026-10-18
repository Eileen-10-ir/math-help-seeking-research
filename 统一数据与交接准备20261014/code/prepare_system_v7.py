"""Build a separate v7 harness; preserve all v6 actual API observations."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[2]
old = ROOT / '联合参数化与系统对照20261014'
new = ROOT / '系统支持修正v7_20261014'
(new / 'code').mkdir(parents=True, exist_ok=True)
source = (old / 'code/run_system_comparison.py').read_text(encoding='utf-8')
source = source.replace('from routing_v6 import support,context_for,ROUTING_VERSION,MEDIUM_SUFFIX',
                        'from routing_v6 import context_for,MEDIUM_SUFFIX\nfrom routing_v7 import support,ROUTING_VERSION')
source = source.replace("ROOT/'数学交互与论文初稿20261009/code/routing_v6.py',OLD/'code/routing_v4.py'",
                        "ROOT/'数学交互与论文初稿20261009/code/routing_v6.py',ROOT/'数学交互与论文初稿20261009/code/routing_v7.py',OLD/'code/routing_v4.py'")
source = source.replace('def main(real=False):', 'def main(real=False, output_dir=None):')
source = source.replace("dest=OUT/'results'/mode;dest.mkdir(parents=True,exist_ok=True)",
                        "dest=Path(output_dir).resolve() if output_dir else OUT/'results'/mode;dest.mkdir(parents=True,exist_ok=True)\n    if output_dir:globals()['EVENT_LOG']=dest/'events.jsonl'\n    if real and (dest/'records.json').exists():raise RuntimeError('已有真实结果，请用--output-dir指定新批次目录，禁止覆盖')")
source = source.replace("with (OUT/'events.jsonl').open('a',encoding='utf-8') as f:",
                        "with globals().get('EVENT_LOG',OUT/'events.jsonl').open('a',encoding='utf-8') as f:")
source = source.replace("p.add_argument('--real',action='store_true');args=p.parse_args();main(args.real)",
                        "p.add_argument('--real',action='store_true');p.add_argument('--output-dir');args=p.parse_args();main(args.real,args.output_dir)")
# Source path indices below must stay attached to model/card/state, the first three entries.
assert 'from routing_v7 import support,ROUTING_VERSION' in source
(new / 'code/run_system_comparison.py').write_text(source, encoding='utf-8')
protocol = (old / '02_固定输入系统对照协议.md').read_text(encoding='utf-8')
protocol = protocol.replace('连续帮助策略v6', '连续帮助策略v7')
protocol = protocol.replace('2026-10-14，执行前冻结。', '2026-10-14，v7执行前冻结。')
protocol += '\n\nv7只修正本地支持：核实提示依据当前题型；三角形高的定义及一次方程等式理由使用固定提示。识别器、EWMA、门控和有效等级的低云/中边云/高边机制不变。不得把v6的真实回复移作v7回复。默认离线验收；真实API预算沿用本协议，使用新本机密钥。\n'
(new / '02_固定输入系统对照协议.md').write_text(protocol, encoding='utf-8')
launcher = (old / '启动真实API对照.ps1').read_text(encoding='utf-8-sig')
assert not re.search(r'sk-[A-Za-z0-9_-]{20,}', launcher)
(new / '启动真实API对照.ps1').write_text(launcher, encoding='utf-8-sig')
print(json.dumps({'prepared': str(new), 'actual_API_executed': False,
                  'v6_source_sha256': hashlib.sha256((old / 'code/run_system_comparison.py').read_bytes()).hexdigest()}, ensure_ascii=False))
