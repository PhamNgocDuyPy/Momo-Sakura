# Requirements Document

## Introduction

MoMo Guardian (bản Web) là trợ lý thanh toán và mua sắm chạy trên trình duyệt (mobile-first), có lớp chống lừa đảo APP (Authorized Push Payment) gắn vào mọi thao tác. Màn hình chính là dashboard quản lý tài chính cá nhân. Bong bóng Guardian nổi trên mọi màn hình là điểm tương tác chính: người dùng chạm vào (hoặc hệ thống tự kiểm tra clipboard khi người dùng đã bật quyền) để mở popup có hiệu ứng quét, sau đó trợ lý hiểu nội dung, điền sẵn thao tác và kiểm tra an toàn.

Kiến trúc bám theo *MoMo Guardian — Technical Verification & Architecture Specification v2.1*:

- **Dual-Flow:** Flow A là cổng chặn đồng bộ lúc thanh toán, không gọi LLM. Flow B là copilot phân tích nội dung không tin cậy.
- **Kiểm tra VietQR ba tầng:** EMVCo nội tại, ngữ cảnh nền tảng, cold-start.
- **Tách vai LLM theo CaMeL:** Planner cho lệnh tin cậy, Quarantined Extractor cho nội dung không tin cậy.
- **AgentSpec R1–R6** do Control Plane Python thực thi.

Các thành phần cần dữ liệu MoMo, NAPAS, SIMO, GNN hoặc lịch sử ví thật chạy bằng bản Sandbox sau interface `RiskDataProvider` / `WalletDataProvider`. LLM mặc định là `MockLLM` tất định, không cần key.

Phạm vi loại trừ: tối ưu chịu tải, tích hợp MoMo/NAPAS/SIMO thật, app mobile native, Accessibility Service. Mọi số liệu latency trong tài liệu này đo trên backend chạy local với Sandbox provider và MockLLM.

## Glossary

- **Guardian_Web**: Ứng dụng web React (Vite, TypeScript) chạy trên trình duyệt, gồm dashboard, bong bóng, popup, màn chuyển tiền và trang kịch bản demo.
- **Guardian_Backend**: Dịch vụ FastAPI (Python 3.11+) đóng vai Control Plane, giữ toàn bộ quyền gọi tool.
- **Control_Plane**: Mã Python tất định trong Guardian_Backend, điều phối tool, policy và ghép verdict. LLM không có quyền gọi tool trực tiếp.
- **Dashboard**: Màn hình chính của Guardian_Web, hiển thị chi tiêu, ngân sách, giao dịch, hóa đơn, gói định kỳ và thẻ "Lá chắn".
- **Shield_Card**: Thẻ "Lá chắn" trên Dashboard, thống kê số lần kiểm tra và số verdict theo từng tier trong session hiện tại.
- **Guardian_Bubble**: Bong bóng nổi, kéo thả được, hiển thị trên mọi màn hình của Guardian_Web.
- **Guardian_Popup**: Popup mở từ Guardian_Bubble, chứa hiệu ứng quét, ô nhập/dán, nút chụp ảnh/quét QR và thẻ kết quả.
- **Scan_Animation**: Hiệu ứng radar/khiên quét hiển thị trong Guardian_Popup khi đang phân tích.
- **Transfer_Screen**: Màn chuyển tiền / VietQR mô phỏng trong Guardian_Web, gửi giao dịch qua Flow_A_Gate.
- **Clipboard_Check**: Tính năng opt-in đọc clipboard bằng Clipboard API khi mở Guardian_Popup hoặc khi tab trở lại trạng thái hiển thị.
- **Untrusted_Content**: Mọi nội dung đến từ dán, clipboard, OCR, QR, Web Share Target hoặc ảnh. Luôn được gắn nhãn UNTRUSTED.
- **Trusted_Command**: Lệnh do chính người dùng gõ vào ô lệnh của Guardian_Popup.
- **VietQR_Verifier**: Module Control_Plane thực thi tool `verify_vietqr_emvco(payload_raw)`, phân tích TLV EMVCo NAPAS 247 và CRC.
- **VietQR_Encoder**: Module tạo chuỗi payload VietQR EMVCo hợp lệ (kèm CRC) từ thông tin người nhận và số tiền.
- **QR_Result**: Kết quả của VietQR_Verifier, thuộc tập `VALID_VIETQR`, `BAD_CRC`, `FOREIGN_OR_NON_VND`, `INVALID_FORMAT`.
- **Flow_A_Gate**: Cổng chặn đồng bộ lúc thanh toán (`POST /api/flow-a/check`), chỉ dùng luật, điểm rủi ro và Risk_Memory, không gọi LLM.
- **Flow_B_Orchestrator**: Bộ điều phối phân tích Untrusted_Content (`POST /api/flow-b/check`), chạy pre-processing, Quarantined_Extractor, Policy_Engine và Verdict_Composer.
- **Decision_Tier**: Một trong `ALLOW`, `SOFT_FRICTION`, `HARD_HOLD`, xếp theo thứ tự tăng dần ALLOW < SOFT_FRICTION < HARD_HOLD.
- **Reason_Code**: Mã lý do dạng `^RC_[A-Z0-9_]{3,40}$`.
- **Reason_Code_Registry**: Module Python duy nhất khai báo toàn bộ Reason_Code.
- **Stop_Code**: Mã dừng của Policy_Engine (ví dụ `ABORT_WAIT_NAPAS_NAME_USER_CONFIRM`, `TEMPORAL_BYPASS_DETECTED_MISSING_VIETQR_CHECK`, `LAW_91_CONSENT_REQUIRED`).
- **Source_Integrity**: Giá trị trong tập `USER_TYPED`, `VALID_VIETQR_CRC`, `OCR_CONFIRMED_BY_USER`, `OCR_UNCONFIRMED`, mô tả nguồn gốc số tài khoản.
- **Name_Confirmation**: Quy trình hai bước: tra tên NAPAS chỉ-đọc cho số tài khoản từ OCR, hiển thị tên và các chữ số tách rời, người dùng chạm xác nhận.
- **Cold_Start_Case**: Giao dịch có QR hợp lệ, SIMO/GNN sạch, người nhận lần đầu và không có bằng chứng ngữ cảnh.
- **Context_Elicitation**: Bộ nút một chạm hỏi ngữ cảnh: "Mua tại cửa hàng", "Đơn hàng online", "Chuyển gấp cho người thân", "Công an hoặc cơ quan nhà nước yêu cầu".
- **Fast_Unblock**: Quy trình mở chặn nhanh (xác minh danh tính và mục đích) cho HARD_HOLD không do SIMO.
- **PII_Redactor**: Hàm `redact_pii_local` che CCCD 12 số, CMND 9 số, số điện thoại, OTP và tên người.
- **Prefilter**: Hàm `prompt_guard_cpu_score` chạy trên CPU, trả điểm nghi prompt injection trong khoảng [0, 1].
- **URL_Checker**: Module kiểm tra URL bằng heuristic, có placeholder Google Safe Browsing bật qua biến môi trường.
- **LLM_Client**: Interface gọi LLM, chọn bản cài đặt bằng `LLM_PROVIDER` thuộc `mock`, `anthropic`, `bedrock`.
- **MockLLM**: Bản cài đặt LLM_Client tất định, không cần key, là giá trị mặc định.
- **Planner**: Vai LLM đặc quyền (Privileged LLM), chỉ nhận Trusted_Command và xuất `PlannerIntent`.
- **Quarantined_Extractor**: Vai LLM cách ly, chỉ nhận Untrusted_Content đã che PII, không có tool, xuất `QuarantinedExtraction`.
- **PlannerIntent**: Schema đầu ra của Planner, intent thuộc `TRANSFER`, `SPLIT_BILL`, `SPEND_QUERY`, `CHECK_PROMO`, `SHOP_CHECK`, `CHECK_CONTENT`, kèm slot có giới hạn.
- **QuarantinedExtraction**: Schema đầu ra của Quarantined_Extractor theo spec v2.1 §7.1, mở rộng thêm `payment_request`, `receipt_items`, `listing`, `promo_claim`.
- **GuardianVerdict**: Schema verdict trả cho Guardian_Web.
- **Policy_Engine**: Module thực thi AgentSpec R1–R6 theo trigger.
- **Verdict_Composer**: Module ghép GuardianVerdict từ Reason_Code và template tiếng Việt.
- **Vietnamese_Template**: Câu văn tiếng Việt soạn sẵn gắn với Reason_Code hoặc câu hỏi System 2, không do LLM sinh.
- **Trace**: Danh sách có thứ tự các tool và stage đã chạy cho một yêu cầu, kèm thời gian.
- **Risk_Memory**: Kho `risk_memory` theo session lưu tài khoản/URL bị Flow B gắn cờ HARD_HOLD, TTL 24 giờ.
- **Risk_Data_Provider**: Interface `RiskDataProvider` gồm `name_inquiry`, `recipient_risk`, `payer_history`.
- **Wallet_Data_Provider**: Interface `WalletDataProvider` cung cấp giao dịch, danh bạ, hóa đơn, gói định kỳ, ngân sách.
- **Sandbox_Provider**: Bản cài đặt Risk_Data_Provider và Wallet_Data_Provider đọc dữ liệu từ `fixtures/`.
- **Audit_Logger**: Module ghi mỗi verdict vào `audit.jsonl`.
- **Amount_Parser**: Hàm chuẩn hóa số tiền tiếng Việt (bao gồm tiếng lóng) thành số nguyên VND.
- **Amount_Formatter**: Hàm định dạng số nguyên VND thành chuỗi hiển thị tiếng Việt (ví dụ "200.000 đ").
- **Bill_Splitter**: Module F3 chia hóa đơn.
- **Shop_Checker**: Module F4 kiểm tra tin bán hàng / link mua sắm.
- **Promo_Checker**: Module F5 đối chiếu khuyến mãi.
- **Spend_Query_Engine**: Module F6 tính chi tiêu tất định.
- **Bill_Monitor**: Module F7 phát hiện hóa đơn bất thường và gói định kỳ.
- **Calm_Shield**: Chế độ hiển thị trấn an khi phát hiện dấu hiệu thao túng hoặc đêm khuya.
- **Late_Night_Window**: Khoảng 23:00–05:00 theo giờ GMT+7.
- **Trusted_Contact**: Người thân được người dùng cấu hình trong dữ liệu sandbox để gọi nhanh.
- **Bank_Handoff**: Thao tác mở app ngân hàng bằng deep link hoặc xuất QR VietQR mã hóa lại.
- **Eval_Harness**: Script `backend/eval/run_suite.py` chạy bộ kịch bản và tính pass^k.
- **Demo_Page**: Trang "Kịch bản demo" trong Guardian_Web.
- **Flows_Doc**: Tệp `docs/FLOWS_AND_GLOSSARY.md`.

## Requirements

### Requirement 1: Dashboard quản lý tài chính

