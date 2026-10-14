const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const roles={unknown:'请选择视角',overall:'整体',base:'底足',mouth:'口沿 / 内壁',detail:'局部细节',mark:'款识'};
let state={status:null,health:null,files:[],roles:[],urls:[],case:null,job:null,report:null,poll:null,epoch:0,busy:false,last:null,delivery:'saved'};
const formatTime=value=>{try{return new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(value)).replaceAll('/','-');}catch{return String(value).slice(0,16);}};
let toastTimer;
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,6000);}
async function api(path,opts={}){
 opts.headers={...opts.headers};if(opts.method&&opts.method!=='GET')opts.headers['x-cz-csrf']=state.status?.csrf||'';
 if(opts.body&&!(opts.body instanceof FormData)){opts.headers['Content-Type']='application/json';opts.body=JSON.stringify(opts.body);}
 const r=await fetch(path,opts);
 if(r.status===401){if(!$('login-dialog').open)$('login-dialog').showModal();throw Error('请输入本机访问口令');}
 if(!r.ok){const e=await r.json().catch(()=>({detail:'连接暂时中断，请稍后重试'}));throw Error(typeof e.detail==='string'?e.detail:'请检查照片和输入信息');}
 return r.json();
}
function setBusy(v){state.busy=v;['analyze','continue','edit-input','history-button','clear-button','rerun'].forEach(id=>$(id).disabled=v);}
function showStep(n){const changed=$(['intake','confirm','progress','report'][n-1]+'-view').hidden;['intake','confirm','progress','report'].forEach((v,i)=>$(v+'-view').hidden=i!==n-1);document.querySelectorAll('.journey li').forEach(li=>{const s=Number(li.dataset.step);li.classList.toggle('done',s<n);li.classList.toggle('current',s===n);if(s===n)li.setAttribute('aria-current','step');else li.removeAttribute('aria-current');});if(changed)window.scrollTo({top:0,behavior:'instant'});}
function pictures(){return state.urls.length?state.urls.map((url,i)=>({url,role:state.roles[i]})):(state.case?.photos||[]).map(p=>({url:`/api/cases/${state.case.id}/photos/${p.id}`,role:p.role}));}
async function refreshHealth(){
 try{state.health=await api('/api/model-health');}catch{state.health={ready:false};}
 $('connection').textContent=state.health.ready?'本机处理 · 原图留存':'设备待就绪';$('connection').classList.toggle('waiting',!state.health.ready);
 return state.health;
}
async function boot(){
 try{
  state.status=await api('/api/status');await refreshHealth();
  $('online').disabled=!state.status.online_enabled;$('online-note').textContent=state.status.online_enabled?'可按需启用公开资料查询。':'当前使用设备内的离线参考资料。';
  const params=new URLSearchParams(location.search);const requested=params.get('report');
  if(requested&&/^job_[a-f0-9]{16}$/.test(requested)){await openJob(requested,'saved');return;}
  if(params.has('new')){newCheck();return;}
  showStep(1);
  const saved=localStorage.getItem('cz_last_job');
  if(saved){try{const j=await api('/api/jobs/'+saved);state.last=j.id;$('resume-text').textContent=['queued','running'].includes(j.status)?'有一件器物正在预检，可继续查看进度。':j.status==='complete'?'上次报告已保存，可随时继续查看。':'上次预检的照片已保存，可继续处理。';$('resume-banner').hidden=false;}catch{localStorage.removeItem('cz_last_job');}}
 }catch(e){toast(e.message);}
}
function selectedFiles(files){
 if(state.files.length+files.length>6){toast('一件器物最多选择 6 张照片');return;}
 for(const f of files){if(f.size>8*1024*1024){toast('单张照片最多 8 MB');return;}if(!['image/jpeg','image/png','image/webp'].includes(f.type)){toast('请使用 JPEG、PNG 或 WebP 照片');return;}}
 if(!state.files.length)state.case=null;
 state.files.push(...files);state.roles.push(...files.map(()=> 'unknown'));state.urls.push(...files.map(f=>URL.createObjectURL(f)));renderUploads();
}
function renderUploads(){
 $('photo-count').textContent=state.files.length+' / 6';$('dropzone').classList.toggle('has-photos',!!state.files.length);
 $('photo-list').innerHTML=state.files.map((f,i)=>`<div class="upload-photo"><img src="${state.urls[i]}" alt="第 ${i+1} 张待检照片"><button type="button" class="remove-photo" data-i="${i}" aria-label="移除第 ${i+1} 张照片">×</button><select data-i="${i}" aria-label="第 ${i+1} 张照片视角">${Object.entries(roles).map(([k,v])=>`<option value="${k}" ${state.roles[i]===k?'selected':''}>${v}</option>`).join('')}</select></div>`).join('');
 document.querySelectorAll('.remove-photo').forEach(b=>b.onclick=()=>{const i=Number(b.dataset.i);URL.revokeObjectURL(state.urls[i]);state.files.splice(i,1);state.roles.splice(i,1);state.urls.splice(i,1);renderUploads();});
 document.querySelectorAll('.upload-photo select').forEach(s=>s.onchange=()=>state.roles[Number(s.dataset.i)]=s.value);
}
function showConfirmation(){
 const photos=pictures();if(photos.length<2){toast('请至少添加整体和底足两张照片');return;}
 $('confirm-name').textContent=state.case?state.case.name:$('name').value;
 $('confirm-count').textContent=photos.length+' 张 · '+[...new Set(photos.map(p=>roles[p.role]))].join('、');
 $('confirm-source').textContent=state.case?state.case.source:$('source').value;
 $('confirm-claim').textContent=(state.case?state.case.claim:$('claim').value)||'先查看可见特征和需要进一步核验的位置';
 $('confirm-main').src=photos[0].url;$('confirm-thumbs').innerHTML=photos.map((p,i)=>`<button class="thumb ${i===0?'selected':''}" data-i="${i}" aria-label="查看第 ${i+1} 张照片"><img src="${p.url}" alt="${esc(roles[p.role])}"><span>${esc(roles[p.role])}</span></button>`).join('');
 document.querySelectorAll('.thumb').forEach(b=>b.onclick=()=>{$('confirm-main').src=photos[Number(b.dataset.i)].url;document.querySelectorAll('.thumb').forEach(t=>t.classList.toggle('selected',t===b));});
 $('confirm-alert').hidden=true;showStep(2);
}
async function submit(){
 if(state.busy)return;setBusy(true);$('confirm-alert').hidden=true;
 try{
  if(state.files.length){const form=new FormData();form.append('metadata',JSON.stringify({name:$('name').value.trim()||'待检瓷器',claim:$('claim').value,source:$('source').value,online:$('online').checked,roles:state.roles}));state.files.forEach(f=>form.append('photos',f));state.case=await api('/api/cases',{method:'POST',body:form});}
  if(!state.case)throw Error('请先添加器物照片');
  if(!(await refreshHealth()).ready){$('confirm-alert').textContent='设备暂未就绪，照片已保存。请联系现场工作人员，稍后可继续预检。';$('confirm-alert').hidden=false;setBusy(false);return;}
  await start();
 }catch(e){toast(e.message);setBusy(false);}
}
async function start(){
 clearTimeout(state.poll);const epoch=++state.epoch;state.delivery='live';state.report=null;$('resume-banner').hidden=true;
 // An explicit new precheck always requests fresh inference; opening an archive never does.
 const j=await api(`/api/cases/${state.case.id}/jobs`,{method:'POST',body:{mode:'analyze',force_new:true}});
 if(epoch!==state.epoch)return;state.job=j.id;localStorage.setItem('cz_last_job',j.id);await observeJob(j,epoch);
}
function progressFor(j){
 showStep(3);const photo=state.case?.photos?.[0];if(photo)$('processing-image').src=`/api/cases/${state.case.id}/photos/${photo.id}`;
 $('processing-name').textContent=state.case?.name||'待检器物';$('progress-title').textContent='正在为这件器物整理意见';
 $('stage').textContent=j.stage||'等待处理';$('percent').textContent=j.percent+'%';$('bar').style.width=j.percent+'%';$('progress-message').textContent=j.message;
 const steps=[...document.querySelectorAll('#phase-list li')];steps.forEach((li,i)=>{const at=Number(li.dataset.at),next=steps[i+1]?Number(steps[i+1].dataset.at):101;li.classList.toggle('done',j.percent>=next);li.classList.toggle('active',j.percent>=at&&j.percent<next);});
 $('retry').hidden=true;$('resume-status').hidden=true;$('failure-history').hidden=true;$('failure-back').hidden=true;$('cancel').hidden=false;
}
async function observeJob(j,epoch=state.epoch){
 if(epoch!==state.epoch)return;
 if(j.status==='complete'){
  const r=await api(`/api/jobs/${j.id}/report`);if(epoch!==state.epoch)return;
  state.report=r;setBusy(false);$('resume-banner').hidden=true;showStep(4);renderReport(r);return;
 }
 progressFor(j);
 if(['failed','cancelled','interrupted'].includes(j.status)){
  setBusy(false);$('cancel').hidden=true;$('retry').hidden=false;$('failure-history').hidden=false;$('failure-back').hidden=false;
  $('progress-title').textContent=j.status==='cancelled'?'本次预检已取消':'这次预检尚未完成';$('progress-message').textContent='照片和处理记录已保存。可以重新预检，或打开此前保存的报告。';return;
 }
 setBusy(true);state.poll=setTimeout(()=>pollJob(j.id,epoch),1000);
}
async function pollJob(id,epoch){
 try{const j=await api('/api/jobs/'+id);if(epoch===state.epoch)await observeJob(j,epoch);}catch(e){if(epoch!==state.epoch)return;$('stage').textContent='正在等待设备连接';$('progress-message').textContent='连接暂时中断，设备上的任务可能仍在处理。请重新连接查看进度。';$('cancel').hidden=true;$('resume-status').hidden=false;$('failure-history').hidden=false;toast(e.message);}
}
async function openJob(id,delivery='saved'){
 clearTimeout(state.poll);const epoch=++state.epoch;const j=await api('/api/jobs/'+id);const data=await api('/api/cases/'+j.case_id);if(epoch!==state.epoch)return;
 state.urls.forEach(u=>URL.revokeObjectURL(u));state.files=[];state.roles=[];state.urls=[];state.case=data.case;state.job=j.id;state.delivery=delivery;localStorage.setItem('cz_last_job',j.id);await observeJob(j,epoch);
}
function newCheck(){
 if(state.busy){toast('当前预检仍在处理，请等待完成或先取消');return;}
 clearTimeout(state.poll);state.epoch++;state.urls.forEach(u=>URL.revokeObjectURL(u));Object.assign(state,{files:[],roles:[],urls:[],case:null,job:null,report:null});
 localStorage.removeItem('cz_last_job');$('case-form').reset();$('resume-banner').hidden=true;$('evidence').hidden=true;$('confirm-alert').hidden=true;renderUploads();showStep(1);history.replaceState(null,'','/');
}
function renderReport(r){
  const value=r.score.value;
  $('workspace-title').textContent=r.object_name;
  $('delivery-label').textContent=state.delivery==='live'?'本次预检已完成':'已保存报告 · '+formatTime(r.generated_at); $('report').hidden=false;
  $('case-context').textContent=r.claim?'核验问题：'+r.claim:'同一器物归档，重新分析保留报告版本';
  $('rerun').disabled=false;
  $('rerun').textContent='重新预检';
  $('mode-badge').textContent=r.mode==='catalog_audit'?'公开馆藏 · 资料核查':'本地视觉 · 辅助预检';
  $('pdf-download').href=`/api/jobs/${r.job_id}/report.pdf`;
  $('report').innerHTML=`<div class="paper-head"><span class="paper-brand">瓷证</span><span class="paper-id">${esc(r.report_id)}<br>${esc(r.generated_at.slice(0,10))}</span></div><h2>${esc(r.title)}</h2><div class="paper-name">${esc(r.object_name)}</div>
  <div class="opinion-block"><div><span class="opinion-kicker">预检意见</span><h3>${esc(r.opinion)}</h3><p>${esc(r.advice)}</p></div><div class="score"><small>送检关注评分</small><div class="score-num">${value??'—'} <span>/ 5</span></div><b>${esc(r.score.label)}</b><div class="score-bars">${[0,1,2,3,4].map(i=>`<i class="${value&&i<value?'active':''}"></i>`).join('')}</div></div></div>
  <div class="paper-photos">${r.photos.slice(0,3).map(p=>`<figure class="paper-photo"><img src="/api/cases/${r.case_id}/photos/${p.id}" alt="输入照片 ${p.id}"><figcaption>${p.id} · ${esc(roles[p.role]||'输入照片')}</figcaption></figure>`).join('')}</div><p class="paper-scope">${esc(r.scope)}</p><h4>判断理由</h4>
  ${r.reasons.map((x,i)=>`<div class="reason"><span class="number">0${i+1}</span><div><strong>${esc(x.title)}</strong><p>${esc(x.body)}</p><span class="refs">${esc(x.photo_ids.join(' / '))}${x.reference_ids.length?' · '+esc(x.reference_ids.join(' / ')):''}</span></div></div>`).join('')}
  <div class="next-step"><b>下一步</b><span>${esc(r.next_step)}</span></div><div class="report-note">${esc(r.score.meaning)}<br>${esc(r.notice)}</div>`;
  renderEvidence(r);
  loadVersions(r);
}
async function loadVersions(r){
  try{
    const data=await api('/api/cases/'+r.case_id);
    if(state.report?.job_id!==r.job_id)return;
    const jobs=data.jobs.filter(j=>j.status==='complete');
    $('report-version').innerHTML=jobs.map((j,i)=>`<option value="${esc(j.id)}">${jobs.length-i} · ${j.mode==='analyze'?'模型分析':'资料核查'} · ${esc(formatTime(j.created_at))}</option>`).join('');
    $('report-version').value=r.job_id;
  }catch(e){toast(e.message);}
}
$('report-version').onchange=async()=>{try{const j=await api('/api/jobs/'+$('report-version').value);state.job=j.id;localStorage.setItem('cz_last_job',j.id);state.delivery='saved';await observeJob(j);}catch(e){toast(e.message);}};
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
$('case-form').onsubmit=e=>{e.preventDefault();if(state.files.length<2){toast('请至少添加整体和底足两张照片');return;}if(state.roles.includes('unknown')){toast('请为每张照片选择视角，方便核对位置');return;}state.case=null;showConfirmation();};
$('analyze').onclick=submit;$('edit-input').onclick=()=>{if(!state.files.length){toast('已归档照片可直接预检；如需替换照片，请开始新的预检');return;}state.case=null;showStep(1);};
$('retry').onclick=async()=>{setBusy(true);try{if(!(await refreshHealth()).ready){toast('设备暂未就绪，请稍后重试');setBusy(false);return;}await start();}catch(e){setBusy(false);toast(e.message);}};
$('resume-status').onclick=()=>pollJob(state.job,state.epoch);
$('cancel').onclick=async()=>{try{await api('/api/jobs/'+state.job+'/cancel',{method:'POST',body:{}});$('cancel').disabled=true;setTimeout(()=>$('cancel').disabled=false,1000);}catch(e){toast(e.message);}};
$('failure-back').onclick=showConfirmation;
$('evidence-button').onclick=()=>{$('evidence').hidden=!$('evidence').hidden;if(!$('evidence').hidden)$('evidence').scrollIntoView({behavior:'smooth',block:'start'});};
$('clear-button').onclick=newCheck;
async function showHistory(){try{
 const records=await api('/api/cases');
 $('history-list').innerHTML=records.length?records.map(c=>`<div class="history-item"><img src="/api/cases/${c.id}/photos/P1" alt="${esc(c.name)}"><div><strong>${esc(c.name)}</strong><small>${c.photo_count} 张照片 · ${c.report_count} 份已保存报告</small><small>${esc(c.source)}</small></div><button class="secondary history-open" data-id="${esc(c.id)}">打开</button></div>`).join(''):'<div class="history-empty"><strong>还没有器物档案</strong><p>添加照片并提交预检后，会保存在这里。</p></div>';
 document.querySelectorAll('.history-open').forEach(b=>b.onclick=async()=>{try{const data=await api('/api/cases/'+b.dataset.id);$('history-dialog').close();const latest=data.jobs.find(j=>j.status==='complete')||data.jobs[0];if(latest)await openJob(latest.id,'saved');else{state.case=data.case;state.files=[];state.urls.forEach(u=>URL.revokeObjectURL(u));state.urls=[];setBusy(false);showConfirmation();}}catch(e){toast(e.message);}});
 $('history-dialog').showModal();
}catch(e){toast(e.message);}}
$('history-button').onclick=showHistory;$('failure-history').onclick=showHistory;
$('close-history').onclick=()=>$('history-dialog').close();
$('rerun').onclick=()=>{state.files=[];state.urls.forEach(u=>URL.revokeObjectURL(u));state.urls=[];showConfirmation();};
$('resume-last').onclick=()=>openJob(state.last).catch(e=>toast(e.message));$('dismiss-resume').onclick=()=>$('resume-banner').hidden=true;
$('login-form').onsubmit=async e=>{e.preventDefault();try{await api('/api/login',{method:'POST',body:{token:$('token').value}});$('token').value='';$('login-dialog').close();await boot();}catch(e){$('login-error').textContent=e.message;}};
$('fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{toast('可使用浏览器菜单进入全屏展示');}};
document.addEventListener('fullscreenchange',()=>$('fullscreen').textContent=document.fullscreenElement?'退出全屏 ⛶':'全屏展示 ⛶');
boot();
