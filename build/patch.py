#!/usr/bin/env python3
"""Tạo public/index.html từ bản gốc (GitHub Pages) + lớp đồng bộ máy chủ Render.
Chạy: python3 build/patch.py <index.html gốc> <public/index.html đầu ra>
Mọi điểm neo đều được kiểm tra đúng 1 lần; sai là dừng ngay để không tạo ra bản hỏng."""
import sys

src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding='utf-8').read()


def rep(old, new, label):
    global s
    n = s.count(old)
    assert n == 1, f'[{label}] điểm neo xuất hiện {n} lần (cần đúng 1)'
    s = s.replace(old, new)


def rep_range(start, end, new, label, include_end=False):
    global s
    assert s.count(start) == 1, f'[{label}] điểm đầu xuất hiện {s.count(start)} lần'
    a = s.index(start)
    b = s.index(end, a)
    if include_end:
        b += len(end)
    s = s[:a] + new + s[b:]


# ---------- 1. Khối đồng bộ ----------
SYNC_NEW = r'''/* ============== Đồng bộ với máy chủ Render ==============
   Mọi người mở trang đều thấy bản TKB đã công bố. Chỉ quản trị (đăng nhập PIN) mới bấm "Công bố". */
let syncConfig = {url: '/api/data', autoLoad: true};
const ROLE = {admin:false, loaded:false, storage:'?', durable:true, adminEnabled:true};
const ADMIN_ONLY_PAGES = ['roster','update'];
let serverRev = null;          // phiên bản dữ liệu đang xem — để phát hiện có người công bố trước
let serverSyncedAt = null;
let lastPublishedJson = null;  // ảnh chụp dữ liệu lúc tải/công bố gần nhất — để biết "chưa công bố"
function snapshotJson(){ return JSON.stringify({store, namHocOptions: NAM_HOC_OPTIONS}); }
function isDirty(){ return ROLE.admin && lastPublishedJson!==null && snapshotJson()!==lastPublishedJson; }
function saveSyncUrlLocally(){ /* không còn dùng — địa chỉ máy chủ cố định */ }
function hasRealStore(st){
  return Object.values(st||{}).some(ctx => ctx && ((ctx.roster && ctx.roster.length>0) || (ctx.classes && ctx.classes.length>0)));
}
async function loadSession(){
  try{
    const r = await fetch('/api/session', {cache:'no-store', credentials:'same-origin'});
    if(!r.ok) throw new Error('HTTP '+r.status);
    const j = await r.json();
    ROLE.admin = !!j.admin; ROLE.storage = j.storage; ROLE.durable = !!j.durable; ROLE.adminEnabled = j.adminEnabled!==false;
  }catch(e){ ROLE.admin = false; }
  ROLE.loaded = true;
}
async function pullFromServer(){
  try {
    const res = await fetch('/api/data', {cache:'no-store', credentials:'same-origin'});
    if(!res.ok) return {ok:false, reason:'Máy chủ trả lỗi HTTP '+res.status};
    const data = await res.json();
    serverRev = data.rev || null;
    if(!data || !data.store || !hasRealStore(data.store)){
      lastPublishedJson = snapshotJson();
      return {ok:false, empty:true, reason:'Chưa có TKB nào được công bố trên máy chủ.'};
    }
    store = data.store;
    if(Array.isArray(data.namHocOptions)){
      data.namHocOptions.forEach(y=>{ if(!NAM_HOC_OPTIONS.includes(y)) NAM_HOC_OPTIONS.push(y); });
      NAM_HOC_OPTIONS.sort();
    }
    // Đưa người xem về đúng năm học/học kỳ đã công lần gần nhất
    let nh = data.namHoc, hk = data.hocKy;
    if(!(nh && hk && store[ctxKey(nh,hk)])){
      const k = Object.keys(store).sort().reverse().find(k=> (store[k].classes||[]).length>0 || (store[k].roster||[]).length>0);
      if(k){ [nh,hk] = k.split('___'); }
    }
    if(nh && hk){ state.namHoc = nh; state.hocKy = hk; if(!NAM_HOC_OPTIONS.includes(nh)){ NAM_HOC_OPTIONS.push(nh); NAM_HOC_OPTIONS.sort(); } }
    serverSyncedAt = data.syncedAt || null;
    lastPublishedJson = snapshotJson();
    return {ok:true, syncedAt: data.syncedAt};
  } catch(e){ return {ok:false, reason: 'Không kết nối được máy chủ ('+e.message+')'}; }
}
async function pushToServer(force){
  try {
    const real = hasRealStore(store);
    const payload = {store, namHocOptions: NAM_HOC_OPTIONS, namHoc: state.namHoc, hocKy: state.hocKy,
      baseRev: force ? 'force' : serverRev, allowEmpty: !real};
    const res = await fetch('/api/data', {
      method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)
    });
    let j = {}; try{ j = await res.json(); }catch(e){}
    if(res.status===401){ ROLE.admin = false; return {ok:false, status:401, reason:'Phiên đăng nhập đã hết hạn'}; }
    if(res.status===409) return {ok:false, status:409, conflict:true, reason: j.error||'Xung đột phiên bản'};
    if(!res.ok) return {ok:false, status:res.status, reason: j.error || ('HTTP '+res.status)};
    serverRev = j.rev || serverRev;
    serverSyncedAt = j.syncedAt;
    lastPublishedJson = snapshotJson();
    return {ok:true, syncedAt: j.syncedAt, durable: j.durable};
  } catch(e){ return {ok:false, reason: 'Không kết nối được máy chủ ('+e.message+')'}; }
}
function toast(msg, ok){
  let t = document.getElementById('appToast');
  if(!t){ t = document.createElement('div'); t.id = 'appToast'; document.body.appendChild(t); }
  t.textContent = msg; t.className = 'show ' + (ok===false?'bad':'good');
  clearTimeout(toast._t); toast._t = setTimeout(()=>{ t.className = ''; }, 6000);
}
async function publishNow(){
  if(!ROLE.admin){ openLoginModal(()=>publishNow()); return; }
  if(!confirm('Công bố TKB hiện tại cho tất cả mọi người xem?\nTKB cũ trên máy chủ sẽ được thay bằng bản này.')) return;
  const btn = document.getElementById('btnPublish');
  if(btn){ btn.disabled = true; btn.textContent = 'Đang công bố…'; }
  let r = await pushToServer(false);
  if(r.conflict){
    if(confirm('Có người vừa công bố một bản mới hơn bản bạn đang mở.\nBấm OK để GHI ĐÈ bằng bản của bạn, hoặc Hủy rồi bấm "Tải bản đang công bố" để xem bản kia trước.')) r = await pushToServer(true);
  }
  if(btn) btn.disabled = false;
  if(r.status===401){ applyRole(); openLoginModal(()=>publishNow()); return; }
  if(r.ok){
    toast(r.durable===false
      ? 'Đã công bố, NHƯNG máy chủ đang lưu tạm — dữ liệu có thể mất khi Render khởi động lại. Hãy cấu hình lưu trữ GitHub (xem Hướng dẫn).'
      : 'Đã công bố TKB lúc ' + new Date(r.syncedAt).toLocaleString('vi-VN') + '. Mọi người mở trang sẽ thấy bản mới.', r.durable!==false);
  } else if(!r.conflict){ toast('Không công bố được: ' + r.reason, false); }
  updateTopMeta(); refreshSyncStatusFoot();
}
async function reloadPublished(){
  if(isDirty() && !confirm('Bạn có thay đổi CHƯA công bố. Tải bản đang công bố sẽ làm mất các thay đổi đó. Tiếp tục?')) return;
  const r = await pullFromServer();
  if(r.ok){ buildContextSelector(); renderPage(currentPageId()); toast('Đã tải bản đang công bố.'); }
  else toast(r.reason, false);
}
function currentPageId(){ const a = document.querySelector('.nav-item.active'); return a ? a.dataset.page : 'overview'; }
function openLoginModal(onOk){
  const body = el(`<div>
    <p class="hint" style="margin:0 0 12px;">${ROLE.adminEnabled ? 'Nhập mã PIN quản trị để cập nhật và công bố TKB.' : 'Máy chủ chưa được đặt mã PIN quản trị (biến ADMIN_PIN).'}</p>
    <label>Mã PIN quản trị</label>
    <input type="password" id="inpAdminPin" autocomplete="current-password" style="width:100%;" ${ROLE.adminEnabled?'':'disabled'}>
    <div id="loginErr" style="color:var(--error);font-size:13px;margin-top:8px;min-height:18px;"></div>
    <div class="btnrow"><button type="button" class="gold" id="btnDoLogin" ${ROLE.adminEnabled?'':'disabled'}>Đăng nhập</button></div>
  </div>`);
  openModal('<span class="material-symbols-outlined">lock</span> Đăng nhập quản trị', body);
  const pin = body.querySelector('#inpAdminPin'); setTimeout(()=>pin.focus(), 50);
  async function go(){
    const errEl = body.querySelector('#loginErr'); errEl.textContent = '';
    try{
      const r = await fetch('/api/login', {method:'POST', credentials:'same-origin', headers:{'Content-Type':'application/json'}, body: JSON.stringify({pin: pin.value})});
      const j = await r.json().catch(()=>({}));
      if(!r.ok){ errEl.textContent = j.error || ('Lỗi HTTP '+r.status); return; }
      ROLE.admin = true; closeModal(); applyRole(); renderPage(currentPageId());
      if(typeof onOk==='function') onOk();
    }catch(e){ errEl.textContent = 'Không kết nối được máy chủ.'; }
  }
  body.querySelector('#btnDoLogin').addEventListener('click', go);
  pin.addEventListener('keydown', (e)=>{ if(e.key==='Enter') go(); });
}
async function doLogout(){
  if(isDirty() && !confirm('Bạn có thay đổi CHƯA công bố. Đăng xuất sẽ không lưu chúng. Tiếp tục?')) return;
  try{ await fetch('/api/logout', {method:'POST', credentials:'same-origin'}); }catch(e){}
  ROLE.admin = false;
  const r = await pullFromServer(); if(r.ok) buildContextSelector();
  applyRole();
  if(ADMIN_ONLY_PAGES.includes(currentPageId())) goTo('overview'); else renderPage(currentPageId());
}
function applyRole(){
  const admin = ROLE.admin;
  document.querySelectorAll('.nav-item').forEach(n=>{ if(ADMIN_ONLY_PAGES.includes(n.dataset.page)) n.style.display = admin ? '' : 'none'; });
  const cta = document.querySelector('.sidebar-cta'); if(cta) cta.style.display = admin ? '' : 'none';
  const ls = document.getElementById('lnkSettings'); if(ls) ls.style.display = admin ? '' : 'none';
  const tb = document.getElementById('topbarSettingsBtn'); if(tb) tb.style.display = admin ? '' : 'none';
  const auth = document.getElementById('btnAuth');
  if(auth){ auth.textContent = admin ? 'Quản trị viên · Đăng xuất' : 'Đăng nhập quản trị'; auth.onclick = admin ? doLogout : ()=>openLoginModal(); }
  const pub = document.getElementById('btnPublish');
  if(pub){ pub.style.display = admin ? '' : 'none'; pub.onclick = publishNow; }
  refreshSyncStatusFoot(); updateTopMeta();
}
window.addEventListener('beforeunload', (e)=>{ if(isDirty()){ e.preventDefault(); e.returnValue = ''; } });

'''
rep_range('/* ============== Online sync (Firebase Realtime Database, optional)', 'const state = {', SYNC_NEW, 'sync-block')

