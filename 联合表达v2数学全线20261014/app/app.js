'use strict';
const $=id=>document.getElementById(id);
const names={high:'高依赖型求助',medium:'中依赖型求助',low:'低依赖型求助','接受引导/非提问':'接受 / 非提问'};
const events={question:'求助或解释表达',ack:'确认回应',answer_only:'仅答案或算式',ambiguous:'信息不足'};
const routeNames={cloud_direct:'纯云端回复',cloud_constrained:'云边协同回复',cloud_unavailable:'云端未成功返回',edge_fixed:'纯边缘固定回复',edge_verify:'本地证据核实',edge_evidence:'本地证据核实',local_evidence:'本地证据核实'};
function currentReading(a){
 if(!a)return {title:'等待你的第一条输入',reason:'从第一轮开始分析本轮表达；不必等待三轮。'};
 if(a.observed_event!=='question')return {title:events[a.observed_event]||'非提问事件',reason:'本轮已检测。'+a.decision_basis_note+'；不将此类回应计为依赖改善。'};
 if(a.eligible)return {title:names[a.current_behavior_level],reason:a.decision_basis_note+'；这是本轮求助方式，不代表学生整体能力。'};
 const candidate=['high','medium','low'].includes(a.candidate_level)?'暂定：'+names[a.candidate_level]:'求助表达';
 return {title:candidate+' · 待核实',reason:'本轮已分析，但不足以确定等级或更新状态。'+a.decision_basis_note};
}
let session=null,config=null,busy=false,pending=null;
async function api(url,options={}){const r=await fetch(url,{...options,headers:{'Content-Type':'application/json',...(options.headers||{})}});const data=await r.json();if(!r.ok){const e=new Error(data.error||'请求失败');e.status=r.status;throw e}return data}
const post=(url,data)=>api(url,{method:'POST',body:JSON.stringify(data)});
function node(tag,text,cls){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el}
function error(text){$('error').textContent=text;$('error').hidden=!text}
function setBusy(value){busy=value;$('submit').disabled=value||!session;$('new-session').disabled=value;$('prompt').disabled=value;$('task').disabled=value||!!session?.records.length;$('submit').textContent=value?'正在分析…':'分析并继续'}
function chart(records){const w=470,h=185,pad=37,right=16,top=12,bottom=30,x=i=>pad+(w-pad-right)*i/Math.max(1,records.length-1),y=v=>top+(h-top-bottom)*(1-v);const ns='http://www.w3.org/2000/svg';const svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.setAttribute('role','img');svg.setAttribute('aria-label','系统状态随实际输入变化，0到1工程值');
 function shape(type,attrs,text){const e=document.createElementNS(ns,type);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,String(v)));if(text!==undefined)e.textContent=text;svg.appendChild(e)}
 for(const v of new Set([0,config?.state_config.history_high_threshold??.5,1])){shape('line',{x1:pad,x2:w-right,y1:y(v),y2:y(v),stroke:'#dce6eb'});shape('text',{x:2,y:y(v)+4},v.toFixed(2))}
 const valid=records.map((r,i)=>({r,i})).filter(v=>v.r.analysis.risk!==null);
 if(valid.length)shape('polyline',{points:valid.map(({r,i})=>`${x(i)},${y(r.analysis.risk)}`).join(' '),fill:'none',stroke:'#327c7b','stroke-width':2.5});
 for(const {r,i} of valid)shape('circle',{cx:x(i),cy:y(r.analysis.risk),r:4.5,fill:r.analysis.risk_updated?'#327c7b':'#b18b6a'});
 if(!valid.length)shape('text',{x:pad+20,y:95},'尚无足够证据，状态值保持未知');
 if(records.length)for(const i of new Set([0,records.length-1]))shape('text',{x:x(i),y:h-8,'text-anchor':'middle'},`第${i+1}次`);
 $('chart').replaceChildren(svg)}
