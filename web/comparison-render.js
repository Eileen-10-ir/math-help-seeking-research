// Reuse the same sanitized Markdown/KaTeX rendering as the actual dialogue UI.
for(const source of document.querySelectorAll('textarea[data-markdown]')){
 const answer=renderAnswer(source.value);
 source.replaceWith(answer);
}
