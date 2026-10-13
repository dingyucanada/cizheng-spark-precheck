const $ = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state = {status:null, files:[], roles:[], job:null, jobMode:"analyze", case:null, report:null, poll:null};
const roles = {unknown:'请选择视角',overall:'整体',base:'底足',mouth:'口沿 / 内壁',detail:'局部细节',mark:'款识'};
let toastTimer;
function toast(text){ $('toast').textContent=text; $('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,6000); }
async function api(path, opts={}){
  opts.headers = {...opts.headers};
  if(opts.method && opts.method!=='GET')opts.headers['x-cz-csrf']=state.status?.csrf || '';
  if(opts.body && !(opts.body instanceof FormData)){opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(opts.body);}
  const r=await fetch(path,opts);
  if(r.status===401){$('login-dialog').showModal();throw Error('请输入本机访问口令');}
  if(!r.ok){const error=await r.json().catch(()=>({detail:'请求失败，请稍后重试'}));throw Error(typeof error.detail==='string'?error.detail:'输入信息未通过检查');}
  return r.json();
}
async function boot(){
  try{
    state.status=await api('/api/status');
    $('connection').textContent=state.status.model_configured?'本地模型已配置':'本地资料工作台';
    $('model-note').textContent=state.status.model_configured?'原图只交给本地视觉模型。评分始终附带依据。':'公开馆藏体验可直接使用；提交新照片研判前，请在 Spark 上连接视觉模型。';
    $('online').disabled=!state.status.online_enabled;
    $('online').closest('label').title=state.status.online_enabled?'':'部署时启用联网检索后可选择';
    const demos=await api('/api/demos');
    $('demo-list').innerHTML=demos.map(d=>`<button class="demo" data-id="${d.object_id}"><img src="${esc(d.photo)}" alt="${esc(d.name)}"><span><strong>${esc(d.name)}</strong><small>${esc(d.description)}</small></span></button>`).join('');
    document.querySelectorAll('.demo').forEach(b=>b.addEventListener('click',()=>demo(Number(b.dataset.id))));
    const saved=localStorage.getItem('cz_last_job');
    if(saved){try{const j=await api('/api/jobs/'+saved);state.job=j.id;const c=await api('/api/cases/'+j.case_id);state.case=c.case;await observeJob(j);}catch{localStorage.removeItem('cz_last_job');}}
  }catch(e){toast(e.message);}
}
function setBusy(busy){$('analyze').disabled=busy;document.querySelectorAll('.demo').forEach(b=>b.disabled=busy);}
function selectedFiles(newFiles){
  if(state.files.length+newFiles.length>6){toast('一件器物最多选择 6 张照片');return;}
  for(const f of newFiles){if(f.size>8*1024*1024){toast('单张照片最多 8 MB');return;}if(!['image/jpeg','image/png','image/webp'].includes(f.type)){toast('请使用 JPEG、PNG 或 WebP 照片');return;}}
  state.files.push(...newFiles);state.roles.push(...newFiles.map(()=> 'unknown'));renderUploads();
}
function renderUploads(){
  document.querySelectorAll('#photo-list img').forEach(im=>URL.revokeObjectURL(im.src));
  $('photo-list').innerHTML=state.files.map((f,i)=>`<div class="upload-photo"><img src="${URL.createObjectURL(f)}" alt="第 ${i+1} 张待检照片"><button type="button" class="remove-photo" data-i="${i}" aria-label="移除第 ${i+1} 张照片">×</button><select data-i="${i}" aria-label="第 ${i+1} 张照片视角">${Object.entries(roles).map(([k,v])=>`<option value="${k}" ${state.roles[i]===k?'selected':''}>${v}</option>`).join('')}</select></div>`).join('');
  document.querySelectorAll('.remove-photo').forEach(b=>b.onclick=()=>{state.files.splice(Number(b.dataset.i),1);state.roles.splice(Number(b.dataset.i),1);renderUploads();});
  document.querySelectorAll('.upload-photo select').forEach(s=>s.onchange=()=>{state.roles[Number(s.dataset.i)]=s.value;});
}
async function demo(id){
  setBusy(true);
  try{state.case=await api('/api/demos',{method:'POST',body:{object_id:id}});await start('catalog');}
  catch(e){toast(e.message);setBusy(false);}
}
async function start(mode){
  clearTimeout(state.poll);state.jobMode=mode;$('retry').hidden=true;state.report=null;$('report').hidden=true;$('evidence').hidden=true;$('report-tools').hidden=true;$('empty').hidden=true;
  const j=await api(`/api/cases/${state.case.id}/jobs`,{method:'POST',body:{mode}});state.job=j.id;localStorage.setItem('cz_last_job',j.id);
  $('workspace-title').textContent=state.case.name;$('progress').hidden=false;$('cancel').hidden=false;await observeJob(j);
}
async function observeJob(j){
  state.jobMode=j.mode;
  $('stage').textContent=j.stage;$('percent').textContent=j.percent+'%';$('bar').style.width=j.percent+'%';$('progress-message').textContent=j.message;
  $('events').innerHTML=j.events.map(e=>`<li>${esc(e.message)}</li>`).join('');
  if(j.status==='complete'){
    state.report=await api(`/api/jobs/${j.id}/report`);$('progress').hidden=true;$('empty').hidden=true;setBusy(false);renderReport(state.report);return;
  }
  $('progress').hidden=false;$('empty').hidden=true;$('report').hidden=true;$('report-tools').hidden=true;$('evidence').hidden=true;
  if(['failed','cancelled','interrupted'].includes(j.status)){setBusy(false);$('cancel').hidden=true;$('retry').hidden=false;toast(j.message);return;}
  $('retry').hidden=true;$('cancel').hidden=false;setBusy(true);state.poll=setTimeout(async()=>{try{await observeJob(await api('/api/jobs/'+j.id));}catch(e){setBusy(false);toast(e.message);}},900);
}
function renderReport(r){
  const value=r.score.value;
  $('workspace-title').textContent=r.object_name;
  $('report-tools').hidden=false;$('report').hidden=false;
  $('mode-badge').textContent=r.mode==='catalog_audit'?'公开馆藏 · 资料核查':'本地视觉 · 辅助预检';
  $('pdf-download').href=`/api/jobs/${r.job_id}/report.pdf`;
  $('report').innerHTML=`<div class="paper-head"><span class="paper-brand">瓷证</span><span class="paper-id">${esc(r.report_id)}<br>${esc(r.generated_at.slice(0,10))}</span></div><h2>${esc(r.title)}</h2><div class="paper-name">${esc(r.object_name)}</div>
  <div class="opinion-block"><div><span class="opinion-kicker">预检意见</span><h3>${esc(r.opinion)}</h3><p>${esc(r.advice)}</p></div><div class="score"><small>送检关注评分</small><div class="score-num">${value??'—'} <span>/ 5</span></div><b>${esc(r.score.label)}</b><div class="score-bars">${[0,1,2,3,4].map(i=>`<i class="${value&&i<value?'active':''}"></i>`).join('')}</div></div></div>
  <div class="paper-photos">${r.photos.slice(0,3).map(p=>`<figure class="paper-photo"><img src="/api/cases/${r.case_id}/photos/${p.id}" alt="输入照片 ${p.id}"><figcaption>${p.id} · ${esc(roles[p.role]||'输入照片')}</figcaption></figure>`).join('')}</div><p class="paper-scope">${esc(r.scope)}</p><h4>判断理由</h4>
  ${r.reasons.map((x,i)=>`<div class="reason"><span class="number">0${i+1}</span><div><strong>${esc(x.title)}</strong><p>${esc(x.body)}</p><span class="refs">${esc(x.photo_ids.join(' / '))}${x.reference_ids.length?' · '+esc(x.reference_ids.join(' / ')):''}</span></div></div>`).join('')}
  <div class="next-step"><b>下一步</b><span>${esc(r.next_step)}</span></div><div class="report-note">${esc(r.score.meaning)}<br>${esc(r.notice)}</div>`;
  renderEvidence(r);
}
function renderEvidence(r){
  const observations=r.audit.observations?.observations || [];
  const groups=new Set(r.references.map(x=>x.source_group));
  $('evidence').innerHTML=`<h3>每条意见，都有来处</h3><p class="small muted">${esc(r.score.trigger)}。${r.mode==='catalog_audit'?'本轮为照片来源和公开资料核验，没有运行视觉模型。':'引用核验检查原句是否存在；模型二次复核仍需专业人士核实。'}</p>
  <h4>照片来源核验</h4><ul>${r.origin_matches.length?r.origin_matches.map(m=>`<li>${esc(m.photo_id)} · ${esc(m.reference_id)} · ${m.match==='exact_file'?'原文件一致':m.match==='exact_pixels'?'解码像素一致':'相似候选，尚未确认'}。不证明实物身份。</li>`).join(''):'<li>当前本地照片索引未发现匹配；这不能证明照片原创。</li>'}</ul>
  ${observations.length?'<h4>照片观察及疑点位置</h4>'+observations.map(o=>`<div class="observation"><div class="obs-image"><img src="/api/cases/${r.case_id}/photos/${o.photo_id}" alt="观察 ${esc(o.id)}"><div class="bbox" style="left:${o.bbox[0]*100}%;top:${o.bbox[1]*100}%;width:${(o.bbox[2]-o.bbox[0])*100}%;height:${(o.bbox[3]-o.bbox[1])*100}%"></div></div><div><strong>${esc(o.dimension)} · ${esc(o.location)}</strong><p>${esc(o.description)}</p><small>另一种解释：${esc(o.alternative||'未提供')}</small></div></div>`).join(''):''}
  <h4>参考资料 <span class="muted">${r.references.length} 条记录，${groups.size} 个来源机构</span></h4>${r.references.map(ref=>`<div class="source-card"><a href="${esc(ref.url)}" target="_blank" rel="noopener noreferrer">${esc(ref.id)} · ${esc(ref.title)} ↗</a><p class="fine">${esc(ref.provider)} · 馆藏号 ${esc(ref.accession)}</p><details><summary>查看原始摘录</summary><pre>${esc(ref.excerpt)}</pre></details></div>`).join('')}
  ${r.audit.comparisons?.length?'<h4>引用原句及替代解释</h4>'+r.audit.comparisons.map(c=>`<div class="source-card"><strong>${esc(c.explanation)}</strong><p>“${esc(c.quote)}”</p><small>替代解释：${esc(c.alternative)}</small></div>`).join(''):''}
  <h4>原图留存</h4><ul>${r.photos.map(p=>`<li>${esc(p.id)} · ${p.width} × ${p.height} · 指纹 ${esc(p.sha256.slice(0,16))}…</li>`).join('')}</ul><div class="audit-links"><a href="/api/jobs/${r.job_id}/evidence.zip">下载照片和完整证据包</a><a href="/api/jobs/${r.job_id}/report" target="_blank" rel="noopener">查看结构化报告</a></div>`;
}
$('photos').onchange=e=>{selectedFiles([...e.target.files]);e.target.value='';};
$('dropzone').onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();$('photos').click();}};
['dragenter','dragover'].forEach(n=>$('dropzone').addEventListener(n,e=>{e.preventDefault();$('dropzone').classList.add('drag');}));
['dragleave','drop'].forEach(n=>$('dropzone').addEventListener(n,e=>{e.preventDefault();$('dropzone').classList.remove('drag');}));
$('dropzone').addEventListener('drop',e=>selectedFiles([...e.dataTransfer.files]));
$('case-form').onsubmit=async e=>{
  e.preventDefault();if(!state.files.length){toast('请先选择器物照片，或体验一件公开馆藏');return;}
  if(!state.status.model_configured){toast('新照片需要本地视觉模型。当前可先体验下方公开馆藏。');return;}
  setBusy(true);try{const form=new FormData();form.append('metadata',JSON.stringify({name:$('name').value||'待检瓷器',claim:$('claim').value,source:$('source').value,online:$('online').checked,roles:state.roles}));state.files.forEach(f=>form.append('photos',f));state.case=await api('/api/cases',{method:'POST',body:form});await start('analyze');}catch(e){toast(e.message);setBusy(false);}
};
$('retry').onclick=async()=>{setBusy(true);try{await start(state.jobMode);}catch(e){setBusy(false);toast(e.message);}};
$('cancel').onclick=async()=>{try{await api('/api/jobs/'+state.job+'/cancel',{method:'POST',body:{}});}catch(e){toast(e.message);}};
$('evidence-button').onclick=()=>{$('evidence').hidden=!$('evidence').hidden;if(!$('evidence').hidden)$('evidence').scrollIntoView({behavior:'smooth',block:'start'});};
$('clear-button').onclick=()=>{clearTimeout(state.poll);localStorage.removeItem('cz_last_job');state.files=[];state.roles=[];renderUploads();$('report').hidden=true;$('evidence').hidden=true;$('progress').hidden=true;$('report-tools').hidden=true;$('empty').hidden=false;$('workspace-title').textContent='你的报告，从这里开始';setBusy(false);};
$('history-button').onclick=async()=>{try{const records=await api('/api/cases');$('history-list').innerHTML=records.length?records.map(c=>`<div class="history-item"><div>${esc(c.name)}<small>${c.photo_count} 张照片 · ${esc(c.source)} · ${esc(c.created_at.slice(0,10))}</small></div><button class="secondary history-open" data-id="${esc(c.id)}">打开</button></div>`).join(''):'<p class="muted">还没有器物记录。</p>';document.querySelectorAll('.history-open').forEach(b=>b.onclick=async()=>{try{const data=await api('/api/cases/'+b.dataset.id);state.case=data.case;$('history-dialog').close();if(data.jobs.length){clearTimeout(state.poll);state.job=data.jobs[0].id;localStorage.setItem('cz_last_job',state.job);await observeJob(data.jobs[0]);}else{toast('该器物尚未生成报告');}}catch(e){toast(e.message);}});$('history-dialog').showModal();}catch(e){toast(e.message);}};
$('close-history').onclick=()=>$('history-dialog').close();
$('login-form').onsubmit=async e=>{e.preventDefault();try{await api('/api/login',{method:'POST',body:{token:$('token').value}});$('token').value='';$('login-dialog').close();await boot();}catch(e){$('login-error').textContent=e.message;}};
boot();
