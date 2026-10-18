"""Fit development runtime models; no in-sample effectiveness report."""
from common import *
from controlled_text import calibrated
from runtime_state_v4 import RULE_VERSION
import joblib,platform,sklearn
def run():
 real,eedi,llm,r3=load();param,cal=calibrated(real,20260930)
 first=Classifier().fit([r['prompt_text'] for r in real+param],[r['final_level'] for r in real+param])
 following=Classifier(intent=False,context=True).fit([r['prompt_text'] for r in r3],[r['final_level'] for r in r3])
 artifact=OUT/'data/runtime_models_v1.joblib';joblib.dump({'first':first,'following':following},artifact)
 write_json('data/runtime_model_card.json',{'model_version':'math-live-v1-20260930','rule_version':RULE_VERSION,
   'artifact_sha256':sha(artifact),'snapshot_sha256':sha(OUT/'data/anonymous_samples_snapshot.json'),
   'state_config_sha256':sha(OUT/'data/runtime_state_config_v4.json'),
   'first_train_rows':len(real+param),'following_train_rows':len(r3),'first_real_ids':[r['sample_id'] for r in real],
   'following_real_ids':[r['sample_id'] for r in r3],'parameter_calibration':cal,
   'first_oof_reference':'E2 parameter_real','following_oof_reference':'E3 r3_only',
   'runtime':{'python':platform.python_version(),'sklearn':sklearn.__version__},
   'limits':['Full-fit development candidates; no training-set accuracy claimed','Parameters and probabilities not psychometric measurements',
      'Controlled grammar review pending','No independent external or longitudinal validation','Cloud response verification requires configured credentials; training is local','R3 model trained on historical vignette responses, deployment shift unresolved']})
 print('Runtime candidates saved. No training-set effectiveness score reported.')
if __name__=='__main__':run()
