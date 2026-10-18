"""Shared frozen analysis for four arms; no stale hard-coded API prices."""
from pathlib import Path
import sys,importlib.util,json,argparse
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
sys.path[:0]=[str(OUT/'code'),str(ROOT/'数学交互与论文初稿20261009/code'),str(ROOT/'数学主线严谨重跑20260930/code')]
import route_models
from state_v5 import State,advance
path=ROOT/'系统支持修正v7_20261014/code/run_system_comparison.py'
spec=importlib.util.spec_from_file_location('frozen_case_runner',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.OLD=OUT;module.OUT=OUT;module.State=State;module.advance=advance
module.cost=lambda usage: {'status':'usage_saved_current_price_verification_pending','usage':usage,'is_billed_fee':False} if usage else None

def run(dest,real=False):
    dest=Path(dest);assert not dest.exists(),'Use a new batch directory.'
    module.main(real=real,output_dir=dest)
    manifest=dest/'frozen_run_manifest.json'
    if manifest.exists():
        value=json.loads(manifest.read_text(encoding='utf-8'))
        value.pop('price_date',None);value['price_status']='verify_current_official_rates_or_actual_invoice; no old rates used'
        value['state_config']='stage cutoffs and evidence-aware release in current contract'
        manifest.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--real',action='store_true');a=p.parse_args();run(a.output_dir,a.real)
