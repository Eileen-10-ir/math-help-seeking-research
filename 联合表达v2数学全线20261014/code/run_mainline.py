"""One canonical entry: verify, serve or compare the same new-method chain."""
import argparse, subprocess, sys, json, uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
from check_handoff_contract import check
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
p=argparse.ArgumentParser();p.add_argument('mode',choices=['check','serve','compare'])
p.add_argument('--output-dir',type=Path);p.add_argument('--port',type=int,default=8770);p.add_argument('--real',action='store_true')
args=p.parse_args()
assert not args.real or args.mode=='compare', '--real applies only to compare.'
proof=check()
stamp=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]
dest=args.output_dir.resolve() if args.output_dir else ROOT/'交付结果'/('统一主线_'+args.mode+'_'+stamp)
assert dest.is_relative_to(ROOT.resolve()) and not dest.exists(), 'Choose a fresh output directory inside this research workspace.'
dest.mkdir(parents=True)
(dest/'统一契约核验.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
def execute(script,*argv):
    result=subprocess.run([sys.executable,'-s','-X','utf8',str(OUT/'code'/script),*map(str,argv)],cwd=ROOT)
    if result.returncode:raise SystemExit(f'{script} failed; preserve {dest} and inspect output.')
execute('check_environment.py')
if args.mode=='serve':
    execute('runtime_joint.py','--port',args.port,'--db',dest/'会话.sqlite3')
elif args.mode=='compare':
    command=['--output-dir',dest/'system']
    if args.real:command.append('--real')
    execute('run_system_new_model.py',*command)
else:
    execute('verify_training_results.py','--output-dir',dest/'training')
    execute('verify_new_mainline.py','--output-dir',dest/'mainline')
    execute('run_system_new_model.py','--output-dir',dest/'system')
    actual=json.loads((dest/'mainline/核验结果.json').read_text(encoding='utf-8'))
    system=json.loads((dest/'system/records.json').read_text(encoding='utf-8'))
    assert actual['model_version']==proof['model'] and actual['passed'] and actual['external_paid_calls']==0
    assert len(system)==64 and all(r['support']['external_cloud_attempts']==0 for r in system)
    groups={}
    for r in system:groups.setdefault((r['case_id'],r['block']),[]).append(r)
    assert all(len(g)==4 and len({r['shared_analysis_sha256'] for r in g})==1 for g in groups.values())
    proof.update({'unified_entry_passed':True,'continuous_HTTP_passed':True,'new_system_records':64,'paid_calls':0,'output_dir':str(dest)})
    (dest/'统一主线验收结果.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(proof,ensure_ascii=False))
