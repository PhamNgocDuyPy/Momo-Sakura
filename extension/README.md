# MoMo Guardian - tiện ích Chrome

Tiện ích Chrome (Manifest V3) đưa lớp Guardian lên trang chat. Người dùng bôi đen tin nhắn đáng ngờ, chạm bong bóng Guardian, và thấy lớp quét hiện đè lên trang rồi thẻ kết quả. Tiện ích dùng chung backend Flow B (`POST /api/flow-b/check`, NDJSON `stage2` rồi `final`). Đây là bản minh họa cho trải nghiệm bong bóng nổi trên Android.

Stack: Vite, React, TypeScript strict, Tailwind, framer-motion. Không import từ `../web` để tránh hai bản React; giao diện được sao chép và rút gọn từ `web/src/components/guardian/`.

## Cài đặt và build

```powershell
cd extension
npm install
npm run build        # ra extension/dist
npm test             # vitest
npx tsc --noEmit
```

`npm run build` chạy `scripts/build.mjs`: `background.js` (service worker dạng module), `content.js` (một file IIFE duy nhất, CSS được nhúng vào Shadow DOM lúc chạy) và trang cài đặt `options.html`. Icon PNG nằm trong `public/icons/` (sinh lại bằng `npm run icons`).

## Nạp vào Chrome

1. Mở `chrome://extensions`, bật **Developer mode**.
2. Chọn **Load unpacked** và trỏ tới thư mục `extension/dist`.
3. Chạy backend và web dev (hai cửa sổ PowerShell riêng), theo README gốc. Backend: `cd backend`, rồi `uvicorn guardian.main:app --port 8000`. Web: `cd web`, rồi `npm run dev`.
4. Mở http://localhost:5173/demo-chat.html (trang chat giả kiểu Zalo, ba cuộc trò chuyện: T01 giả công an, T07 shipper giả, A01 bạn bè chuyển tiền cơm).
5. Bôi đen một tin nhắn, rồi chạm bong bóng Guardian hoặc nhấn **Alt+G**.

Sau khi build lại, bấm nút tải lại của tiện ích ở `chrome://extensions` và tải lại tab đang mở.

## Cách dùng

- **Bong bóng**: tự chèn trên chat.zalo.me, messenger.com, facebook.com, web.telegram.org và http://localhost. Kéo thả được, tự bám cạnh trái hoặc phải và nhớ vị trí.
- **Có đoạn được chọn**: gửi đoạn đó với `origin = EXTENSION_SELECTION`.
- **Không chọn gì**: lấy văn bản đang hiển thị trong khung nhìn (tối đa 4.000 ký tự cuối, bỏ input, textarea, script, style và phần tử ẩn) và gửi với `origin = EXTENSION_PAGE_TEXT`. Tiện ích không đọc nội dung trang trước khi người dùng thao tác.
- **Trang khác**: chuột phải vào đoạn đã chọn, chọn **Kiểm tra bằng MoMo Guardian**, hoặc nhấn Alt+G. Khi đó tiện ích được chèn vào đúng tab đó bằng `chrome.scripting` (quyền `activeTab`). Có thể đổi phím tắt ở `chrome://extensions/shortcuts`.
- **Tự động bảo vệ** (mặc định tắt, bật riêng cho từng tên miền): công tắc "Tự động: Tắt/Bật" nằm dưới bong bóng, và danh sách tên miền đã bật nằm ở trang Options. Khi bật, tiện ích theo dõi tin nhắn mới trên trang (MutationObserver), quét một lần các tin đang hiển thị, và chấm điểm ngay trong trình duyệt (`src/content/localScreen.ts`: từ khóa chuyển tiền, số tài khoản gần tên ngân hàng, link, đổi tài khoản, mạo danh cơ quan, hối thúc, phí/cọc, thu hồi đơn, trúng thưởng; so khớp không dấu). Tin đạt ngưỡng được gắn nhãn hổ phách "Guardian: nên kiểm tra" (tối đa 20 nhãn mỗi trang, không trùng). Nhãn chỉ là gợi ý, không phải kết luận, không dùng màu xanh hay chữ "an toàn". Không có gì rời khỏi trình duyệt cho tới khi bạn chạm nhãn: khi đó đúng nội dung tin đó được gửi tới Flow B với `origin = EXTENSION_SELECTION` và lớp quét hiện ra. Thử nhanh trên `demo-chat.html`: bật công tắc, rồi bấm **Mô phỏng tin nhắn mới**.
- **Esc** hoặc nút đóng sẽ đóng lớp kết quả.
- Kết quả chỉ hiển thị chữ lấy từ verdict và `ui_hints` (template tiếng Việt). Khi `ui_hints.calm_shield` bật, hiện Calm Shield rút gọn (chữ lớn, tối đa 3 bullet, banner "MoMo không bao giờ gọi điện yêu cầu bạn chuyển tiền", liên kết `tel:` tới hotline). Khi backend lỗi hoặc quá thời gian, chỉ hiện thông báo tiếng Việt, không có kết luận nào (không bao giờ hiện ALLOW).

## Cài đặt tiện ích

Mở trang Options của tiện ích (`chrome://extensions`, Details, Extension options):

- Địa chỉ backend (mặc định `http://localhost:8000`).
- Địa chỉ ứng dụng web (mặc định `http://localhost:5173`, dùng cho nút "Mở MoMo Guardian").
- Nút **Kiểm tra kết nối** gọi `GET {backend}/api/health`.
- Mục **Tự động bảo vệ**: xem, thêm và tắt các tên miền đã bật (lưu ở `chrome.storage.local`, khóa `guardianAutoProtect`).

Session id (uuid v4) và địa chỉ được lưu trong `chrome.storage.local`. Nếu đổi sang backend khác `localhost:8000`, Chrome sẽ hỏi cấp quyền truy cập địa chỉ đó (`optional_host_permissions`).

## Cấu trúc

```
src/background.ts          menu chuột phải, phím tắt, onConnect
src/background/check.ts    port "guardian-check": fetch NDJSON, chuyển stage2/final/error, timeout
src/background/trigger.ts  gửi lệnh tới tab, chèn content.js khi trang chưa có
src/content/               mount (Shadow DOM), Bubble, Overlay, ScanAnimation, ResultPanel, CalmShield, capture,
                           localScreen (chấm điểm cục bộ), autoProtect (observer + nhãn)
src/shared/                types, settings (session uuid v4), autoProtect (công tắc theo tên miền), ndjson
src/options/               trang cài đặt
```

Backend chỉ được gọi từ service worker (`host_permissions`), không từ content script, nên script của trang không thấy session id. Timeout: 10 giây chờ sự kiện đầu tiên, 20 giây chờ `final` sau `stage2`.

## CORS

Service worker gọi backend bằng `host_permissions` nên không cần cấu hình CORS ở backend. Nếu Chrome vẫn chặn (thường do đổi sang địa chỉ khác mà chưa cấp quyền), cấp quyền khi Chrome hỏi ở trang Options, hoặc thêm địa chỉ đó vào `host_permissions` trong `public/manifest.json` rồi build lại. Mục này chưa được thử trên Chrome thật.