**User Story:** Là người dùng ví, tôi muốn màn hình chính cho thấy tình hình chi tiêu và an toàn, để tôi nắm được tài chính cá nhân ngay khi mở ứng dụng.

#### Acceptance Criteria

1. WHEN Guardian_Web mở màn hình chính, THE Dashboard SHALL hiển thị tổng chi tiêu theo từng danh mục của tháng hiện tại dưới dạng biểu đồ, lấy từ `GET /api/wallet/summary`.
2. THE Dashboard SHALL hiển thị từng ngân sách kèm số đã chi, hạn mức và phần trăm đã dùng.
3. WHILE phần trăm đã dùng của một ngân sách lớn hơn hoặc bằng 80% và nhỏ hơn 100%, THE Dashboard SHALL hiển thị ngân sách đó với trạng thái cảnh báo màu vàng.
4. WHILE phần trăm đã dùng của một ngân sách lớn hơn hoặc bằng 100%, THE Dashboard SHALL hiển thị ngân sách đó với trạng thái vượt hạn mức màu đỏ.
5. THE Dashboard SHALL hiển thị 10 giao dịch gần nhất theo thứ tự thời gian giảm dần.
6. THE Dashboard SHALL hiển thị danh sách hóa đơn và gói định kỳ kèm ngày đến hạn.
7. THE Shield_Card SHALL hiển thị tổng số lần kiểm tra và số verdict ALLOW, SOFT_FRICTION, HARD_HOLD trong session hiện tại.
8. WHEN một verdict mới được trả về cho Guardian_Web, THE Shield_Card SHALL cập nhật số liệu trong vòng 1 giây.
9. THE Guardian_Backend SHALL cung cấp `GET /api/health` trả trạng thái dịch vụ và tên LLM provider đang dùng.

### Requirement 2: Bong bóng Guardian và popup quét

**User Story:** Là người dùng, tôi muốn một bong bóng Guardian luôn sẵn trên mọi màn hình, để tôi kiểm tra nội dung đáng ngờ bằng một chạm.

#### Acceptance Criteria

1. THE Guardian_Web SHALL hiển thị Guardian_Bubble trên mọi màn hình trừ khi Guardian_Popup đang mở.
2. WHEN người dùng kéo Guardian_Bubble và thả ra, THE Guardian_Bubble SHALL bám vào cạnh trái hoặc phải gần nhất của khung nhìn.
3. WHEN người dùng thả Guardian_Bubble, THE Guardian_Web SHALL lưu vị trí Guardian_Bubble vào localStorage và khôi phục vị trí đó ở lần tải trang sau.
4. WHEN người dùng chạm Guardian_Bubble mà không kéo, THE Guardian_Popup SHALL mở trong vòng 100 ms.
5. WHILE Flow_B_Orchestrator hoặc OCR đang xử lý, THE Guardian_Popup SHALL hiển thị Scan_Animation.
6. THE Guardian_Popup SHALL cung cấp ô dán nội dung, ô gõ lệnh, nút chọn/chụp ảnh và nút quét QR bằng camera.
7. WHEN người dùng đóng Guardian_Popup, THE Guardian_Web SHALL hiển thị lại Guardian_Bubble tại vị trí đã lưu.

### Requirement 3: Điểm vào nội dung và Clipboard_Check opt-in

**User Story:** Là người dùng, tôi muốn đưa nội dung vào Guardian bằng nhiều cách mà vẫn giữ quyền riêng tư, để việc kiểm tra tiện mà không bị theo dõi clipboard.

#### Acceptance Criteria

1. THE Guardian_Web SHALL đặt Clipboard_Check ở trạng thái tắt cho đến khi người dùng bật trong Guardian_Popup.
2. WHILE Clipboard_Check đang bật, WHEN Guardian_Popup mở hoặc tab chuyển sang trạng thái hiển thị, THE Guardian_Web SHALL đọc clipboard đúng một lần cho sự kiện đó.
3. THE Guardian_Web SHALL đọc clipboard chỉ tại các sự kiện mở Guardian_Popup hoặc tab chuyển sang trạng thái hiển thị, không dùng bộ hẹn giờ định kỳ.
4. WHILE Clipboard_Check đang bật, WHEN nội dung clipboard trùng với nội dung đã kiểm tra ở lần đọc trước, THE Guardian_Web SHALL bỏ qua việc gửi lại nội dung đó.
5. IF trình duyệt từ chối quyền đọc clipboard, THEN THE Guardian_Popup SHALL hiển thị thông báo tiếng Việt và chuyển tiêu điểm vào ô dán thủ công.
6. WHEN người dùng chọn hoặc chụp ảnh, THE Guardian_Web SHALL chạy OCR tesseract.js ngôn ngữ `vie` trên trình duyệt và gửi văn bản thu được với nhãn UNTRUSTED.
7. WHEN người dùng quét QR bằng camera hoặc chọn ảnh có QR, THE Guardian_Web SHALL giải mã bằng jsQR và gửi payload thô tới Guardian_Backend với nhãn UNTRUSTED.
8. THE Guardian_Web SHALL gắn nhãn UNTRUSTED cho mọi nội dung đến từ dán, clipboard, OCR, QR và Web Share Target.
9. WHEN Guardian_Web được mở qua Web Share Target với text, URL hoặc ảnh, THE Guardian_Popup SHALL mở và đưa nội dung chia sẻ vào luồng Flow_B_Orchestrator với nhãn UNTRUSTED.

### Requirement 4: Phân tích VietQR EMVCo (Tier 1)

**User Story:** Là người dùng quét mã QR, tôi muốn biết mã có đúng chuẩn VietQR NAPAS 247 và chưa bị sửa, để tôi không chuyển tiền theo mã giả.

#### Acceptance Criteria

1. WHEN VietQR_Verifier nhận payload có Tag 00 = "01", Tag 01 thuộc {"11", "12"}, Tag 38 chứa AID `A000000727`, Tag 53 = "704", Tag 58 = "VN" và CRC hợp lệ, THE VietQR_Verifier SHALL trả QR_Result `VALID_VIETQR` kèm BIN ngân hàng, số tài khoản, số tiền (nếu có) và nội dung Tag 62.
2. THE VietQR_Verifier SHALL tính CRC-16/CCITT-FALSE (đa thức 0x1021, giá trị khởi tạo 0xFFFF) trên toàn bộ payload tính đến hết "6304".
3. IF CRC tính được khác giá trị Tag 63, THEN THE VietQR_Verifier SHALL trả QR_Result `BAD_CRC`.
4. IF payload chứa AID của hệ QR nước ngoài (PromptPay `A000000677`, PayNow, QRIS) hoặc Tag 53 khác "704", THEN THE VietQR_Verifier SHALL trả QR_Result `FOREIGN_OR_NON_VND`.
5. IF Tag 54 chứa ký tự khác chữ số (bao gồm dấu thập phân), THEN THE VietQR_Verifier SHALL trả QR_Result `INVALID_FORMAT`.
6. IF payload có cấu trúc TLV không phân tích được hoặc thiếu Tag bắt buộc, THEN THE VietQR_Verifier SHALL trả QR_Result `INVALID_FORMAT`.
7. THE VietQR_Verifier SHALL phân tích độ dài trường Tag 62 theo số Unicode code point trước.
8. IF phân tích theo code point thất bại, THEN THE VietQR_Verifier SHALL phân tích lại theo độ dài byte UTF-8 và chấp nhận kết quả chỉ khi TLV kết thúc đúng tại Tag 63 và CRC hợp lệ, kèm cờ `UTF8_BYTE_FALLBACK`.
9. WHEN payload là QR merchant kiểu cũ thiếu subtag 02 trong Tag 38, THE VietQR_Verifier SHALL dùng mã dịch vụ mặc định `QRIBFTTA` và tiếp tục kiểm tra các điều kiện còn lại.
10. THE Guardian_Backend SHALL cung cấp `POST /api/qr/verify` nhận payload thô và trả QR_Result cùng các trường đã phân tích.
11. WHEN QR_Result là `BAD_CRC`, THE Policy_Engine SHALL đặt Decision_Tier tối thiểu `HARD_HOLD` kèm `RC_VIETQR_TAMPERED_BAD_CRC`.
12. WHEN QR_Result là `FOREIGN_OR_NON_VND` hoặc `INVALID_FORMAT`, THE Policy_Engine SHALL đặt Decision_Tier tối thiểu `SOFT_FRICTION` kèm Reason_Code tương ứng trong Reason_Code_Registry.
13. THE VietQR_Verifier SHALL xử lý nội dung Tag 62 như dữ liệu thuần, không chuyển nội dung Tag 62 tới Planner.

### Requirement 5: Mã hóa VietQR và tính khứ hồi

**User Story:** Là người dùng chia hóa đơn hoặc chuyển sang app ngân hàng, tôi muốn hệ thống tạo mã VietQR đúng chuẩn, để app ngân hàng đọc được chính xác.

#### Acceptance Criteria

1. WHEN VietQR_Encoder nhận BIN ngân hàng, số tài khoản, số tiền nguyên VND và nội dung, THE VietQR_Encoder SHALL tạo payload EMVCo có Tag 00, 01, 38, 53 = "704", 54, 58 = "VN", 62 và Tag 63 chứa CRC-16/CCITT-FALSE đúng.
2. THE VietQR_Encoder SHALL tính độ dài Tag 62 sao cho VietQR_Verifier phân tích lại không cần cờ `UTF8_BYTE_FALLBACK`.
3. FOR ALL bộ (BIN hợp lệ, số tài khoản 6–19 chữ số, số tiền nguyên không âm, nội dung tối đa 25 ký tự), phân tích payload do VietQR_Encoder tạo bằng VietQR_Verifier SHALL trả `VALID_VIETQR` và đúng BIN, số tài khoản, số tiền, nội dung ban đầu (round-trip).
4. FOR ALL payload `VALID_VIETQR`, mã hóa lại các trường đã phân tích bằng VietQR_Encoder rồi phân tích lần nữa SHALL cho cùng tập trường (round-trip parse → encode → parse).
5. FOR ALL payload do VietQR_Encoder tạo, thay đổi một ký tự bất kỳ trước Tag 63 SHALL làm VietQR_Verifier trả QR_Result khác `VALID_VIETQR`.

### Requirement 6: Flow A – cổng chặn lúc thanh toán

**User Story:** Là người dùng bấm chuyển tiền, tôi muốn giao dịch được kiểm tra rủi ro ngay lập tức mà không phải chờ, để tôi được bảo vệ ở bước cuối cùng.

#### Acceptance Criteria

