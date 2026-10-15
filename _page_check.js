
const S = { tasks: [], summary: {}, problems: [], ai: {}, now: null };
const $ = id => document.getElementById(id);

function toast(msg){
  const t = $('toast'); t.textContent = msg; t.classList.add('show');
  clearTimeout(t._h); t._h = setTimeout(()=>t.classList.remove('show'), 2200);
}
let globalsNow = Date.now();
function parseDue(s){ if(!s) return null; const d = new Date(s.replace(' ','T')); return isNaN(d)?null:d; }
function remainText(dueStr){
  const d = parseDue(dueStr); if(!d) return '未知';
  let ms = d.getTime() - globalsNow;
  const over = ms < 0; ms = Math.abs(ms);
  const min = Math.floor(ms/60000), h = Math.floor(min/60), day = Math.floor(h/24);
  let parts=[]; if(day) parts.push(day+' 天');
  if(h%24) parts.push((h%24)+' 小时');
  if(!day && min%60) parts.push((min%60)+' 分钟');
  if(!parts.length) parts.push('不到 1 分钟');
  return (over?'已过期 ':'还剩 ') + parts.join(' ');
}
const ORIGIN = {rule:['规则','b-rule'], ai:['AI 推断','b-ai'], user:['已修改','b-user']};

function badge(status){ return '<span class="badge b-'+status+'">'+status+'</span>'; }
function originBadge(o){ const [t,c]=ORIGIN[o]||ORIGIN.rule; return '<span class="badge '+c+'">'+t+'</span>'; }

function render(){
  globalsNow = S.now ? new Date(S.now).getTime() : Date.now();
  renderSummary(); renderChatFilter(); renderList();
}
function renderSummary(){
  const s = S.summary || {};
  $('summary').innerHTML =
    ['total|任务总数|total','urgent|紧急任务|urgent','soon|即将截止|soon','confirm|待确认|confirm']
    .map(x=>{const [k,label,cls]=x.split('|');
      return '<div class="stat '+cls+'"><b>'+(s[k]||0)+'</b><span>'+label+'</span></div>';}).join('');
}
function renderChatFilter(){
  const sel = $('fChat'); const cur = sel.value;
  const chats = [...new Set(S.tasks.map(t=>t.chat))].sort();
  sel.innerHTML = '<option value="">全部课程群</option>' + chats.map(c=>'<option>'+c+'</option>').join('');
  sel.value = cur;
}
function visibleTasks(){
  const q = $('q').value.trim().toLowerCase();
  const st = $('fStatus').value, ch = $('fChat').value, sort = $('sortBy').value;
  let arr = S.tasks.filter(t=>{
    if(st && t.status !== st) return false;
    if(ch && t.chat !== ch) return false;
    if(q){ const hay = (t.topic||'')+t.chat+t.text+t.sender; if(!hay.toLowerCase().includes(q)) return false; }
    return true;
  });
  const rank = {'已过期':0,'紧急':1,'即将':2,'待确认':3,'一般':4,'未知':5,'已作废':9};
  arr.sort((a,b)=>{
    if(sort==='chat') return (a.chat+a.topic).localeCompare(b.chat+b.topic);
    if(sort==='conf') return (b.needs_confirm?1:0)-(a.needs_confirm?1:0) || (rank[a.status]-rank[b.status]);
    if(sort==='urgent') return rank[a.status]-rank[b.status];
    const da=a.due?new Date(a.due.replace(' ','T')).getTime():Infinity;
    const db=b.due?new Date(b.due.replace(' ','T')).getTime():Infinity;
    return da-db;
  });
  return arr;
}
function renderList(){
  const arr = visibleTasks();
  $('filters').style.display = S.tasks.length ? 'flex' : 'none';
  if(!S.tasks.length){ $('list').innerHTML = '<div class="empty">还没有分析结果。<br>粘贴聊天记录后点「开始分析」，或点「载入示例」。</div>'; return; }
  if(!arr.length){ $('list').innerHTML = '<div class="empty">没有符合筛选条件的任务。</div>'; return; }
  $('list').innerHTML = arr.map(t=>{
    const over = t.status==='已过期';
    const dim = (t.status==='已作废'||t.excluded) ? ' dim' : '';
    return '<div class="task'+dim+(t.done?' done':'')+'">'+
      '<div class="tline">'+badge(t.status)+originBadge(t.origin)+
        '<span class="tname">'+esc(t.topic||t.text.slice(0,18))+'</span>'+
        (t.needs_confirm?'<span class="badge b-待确认">建议确认</span>':'')+'</div>'+
      '<div class="meta">课程群：'+esc(t.chat)+'｜发送人：'+esc(t.sender)+'｜消息时间：'+esc(t.msg_time)+'</div>'+
      '<div class="meta">截止：<span class="due'+(over?' over':'')+'">'+esc(t.due||'未知')+'</span>'+
        '（'+esc(t.due_source)+'）｜'+esc(t.remaining||remainText(t.due))+'</div>'+
      '<div class="meta">判断方式：'+esc(t.judge||'规则确认')+'｜置信度：'+esc(t.confidence_label||'未知')+
        '｜来源：课程群第'+((t.source_index==null?'?':t.source_index+1))+'条消息'+
        (t.reason?'｜原因：'+esc(t.reason):'')+'</div>'+
      '<div class="raw">原文：'+esc(t.text)+'</div>'+
      '<div class="acts">'+
        '<button onclick="toggleDone(\''+t.id+'\')">'+(t.done?'取消完成':'标记完成')+'</button>'+
        '<button onclick="openEdit(\''+t.id+'\')">修改</button>'+
        '<button onclick="exclude(\''+t.id+'\')">'+(t.excluded?'恢复':'排除误识别')+'</button>'+
      '</div></div>';
  }).join('');
}
async function smartPaste(){
  const raw = $('pasteInput').value;
  if(!raw.trim()){ toast('请先把老师发的消息粘贴进来'); return; }
  try{
    const r = await fetch('/api/smart_paste', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({text: raw, sender: $('pasteSender').value, chat: $('pasteChat').value})});
    const d = await r.json();
    if(!d.ok){ $('pasteNotes').innerHTML='<div class="notice err">'+esc(d.error)+'</div>'; return; }
    // 把补全后的标准行追加进主输入框
    const cur = $('input').value.trim();
    $('input').value = (cur ? cur + '\n' : '') + d.standard_line;
    $('pasteNotes').innerHTML = '<div class="notice info">已加入：'+esc(d.standard_line)+
      (d.notes && d.notes.length ? '<br>'+d.notes.map(esc).join('<br>') : '')+'</div>';
    $('pasteInput').value = '';
    toast('已识别并加入，点「开始分析」查看');
  }catch(e){ toast('识别失败：'+(e.message||e)); }
}
$('btnSmartPaste').onclick = smartPaste;

