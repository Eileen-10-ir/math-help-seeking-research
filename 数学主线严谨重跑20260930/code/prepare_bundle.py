"""Copy only needed logic and anonymized research inputs into a reproducible local bundle."""
from common import *
import ast,shutil
def selected_functions(path,names):
    source=path.read_text(encoding='utf-8');tree=ast.parse(source);parts=[]
    for node in tree.body:
      if isinstance(node,ast.FunctionDef) and node.name in names:parts.append(ast.get_source_segment(source,node))
      if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in node.targets):parts.append(ast.get_source_segment(source,node))
    return '\n\n'.join(parts)
def run():
 real,eedi,llm,r3=load();write_json('data/anonymous_samples_snapshot.json',{'real_r1':real,'eedi_r1':eedi,'llm_r1':llm,'real_r3':r3})
 code=OUT/'code'
 (code/'legacy_features.py').write_text('import re,hashlib\nimport numpy as np\nfrom scipy import sparse\n\n'+selected_functions(ROOT/'7月数据/回填V3/v3_rebuild.py',
    {'normalize_prompt','unicodedata_normalize','mask_math_content','extract_intent_features','build_features','sha256_group','INTENT_NAMES','_INTENT_PATTERNS','LABELS'}),encoding='utf-8')
 (code/'bounded_mask.py').write_text('import re\n\n'+selected_functions(ROOT/'项目复核20260930/masking_diagnostic.py',{'safe_mask'}),encoding='utf-8')
 shutil.copyfile(ROOT/'项目复核20260930/math_state.py',code/'math_state.py')
 # Forms for independent review omit old human/model labels; A/B receive separate identical inputs.
 text=(ROOT/'项目复核20260930/sources/问卷.txt').read_text(encoding='utf-8').split('情境二：')[0]
 guides={}
 for k,end in [('A','如果你选择了B'),('B','如果你选择了C'),('C','第四步：')]:
    guides[k]=text.split(f'如果你选择了{k}，AI这样回复你：')[1].split(end)[0].strip()
 by={r['sample_id']:r for r in real}
 forms=[{'student_id':r['student_id'],'r3_id':r['sample_id'],'R1原文':by[r['pair_id']]['prompt_text'],
          '预设回复_问卷文档':guides[r['ai_type']],'R3原文':r['prompt_text'],
          '主要回应事件':'','展示新推理证据':'','是否仅复述提示内容':'','是否需更多上下文':'','判断依据':''} for r in r3]
 for who in ['A','B']:
    if not (OUT/f'data/R3独立证据复核_{who}.csv').exists():write_csv(f'data/R3独立证据复核_{who}.csv',forms)
 from controlled_text import pool
 _,grammar=pool()
 review=[{'template_family':r['template_family'],'task_id':r['task_id'],'prompt_text':r['prompt_text'],
           '候选工程标签':r['final_level'],'人工审核标签':'','歧义或语义问题':'','是否通过':''} for r in grammar]
 if not (OUT/'data/受控语法120条_人工审核.csv').exists():write_csv('data/受控语法120条_人工审核.csv',review)
 manifest=json.loads((OUT/'data/input_manifest.json').read_text(encoding='utf-8'))
 manifest['anonymous_snapshot_sha256']=sha(OUT/'data/anonymous_samples_snapshot.json')
 write_json('data/input_manifest.json',manifest)
 print('Prepared portable feature/state logic, anonymized input snapshot, two independent R3 forms and 120 unique grammar review rows.')
if __name__=='__main__':run()
