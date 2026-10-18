"""Expose and check G1 parameter/text contracts; structural checks, not human ratings."""
from pathlib import Path
import csv,json,re,hashlib
from collections import Counter
from datetime import datetime
OUT=Path(__file__).resolve().parents[1];ROOT=OUT.parent
OUT.joinpath('data').mkdir(exist_ok=True);OUT.joinpath('results').mkdir(exist_ok=True)
SRC=ROOT/'G0_G1严谨对照20261014/data/generated_outer_corpora.csv'
REAL=ROOT/'参数验证与生成器比较20261014/四维均值_真实R1_47条.csv'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,obj):(OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
def csvsave(name,rr):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        fields=list(dict.fromkeys(k for r in rr for k in r));w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rr:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def behavior_suggestion(text,level):
    if level=='low' and re.search(r'我会写|我会做|我已经会|我能自己完成',text):return 'autonomous_statement'
    if level=='low' and re.search(r'不要.*答案|我想自己|我自己.*写',text) and not re.search(r'我.{0,15}(?:先|列|算|判断|知道|写出)',text):return 'autonomy_declared_request'
    if level=='low':return 'local_process_help'
    if level=='medium':return 'method_or_concept_help'
    if level=='high':return 'answer_or_full_solution_request'
    return 'unknown'
before=sha(SRC);rows=list(csv.DictReader(SRC.open(encoding='utf-8-sig')));contracts=[];bad=[];counts=Counter()
for r in rows:
    if r['generator']!='G1_ALSP':continue
    a,l,s,p=json.loads(r['profile']);t=r['prompt_text'];lv=r['final_level']
    scope={'high':'answer_or_full_solution','medium':'method_or_concept','low':'local_feedback'}[lv]
    attempt={1:'no_attempt_displayed',3:'claimed_attempt_no_steps',4:'method_clue_and_stuck',5:'explicit_math_step'}[p]
    checks={}
    checks['help_scope_present']=bool(re.search(r'答案|结果|得数|完整.*解答|替我完成|整道题.*(?:步骤|计算)|从第一步到最后',t)) if lv=='high' else bool(re.search(r'方法|思路|原理|依据|道理|意思|怎么起步|先考虑|怎样运用|怎么用|理由|为什么',t)) if lv=='medium' else bool(re.search(r'核对|检查|依据|逻辑|提示|线索|反馈|理由|这一环|这一步是否合理|只帮我理解这一处',t))
    checks['learning_evidence_present']=bool(re.search(r'作业|任务|完成这题|完成任务|结果填|交上去',t)) if l==1 else bool(re.search(r'明白|理解|弄懂|学会|掌握|总结|规律|类似|举一反三|迁移|道理|我想知道',t))
    checks['attempt_evidence_present']=not bool(re.search(r'我先|我想到|我发现|我(?:已经|已)写|我试过|我想过|我考虑过|我试着|我自己想|我想了一',t)) if p==1 else bool(re.search(r'想过|想了|考虑过|试过思考|试着想',t)) if p==3 else bool(re.search(r'我想到|我发现',t)) if p==4 else bool(re.search(r'我先试了|我先把|我先写成|我先算',t))
    checks['information_layout_present']=t.startswith('这题。') if s==1 else t.startswith('关于') if s==2 else bool(re.search(r'解方程|计算2/|求底',t)) if not(lv=='low' and s==3) else True
    if s==5:checks['explicit_stuck_information']=bool(re.search(r'我不明白',t))
    failures=[k for k,v in checks.items() if not v]
    contract={'seed':r['seed'],'fold':r['fold'],'synthetic_row':r['synthetic_row'],'parent_id':r['parent_id'],'final_level':lv,
              'target_ALSP':json.loads(r['target_profile']),'implementation_prototype_ALSP':[a,l,s,p],
              'behavior_type':'answer_request' if lv=='high' and a==1 else 'full_solution_request' if lv=='high' else 'method_help' if lv=='medium' and a==3 else 'concept_or_reason_help' if lv=='medium' else 'method_clue_local_help' if p==4 else 'step_feedback',
              'help_scope':scope,'attempt_type':attempt,'prompt_text':t,'structural_checks':checks,
              'structural_status':'pass' if not failures else 'needs_check','semantic_human_review':'pending'}
    contracts.append(contract);counts.update(failures)
    if failures:bad.append(contract)
csvsave('data/现有G1参数文本契约.csv',contracts);save('results/契约失败记录.json',bad)
real=list(csv.DictReader(REAL.open(encoding='utf-8-sig')));types=[]
for r in real:
    types.append({'sample_id':r['sample_id'],'student_id':r['student_id'],'original_final_level':r['final_level'],
                  'original_prompt':r['prompt_text'],'suggested_behavior_type':behavior_suggestion(r['prompt_text'],r['final_level']),
                  'status':'machine_suggestion_not_new_human_annotation','ALSP_mean':{d:float(r[d+'_mean']) for d in ['A','L','S','P']}})
csvsave('data/真实行为类型建议_保留原标签.csv',types)
examples=[r for r in types if r['sample_id'] in ['S0013','S0049','S0071']]
save('data/必须保留的低类结构示例.json',examples)
result={'time':datetime.now().astimezone().isoformat(),'source_sha256':before,'source_unchanged':sha(SRC)==before,'checked_G1_ALSP_rows':len(contracts),'structural_failure_rows':len(bad),'failure_types':dict(counts),'original_label_changes':0,'new_human_annotations':0,'behavior_types_are_suggestions':True,'semantic_score_validity':'pending independent review','note':'Template-feature correspondence checks do not establish actual ALSP ratings; missing autonomous statements/declarations require a new renderer version, not relabeling.'}
save('results/参数文本对应核验.json',result)
with (OUT/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'stage':'parameter_text_contract_checked',**result},ensure_ascii=False)+'\n')
print(json.dumps(result,ensure_ascii=False))
