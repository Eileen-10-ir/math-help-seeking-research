"""Versioned evidence gate shared by live service and supplementary evaluations."""
from math_state import State,update,profile,event_type
import math,copy,re

RULE_VERSION='math-evidence-v3.1-20260930'
DEFAULT_CUTOFF=.6
LABELS=['high','medium','low'];ACK='接受引导/非提问'
def observe_event(text):
 kind=event_type(text,True)
 if kind=='question' and re.fullmatch(r'[\sxXyY0-9＋+\-－−()（）＝=×✕*,，、和或²^./]+',text):return 'answer_only'
 return kind
def assess(text,scores,cutoff=DEFAULT_CUTOFF,events=True,confidence=True):
 if not 0<=cutoff<=1:raise ValueError('Invalid cutoff')
 if not scores or any(not math.isfinite(float(v)) or v<0 for v in scores.values()) or not math.isclose(sum(scores.values()),1,abs_tol=1e-5):
  raise ValueError('Invalid model scores')
 if set(scores) not in [set(LABELS),set(LABELS+[ACK])]:raise ValueError('Unexpected model classes')
 kind=observe_event(text);candidate=max(scores,key=scores.get);score=float(scores[candidate]);reasons=[]
 if events and kind!='question':reasons.append({'ack':'确认回应未提供新求助证据','answer_only':'仅答案或算式，需解释推理过程','ambiguous':'文本信息不足'}[kind])
 if candidate==ACK:reasons.append('模型倾向接受/非提问，不能当作低依赖')
 if confidence and score<cutoff:reasons.append(f'最大模型分数{score:.3f}低于固定工程阈值{cutoff:.2f}')
 return {'eligible':not reasons,'observed_event':kind,'candidate_level':candidate,'max_model_score':score,'hold_reasons':reasons,
         'rule_version':RULE_VERSION,'cutoff':cutoff}

def behavioral_evidence(text):
 """Limited rubric rules. They describe displayed text, not true motivation."""
 neg=r'(?:不要|不用|别|不需要|不想要|不求).{0,5}(?:答案|结果|解答|过程|步骤|直接给)'
 negatives=list(re.finditer(neg,text))
 demand_pattern=r'(?:直接|只要|只需|只给|只想要).{0,6}(?:答案|结果|得数|解答)|(?:给我|给出|告诉我|发给我|提供).{0,4}(?:最终答案|详细答案|完整答案|答案)|(?:最终答案|这题答案|结果).{0,3}(?:告诉我|给我|发给我)|(?:代写|代做|替我做完|不想(?:自己)?(?:思考|算|做))|(?:我的|这题的?).{0,2}答案是什么'
 demands=[]
 for m in re.finditer(demand_pattern,text):
  prefix=text[max(0,m.start()-6):m.start()]
  if not re.search(r'不要|不用|别|不需要|不想要|不求',prefix):demands.append(m.group())
 if demands and negatives:return {'conflict':True,'matches':demands+[m.group() for m in negatives],'reason':'同时出现索答与拒绝索答，需澄清实际诉求'}
 if demands:return {'level':'high','matches':demands,'reason':'明确未被否定的索答或代做诉求'}
 if re.search(r'什么是|是什么意思|的定义|的概念',text) and re.search(r'整数|平方|因式分解|分母|等式|三角形',text):
  return {'level':'low','matches':[text],'reason':'纯数学概念咨询，按现行规范作低类候选'}
 work=re.search(r'我(?:先|已经|已|写|列|算|试|的思路).{0,45}[=＝×÷]|我.{0,20}写.{0,20}[=＝×÷]',text)
 help_match=re.search(r'检查|核对|依据|理由|原理|提示|这一步|这一环',text)
 full=re.search(r'(?:完整|全部)(?:答案|解答|过程|步骤)',text)
 if work and help_match and (not full or negatives):
  return {'level':'low','matches':[work.group(),help_match.group()],'reason':'展示具体式子并请求针对步骤的帮助；不判断式子来源或学生能力'}
 return None