# ---------- 2. Chân sidebar ----------
FOOT_NEW = r'''function refreshSyncStatusFoot(){
  const el2 = document.getElementById('syncStatusFoot');
  if(!el2) return;
  let h = serverSyncedAt ? `Công bố lúc ${new Date(serverSyncedAt).toLocaleString('vi-VN')}` : 'Chưa có bản công bố';
  if(ROLE.admin){
    h += isDirty() ? '<br><span style="color:#e7cd9b;">● Có thay đổi chưa công bố</span>' : '<br>✓ Đã đồng bộ với máy chủ';
    if(!ROLE.durable) h += '<br><span style="color:#ffb4ab;">⚠ Máy chủ đang lưu tạm</span>';
  }
  el2.innerHTML = h;
}
'''
rep_range('function refreshSyncStatusFoot(){', 'function bindContextSelectorEvents(){', FOOT_NEW, 'foot')

rep('Dữ liệu lưu trong trình duyệt của bạn (phiên làm việc hiện tại). Dùng "Xuất / Nhập" để lưu lâu dài.',
    'TKB do nhà trường công bố trên máy chủ — mở trang là thấy bản mới nhất.', 'sidebar-foot-text')

# ---------- 3. Thanh trên: nút công bố + đăng nhập ----------
rep('<div class="topbar-admin">Admin Panel<span class="topbar-avatar"></span></div>',
    '<div class="topbar-admin"><button id="btnPublish" class="btn-publish" type="button" style="display:none">Công bố TKB</button>'
    '<button id="btnAuth" class="btn-auth" type="button">Đăng nhập quản trị</button><span class="topbar-avatar"></span></div>',
    'topbar-admin')

