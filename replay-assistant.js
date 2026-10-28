// D: UI state is independent of canonical candidates; never edits B's ranks.
export const words = {
 en: {fallbackTitle:'Analysis status',limitsLabel:'Model limitations and assumptions',configuration:'Model agents are not configured on the server. Computed analysis is available below.',title:'Ask the replay coach',language:'Language',audience:'Audience',fan:'Fan · plain explanation',analyst:'Analyst · evidence and assumptions',training:'Training · choose before comparison',choose:'Choose your action first',commit:'Lock my choice and compare',question:'Your football question',placeholder:'Why pass here instead of carrying forward?',run:'Run four model agents',running:'Reviewing evidence…',trace:'Actual agent calls',empty:'No model calls yet. Computed evidence remains available.',limits:'Synthetic match. Rankings and scenarios are model estimates, not verified real-match probabilities.',answer:'Reviewed explanation',fallback:'No approved model explanation. Use the computed comparison below.',choice:'Your locked choice',reveal:'Reveal historical action',stale:'Stale model answer discarded.',hypothesis:'HYPOTHESIS · alternative routes are not observed play',pending:'Choose an action to reveal computed ranks, reasons and the historical choice.'},
 zh: {fallbackTitle:'分析状态',limitsLabel:'模型限制与假设',configuration:'服务端尚未配置模型，暂未调用 Agent。下方计算分析仍可使用。',title:'向回放教练提问',language:'语言',audience:'解读方式',fan:'球迷 · 通俗解释',analyst:'分析师 · 证据与假设',training:'训练 · 先选动作再比较',choose:'先选出你会执行的动作',commit:'确定选择并查看比较',question:'你的足球问题',placeholder:'为什么这里选择传球，而不是向前带球？',run:'运行四个模型 Agent',running:'正在审核证据…',trace:'实际 Agent 调用记录',empty:'尚未调用模型。计算出的证据可直接查看。',limits:'模拟比赛。排名和推演来自模型假设，不是已验证的真实比赛概率。',answer:'审核后的解释',fallback:'没有通过审核的模型解释，请查看下方计算结果。',choice:'你已确定的动作',reveal:'揭示历史动作',stale:'已丢弃过期的模型回答。',hypothesis:'假设推演 · 替代路线不是已发生的比赛',pending:'先选择动作，再揭示计算排名、原因和历史动作。'}
};
export function newCoachState(language='en', audience='fan') {return {language,audience,training:false,locked:null,pick:null,question:'',response:null,busy:false,generation:0,error:''};}
export function acceptsResponse(value, doc) {return value?.snapshot_id===doc.snapshot_id && value?.data_version===doc.data_version && value?.candidate_set_id===doc.candidate_set_id;}
export function situationMarkup(state,doc,metadata,esc) {
 const f=doc.snapshot?.frame;if(!f?.score)return '';
 const team=metadata.players.find(p=>p.player_id===doc.snapshot.frame.ball_owner_id)?.team_id;
 const margin=(f.score[0]-f.score[1])*(team==='HOME'?1:-1),zh=state.language==='zh';
 const status=margin>0?(zh?'领先':'Leading'):margin<0?(zh?'落后':'Trailing'):(zh?'平局':'Level');
 const remaining=[1,2].includes(f.period)?Math.max(0,(3-f.period)*45-f.period_ms/60000):null;
 const text=zh?'当前排名未考虑保比分、争胜或晋级目标。赛制、总比分及补时剩余未知；不能据此断言应拖入加时。':'Current ranks do not model protecting a score, winning or qualification objectives. Competition rules, aggregate score and remaining added time are unknown; extra time cannot be assumed.';
 return `<div class="decision-note"><strong>${zh?'比赛背景':'Match context'} · ${esc(f.score.join(' – '))} · ${status}</strong><p>${remaining===null?'':(zh?'常规时间名义剩余约 ':'Nominal regulation time remaining: ')+Math.ceil(remaining)+(zh?' 分钟（不含补时）。':' min, excluding added time.')}</p><p>${text}</p></div>`;
}
export function coachMarkup(state, doc, metadata, actionLabel, esc) {
 const t=words[state.language], locked=state.training&&!state.locked;
 return `<section class="decision-reason replay-assistant"><h3>${t.title}</h3>${situationMarkup(state,doc,metadata,esc)}<div class="decision-toolbar"><label>${t.language}<select id="ra-lang"><option value="en" ${state.language==='en'?'selected':''}>English</option><option value="zh" ${state.language==='zh'?'selected':''}>中文</option></select></label><label>${t.audience}<select id="ra-audience"><option value="fan" ${state.audience==='fan'?'selected':''}>${t.fan}</option><option value="analyst" ${state.audience==='analyst'?'selected':''}>${t.analyst}</option></select></label></div><label><input id="ra-training" type="checkbox" ${state.training?'checked':''}> ${t.training}</label>
 ${locked?`<p>${t.pending}</p><label>${t.choose}<select id="ra-pick"><option value="">${t.choose}</option>${doc.public.candidates.filter(c=>c.eligible).sort((a,b)=>a.action_id.localeCompare(b.action_id)).map(c=>`<option value="${esc(c.action_id)}" ${state.pick===c.action_id?'selected':''}>${esc(actionLabel(c,metadata))}</option>`).join('')}</select></label><button class="button" id="ra-commit" ${state.pick?'':'disabled'}>${t.commit}</button>`:state.locked?`<p>${t.choice}: <strong>${esc(actionLabel(doc.public.candidates.find(c=>c.action_id===state.locked),metadata))}</strong></p>`:''}
 <p class="decision-note">${t.hypothesis}</p><label for="ra-question">${t.question}</label><textarea id="ra-question" maxlength="1200" rows="3" placeholder="${t.placeholder}">${esc(state.question)}</textarea><button class="button" id="ra-run" ${state.busy||locked?'disabled':''}>${state.busy?t.running:t.run}</button><p role="status">${esc(state.error)}</p>
 <div id="ra-result">${state.response?`<h4>${state.response.explanation?t.answer:t.fallbackTitle}</h4><p class="ra-answer">${esc(state.response.explanation?.text||(state.response.limitations.some(x=>x.includes('not configured'))?t.configuration:t.fallback))}</p>${state.response.explanation?`<p class="decision-note">${state.response.explanation.cited_evidence_ids.map(esc).join(' · ')}</p>`:''}<details><summary>${t.limitsLabel}</summary><ul>${state.response.limitations.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></details>`:''}
 <details><summary>${t.trace}</summary>${state.response?.agent_trace.length?`<ol>${state.response.agent_trace.map(x=>`<li>${esc(x.agent)} → ${esc(x.tool)} · ${x.ms} ms · ${x.ok?'OK':'failed'}</li>`).join('')}</ol>`:`<p>${t.empty}</p>`}</details><p class="decision-note">${t.limits}</p></div></section>`;
}
export function bindCoach(root,state,doc,bundle,api,redraw,signal,isCurrent) {
 const $=x=>root.querySelector(x),invalidate=()=>{state.generation++;state.response=null;state.error='';state.busy=false;};
 $('#ra-question').oninput=e=>{state.question=e.target.value;invalidate();$('#ra-result').replaceChildren();$('#ra-run').disabled=state.training&&!state.locked;};
 for(const [id,key] of [['ra-lang','language'],['ra-audience','audience']]) $('#'+id).onchange=e=>{state[key]=e.target.value;invalidate();redraw();};
 $('#ra-training').onchange=e=>{state.training=e.target.checked;state.locked=null;invalidate();redraw();};
 if($('#ra-pick')){$('#ra-pick').onchange=e=>{state.pick=e.target.value;$('#ra-commit').disabled=!state.pick;};$('#ra-commit').onclick=()=>{if(!$('#ra-pick').value)return;state.locked=$('#ra-pick').value;invalidate();redraw();};}
 $('#ra-run').onclick=async()=>{
  const generation=++state.generation;state.busy=true;state.error='';state.response=null;redraw();
  try {const request={...bundle.request,question:state.question.trim()||(state.language==='zh'?'比较当前可行的动作及其风险':'Compare the current options and their risks'),mode:state.audience,language:state.language};
   const result=await api('agents',{request,candidate_set_id:doc.candidate_set_id},signal);
   if(!isCurrent()||generation!==state.generation)return;
   if(!acceptsResponse(result,doc))throw Error(words[state.language].stale);
   state.response=result;
  }catch(e){if(e.name!=='AbortError'&&isCurrent()&&generation===state.generation)state.error=e.message;}
  finally{if(isCurrent()&&generation===state.generation){state.busy=false;redraw();}}
 };
}
