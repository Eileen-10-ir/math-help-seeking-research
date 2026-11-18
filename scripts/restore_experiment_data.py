"""Restore hash-pinned supplemental engineering inputs; never overwrite changed data."""
from pathlib import Path
import argparse,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'.private/workspace'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);a=p.parse_args()
 m=json.loads((ROOT/'configs/experiment_data_manifest.json').read_text(encoding='utf-8'))
 assert sha(a.archive.read_bytes())==m['archive_sha256'],'Supplement archive does not match this code version'
 pending=[]
 with zipfile.ZipFile(a.archive) as z:
  for name,h in m['files'].items():
   target=(WORK/name).resolve();assert target.is_relative_to(WORK.resolve()) and '.git' not in target.parts
   data=z.read(m['prefix']+name);assert sha(data)==h
   if target.exists():assert sha(target.read_bytes())==h,'Existing input differs; do not overwrite'
   else:pending.append((target,data))
 for target,data in pending:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 print(json.dumps({'files_verified':len(m['files']),'new_files':len(pending),'secret_included':False}))
if __name__=='__main__':main()
