"""Validate a private archive fully before restoring; never overwrite a changed source."""
import argparse,json,zipfile,hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parent
EXPECTED='76f0b9ddb20b319b60e7b6944d8c56629e90aefd9d780e0798799f099c1b7c9f'
PREFIX='共享研究资料/研究工作区/'

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);a=p.parse_args()
 assert hashlib.sha256(a.archive.read_bytes()).hexdigest()==EXPECTED,'Use the frozen private shared ZIP, not the outer 3-part ZIP.'
 with zipfile.ZipFile(a.archive) as z:
  assert z.testzip() is None
  manifest=json.loads(z.read(PREFIX+'release_manifest.json').decode('utf-8'))
  pending=[];unchanged=0
  for rel,h in manifest['protected_files'].items():
   dest=(ROOT/rel).resolve();assert dest.is_relative_to(ROOT.resolve()) and '.git' not in Path(rel).parts
   content=z.read(PREFIX+rel);assert hashlib.sha256(content).hexdigest()==h
   if dest.exists():
    assert dest.is_file() and hashlib.sha256(dest.read_bytes()).hexdigest()==h,'Changed local file: '+rel
    unchanged+=1
   else:pending.append((dest,content))
  manifest_dest=ROOT/'release_manifest.json'
  if manifest_dest.exists():assert manifest_dest.read_bytes()==z.read(PREFIX+'release_manifest.json'),'Changed release manifest'
  # Validate every member before writing the first byte; no partial overwrite on a conflict.
  for dest,content in pending:dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content)
  dest=ROOT/'release_manifest.json'
  if dest.exists():assert dest.read_bytes()==z.read(PREFIX+'release_manifest.json')
  else:dest.write_bytes(z.read(PREFIX+'release_manifest.json'))
 print(json.dumps({'restored_new_files':len(pending),'existing_same_files':unchanged,'protected_files':len(manifest['protected_files']),
  'private_files_remain_git_ignored':True,'next':'python -s -X utf8 数学共同主线定版20261018/code/run_mainline.py check'},ensure_ascii=False))