# ---------- 4. goTo: chặn trang quản trị khi chưa đăng nhập ----------
rep("function goTo(pageId){\n", "function goTo(pageId){\n  if(ADMIN_ONLY_PAGES.includes(pageId) && !ROLE.admin){ pageId = 'overview'; }\n", 'goTo')

# ---------- 5. updateTopMeta: trạng thái công bố ----------
rep("  refreshEffDatePill();\n}\n\nfunction updateBadges(){",
    "  refreshEffDatePill();\n"
    "  const pub = document.getElementById('btnPublish');\n"
    "  if(pub && ROLE.admin && !pub.disabled){ const d = isDirty(); pub.classList.toggle('dirty', d); pub.textContent = d ? 'Công bố TKB ●' : 'Đã công bố ✓'; }\n"
    "  if(serverSyncedAt && !ROLE.admin){ document.getElementById('topMeta').textContent += ' · Cập nhật ' + new Date(serverSyncedAt).toLocaleDateString('vi-VN'); }\n"
    "}\n\nfunction updateBadges(){", 'updateTopMeta')

# ---------- 6. Tổng quan ----------
rep('<h1 class="page-hello">Chào mừng trở lại, Quản trị viên</h1>',
    '<h1 class="page-hello">${ROLE.admin ? \'Chào mừng trở lại, Quản trị viên\' : \'Thời khóa biểu Trường THCS-THPT Nguyễn Khuyến\'}</h1>', 'hello')
