"""Workspace-only packaging; original materials and reviewer entries are preserved."""
from pathlib import Path
import csv,json,hashlib,zipfile,shutil,platform,importlib.metadata
BASE=Path(__file__).resolve().parents[1];ROOT=BASE.parent
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run():
 for origin in sorted((ROOT/'7-8月实验日志').glob('2026-09-30_*.md')):
  if origin.exists():shutil.copyfile(origin,BASE/'report'/origin.name)
 rows=[]
 for p in sorted(BASE.rglob('*')):
  if not p.is_file() or '__pycache__' in p.parts or 'runtime' in p.relative_to(BASE).parts or p.name in ['有效文件清单.csv','交付文件哈希清单.json']:continue
  rel=p.relative_to(BASE).as_posix();role='成果入口与协议'
  if rel.startswith('code/'):role='复现代码（prepare/finalize为工作区提取/打包辅助）'
  elif rel.startswith('results/'):role='实验输出/可审计记录'
  elif rel.startswith('report/'):role='报告、论文工作稿、人工说明与日志'
  elif rel.startswith('figures/'):role='科研汇报图'
  elif rel.startswith('qa/'):role='浏览器展示检查证据'
  elif rel.startswith('data/'):role='冻结输入、候选语法、模型、分折及审核表'
  if '人工审核' in rel or '独立证据复核' in rel or '独立边界复核' in rel:role='人工审核待办，不能充当已完成结果'
  if rel.startswith('app/'):role='现场前端（配合本机Python后台）'
  if '历史240' in rel:role='已存在工程证据的归档，本轮主表为256配置'
  rows.append({'relative_path':rel,'role':role,'bytes':p.stat().st_size,'sha256':digest(p)})
 with (BASE/'有效文件清单.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 manifest={'date':'2026-09-30','python':platform.python_version(),'versions':{k:importlib.metadata.version(k) for k in ['numpy','scipy','scikit-learn','matplotlib','pandas','joblib']},
  'new_real_students':0,'paid_calls':0,'independent_external_validation':False,'human_review':'pending',
  'hash_scope':'all delivered files except this manifest, inventory itself, Python caches, and runtime operator-session databases','operator_records_included':False,'files':rows}
 (BASE/'交付文件哈希清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 archive=ROOT/'数学主线有效成果包_20260930.zip'
 with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for p in sorted(BASE.rglob('*')):
   if p.is_file() and '__pycache__' not in p.parts and 'runtime' not in p.relative_to(BASE).parts:z.write(p,arcname=str(Path(BASE.name)/p.relative_to(BASE)))
 with zipfile.ZipFile(archive) as z:
  assert z.testzip() is None
  info={'zip':archive.name,'bytes':archive.stat().st_size,'sha256':digest(archive),'entries':len(z.namelist()),'crc_test':'passed'}
 (ROOT/'数学主线有效成果包_20260930_校验.json').write_text(json.dumps(info,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(info,ensure_ascii=False))
if __name__=='__main__':run()