function render(){if(!session)return;const records=session.records,state=session.state,last=records.at(-1),a=last?.analysis;
 $('task').value=session.task_id;$('task-question').textContent=session.conversation_context?.question||session.task.question;$('task').disabled=!!records.length||busy;
 $('prompt-label').textContent=records.length?'继续写你的卡点、想法或尝试':'先写下题目和想问的内容';
 $('prompt').placeholder=records.length?'不用重复题目。例如：我不知道怎么找那两个数字，可以用另一个例子说明吗？':'例如：解x²−5x+6=0，可以先给我一些思路吗？';
 $('session-info').textContent=`匿名会话 ${session.session_id.slice(0,8)} · ${records.length}条现场输入 · 本机保存`;
 $('export').href='/api/export?id='+session.session_id;$('export').hidden=false;$('turn-badge').textContent=last?`第 ${last.turn} 次`:'尚无输入';
 $('versions').textContent=`模型 ${session.model_version}；规则 ${session.rule_version}；支持 ${session.support_policy_version}。导出包含原文、题目背景、实际支持、分数与更新理由。换题请新建会话。`;
 $('history').replaceChildren();if(!records.length)$('history').append(node('div','可以直接提问，也可以贴出自己已有的计算。每条新输入都会进入后台分析；系统不会替你生成下一次回应。','empty'));
 for(const r of records){const u=node('div',undefined,'message user');u.append(node('span',`你的输入 · 第${r.turn}次 · ${currentReading(r.analysis).title}`,'meta'),node('div',r.text));const s=node('div',undefined,'message tutor');s.append(node('span',`${r.support.tier} · ${r.support.provider} · ${r.support.status}`,'meta'),renderAnswer(r.support.text));$('history').append(u,s)}
 $('history').scrollTop=$('history').scrollHeight;
 const reading=currentReading(a);$('current-reading').textContent=reading.title;$('current-reading-reason').textContent=reading.reason;
 $('decision').textContent=a?(routeNames[last.support.route_executed]||last.support.tier):'等待你的第一条输入';
 $('decision-reason').textContent=a?((a.eligible?'综合路由等级：'+names[a.decision_level]+'。':'本轮等级待确认，按证据核实或起步提示规则支持。')+(a.history_high_protection||last.support.support_policy==='history_high_fixed_starter'?'历史高信号保护仍生效；即使本轮求助方式改变，也可能继续走纯边缘。':'')+(a.review_required?'规则与模型有差异，保留复核标记。':'')):'每次判断都保留原文与依据。';
 $('scores').replaceChildren();if(a){$('scores').append(node('div',`文本候选：${names[a.candidate_level]}；以下为模型分数。`,'muted'));for(const [key,value] of Object.entries(a.model_scores)){const row=node('div',undefined,'score'),track=node('div',undefined,'track'),fill=node('div',undefined,'fill');fill.style.width=`${value*100}%`;track.append(fill);row.append(node('span',names[key]),track,node('span',value.toFixed(3)));$('scores').append(row)}}
 $('evidence').replaceChildren();if(a){$('evidence').append(node('div',`回应事件：${events[a.observed_event]||a.observed_event}；${a.risk_updated?'状态已更新':'状态保持'}。`,'evidence-item'));
  for(const clue of a.lexical_clues||[])if(clue.matches.length)$('evidence').append(node('div',`${clue.name}：${clue.matches.join('、')}（词句匹配，需结合否定和语境）`,'evidence-item'));
  if(last.support.mathematical_check)$('evidence').append(node('div',last.support.mathematical_check.message,'evidence-item'));
  $('evidence').append(node('div',`拟执行路径：${last.support.route_requested}；实际路径：${last.support.route_executed}；外部API尝试 ${last.support.external_cloud_attempts} 次，成功 ${last.support.external_cloud_successes} 次。`,'evidence-item'));
  if(last.support.edge_suffix)$('evidence').append(node('div','本地追加模板：'+last.support.edge_suffix,'evidence-item'));
  if(a.single_risk!==null)$('evidence').append(node('div',`单轮信号 ${a.single_risk.toFixed(3)}（${a.single_risk_source}）；λ=${a.lambda}。`,'evidence-item'));
  $('evidence').append(node('div',`后台识别耗时 ${last.timing.model_ms.toFixed(2)} ms；本次请求往返 ${last.client_roundtrip_ms?.toFixed(2)||'刷新前未保留'} ms。`,'muted'))}
 $('risk').textContent=state.risk===null?'未知':state.risk.toFixed(3);$('coverage').textContent=`${state.evidence_turns} / ${state.events}`;
 $('change').textContent=a?.risk_change==null?'—':`${a.risk_change>0?'+':''}${a.risk_change.toFixed(3)}`;
 $('profile-note').textContent=(state.evidence_turns<3?`累计趋势待更多有效记录（已有${state.evidence_turns}条，工程展示规则至少3条）；本轮检测结果已在上方显示。`:`本会话系统状态：${a.profile.trajectory}。这是程序估计，不能推出学习效果。`)+(last?.support.hint_bridge_used?' 本轮提供方法提示，依赖证据不足，累计状态保持。':'');
 $('event-counts').replaceChildren(...[ ['确认',state.acknowledgements],['仅答案/算式',state.answer_only],['信息不足',state.ambiguous] ].map(([k,v])=>node('span',`${k} ${v}`)));
 chart(records)}
