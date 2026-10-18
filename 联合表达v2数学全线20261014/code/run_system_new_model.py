"""Same frozen system cases with the new trained model; offline default."""
from pathlib import Path
import importlib.util, argparse
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
path=ROOT/'系统支持修正v7_20261014/code/run_system_comparison.py'
spec=importlib.util.spec_from_file_location('new_joint_system_runner',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.OLD=OUT
module.OUT=OUT
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--real',action='store_true');parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args()
    dest=args.output_dir or OUT/('results/system_real_api' if args.real else 'results/system_dry_run')
    module.main(real=args.real,output_dir=dest)
