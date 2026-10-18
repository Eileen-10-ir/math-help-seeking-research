"""Reproduce E7--E10 and archived v3 reports without editing original data."""
from pathlib import Path
import subprocess,sys
HERE=Path(__file__).resolve().parent
for filename in ['parameter_v2_experiment.py','coverage_evaluation.py','unified_state_pressure.py','behavior_rule_evaluation.py','build_live_report.py','verify_live_research.py']:
 print('Running '+filename,flush=True)
 subprocess.run([sys.executable,'-X','utf8',str(HERE/filename)],check=True)
print('E7--E10 and archived v3 reports reproduced. Use run_v4.py for current runtime. Operator database untouched.')
