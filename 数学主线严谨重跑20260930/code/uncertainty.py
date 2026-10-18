from common import *
from scipy.stats import fisher_exact,binomtest
def bootstrap_prediction_metrics(rows,labels,seed=20260930):
    seeds=sorted({int(r['seed']) for r in rows});ids=sorted({r['sample_id'] for r in rows})
    by={(int(r['seed']),r['sample_id']):r for r in rows};truth=np.array([labels.index(by[seeds[0],i]['truth']) for i in ids])
    pred=np.array([[labels.index(by[s,i]['prediction']) for i in ids] for s in seeds])
    rng=np.random.default_rng(seed)
    # Stratified by actual class, preserving n/classes; all repeat predictions for a sampled student stay together.
    ix=np.concatenate([rng.choice(np.where(truth==c)[0],size=(5000,(truth==c).sum()),replace=True) for c in range(len(labels))],axis=1)
    yy=truth[ix];pp=pred[:,ix];macro=np.zeros(pp.shape[:2])
    for c in range(len(labels)):
      tp=((pp==c)&(yy==c)).sum(axis=2);den=(pp==c).sum(axis=2)+(yy==c).sum(axis=1)
      macro+=np.divide(2*tp,den,out=np.zeros_like(tp,dtype=float),where=den!=0)/len(labels)
    values=macro.mean(axis=0)
    hi=labels.index('high');recall=(((pp==hi)&(yy==hi)).sum(axis=2)/(yy==hi).sum(axis=1)).mean(axis=0)
    return values,{'macro_f1_conditional95':np.quantile(values,[.025,.975]).tolist(),
                   'high_recall_conditional95':np.quantile(recall,[.025,.975]).tolist(),'n_students':len(ids),'repeats':len(seeds)}
