"""Auditable local text classifiers / real-crossfit calibrated lexical retrieval."""
from pathlib import Path
import sys
from collections import Counter
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'数学主线严谨重跑20260930/code'))
from common import Classifier, F, B, LAB, ACK

def norm(text):return B.safe_mask(F.normalize_prompt(text))
def terms(text):
    text=norm(text)
    return Counter(text[i:i+2] for i in range(max(len(text)-1,0))) or Counter({text:1})

class BM25:
    def __init__(self,records,labels):
        self.labels=list(labels);self.records=records
        self.truth=np.array([r['final_level'] for r in records])
        docs=[terms(r['prompt_text']) for r in records]
        self.vocabulary=sorted(set().union(*(set(d) for d in docs)))
        self.index={k:i for i,k in enumerate(self.vocabulary)}
        lengths=np.array([sum(d.values()) for d in docs],float)
        tf=np.zeros((len(docs),len(self.index)))
        for i,doc in enumerate(docs):
            for term,count in doc.items():tf[i,self.index[term]]=count
        df=(tf>0).sum(0);idf=np.log(1+(len(docs)-df+.5)/(df+.5))
        self.weights=idf[None,:]*tf*2.2/(tf+1.2*(.25+.75*lengths[:,None]/lengths.mean()))
    def scores(self,texts):
        query=np.zeros((len(texts),len(self.index)))
        for i,text in enumerate(texts):
            for term in terms(text):
                if term in self.index:query[i,self.index[term]]=1
        all_scores=query@self.weights.T
        result=np.zeros((len(texts),len(self.labels)))
        for j,label in enumerate(self.labels):
            values=all_scores[:,self.truth==label]
            if values.shape[1]:result[:,j]=np.sort(values,axis=1)[:,-min(3,values.shape[1]):].mean(1)
        return result

def score_features(scores):
    # Query-normalized class similarities: bounded ratios plus overall match magnitude.
    peak=scores.max(1,keepdims=True)
    return np.hstack([np.divide(scores,peak,out=np.zeros_like(scores),where=peak>0),np.log1p(peak)])

class CalibratedBM25:
    def __init__(self,records,labels,inner_scores,inner_truth):
        self.labels=list(labels);self.retrieval=BM25(records,labels)
        self.scaler=StandardScaler().fit(score_features(inner_scores))
        self.mapping=LogisticRegression(C=1.,class_weight='balanced',solver='lbfgs',max_iter=4000).fit(
            self.scaler.transform(score_features(inner_scores)),inner_truth)
        self.intent=False;self.mask='bounded'
    def probs(self,texts,labels=LAB):
        p=self.mapping.predict_proba(self.scaler.transform(score_features(self.retrieval.scores(texts))))
        return np.column_stack([p[:,list(self.mapping.classes_).index(k)] if k in self.mapping.classes_ else np.zeros(len(texts)) for k in labels])

def fit_lr(records,following=False):
    return Classifier(intent=False,context=following).fit([r['prompt_text'] for r in records],[r['final_level'] for r in records])
