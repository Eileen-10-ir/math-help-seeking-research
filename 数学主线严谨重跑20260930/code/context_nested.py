from common import *
from sklearn.model_selection import StratifiedKFold
class BlockContext:
 def __init__(self,weight):
    self.weight=weight;self.current=TfidfVectorizer(analyzer='char',ngram_range=(1,3),max_features=6000,sublinear_tf=True)
    self.history=TfidfVectorizer(analyzer='char',ngram_range=(1,3),max_features=6000,sublinear_tf=True)
    self.model=LogisticRegression(C=2.,class_weight='balanced',max_iter=4000)
 def X(self,current,history,fit=False):
    c=[B.safe_mask(F.normalize_prompt(t)) for t in current];h=[B.safe_mask(F.normalize_prompt(t)) for t in history]
    a=self.current.fit_transform(c) if fit else self.current.transform(c)
    if self.weight==0:return a
    b=self.history.fit_transform(h) if fit else self.history.transform(h)
    return sparse.hstack([a,self.weight*b],format='csr')
 def fit(self,c,h,y):self.model.fit(self.X(c,h,True),y);return self
 def probs(self,c,h):
    p=self.model.predict_proba(self.X(c,h));o=np.zeros((len(c),4))
    for i,k in enumerate(self.model.classes_):o[:,(LAB+[ACK]).index(k)]=p[:,i]
    return o
def run():
 real,eedi,llm,r3=load();by={r['sample_id']:r for r in real};y=np.array([r['final_level'] for r in r3]);labels=LAB+[ACK]
 c=np.array([r['prompt_text'] for r in r3]);h=np.array([by[r['pair_id']]['prompt_text'] for r in r3]);records=[];predictions=[];choices=[]
 for seed in SEEDS:
  p=np.zeros((47,4))
  for fold,(tr,te) in enumerate(StratifiedKFold(4,shuffle=True,random_state=seed).split(c,y)):
    candidates=[]
    for weight in [0,.25,.5,1.]:
      ip=np.zeros((len(tr),4))
      for itr,ite in StratifiedKFold(3,shuffle=True,random_state=seed+fold).split(c[tr],y[tr]):
        m=BlockContext(weight).fit(c[tr[itr]],h[tr[itr]],y[tr[itr]]);ip[ite]=m.probs(c[tr[ite]],h[tr[ite]])
      candidates.append({'weight':weight,'inner_macro_f1':metrics(y[tr],ip,labels)['macro_f1']})
    chosen=max(candidates,key=lambda r:r['inner_macro_f1'])['weight']
    model=BlockContext(chosen).fit(c[tr],h[tr],y[tr]);p[te]=model.probs(c[te],h[te])
    choices.append({'seed':seed,'fold':fold,'chosen_weight':chosen,'inner_candidates':candidates,
                    'training_students':[r3[i]['student_id'] for i in tr],'heldout_students':[r3[i]['student_id'] for i in te]})
    predictions.extend(collect_predictions('E3b_nested_blocks','nested_context',seed,fold,[r3[i] for i in te],p[te],labels))
  records.append({'variant':'nested_context','seed':seed,**metrics(y,p,labels)})
  print(f'E3b nested seed {seed} complete',flush=True)
 write_json('results/E3b_summary.json',{'metrics':summarize(records),'weight_counts':dict(Counter(str(r['chosen_weight']) for r in choices)),
       'median_R1_chars':float(np.median([len(t) for t in h])),'median_R3_chars':float(np.median([len(t) for t in c])),
       'supplement_protocol_sha256':sha(OUT/'上下文补充实验协议.md')})
 write_csv('results/E3b_repeat_metrics.csv',records);write_csv('results/E3b_predictions.csv',predictions);write_json('data/E3b_inner_selection.json',choices)
if __name__=='__main__':run()