def run():
    rows=list(csv.DictReader((OUT/'results/recognition_predictions.csv').open(encoding='utf-8-sig')))
    result={};draws={}
    for experiment,labels in [('E2_student_crossfit',LAB),('E3_r3_crossfit',LAB+[ACK])]:
      for variant in sorted({r['variant'] for r in rows if r['experiment']==experiment}):
        subset=[r for r in rows if r['experiment']==experiment and r['variant']==variant]
        d,summary=bootstrap_prediction_metrics(subset,labels);result[experiment+'/'+variant]=summary;draws[experiment,variant]=d
    contrasts={}
    for e,a,b in [('E2_student_crossfit','parameter_real','real_only'),('E2_student_crossfit','parameter_eedi_real_llm','eedi_real_llm'),
                  ('E3_r3_crossfit','context','r3_only'),('E3_r3_crossfit','context_guide','r3_only')]:
      d=draws[e,a]-draws[e,b]
      summary_file='E2_summary.json' if e=='E2_student_crossfit' else 'E3_summary.json'
      summary=json.loads((OUT/'results'/summary_file).read_text(encoding='utf-8'))
      contrasts[f'{e}: {a} minus {b}']={'observed_mean_difference':summary[a]['macro_f1']['mean']-summary[b]['macro_f1']['mean'],
          'bootstrap_mean_difference':float(d.mean()),'conditional95':np.quantile(d,[.025,.975]).tolist()}
    write_json('results/prediction_uncertainty.json',{'method':'5000 paired class-stratified student resamples, retaining all repeats; fixed predictions',
      'limitation':'Conditional resampling bands; not full model-training/CV uncertainty or independent population validation','models':result,'contrasts':contrasts})
    supplementary=OUT/'results/E3b_predictions.csv'
    if supplementary.exists():
      rr=list(csv.DictReader(supplementary.open(encoding='utf-8-sig')))
      d,summary=bootstrap_prediction_metrics(rr,LAB+[ACK]);delta=d-draws['E3_r3_crossfit','r3_only']
      main=json.loads((OUT/'results/E3_summary.json').read_text(encoding='utf-8'))
      nested=json.loads((OUT/'results/E3b_summary.json').read_text(encoding='utf-8'))
      write_json('results/E3b_uncertainty.json',{'model':summary,'observed_difference':nested['metrics']['nested_context']['macro_f1']['mean']-main['r3_only']['macro_f1']['mean'],
        'paired_conditional95':np.quantile(delta,[.025,.975]).tolist(),'scope':'post-E3 exploratory supplement; inner folds select history weight, outer students held out'})
    real,eedi,llm,r3=load();by={r['sample_id']:r for r in real};rank={'high':2,'medium':1,'low':0};data=[]
    for r in r3:
      parent=by[r['pair_id']];match={'A':'high','B':'medium','C':'low'}[r['ai_type']]==parent['final_level']
      old=r['final_level']==ACK or rank[r['final_level']]<rank[parent['final_level']]
      conservative=r['final_level']!=ACK and rank[r['final_level']]<rank[parent['final_level']]
      data.append({'student_id':r['student_id'],'baseline':parent['final_level'],'after':r['final_level'],'matched':match,
                   'historical_guidance':r['ai_type'],'old_decline':old,'conservative_decline':conservative,'r3_text':r['prompt_text']})
    res={};strata=[]
    for outcome in ['old_decline','conservative_decline']:
      groups={};std={True:0.,False:0.}
      for g in [True,False]:
        gg=[r for r in data if r['matched']==g];groups[str(g)]={'n':len(gg),'k':sum(r[outcome] for r in gg),'rate':sum(r[outcome] for r in gg)/len(gg)}
      for lv in LAB:
        allg=[r for r in data if r['baseline']==lv];weight=len(allg)/47
        for g in [True,False]:
          gg=[r for r in allg if r['matched']==g];k=sum(r[outcome] for r in gg)
          assert len(gg)>0;rate=k/len(gg);std[g]+=weight*rate
          strata.append({'outcome':outcome,'baseline':lv,'matched':g,'n':len(gg),'k':k,'rate':rate,'standard_weight':weight})
      a,b=groups['True'],groups['False'];p=fisher_exact([[a['k'],a['n']-a['k']],[b['k'],b['n']-b['k']]]).pvalue
      res[outcome]={'groups':groups,'fisher_two_sided':float(p),'baseline_standardized_rates':{str(g):v for g,v in std.items()},
                    'standardized_mismatch_minus_match':std[False]-std[True]}
    counts=[[sum(r['baseline']==a and r['after']==b for r in data) for b in LAB+[ACK]] for a in LAB]
    selected=[r for r in data if r['after']!=ACK];selected_groups={}
    for g in [True,False]:
      gg=[r for r in selected if r['matched']==g]
      selected_groups[str(g)]={'n':len(gg),'k':sum(r['conservative_decline'] for r in gg)}
    a,b=selected_groups['True'],selected_groups['False']
    excluded={'n':len(selected),'k':sum(r['conservative_decline'] for r in selected),'groups':selected_groups,
       'fisher_two_sided':float(fisher_exact([[a['k'],a['n']-a['k']],[b['k'],b['n']-b['k']]]).pvalue),
       'limit':'Selection on post-guidance response; descriptive sensitivity, not causal evidence'}
    write_json('results/E4_observational.json',{'n':47,'transitions':counts,'outcomes':res,'excluding_ack_sensitivity':excluded,
       'limits':['历史指导由自报确定，无随机对照','接受事件不是学习成效','起点标准化仅描述，不消除未测混淆','不使用旧R3评价不存在的新算法引导效果']})
    write_csv('results/E4_baseline_strata.csv',strata);write_csv('results/E4_real_pairs.csv',data)
    # Patient/student-level aggregate fold-out predictions for auditable error review, no invented human labels.
    agg=[]
    for e,labels in [('E2_student_crossfit',LAB),('E3_r3_crossfit',LAB+[ACK])]:
      for v in sorted({r['variant'] for r in rows if r['experiment']==e}):
        for sid in sorted({r['sample_id'] for r in rows if r['experiment']==e}):
          rr=[r for r in rows if r['experiment']==e and r['variant']==v and r['sample_id']==sid]
          p=np.mean([[float(r['p_'+k]) for k in labels] for r in rr],axis=0);pred=labels[p.argmax()]
          agg.append({'experiment':e,'variant':v,'sample_id':sid,'student_id':rr[0]['student_id'],'truth':rr[0]['truth'],
                      'repeat_averaged_prediction':pred,'error':pred!=rr[0]['truth'],'repeat_agreement':max(Counter(r['prediction'] for r in rr).values())/len(rr),
                      **{'p_'+k:float(p[i]) for i,k in enumerate(labels)}})
    write_csv('results/重复折外预测_错误复核.csv',agg)
    print('Prediction uncertainty, paired contrasts, baseline-stratified observation analysis and error review completed.')
if __name__=='__main__':run()
