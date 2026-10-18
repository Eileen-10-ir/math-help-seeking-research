"""Source-hidden independent response forms, only for actual executed batches."""
from pathlib import Path
import argparse,json,csv,random,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'数学主线严谨重跑20260930/code'))
from evidence_runtime import TASKS
def main():
    p=argparse.ArgumentParser();p.add_argument('--records',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args()
    records=json.loads(a.records.read_text(encoding='utf-8'));assert records and all(r['mode']=='real_api' for r in records),'Never score dry-run placeholders as cloud responses.'
    a.output_dir.mkdir(parents=True,exist_ok=False);rows=[];keys=[]
    rng=random.Random(20261018);indices=list(range(len(records)));rng.shuffle(indices)
    for i,index in enumerate(indices):
        r=records[index];s=r['support'];rid=f'RESP{i+1:04d}'
        good=s['status'] in ['success','local_success']
        rows.append({'review_id':rid,'question':TASKS[r['task_id']]['question'],'student_text':r['text'],
            'actual_given_history':json.dumps(r['history'],ensure_ascii=False),'execution_status':'returned' if good else 'failed',
            'reply':s['text'] if good else '', 'reviewer':'','C_math_0_1_2_NA':'','T_target_0_1_2':'',
            'A_action_0_1_2':'','H_continuity_0_1_2_NA':'','E_final_answer_yes_no_NA_unknown':'',
            'R_unnecessary_block_yes_no_unknown':'','evidence_quote':'','reason':''})
        keys.append({'review_id':rid,'case_id':r['case_id'],'arm':r['arm'],'block':r['block'],'record_index':index})
    for reviewer in ['A','B']:
        copy=rows.copy();random.Random(20261018+(reviewer=='B')).shuffle(copy)
        with (a.output_dir/f'回复独立评分_{reviewer}.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(copy)
    (a.output_dir/'仅汇总者可开_评分后核对.json').write_text(json.dumps(keys,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'rows':len(rows),'two_independent_forms':True,'key_hidden_by_workflow_not_access_control':True},ensure_ascii=False))
if __name__=='__main__':main()
