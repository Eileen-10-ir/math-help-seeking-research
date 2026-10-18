from common import *
import joblib,copy
from math_state import State,update,profile,event_type,TEMPLATES
TEMPLATES['low']='我们可以针对你的具体问题深入解释。你可以贴出已有步骤，或说明想弄懂的概念，再一起做一道变式题。'
def run():
 real,eedi,llm,r3=load();parents={r['sample_id']:r for r in real}
 rows=list(csv.DictReader((OUT/'results/recognition_predictions.csv').open(encoding='utf-8-sig')))
 def scores(experiment,variant,sid,labels):
    rr=[r for r in rows if r['experiment']==experiment and r['variant']==variant and r['sample_id']==sid]
    assert len(rr)==5
    return {k:float(np.mean([float(r['p_'+k]) for r in rr])) for k in labels}
 profiles=[];review=[]
 guide_rows=list(csv.DictReader((OUT/'data/R3独立证据复核_A.csv').open(encoding='utf-8-sig')))
 guides={r['r3_id']:r['预设回复_问卷文档'] for r in guide_rows}
 for r in r3:
    p=parents[r['pair_id']];state=State();a=update(state,p['prompt_text'],scores('E2_student_crossfit','parameter_real',p['sample_id'],LAB));a['text']=p['prompt_text']
    prob=scores('E3_r3_crossfit','r3_only',r['sample_id'],LAB+[ACK]);kind=event_type(r['prompt_text'],True)
    # Historical four-way model is weak on rare high; insufficient model evidence never forces a lower state.
    if kind=='question' and (max(prob.values())<.6 or max(prob,key=prob.get)==ACK):
      b=update(state,'',None,True);b['reason']='R3模型证据不足或倾向非提问，保留历史状态并核实';b['probabilities']=prob
    else:
      p3={k:prob[k]/sum(prob[v] for v in LAB) for k in LAB}
      b=update(state,r['prompt_text'],p3,True);b['probabilities']=prob
    b['text']=r['prompt_text'];b['observed_text_event']=kind
    clues={name:sum(int(F.extract_intent_features(t)[j]) for t in [p['prompt_text'],r['prompt_text']]) for name,j in [('直接索答线索',0),('方法求助线索',2),('尝试线索',6),('具体卡点线索',8)]}
    profiles.append({'id':r['student_id'],'steps':[a,b],'profile':profile(state),'clues':clues,
       'human':[p['final_level'],r['final_level']],'historical_guide':guides.get(r['sample_id'],''),'source':'原始情境问卷中的两条学生表达；R1/R3模型分数为5次学生折外均值；历史回复 '+r['ai_type']+'；状态值与建议由程序计算，并非学生心理测量'})
    review.append({'student_id':r['student_id'],'r1_id':p['sample_id'],'r3_id':r['sample_id'],'human_r1':p['final_level'],'human_r3':r['final_level'],
         'r1_prediction':max(a['probabilities'],key=a['probabilities'].get),'r3_prediction':max(prob,key=prob.get),
         'r3_high_score':prob['high'],'r3_confidence_score':max(prob.values()),'r3_state_updated':b['risk_updated'],
         'r1_text':p['prompt_text'],'r3_text':r['prompt_text'],'人工误差审查':''})
 write_csv('results/真实47_折外画像与误差审查.csv',review)
 # Separate illustrative sequence source: retained historical engineering inputs, never used as validation truth.
 sequence_path=OUT/'data/受控八轮展示输入.csv'
 if not sequence_path.exists():sequence_path=ROOT/'项目复核20260930/parameter_math/数学参数化候选_300人8轮.csv'
 seqrows=list(csv.DictReader(sequence_path.open(encoding='utf-8-sig')))
 write_csv('data/受控八轮展示输入.csv',[{k:r[k] for k in ['sample_id','user_id','turn_id','prompt_text']} for r in seqrows])
 bundle=joblib.load(OUT/'data/math_demo_candidate.joblib');classifier=Classifier();classifier.vec=bundle['vectorizer'];classifier.clf=bundle['classifier']
 pp=classifier.probs([r['prompt_text'] for r in seqrows]);by={}
 for r,p in zip(seqrows,pp):by.setdefault(r['user_id'],[]).append((r,p))
 sims=[]
 for uid,rr in by.items():
    state=State();steps=[]
    for r,p in rr:
      d=update(state,r['prompt_text'],dict(zip(LAB,p)),followup=int(r['turn_id'])>1);d['text']=r['prompt_text'];steps.append(d)
    clues={name:sum(int(F.extract_intent_features(r['prompt_text'])[j]) for r,p in rr) for name,j in [('直接索答线索',0),('方法求助线索',2),('尝试线索',6),('具体卡点线索',8)]}
    sims.append({'id':uid,'steps':steps,'profile':profile(state),'clues':clues,'source':'受控八轮演示输入；全量拟合演示候选逐条文本识别，生成标签未输入模型；不是新测试成绩或动作效果模拟'})
 data={'real':profiles,'synthetic':sims};write_json('data/validated_replay_profiles.json',data)
 template_path=OUT/'data/dashboard_template.html'
 old=(template_path if template_path.exists() else ROOT/'项目复核20260930/数学单科中期画像展示.html').read_text(encoding='utf-8')
 start=old.index('const data=');end=old.index('\nconst $=',start)
 old=old[:start]+'const data='+json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';'+old[end:]
 old=old.replace('② 三类识别信号','② 识别分数')
 old=old.replace('数学单学科 · 中期行为画像','数学单学科 · 重跑后的行为画像').replace('数学单学科 · AI求助行为画像','数学单学科 · 重跑后的行为画像')
 old=old.replace("low:'低依赖'}","low:'低依赖','接受引导/非提问':'接受/非提问'}")
 old=old.replace('识别重建版开发Macro-F1 <b>0.537</b>；高依赖召回 <b>7/12</b>。真实47与16条训练改写有来源关系，属于开发诊断。',
   '参数＋真实训练的学生折外Macro-F1均值 <b>0.655</b>；高依赖召回均值 <b>0.633</b>。每次仍为47名学生，验证父样本及其改写均排除；这是回顾性开发验证。')
 old=old.replace('240配置压力测试已揭示平滑与突变响应的取舍。新版参数文本语言覆盖不足，先扩独立表达并抽审，再升级训练主体。',
   '真实训练基线F1均值0.609；参数补充增量的条件带跨过零。R3仅当前文本约0.611，拼接历史约0.398。低置信度或非提问信号保留状态并核实。')
 old=old.replace("(i===1?'本轮为规则占位分数，非概率校准结果。':'分类器分数未独立校准。')", "(i===1?'R3为历史四类学生折外分数；弱证据保留历史，未做概率校准。':'R1为学生折外分数均值，未做概率校准。')")
 old=old.replace('已串联数学单科离线行为画像原型，完成数据来源与标注核查、识别消融修复、短回应敏感性分析及状态规则工程对照。下一步完善参数化语言覆盖、上下文识别与数学全线统一评估，形成方法与系统初稿。',
   '已完成来源与家族隔离重跑、固定组件消融、学生层面配对不确定性、上下文负结果及嵌套补充、状态压力与动作响应情景比较。报告中保留假设、失败结果及人工复核待办；画像仅描述任务内证据。')
 old=old.replace('累计风险代理轨迹','系统状态回放（工程计算）').replace('末次风险代理 · μ=0.5','末次系统状态值 · μ=0.5').replace('<h3>识别与证据</h3>','<h3>识别分数与证据（非心理依赖百分比）</h3>')
 old=old.replace("${(v*100).toFixed(1)}%","${v.toFixed(3)}")
 old=old.replace('<h3>词句线索计数</h3>','<h3>词句线索计数（整段原文）</h3>')
 old=old.replace("$('utterance').textContent=s.text;", "$('utterance').textContent=s.text;const guide=$('historical-guide');if(guide){guide.parentElement.style.display=real&&i===1?'block':'none';guide.textContent=d.historical_guide||'暂无可追溯引导文本';}")
 realpage=old.replace('const data='+json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';',
     'const data='+json.dumps({'real':profiles,'synthetic':[]},ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';')
 realpage=realpage.replace('<option value="synthetic">参数化300人 · 八轮演示</option>','')
 realpage=realpage.replace('数学单学科 · 重跑后的行为画像','真实学生数学求助画像（情境问卷）')
 realpage=realpage.replace('现有真实数据标定 · 受控文本与动态状态','真实学生原文 · 标注与模型判断分别呈现')
 realpage=realpage.replace('受控多轮演示</div><div class="big">300 × 8</div><div class="small">候选文本 · 非新增学生','实际问卷记录</div><div class="big">47 × 2</div><div class="small">两条情境表达 · 无真实八轮记录')
 realpage=realpage.replace('中期展示原型：输入识别 → 状态更新 → 任务画像 → 分级支持 → 后续更新','原始问卷表达 → 行为线索与等级判断 → 系统状态回放 → 支持建议；建议未实际发送，R3不是该建议实施后的反馈')
 realpage=realpage.replace('<h3>识别分数与证据（非心理依赖百分比）</h3>','<section><h3>R3前的预设引导（来自问卷文档）</h3><div id="historical-guide" class="text"></div><div class="small">在线问卷与文档话术的一致性仍需成员核查。</div></section><h3>识别分数与证据（非心理依赖百分比）</h3>')
 realpage=realpage.replace('本页未执行云端服务。模拟下一条文本由候选生成器预先产生，不由本页建议改变；八轮走势是条件输入下的系统状态回放。',
     '本页只展示真实学生填写的两条情境表达。等级与词句线索是任务内判断；系统状态及支持建议是程序推断，不是实测心理依赖或教学效果。<a href="八轮工程模拟_非真实学生.html">另看八轮工程模拟（非真实学生画像）</a>。')
 (OUT/'数学重跑结果与画像.html').write_text(realpage,encoding='utf-8')
 simulation=old.replace('<option value="real">真实47人 · 两点回放</option>','').replace('参数化300人 · 八轮演示','300组生成序列 · 八轮工程检查')
 simulation=simulation.replace('数学单学科 · 重跑后的行为画像','八轮工程模拟（非真实学生）').replace('现有真实数据标定 · 受控文本与动态状态','工程检查材料 · 全部八轮文本由生成器预先产生')
 simulation=simulation.replace('中期展示原型：输入识别 → 状态更新 → 任务画像 → 分级支持 → 后续更新','用于检查程序面对连续输入时怎样更新。后续文本不受教学建议影响；不能用来呈现真实学生成长或依赖下降。')
 simulation=simulation.replace('当前任务画像','工程序列状态').replace("d.id+' · 任务内画像'","d.id+' · 工程序列状态'").replace('打印当前画像','打印工程回放')
 simulation=simulation.replace('真实数据总览','标定背景：真实问卷类别分布')
 (OUT/'八轮工程模拟_非真实学生.html').write_text(simulation,encoding='utf-8')
 print('Created updated 47 cross-fitted real profiles and 300 x 8 text-driven illustration; no human labels enter inference.')
if __name__=='__main__':run()