1. THE Guardian_Backend SHALL cung cấp `POST /api/flow-a/check` nhận BIN, số tài khoản, số tiền VND, Source_Integrity, session id và payload QR (nếu có), trả GuardianVerdict kèm `latency_ms`.
2. THE Flow_A_Gate SHALL ra quyết định chỉ từ luật tất định, dữ liệu Risk_Data_Provider và Risk_Memory, không gọi LLM_Client.
3. WHEN Flow_A_Gate xử lý một yêu cầu, THE Flow_A_Gate SHALL trả GuardianVerdict với p95 `latency_ms` dưới 200 ms đo trên bộ kịch bản Flow A với Sandbox_Provider.
4. WHEN yêu cầu có payload QR, THE Flow_A_Gate SHALL gọi VietQR_Verifier trước mọi bước kiểm tra rủi ro khác và ghi `verify_vietqr_emvco` vào Trace.
5. WHEN Risk_Data_Provider báo SIMO khớp cho người nhận, THE Flow_A_Gate SHALL trả `HARD_HOLD` kèm `RC_SIMO_OR_MULE_HIGH_RISK`, `cooling_off_seconds` = 60 và `allow_fast_unblock` = false.
6. WHEN Risk_Data_Provider báo `gnn_mule_score` lớn hơn hoặc bằng 0.85 và không có SIMO khớp, THE Flow_A_Gate SHALL trả `HARD_HOLD` kèm `RC_SIMO_OR_MULE_HIGH_RISK`, `cooling_off_seconds` = 60 và `allow_fast_unblock` = true.
7. WHEN Risk_Data_Provider báo fan-in velocity vượt ngưỡng cấu hình và không có SIMO khớp, THE Flow_A_Gate SHALL trả `HARD_HOLD` kèm `allow_fast_unblock` = true.
8. WHEN số tiền giao dịch hiện tại nằm trong [9.000.000, 10.000.000) VND và tổng giao dịch 24 giờ qua cộng giao dịch hiện tại lớn hơn hoặc bằng 20.000.000 VND, THE Flow_A_Gate SHALL đặt Decision_Tier tối thiểu `SOFT_FRICTION` kèm `RC_CIRCULAR50_STRUCTURING_RISK` và `cooling_off_seconds` = 30.
9. WHEN Risk_Data_Provider báo người nhận nằm trong vùng xám rủi ro, THE Flow_A_Gate SHALL trả `SOFT_FRICTION` kèm câu hỏi tự phản tỉnh lấy từ Vietnamese_Template.
10. WHEN người nhận có lịch sử giao dịch với người trả và không có tín hiệu rủi ro nào, THE Flow_A_Gate SHALL trả `ALLOW` kèm `RC_TRUSTED_PAYEE_HISTORY`.
11. WHEN Flow_A_Gate trả `SOFT_FRICTION`, THE Transfer_Screen SHALL hiển thị nút "Kiểm tra cùng Guardian" mở Guardian_Popup ở luồng Flow_B_Orchestrator với thông tin giao dịch đã điền sẵn.
12. THE Flow_A_Gate SHALL đính kèm ít nhất một Reason_Code vào mọi GuardianVerdict, bao gồm verdict `ALLOW`.

### Requirement 7: Fast Unblock

**User Story:** Là người dùng bị chặn do tín hiệu vận tốc hoặc điểm mule nhưng giao dịch là thật, tôi muốn có đường mở chặn nhanh, để tôi không bị kẹt vô lý.

#### Acceptance Criteria

1. WHILE GuardianVerdict có `allow_fast_unblock` = true, THE Transfer_Screen SHALL hiển thị nút "Mở chặn nhanh".
2. WHEN người dùng chạm "Mở chặn nhanh", THE Transfer_Screen SHALL yêu cầu bước xác minh danh tính sandbox và chọn mục đích giao dịch từ danh sách cố định.
3. WHEN người dùng hoàn tất Fast_Unblock, THE Flow_A_Gate SHALL đánh giá lại giao dịch và trả `SOFT_FRICTION` kèm `RC_FAST_UNBLOCK_VERIFIED` và `cooling_off_seconds` = 30.
4. WHILE GuardianVerdict có `allow_fast_unblock` = false, THE Transfer_Screen SHALL ẩn nút "Mở chặn nhanh".
5. WHEN Fast_Unblock hoàn tất, THE Audit_Logger SHALL ghi bản ghi gồm Reason_Code ban đầu, mục đích đã chọn và thời điểm mở chặn.

### Requirement 8: Cold-start và Context Elicitation (Tier 3)

**User Story:** Là người dùng chuyển tiền cho người nhận mới, tôi muốn Guardian trung thực khi chưa đủ bằng chứng, để tôi không tin nhầm vào nhãn "an toàn".

#### Acceptance Criteria

1. THE Verdict_Composer SHALL loại mọi chuỗi hiển thị chứa cụm "100% an toàn" hoặc "100% Safe" khỏi GuardianVerdict.
2. WHEN giao dịch là Cold_Start_Case, THE Flow_A_Gate SHALL trả `SOFT_FRICTION` kèm `RC_COLD_START_NEEDS_CONTEXT`.
3. WHEN GuardianVerdict chứa `RC_COLD_START_NEEDS_CONTEXT`, THE Guardian_Web SHALL hiển thị bốn nút Context_Elicitation và lời mời tùy chọn chia sẻ ảnh chụp đoạn chat.
4. WHEN người dùng chọn "Mua tại cửa hàng", THE Flow_A_Gate SHALL trả `ALLOW` kèm `RC_CONTEXT_IN_STORE_DECLARED`.
5. WHEN người dùng chọn "Đơn hàng online", THE Guardian_Web SHALL hiển thị gợi ý thanh toán an toàn của Shop_Checker và giữ Decision_Tier `SOFT_FRICTION`.
6. WHEN người dùng chọn "Chuyển gấp cho người thân", THE Verdict_Composer SHALL trả `SOFT_FRICTION` kèm tối đa 2 câu hỏi System 2 của playbook `DEEPFAKE_RELATIVE_EMERGENCY` lấy từ Vietnamese_Template.
7. WHEN người dùng chọn "Công an hoặc cơ quan nhà nước yêu cầu", THE Verdict_Composer SHALL trả `SOFT_FRICTION` kèm tối đa 2 câu hỏi System 2 của playbook `IMPERSONATE_AUTHORITY_VNEID`, `cooling_off_seconds` = 60 và bật Calm_Shield.
8. WHEN người dùng chia sẻ ảnh chụp đoạn chat từ màn Context_Elicitation, THE Guardian_Web SHALL gửi văn bản OCR tới Flow_B_Orchestrator với nhãn UNTRUSTED và liên kết kết quả với giao dịch đang chờ.

### Requirement 9: Xác nhận tên NAPAS hai bước cho số tài khoản OCR (R2)

**User Story:** Là người dùng chụp ảnh số tài khoản, tôi muốn xác nhận tên người nhận trước khi tra rủi ro, để lỗi OCR một chữ số không dẫn tới chuyển nhầm người.

#### Acceptance Criteria

1. WHEN số tài khoản được trích từ OCR, THE Control_Plane SHALL gán Source_Integrity = `OCR_UNCONFIRMED`.
2. WHILE Source_Integrity = `OCR_UNCONFIRMED`, THE Control_Plane SHALL gọi chỉ `Risk_Data_Provider.name_inquiry` ở chế độ chỉ-đọc cho số tài khoản đó.
3. WHEN `name_inquiry` trả tên, THE Guardian_Web SHALL hiển thị tên người nhận và số tài khoản với các chữ số tách rời bằng khoảng trắng.
4. WHEN người dùng chạm xác nhận tên, THE Control_Plane SHALL chuyển Source_Integrity sang `OCR_CONFIRMED_BY_USER`.
5. IF `lookup_recipient_risk_and_simo` được gọi với Source_Integrity = `OCR_UNCONFIRMED`, THEN THE Control_Plane SHALL hủy lời gọi và trả `UNCONFIRMED_ACCOUNT_ABORTED`.
6. IF Policy_Engine phát hiện bước tra rủi ro được yêu cầu khi Source_Integrity = `OCR_UNCONFIRMED`, THEN THE Policy_Engine SHALL dừng với Stop_Code `ABORT_WAIT_NAPAS_NAME_USER_CONFIRM`.
7. WHEN số tài khoản đến từ OCR, THE Verdict_Composer SHALL đặt `requires_user_account_confirm` = true trong GuardianVerdict.
8. IF người dùng từ chối tên hiển thị, THEN THE Guardian_Web SHALL cho phép sửa số tài khoản và chạy lại `name_inquiry`.

### Requirement 10: Che PII trước khi gọi LLM (R1)

**User Story:** Là người dùng, tôi muốn dữ liệu cá nhân trong nội dung dán được che trước khi gửi cho AI, để thông tin của tôi không bị lộ.

#### Acceptance Criteria

1. WHEN Flow_B_Orchestrator chuẩn bị gọi Quarantined_Extractor, THE PII_Redactor SHALL thay mọi dãy 12 chữ số dạng CCCD, 9 chữ số dạng CMND, số điện thoại Việt Nam, mã OTP và tên người bằng token che có loại tương ứng.
2. IF văn bản gửi tới LLM_Client còn chứa mẫu CCCD 12 số hoặc số điện thoại sau bước che, THEN THE Policy_Engine SHALL chặn lời gọi LLM và ghi Reason_Code `RC_PII_EGRESS_BLOCKED` vào audit.
3. FOR ALL văn bản đầu vào, áp dụng PII_Redactor hai lần SHALL cho kết quả giống áp dụng một lần (idempotence).
4. FOR ALL văn bản đầu vào chứa mẫu CCCD hoặc số điện thoại, đầu ra của PII_Redactor SHALL không chứa chuỗi chữ số gốc của mẫu đó.
5. THE PII_Redactor SHALL giữ nguyên số tài khoản ngân hàng 6–19 chữ số đi kèm ngữ cảnh "stk", "số tài khoản" hoặc tên ngân hàng để phục vụ điền sẵn giao dịch.
6. THE PII_Redactor SHALL chạy cục bộ trong Guardian_Backend, không gọi dịch vụ bên ngoài.

### Requirement 11: CPU pre-filter và kiểm tra URL

**User Story:** Là người dùng, tôi muốn tín hiệu tất định hiện ra ngay cả khi AI chậm, để tôi được cảnh báo sớm về liên kết lừa đảo.

#### Acceptance Criteria

1. WHEN Flow_B_Orchestrator nhận Untrusted_Content, THE Prefilter SHALL trả `prompt_guard_cpu_score` trong vòng 20 ms cho văn bản tối đa 4.000 ký tự.
2. THE Prefilter SHALL chạy song song với bước gọi Quarantined_Extractor.
3. WHEN `prompt_guard_cpu_score` lớn hơn hoặc bằng 0.85, THE Policy_Engine SHALL nâng Decision_Tier tối thiểu lên `SOFT_FRICTION` kèm `RC_SUSPECT_INJECTION_REVIEW`.
4. THE Policy_Engine SHALL dùng `prompt_guard_cpu_score` chỉ để nâng Decision_Tier tối đa tới `SOFT_FRICTION`.
5. WHEN Untrusted_Content chứa URL, THE URL_Checker SHALL trả danh sách domain đã chuẩn hóa và cờ heuristic (domain giả mạo thương hiệu/cơ quan, TLD rủi ro, link tải APK, punycode).
6. WHEN URL_Checker phát hiện link tải APK hoặc domain giả mạo cơ quan nhà nước, THE Policy_Engine SHALL đặt Decision_Tier tối thiểu `HARD_HOLD` kèm `RC_UNOFFICIAL_APK_PHISHING`.
7. WHERE biến môi trường khóa Google Safe Browsing được cấu hình, THE URL_Checker SHALL tra thêm Google Safe Browsing và gộp kết quả vào cờ heuristic.
8. THE Guardian_Backend SHALL cung cấp `POST /api/precheck` trả văn bản đã che PII, `prompt_guard_cpu_score` và kết quả URL_Checker.

