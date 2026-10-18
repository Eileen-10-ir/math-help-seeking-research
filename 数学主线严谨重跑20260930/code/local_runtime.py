from common import *
from controlled_text import calibrated
import time,platform
def run():
 real,eedi,llm,r3=load();param,cal=calibrated(real,20260930)
 # Predeclared demo path, not selected to maximize the just-observed validation score.
 corpus=param+real;model=Classifier().fit([r['prompt_text'] for r in corpus],[r['final_level'] for r in corpus])
 texts=[r['prompt_text'] for r in real];model.probs(texts);single=[];batch=[]
 for _ in range(10):
    for t in texts:
      begin=time.perf_counter();model.probs([t]);single.append((time.perf_counter()-begin)*1000)
    begin=time.perf_counter();model.probs(texts);batch.append((time.perf_counter()-begin)*1000/47)
 import joblib
 joblib.dump({'vectorizer':model.vec,'classifier':model.clf,'intent':True,'mask':'bounded',
              'scope':'demo fit on all real47 plus controlled engineering candidates; not independent validation'},OUT/'data/math_demo_candidate.joblib')
 write_json('results/local_runtime.json',{'model_variant':'parameter_real_predeclared_demo','training_rows':len(corpus),
   'calibration':cal,'warmup':'one 47-text batch','single_repeats':470,'single_ms':{'median':float(np.median(single)),'p95':float(np.quantile(single,.95))},
   'batch_per_text_ms':{'median':float(np.median(batch)),'p95':float(np.quantile(batch,.95))},
   'model_bytes':(OUT/'data/math_demo_candidate.joblib').stat().st_size,'python':platform.python_version(),
   'platform':platform.platform(),'cloud_calls':0,'limits':['本机暖启动延迟，不含通信/生成/冷启动','重复调用不增加真实学生数','候选语法未经人工验证，模型仅用于演示','未经概率校准']})
 print('Actual local inference runtime measured; no cloud cost or latency inferred.')
if __name__=='__main__':run()
