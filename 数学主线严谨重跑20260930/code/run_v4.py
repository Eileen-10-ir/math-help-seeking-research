"""Reproduce v4 state/routing experiments; no operator DB or external API calls."""
from pathlib import Path
import subprocess,sys
HERE=Path(__file__).resolve().parent
for filename in ['ewma_validation_v4.py','runtime_train.py','test_runtime_v4.py','build_v4_report.py','verify_v4.py']:
 print('Running '+filename,flush=True)
 subprocess.run([sys.executable,'-X','utf8',str(HERE/filename)],check=True)
print('v4 reproduced. Actual DeepSeek connection and response adherence remain pending credentials.')
