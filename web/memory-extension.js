// Loaded only by the candidate service. The frozen common page is untouched.
const memoryOriginalRender=render;
render=function(){
 memoryOriginalRender();
 if(!session?.evidence_memory)return;
 const memory=session.evidence_memory.view,last=session.records.at(-1);
 if(session.records.some(record=>record.support.routing_version!==session.support_policy_version)){
  document.querySelector('.notice').textContent='连续辅导已更新：题目和前面的记录都保留。之前的回复保持原样，接下来发的新问题会使用新版辅导。';
 }
 $('versions').textContent=$('versions').textContent.replace('换题请新建会话。','可以明确写“换一道题”或“回到上一题”；指向不清时会保留待确认。');
 if(memory.latest_student)$('evidence').append(node('div','当前接续：'+memory.latest_student.text,'evidence-item'));
 $('evidence').append(node('div',`已保留本题 ${memory.student_contributions.length} 条学生步骤或思路线索；助手提示单独保存，不当作学生自主完成。`,'muted'));
 if(last?.support.continuation_bridge_used)$('evidence').append(node('div','本轮核对已有步骤；等级仍待确认，累计状态没有因此下降。','evidence-item'));
 const tutorNodes=$('history').querySelectorAll('.message.tutor');
 session.records.forEach((record,index)=>{
  const meta=tutorNodes[index]?.querySelector('.meta');if(!meta)return;
  const support=record.support;
  meta.textContent=support.route_executed==='edge_fixed'?'一起想下一步 · 本地引导':
   support.route_executed==='edge_verify'?'继续交流':
   support.route_executed==='cloud_reply_withheld_local_hint'?'先给你一个小提示':
   support.status==='success'?'数学辅导 · '+support.tier:'本轮连接未成功';
 });
 if(last?.support.continuation_bridge_used){
  $('decision-reason').textContent='题目和已有步骤已保留。本轮按你的思路或核对需求提供受限云端辅导；依赖等级仍待确认，累计状态如实保持。';
 }
 if(last?.support.response_guard?.withheld)$('decision').textContent='核对后提供本地提示';
};
