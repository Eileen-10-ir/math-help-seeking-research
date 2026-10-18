"""Canonical current check / serve / compare; all new runs in fresh output directories."""
import argparse,sys,subprocess,json,uuid
from pathlib import Path
from datetime import datetime,timezone,timedelta
from importlib.metadata import version
from check_contract import check
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
p=argparse.ArgumentParser();p.add_argument('mode',choices=['check','serve','compare']);p.add_argument('--output-dir',type=Path)
p.add_argument('--port',type=int,default=8771);p.add_argument('--real',action='store_true');a=p.parse_args()
assert not a.real or a.mode=='compare'
contract=json.loads((OUT/'data/统一主线交接契约.json').read_text(encoding='utf-8'))
expected=contract['environment'];actual={k:version(n) for k,n in [('numpy','numpy'),('scipy','scipy'),('sklearn','scikit-learn'),('joblib','joblib')]}
actual['python_minor']='.'.join(map(str,sys.version_info[:2]))
assert actual==expected,('Use a pinned dedicated environment',actual,expected)
assert sys.flags.no_user_site,'Use python -s -X utf8 to isolate user packages.'
proof=check();stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]
dest=a.output_dir.resolve() if a.output_dir else ROOT/'交付结果'/('当前主线_'+a.mode+'_'+stamp)
assert dest.is_relative_to(ROOT.resolve()) and not dest.exists(),'Use a fresh directory in this workspace.'
dest.mkdir(parents=True);(dest/'契约核验.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
def run(name,*args):
    subprocess.run([sys.executable,'-s','-X','utf8',str(OUT/'code'/name),*map(str,args)],cwd=ROOT,check=True)
if a.mode=='serve':run('runtime_current.py','--port',a.port,'--db',dest/'会话.sqlite3')
elif a.mode=='compare':run('run_system_current.py','--output-dir',dest/'system',*(['--real'] if a.real else []))
else:
    run('verify_results.py','--output-dir',dest/'recognition')
    run('verify_http.py','--output-dir',dest/'http')
    run('run_system_current.py','--output-dir',dest/'system')
    proof.update(unified_entry_passed=True,continuous_HTTP_passed=True,recognition_metrics_recomputed=True,output_dir=str(dest))
    (dest/'统一主线验收.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(proof,ensure_ascii=False))