function esc(s){ return (s==null?'':String(s)).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

function find(id){ return S.tasks.find(t=>t.id===id); }
function toggleDone(id){ const t=find(id); if(t){ t.done=!t.done; renderList(); } }
function exclude(id){ const t=find(id); if(t){ t.excluded=!t.excluded; render(); toast(t.excluded?'已排除该任务':'已恢复该任务'); } }
function openEdit(id){
  const t=find(id); if(!t) return;
  $('editId').value=id; $('editTopic').value=t.topic||''; $('editDue').value=t.due||''; $('editNote').value=t.note||'';
  $('editRaw').textContent='原文：'+t.text;
  $('editDlg').showModal();
}
$('editCancel').onclick = ()=>$('editDlg').close();
$('editSave').onclick = ()=>{
  const t = find($('editId').value); if(!t) return;
  t.topic = $('editTopic').value.trim() || t.topic;
  const due = $('editDue').value.trim();
  if(due){ if(!parseDue(due)){ toast('时间格式不对，应为 YYYY-MM-DD HH:MM'); return; }
    t.due = due; t.due_source='用户修改'; t.explicit=true; t.ambiguous=false; t.needs_confirm=false;
    t.status = dueStatus(due); t.remaining = remainText(due);
  }
  t.note = $('editNote').value.trim();
  t.origin = 'user'; t.user_edited = true;
  $('editDlg').close(); render(); toast('已保存修改');
};
function dueStatus(dueStr){
  const d = parseDue(dueStr); if(!d) return '未知';
  const ms = d.getTime() - Date.now();
  if(ms < 0) return '已过期';
  if(ms <= 86400000) return '紧急';
  if(ms <= 3*86400000) return '即将';
  return '一般';
}

function currentMode(){ const el=document.querySelector('input[name=aimode]:checked'); return el?el.value:'offline'; }
function setMode(m){ const el=document.querySelector('input[name=aimode][value="'+m+'"]'); if(el) el.checked=true; updateModeBar(); }
function updateModeBar(){
  const m = currentMode();
  const map = {offline:'离线模式（仅规则）', demo:'项目演示 API', custom:'我的 API'};
  $('modeBar').textContent = '当前：' + (map[m]||m);
}
document.querySelectorAll('input[name=aimode]').forEach(el=>el.addEventListener('change', updateModeBar));

async function analyze(){
  const text = $('input').value;
  if(!text.trim()){ toast('请先粘贴聊天记录或载入示例'); return; }
  const btn = $('btnAnalyze'); btn.disabled=true; btn.innerHTML='<span class="spinner"></span> Agent 分析中…';
  $('notices').innerHTML=''; $('traceBox').innerHTML=''; $('uncBox').innerHTML='';
  try{
    const r = await fetch('/api/agent', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(Object.assign({text, mode: currentMode()}, customCfgPayload()))});
    const data = await r.json();
    if(!data.ok){ $('notices').innerHTML='<div class="notice err">分析失败：'+esc(data.error||'未知错误')+'</div>'; return; }
    S.tasks = data.tasks; S.summary = data.summary; S.problems = data.problems;
    S.ai = data.ai||{}; S.now = data.now; S.trace = data.trace||[]; S.uncertain = data.uncertain||{};
    renderProblems(); renderNotices(); renderTrace(); renderUncertain(); render();
  }catch(e){
    $('notices').innerHTML='<div class="notice err">请求失败：'+esc(e.message||e)+'</div>';
  }finally{ btn.disabled=false; btn.textContent='开始分析'; }
}
function renderProblems(){
  const p = S.problems||[];
  $('problemBox').innerHTML = p.length
    ? '<div class="notice warn">有 '+p.length+' 行无法识别：<br>'+p.slice(0,6).map(x=>'第 '+x.line_no+' 行（'+esc(x.reason)+'）').join('<br>')
      + (p.length>6?'<br>…':'')+'</div>'
    : '';
}
function renderNotices(){
  const a = S.ai||{}; let html='';
  if(a.enabled && a.used) html+='<div class="notice info">AI 增强：已发送 '+a.candidates+' 条待确认消息给模型。'+esc(a.sent_scope||'')+'（AI 结果标记为「AI 推断」，需你确认）</div>';
  else if(a.enabled && a.error) html+='<div class="notice warn">AI 增强不可用：'+esc(a.error)+'（下方为规则结果）</div>';
  else if(a.error) html+='<div class="notice info">'+esc(a.error)+'</div>';
  $('notices').innerHTML = html;
}

