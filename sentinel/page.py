"""网页前端（HTML + CSS + 原生 JS），由 webapp.py 作为静态页面返回。

之所以单独放一个模块：webapp.py 只管 HTTP 路由与 JSON API，
页面本身不掺 Python 逻辑，避免 f-string 大括号转义问题，也更好维护。
"""

PAGE_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>课程 Deadline 哨兵</title>
<style>
  :root{
    --bg:#0f172a; --panel:#ffffff; --ink:#1e293b; --muted:#64748b;
    --line:#e2e8f0; --brand:#2563eb; --brand-dark:#1d4ed8;
    --red:#dc2626; --orange:#ea580c; --green:#16a34a; --gray:#64748b;
    --violet:#7c3aed;
  }
  *{box-sizing:border-box}
  body{margin:0;font-family:"Microsoft YaHei","PingFang SC",system-ui,sans-serif;
       color:var(--ink);background:#0b1220;line-height:1.55}
  /* 视频背景层（fixed 铺满，纯装饰、不吃鼠标事件） */
  #bgvideo{position:fixed;inset:0;width:100%;height:100%;object-fit:cover;
           z-index:-2;pointer-events:none}
  #bgmask{position:fixed;inset:0;z-index:-1;pointer-events:none;
          background:linear-gradient(180deg,rgba(6,10,20,.34),rgba(6,10,20,.58))}
  @media(max-width:640px){#bgvideo{display:none}}
  header{background:linear-gradient(135deg,rgba(30,58,138,.86),rgba(37,99,235,.80));color:#fff;padding:22px 28px}
  header h1{margin:0;font-size:22px;font-weight:700;letter-spacing:.5px}
  header p{margin:6px 0 0;font-size:13px;opacity:.9}
  .wrap{max-width:1180px;margin:0 auto;padding:20px 24px 60px}
  .grid{display:grid;grid-template-columns:minmax(360px,1fr) minmax(420px,1.15fr);gap:20px;align-items:start}
  .panel{background:rgba(255,255,255,.94);backdrop-filter:blur(6px);
         border:1px solid var(--line);border-radius:12px;padding:16px 18px;
         box-shadow:0 2px 10px rgba(2,6,23,.18)}
  .panel h2{margin:0 0 10px;font-size:15px;font-weight:700;color:#0f172a}
  .hint{color:var(--muted);font-size:12.5px}
  textarea{width:100%;height:210px;resize:vertical;padding:10px;border:1px solid var(--line);
           border-radius:8px;font-family:Consolas,monospace;font-size:12.5px;color:var(--ink)}
  .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:10px}
  button{cursor:pointer;border:1px solid var(--line);background:#fff;color:var(--ink);
         padding:8px 14px;border-radius:8px;font-size:13.5px;transition:.15s}
  button:hover{border-color:#cbd5e1;background:#f8fafc}
  button.primary{background:var(--brand);border-color:var(--brand);color:#fff;font-weight:600}
  button.primary:hover{background:var(--brand-dark)}
  button:disabled{opacity:.55;cursor:not-allowed}
  button.link{border:none;background:none;color:var(--brand);padding:2px 4px}
  .file{display:none}
  label.check{font-size:13px;color:var(--muted);display:inline-flex;gap:6px;align-items:center}
  .cards{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:14px}
  .stat{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 12px}
  .stat b{display:block;font-size:22px;line-height:1.2}
  .stat span{font-size:12px;color:var(--muted)}
  .stat.urgent b{color:var(--red)} .stat.soon b{color:var(--orange)}
  .stat.confirm b{color:var(--violet)} .stat.total b{color:var(--brand)}
  .task{border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin-bottom:10px;background:#fff}
  .task.dim{opacity:.55}
  .task.done{text-decoration:line-through}
  .tline{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
  .tname{font-weight:700;font-size:15px}
  .badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:11.5px;color:#fff}
  .b-已过期{background:var(--red)} .b-紧急{background:var(--red)}
  .b-即将{background:var(--orange)} .b-一般{background:var(--green)}
  .b-未知{background:var(--gray)} .b-待确认{background:var(--violet)}
  .b-已作废{background:#94a3b8}
  .b-ai{background:#0891b2} .b-user{background:#4f46e5} .b-rule{background:#475569}
  .meta{color:var(--muted);font-size:12.5px;margin-top:4px}
  .due{font-weight:700}
  .due.over{color:var(--red)}
  .raw{margin-top:6px;font-size:12.5px;color:#475569;background:#f8fafc;border-left:3px solid var(--line);
       padding:6px 10px;border-radius:0 6px 6px 0}
  .acts{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
  .notice{border-radius:8px;padding:10px 12px;font-size:13px;margin-bottom:12px}
  .notice.err{background:#fef2f2;border:1px solid #fecaca;color:#991b1b}
  .notice.warn{background:#fffbeb;border:1px solid #fde68a;color:#92400e}
  .notice.info{background:#eff6ff;border:1px solid #bfdbfe;color:#1e40af}
  .empty{text-align:center;color:var(--muted);padding:34px 10px;font-size:14px}
  .spinner{width:15px;height:15px;border:2px solid #c7d2fe;border-top-color:var(--brand);
           border-radius:50%;display:inline-block;animation:spin .7s linear infinite;vertical-align:-2px}
  @keyframes spin{to{transform:rotate(360deg)}}
  .filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}
  .filters input[type=search],.filters select{padding:7px 10px;border:1px solid var(--line);
        border-radius:8px;font-size:13px;color:var(--ink);background:#fff}
  .filters input[type=search]{flex:1;min-width:150px}
  dialog{border:none;border-radius:12px;padding:0;box-shadow:0 20px 50px rgba(15,23,42,.3);max-width:520px;width:92%}
  dialog .dbody{padding:18px 20px}
  dialog h3{margin:0 0 10px;font-size:16px}
  dialog label{display:block;font-size:13px;color:var(--muted);margin:10px 0 4px}
  dialog input,dialog textarea{width:100%;padding:8px 10px;border:1px solid var(--line);
        border-radius:8px;font-size:13px;font-family:inherit}
  .toast{position:fixed;right:20px;bottom:20px;background:#0f172a;color:#fff;padding:10px 16px;
         border-radius:9px;font-size:13.5px;opacity:0;transform:translateY(8px);transition:.25s;pointer-events:none}
  .toast.show{opacity:1;transform:none}
  .legend{font-size:12px;color:var(--muted);margin-top:8px}
  .smart{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:12px 14px;margin-bottom:8px}
  .smart-title{font-weight:700;font-size:13.5px;color:#166534;margin-bottom:4px}
  .smart textarea{height:70px;background:#fff}
  .mini{font-size:12.5px;color:#374151;display:inline-flex;align-items:center;gap:5px}
  .mini input{padding:5px 8px;border:1px solid var(--line);border-radius:6px;font-size:12.5px;width:110px}
  .ver{font-size:12px;background:#1e40af;padding:2px 8px;border-radius:999px;font-weight:400;vertical-align:3px}
  .gear{position:absolute;right:24px;top:22px;background:rgba(255,255,255,.15);color:#fff;border:1px solid rgba(255,255,255,.35)}
  .gear:hover{background:rgba(255,255,255,.28)}
  header{position:relative}
  .trace{background:#0f172a;color:#cbd5e1;border-radius:10px;padding:12px 14px;font-size:12.5px;margin-bottom:12px}
  .trace h3{margin:0 0 8px;font-size:13px;color:#fff}
  .trace .t{display:flex;gap:8px;padding:3px 0;border-bottom:1px dashed #1e293b}
  .trace .t:last-child{border-bottom:none}
  .trace .n{color:#38bdf8;font-weight:700;min-width:16px}
  .trace .tool{color:#a78bfa;font-size:11px}
  .unc{background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:10px 12px;font-size:12.5px;margin-bottom:12px}
  .unc b{color:#92400e}
  .modebar{font-size:12.5px;color:var(--muted);margin-left:8px}
  dialog.wide{max-width:620px}
  .modeopt{display:flex;gap:16px;flex-wrap:wrap;margin:6px 0 4px}
  .modeopt label{display:flex;gap:6px;align-items:center;font-size:13.5px;color:var(--ink)}
  .kstatus{font-size:12.5px;color:var(--muted);margin-top:6px}
  .kstatus .ok{color:#16a34a;font-weight:700}
  .kstatus .no{color:#dc2626;font-weight:700}
  @media(max-width:900px){.grid{grid-template-columns:1fr}.cards{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body>
<video id="bgvideo" autoplay muted loop playsinline preload="auto" poster="">
  <source src="/assets/bg.mp4" type="video/mp4">
</video>
<div id="bgmask"></div>
<header>
  <h1>📌 课程 Deadline 哨兵 <span class="ver">Agent 版</span></h1>
  <p>Agent 编排 · 工具调用 · 规则优先 · AI 可选 · 可解释</p>
  <button class="gear" id="btnSettings">⚙ 设置 · AI 配置</button>
</header>
<div class="wrap">
  <div class="grid">
    <!-- 左：输入 -->
    <div class="panel">
      <h2>① 输入聊天记录</h2>

      <!-- 智能粘贴：最省事的用法 -->
      <div class="smart">
        <div class="smart-title">⚡ 懒人用法：直接把老师发的消息贴进来</div>
        <p class="hint">不用管格式，粘贴后自动补上「时间 / 发送人 / 群名」。</p>
        <textarea id="pasteInput" placeholder="实验三报告下周日晚上12点前交，迟交扣20%"></textarea>
        <div class="row">
          <label class="mini">发送人 <input id="pasteSender" value="老师" placeholder="老师"></label>
          <label class="mini">群名 <input id="pasteChat" value="我的课程群" placeholder="我的课程群"></label>
          <button class="primary" id="btnSmartPaste">识别并加入</button>
        </div>
        <div id="pasteNotes"></div>
      </div>

      <p class="hint" style="margin-top:14px">标准格式（也可以自己粘贴/上传）：<code>时间 | 发送人 | 群名 | 内容</code></p>
      <textarea id="input" placeholder="2026-10-14 09:12 | 助教-李 | 数据结构-2026秋 | 实验三报告下周日晚上12点前交"></textarea>
      <div class="row">
        <button class="primary" id="btnAnalyze">开始分析</button>
        <button id="btnLoadDemo">载入示例</button>
        <button id="btnUpload">上传 TXT</button>
        <input type="file" id="file" class="file" accept=".txt,text/plain">
        <button id="btnClear">清空</button>
      </div>
      <div class="row">
        <label class="check"><input type="radio" name="aimode" value="offline" checked> 离线模式</label>
        <label class="check"><input type="radio" name="aimode" value="demo"> 项目演示 API</label>
        <label class="check"><input type="radio" name="aimode" value="custom"> 我的 API</label>
        <span class="modebar" id="modeBar"></span>
      </div>
      <p class="hint" id="aiHint"></p>
      <div id="problemBox"></div>
    </div>

    <!-- 右：结果 -->
    <div class="panel">
      <h2>② 待办清单</h2>
      <div id="summary" class="cards"></div>
      <div id="notices"></div>
      <div id="traceBox"></div>
      <div id="uncBox"></div>
      <div class="filters" id="filters" style="display:none">
        <input type="search" id="q" placeholder="搜索任务 / 群名 / 原文…">
        <select id="fStatus">
          <option value="">全部状态</option>
          <option>紧急</option><option>即将</option><option>一般</option>
          <option>已过期</option><option>待确认</option><option>未知</option><option>已作废</option>
        </select>
        <select id="fChat"><option value="">全部课程群</option></select>
        <select id="sortBy">
          <option value="due">按截止时间</option>
          <option value="urgent">按紧急程度</option>
          <option value="chat">按课程群</option>
          <option value="conf">按待确认优先</option>
        </select>
        <button class="primary" id="btnExportXlsx">导出 Excel（推荐）</button>
        <button id="btnExportCsv">导出 CSV</button>
        <button id="btnExportJson">导出 JSON</button>
      </div>
      <div id="list"></div>
    </div>
  </div>
</div>

<dialog id="editDlg">
  <div class="dbody">
    <h3>修改任务</h3>
    <input type="hidden" id="editId">
    <label>任务名称</label>
    <input id="editTopic">
    <label>截止时间（YYYY-MM-DD HH:MM，留空表示未知）</label>
    <input id="editDue" placeholder="2026-10-20 23:59">
    <label>备注（可选）</label>
    <textarea id="editNote" rows="3"></textarea>
    <div class="raw" id="editRaw"></div>
    <div class="row" style="justify-content:flex-end">
      <button id="editCancel">取消</button>
      <button class="primary" id="editSave">保存</button>
    </div>
  </div>
</dialog>

<dialog id="settingsDlg" class="wide">
  <div class="dbody">
    <h3>⚙ 设置 · AI 配置</h3>
    <p class="hint">选择 AI 模式。离线模式无需任何配置；演示 API 由作品作者提供；「我的 API」兼容 OpenRouter / DeepSeek / 任意 OpenAI 兼容接口。</p>
    <div class="modeopt">
      <label><input type="radio" name="smode" value="offline"> 离线模式（只用规则，免费）</label>
      <label><input type="radio" name="smode" value="demo"> 项目演示 API</label>
      <label><input type="radio" name="smode" value="custom"> 我的 API</label>
    </div>

    <div id="demoPane" class="kstatus"></div>

    <div id="customPane" style="display:none">
      <label>API Base URL</label>
      <input id="cfgBase" placeholder="https://openrouter.ai/api/v1">
      <label>API Key</label>
      <input id="cfgKey" type="password" placeholder="sk-...">
      <label>Model</label>
      <input id="cfgModel" placeholder="openai/gpt-4o-mini">
      <p class="hint">Key 只保存在<b>你自己的浏览器</b>（localStorage），不发给其他访客、服务端也不保存；清除浏览器数据即删除。</p>
    </div>

    <div class="row" style="justify-content:flex-end">
      <button id="cfgTest">测试连接</button>
      <button class="primary" id="cfgSave">保存配置</button>
      <button id="cfgClose">关闭</button>
    </div>
    <div id="cfgMsg"></div>
  </div>
</dialog>

<div class="toast" id="toast"></div>

<script>
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
document.querySelectorAll('input[name=aimode]').forEach(el=>el.addEventListener('change', ()=>onMainModeChange(el.value)));
// 主面板选「我的 API / 演示 API」时，直接打开设置弹窗并展开对应输入框，
// 避免用户误以为"点了没反应、无处可填"。
function onMainModeChange(m){
  updateModeBar();
  if(m==='custom' || m==='demo') openSettings(m);
}
function openSettings(m){
  const el = document.querySelector('input[name=smode][value="'+m+'"]');
  if(el) el.checked = true;
  $('customPane').style.display = (m==='custom')?'block':'none';
  const d = $('settingsDlg');
  if(!d.open) d.showModal();
  loadCfg().then(()=>renderCfg());
}

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
$('btnSettings').onclick = async ()=>{
  const m = currentMode();
  openSettings(m==='demo' || m==='custom' ? m : 'offline');
};
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
</script>
</body>
</html>
"""
