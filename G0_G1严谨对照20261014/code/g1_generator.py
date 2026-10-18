"""Empirical joint ALSP-conditioned semantic grammar. All scores are prototypes,
not independently human-rated synthetic data. No student text is an input."""
import sys, itertools, hashlib, json
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'数学主线严谨重跑20260930/code'))
from common import LAB,F,B
DIMS=['A','L','S','P']
DOMAINS={'high':[[1,2],[1,3,5],[1,3,5],[1,3]],
         'medium':[[3,4],[3,5],[2,3,5],[1,3]],
         'low':[[4,5],[3,5],[3,5],[4,5]]}

def tasks(i):
    a,b=i+2,i+5;k=i%4+2;x=i+4;d=i+7;base=i+5;height=i+8
    return [
      dict(id=f'q{i}',question=f'解方程x²−{a+b}x+{a*b}=0',concept='因式分解',focus=f'怎样找到和为−{a+b}、积为{a*b}的两个数',
           clue='我想到用因式分解，要先找两个合适的数',step=f'我先试了−{a}和−{b}，它们的和是−{a+b}，积是{a*b}',next='怎样把这两个数写进两个一次式',check=(a+b,a*b)),
      dict(id=f'l{i}',question=f'解方程{k}x+3={k*x+3}',concept='等式的性质',focus='等式两边应该先作什么相同的运算',
           clue='我想到等式两边可以同时减去同一个数',step=f'我先把两边都减3，写成{k}x={k*x}',next='接下来怎样把x的系数变成1',check=(k*x+3-3,k*x)),
      dict(id=f'f{i}',question=f'计算2/{d}+3/{d}',concept='同分母分数相加',focus='相加时分母是否需要改变',
           clue='我发现两个分数的分母相同，想到先处理分子',step=f'我先写成(2+3)/{d}，把分子相加得到5',next='分母是否应该保持不变',check=(2+3,5)),
      dict(id=f'g{i}',question=f'求底{base}厘米、高{height}厘米的三角形面积',concept='三角形面积公式',focus='底乘高之后为什么还要除以2',
           clue='我想到先用底乘高，再考虑三角形与平行四边形的关系',step=f'我先算底乘高：{base}×{height}={base*height}',next='为什么还需要把这个结果除以2',check=(base*height,base*height))]

REQ={
 ('high',1):['请直接告诉我最后答案。','把最终结果给我。','这题的答案是多少，直接报结果。','我需要这题的得数，替我算出来。','直接把结果写给我吧。','帮我算出最终答案。','请报出最后的结果。','替我把答案算好。'],
 ('high',2):['请把从头到尾的解答和结果都写出来。','把完整过程和最后答案一起给我。','请替我完成整道题的推导和计算。','从第一步到最后结果都帮我写好。','帮我写一份完整解答，包括答案。','把每一步和最终结果全部算给我。','请完成整题并列出全部步骤。','整道题的步骤和答案都替我写出来。'],
 ('medium',3):['这题应该怎样运用{concept}？','请讲讲{concept}在这题中的解题方法。','这道题用{concept}该怎么起步？','能解释一下这题的{concept}思路吗？','我需要理解{concept}在这里怎么用。','请教我这题的{concept}方法。','这题用{concept}要先考虑什么？','说明一下用{concept}处理这题的思路。'],
 ('medium',4):['请解释{concept}的依据。','我想问{concept}为什么能这样用。','{concept}的原理能讲一下吗？','这题涉及的{concept}是什么意思？','请说明{concept}成立的理由。','能讲清楚{concept}背后的道理吗？','我需要了解{concept}的原理。','请解释这里为什么能用{concept}。'],
 ('low',4):['请检查我这一步的依据。','帮我核对这一步有没有问题。','我写的这一步是否合理？','请指出我这一步哪里需要检查。','帮我看看这一环的理由对不对。','我这一步的逻辑成立吗？','核对我这一小步就可以。','请针对我这一步给反馈。'],
 ('low',5):['只提示我下一步该想什么，剩下的我自己算。','请只核对这一环，不要替我把后面做完。','给我这一小步的提示就好，后续我自己做。','我想自己继续，请只指出这一步要检查什么。','别直接给最后答案，只帮我理解这一处。','只解释我这一环的依据，结果让我自己算。','我自己完成后面的计算，请只给这里的线索。','只帮助我检查当前这一步，不用完整解答。']}
LEARN={1:['我现在只想完成作业。','我只需要先把结果填上。','我主要是要交这份作业。','先让我把这题交上去。','我只想把这道作业做完。','现在只求完成这题。','我先把作业交掉。','目前只需要完成任务。'],
       3:['我想弄明白这道题。','我希望理解这题的做法。','我想学会当前这题的处理。','我想知道这道题为什么这样做。','我希望把这题的思路弄懂。','我想理解这道题的道理。','我想学会这一题。','我希望明白本题的做法。'],
       5:['我还想总结这类题的通用方法。','我想掌握规律，以后能自己做类似题。','我希望学会举一反三的方法。','我还想知道类似题可以怎样处理。','我想总结能用于同类题的思路。','我希望掌握方法并用到其他类似题。','我想找出这类题共同的规律。','我还希望能迁移到同类型题。']}
