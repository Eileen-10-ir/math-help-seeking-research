/* Local Markdown + sanitized HTML + bounded, untrusted KaTeX. */
function renderAnswer(source) {
 const box=document.createElement('div');box.className='answer-markdown';
 const maths=[], prefix='MATHPLACE'+crypto.randomUUID().replaceAll('-','')+'X';
 const protectedText=String(source).replace(/\\\[([\s\S]*?)\\\]|\$\$([\s\S]*?)\$\$|\\\(([^\n]*?)\\\)|(?<!\\)\$([^\n$]+?)\$/g,(raw,a,b,c,d)=>{
  if(maths.length>=200||raw.length>6000)return raw;
  const index=maths.push({raw,tex:a??b??c??d,display:a!==undefined||b!==undefined})-1;
  return prefix+index+'END';
 });
 const html=marked.parse(protectedText,{gfm:true,breaks:false});
 box.innerHTML=DOMPurify.sanitize(html,{FORBID_TAGS:['img','style','form','input','iframe','object','embed'],FORBID_ATTR:['style']});
 const walker=document.createTreeWalker(box,NodeFilter.SHOW_TEXT),texts=[];
 while(walker.nextNode())texts.push(walker.currentNode);
 const pattern=new RegExp(prefix+'(\\d+)END','g');
 for(const text of texts){
  const value=text.textContent;pattern.lastIndex=0;
  if(!pattern.test(value))continue;pattern.lastIndex=0;
  const fragment=document.createDocumentFragment();let cursor=0;
  for(const m of value.matchAll(pattern)){
   fragment.append(document.createTextNode(value.slice(cursor,m.index)));
   const item=maths[Number(m[1])];
   if(text.parentElement.closest('pre,code'))fragment.append(document.createTextNode(item.raw));
   else{const span=document.createElement(item.display?'div':'span');span.className=item.display?'math-block':'math-inline';
    try{katex.render(item.tex,span,{displayMode:item.display,throwOnError:false,trust:false,strict:'warn',maxExpand:1000,maxSize:10});}
    catch{span.textContent=item.raw}fragment.append(span)}
   cursor=m.index+m[0].length;
  }
  fragment.append(document.createTextNode(value.slice(cursor)));text.replaceWith(fragment);
 }
 for(const link of box.querySelectorAll('a')){link.rel='noopener noreferrer';link.target='_blank'}
 return box;
}