function renderTrace(){
  const t = S.trace || [];
  if(!t.length){ $('traceBox').innerHTML=''; return; }
  const rows = t.map(s=>'<div class="t"><span class="n">'+s.step+'</span><span><b>'+esc(s.title)+'</b>'+
    (s.detail?' — '+esc(s.detail):'')+(s.tool?' <span class="tool">[工具: '+esc(s.tool)+']</span>':'')+'</span></div>').join('');
  $('traceBox').innerHTML = '<div class="trace"><h3>🧠 分析过程（Agent Trace）</h3>'+rows+'</div>';
}
function renderUncertain(){
  const u = S.uncertain || {};
  if(!u.count){ $('uncBox').innerHTML=''; return; }
  const items = (u.items||[]).slice(0,8).map(i=>'· '+esc(i.topic)+'（'+esc(i.chat||'')+'）—— '+esc(i.reason)).join('<br>');
  $('uncBox').innerHTML = '<div class="unc"><b>⚠ 需要确认 '+u.count+' 条</b>（其中 '+u.need_ai+' 条建议交给 AI 判断）<br>'+items+'</div>';
}

$('btnAnalyze').onclick = analyze;
$('btnLoadDemo').onclick = async ()=>{
  const r = await fetch('/api/demo'); const d = await r.json();
  $('input').value = d.text; toast('已载入示例');
};
$('btnClear').onclick = ()=>{ $('input').value=''; S.tasks=[]; S.summary={}; S.problems=[]; render(); $('problemBox').innerHTML=''; $('notices').innerHTML=''; toast('已清空'); };
$('btnUpload').onclick = ()=>$('file').click();
$('file').onchange = e=>{
  const f = e.target.files[0]; if(!f) return;
  if(f.size > 512*1024){ toast('文件过大（限 512KB）'); return; }
  if(!/\.txt$/i.test(f.name)){ toast('只支持 .txt 文件'); return; }
  const rd = new FileReader(); rd.onload = ()=>{ $('input').value = rd.result; toast('已读取：'+f.name); };
  rd.readAsText(f, 'utf-8');
};
['q','fStatus','fChat','sortBy'].forEach(id=>{ $(id).addEventListener('input', renderList); $(id).addEventListener('change', renderList); });

function downloadBlob(name, blob){
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(a.href);
}
const MIME = {
  xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  csv: 'text/csv;charset=utf-8',
  json: 'application/json',
};
$('btnExportXlsx').onclick = ()=>fetchExport('xlsx');
$('btnExportCsv').onclick = ()=>fetchExport('csv');
$('btnExportJson').onclick = ()=>fetchExport('json');
async function fetchExport(kind){
  if(!S.tasks || !S.tasks.length){ toast('还没有可导出的任务'); return; }
  try{
    const r = await fetch('/api/export?format='+kind, {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({tasks: S.tasks})});
    if(!r.ok){
      let msg = '导出失败';
      try{ const e = await r.json(); if(e && e.error) msg = e.error; }catch(_){}
      toast(msg); return;
    }
    // 用 blob 拿二进制，避免把 XLSX 当文本破坏内容
    const blob = await r.blob();
    downloadBlob('deadline-sentinel.'+kind, new Blob([blob], {type: MIME[kind]||'application/octet-stream'}));
    toast('已导出 '+kind.toUpperCase());
  }catch(e){ toast('导出失败：'+(e.message||e)); }
}