TRIED=['我想过一会儿，但还没列出具体步骤。','我试着想了，但没有写出式子。','我考虑过了，暂时说不出具体过程。','我自己想了一下，还没有成形的步骤。','我试过思考，不过还没写出推导。','我想了一阵，目前没有可展示的步骤。','我想过这题，但没有列出计算。','我试着分析了，还没形成具体步骤。']

def render(level,profile,style,t):
    a,l,s,p=profile;parts=[]
    if s==1:parts.append('这题。')
    elif s==2:parts.append('关于'+t['concept']+'。')
    elif s>=3 and not (level=='low' and s==3):parts.append(t['question']+'。')
    if s==5:parts.append('我不明白'+(t['next'] if p==5 else t['focus'])+'。')
    if p==3:parts.append(TRIED[style])
    elif p==4:parts.append(t['clue']+'，卡在'+t['focus']+'。')
    elif p==5:parts.append(t['step']+'，接着不确定'+t['next']+'。')
    parts.append(REQ[(level,a)][style].format(**t))
    parts.append(LEARN[l][style])
    return ''.join(parts)

def feature_key(text):return B.safe_mask(F.normalize_prompt(text))

def build_pool(split='train'):
    styles=range(6) if split=='train' else range(6,8)
    indices=range(6) if split=='train' else range(6,9)
    unique={};raw=0
    for lv in LAB:
      for profile in itertools.product(*DOMAINS[lv]):
       for j in styles:
        for i in indices:
         for t in tasks(i):
          assert t['check'][0]==t['check'][1] if t['id'][0]!='q' else (t['check']==(2*i+7,(i+2)*(i+5)))
          text=render(lv,profile,j,t);key=feature_key(text);raw+=1
          r={'prompt_text':text,'final_level':lv,'profile':list(profile),'profile_kind':'engineering_prototype_not_human_rating',
             'task_id':t['id'],'surface_family':f'wording_{j}','program_id':lv+'_'+''.join(map(str,profile)),
             'feature_key':key,'split':split,'human_review':'pending','label_basis':'explicit_request_program_candidate',
             'math_check':list(t['check']),'candidate_id':hashlib.sha256(key.encode()).hexdigest()[:16]}
          if key in unique:
              assert unique[key]['final_level']==lv,'Cross-class grammar collision'
              assert unique[key]['profile']==list(profile),'Same text assigned different prototype'
          else:unique[key]=r
    return list(unique.values()),{'raw':raw,'unique_masked':len(unique),'by_class':dict(Counter(r['final_level'] for r in unique.values()))}

POOL,META=build_pool()
GROUPS={lv:defaultdict(list) for lv in LAB}
for row in POOL:GROUPS[row['final_level']][tuple(row['profile'])].append(row)

def generate(calibration,quotas,seed,mode='ALSP',tau=1.,rater='mean'):
    assert mode in ['ALSP','AP','uniform'];assert tau>0
    assert all('prompt_text' not in r for r in calibration),'Generator must not receive real text'
    rng=np.random.default_rng(seed);donor_rng=np.random.default_rng(seed+7321);result=[]
    dims=[0,3] if mode=='AP' else [0,1,2,3]
    for lv in LAB:
      donors=[r for r in calibration if r['final_level']==lv];assert donors
      available={p:list(rr) for p,rr in GROUPS[lv].items()}
      for _ in range(quotas[lv]):
        donor=donors[int(donor_rng.integers(len(donors)))]
        target=np.array([donor[d+'_'+rater] for d in DIMS],float)
        profiles=sorted(p for p,rr in available.items() if rr)
        if not profiles:raise RuntimeError('Unique semantic pool exhausted; no silent truncation')
        delta=np.asarray(profiles,float)[:,dims]-target[dims]
        dist=np.sum(delta**2,axis=1)
        logits=np.zeros(len(profiles)) if mode=='uniform' else -dist/(2*tau*tau)
        weights=np.exp(logits-logits.max());weights/=weights.sum()
        chosen=profiles[int(rng.choice(len(profiles),p=weights))]
        bank=available[chosen];row=bank.pop(int(rng.integers(len(bank)))).copy()
        row.update({'parent_id':donor['sample_id'],'parent_student_id':donor['student_id'],
                    'target_profile':target.tolist(),'active_dimensions':[DIMS[i] for i in dims] if mode!='uniform' else [],
                    'generator_mode':mode,'tau':tau,'rater_source':rater,
                    'profile_abs_error':[abs(float(x)-float(y)) for x,y in zip(row['profile'],target)]})
        result.append(row)
    assert dict(Counter(r['final_level'] for r in result))==quotas
    assert len({r['feature_key'] for r in result})==len(result)
    return result
