"""Frozen engineering grammar; labels are candidate specifications, not human validation."""
from collections import Counter
import numpy as np
from common import LAB,F,B
GRAMMAR={
'high':[
 '把{task}的最终答案给我，不用讲方法。','{task}我不打算自己做，请你替我做完。',
 '帮我把{task}的完整演算和结果写好，我直接照着填。','只要{task}的结果，解释就免了。',
 '别让我列步骤，{task}从开始到结尾你都写出来。','{task}需要交作业，发我可以直接抄的解答。',
 '我没有算{task}，你直接完成全部步骤。','{task}麻烦报最后得数，不需要让我理解。',
 '不用提示了，直接告诉我{task}等于多少。','我不想分析{task}，帮我生成完整答案。',
 '关于{task}，请包办这题的解答，我不参与计算。','把{task}的答案连同所有过程发来，我复制过去。',
 '这题{task}我只想拿到结果，替我算完吧。','我不准备自己推，{task}你把解答写齐。',
 '不要追问我的思路，直接交给我{task}的全套解法。','完成{task}后把最后数字告诉我，学习方法先不管。'],
'medium':[
 '{task}应该怎样开始？我还没有列步骤。','我想理解{task}的解题方法，请说明第一步要考虑什么。',
 '不是要你直接报答案，我需要从头理解{task}该怎么想。','{task}我试着想过，但说不出具体步骤，可以教我起步吗？',
 '我还没动笔做{task}，请解释适用的方法。','想学会{task}，能先说明解题思路吗？',
 '为什么{task}能这样处理？我目前只有题干，没有推导。','{task}我没有思路，先讲一下怎么找到入口。',
 '不用直接算出结果，说明{task}的基本操作顺序就行，我还没开始。','我试了很久仍然没有步骤，{task}该用哪种方法？',
 '请教我{task}的起步策略，暂时没有自己的演算。','我愿意跟着学{task}，但还没有列出任何式子。',
 '{task}我不知道从哪里下手，需要解释思路。','我没有写过计算，怎样理解{task}的处理方法？',
 '能解释{task}从题目条件到第一步的思考吗？我尚未尝试。','{task}请先带我理解方法，不要只给一个答案，我没列出步骤。'],
'low':[
 '{task}。{attempt}。请检查这一步的依据，不要直接给最后答案。',
 '关于{task}，{attempt}，我想自己往下做，只给下一步提示。',
 '我已经尝试{task}：{attempt}。这个起步理由是否成立？',
 '{attempt}，这是我处理{task}的过程。请指出哪里需要核对。',
 '我对{task}先写了如下推导：{attempt}。希望理解这一变形的原理。',
 '{task}我已经开始算，{attempt}，只帮我检查这一环。',
 '不用替我完成{task}，{attempt}；请提示我应检查什么。',
 '我的思路是{attempt}，对应题目{task}。能核对这个依据吗？',
 '我先做了{task}的起步：{attempt}。想自己完成，只请你指出错误。',
 '{task}中我已经列出{attempt}。下一步的依据我想弄清楚，不要直接解完。',
 '我自己推{task}，目前{attempt}。解释我这一步为什么可行就好。',
 '请针对我的步骤给提示：题目{task}，我的推导{attempt}，结果我自己算。',
 '对于{task}，我已写到这里：{attempt}。只需要这一步的反馈。',
 '我算{task}时得到如下关系：{attempt}。可以检查逻辑而不公布答案吗？',
 '{attempt}。这是我自主处理{task}的起点，请帮助定位这一步的问题。',
 '我已经有{task}的推导，{attempt}，请解释这一依据，我继续自己做。']}
def tasks(indices):
 out=[]
 for i in indices:
    a,b=i+2,i+4
    out.append({'task_id':f'q_{i}','task':f'解方程x²−{a+b}x+{a*b}=0',
                'attempt':f'我已把它写成两个一次式相乘，需要两数的和为−{a+b}且积为{a*b}'})
    k,t=i%5+2,i+3;rhs=k*t+4
    out.append({'task_id':f'l_{i}','task':f'解方程{k}x+4={rhs}',
                'attempt':f'我先两边同时减4，得到{k}x={rhs-4}'})
    den=i+5
    out.append({'task_id':f'f_{i}','task':f'计算2/{den}+3/{den}',
                'attempt':f'我先保留相同分母{den}，把分子2和3相加'})
    base,height=i+4,i+6
    out.append({'task_id':f'g_{i}','task':f'求底{base}厘米高{height}厘米的三角形面积',
                'attempt':f'我已写出底乘高除以2，即{base}×{height}÷2'})
 return out
def pool(split='train'):
 idx=range(12) if split=='train' else range(12,16);tt=tasks(range(6) if split=='train' else range(6,9))
 raw=[]
 for lv in LAB:
  for j in idx:
   for t in tt:
    text=GRAMMAR[lv][j].format(**t)
    raw.append({'prompt_text':text,'final_level':lv,'template_family':f'{lv}_{j}','task_id':t['task_id'],
                'split':split,'label_basis':'frozen_controlled_grammar','human_review':'pending',
                'feature_key':B.safe_mask(F.normalize_prompt(text))})
 # Mask-identical variants count once. Avoid manufacturing extra training weight with math numbers.
 unique={}
 for r in raw:
    key=r['feature_key']
    if key in unique:assert unique[key]['final_level']==r['final_level'],'Conflicting engineering labels'
    else:unique[key]=r
 return raw,list(unique.values())
def calibrated(training_real,seed):
 _,candidate=pool();rng=np.random.default_rng(seed)
 counts=np.array([sum(r['final_level']==k for r in training_real) for k in LAB]);prob=(counts+.5)/(len(training_real)+1.5)
 selected=[]
 for k,p in zip(LAB,prob):
    eligible=[r for r in candidate if r['final_level']==k]
    n=min(len(eligible),max(8,round(200*p)))
    selected.extend(eligible[i].copy() for i in rng.choice(len(eligible),n,replace=False))
 return selected,{'calibration_ids':[r['sample_id'] for r in training_real],
                  'initial_distribution_jeffreys_smoothing':prob.tolist(),
                  'n_unique_prompts':len(selected),'classes':dict(Counter(r['final_level'] for r in selected)),
                  'language_grammar':'engineering_candidates_pending_human_review',
                  'caps':'200*p per class capped by distinct masked text; minimum8 per class'}
