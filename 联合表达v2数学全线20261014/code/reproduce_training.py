"""Reproduce frozen training in a fresh delivery directory, leaving archives intact."""
import argparse, importlib.util, shutil, sys, subprocess
from pathlib import Path
SOURCE=Path(__file__).resolve().parents[1];ROOT=SOURCE.parent
if not sys.flags.no_user_site:
    raise SystemExit(subprocess.call([sys.executable,'-s','-X','utf8',str(Path(__file__).resolve()),*sys.argv[1:]]))
if (SOURCE/'data/统一主线交接契约.json').exists():
    subprocess.run([sys.executable,'-s','-X','utf8',str(SOURCE/'code/check_environment.py')],check=True)
parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True);args=parser.parse_args()
dest=args.output_dir.resolve()
assert dest.is_relative_to(ROOT.resolve()) and dest != SOURCE.resolve(), 'Use a new directory within the research workspace.'
assert not dest.exists(), 'Output exists; choose a new directory to preserve prior results.'
dest.mkdir(parents=True)
for name in ['data','results','app']: (dest/name).mkdir()
shutil.copy2(SOURCE/'01_执行前协议.md',dest/'01_执行前协议.md')
spec=importlib.util.spec_from_file_location('joint_training_reproduction',SOURCE/'code/run_joint_training.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.OUT=dest
module.main()
selection=importlib.util.spec_from_file_location('current_runtime_selection',SOURCE/'code/select_runtime_text.py')
selector=importlib.util.module_from_spec(selection);selection.loader.exec_module(selector)
selector.apply_selection(dest)
