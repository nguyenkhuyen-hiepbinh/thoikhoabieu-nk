import subprocess, time, os, json, sys, tempfile, urllib.request, urllib.error
from playwright.sync_api import sync_playwright

PORT = 3917; BASE = f'http://127.0.0.1:{PORT}'
tmp = tempfile.mkdtemp()
env = dict(os.environ, PORT=str(PORT), ADMIN_PIN='test-pin-123', SESSION_SECRET='x'*40, DATA_DIR=tmp)
srv = subprocess.Popen(['node','server.js'], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(1.2)
ok = True
def check(name, cond, extra=''):
    global ok
    print(('PASS ' if cond else 'FAIL ') + name + (' '+str(extra) if extra and not cond else ''))
    ok = ok and bool(cond)

def req(method, path, body=None, headers=None):
    r = urllib.request.Request(BASE+path, method=method, data=(json.dumps(body).encode() if body is not None else None),
        headers=dict({'Content-Type':'application/json'}, **(headers or {})))
    def parse(raw):
        try: return json.loads(raw or b'{}')
        except Exception: return {'_text': raw.decode('utf8','replace')[:80]}
    try:
        with urllib.request.urlopen(r) as resp: return resp.status, parse(resp.read()), resp.headers
    except urllib.error.HTTPError as e:
        return e.code, parse(e.read()), e.headers

try:
    # --- API ---
    st, j, _ = req('GET','/api/health'); check('health', st==200)
    st, j, _ = req('GET','/api/data'); check('data rỗng ban đầu', st==200 and j['store']=={}, j)
    st, j, _ = req('POST','/api/data',{'store':{}}); check('POST không đăng nhập bị chặn 401', st==401, (st,j))
    st, j, _ = req('POST','/api/login',{'pin':'sai'}); check('PIN sai 401', st==401)
    st, j, h = req('POST','/api/login',{'pin':'test-pin-123'}); check('PIN đúng 200', st==200)
    ck = h.get('Set-Cookie',''); check('cookie HttpOnly+SameSite', 'HttpOnly' in ck and 'SameSite=Lax' in ck, ck)
    cookie = ck.split(';')[0]
    st, j, _ = req('POST','/api/data',{'store':{}}, {'Cookie':cookie}); check('admin gửi dữ liệu trống bị từ chối 400', st==400, (st,j))
    st, j, _ = req('POST','/api/data',{'store':{'x___y':{'roster':[1],'classes':[]}}}, {'Cookie':cookie,'Origin':'https://evil.example'}); check('Origin lạ bị chặn 403', st==403, (st,j))
    st, j, _ = req('GET','/server.js'); check('không lộ server.js', st==404)
    st, j, _ = req('GET','/data/dulieu.json'); check('không lộ tệp dữ liệu qua đường dẫn', st==404)
    for i in range(6): s2,_,_ = req('POST','/api/login',{'pin':'sai'}, {'X-Forwarded-For':'9.9.9.9'})
    check('khoá IP sau nhiều lần sai (429)', s2==429, s2)

    # --- Giao diện ---
    sched = {}
    for ci,cls in enumerate(['10A1','10A2','11A1']):
        sched[cls] = [{'thu':t,'tiet':p,'mon':m,'gv':g} for (t,p,m,g) in [('Hai',1,'Toán','Nguyễn Văn An'),('Hai',2,'Văn','Trần Thị Bình'),('Ba',1,'Anh','Lê Văn Cường')] if not (ci==1 and t=='Hai' and p==1)]
    TEST = {'store':{'2026-2027___Học kỳ 1':{'roster':[{'ma':'GV01','ho':'Nguyễn Văn','ten':'An','mon':'Toán'}],'scheduleCurrent':sched,'schedulePrev':{},'classes':list(sched.keys()),'ngayApDung':'2026-09-05','history':[]}},'namHocOptions':['2026-2027'],'namHoc':'2026-2027','hocKy':'Học kỳ 1'}
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        # Người xem (trước khi có dữ liệu)
        ctx = b.new_context(viewport={'width':1280,'height':800}); pg = ctx.new_page()
        pg.on('pageerror', lambda e: errors.append(str(e))); pg.on('console', lambda m: errors.append(m.text) if m.type=='error' and 'fonts' not in m.text.lower() and 'ERR_' not in m.text and ' 401 ' not in m.text and ' 409 ' not in m.text else None)
        pg.goto(BASE); pg.wait_for_selector('#navList .nav-item', timeout=15000); pg.wait_for_timeout(800)
        vis = pg.eval_on_selector_all('.nav-item', 'els=>els.filter(e=>e.offsetParent!==null).map(e=>e.dataset.page)')
        check('người xem thấy tra cứu/thống kê, KHÔNG thấy DS GV/Cập nhật', 'tracuu' in vis and 'thongke' in vis and 'roster' not in vis and 'update' not in vis, vis)
        check('người xem không thấy nút quản trị/công bố', not pg.is_visible('#btnPublish') and pg.is_visible('#btnAuth'))
        check('người xem không thấy thẻ Quản lý & Chia sẻ dữ liệu', 'Quản lý' not in pg.inner_text('#content'))
        pg.evaluate("goTo('update')"); pg.wait_for_timeout(200)
        check('người xem gõ goTo(update) bị đưa về Tổng quan', pg.inner_text('#pageTitle')=='Tổng quan', pg.inner_text('#pageTitle'))

        # Quản trị đăng nhập qua giao diện
        pg.click('#btnAuth'); pg.fill('#inpAdminPin','sai'); pg.click('#btnDoLogin'); pg.wait_for_timeout(400)
        check('PIN sai hiện lỗi trong hộp thoại', 'không đúng' in pg.inner_text('#loginErr'), pg.inner_text('#loginErr'))
        pg.fill('#inpAdminPin','test-pin-123'); pg.press('#inpAdminPin','Enter'); pg.wait_for_timeout(600)
        vis = pg.eval_on_selector_all('.nav-item', 'els=>els.filter(e=>e.offsetParent!==null).map(e=>e.dataset.page)')
        check('sau đăng nhập hiện DS GV + Cập nhật', 'roster' in vis and 'update' in vis, vis)
        check('hiện nút Công bố', pg.is_visible('#btnPublish'))
        # nạp dữ liệu thử vào bộ nhớ trang như khi nhập Excel xong
        pg.evaluate("(T)=>{ store=T.store; NAM_HOC_OPTIONS.includes('2026-2027')||NAM_HOC_OPTIONS.push('2026-2027'); state.namHoc=T.namHoc; state.hocKy=T.hocKy; buildContextSelector(); renderPage('overview'); }", TEST)
        pg.wait_for_timeout(300)
        check('nút Công bố báo "chưa lưu" khi có thay đổi', 'Công bố TKB ●' in pg.inner_text('#btnPublish'), pg.inner_text('#btnPublish'))
        pg.once('dialog', lambda d: d.accept()); pg.click('#btnPublish'); pg.wait_for_timeout(1500)
        check('công bố thành công (toast)', 'Đã công bố' in pg.inner_text('#appToast') or 'lưu tạm' in pg.inner_text('#appToast'), pg.inner_text('#appToast'))
        check('nút chuyển sang "Đã công bố ✓"', 'Đã công bố' in pg.inner_text('#btnPublish'), pg.inner_text('#btnPublish'))
        pg.screenshot(path='build/shot-admin.png')

        # Người xem mới (thiết bị khác) thấy ngay bản mới
        ctx2 = b.new_context(viewport={'width':390,'height':800}); pv = ctx2.new_page()
        pv.on('pageerror', lambda e: errors.append(str(e)))
        pv.goto(BASE); pv.wait_for_selector('#navList .nav-item', timeout=15000); pv.wait_for_timeout(1000)
        meta = pv.inner_text('#topMeta')
        check('người xem thiết bị khác thấy dữ liệu mới (3 lớp)', '3 lớp' in meta and '2026-2027' in meta, meta)
        pv.evaluate("goTo('tracuu')"); pv.wait_for_timeout(500)
        check('trang tra cứu có dữ liệu', 'Nguyễn Văn An' in pv.inner_text('#content') or '10A1' in pv.inner_text('#content'))
        pv.evaluate("goTo('trunglich')"); pv.wait_for_timeout(300)
        pv.screenshot(path='build/shot-mobile.png')
        w = pv.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        check('điện thoại 390px không tràn ngang', w)

        # Xung đột: admin A mở bản cũ, admin B công bố trước
        pg.evaluate("()=>{ store['2026-2027___Học kỳ 1'].classes.push('12A1'); store['2026-2027___Học kỳ 1'].scheduleCurrent['12A1']=[{thu:'Hai',tiet:3,mon:'Lý',gv:'Phạm Văn Dũng'}]; }")
        st, j, _ = req('POST','/api/data', dict(TEST, baseRev='force'), {'Cookie':cookie}); check('B công bố trước (force)', st==200, (st,j))
        pg.evaluate("renderPage('overview')")
        dialogs = []
        def on_dialog(d):
            dialogs.append(d.message[:40]); d.dismiss()
        pg.on('dialog', on_dialog)
        pg.click('#btnPublish'); pg.wait_for_timeout(300)
        check('xác nhận công bố hiện hộp thoại', len(dialogs)>=1)
        pg.remove_listener('dialog', on_dialog)
        def conflict_flow(d):
            dialogs.append(d.message[:40]); d.dismiss() if 'GHI ĐÈ' in d.message else d.accept()
        pg.on('dialog', conflict_flow); pg.click('#btnPublish'); pg.wait_for_timeout(1500)
        check('A bị cảnh báo xung đột phiên bản và có nút ghi đè', any(x.startswith('Có người vừa công bố') for x in dialogs), dialogs)
        st, j, _ = req('GET','/api/data'); check('xung đột không ghi đè (vẫn 3 lớp)', len(j['store']['2026-2027___Học kỳ 1']['classes'])==3, len(j['store']['2026-2027___Học kỳ 1']['classes']))
        b.close()
    check('không có lỗi JavaScript', not errors, errors[:5])
finally:
    srv.terminate()
    try: out = srv.communicate(timeout=3)[0]
    except Exception: out = ''
    print('--- log máy chủ ---'); print(out[-600:])
print('KẾT QUẢ:', 'TẤT CẢ ĐẠT' if ok else 'CÓ LỖI'); sys.exit(0 if ok else 1)