def advance(state,text,scores,mu=.5,cutoff=DEFAULT_CUTOFF,previous_support=None,behavior_rules=True):
 gate=assess(text,scores,cutoff);before=state.risk
 cue=behavioral_evidence(text) if behavior_rules and gate['observed_event']=='question' else None
 if cue and cue.get('conflict'):
  gate['eligible']=False;gate['hold_reasons'].append(cue['reason'])
 elif cue:
  gate['eligible']=True;gate['hold_reasons']=[]
 if previous_support and re.sub(r'\s','',text)==re.sub(r'\s','',previous_support):
  gate['eligible']=False;gate['hold_reasons'].append('逐字复述上一条系统反馈，尚无新增推理证据')
 if gate['eligible']:
  total=sum(scores[k] for k in LABELS)
  p={k:float(k==cue['level']) for k in LABELS} if cue else {k:float(scores[k]/total) for k in LABELS}
  result=update(state,text,p,followup=True,mu=mu)
 else:
  # Preserve an actual non-question event; uncertain questions count as insufficient evidence.
  proxy=text if gate['observed_event']!='question' else ''
  if gate['observed_event']=='answer_only' and event_type(proxy,True)=='question':proxy='2、3'
  result=update(state,proxy,None,followup=True,mu=mu)
  result['reason']='；'.join(gate['hold_reasons'])+'；保留历史状态并核实'
  assert state.risk==before
 result.update(gate);result['model_scores']={k:float(v) for k,v in scores.items()}
 result['decision_basis']='behavior_rule' if gate['eligible'] and cue else ('model_score' if gate['eligible'] else 'insufficient_evidence')
 result['decision_basis_note']=cue['reason'] if cue else ('模型分数与累计状态' if gate['eligible'] else '；'.join(gate['hold_reasons']))
 result['behavior_evidence']=cue
 result['current_behavior_level']=(cue['level'] if cue else gate['candidate_level']) if gate['eligible'] else None
 result['review_required']=bool(cue and (cue.get('conflict') or cue.get('level')!=gate['candidate_level']))
 if 'probabilities' in result:result['state_update_weights']=result.pop('probabilities')
 if cue and 'confidence_score' in result:result.pop('confidence_score')
 result['previous_risk']=before;result['risk_change']=None if before is None or state.risk is None else state.risk-before
 result['profile']=profile(state);result['score_status']='模型分数未校准；规则更新权重不是模型概率；状态锚点和阈值是工程先验'
 return result

TASKS={
 'quadratic':{'title':'二次方程','question':'解方程 x²−5x+6=0','hint':'尝试写成(x+a)(x+b)。展开后，a+b应为−5，ab应为6。先列出6的因数对，再检查和。',
   'solution':'x²−5x+6=(x−2)(x−3)。零乘积定理给出x=2或x=3；把两个值代回原式检查均为0。',
   'extension':'试着解释为什么不能从(x−2)(x−3)=0推得x同时等于2和3。'},
 'linear':{'title':'一次方程','question':'解方程 3x+4=19','hint':'先用等式性质让含x的项单独留在一边：两边同时减4。',
   'solution':'两边同时减4得到3x=15；再同时除以3得到x=5。代回3×5+4=19。','extension':'如果把等式右边改为22，哪一步会发生变化？'},
 'fraction':{'title':'同分母分数','question':'计算 2/7+3/7','hint':'两个分数的单位都是七分之一，可以合并这些相同的单位。请说明分母为什么保持不变。',
   'solution':'2/7+3/7=(2+3)/7=5/7。分母表示每份的大小，合并的是这样的份数。','extension':'如果分母不同，为什么不能直接相加分子？'},
 'triangle':{'title':'三角形面积','question':'求底6厘米、高4厘米的三角形面积','hint':'想象两个全等三角形拼成平行四边形。平行四边形面积是底乘高，一个三角形占多少？',
   'solution':'面积=底×高÷2=6×4÷2=12平方厘米。这里的高必须对应这条底并与底垂直。','extension':'底不变、高加倍，面积会怎样变化？'},
 'free':{'title':'自由数学情境','question':'输入数学题目、已有尝试和想问的内容','hint':'请把题目条件、你已经做的步骤和卡住的位置写清楚，我们从那一步开始。',
   'solution':'请给出具体题目与已有步骤。这一原型对自由题目提供求助分析和核实，尚未接入通用数学解答生成。','extension':'你最希望理解的是哪个概念或哪一步的依据？'}}

