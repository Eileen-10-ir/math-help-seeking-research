"""Stage-specific acceptance and evidence-aware release, no hidden risk resets."""
from pathlib import Path
from dataclasses import dataclass
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'数学主线严谨重跑20260930/code'))
from math_state import State as PreviousState
from runtime_state_v4 import advance as previous_advance

RULE_VERSION='math-evidence-state-v5-20261018'
@dataclass
class State(PreviousState):
    non_high_evidence_streak:int=0

def advance(state,text,scores,config,previous_support=None):
    stage='R1' if state.events==0 else 'R3'
    local=dict(config,cutoff=config.get('stage_cutoffs',{}).get(stage,config['cutoff']))
    analysis=previous_advance(state,text,scores,local,previous_support)
    original=analysis['decision_level'];released=False
    if analysis['risk_updated']:
        level=analysis['current_behavior_level']
        state.non_high_evidence_streak=0 if level=='high' else state.non_high_evidence_streak+1
        explicit=analysis['decision_basis']=='behavior_rule' and level!='high'
        if config.get('history_policy')=='evidence_release' and analysis['history_high_protection']:
            released=explicit or state.non_high_evidence_streak>=2
            if released:
                analysis['decision_level']=level;analysis['history_high_protection']=False
    analysis.update(rule_version=RULE_VERSION,stage_for_gate=stage,
        history_policy=config.get('history_policy','strong'),history_release_applied=released,
        decision_before_history_revision=original,non_high_evidence_streak=state.non_high_evidence_streak)
    # Risk is kept as produced by EWMA; a route release must not fake an improving score.
    return analysis
