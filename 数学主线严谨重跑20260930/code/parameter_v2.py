"""Frozen exploratory grammar; every generated label remains pending human review."""
from common import *
from controlled_text import tasks
GR={
 'high':[
 '给我这题的答案。','这道题你替我做完。','把全部步骤发我。','我只要最后结果。','别解释，直接算好。','图片题直接给答案。','整题帮我包办。','我不做，你解完。',
 '{task}，帮我把答案写出来就行。','{task}，全部过程替我算，我照抄。','我不想自己推，{task}直接解完。','题目是{task}。不用提示我，发完整解答。','{task}快给最终结果，我先填上。','求{task}的答案，不需要学方法。','请你从头到尾完成{task}，我不参与。','{task}我只需要可以复制的全套解法。',
 '这道{task}要交了。我没有算，也不打算分析，把完整答案和步骤给我抄一下。','请帮我代做{task}，我只想拿到正确结果，原理和提示都不用讲。',
 '我不想列式研究{task}。你把整个解题过程写完，我直接按照你的结果填写。','遇到{task}我不准备自己做，发一份从第一步到最后答案的完整解答。',
 '{task}我等着交作业。请直接替我完成，不要让我先试，也不要追问我的想法。','麻烦把{task}的标准答案和所有计算一次给我，我不需要说明为什么。',
 '这题{task}只要结果，全部步骤也替我完成，我没有学习方法的打算。','我现在只想复制{task}的解答，不愿动笔推理，你从头算到结尾。'],
 'medium':[
 '这道题怎么做？','没思路，教我起步。','要用什么方法？','讲讲解题思路。','我试过，但没写步骤。','别只报答案，讲方法。','我还没开始，给点提示。','这题怎么理解呀？',
 '{task}，我不会起步，能讲讲方法吗？','{task}我有点懵，先告诉我从哪想。','我想学{task}的思路，还没写出式子。','请带我理解{task}，不要只发答案。','{task}我试过，但没形成可描述的步骤。','题目{task}。我暂时没动笔，教我第一步。','{task}需要用什么方法？我目前没自己的演算。','不需要直接给结果，{task}如何起步？',
 '关于{task}，我想真正弄懂解题办法，但现在不知道第一步该怎样想，也没有列式。','我看了{task}一会儿，还是没形成具体步骤。能先解释适用的思路吗？',
 '请教我{task}从条件到起步的过程，我希望跟着理解，暂时没有可展示的推导。','不是为了直接抄答案，我想理解{task}，不过自己还没算，请说明起步方法。',
 '我试着思考{task}但只有大概感觉，说不出哪一步。需要你带我找到入口。','{task}我不想只知道一个数字，希望学会思路，但还没列出自己的步骤。',
 '面对{task}我很困惑，没有任何具体演算。请讲解怎么分析条件和选择方法。','能先给{task}的方法提示吗？我愿意接着试，不过现在还没有前置推导。'],
 'low':[
 '{concept}是什么意思？','什么叫{concept}？','解释{concept}的定义。','{brief}，依据对吗？','我写了{brief}，检查这步。','{brief}，只给下一步提示。','{concept}能举个例子吗？','我列出{brief}，请核对理由。',
 '我做{task}先写了{brief}。这一步的依据是什么？','{task}：{attempt}。只帮我核对这一环。','不用解完{task}，我已写{brief}，提示我该检查哪一步。','我想理解{concept}这个术语本身，不是请你算整题，能说明定义吗？','{attempt}。这是我做{task}的过程，结果留给我自己算。','关于{task}，我已写到{brief}，想弄清这一步的原理。','我不懂{concept}的含义，希望先弄明白概念并看一个例子。','请只检查我的步骤：{task}，{attempt}。',
 '我已经对{task}做了尝试：{attempt}。希望你解释我这一步的理由，不要把后面全部算出来。','在{task}里我先写了{brief}。我想自己继续完成，请指出这一步该怎样核对。',
 '我不需要这一题的完整解答，只是想弄懂{concept}的定义和适用含义，请用一个例子说明。','这是我处理{task}的推导：{attempt}。请针对我的依据给反馈，最终计算我继续做。',
 '我对{task}目前的步骤是{brief}，想自己走完后续过程，只需要核实这一变形为什么成立。','我在理解{concept}这个概念，不涉及请求题目的最终答案，希望学会它的含义并自己举例。',
 '处理{task}时我先写{brief}。能解释这一操作的道理，而让我自主完成剩余推导吗？','我已写出{task}的这一步：{attempt}。我希望得到针对这一步的提示，而非完整代答。']}
TRAIN_INDEX=list(range(6))+list(range(8,14))+list(range(16,22));TEST_INDEX=[6,7,14,15,22,23]
def pool_v2(split='train'):
 tt=tasks(range(6) if split=='train' else range(6,9));raw=[];unique={}
 for level in LAB:
  for j in TRAIN_INDEX if split=='train' else TEST_INDEX:
   for task in tt:
    t=dict(task);kind=t['task_id'][0];i=int(t['task_id'].split('_')[1]);a,b=i+2,i+4
    t['concept']={'q':'因式分解','l':'等式的性质','f':'分数的分母','g':'三角形的高'}[kind]
    t['brief']={'q':f'(x−{a})(x−{b})=0','l':f'{i%5+2}x={(i%5+2)*(i+3)}','f':f'(2+3)/{i+5}','g':f'{i+4}×{i+6}÷2'}[kind]
    text=GR[level][j].format(**t);key=B.safe_mask(F.normalize_prompt(text))
    row={'prompt_text':text,'final_level':level,'template_family':f'v2_{level}_{j}','task_id':t['task_id'],'split':split,
       'feature_key':key,'human_review':'pending','label_basis':'existing_rubric_engineering_candidate',
       'expression_style':['short','plain','long'][j//8],'length_bin':bin_length(text)}
    raw.append(row)
    if key in unique:assert unique[key]['final_level']==level
    else:unique[key]=row
 return raw,list(unique.values())
def bin_length(text):return 0 if len(text)<=10 else (1 if len(text)<=25 else 2)
def calibrated_v2(real,seed):
 _,candidate=pool_v2();rng=np.random.default_rng(seed);result=[];style={};classes={}
 class_counts=np.array([sum(r['final_level']==k for r in real) for k in LAB]);prob=(class_counts+.5)/(len(real)+1.5)
 for level,p in zip(LAB,prob):
  source=[r for r in real if r['final_level']==level];counts=np.array([sum(bin_length(r['prompt_text'])==b for r in source) for b in range(3)])
  weights=(counts+.5)/(len(source)+1.5);eligible=[r for r in candidate if r['final_level']==level]
  n=min(len(eligible),max(8,round(200*p)));w=np.array([weights[r['length_bin']]/sum(x['length_bin']==r['length_bin'] for x in eligible) for r in eligible]);w/=w.sum()
  result.extend(eligible[i].copy() for i in rng.choice(len(eligible),n,replace=False,p=w));style[level]=weights.tolist();classes[level]=n
 return result,{'calibration_ids':[r['sample_id'] for r in real],'class_proportions':prob.tolist(),'conditional_length_bins':style,'n_unique_prompts':len(result),
      'class_counts':classes,'actual_length_counts':dict(Counter(str(r['length_bin']) for r in result)),'human_review':'pending',
      'note':'Sampling weights are calibration references; uniqueness caps constrain achieved class/style proportions'}
