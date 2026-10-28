const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
export function tendencyMarkup(value,language='en'){
 const zh=language==='zh';if(!value||value.status!=='computed')return '';
 const names=zh?{pass:'传球',shoot:'射门',dribble:'带球',hold:'等待'}:{pass:'Pass',shoot:'Shoot',dribble:'Carry',hold:'Hold'};
 return `<section class="card action-tendency"><h3>${zh?'动作类别倾向':'Action category tendency'}</h3><p>${zh?'手设 softmax 基线 · 不是成功率或进球概率 · 不改变候选排名':'Hand-set softmax baseline · not success or goal probability · does not change candidate ranks'}</p>${Object.entries(names).map(([k,label])=>`<label style="display:block">${label}: ${esc((100*value.distribution[k]).toFixed(1))}% <progress max="1" value="${esc(value.distribution[k])}"></progress></label>`).join('')}<details><summary>${zh?'方法与限制':'Method and limitations'}</summary><p>${esc(value.meaning)}</p><ul>${value.assumptions.map(a=>`<li>${esc(a)}</li>`).join('')}</ul></details></section>`;
}

export function workflowMarkup(value,language='en'){
 if(!value)return '';const zh=language==='zh';
 return `<section class="card"><h3>Microsoft Agent Framework · ${zh?'决策内核流程':'Decision kernel workflow'}</h3><p>${esc(value.backend)} · ${esc(value.status)}</p><p>${value.status==='computed'?(value.output.tools||[]).map(t=>esc(t.tool)).join(' → '):esc(value.reason)}</p><p>${zh?'解析式路线分数不替代 Q2；本流程未调用解说模型。四角色证据审核独立运行。':'Analytic route scores do not replace Q2. No narration model was called here; the evidence-reviewed four-role team runs separately.'}</p></section>`;
}
