# HỆ THỐNG TKB — Trường THCS-THPT Nguyễn Khuyến (bản chạy trên Render)

Cập nhật 08/10/2026 · Địa chỉ: **https://thoikhoabieu-nk.onrender.com** · Mã nguồn: nhánh `render` của repo `nguyenkhuyen-hiepbinh/thoikhoabieu-nk` (nhánh `main` vẫn là bản GitHub Pages cũ, chưa bị thay đổi).

## 1. Hệ thống làm gì

Giữ nguyên giao diện và chức năng TKB hiện tại (nhập Excel, tra cứu theo lớp/giáo viên, thống kê, báo cáo trùng lịch, so sánh bản cũ/mới). Điểm mới:

| | Trước (GitHub Pages) | Nay (Render) |
|---|---|---|
| Nơi lưu TKB | Trong trình duyệt từng người (mất khi đóng/xoá), muốn chia sẻ phải gửi file HTML | Trên máy chủ, dùng chung |
| Người khác xem | Phải nhận file hoặc tự cấu hình Firebase | Chỉ cần mở **một đường dẫn** — luôn thấy bản mới nhất |
| Ai được sửa | Ai mở cũng sửa được (trên máy mình) | Chỉ người đăng nhập **mã PIN quản trị** |
| Cập nhật TKB mới | Xuất file HTML gửi lại cho mọi người | Cập nhật → bấm **Công bố TKB** → xong |

Người xem (giáo viên, học sinh) chỉ thấy: Tổng quan, Tra cứu TKB, Thống kê, Báo cáo trùng lịch. Các mục *DS Giáo viên*, *Cập nhật TKB mới*, *Cài đặt*, xuất/nhập/xoá dữ liệu chỉ hiện sau khi quản trị đăng nhập.

## 2. Quy trình cập nhật TKB mới (mỗi lần có TKB mới)

1. Mở địa chỉ trên → bấm **Đăng nhập quản trị** (góc trên bên phải) → nhập PIN.
2. Chọn đúng *Năm học* và *Học kỳ* ở thanh bên.
3. Vào **Cập nhật TKB mới** → tải file Excel → xem phần so sánh, đặt ngày áp dụng → xác nhận.
4. Kiểm tra nhanh ở *Báo cáo trùng lịch* và *Tra cứu TKB*.
5. Bấm nút **Công bố TKB** ở thanh trên (hoặc thẻ "Công bố TKB cho mọi người" ở Tổng quan). Khi nút đổi thành **Đã công bố ✓** là xong.
6. Gửi (hoặc giữ nguyên) đường dẫn cho mọi người; ai mở lại trang sẽ thấy bản mới.

Lưu ý:
- Dấu **●** trên nút Công bố = bạn có thay đổi **chưa công bố**. Đóng trang lúc này sẽ bị cảnh báo vì thay đổi chưa công bố sẽ mất.
- Nếu hai người quản trị cùng sửa, người công bố sau sẽ được hỏi trước khi ghi đè bản vừa được công bố.
- Phiên đăng nhập hết sau 8 giờ. Nhập sai PIN 5 lần sẽ bị khoá 15 phút.

## 3. VIỆC BẮT BUỘC LÀM MỘT LẦN: bật lưu trữ bền vững

Gói Render miễn phí **xoá mọi tệp khi dịch vụ khởi động lại** (xảy ra thường xuyên). Vì vậy dữ liệu TKB được lưu vào GitHub (cách đã dùng ở Cổng Một Cửa Số). Cho đến khi làm bước này, hệ thống vẫn chạy nhưng hiện cảnh báo đỏ "Máy chủ đang lưu tạm" và **TKB đã công bố có thể biến mất**.

1. GitHub → *Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token*.
2. *Repository access*: chọn **Only select repositories** → `thoikhoabieu-nk`. *Permissions → Contents*: **Read and write**. Hạn dùng: 1 năm (đặt lịch nhắc gia hạn — hết hạn là nút Công bố ngừng hoạt động).
3. Render → dịch vụ **thoikhoabieu-nk** → *Environment* → thêm biến `GITHUB_TOKEN` = token vừa tạo → *Save* (dịch vụ tự khởi động lại).
4. Mở trang, đăng nhập quản trị: cảnh báo "lưu tạm" biến mất = đã bật.

