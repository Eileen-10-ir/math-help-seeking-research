"""Sequential offline reproduction. Existing independent reviewer forms are preserved."""
from pathlib import Path
import sys,subprocess,datetime,os
base=Path(__file__).resolve().parent
steps=['recognition.py','context_nested.py','candidate_diagnostics.py','uncertainty.py','simulations.py','local_runtime.py','build_report.py','build_profiles.py','verify_bundle.py']
with (base.parent/'results/复现运行日志.txt').open('w',encoding='utf-8') as log:
 for name in steps:
  line=f'{datetime.datetime.now().isoformat()} START {name}'
  print(line,flush=True);log.write(line+'\n');log.flush()
  result=subprocess.run([sys.executable,str(base/name)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env={**os.environ,'PYTHONIOENCODING':'utf-8'})
  print(result.stdout,flush=True);log.write(result.stdout);log.flush()
  if result.returncode:raise SystemExit(f'{name} failed ({result.returncode}); stop and inspect log.')
 print('Offline reproduction complete. Human review was not performed by this script.')
