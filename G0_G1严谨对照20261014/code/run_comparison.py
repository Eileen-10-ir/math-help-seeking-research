"""Frozen G0 versus joint-profile G1: synthetic primary and mixed secondary."""
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import sys,json,csv,hashlib,shutil,traceback,platform
from pathlib import Path
from datetime import datetime
from collections import Counter
import numpy as np
import sklearn
from sklearn.model_selection import StratifiedKFold
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
OLD=ROOT/'数学主线严谨重跑20260930'
sys.path.insert(0,str(OLD/'code'))
from common import load,Classifier,metrics,LAB,SEEDS
from controlled_text import calibrated,pool
from g1_generator import generate,POOL,META,DIMS,feature_key,build_pool,DOMAINS
for d in ['archive','data','results','review']: (OUT/d).mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jd(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,default=lambda v:v.item() if hasattr(v,'item') else str(v))
def save(path,obj): (OUT/path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)),encoding='utf-8')
def csvsave(path,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:w.writerow({k:jd(v) if isinstance(v,(list,dict)) else v for k,v in r.items()})
def event(stage,**data):
    obj={'time':datetime.now().astimezone().isoformat(),'stage':stage,**data}
    with (OUT/'events.jsonl').open('a',encoding='utf-8') as f:f.write(jd(obj)+'\n')
    print(jd(obj),flush=True)
def calibration_rows(rows,scoreby,rater='mean'):
    result=[]
    for r in rows:
        d=scoreby[r['sample_id']]; assert d['final_level']==r['final_level']
        o={k:r[k] for k in ['sample_id','student_id','final_level']}
        for dim in DIMS:
            for suffix in ['mean','rater_A','rater_B']:o[dim+'_'+suffix]=float(d[dim+'_'+suffix])
        result.append(o)
    return result
def corp_hash(rows):return hashlib.sha256(jd([(r['prompt_text'],r['final_level']) for r in rows]).encode()).hexdigest()
FITS=0;CACHE={}
def fitpred(data,test):
    global FITS
    key=(corp_hash(data),tuple(r['sample_id'] for r in test))
    if key not in CACHE:
        model=Classifier().fit([r['prompt_text'] for r in data],[r['final_level'] for r in data])
        CACHE[key]=model.probs([r['prompt_text'] for r in test]);FITS+=1
    return CACHE[key]
def generated_checks(rows,train,test,quotas):
    ids={r['sample_id'] for r in train}; held={r['sample_id'] for r in test}
    assert not ids&held
    assert not {r['student_id'] for r in train}&{r['student_id'] for r in test}
    assert dict(Counter(r['final_level'] for r in rows))==quotas
    assert len({feature_key(r['prompt_text']) for r in rows})==len(rows)
    for r in rows:
        if 'parent_id' in r:assert r['parent_id'] in ids and r['parent_id'] not in held
    # Audit only: never filter generation based on held-out text.
    return {'exact_held_text_overlap':len({F.normalize_prompt(r['prompt_text']) for r in rows}&{F.normalize_prompt(r['prompt_text']) for r in test}),
            'masked_held_text_overlap':len({feature_key(r['prompt_text']) for r in rows}&{feature_key(r['prompt_text']) for r in test})}
from common import F

def logic_checks(cal):
    quotas={'high':12,'medium':12,'low':12};seed=120141
    a=generate(cal,quotas,seed);b=generate(cal,quotas,seed);assert a==b
    changed=[dict(r,**{d+'_mean':1. for d in DIMS}) for r in cal]
    changed2=[dict(r,**{d+'_mean':5. for d in DIMS}) for r in cal]
    ids=lambda rr:[r['candidate_id'] for r in rr]
    effects={}
    for d in DIMS:
        c=[dict(r,**{d+'_mean':6-r[d+'_mean']}) for r in cal]
        x=generate(c,quotas,seed);effects[d]=sum(p!=q for p,q in zip(ids(a),ids(x)))
        assert effects[d]>0,f'{d} has no effect on generated text'
    assert ids(generate(changed,quotas,seed,mode='uniform'))==ids(generate(changed2,quotas,seed,mode='uniform'))
    onlyls=[dict(r,L_mean=6-r['L_mean'],S_mean=6-r['S_mean']) for r in cal]
    assert ids(generate(cal,quotas,seed,mode='AP'))==ids(generate(onlyls,quotas,seed,mode='AP'))
    try:generate([dict(cal[0],prompt_text='forbidden')]+cal[1:],quotas,seed)
    except AssertionError:pass
    else:raise AssertionError('Real text accepted by generator')
    hold,hm=build_pool('heldout')
    assert not {r['feature_key'] for r in POOL}&{r['feature_key'] for r in hold}
    assert not {r['surface_family'] for r in POOL}&{r['surface_family'] for r in hold}
    assert not {r['task_id'] for r in POOL}&{r['task_id'] for r in hold}
    return {'same_seed_exact_reproduction':True,'each_dimension_changes_text_count_of_36':effects,
            'uniform_ignores_scores':True,'AP_ignores_LS':True,'real_text_input_rejected':True,
            'train_vs_heldout_wording_tasks_masked_text_disjoint':True,'math_construction_checks':True,
            'pool':META,'heldout_pool':hm,'all_generated_human_review':'pending'}

def main():
    event('start',purpose='G0/G1候选比较，合成主训练、真实混合辅助')
    sources=[OLD/'code'/n for n in ['controlled_text.py','common.py','legacy_features.py','bounded_mask.py']]
    sources += [OLD/'results/E2_summary.json',OLD/'results/E2_repeat_metrics.csv',OLD/'data/E2_family_calibration_splits.json',OLD/'data/anonymous_samples_snapshot.json',ROOT/'参数验证与生成器比较20261014/四维均值_真实R1_47条.csv',ROOT/'参数验证与生成器比较20261014/四维均值数据说明.json',ROOT/'7月数据/依赖标注数据库.db',OUT/'01_执行前协议.md',Path(__file__),OUT/'code/g1_generator.py']
    sourcehash={str(p.relative_to(ROOT)):sha(p) for p in sources}
    for p in sources[:7]:
        dest=OUT/'archive'/p.name
        if dest.exists():assert sha(dest)==sha(p),'Frozen archive differs'
        else:shutil.copy2(p,dest)
    manifest={'time':datetime.now().astimezone().isoformat(),'sources':sourcehash,'python':sys.version,'sklearn':sklearn.__version__,'numpy':np.__version__,'seeds':SEEDS,'tau_candidates':[.5,1.,2.],'human_review':'pending','real_label_changes':0,'paid_calls':0,'notes':'G0 frozen archive; source calibration text excluded from G1; retrospective internal evaluation'}
    save('data/frozen_manifest.json',manifest)
    real,_,_,_=load(); assert len(real)==47 and len({r['student_id'] for r in real})==47
    records=list(csv.DictReader(sources[8].open(encoding='utf-8-sig')));scoreby={r['sample_id']:r for r in records}
    assert set(scoreby)=={r['sample_id'] for r in real}
    for r in records:
      for d in DIMS:assert float(r[d+'_mean'])==(float(r[d+'_rater_A'])+float(r[d+'_rater_B']))/2
    inputmanifest=json.loads(sources[9].read_text(encoding='utf-8'))
    assert sha(sources[8])==inputmanifest['files'][sources[8].name]['sha256']
    for p,h in inputmanifest['source_hashes'].items():assert sha(ROOT/p)==h
    audit=logic_checks(calibration_rows(real,scoreby));save('results/preflight_logic_checks.json',audit)
    event('preflight_pass',pool=META,checks=audit['each_dimension_changes_text_count_of_36'])
    csvsave('data/G1_candidate_pool.csv',POOL)
    splits=json.loads((OLD/'data/E2_family_calibration_splits.json').read_text(encoding='utf-8'))
    names=['G0_synth','G1_ALSP_synth','G1_bank_uniform_synth','G1_AP_synth','real_only','G0_mixed','G1_ALSP_mixed','G1_bank_uniform_mixed','G1_AP_mixed','G1_raterA_synth','G1_raterB_synth']
    pp={n:np.zeros((5,47,3)) for n in names};pos={r['sample_id']:i for i,r in enumerate(real)}
    y=[r['final_level'] for r in real]; predictions=[];repeats=[];inners=[];foldaudits=[];generated=[]
    for si,seed in enumerate(SEEDS):
      for split in [s for s in splits if s['seed']==seed]:
        fold=split['fold'];tr=[r for r in real if r['sample_id'] in split['training_real_ids']];te=[r for r in real if r['sample_id'] in split['heldout_real_ids']]
        cal=calibration_rows(tr,scoreby);ty=np.array([r['final_level'] for r in tr]);ips={t:np.zeros((len(tr),3)) for t in [.5,1.,2.]};inside=[]
        for j,(a,b) in enumerate(StratifiedKFold(3,shuffle=True,random_state=seed*100+fold).split(np.zeros(len(tr)),ty)):
            itr=[tr[i] for i in a];ite=[tr[i] for i in b];ical=calibration_rows(itr,scoreby);sseed=seed*10000+fold*100+j
            g0,_=calibrated(itr,sseed);q=dict(Counter(r['final_level'] for r in g0))
            for tau in [.5,1.,2.]:
                g=generate(ical,q,sseed,tau=tau);generated_checks(g,itr,ite,q);ips[tau][b]=fitpred(g,ite)
            inside.append({'inner_fold':j,'calibration_ids':[r['sample_id'] for r in itr],'validation_ids':[r['sample_id'] for r in ite],'quota':q})
        im={t:metrics(ty,p) for t,p in ips.items()};chosen=max(im,key=lambda t:(im[t]['macro_f1'],t==1.,-abs(t-1.),-t))
        for t,m in im.items():inners.append({'seed':seed,'fold':fold,'tau':t,'macro_f1':m['macro_f1'],'accuracy':m['accuracy'],'selected':t==chosen})
        sseed=seed*100+fold;g0,g0cal=calibrated(tr,sseed);q=dict(Counter(r['final_level'] for r in g0))
        g1=generate(cal,q,sseed,tau=chosen);gu=generate(cal,q,sseed,mode='uniform',tau=chosen);gap=generate(cal,q,sseed,mode='AP',tau=chosen)
        ga=generate(cal,q,sseed,tau=chosen,rater='rater_A');gb=generate(cal,q,sseed,tau=chosen,rater='rater_B')
        gens={'G0':g0,'G1_ALSP':g1,'G1_bank_uniform':gu,'G1_AP':gap,'G1_raterA':ga,'G1_raterB':gb};checks={}
        for name,rr in gens.items():
            checks[name]=generated_checks(rr,tr,te,q)
            for i,r in enumerate(rr):generated.append({'seed':seed,'fold':fold,'generator':name,'synthetic_row':i,**r})
        corpora={'G0_synth':g0,'G1_ALSP_synth':g1,'G1_bank_uniform_synth':gu,'G1_AP_synth':gap,'real_only':tr,'G0_mixed':g0+tr,'G1_ALSP_mixed':g1+tr,'G1_bank_uniform_mixed':gu+tr,'G1_AP_mixed':gap+tr,'G1_raterA_synth':ga,'G1_raterB_synth':gb}
        for name,data in corpora.items():
            probs=fitpred(data,te)
            for r,p in zip(te,probs):
                pp[name][si,pos[r['sample_id']]]=p
                predictions.append({'variant':name,'seed':seed,'fold':fold,'sample_id':r['sample_id'],'student_id':r['student_id'],'truth':r['final_level'],'prediction':LAB[int(p.argmax())],**{'p_'+k:float(p[i]) for i,k in enumerate(LAB)}})
        foldaudits.append({'seed':seed,'fold':fold,'train_ids':[r['sample_id'] for r in tr],'heldout_ids':[r['sample_id'] for r in te],'selected_tau':chosen,'inner':inside,'g0_calibration':g0cal,'quotas':q,'generation_checks':checks,'generator_hashes':{k:corp_hash(v) for k,v in gens.items()}})
        # Checkpoints retain progress even if a later fold fails.
        csvsave('results/inner_selection.csv',inners);csvsave('results/predictions.csv',predictions);save('data/fold_audit.json',foldaudits)
        event('outer_fold_complete',seed=seed,fold=fold,tau=chosen,quotas=q,total_fits=FITS)
      for name in names:repeats.append({'variant':name,'seed':seed,**metrics(y,pp[name][si])})
      csvsave('results/repeat_metrics.csv',repeats)
      event('repeat_complete',seed=seed,macro_f1={n:round(metrics(y,pp[n][si])['macro_f1'],4) for n in names})
    csvsave('data/generated_outer_corpora.csv',generated)
    summaries={name:{k:float(np.mean([r[k] for r in repeats if r['variant']==name])) for k in ['macro_f1','accuracy','high_recall','high_to_low','brier_multiclass']} for name in names}
    for name in names:
        cms=np.array([r['confusion_matrix'] for r in repeats if r['variant']==name]);summaries[name]['confusion_matrix_sum_repeated_predictions']=cms.sum(axis=0).tolist()
        summaries[name]['low_to_high']=float(np.mean([m[2,0]/m[2].sum() for m in cms]))
        summaries[name]['recall_by_class']={k:float(np.mean([m[i,i]/m[i].sum() for m in cms])) for i,k in enumerate(LAB)}
    old=json.loads((OLD/'results/E2_summary.json').read_text(encoding='utf-8'))
    for name,oldname in [('G0_synth','parameter_primary'),('G0_mixed','parameter_real'),('real_only','real_only')]:
        for metric in ['accuracy','macro_f1']:assert abs(summaries[name][metric]-old[oldname][metric]['mean'])<1e-8,(name,'legacy reproduction fails')
    yi=np.array([LAB.index(v) for v in y]);pred={n:p.argmax(2) for n,p in pp.items()}
    def score(p,idx):
        vals=[]
        for v in p:
            cm=np.bincount(yi[idx]*3+v[idx],minlength=9).reshape(3,3);den=cm.sum(0)+cm.sum(1)
            vals.append(np.divide(2*np.diag(cm),den,out=np.zeros(3),where=den>0).mean())
        return np.mean(vals)
    pairs=[('G1_ALSP_synth','G0_synth'),('G1_ALSP_synth','G1_bank_uniform_synth'),('G1_ALSP_synth','G1_AP_synth'),('G0_mixed','G0_synth'),('G1_ALSP_mixed','G1_ALSP_synth'),('G1_ALSP_mixed','G0_mixed'),('G1_raterA_synth','G1_ALSP_synth'),('G1_raterB_synth','G1_ALSP_synth')]
    rng=np.random.default_rng(20261014);bs={n:[] for n in names}
    for _ in range(2000):
        idx=rng.integers(0,47,47)
        for name in names:bs[name].append(score(pred[name],idx))
    differences=[]
    for a,b in pairs:
        delta=np.array(bs[a])-np.array(bs[b]);vals=[metrics(y,pp[a][i])['macro_f1']-metrics(y,pp[b][i])['macro_f1'] for i in range(5)]
        differences.append({'comparison':a+' minus '+b,'delta_macro_f1':summaries[a]['macro_f1']-summaries[b]['macro_f1'],'conditional_95_lo':float(np.quantile(delta,.025)),'conditional_95_hi':float(np.quantile(delta,.975)),'repeat_deltas':vals})
    csvsave('results/comparisons.csv',differences)
    profile_stats={}
    for name in ['G1_ALSP','G1_bank_uniform','G1_AP','G1_raterA','G1_raterB']:
        rr=[r for r in generated if r['generator']==name]
        profile_stats[name]={d:{'target_mean':float(np.mean([r['target_profile'][j] for r in rr])),'prototype_mean':float(np.mean([r['profile'][j] for r in rr])),'mean_absolute_target_gap':float(np.mean([r['profile_abs_error'][j] for r in rr]))} for j,d in enumerate(DIMS)}
    save('results/profile_fidelity_diagnostic.json',profile_stats)
    # Blinded review packet: one unique text per observed (class, prototype) + G0 class examples.
    review=[];seen=set()
    for r in generated:
        if r['generator']=='G1_ALSP':
            key=(r['final_level'],tuple(r['profile']))
            if key not in seen:seen.add(key);review.append(r)
    for k in LAB:review.extend([r for r in generated if r['generator']=='G0' and r['final_level']==k][:8])
    rng=np.random.default_rng(20261015);order=rng.permutation(len(review));blind=[];answer=[]
    for i,j in enumerate(order):
        r=review[j];rid=f'R{i+1:03d}'
        blind.append({'review_id':rid,'prompt_text':r['prompt_text'],'reviewer':'','proposed_level':'','A':'','L':'','S':'','P':'','contradiction_or_math_issue':'','evidence':''})
        answer.append({'review_id':rid,**r})
    csvsave('review/盲审待填.csv',blind);save('review/目标与来源_审后核对.json',answer)
    unchanged=all(sha(ROOT/p)==h for p,h in sourcehash.items());assert unchanged
    outcome={'status':'completed_candidate_comparison','n_real_students':47,'repeats':5,'folds_per_repeat':4,'fits':FITS,'selected_tau_counts':dict(Counter(a['selected_tau'] for a in foldaudits)),'metrics':summaries,'comparisons':differences,'G0_and_real_baselines_reproduced':True,'source_hashes_unchanged':unchanged,'all_folds_budget_and_parent_isolation_passed':True,'heldout_text_overlap_totals':{k:sum(v[k] for a in foldaudits for v in a['generation_checks'].values()) for k in ['exact_held_text_overlap','masked_held_text_overlap']},'review_packet_n':len(blind),'independent_human_review':'pending','actual_label_changes':0,'paid_calls':0,'deployed_model_changed':False,'scope':'Retrospective internal candidate comparison; not behavioral improvement, not fully human-validated generated corpus.'}
    save('results/summary.json',outcome)
    event('completed',metrics={n:{'macro_f1':m['macro_f1'],'accuracy':m['accuracy']} for n,m in summaries.items()},unchanged=unchanged,independent_review='pending')
if __name__=='__main__':
    try:main()
    except Exception as e:
        event('failed',error=str(e),traceback=traceback.format_exc());raise
