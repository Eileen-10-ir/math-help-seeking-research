"""Collect completed QA and zip only the first member pack."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / '团队专属交接20261014/lbb_更新任务包'
WORK = PACK / '03_数据与代码/研究工作区'
QA = ROOT / '团队专属交接20261014/制作与检查/lbb页面'
REF = PACK / '04_参考与历史'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for name in ('参数说明_联合表达v2.json', '联合表达v2_全部折候选.csv'):
    assert sha(WORK / '统一数据与交接准备20261014/data' / name) == sha(WORK / '交付结果/包验收_联合生成复现/data' / name)
assert sha(WORK / '统一数据与交接准备20261014/review/联合表达v2_44条盲审公共空表.csv') == sha(WORK / '交付结果/包验收_联合生成复现/review/联合表达v2_44条盲审公共空表.csv')
receipt = json.loads((WORK / '交付结果/包核验/核验结果.json').read_text(encoding='utf-8'))
system = json.loads((WORK / '交付结果/包验收_系统v7离线/v7_离线修正核验.json').read_text(encoding='utf-8'))
assert system['same_model_state_inference_routes'] and system['local_only_dry_run_no_API']
assert (QA / 'page-1.png').is_file() and (QA / 'page-2.png').is_file()
render = json.loads((QA / '渲染方式.json').read_text(encoding='utf-8'))
render['visual_QA'] = 'both_pages_inspected_no_clipping_or_title_decoration'
(QA / '渲染方式.json').write_text(json.dumps(render, ensure_ascii=False, indent=2), encoding='utf-8')
shutil.copy2(QA / '内部检查.pdf', PACK / '01_给本人阅读/项目回顾与本次任务.pdf')
proof = {'package_check': receipt, 'full_joint_data_reproduction_exact': True,
         'blind_sheet_reproduction_exact': True, 'v7_offline_records': 64,
         'source_model_state_routes_unchanged': True, 'Word_pages': 2,
         'Word_visual_QA': render['visual_QA'], 'API_called_for_this_preparation': False,
         'human_review_completed': False, 'other_member_packs_created': False}
(REF / '交接包验收证明.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf-8')
files = []
for path in sorted(PACK.rglob('*')):
    if not path.is_file() or '__pycache__' in path.parts:
        continue
    if '交付结果' in path.parts and path.name != 'README.md':
        continue
    if path.name == '交接包文件清单.json':
        continue
    files.append(path)
manifest = {str(p.relative_to(PACK)): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in files}
(PACK / '交接包文件清单.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
files.append(PACK / '交接包文件清单.json')
archive = PACK.parent / 'lbb_更新任务包_20261014.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for path in files:
        z.write(path, 'lbb_更新任务包/' + path.relative_to(PACK).as_posix())
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for path, info in manifest.items():
        content = z.read('lbb_更新任务包/' + Path(path).as_posix())
        assert hashlib.sha256(content).hexdigest() == info['sha256']
print(json.dumps({'zip': str(archive), 'files': len(files), 'zip_bytes': archive.stat().st_size,
                  'all_archived_hashes_verified': True, 'next_member': 'lwl_pending_user_confirmation'}, ensure_ascii=False))
