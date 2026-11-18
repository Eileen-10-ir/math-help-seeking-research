"""Controlled ablations of the existing calibrated sampler; original labels preserved."""
import numpy as np
from g1_generator import GROUPS,DIMS,LAB
from joint_renderer import make_spec,realize_unique
from independent_contract_check import check_contract

def generate_variant(calibration,kinds,quotas,seed,tau=1.,mode='ALSP',rater='mean'):
    dims={'ALSP':[0,1,2,3],'ALP':[0,1,3],'uniform':[]}[mode]
    assert all('prompt_text' not in r for r in calibration)
    rng=np.random.default_rng(seed);donor_rng=np.random.default_rng(seed+7321)
    rows=[];seen=set()
    for level in LAB:
        donors=[r for r in calibration if r['final_level']==level]
        available={p:list(rr) for p,rr in GROUPS[level].items()}
        for _ in range(quotas[level]):
            donor=donors[int(donor_rng.integers(len(donors)))]
            target=np.array([donor[d+'_'+rater] for d in DIMS],float)
            profiles=sorted(p for p,rr in available.items() if rr)
            if not profiles:raise RuntimeError('Unique pool exhausted')
            dist=np.sum((np.asarray(profiles,float)[:,dims]-target[dims])**2,axis=1)
            logits=-dist/(2*tau*tau);w=np.exp(logits-logits.max());w/=w.sum()
            profile=profiles[int(rng.choice(len(profiles),p=w))];bank=available[profile]
            row=bank.pop(int(rng.integers(len(bank)))).copy()
            row.update(parent_id=donor['sample_id'],parent_student_id=donor['student_id'],target_profile=target.tolist(),tau=tau,seed=seed,fold=-1,synthetic_row=len(rows))
            spec=make_spec(row,kinds[donor['sample_id']]);text,question,_=realize_unique(spec,seen)
            assert check_contract(spec,text,question)['status']=='pass'
            rows.append(dict(prompt_text=text,final_level=level,parent_id=donor['sample_id'],spec=spec))
    return rows
