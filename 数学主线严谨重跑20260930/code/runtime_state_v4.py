"""v4 high-signal EWMA; old v3 module and E10 remain immutable."""
from math_state import State
from evidence_runtime import assess,behavioral_evidence,LABELS
import re
RULE_VERSION='math-cloudedge-v4-20260930'

def advance(state,text,scores,config,previous_support=None):
 gate=assess(text,scores,config['cutoff']);cue=behavioral_evidence(text) if gate['observed_event']=='question' else None
 if cue:gate['eligible']=not cue.get('conflict',False)
 if cue and cue.get('conflict'):gate['hold_reasons'].append(cue['reason'])
 elif cue:gate['hold_reasons']=[]
 if previous_support and re.sub(r'\s','',text)==re.sub(r'\s','',previous_support):
  gate['eligible']=False;gate['hold_reasons'].append('逐字复述前一条支持，尚无新增证据')
 previous=state.risk;state.events+=1;level=None;x=None;protection=False
 if gate['eligible']:
  level=cue['level'] if cue else gate['candidate_level'];x=float(level=='high') if cue else float(scores['high'])
  state.risk=x if previous is None else config['lambda']*x+(1-config['lambda'])*previous
  state.evidence_turns+=1;state.risks.append(state.risk);state.last_evidence_level=level;state.high_predictions+=int(level=='high')
  state.explicit_attempts+=int(any(k in text for k in ['我试','我列','我算','我的思路','我找到','我回忆']))
  protection=level!='high' and state.risk>=config['history_high_threshold']
  decision='high' if level=='high' or protection else level
 else:
  kind=gate['observed_event'];field={'ack':'acknowledgements','answer_only':'answer_only','ambiguous':'ambiguous','question':'ambiguous'}[kind]
  setattr(state,field,getattr(state,field)+1);decision=None
 profile={'description':'本次数学求助的高类信号累计，不是心理依赖百分比','trajectory':'证据不足' if state.evidence_turns<3 else ('高类信号减弱' if state.risks[-1]<state.risks[0]-.05 else ('高类信号增强' if state.risks[-1]>state.risks[0]+.05 else '基本平稳'))}
 basis='behavior_rule' if cue and gate['eligible'] else ('model_score' if gate['eligible'] else 'insufficient_evidence')
 note=cue['reason'] if cue else ('模型文本判断' if gate['eligible'] else '；'.join(gate['hold_reasons']))
 return {**gate,'rule_version':RULE_VERSION,'model_scores':dict(scores),'candidate_level':gate['candidate_level'],'current_behavior_level':level,
  'decision_level':decision,'history_high_protection':protection,'decision_basis':basis,'decision_basis_note':note,
  'review_required':bool(cue and (cue.get('conflict') or cue.get('level')!=gate['candidate_level'])),'behavior_evidence':cue,
  'single_risk':x,'single_risk_source':'rule_binary_proxy' if cue and gate['eligible'] else ('raw_model_p_high' if gate['eligible'] else None),
  'risk':state.risk,'previous_risk':previous,'risk_change':None if previous is None or state.risk is None else state.risk-previous,
  'risk_updated':gate['eligible'],'lambda':config['lambda'],'history_high_threshold':config['history_high_threshold'],'profile':profile,
  'score_status':'p_high未经独立概率校准；规则1/0是行为编码；EWMA系数为工程选型，非心理参数'}
