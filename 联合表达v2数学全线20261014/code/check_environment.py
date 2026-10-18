"""Fail before unpickling if the scientific environment does not match the frozen release."""
import sys, json
from importlib.metadata import version
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]
contract=json.loads((OUT/'data/统一主线交接契约.json').read_text(encoding='utf-8'))
expected=contract['environment']
actual={k:version(package) for k,package in [('numpy','numpy'),('scipy','scipy'),('sklearn','scikit-learn'),('joblib','joblib')]}
actual['python_minor']='.'.join(map(str,sys.version_info[:2]))
actual['no_user_site']=bool(sys.flags.no_user_site)
errors=[f'{k}: expected {v}, actual {actual.get(k)}' for k,v in expected.items() if actual.get(k)!=v]
if not actual['no_user_site']:errors.append('Use isolated child process with -s / no user site.')
if errors:raise SystemExit('Environment differs from frozen model: '+'; '.join(errors)+'. Install pinned dependencies in a dedicated environment.')
print(json.dumps({'environment_match':True,'actual':actual},ensure_ascii=False))
