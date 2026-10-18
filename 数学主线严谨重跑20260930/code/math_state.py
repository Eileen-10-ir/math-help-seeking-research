"""Evidence-aware mathematics state engine. Scores and thresholds are engineering priors.

An acknowledgement or answer-only utterance is an event, not a measured dependency level.
The engine never reads adjudicated labels at inference time.
"""
from dataclasses import dataclass, field, asdict
import math, re

ANCHORS={'high':.78,'medium':.52,'low':.28}
LABELS=list(ANCHORS)
TEMPLATES={
    'high':'我可以陪你解这道题。先选一个你能开始的步骤，或者告诉我哪一个概念还不熟悉，我们从那里开始。',
    'medium':'你现在需要的是方法、某一步的解释，还是检查已有思路？把卡住的一步告诉我，我给你一个小提示。',
    'low':'我看到了你的尝试。请说明这一步的理由，我会针对你的卡点反馈，再一起试一道变式题。',
    'verify':'收到。你愿意写出下一步或说明刚才一步的理由吗？这样我才能判断你需要哪种帮助。',
}
@dataclass
class State:
    risk:float|None=None
    evidence_turns:int=0
    events:int=0
    acknowledgements:int=0
    answer_only:int=0
    ambiguous:int=0
    high_predictions:int=0
    explicit_attempts:int=0
    risks:list=field(default_factory=list)
    last_evidence_level:str|None=None

def event_type(text,followup=False):
    t=(text or '').strip()
    if not t:return 'ambiguous'
    if not followup:return 'question'
    plain=re.sub(r'[\s,，。.!！?？、]','',t)
    if re.fullmatch(r'(好|好的|可以|可以可以|很好|谢谢|谢谢你|哦哦我会了谢谢你|嗯+|哦+|ok|OK|我会了|明白了|我明白了|知道了|我知道了)',plain):return 'ack'
    if re.fullmatch(r'[\sxXyY0-9＋+\-－−()（）＝=×✕*,，、和²^./]+',t) and not re.search(r'[?？]',t):return 'answer_only'
    if t in ['说完之后','没想到','？','?','第一步','第二步','不会','不会做','不会解','我先试试','我试试']:
        return 'ambiguous'
    return 'question'

def r3_probabilities(text):
    """Transparent placeholder, not a validated R3 model; reserved for the replay prototype."""
    t=text or ''
    reject=any(k in t for k in ['不要答案','不用给答案','只要提示','别直接给'])
    demand=not reject and any(k in t for k in ['直接给','给我答案','给答案','给出答案','答案是什么','速速','帮我解','帮我完成'])
    attempt=any(k in t for k in ['我列出','我尝试','我找到','我回忆','我的思路','我试着','我试了','我试过'])
    lv='high' if demand else ('low' if attempt and len(t)>=15 else 'medium')
    return {k:float(k==lv) for k in LABELS}

def update(state,text,probabilities=None,followup=False,mu=.5,confidence_cut=.6):
    if not 0<mu<=1:raise ValueError('mu must lie in (0, 1]')
    kind=event_type(text,followup)
    if kind!='question':
        state.events+=1
        fieldname={'ack':'acknowledgements','answer_only':'answer_only','ambiguous':'ambiguous'}[kind]
        setattr(state,fieldname,getattr(state,fieldname)+1)
        return {'event':kind,'risk':state.risk,'risk_updated':False,'route':'edge_verify',
                'decision_level':None,'reply':TEMPLATES['verify'],'reason':'尚无可判定的依赖行为证据，保留历史状态并邀请展示思路'}
    if probabilities is None:raise ValueError('Question requires explicit class scores')
    if set(probabilities)!=set(LABELS):raise ValueError('Need all three class scores')
    if any(not math.isfinite(p) or p<0 for p in probabilities.values()) or abs(sum(probabilities.values())-1)>1e-4:
        raise ValueError('Invalid class scores')
    state.events+=1
    level=max(LABELS,key=lambda k:probabilities[k]);confidence=probabilities[level]
    single=sum(probabilities[k]*ANCHORS[k] for k in LABELS)
    # Initial mu/evidence anchors fixed before replay, never optimized using human R3 outcomes.
    state.risk=single if state.risk is None else mu*single+(1-mu)*state.risk
    state.evidence_turns+=1;state.risks.append(state.risk);state.last_evidence_level=level
    state.high_predictions+=int(level=='high')
    state.explicit_attempts+=int(any(k in text for k in ['我试','我列','我算','我的思路','我找到','我回忆']))
    # Formula (12) structure: current evidence can trigger high immediately;
    # high history matters only together with current moderate signal.
    if single>=.65 or level=='high' or (state.risk>=.65 and single>=.52):decision='high'
    elif single>=.4 or state.risk>=.4:decision='medium'
    else:decision='low'
    if confidence<confidence_cut:
        route='hybrid_review';reply=TEMPLATES['medium'];reason='低置信度，需补充上下文或进一步识别'
    else:
        route={'high':'edge','medium':'cloud_requested','low':'cloud_optional'}[decision]
        reply=TEMPLATES[decision];reason='结合当前证据和累计状态选择教学支持'
    return {'event':kind,'probabilities':probabilities,'confidence_score':confidence,
            'single_risk':single,'risk':state.risk,'risk_updated':True,'prediction_level':level,
            'decision_level':decision,'route':route,'reply':reply,'reason':reason}

def profile(state):
    d=asdict(state)
    d['description']='本次数学任务中的求助行为记录；不代表学生能力或稳定人格'
    d['trajectory']='证据不足' if state.evidence_turns<3 else ('风险下降' if state.risks[-1]<state.risks[0]-.05 else ('风险上升' if state.risks[-1]>state.risks[0]+.05 else '基本平稳'))
    d['score_status']='分类器分数或规则代理，未经独立概率校准'
    return d