### Requirement 12: LLM_Client và lựa chọn provider

**User Story:** Là thành viên team, tôi muốn đổi LLM bằng biến môi trường, để demo chạy được không cần key và vẫn nối được LLM thật.

#### Acceptance Criteria

1. THE LLM_Client SHALL chọn bản cài đặt theo biến môi trường `LLM_PROVIDER` với giá trị `mock`, `anthropic` hoặc `bedrock`, mặc định `mock`.
2. FOR ALL đầu vào, MockLLM SHALL trả cùng một đầu ra cho cùng một đầu vào qua các lần gọi (tất định).
3. WHERE `LLM_PROVIDER` = `anthropic`, THE LLM_Client SHALL ép đầu ra theo schema qua tool-use và giới hạn đầu ra tối đa 280 token.
4. WHERE `LLM_PROVIDER` = `anthropic`, IF `stop_reason` cho thấy từ chối, cắt cụt hoặc không gọi tool schema, THEN THE LLM_Client SHALL trả `scam_playbook` = `UNKNOWN_SUSPICIOUS`.
5. IF `LLM_PROVIDER` = `anthropic` và `ANTHROPIC_API_KEY` chưa được cấu hình, THEN THE Guardian_Backend SHALL dừng khởi động và in thông báo nêu tên biến còn thiếu.
6. WHERE `LLM_PROVIDER` = `bedrock`, THE LLM_Client SHALL trả lỗi "provider chưa được cài đặt" và Flow_B_Orchestrator SHALL dùng kết quả fallback của Stage 2.
7. THE Guardian_Backend SHALL đọc cấu hình từ `.env`, và repo SHALL có `.env.example` liệt kê mọi biến cấu hình mà không chứa giá trị khóa thật.

### Requirement 13: Quarantined_Extractor và schema QuarantinedExtraction

**User Story:** Là kỹ sư bảo mật, tôi muốn AI đọc nội dung không tin cậy chỉ xuất dữ liệu có cấu trúc giới hạn, để nội dung độc hại không điều khiển được hệ thống.

#### Acceptance Criteria

1. THE Control_Plane SHALL chuyển Untrusted_Content chỉ tới Quarantined_Extractor.
2. THE Quarantined_Extractor SHALL chạy không có quyền gọi tool nào.
3. THE QuarantinedExtraction SHALL có `reasoning_summary` là trường đầu tiên, chuỗi tối đa 400 ký tự.
4. THE QuarantinedExtraction SHALL có `scam_playbook` thuộc enum `NONE_DETECTED`, `IMPERSONATE_AUTHORITY_VNEID`, `FAKE_SHIPPER_RECALL`, `C2C_DEPOSIT_OR_FAKE_RECEIPT`, `TASK_SCAM_JOB_ONLINE`, `INVESTMENT_ROMANCE_PIG_BUTCHERING`, `DEEPFAKE_RELATIVE_EMERGENCY`, `PHISHING_LINK_OR_APK_MALWARE`, `UNKNOWN_SUSPICIOUS`.
5. THE QuarantinedExtraction SHALL có `manipulation_cues` là mảng tối đa 6 phần tử thuộc enum `URGENCY_TIME_PRESSURE`, `SECRECY_DO_NOT_TELL_ANYONE`, `COACHING_WHAT_TO_TELL_BANK`, `UPFRONT_DEPOSIT_OR_UNLOCK_FEE`, `GUARANTEED_HIGH_RETURN`, `SCREEN_SHARE_OR_REMOTE_APP`, `SPLIT_TRANSFER_UNDER_10M`.
6. THE QuarantinedExtraction SHALL có `extracted_entities` gồm `bank_bin_or_name` (chuỗi hoặc null, tối đa 40), `account_digits_raw` (chuỗi hoặc null, mẫu `^[0-9]{6,19}$`), `amount_vnd` (số nguyên hoặc null, tối thiểu 0) và `urls_redacted_domains` (mảng tối đa 5 chuỗi, mỗi chuỗi tối đa 120).
7. THE QuarantinedExtraction SHALL có `contains_prompt_injection` (boolean) và `confidence_level` thuộc `LOW`, `MEDIUM`, `HIGH`.
8. THE QuarantinedExtraction SHALL có các trường mở rộng tùy chọn `payment_request`, `receipt_items`, `listing`, `promo_claim`, mỗi trường chỉ chứa enum, số nguyên và chuỗi có `max_length`.
9. THE QuarantinedExtraction SHALL khai báo Pydantic `extra="forbid"` ở mọi model lồng nhau.
10. IF đầu ra của Quarantined_Extractor không hợp lệ theo schema, THEN THE Control_Plane SHALL thay bằng QuarantinedExtraction có `scam_playbook` = `UNKNOWN_SUSPICIOUS` và Policy_Engine SHALL đặt Decision_Tier tối thiểu `SOFT_FRICTION` kèm `RC_LLM_OUTPUT_INVALID`.
11. FOR ALL QuarantinedExtraction hợp lệ, serialize sang JSON rồi parse lại SHALL cho đối tượng bằng đối tượng ban đầu (round-trip).
12. WHEN Untrusted_Content chứa tiếng lóng số tiền ("2 lít", "5 xị", "1 củ", "200k", "1tr5"), THE MockLLM SHALL điền `extracted_entities.amount_vnd` bằng giá trị Amount_Parser trả về cho cụm đó.

### Requirement 14: Planner và schema PlannerIntent

**User Story:** Là người dùng, tôi muốn gõ lệnh tự nhiên để trợ lý làm việc, để tôi thao tác nhanh mà không phải điền form.

#### Acceptance Criteria

1. THE Control_Plane SHALL chuyển tới Planner chỉ Trusted_Command.
2. THE Control_Plane SHALL loại toàn bộ Untrusted_Content khỏi đầu vào của Planner.
3. THE PlannerIntent SHALL có `intent` thuộc enum `TRANSFER`, `SPLIT_BILL`, `SPEND_QUERY`, `CHECK_PROMO`, `SHOP_CHECK`, `CHECK_CONTENT`, `UNKNOWN`.
4. THE PlannerIntent SHALL chỉ chứa slot kiểu enum, số nguyên hoặc chuỗi có `max_length`, và khai báo Pydantic `extra="forbid"`.
5. IF đầu ra của Planner không hợp lệ theo schema, THEN THE Control_Plane SHALL coi intent là `UNKNOWN` và Guardian_Popup SHALL hiển thị Vietnamese_Template yêu cầu người dùng diễn đạt lại.
6. FOR ALL PlannerIntent hợp lệ, serialize sang JSON rồi parse lại SHALL cho đối tượng bằng đối tượng ban đầu (round-trip).

### Requirement 15: Policy_Engine thực thi AgentSpec R1–R6

**User Story:** Là kỹ sư bảo mật, tôi muốn các luật an toàn được thực thi bằng code tất định, để AI không thể vượt qua hay hạ mức chặn.

#### Acceptance Criteria

1. IF có yêu cầu lưu bằng chứng khi `explicit_consent_flag` khác true, THEN THE Policy_Engine SHALL chặn thao tác lưu với Stop_Code `LAW_91_CONSENT_REQUIRED` (R1).
2. WHEN `contains_prompt_injection` = true hoặc Control_Plane phát hiện hijack control plane, THE Policy_Engine SHALL trả `HARD_HOLD` kèm `RC_PROMPT_INJECTION_BLOCKED` và `cooling_off_seconds` = 60 (R3 mức cứng).
3. WHEN Risk_Data_Provider báo SIMO khớp hoặc `gnn_mule_score` lớn hơn hoặc bằng 0.85, THE Policy_Engine SHALL trả `HARD_HOLD` kèm `RC_SIMO_OR_MULE_HIGH_RISK` và `cooling_off_seconds` = 60 bất kể Decision_Tier do LLM đề xuất (R4).
4. WHEN `manipulation_cues` chứa `SPLIT_TRANSFER_UNDER_10M`, hoặc số tiền hiện tại trong [9.000.000, 10.000.000) VND và tổng 24 giờ cộng hiện tại lớn hơn hoặc bằng 20.000.000 VND, THE Policy_Engine SHALL đặt Decision_Tier tối thiểu `SOFT_FRICTION` kèm `RC_CIRCULAR50_STRUCTURING_RISK` và `cooling_off_seconds` = 30 (R5).
5. IF yêu cầu có payload QR và Trace không chứa `verify_vietqr_emvco` trước bước ghép verdict, THEN THE Policy_Engine SHALL dừng với Stop_Code `TEMPORAL_BYPASS_DETECTED_MISSING_VIETQR_CHECK` và trả `HARD_HOLD` (R6).
6. FOR ALL tổ hợp tín hiệu tất định và Decision_Tier do LLM đề xuất, Decision_Tier cuối cùng SHALL lớn hơn hoặc bằng mọi Decision_Tier tối thiểu do luật tất định đặt ra (LLM không hạ cấp được).
7. FOR ALL tổ hợp tín hiệu, Decision_Tier cuối cùng SHALL bằng `HARD_HOLD` chỉ khi có ít nhất một nguồn HARD hợp lệ: `contains_prompt_injection`, hijack control plane, SIMO khớp, `gnn_mule_score` lớn hơn hoặc bằng 0.85, fan-in velocity vượt ngưỡng (Requirement 6.6, 6.7), `BAD_CRC`, URL APK/giả mạo cơ quan, R6, Risk_Memory, khuyến mãi giả hoặc nhân danh MoMo do Promo_Checker phát hiện (Requirement 24.3, 24.4), hoặc `scam_playbook` được ánh xạ HARD; `prompt_guard_cpu_score` đơn lẻ, `manipulation_cues` đơn lẻ và heuristic dự phòng khi LLM timeout hoặc lỗi SHALL không thuộc nguồn HARD hợp lệ.
8. WHEN `scam_playbook` khác `NONE_DETECTED`, THE Policy_Engine SHALL đặt Decision_Tier tối thiểu `SOFT_FRICTION`.
9. THE Policy_Engine SHALL ghi danh sách luật đã kích hoạt (R1–R6) vào Trace của mỗi yêu cầu.
10. WHEN cùng một đầu vào được đánh giá nhiều lần với MockLLM, THE Policy_Engine SHALL trả cùng Decision_Tier và cùng tập Reason_Code.
11. WHEN `manipulation_cues` khác rỗng và `scam_playbook` không thuộc nhóm playbook được ánh xạ HARD, THE Policy_Engine SHALL đặt Decision_Tier tối thiểu do `manipulation_cues` tạo ra tối đa bằng `SOFT_FRICTION`.

