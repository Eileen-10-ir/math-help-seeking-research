"""Assemble only the first updated member pack; other packs await user confirmation."""
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / '团队专属交接20261014/lbb_更新任务包'
WORK = PACK / '03_数据与代码/研究工作区'
WORK.mkdir(parents=True, exist_ok=True)
for name in ('build_lbb_package.py', 'build_lbb_word.py', 'prepare_system_v7.py'):
    obsolete = WORK / '统一数据与交接准备20261014/code' / name
    assert obsolete.resolve().is_relative_to(WORK.resolve())
    if obsolete.is_file():
        obsolete.unlink()
allowed = {'.py', '.json', '.csv', '.md', '.joblib', '.ps1', '.png', '.pdf', '.jsonl'}
copied = []

def copy_relative(path):
    dest = WORK / path.relative_to(ROOT)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)
    copied.append(str(dest.relative_to(WORK)))

for name in ('G0_G1严谨对照20261014', 'G0_G1_融合候选20261014',
             '联合参数化与系统对照20261014', '系统支持修正v7_20261014', '统一数据与交接准备20261014'):
    for path in (ROOT / name).rglob('*'):
        if not path.is_file() or '__pycache__' in path.parts:
            continue
        if path.suffix in allowed or path.suffix == '.sqlite3':
            # Ignore packaging helpers in the recipient runtime to avoid creating nested packs.
            if path.name in ('build_lbb_package.py', 'verify_shared_release.py', 'build_lbb_word.py', 'prepare_system_v7.py'):
                continue
            copy_relative(path)
for sub in ('code', 'data'):
    for path in (ROOT / '数学主线严谨重跑20260930' / sub).glob('*'):
        if path.is_file() and path.suffix in allowed:
            copy_relative(path)
for path in (ROOT / '数学主线严谨重跑20260930/results').glob('*'):
    if path.is_file() and (path.name.startswith(('E2_', 'E3_', 'E11_', 'E12_')) or path.name == 'recognition_predictions.csv'):
        copy_relative(path)
for name in ('冻结重跑协议.md', '云边机制与EWMA修正协议_v4.md'):
    copy_relative(ROOT / '数学主线严谨重跑20260930' / name)
for name in ('routing_v6.py', 'routing_v7.py'):
    copy_relative(ROOT / '数学交互与论文初稿20261009/code' / name)
for name in ('四维均值_真实R1_47条.csv', '四维均值数据说明.json', '02_参数验证台账.md'):
    copy_relative(ROOT / '参数验证与生成器比较20261014' / name)
for name in ('依赖标注数据库.db', '标注合并入库/合并结果_最终整合.xlsx', 'R3标注/合并结果_R3_47条.xlsx'):
    copy_relative(ROOT / '7月数据' / name)
base = ROOT / '科研工作流与基线补强20261011'
copy_relative(base / '补充识别实验协议.md')
copy_relative(base / 'code/run_recognition_baselines.py')
for path in (base / 'results').glob('识别基线*'):
    if path.is_file():
        copy_relative(path)
copy_relative(ROOT / '研究主线统一口径_20261014.md')
copy_relative(ROOT / '待分工前_生成文本与回复审核规范_20261014.md')
shutil.copy2(ROOT / '统一数据与交接准备20261014/code/verify_shared_release.py', WORK / 'verify_shared_release.py')
(WORK / 'requirements.txt').write_text('numpy==2.1.3\nscipy==1.15.3\nscikit-learn==1.6.1\njoblib==1.4.2\n', encoding='utf-8')
(WORK / '交付结果').mkdir(exist_ok=True)
(WORK / '交付结果/README.md').write_text('# 新结果存放处\n所有新实验、协议、模型、预测、请求和日志写本目录。冻结资料只读。\n', encoding='utf-8')
docdir = PACK / '03_数据与代码'
for name in ('申报书2026_1.pdf', '中小学生AI学习提问行为调查问卷.docx'):
    shutil.copy2(ROOT.parent / name, docdir / name)
ref = PACK / '04_参考与历史'
ref.mkdir(exist_ok=True)
shutil.copy2(ROOT / '7月数据/交接1/交接1识别线分析与实施报告.md', ref / '上次交接1成果说明.md')
shutil.copy2(ROOT / '统一数据与交接准备20261014/01_负责人已完成与数据定版说明.md', ref / '本轮数据定版与文献定位.md')
shutil.copy2(ROOT / '统一数据与交接准备20261014/03_数据字典与复现方法.md', docdir / '数据字典与复现方法.md')
# A separate baseline adapter avoids overwriting frozen baseline tables.
source = (base / 'code/run_recognition_baselines.py').read_text(encoding='utf-8')
source = source.replace("OUT = BASE / 'results'", "OUT = ROOT / '交付结果/识别基线复现'")
source = source.replace('OUT.mkdir(exist_ok=True)', 'OUT.mkdir(parents=True, exist_ok=True)')
adapter = WORK / '科研工作流与基线补强20261011/code/复现现有基线_写交付目录.py'
adapter.write_text(source, encoding='utf-8')
launcher = WORK / '系统支持修正v7_20261014/启动真实API对照.ps1'
body = launcher.read_text(encoding='utf-8-sig')
body = "param([string]$experimentPython = 'python')\n" + body
body = body.replace("& 'D:\\anaconda3\\python.exe' -s -X utf8", '& $experimentPython -s -X utf8')
body = body.replace("--real\n", "--real --output-dir (Join-Path (Split-Path -Parent $PSScriptRoot) ('交付结果/系统v7真实_' + (Get-Date -Format 'yyyyMMdd_HHmmss')))\n")
launcher.write_text(body, encoding='utf-8-sig')
for path in WORK.rglob('*'):
    if path.is_file() and path.suffix in ('.py', '.md', '.json', '.csv', '.ps1'):
        assert not re.search(r'sk-[A-Za-z0-9_-]{20,}', path.read_text(encoding='utf-8-sig', errors='ignore')), ('Possible credential', str(path))
protected = {}
for path in sorted(WORK.rglob('*')):
    if not path.is_file() or '__pycache__' in path.parts or '交付结果' in path.parts or path.name == 'release_manifest.json':
        continue
    protected[str(path.relative_to(WORK))] = hashlib.sha256(path.read_bytes()).hexdigest()
manifest = {'version': 'lbb-updated-math-release-20261014', 'member': 'lbb',
            'protected_files': protected, 'data_and_outputs_frozen': True,
            'current_runtime_not_replaced': True, 'human_review_pending': True, 'API_key_included': False,
            'other_member_packs_created': False}
(WORK / 'release_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'pack': str(PACK), 'protected_files': len(protected),
                  'bytes': sum(path.stat().st_size for path in WORK.rglob('*') if path.is_file()),
                  'API_key_included': False, 'next_member_status': 'waiting_for_user_confirmation'}, ensure_ascii=False))
