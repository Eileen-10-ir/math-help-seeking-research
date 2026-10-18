from pathlib import Path
import json,csv,sqlite3,hashlib,importlib.util,re
from collections import Counter
import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score,accuracy_score,confusion_matrix,average_precision_score
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parents[1]
for d in ['data','results','figures','report']: (OUT/d).mkdir(exist_ok=True)
LAB=['high','medium','low'];ACK='接受引导/非提问';SEEDS=[17,29,43,71,101]
local_features=OUT/'code/legacy_features.py'
spec=importlib.util.spec_from_file_location('features',local_features if local_features.exists() else ROOT/'7月数据/回填V3/v3_rebuild.py')
F=importlib.util.module_from_spec(spec);spec.loader.exec_module(F)
local_mask=OUT/'code/bounded_mask.py'
spec2=importlib.util.spec_from_file_location('bounded',local_mask if local_mask.exists() else ROOT/'项目复核20260930/masking_diagnostic.py')
B=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(B)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_json(rel,data): (OUT/rel).write_text(json.dumps(data,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)),encoding='utf-8')
def write_csv(rel,rows):
    if not rows:return
    with (OUT/rel).open('w',encoding='utf-8-sig',newline='') as f:
        fields=list(dict.fromkeys(k for r in rows for k in r))
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def load():
    snapshot=OUT/'data/anonymous_samples_snapshot.json'
    if snapshot.exists():
      manifest=json.loads((OUT/'data/input_manifest.json').read_text(encoding='utf-8'))
      assert sha(snapshot)==manifest['anonymous_snapshot_sha256'],'Snapshot changed'
      d=json.loads(snapshot.read_text(encoding='utf-8'));return d['real_r1'],d['eedi_r1'],d['llm_r1'],d['real_r3']
    c=sqlite3.connect((ROOT/'7月数据/依赖标注数据库.db').as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
    samples=[dict(r) for r in c.execute('SELECT * FROM samples ORDER BY sample_id')];c.close()
    real=[r for r in samples if r['round']=='R1' and r['src_real']]
    eedi=[r for r in samples if r['round']=='R1' and r['src_eedi']]
    llm=[r for r in samples if r['round']=='R1' and r['src_llm']]
    lineage=list(csv.DictReader((ROOT/'项目复核20260930/LLM16条_训练开发同源关系.csv').open(encoding='utf-8-sig')))
    parent={r['training_llm_id']:r['development_parent_id'] for r in lineage}
    for r in llm:r['parent_id']=parent[r['sample_id']]
    r3=[r for r in samples if r['round']=='R3' and r['src_real']]
    return real,eedi,llm,r3
def metrics(y,probs,labels=LAB):
    y=np.array(y);probs=np.asarray(probs);pred=np.array(labels)[probs.argmax(axis=1)]
    cm=confusion_matrix(y,pred,labels=labels);n=len(y);hi=labels.index('high');lo=labels.index('low')
    one=np.array([[float(v==k) for k in labels] for v in y])
    return {'n':n,'macro_f1':float(f1_score(y,pred,labels=labels,average='macro',zero_division=0)),
            'accuracy':float(accuracy_score(y,pred)),'high_recall':float(cm[hi,hi]/cm[hi].sum()) if cm[hi].sum() else None,
            'high_to_low':float(cm[hi,lo]/cm[hi].sum()) if cm[hi].sum() else None,
            'brier_multiclass':float(np.mean(np.sum((probs-one)**2,axis=1))),
            'high_pr_auc':float(average_precision_score(y=='high',probs[:,hi])) if any(y=='high') else None,
            'confusion_matrix':cm.tolist()}
class Classifier:
    def __init__(self,intent=True,mask='bounded',balance=True,context=False):
        self.intent=intent;self.mask=mask
        self.vec=TfidfVectorizer(analyzer='char',ngram_range=(1,3) if context else (1,4),max_features=6000 if context else 12000,sublinear_tf=True)
        self.clf=LogisticRegression(C=2.,class_weight='balanced' if balance else None,max_iter=4000,solver='lbfgs')
    def x(self,texts,fit=False):
        nt=[F.normalize_prompt(t) for t in texts]
        mask=B.safe_mask if self.mask=='bounded' else (F.mask_math_content if self.mask=='old' else lambda t:t)
        z=[mask(t) for t in nt];x=self.vec.fit_transform(z) if fit else self.vec.transform(z)
        if self.intent:x=sparse.hstack([sparse.csr_matrix(np.vstack([F.extract_intent_features(t) for t in texts])),x],format='csr')
        return x
    def fit(self,texts,y):self.clf.fit(self.x(texts,True),y);return self
    def probs(self,texts,labels=LAB):
        p=self.clf.predict_proba(self.x(texts));o=np.zeros((len(texts),len(labels)))
        for i,k in enumerate(self.clf.classes_):o[:,labels.index(k)]=p[:,i]
        return o
def majority(y,n,labels=LAB):
    k=Counter(y).most_common(1)[0][0];p=np.zeros((n,len(labels)));p[:,labels.index(k)]=1;return p
def collect_predictions(experiment,variant,seed,fold,records,probs,labels=LAB):
    return [{'experiment':experiment,'variant':variant,'seed':seed,'fold':fold,'sample_id':r['sample_id'],
             'student_id':r.get('student_id',''),'truth':r['final_level'],'prediction':labels[int(np.argmax(p))],
             **{'p_'+k:float(p[i]) for i,k in enumerate(labels)}} for r,p in zip(records,probs)]
def summarize(records):
    result={}
    for name in sorted({r['variant'] for r in records}):
        rr=[r for r in records if r['variant']==name]
        result[name]={'repeats':len(rr),'n_per_repeat':rr[0]['n'],
                      **{k:{'mean':float(np.mean([r[k] for r in rr])), 'min':float(min(r[k] for r in rr)), 'max':float(max(r[k] for r in rr))} for k in ['macro_f1','accuracy','high_recall','high_to_low','brier_multiclass','high_pr_auc']}}
    return result
def source_manifest():
    if not (ROOT/'7月数据/依赖标注数据库.db').exists():
      info=json.loads((OUT/'data/input_manifest.json').read_text(encoding='utf-8'))
      assert info['protocol_sha256']==sha(OUT/'冻结重跑协议.md')
      assert info['anonymous_snapshot_sha256']==sha(OUT/'data/anonymous_samples_snapshot.json')
      return info
    files=[ROOT/'7月数据/依赖标注数据库.db',ROOT.parent/'申报书2026_1.pdf',ROOT/'7月数据/标注合并入库/合并结果_最终整合.xlsx',ROOT/'7月数据/R3标注/合并结果_R3_47条.xlsx']
    dbhash=sha(files[0]);assert dbhash=='2eaf9918bddbee3f3a9d108b840ff77e7b0228c92c02ceb6323de3a44739e3dd'
    info={'protocol_sha256':sha(OUT/'冻结重跑协议.md'),'sources':{str(p):sha(p) for p in files},'seeds':SEEDS,'new_real_data':False,'paid_calls':0}
    snapshot=OUT/'data/anonymous_samples_snapshot.json'
    if snapshot.exists():info['anonymous_snapshot_sha256']=sha(snapshot)
    write_json('data/input_manifest.json',info);return info