### Requirement 16: Verdict_Composer và schema GuardianVerdict

**User Story:** Là người dùng, tôi muốn lời giải thích rõ ràng, nhất quán bằng tiếng Việt, để tôi hiểu vì sao giao dịch bị cảnh báo.

#### Acceptance Criteria

1. THE GuardianVerdict SHALL có `decision_tier` thuộc `ALLOW`, `SOFT_FRICTION`, `HARD_HOLD`.
2. THE GuardianVerdict SHALL có `reason_codes` gồm 1 đến 6 phần tử, mỗi phần tử khớp mẫu `^RC_[A-Z0-9_]{3,40}$` và có trong Reason_Code_Registry.
3. THE GuardianVerdict SHALL có `evidence_bullets` tối đa 4 chuỗi, mỗi chuỗi tối đa 160 ký tự, và `system2_check_questions` tối đa 2 chuỗi, mỗi chuỗi tối đa 180 ký tự.
4. THE GuardianVerdict SHALL có `cooling_off_seconds` thuộc {0, 15, 30, 60, 300}, `requires_user_account_confirm` (boolean) và `allow_fast_unblock` (boolean).
5. THE Verdict_Composer SHALL lấy mọi `evidence_bullets` và `system2_check_questions` từ Vietnamese_Template gắn với Reason_Code hoặc playbook.
6. THE Verdict_Composer SHALL giữ `reasoning_summary` chỉ trong audit, không đưa vào GuardianVerdict trả cho Guardian_Web.
7. FOR ALL QuarantinedExtraction chứa chuỗi bất kỳ trong `reasoning_summary`, `bank_bin_or_name` hoặc các trường chuỗi mở rộng, GuardianVerdict SHALL không chứa chuỗi đó trong `evidence_bullets` hoặc `system2_check_questions`.
8. FOR ALL GuardianVerdict hợp lệ, serialize sang JSON rồi parse lại SHALL cho đối tượng bằng đối tượng ban đầu (round-trip).
9. WHEN số tiền được hiển thị trong verdict hoặc màn điền sẵn, THE Guardian_Web SHALL định dạng bằng Amount_Formatter.

### Requirement 17: Flow_B_Orchestrator, progressive disclosure và circuit breaker

**User Story:** Là người dùng dán nội dung đáng ngờ, tôi muốn thấy kết quả từng bước và không bao giờ bị treo, để tôi quyết định kịp thời.

#### Acceptance Criteria

1. THE Guardian_Backend SHALL cung cấp `POST /api/flow-b/check` trả GuardianVerdict, Trace, danh sách luật đã kích hoạt và thời gian từng stage.
2. WHEN người dùng gửi nội dung trong Guardian_Popup, THE Guardian_Web SHALL hiển thị Stage 1 (xác nhận đã nhận, thông điệp trấn an cục bộ) trong vòng 100 ms mà không chờ Guardian_Backend.
3. WHEN Flow_B_Orchestrator nhận yêu cầu, THE Flow_B_Orchestrator SHALL trả kết quả Stage 2 (VietQR_Verifier, URL_Checker, SIMO/GNN sandbox, Prefilter) trong vòng 250 ms.
4. WHEN Stage 2 có QR_Result `BAD_CRC` hoặc SIMO khớp, THE Guardian_Popup SHALL hiển thị cảnh báo đỏ ngay khi nhận Stage 2, trước khi có Stage 3.
5. WHEN Quarantined_Extractor trả kết quả trong vòng 4.000 ms, THE Flow_B_Orchestrator SHALL trả Stage 3 là GuardianVerdict đầy đủ từ Policy_Engine và Verdict_Composer.
6. IF Quarantined_Extractor chưa trả kết quả sau 4.000 ms, THEN THE Flow_B_Orchestrator SHALL ngắt lời gọi LLM và trả GuardianVerdict ghép từ bằng chứng Stage 2 và heuristic từ khóa cục bộ, kèm `RC_LLM_TIMEOUT_FALLBACK`.
7. THE Flow_B_Orchestrator SHALL chạy các bước theo thứ tự: (1) gắn nhãn UNTRUSTED, (2) PII_Redactor, (3) nhóm tất định Prefilter, URL_Checker, VietQR_Verifier, (4) Quarantined_Extractor, (5) Policy_Engine, (6) Verdict_Composer, (7) Audit_Logger; Prefilter được phép chạy song song với bước (4).
8. WHEN Untrusted_Content là payload QR có Tag 62 chứa chỉ dẫn dạng lệnh, THE Flow_B_Orchestrator SHALL xử lý Tag 62 như dữ liệu và Trace SHALL không chứa lời gọi tool nào ngoài danh sách tool cho phép của Control_Plane.
9. WHEN Untrusted_Content yêu cầu đổi tài khoản nhận so với tài khoản người dùng đã nhập, THE Verdict_Composer SHALL đặt `requires_user_account_confirm` = true và giữ tài khoản do người dùng nhập.
10. WHEN Guardian_Popup nhận GuardianVerdict, THE Guardian_Popup SHALL hiển thị thẻ kết quả và panel "Guardian đã quyết định thế nào" liệt kê các bước Trace, luật đã kích hoạt và thời gian từng stage.
11. IF Quarantined_Extractor timeout hoặc LLM_Client lỗi, THEN THE Flow_B_Orchestrator SHALL giới hạn Decision_Tier do heuristic dự phòng tạo ra tối đa ở `SOFT_FRICTION` và chỉ đặt `HARD_HOLD` khi bằng chứng Stage 2 chứa nguồn HARD hợp lệ theo Requirement 15.7.

### Requirement 18: Risk_Memory dùng chung Flow B ↔ Flow A

**User Story:** Là người dùng vừa được cảnh báo về một tài khoản, tôi muốn Guardian nhớ cảnh báo đó khi tôi chuyển tiền sau, để kẻ gian không lợi dụng việc tôi bỏ qua popup.

#### Acceptance Criteria

1. WHEN Flow_B_Orchestrator trả `HARD_HOLD` có tài khoản hoặc domain URL trong `extracted_entities`, THE Risk_Memory SHALL lưu khóa (session id, BIN + số tài khoản đã chuẩn hóa hoặc domain đã chuẩn hóa) kèm Reason_Code và thời điểm hết hạn sau 24 giờ.
2. WHEN Flow_A_Gate kiểm tra giao dịch có tài khoản nằm trong Risk_Memory chưa hết hạn của cùng session, THE Flow_A_Gate SHALL trả `HARD_HOLD` kèm `RC_FLOWB_FLAGGED_RECENTLY`.
3. WHEN mục Risk_Memory quá 24 giờ, THE Risk_Memory SHALL bỏ qua mục đó khi Flow_A_Gate tra cứu.
4. THE Risk_Memory SHALL tách dữ liệu theo session id, mục của session này không ảnh hưởng session khác.
5. FOR ALL tài khoản được ghi vào Risk_Memory, tra cứu trong cùng session trước khi hết hạn SHALL trả mục đã ghi (round-trip ghi → đọc).
6. FOR ALL tài khoản, ghi cùng một cờ vào Risk_Memory nhiều lần SHALL cho cùng kết quả tra cứu như ghi một lần (idempotence).

### Requirement 19: Chuẩn hóa số tiền tiếng Việt

**User Story:** Là người dùng hay viết tắt, tôi muốn Guardian hiểu "2 lít", "5 xị", "1 củ", để số tiền điền sẵn đúng ý tôi.

#### Acceptance Criteria

1. WHEN Amount_Parser nhận "2 lít", THE Amount_Parser SHALL trả 200000.
2. WHEN Amount_Parser nhận "5 xị", THE Amount_Parser SHALL trả 500000.
3. WHEN Amount_Parser nhận "1 củ", THE Amount_Parser SHALL trả 1000000.
4. WHEN Amount_Parser nhận chuỗi dạng "<số>k", "<số>tr", "<số>tr<số>" hoặc "<số>.<số>tr", THE Amount_Parser SHALL trả số nguyên VND tương ứng (ví dụ "200k" → 200000, "1tr5" → 1500000, "1.5tr" → 1500000).
5. IF chuỗi số tiền không khớp mẫu nào, THEN THE Amount_Parser SHALL trả null.
6. THE Amount_Formatter SHALL định dạng số nguyên VND với dấu chấm phân cách hàng nghìn và hậu tố " đ" (ví dụ 200000 → "200.000 đ").
7. FOR ALL số nguyên VND không âm, Amount_Parser áp dụng lên đầu ra của Amount_Formatter SHALL trả lại số ban đầu (round-trip).

### Requirement 20: F1 "Dán là chuyển"

**User Story:** Là người dùng nhận tin nhắn đòi tiền, tôi muốn dán tin vào Guardian để có ngay giao dịch điền sẵn đã kiểm tra, để tôi không phải gõ lại số tài khoản.

#### Acceptance Criteria

1. WHEN người dùng dán đoạn chat chứa yêu cầu chuyển tiền (ví dụ "ck t 2 lít vào stk 0123456789 VCB nha, tiền cơm"), THE Flow_B_Orchestrator SHALL trả `payment_request` gồm BIN ngân hàng, số tài khoản, số tiền VND và nội dung chuyển.
2. WHEN `payment_request` có đủ BIN, số tài khoản và số tiền, THE Guardian_Popup SHALL hiển thị nút "Chuyển ngay".
3. WHEN người dùng chạm "Chuyển ngay", THE Guardian_Web SHALL mở Transfer_Screen điền sẵn thông tin và yêu cầu người dùng xác nhận hai bước trước khi gửi tới Flow_A_Gate.
4. WHEN giao dịch điền sẵn từ nội dung dán được gửi tới Flow_A_Gate, THE Transfer_Screen SHALL gửi Source_Integrity tương ứng với nguồn số tài khoản (`OCR_UNCONFIRMED` hoặc `OCR_CONFIRMED_BY_USER` với OCR, `USER_TYPED` sau khi người dùng xác nhận số đã dán).
5. WHILE GuardianVerdict của nội dung dán là `HARD_HOLD`, THE Guardian_Popup SHALL ẩn nút "Chuyển ngay".
6. IF `payment_request` thiếu BIN, số tài khoản hoặc số tiền, THEN THE Guardian_Popup SHALL hiển thị các trường còn thiếu để người dùng tự điền.

### Requirement 21: F2 lệnh bằng câu nói

**User Story:** Là người dùng, tôi muốn gõ "chuyển 200k cho Minh tiền cà phê", để trợ lý tìm đúng người và điền sẵn giao dịch.

#### Acceptance Criteria

