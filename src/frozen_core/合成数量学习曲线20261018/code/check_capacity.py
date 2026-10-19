"""Structural feasibility before comparing scores; first counterexample suffices."""
from pathlib import Path
import sys,json,csv
import numpy as np
from sklearn.model_selection import StratifiedKFold
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
sys.path[:0]=[str(OUT/'code'),str(ROOT/'统一数据与交接准备20261014/code')]
from run_budget import quotas,csvread,read,save
from joint_renderer import sample_and_render
from independent_contract_check import check_contract
base=ROOT/'数学共同主线定版20261018';real=read(base/'data/anonymous_samples_snapshot.json')['real_r1']
folds=read(base/'data/fold_audit.json');raw=csvread(ROOT/'参数验证与生成器比较20261014/四维均值_真实R1_47条.csv')
cal=[{k:(float(v) if k.endswith(('_mean','_rater_A','_rater_B')) else v) for k,v in r.items() if k in ['sample_id','student_id','final_level'] or k.endswith(('_mean','_rater_A','_rater_B'))} for r in raw]
kinds={r['sample_id']:r['behavior_type'] for r in csvread(ROOT/'统一数据与交接准备20261014/data/真实行为类型解释_机器候选.csv')}
views=[]
for f in folds:
    tr=[r for r in real if r['sample_id'] in f['train_ids']];labels=np.array([r['final_level'] for r in tr])
    seed,fi=f['seed'],f['fold'];views.append({'view':'outer','seed':seed,'fold':fi,'ids':f['train_ids'],'generation_seed':20261018+seed*100+fi})
    for j,(a,b) in enumerate(StratifiedKFold(n_splits=3,shuffle=True,random_state=seed*100+fi).split(labels,labels)):
        views.append({'view':'inner','seed':seed,'fold':fi,'inner':j,'ids':[tr[i]['sample_id'] for i in a],
                      'generation_seed':20261018+seed*100+fi+(j+1)*10000})
attempts=[];chosen=None
for budget in [364,182,91,45]:
    passed=True
    for v in views:
        try:
            fresh=sample_and_render([r for r in cal if r['sample_id'] in v['ids']],kinds,quotas(budget),v['generation_seed'],tau=1.)
            assert all(check_contract(r['spec'],r['prompt_text'],r['question'])['status']=='pass' for r in fresh)
            attempts.append({**v,'budget':budget,'passed':True})
        except RuntimeError as e:
            attempts.append({**v,'budget':budget,'passed':False,'reason':str(e)});passed=False;break
    if passed:chosen=budget;break
result={'selected_maximum_safe_grid_budget':chosen,'views_in_required_check':len(views),'attempts':attempts,
        'scope':'failed budget stops at first counterexample; success checked all 80 views; not a population failure rate'}
save('capacity_check.json',result);print(json.dumps({'max_safe':chosen,'attempts':len(attempts),'counterexamples':[r for r in attempts if not r['passed']]},ensure_ascii=False))
assert chosen is not None,'No valid common budget; retain old experiment and revise generator separately.'
