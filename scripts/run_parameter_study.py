"""Reproduce versioned experiments against the restored private workspace."""
from pathlib import Path
import argparse,os,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from run import WORK,sync_sources

def main():
 p=argparse.ArgumentParser();p.add_argument('kind',choices=['selection','summarize','ablation','state','system','continuity'])
 p.add_argument('--name',default='参数完善实验20261118_复现');p.add_argument('--smoke',action='store_true');p.add_argument('--real',action='store_true');a=p.parse_args()
 assert sys.flags.no_user_site,'Use python -s -X utf8'
 assert Path(a.name).name==a.name and a.name not in ('.','..')
 sync_sources();dest=WORK/a.name;(dest/'code').mkdir(parents=True,exist_ok=True)
 for n in ['results','models']:(dest/n).mkdir(exist_ok=True)
 source=ROOT/'experiments/parameter_selection'
 for f in source.glob('*.py'):shutil.copy2(f,dest/'code'/f.name)
 shutil.copy2(source/'protocol.md',dest/'执行协议.md')
 os.environ['MATH_CODE_REPOSITORY']=str(ROOT)
 if a.real:
  from scripts.api_config import load_api_key
  load_api_key()
  if not os.environ.get('MATH_DEEPSEEK_API_KEY'):raise SystemExit('先配置本机API密钥。')
 if a.kind=='continuity' and not a.real:raise SystemExit('连续API回放需显式 --real；本地规则测试用 run.py check。')
 mapping={'selection':['run_selection.py'],'summarize':['summarize_and_fit.py','analyze_results.py'],
  'ablation':['run_generation_ablation.py'],'state':['run_state_sensitivity.py','state_response_analysis.py'],'system':['run_system_validation.py'],'continuity':['run_continuity_replay.py']}
 for name in mapping[a.kind]:
  args=['--smoke'] if a.smoke and a.kind=='selection' else ['--real'] if a.real else []
  subprocess.run([sys.executable,'-s','-X','utf8',str(dest/'code'/name),*args],cwd=ROOT,check=True)
 print(str(dest))
if __name__=='__main__':main()