1. WHEN người dùng gõ Trusted_Command chuyển tiền, THE Planner SHALL trả PlannerIntent `TRANSFER` với slot tên người nhận (tối đa 40 ký tự), `amount_vnd` và nội dung (tối đa 60 ký tự).
2. WHEN tên người nhận khớp đúng một liên hệ trong danh bạ Wallet_Data_Provider, THE Guardian_Web SHALL mở Transfer_Screen điền sẵn tài khoản của liên hệ đó.
3. WHEN tên người nhận khớp từ hai liên hệ trở lên, THE Guardian_Popup SHALL hiển thị danh sách liên hệ khớp để người dùng chọn.
4. IF tên người nhận không khớp liên hệ nào, THEN THE Guardian_Popup SHALL hiển thị Vietnamese_Template báo không tìm thấy và đề nghị nhập số tài khoản.
5. IF Trusted_Command thiếu số tiền, THEN THE Guardian_Popup SHALL hỏi lại số tiền trước khi mở Transfer_Screen.
6. WHEN Transfer_Screen được điền sẵn từ F2, THE Transfer_Screen SHALL gửi giao dịch qua Flow_A_Gate.

### Requirement 22: F3 chia hóa đơn

**User Story:** Là người đi ăn nhóm, tôi muốn chụp hóa đơn và chia tiền cho từng người kèm mã QR, để mọi người trả đúng phần của mình.

#### Acceptance Criteria

1. WHEN người dùng chụp ảnh hóa đơn ở chế độ chia hóa đơn, THE Flow_B_Orchestrator SHALL trả `receipt_items` gồm tên món (tối đa 60 ký tự), số lượng và đơn giá nguyên VND, kèm tổng hóa đơn.
2. THE Bill_Splitter SHALL cho người dùng gán từng món cho một hoặc nhiều người, hoặc chọn chia đều.
3. FOR ALL cách gán món và chia đều, tổng số tiền phân cho mọi người SHALL bằng đúng tổng hóa đơn, không lệch 1 đồng (invariant).
4. WHEN chia đều không chia hết, THE Bill_Splitter SHALL phân phần dư từng đồng theo thứ tự người tham gia cố định.
5. WHEN Bill_Splitter tạo mã QR cho từng người, THE Control_Plane SHALL tạo payload bằng VietQR_Encoder và kiểm tra bằng `verify_vietqr_emvco` trước khi hiển thị.
6. IF payload cho một người không trả `VALID_VIETQR`, THEN THE Bill_Splitter SHALL ẩn mã QR của người đó và hiển thị thông báo lỗi.
7. IF tổng các món OCR khác tổng hóa đơn OCR, THEN THE Bill_Splitter SHALL hiển thị chênh lệch và yêu cầu người dùng sửa trước khi chia.

### Requirement 23: F4 mua sắm an toàn

**User Story:** Là người mua hàng online, tôi muốn kiểm tra tin bán hoặc link trước khi đặt cọc, để tôi tránh hàng giả và lừa đặt cọc.

#### Acceptance Criteria

1. WHEN người dùng dán tin bán hàng hoặc link, THE Flow_B_Orchestrator SHALL trả `listing` gồm danh mục sản phẩm (enum), giá rao nguyên VND và cờ yêu cầu đặt cọc.
2. WHEN giá rao thấp hơn giá tham chiếu trong `fixtures/reference_prices.json` từ 40% trở lên, THE Shop_Checker SHALL thêm `RC_PRICE_TOO_GOOD_TO_BE_TRUE` và đặt Decision_Tier tối thiểu `SOFT_FRICTION`.
3. WHEN `listing` có cờ yêu cầu đặt cọc hoặc `manipulation_cues` chứa `UPFRONT_DEPOSIT_OR_UNLOCK_FEE`, THE Verdict_Composer SHALL hiển thị gợi ý thanh toán khi nhận hàng (COD) hoặc thanh toán qua kênh có bảo vệ người mua, lấy từ Vietnamese_Template.
4. WHEN `listing` có URL, THE Shop_Checker SHALL gộp kết quả URL_Checker vào verdict.
5. IF danh mục sản phẩm không có trong `fixtures/reference_prices.json`, THEN THE Shop_Checker SHALL bỏ qua bước so giá và ghi `RC_NO_REFERENCE_PRICE` vào verdict.

### Requirement 24: F5 khuyến mãi thật hay giả

**User Story:** Là người dùng nhận tin trúng thưởng, tôi muốn biết khuyến mãi có trong danh sách chính thức không, để tôi không mất phí "nhận quà".

#### Acceptance Criteria

1. WHEN người dùng dán tin khuyến mãi, THE Flow_B_Orchestrator SHALL trả `promo_claim` gồm thương hiệu (enum), mã khuyến mãi (tối đa 30 ký tự) và cờ yêu cầu trả phí.
2. WHEN `promo_claim` khớp một mục trong `fixtures/official_promos.json`, THE Promo_Checker SHALL hiển thị thông tin khuyến mãi chính thức từ fixture và Decision_Tier `ALLOW` kèm `RC_PROMO_MATCHES_OFFICIAL_LIST`.
3. WHEN `promo_claim` không khớp danh sách chính thức và có cờ yêu cầu trả phí hoặc cue `UPFRONT_DEPOSIT_OR_UNLOCK_FEE`, THE Promo_Checker SHALL đặt `HARD_HOLD` kèm `RC_FAKE_PROMO_REFUND`.
4. WHEN `promo_claim` nhân danh MoMo và không khớp danh sách chính thức, THE Promo_Checker SHALL đặt `HARD_HOLD` kèm `RC_BRAND_IMPERSONATION_MOMO`.
5. WHEN `promo_claim` không khớp danh sách chính thức và không có yêu cầu trả phí, THE Promo_Checker SHALL đặt `SOFT_FRICTION` kèm `RC_PROMO_NOT_IN_OFFICIAL_LIST`.

### Requirement 25: F6 hỏi chi tiêu

**User Story:** Là người dùng, tôi muốn hỏi "tháng này cà phê hết bao nhiêu?", để biết ngay số liệu mà không phải tự cộng.

#### Acceptance Criteria

1. WHEN người dùng gõ câu hỏi chi tiêu, THE Planner SHALL trả PlannerIntent `SPEND_QUERY` với slot `category` (enum), `period` (enum) và `metric` (enum).
2. THE Spend_Query_Engine SHALL tính kết quả bằng code tất định trên dữ liệu Wallet_Data_Provider, không thực thi truy vấn sinh từ LLM.
3. FOR ALL tổ hợp (`category`, `period`, `metric`) và tập giao dịch sandbox, kết quả của Spend_Query_Engine SHALL bằng kết quả của hàm tham chiếu lọc-và-cộng đơn giản (model-based).
4. WHEN Spend_Query_Engine trả kết quả, THE Guardian_Popup SHALL hiển thị câu trả lời từ Vietnamese_Template kèm biểu đồ nhỏ theo ngày hoặc tuần của kỳ được hỏi.
5. IF Planner trả intent khác `SPEND_QUERY` hoặc slot ngoài enum cho câu hỏi chi tiêu, THEN THE Guardian_Popup SHALL hiển thị Vietnamese_Template đề nghị hỏi lại kèm ví dụ câu hỏi.

### Requirement 26: F7 hóa đơn bất thường và gói định kỳ

**User Story:** Là người dùng, tôi muốn được nhắc khi hóa đơn tăng bất thường hoặc gói định kỳ sắp gia hạn, để tôi không mất tiền oan.

#### Acceptance Criteria

1. WHEN số tiền hóa đơn kỳ hiện tại lớn hơn hoặc bằng 130% trung bình 3 kỳ trước của cùng nhà cung cấp, THE Bill_Monitor SHALL tạo cảnh báo hóa đơn bất thường trên Dashboard kèm phần trăm tăng.
2. WHEN một gói định kỳ có ngày gia hạn trong vòng 7 ngày tới, THE Bill_Monitor SHALL tạo nhắc nhở sắp gia hạn kèm số tiền và ngày gia hạn.
3. WHEN một gói định kỳ không có lần sử dụng nào trong 30 ngày gần nhất theo dữ liệu Wallet_Data_Provider, THE Bill_Monitor SHALL tạo gợi ý xem xét hủy gói.
4. IF nhà cung cấp có ít hơn 3 kỳ hóa đơn trước đó, THEN THE Bill_Monitor SHALL bỏ qua kiểm tra hóa đơn bất thường cho nhà cung cấp đó.

### Requirement 27: Calm Shield, cooling-off và TTS

**User Story:** Là người dùng lớn tuổi đang bị hối thúc, tôi muốn giao diện bình tĩnh, chữ to và có thời gian suy nghĩ, để tôi không chuyển tiền trong lúc hoảng.

#### Acceptance Criteria

1. WHEN `manipulation_cues` chứa `URGENCY_TIME_PRESSURE` hoặc `SECRECY_DO_NOT_TELL_ANYONE`, THE Guardian_Web SHALL bật Calm_Shield.
2. WHEN Decision_Tier khác `ALLOW` và thời điểm hiện tại nằm trong Late_Night_Window, THE Guardian_Web SHALL bật Calm_Shield.
3. WHILE Calm_Shield bật, THE Guardian_Web SHALL ẩn nội dung khuyến mãi, hiển thị chữ cỡ 18–20 sp độ tương phản cao và tối đa 3 evidence bullet.
4. WHILE Calm_Shield bật, THE Guardian_Web SHALL hiển thị nút "Tạm dừng & xác minh" làm nút chính và nút tiếp tục ở dạng mờ.
5. WHILE `cooling_off_seconds` lớn hơn 0 và đồng hồ đếm ngược chưa về 0, THE Guardian_Web SHALL khóa nút tiếp tục và hiển thị thời gian còn lại.
6. WHILE GuardianVerdict có `system2_check_questions`, THE Guardian_Web SHALL khóa nút tiếp tục cho đến khi người dùng trả lời mọi câu hỏi.
7. WHEN Calm_Shield bật, THE Guardian_Web SHALL đọc evidence bullet bằng Web Speech API giọng vi-VN với tốc độ 0.8 lần bình thường.
8. IF trình duyệt không hỗ trợ giọng vi-VN, THEN THE Guardian_Web SHALL ẩn nút đọc và giữ hiển thị văn bản.
9. WHILE Calm_Shield bật, THE Guardian_Web SHALL hiển thị nút gọi `tel:` tới hotline MoMo và tới Trusted_Contact.
10. WHILE Calm_Shield bật, THE Guardian_Web SHALL hiển thị banner "MoMo không bao giờ gọi điện yêu cầu bạn chuyển tiền".

### Requirement 28: Chuyển sang app ngân hàng

**User Story:** Là người dùng đã kiểm tra xong, tôi muốn mở app ngân hàng với thông tin điền sẵn, để hoàn tất thanh toán nhanh.

#### Acceptance Criteria