**Chọn nơi lưu dữ liệu (quan trọng về quyền riêng tư):**
- **Mặc định**: lưu tệp `dulieu.json` ở nhánh `render` của repo hiện tại. Repo này **công khai**, nên *tên giáo viên và TKB sẽ đọc được bởi bất kỳ ai biết địa chỉ GitHub* (đường dẫn `/api/data` của trang cũng công khai — đó là cách người xem tải dữ liệu).
- **Nếu muốn dữ liệu nằm trong kho riêng tư**: tạo repo **Private** mới (ví dụ `tkb-dulieu`, tick "Add a README"), cấp token cho repo đó, rồi trên Render đổi `GITHUB_REPO` = `nguyenkhuyen-hiepbinh/tkb-dulieu` và `GITHUB_BRANCH` = `main`. Không cần sửa mã.
- Dù chọn cách nào, ai có đường dẫn trang đều xem được TKB (đúng mục đích chia sẻ). Nếu cần giới hạn người xem, nên đặt sau Google Sites nội bộ của trường.

## 4. Chuyển dữ liệu từ bản cũ sang

Bản cũ lưu dữ liệu trong trình duyệt nên mình **không thấy được dữ liệu thật** của trường. Để chuyển:
1. Mở bản GitHub Pages cũ trên máy đang có dữ liệu → Tổng quan → **Xuất toàn bộ (.json)**.
2. Mở bản mới, đăng nhập quản trị → biểu tượng **Cài đặt** → **Nhập (.json)** → chọn tệp.
3. Kiểm tra lại, rồi bấm **Công bố TKB**.

## 5. Vận hành & bảo trì

| Việc | Cách làm |
|---|---|
| Đổi mã PIN | Render → *Environment* → sửa `ADMIN_PIN` → Save |
| Xem lỗi máy chủ | Render → *Logs* |
| Sao lưu | **Xuất toàn bộ (.json)** định kỳ; nếu đã bật GitHub, mỗi lần công bố là một phiên bản trong lịch sử commit (khôi phục được) |
| Cập nhật mã | Tự động triển khai đang **tắt** có chủ đích (mỗi lần công bố là một commit, bật sẽ khiến máy chủ khởi động lại ngay lúc đang dùng). Sửa mã xong bấm *Manual Deploy* |
| Dựng lại giao diện từ bản gốc | `python3 build/patch.py build/goc/index.html public/index.html` |
| Kiểm thử tự động | `python3 build/e2e.py` (cần Playwright) |
| Tên miền riêng | Render → *Settings → Custom Domains* (cần có tên miền của trường) |

## 6. Giới hạn đã biết

- **Khởi động chậm**: gói miễn phí tự ngủ sau 15 phút không ai dùng; lần mở đầu có thể chờ ~50 giây (trang hiện thanh "Đang tải…"). Muốn hết chậm cần gói trả phí.
- Dữ liệu chưa công bố chỉ nằm trong trình duyệt của quản trị (không tự lưu nháp).
- Chưa có tài khoản riêng từng người: một PIN dùng chung cho quản trị. Chưa có thông báo đẩy khi có TKB mới.
- Biểu tượng và phông chữ tải từ Google Fonts (như bản cũ) — cần Internet.

## 7. Đã kiểm thử gì

Chạy tự động 28 bước trên máy chủ thật (chế độ lưu tệp) + trình duyệt Chromium: người xem không thấy mục quản trị; gọi thẳng trang quản trị bị chuyển về Tổng quan; ghi dữ liệu khi chưa đăng nhập bị từ chối (401); Origin lạ bị chặn; PIN sai/khoá sau 5 lần; công bố rồi mở từ thiết bị khác thấy ngay; cảnh báo xung đột khi hai người công bố; dữ liệu trống bị từ chối; không lộ tệp mã nguồn; điện thoại 390px không tràn ngang; không lỗi JavaScript.

**Chưa kiểm thử:** (1) chế độ lưu bằng GitHub với token thật (chưa có token); (2) thao tác trực tiếp trên địa chỉ onrender.com sau khi triển khai; (3) nhập file Excel TKB thật của trường (chưa có tệp mẫu — luồng nhập Excel là mã gốc không đổi).