rep("""Thời khóa biểu <b>${state.namHoc} · ${state.hocKy}</b>: cập nhật bằng file Excel,
    tra cứu theo lớp/giáo viên, thống kê số tiết và phát hiện trùng lịch — chạy hoàn toàn trong trình duyệt.</p>`));""",
    """Thời khóa biểu <b>${state.namHoc} · ${state.hocKy}</b>: ${ROLE.admin
      ? 'cập nhật bằng file Excel rồi bấm <b>Công bố TKB</b> để mọi người cùng thấy bản mới.'
      : 'tra cứu theo lớp/giáo viên, xem thống kê số tiết. Dữ liệu do nhà trường công bố' + (serverSyncedAt ? ' lúc ' + new Date(serverSyncedAt).toLocaleString('vi-VN') : '') + '.'}</p>`));""", 'lede')
rep('if(t7violations.length){\n    const warnCard', 'if(t7violations.length && ROLE.admin){\n    const warnCard', 't7')
rep('  wrap.appendChild(manageGrid);\n', '  if(ROLE.admin) wrap.appendChild(manageGrid);\n', 'manageGrid')

SYNCCARD_NEW = r'''const syncCard = el(`<div class="card teal">
    <h2><span class="material-symbols-outlined">cloud_upload</span> Công bố TKB cho mọi người</h2>
    <p class="hint">Sau khi cập nhật TKB (Excel) và kiểm tra, bấm <b>Công bố</b>. Người khác chỉ cần mở lại đường dẫn của trang là thấy bản mới nhất —
    không cần gửi file. Dữ liệu bạn đang chỉnh <b>chưa được lưu lên máy chủ</b> cho đến khi bấm Công bố.</p>
    ${ROLE.durable ? '' : '<p class="hint" style="color:#ffd9d4;"><b>⚠ Máy chủ đang lưu tạm:</b> dữ liệu đã công bố có thể mất khi Render khởi động lại. Cần cấu hình lưu trữ GitHub (xem Hướng dẫn bàn giao).</p>'}
    <div class="btnrow">
      <button id="btnPullSync" class="secondary" type="button">⬇ Tải bản đang công bố</button>
      <button id="btnPushSync" class="gold" type="button">⬆ Công bố TKB hiện tại</button>
    </div>
    <div id="syncStatus" style="margin-top:8px;font-size:13px;color:rgba(255,255,255,.85);">${serverSyncedAt ? 'Bản đang công bố: ' + new Date(serverSyncedAt).toLocaleString('vi-VN') : 'Chưa có bản công bố.'}</div>
  </div>`);
  syncCol.appendChild(syncCard);
  syncCard.querySelector('#btnPullSync').addEventListener('click', reloadPublished);
  syncCard.querySelector('#btnPushSync').addEventListener('click', publishNow);

  '''