// ===== AI 配置中心（配置只存本浏览器，服务端不保存）=====
let CFG = null;
const CFG_KEY = 'ds_custom_api';
function readLocalCfg(){
  try{ return JSON.parse(localStorage.getItem(CFG_KEY) || '{}') || {}; }catch(e){ return {}; }
}
function writeLocalCfg(o){
  try{ localStorage.setItem(CFG_KEY, JSON.stringify(o||{})); }catch(e){}
}
function clearLocalCfg(){ try{ localStorage.removeItem(CFG_KEY); }catch(e){} }
function customCfgPayload(){
  // 仅当"我的 API"模式、且本地填了 Key 时，才随请求带上；其余模式不带
  if(currentMode() !== 'custom') return {};
  const c = readLocalCfg();
  if(!c.api_key) return {};
  return {base_url:c.base_url||'', api_key:c.api_key||'', model:c.model||''};
}
function maskKey(k){
  k = (k||'').trim(); if(!k) return '(未配置)';
  if(k.length <= 8) return k[0] + '****';
  return k.slice(0,4) + '******' + k.slice(-2);
}
async function loadCfg(){
  try{ const r = await fetch('/api/agent_config'); const d = await r.json(); CFG = d.status; }catch(e){ CFG=null; }
  return CFG;
}
function renderCfg(){
  const c = CFG || {};
  const demo = c.demo||{};
  $('demoPane').innerHTML = demo.available
    ? ('演示 API：<span class="ok">可用</span>｜模型：'+esc(demo.model))
    : ('演示 API：<span class="no">未配置</span>（作品作者尚未提供默认演示接口）');
  const lc = readLocalCfg();
  $('cfgBase').value  = lc.base_url || '';
  $('cfgModel').value = lc.model || '';
  $('cfgKey').value   = lc.api_key || '';
  // 顶部提示
  const parts = [];
  if(demo.available) parts.push('演示 API 可用');
  if(lc.api_key) parts.push('我的 API 已配置（仅本浏览器）：'+esc(maskKey(lc.api_key)));
  $('aiHint').textContent = parts.length ? parts.join('｜') : '未配置任何 API；离线模式（规则）可正常使用。';
}
$('btnSettings').onclick = async ()=>{ await loadCfg(); renderCfg(); $('settingsDlg').showModal(); };
$('cfgClose').onclick = ()=>$('settingsDlg').close();
document.querySelectorAll('input[name=smode]').forEach(el=>el.addEventListener('change', ()=>{
  const m = document.querySelector('input[name=smode]:checked').value;
  $('customPane').style.display = (m==='custom')?'block':'none';
}));
$('cfgSave').onclick = async ()=>{
  const m = document.querySelector('input[name=smode]:checked').value;
  if(m==='custom'){
    writeLocalCfg({base_url:$('cfgBase').value, api_key:$('cfgKey').value, model:$('cfgModel').value});
    $('cfgMsg').innerHTML='<div class="notice info">已保存到<b>本浏览器</b>（localStorage），不会发给别人、服务端也不保存。</div>';
  }else{
    $('cfgMsg').innerHTML='<div class="notice info">已切换到 '+m+' 模式。</div>';
  }
  await loadCfg(); setMode(m); renderCfg();
};
$('cfgTest').onclick = async ()=>{
  const m = document.querySelector('input[name=smode]:checked').value;
  $('cfgMsg').innerHTML='<div class="notice info">测试中…</div>';
  const body = Object.assign({mode:m}, (m==='custom')
    ? {base_url:$('cfgBase').value, api_key:$('cfgKey').value, model:$('cfgModel').value} : {});
  const r = await fetch('/api/agent_test', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  const d = await r.json();
  $('cfgMsg').innerHTML = d.ok
    ? '<div class="notice info">✔ '+esc(d.message||'连接成功')+'（模型：'+esc(d.model||'')+'）</div>'
    : '<div class="notice err">✘ '+esc(d.error||d.message||'测试失败')+'</div>';
};
(async function initAI(){
  await loadCfg(); renderCfg(); updateModeBar();
  // 自动选择可用模式（优先级：演示 API > 本浏览器已配的「我的 API」> 离线）
  if(CFG && CFG.demo && CFG.demo.available){
    setMode('demo');
    $('aiHint').innerHTML += '<br>已自动选择「项目演示 API」，可点击「开始分析」直接体验。';
  } else if(readLocalCfg().api_key){
    setMode('custom');
  }
})();