async function newSession(){setBusy(true);error('');pending=null;try{session=await post('/api/sessions',{task_id:$('task').value||'free'});localStorage.setItem('math-live-session',session.session_id);$('prompt').value='';$('length').textContent='0 / 2000';render()}catch(e){error(e.message)}finally{setBusy(false)}}
$('new-session').addEventListener('click',newSession);$('task').addEventListener('change',newSession);
$('prompt').addEventListener('input',()=>{$('length').textContent=`${$('prompt').value.length} / 2000`;if(pending&&pending.text!==$('prompt').value.trim())pending=null});
$('prompt-form').addEventListener('submit',async e=>{e.preventDefault();if(busy||!session)return;const text=$('prompt').value.trim();if(!text){error('请输入数学问题、尝试或回应');return}setBusy(true);error('');pending=pending||{session_id:session.session_id,text,request_id:crypto.randomUUID(),expected_version:session.version};const start=performance.now();try{const response=await post('/api/turns',pending);session=response.session;if(!response.duplicate)session.records.at(-1).client_roundtrip_ms=performance.now()-start;pending=null;$('prompt').value='';$('length').textContent='0 / 2000';render()}catch(e){error(e.message);if(e.status===409){session=await api('/api/session?id='+session.session_id);pending=null;render()}}finally{setBusy(false);$('prompt').focus()}});
async function boot(){try{config=await api('/api/config');$('task').replaceChildren(...Object.entries(config.tasks).sort(([a],[b])=>a==='free'?-1:b==='free'?1:0).map(([key,t])=>{const o=node('option',key==='free'?'自行输入数学题目':t.title+'（验收示例）');o.value=key;return o}));$('connection').textContent=config.cloud.configured?'本机已连接 · 云端已配置，待实际请求':'本机已连接 · 云端密钥未配置';$('cloud-status').textContent=`云端：${config.cloud.provider} / ${config.cloud.model_requested}；${config.cloud.configured?'已配置，实际请求结果逐条记录':'未配置密钥，未进行外部调用'}。`;$('coefficient-source').textContent=`信号采用原始p_high或明确行为规则的1/0编码；λ=${config.state_config.lambda}来自工程开发场景比较，历史保护阈值${config.state_config.history_high_threshold}暂保留工程参照。2026-10-15已复核新文本模型的代理阈值和两点敏感性；单轮标签不足以确定累计状态最优阈值。`;const previous=localStorage.getItem('math-live-session');if(previous){try{session=await api('/api/session?id='+previous);if(session.rule_version!==config.model_card.rule_version||session.model_version!==config.model_card.model_version)session=null}catch(e){if(e.status!==404&&e.status!==400)throw e}}if(session){render();setBusy(false)}else await newSession()}catch(e){$('connection').textContent='后台连接失败';error('无法连接本机服务：'+e.message);setBusy(false)}}
boot();
function renderCloud(){
 $('connection').textContent=config.cloud.configured?'本机已连接 · 云端已配置，实际结果逐条记录':'本机已连接 · 云端密钥未配置';
 $('cloud-status').textContent=`云端：${config.cloud.provider} / ${config.cloud.model_requested}；${config.cloud.configured?'已配置，连接与响应按实际请求记录':'未配置密钥，没有云端回答'}。`;
 $('api-setup').open=!config.cloud.configured;
}
$('key-form').addEventListener('submit',async e=>{
 e.preventDefault();let key=$('api-key').value.trim();$('key-status').textContent='正在本机配置…';
 try{const r=await post('/api/cloud-config',{api_key:key});config.cloud=r.cloud;renderCloud();$('key-status').textContent='本机配置成功。尚未发出验证请求；下一条需要云端的输入会实际调用。'}
 catch(err){$('key-status').textContent=err.message}finally{key=null;$('api-key').value=''}
});
const initialCloud=setInterval(()=>{if(config){renderCloud();clearInterval(initialCloud)}},100);