rep_range('const syncCard = el(`<div class="card teal">', "exportCard.querySelector('#btnResetSeed')", SYNCCARD_NEW, 'syncCard')

# ---------- 7. Cài đặt ----------
SET_HTML_NEW = '''<div class="modal-section">
      <h3>Công bố &amp; lưu trữ</h3>
      <p class="hint" style="margin:0 0 8px;">Lưu trữ máy chủ: <b>${ROLE.durable ? 'GitHub (bền vững)' : 'tạm thời (có thể mất khi khởi động lại)'}</b>.<br>
      ${serverSyncedAt ? 'Bản đang công bố: ' + new Date(serverSyncedAt).toLocaleString('vi-VN') : 'Chưa có bản công bố.'}</p>
      <div class="btnrow"><button id="mBtnPublish" class="gold" type="button">Công bố TKB hiện tại</button></div>
    </div>
    '''
rep_range('<div class="modal-section">\n      <h3>Đồng bộ trực tuyến (Firebase)</h3>', '<div class="modal-section">\n      <h3>Dữ liệu hệ thống</h3>', SET_HTML_NEW, 'settings-html')
rep_range("body.querySelector('#mBtnSaveSyncUrl')", "body.querySelector('#mBtnExportState')",
          "body.querySelector('#mBtnPublish').addEventListener('click', ()=>{ closeModal(); publishNow(); });\n  ", 'settings-handlers')

# ---------- 8. Hỗ trợ ----------
s = s.replace('''<p class="hint" style="margin:0 0 10px;">Toàn bộ dữ liệu chạy ngay trong trình duyệt của bạn, không gửi lên máy chủ nào (trừ khi bạn tự bật Đồng bộ Firebase). Nếu gặp lỗi hiển thị, hãy chụp lại màn hình lỗi và gửi cho quản trị viên kỹ thuật của trường.</p>''',
              '''<p class="hint" style="margin:0 0 10px;">TKB hiển thị là bản do nhà trường đã công bố; mở lại trang là thấy bản mới nhất. Nếu gặp lỗi hiển thị, hãy chụp lại màn hình và gửi cho quản trị viên kỹ thuật của trường.</p>''')