1. WHEN Decision_Tier là `ALLOW` hoặc người dùng đã hoàn tất cooling-off của `SOFT_FRICTION`, THE Guardian_Web SHALL cho phép Bank_Handoff bằng deep link (nếu ngân hàng được hỗ trợ) hoặc mã QR do VietQR_Encoder tạo.
2. WHEN Guardian_Web hiển thị QR cho Bank_Handoff, THE Control_Plane SHALL kiểm tra payload bằng `verify_vietqr_emvco` và chỉ hiển thị khi kết quả là `VALID_VIETQR`.
3. WHILE Decision_Tier là `HARD_HOLD`, THE Guardian_Web SHALL vô hiệu hóa mọi deep link và xuất QR sang app ngân hàng.
4. IF Guardian_Backend nhận yêu cầu tạo QR Bank_Handoff cho giao dịch có verdict `HARD_HOLD`, THEN THE Guardian_Backend SHALL từ chối yêu cầu và ghi audit.

### Requirement 29: Audit và đồng thuận

**User Story:** Là người vận hành, tôi muốn mọi quyết định được ghi lại đầy đủ nhưng tôn trọng quyền riêng tư, để tôi truy vết được mà vẫn tuân thủ Luật 91/2025.

#### Acceptance Criteria

1. WHEN Flow_A_Gate hoặc Flow_B_Orchestrator trả GuardianVerdict, THE Audit_Logger SHALL ghi một dòng JSON vào `audit.jsonl` gồm timestamp, flow channel, Decision_Tier, Reason_Code, luật đã kích hoạt, Stop_Code (nếu có), Trace và `reasoning_summary`.
2. THE Audit_Logger SHALL ghi thêm vào `audit.jsonl` mà không sửa hoặc xóa dòng đã ghi.
3. WHILE `explicit_consent_flag` khác true, THE Audit_Logger SHALL ghi hash của nội dung thay cho văn bản hoặc ảnh gốc.
4. WHEN `explicit_consent_flag` = true, THE Audit_Logger SHALL lưu bằng chứng ở dạng đã qua PII_Redactor.
5. THE Guardian_Popup SHALL hiển thị lựa chọn đồng ý lưu bằng chứng, mặc định là không đồng ý.

### Requirement 30: Reason_Code_Registry

**User Story:** Là thành viên team, tôi muốn mọi mã lý do nằm một chỗ và có tài liệu, để không có mã "mồ côi" khi trình bày.

#### Acceptance Criteria

1. THE Reason_Code_Registry SHALL khai báo mọi Reason_Code dùng trong Guardian_Backend trong một module Python duy nhất.
2. THE Reason_Code_Registry SHALL gắn mỗi Reason_Code với Vietnamese_Template hiển thị và Decision_Tier tối thiểu.
3. FOR ALL Reason_Code trong Reason_Code_Registry, mã SHALL khớp mẫu `^RC_[A-Z0-9_]{3,40}$`.
4. FOR ALL Reason_Code trong Reason_Code_Registry, Flows_Doc SHALL chứa mã đó (kiểm tra bằng test tự động).
5. FOR ALL chuỗi dạng `RC_` xuất hiện trong mã nguồn Guardian_Backend, chuỗi đó SHALL có trong Reason_Code_Registry.

### Requirement 31: Data provider và dữ liệu sandbox

**User Story:** Là thành viên team, tôi muốn dữ liệu không khả thi đi qua interface có bản Sandbox, để sau này nối dữ liệu thật mà không sửa logic nghiệp vụ.

#### Acceptance Criteria

1. THE Risk_Data_Provider SHALL cung cấp `name_inquiry(bank_bin, account_number)`, `recipient_risk(bank_bin, account_number, amount_vnd)` trả trạng thái SIMO, `gnn_mule_score`, fan-in velocity, tuổi tài khoản, và `payer_history(payer_session_hash, bank_bin, account_number)` trả lịch sử với người nhận và tổng giao dịch 24 giờ.
2. THE Wallet_Data_Provider SHALL cung cấp giao dịch, danh bạ, hóa đơn, gói định kỳ, ngân sách và Trusted_Contact.
3. THE Sandbox_Provider SHALL đọc dữ liệu từ `fixtures/`, bao gồm `fixtures/wallet_sandbox.json` chứa khoảng 3 tháng giao dịch.
4. THE Control_Plane SHALL truy cập dữ liệu rủi ro và dữ liệu ví chỉ qua Risk_Data_Provider và Wallet_Data_Provider.
5. THE Guardian_Web SHALL đánh dấu rõ trên giao diện các kết quả đến từ Sandbox_Provider (ví dụ nhãn "Dữ liệu mô phỏng" cạnh kết quả SIMO/NAPAS).
6. THE repo SHALL có `fixtures/gen_qr.py` tạo các payload QR mẫu cho kịch bản kiểm thử (hợp lệ, sai CRC, nước ngoài, số tiền thập phân, Tag 62 có dấu, merchant kiểu cũ).

### Requirement 32: Tài liệu luồng và thuật ngữ

**User Story:** Là giám khảo hoặc thành viên mới, tôi muốn một tài liệu giải thích luồng và thuật ngữ nghiệp vụ, để tôi hiểu hệ thống mà không phải đọc code.

#### Acceptance Criteria

1. THE Flows_Doc SHALL chứa sơ đồ mermaid cho Flow A, Flow B, Risk_Memory và từng tính năng F1–F7.
2. THE Flows_Doc SHALL chứa bảng phân loại Thật / Sandbox cho từng thành phần.
3. THE Flows_Doc SHALL chứa bảng thuật ngữ nghiệp vụ (APP fraud, VietQR, EMVCo, NAPAS 247, SIMO, GNN mule, CaMeL, AgentSpec, Thông tư 50, Luật 91/2025) và danh sách mọi Reason_Code kèm ý nghĩa.
4. THE Flows_Doc SHALL chứa lộ trình mobile: Android share sheet, NotificationListener opt-in, bong bóng `SYSTEM_ALERT_WINDOW`, iOS Share Extension và lý do không dùng Accessibility Service.
5. THE Guardian_Web SHALL có PWA manifest khai báo Web Share Target nhận text, URL và ảnh.

### Requirement 33: Bộ kịch bản và eval harness

**User Story:** Là thành viên team, tôi muốn chạy toàn bộ kịch bản và có báo cáo pass^k, để chứng minh Control_Plane xử lý đúng trước buổi giới thiệu.

#### Acceptance Criteria

1. THE repo SHALL có trong `fixtures/scenarios/` một fixture cho mỗi kịch bản T01–T31 và A01–A12, mỗi fixture ghi đầu vào, flow channel, Decision_Tier mong đợi và Reason_Code mong đợi.
2. THE bộ kịch bản A01–A12 SHALL bao phủ mỗi tính năng F1–F7 bằng ít nhất một kịch bản.
3. WHEN chạy `backend/eval/run_suite.py --runs 5 --k 3`, THE Eval_Harness SHALL chạy mỗi kịch bản 5 lần và tính pass^3 = E[C(c,3)/C(5,3)], với c là số lần đạt.
4. WHEN Eval_Harness chạy xong, THE Eval_Harness SHALL ghi `eval_report.md` gồm pass^3 tổng, pass^3 theo nhóm (red-risk, injection, PII, cold-start, trợ lý) và danh sách kịch bản không đạt.
5. WHERE `LLM_PROVIDER` = `mock`, THE Eval_Harness SHALL đạt pass^3 = 100% trên toàn bộ T01–T31 và A01–A12.
6. THE Eval_Harness SHALL ghi trong `eval_report.md` câu nêu rõ kết quả trên MockLLM chỉ chứng minh Control_Plane chạy đúng và độ ổn định với LLM thật phải đo lại.
7. THE Eval_Harness SHALL ghi tên LLM provider đã dùng vào `eval_report.md`.
8. WHEN mỗi kịch bản T01–T31 chạy, THE Eval_Harness SHALL so khớp kết quả với bảng kỳ vọng ở Phụ lục A.

### Requirement 34: Trang "Kịch bản demo"

**User Story:** Là người trình bày, tôi muốn chạy từng kịch bản ngay trên giao diện, để giám khảo thấy hệ thống phản ứng thật.

#### Acceptance Criteria

1. THE Demo_Page SHALL liệt kê mọi kịch bản T01–T31 và A01–A12 kèm mô tả ngắn và kết quả mong đợi.
2. WHEN người dùng chọn "Chạy" ở một kịch bản, THE Demo_Page SHALL gửi đầu vào kịch bản qua cùng endpoint mà Guardian_Popup hoặc Transfer_Screen dùng và hiển thị GuardianVerdict thực tế.
3. WHEN người dùng chọn "Chạy tất cả", THE Demo_Page SHALL chạy lần lượt mọi kịch bản và hiển thị số kịch bản đạt trên tổng số.
4. WHEN kết quả thực tế khác kết quả mong đợi, THE Demo_Page SHALL đánh dấu kịch bản đó là không đạt và hiển thị Decision_Tier và Reason_Code thực tế cạnh giá trị mong đợi.

### Requirement 35: Tiện ích Chrome – lớp Guardian trên nền tảng khác
**User Story:** Là người dùng đang chat trên Zalo Web, Messenger hay Facebook, tôi muốn bấm vào bong bóng Guardian ngay trên trang đó và thấy lớp quét hiện đè lên khung chat, để kiểm tra tin nhắn mà không phải sao chép sang ứng dụng khác.
#### Acceptance Criteria
1. THE Guardian_Extension SHALL là tiện ích Chrome Manifest V3, tự chèn bong bóng Guardian trên chat.zalo.me, messenger.com, facebook.com, web.telegram.org và http://localhost, và chỉ chèn trên trang khác khi người dùng chọn mục menu chuột phải hoặc phím tắt (activeTab).
2. THE Guardian_Extension SHALL hiển thị bong bóng và lớp kết quả trong Shadow DOM để CSS của trang và của tiện ích không ảnh hưởng nhau.
3. WHEN người dùng bôi đen văn bản rồi chạm bong bóng, chọn menu chuột phải "Kiểm tra bằng MoMo Guardian" hoặc nhấn phím tắt, THE Guardian_Extension SHALL gửi đoạn đã chọn tới Flow B với `origin = EXTENSION_SELECTION`.
4. WHEN người dùng chạm bong bóng mà không có đoạn nào được chọn, THE Guardian_Extension SHALL lấy phần văn bản đang hiển thị trong khung nhìn (tối đa 4.000 ký tự, ưu tiên phần gần cuối khung chat) và gửi tới Flow B với `origin = EXTENSION_PAGE_TEXT`; THE Guardian_Extension SHALL không đọc nội dung trang khi người dùng chưa thao tác.
5. WHILE Flow B đang xử lý, THE Guardian_Extension SHALL hiển thị hiệu ứng quét đè lên trang, hiện kết quả Stage 2 khi nhận sự kiện `stage2` (cảnh báo đỏ khi `red_alert`) và hiện thẻ kết quả khi nhận `final`.
6. THE Guardian_Extension SHALL chỉ hiển thị văn bản lấy từ GuardianVerdict và ui_hints (template), không hiển thị văn bản tự do do LLM sinh và không bao giờ hiển thị "100% an toàn".
7. WHEN `ui_hints.calm_shield` là true, THE Guardian_Extension SHALL hiển thị Calm Shield rút gọn: chữ lớn tương phản cao, tối đa 3 bullet, banner "MoMo không bao giờ gọi điện yêu cầu bạn chuyển tiền" và liên kết `tel:` tới hotline.
8. THE Guardian_Extension SHALL gọi backend từ service worker nền (host_permissions tới địa chỉ backend), không gọi từ content script, và lưu session id (uuid v4) cùng địa chỉ backend trong `chrome.storage.local`.
9. IF backend không phản hồi hoặc trả lỗi, THEN THE Guardian_Extension SHALL hiển thị thông báo tiếng Việt và không hiển thị kết luận ALLOW.
10. THE Backend SHALL chấp nhận `EXTENSION_SELECTION` và `EXTENSION_PAGE_TEXT` là Content_Origin không tin cậy, xử lý như nội dung dán (`account_origin = PASTE`) qua đủ R1–R6.