def mathematical_evidence(text,task_id):
 """Finite checks for declared tasks. Never eval/sympify arbitrary user strings."""
 t=text.replace('－','-').replace('−','-').replace('＋','+').replace('（','(').replace('）',')')
 if task_id=='quadratic':
  m=re.search(r'\(\s*x\s*([+-]\s*\d+)\s*\)\s*(?:[×✕*]\s*)?\(\s*x\s*([+-]\s*\d+)\s*\)',t,re.I)
  if m:
   a,b=[int(x.replace(' ','')) for x in m.groups()];correct=a+b==-5 and a*b==6
   return {'kind':'factorization','correct':correct,'observed_span':m.group(0),
       'message':f'你写出的因式展开为x²{a+b:+d}x{a*b:+d}，'+('与所选方程一致。请说明这两个一次式的系数怎样确定。' if correct else '与所选方程的系数不一致。先核对和与积的符号。')}
  if observe_event(text)=='answer_only':
   numbers=[int(x) for x in re.findall(r'[+-]?\d+',t)]
   if len(numbers)==2:
    substitutions=[n*n-5*n+6 for n in numbers]
    return {'kind':'numeric_answer','correct':set(numbers)=={2,3},'observed_span':text,
        'message':'两个数代入原式后的值分别为'+str(substitutions)+'。数值检查与自主推理证据分开；请写出得到这两个数的理由。'}
 if task_id=='linear' and re.search(r'3\s*x\s*=\s*15',t,re.I):
  return {'kind':'equation_step','correct':True,'observed_span':'3x=15','message':'这一步与两边同时减4一致。请说明下一步对等式两边怎样操作。'}
 if task_id=='fraction' and re.search(r'(?:2\s*\+\s*3|5)\s*[/÷]\s*7',t):
  return {'kind':'fraction_step','correct':True,'observed_span':'同分母合并式','message':'你提供了同分母合并的式子。请解释保持分母的理由。'}
 if task_id=='triangle' and re.search(r'6\s*[×*]\s*4\s*[/÷]\s*2',t):
  return {'kind':'area_step','correct':True,'observed_span':'6×4÷2','message':'面积公式与所选底、高相符。结果应使用平方厘米，请解释除以2的依据。'}
 return None

def support(text,task_id,result):
 task=TASKS[task_id];check=mathematical_evidence(text,task_id)
 concept=None
 if re.search(r'什么意思|是什么|什么是|定义',text):
  definitions={'整数':'整数包括正整数、0和负整数，例如−2、0、3；1/2不是整数。',
    '平方':'一个数的平方是它与自身相乘，例如3²=3×3=9；它不同于3×2。',
    '因式分解':'因式分解把一个多项式写成几个因式的乘积，它与展开是相反的过程，例如x²−1=(x−1)(x+1)。'}
  concept=next((v for k,v in definitions.items() if k in text),None)
 if concept:reply=concept+'你可以举一个例子说明自己的理解。';tier='概念说明'
 elif check:reply=check['message'];tier='数学步骤反馈'
 elif not result['eligible']:reply='请说明这句话对应的题目或步骤，并写出你已经想过的一步；我会依据新信息继续分析。';tier='证据核实'
 elif result['decision_level']=='high':reply='我们先完成一个小步骤。'+task['hint'];tier='基础引导'
 elif result['decision_level']=='medium':reply=task['hint']+'把你的尝试写出来，我再针对那一步反馈。';tier='方法提示'
 else:reply=task['solution']+' '+task['extension'];tier='充分解释'
 return {'text':reply,'tier':tier,'provider':'local_task_templates','mathematical_check':check,
         'route_requested':result.get('route'),'route_executed':'local','cloud_calls':0,
         'scope':'反馈针对所选题目；数学检查不是依赖等级裁定，也不证明教学效果'}