assert 'Toàn bộ dữ liệu chạy ngay trong trình duyệt' not in s, 'help-text'
a = s.index('<button id="mBtnOpenFirebaseGuide"')
b = s.index('</button>', a) + len('</button>')
s = s[:a] + s[b:]
a = s.index("body.querySelector('#mBtnOpenFirebaseGuide')")
b = s.index('  });\n}', a) + len('  });\n')
s = s[:a] + s[b:]

# ---------- 9. Khởi động ----------
INIT_NEW = r'''applyRole();
(async function startup(){
  const banner = el('<div id="loadingBanner">Đang tải thời khóa biểu từ máy chủ… (lần đầu trong ngày có thể mất tới 1 phút)</div>');
  document.body.appendChild(banner);
  try {
    await loadSession();
    applyRole();
    const r = await pullFromServer();
    buildContextSelector();
    if(ADMIN_ONLY_PAGES.includes(currentPageId()) && !ROLE.admin) goTo('overview'); else renderPage(currentPageId());
    if(!r.ok && !r.empty) toast(r.reason, false);
  } catch(err){
    console.error('Lỗi khởi động:', err);
    try{ renderPage('overview'); }catch(e2){}
  } finally { banner.remove(); applyRole(); }
})();

'''
a = s.index('if(syncConfig.url && syncConfig.autoLoad){')
b = s.rindex('</script>\n</body>')
s = s[:a] + INIT_NEW + s[b:]

# ---------- 10. Kiểu dáng bổ sung ----------
CSS_NEW = '''
.btn-publish,.btn-auth{white-space:nowrap;}
.btn-publish{background:var(--surface-container-low);border:1px solid var(--outline-variant);color:var(--on-surface);padding:8px 16px;border-radius:999px;font-weight:700;font-size:13px;cursor:pointer;}
.btn-publish.dirty{background:var(--primary-container);border-color:var(--primary-container);color:var(--on-primary-container);}
.btn-auth{background:transparent;border:1px solid var(--outline-variant);color:var(--on-surface);padding:8px 14px;border-radius:999px;font-weight:700;font-size:13px;cursor:pointer;}
#loadingBanner{position:fixed;left:50%;top:14px;transform:translateX(-50%);z-index:500;background:var(--primary);color:#fff;padding:10px 18px;border-radius:999px;font-size:13px;font-weight:600;box-shadow:0 6px 24px rgba(0,0,0,.2);max-width:92vw;text-align:center;}
#appToast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%) translateY(20px);opacity:0;pointer-events:none;z-index:600;padding:12px 18px;border-radius:14px;font-size:14px;font-weight:600;max-width:92vw;box-shadow:0 8px 28px rgba(0,0,0,.25);transition:all .25s;}
#appToast.show{opacity:1;transform:translateX(-50%) translateY(0);}
#appToast.good{background:#0b5f3d;color:#fff;}
#appToast.bad{background:#93000a;color:#fff;}
@media (max-width:680px){.topbar-admin{gap:6px;}.btn-auth{padding:7px 10px;font-size:12px;white-space:nowrap;}.btn-publish{padding:7px 10px;font-size:12px;white-space:nowrap;}.topbar-avatar,.topbar-bell{display:none;}.topbar-right{gap:8px;}#topMeta{font-size:11px;line-height:1.3;max-width:42vw;}}
'''
rep('</style>\n</head>', CSS_NEW + '</style>\n</head>', 'css')

# ---------- 11. Nhãn bản dựng ----------
assert s.count('2026-06-29_0110-v32') >= 1
s = s.replace('2026-06-29_0110-v32', 'render-2026-10-08')

open(dst, 'w', encoding='utf-8').write(s)
print('OK', len(s), 'ký tự')