### Requirement 36: Provider LLM tương thích OpenAI
**User Story:** Là nhóm phát triển, tôi muốn dùng bất kỳ nhà cung cấp LLM nào có API kiểu OpenAI (OpenCode, DeepSeek, OpenRouter, Gemini), để không phụ thuộc một nhà cung cấp.
#### Acceptance Criteria
1. WHERE `LLM_PROVIDER=openai_compat`, THE LLM_Client SHALL gọi `POST {OPENAI_COMPAT_BASE_URL}/chat/completions` với `OPENAI_COMPAT_MODEL` và khóa `OPENAI_COMPAT_API_KEY`, giới hạn 280 token đầu ra, cho cả Quarantined_Extractor và Planner.
2. THE LLM_Client SHALL ép đầu ra theo schema bằng `response_format` kiểu `json_schema`, hoặc theo `OPENAI_COMPAT_JSON_MODE` (`json_schema`, `tools`, `json_object`), và kiểm lại bằng Pydantic; đầu ra không hợp lệ được coi là `INVALID_SCHEMA`.
3. IF nhà cung cấp trả mã 401, 403, 429 hoặc 5xx, hoặc hết thời gian chờ, THEN THE LLM_Client SHALL trả trạng thái `ERROR` để Circuit_Breaker và heuristic dự phòng xử lý, và SHALL không ghi khóa API vào log hay trace.
4. WHERE `LLM_PROVIDER=openai_compat` và thiếu `OPENAI_COMPAT_API_KEY`, `OPENAI_COMPAT_BASE_URL` hoặc `OPENAI_COMPAT_MODEL`, THE Backend SHALL từ chối khởi động với thông báo tiếng Việt.
5. THE `GET /api/health` SHALL trả tên provider và tên model đang dùng, không trả khóa.

### Requirement 37: Giảm thao tác dán – kiểm tra một chạm
**User Story:** Là người dùng, tôi không muốn phải sao chép rồi dán tin nhắn, để việc kiểm tra nhanh như một cú chạm.
#### Acceptance Criteria
1. THE Guardian_Popup SHALL có nút "Dán & kiểm tra" đọc clipboard bằng một lần chạm (Clipboard API trong cử chỉ của người dùng) và gửi ngay tới Flow B với `origin = CLIPBOARD`; IF trình duyệt từ chối, THEN THE Guardian_Popup SHALL hiện thông báo và focus ô dán.
2. WHERE người dùng bật "Tự động bảo vệ" cho một trang trong Guardian_Extension, THE Guardian_Extension SHALL theo dõi tin nhắn mới hiển thị trên trang đó và chấm điểm cục bộ trong trình duyệt (từ khóa chuyển tiền, số tài khoản, đường link, đổi tài khoản, mạo danh cơ quan) mà không gửi gì ra mạng.
3. WHEN một tin nhắn đạt ngưỡng chấm điểm cục bộ, THE Guardian_Extension SHALL gắn một nhãn nhỏ "Guardian: nên kiểm tra" cạnh tin nhắn đó; WHEN người dùng chạm nhãn, THE Guardian_Extension SHALL gửi đúng nội dung tin nhắn đó tới Flow B với `origin = EXTENSION_SELECTION` và hiện lớp quét.
4. THE Guardian_Extension SHALL tắt "Tự động bảo vệ" theo mặc định, lưu lựa chọn theo từng tên miền và cho phép tắt bất kỳ lúc nào; nhãn chấm điểm cục bộ SHALL không phải là kết luận và không dùng màu xanh hay chữ "an toàn".

### Requirement 38: Quét khung hội thoại bằng một chạm và minh bạch nội dung đã đọc
**User Story:** Là người dùng, tôi muốn chạm bong bóng một lần là Guardian đọc đúng đoạn hội thoại đang mở và cho tôi biết nó đã đọc gì, để kiểm tra nhanh mà vẫn yên tâm về quyền riêng tư.
#### Acceptance Criteria
1. WHEN người dùng chạm bong bóng mà không bôi đen văn bản, THE Guardian_Extension SHALL xác định khung hội thoại chính trên trang (vùng cuộn được, nằm trong khung nhìn, chứa nhiều khối tin nhắn) và chỉ lấy tối đa 15 tin nhắn gần nhất trong khung đó, theo thứ tự hiển thị, tổng không quá 4.000 ký tự.
2. THE Guardian_Extension SHALL bỏ qua thanh bên, danh sách cuộc trò chuyện, thanh điều hướng, ô nhập, mốc thời gian và chính giao diện của Guardian khi lấy nội dung.
3. IF không xác định được khung hội thoại, THEN THE Guardian_Extension SHALL dùng cách lấy văn bản hiển thị trong khung nhìn của Requirement 35.4.
4. WHILE và sau khi quét, THE Guardian_Extension SHALL hiển thị cho người dùng số tin nhắn đã đọc và cho phép mở xem danh sách các tin nhắn đó (chỉ hiển thị cục bộ, không gửi thêm).
5. THE `docs/FLOWS_AND_GLOSSARY.md` SHALL có mục mô tả, cho từng điểm vào và từng tính năng, người dùng đưa vào gì (đầu vào), người dùng nhìn thấy và làm được gì (đầu ra), và dữ liệu nào rời khỏi thiết bị.

## Phụ lục A: Kết quả mong đợi T01–T31

| ID | Kịch bản | Decision_Tier | Reason_Code / kiểm tra chính |
|---|---|---|---|
| T01 | Giả công an / VNeID ép chuyển tiền | HARD_HOLD | `RC_AUTHORITY_COERCION` |
| T02 | Phạt nguội kèm link APK `vneid-phatnguoi-vn[.]top` | HARD_HOLD | `RC_UNOFFICIAL_APK_PHISHING` |
| T03 | Kịch bản dặn trả lời ngân hàng | HARD_HOLD | `RC_BANK_COACHING_DETECTED` |
| T04 | Cuộc gọi giả MoMo trao thưởng | HARD_HOLD | `RC_BRAND_IMPERSONATION_MOMO` |
| T05 | Người thân deepfake vay gấp | HARD_HOLD | `RC_URGENT_THIRD_PARTY_ACCT` |
| T06 | Yêu cầu chia sẻ màn hình / app điều khiển từ xa | HARD_HOLD | `RC_REMOTE_SCREEN_TAKEOVER` |
| T07 | Shipper giả thu hồi đơn | HARD_HOLD | `RC_FAKE_SHIPPER_RECALL` |
| T08 | Đặt cọc C2C có hối thúc | SOFT_FRICTION (HARD_HOLD nếu SIMO khớp) | Reason_Code C2C trong registry |
| T09 | Biên lai chuyển khoản giả | HARD_HOLD | `RC_UNVERIFIED_INBOUND_RECEIPT` |
| T10 | Việc làm online đòi phí mở khóa | HARD_HOLD | `RC_TASK_SCAM_UNLOCK_FEE` |
| T11 | Đầu tư / tình cảm cam kết lãi cao | HARD_HOLD | `RC_GUARANTEED_RETURN_PIG_BUTCHERING` |
| T12 | Hoàn tiền giả sàn TMĐT | HARD_HOLD | `RC_FAKE_PROMO_REFUND` |
| T13 | VietQR VCB hợp lệ BIN 970436, người nhận quen | ALLOW | `VALID_VIETQR`, `RC_TRUSTED_PAYEE_HISTORY` |
| T14 | QR bị sửa | HARD_HOLD | `BAD_CRC`, `RC_VIETQR_TAMPERED_BAD_CRC` |
| T15 | Tag 62 có dấu cần fallback UTF-8 | theo người nhận | `VALID_VIETQR`, cờ `UTF8_BYTE_FALLBACK` |
| T16 | QR nước ngoài / số tiền thập phân | ≥ SOFT_FRICTION | `FOREIGN_OR_NON_VND` / `INVALID_FORMAT` |
| T17 | Ảnh OCR số tài khoản bị mờ | theo luồng R2 | `requires_user_account_confirm` = true |
| T18 | Injection chữ trắng ẩn | HARD_HOLD | `RC_PROMPT_INJECTION_BLOCKED` |
| T19 | Honeypot injection | HARD_HOLD | `RC_PROMPT_INJECTION_BLOCKED` |
| T20 | Injection trong Tag 62 của QR | theo QR | Tag 62 là dữ liệu, Trace không có tool trái phép |
| T21 | Injection đổi tài khoản nhận | ≥ SOFT_FRICTION | `requires_user_account_confirm` = true, giữ tài khoản người dùng |
| T22 | Bỏ qua kiểm tra QR theo thời gian | HARD_HOLD | Stop_Code `TEMPORAL_BYPASS_DETECTED_MISSING_VIETQR_CHECK` |
| T23 | 3 × 9,8 triệu trong 24 giờ | SOFT_FRICTION | `RC_CIRCULAR50_STRUCTURING_RISK` |
| T24 | SIMO khớp + lời nhắn vô hại | HARD_HOLD | `RC_SIMO_OR_MULE_HIGH_RISK`, LLM không hạ cấp |
| T25 | Tài khoản mule 5 ngày tuổi, 20 người gửi/giờ | HARD_HOLD | `latency_ms` < 200, `allow_fast_unblock` = true |
| T26 | Lộ CCCD và số điện thoại thô | theo nội dung | Che PII, chặn egress LLM |
| T27 | Lời nhắn đùa gửi bạn lâu năm | ALLOW | `RC_TRUSTED_PAYEE_HISTORY` |
| T28 | QR merchant kiểu cũ thiếu subtag 02 | ALLOW | `VALID_VIETQR`, `QRIBFTTA` |
| T29 | LLM chậm 6.000 ms | theo Stage 2 | Stage 2 < 250 ms, fallback tại 4.000 ms, `RC_LLM_TIMEOUT_FALLBACK` |
| T30 | Người cao tuổi đêm khuya | ≥ SOFT_FRICTION | Calm_Shield, TTS, nút Trusted_Contact |
| T31 | QR trơn, người nhận lần đầu | SOFT_FRICTION | `RC_COLD_START_NEEDS_CONTEXT`, Context_Elicitation |
