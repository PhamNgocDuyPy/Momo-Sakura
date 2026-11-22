# Implementation Plan: MoMo Guardian Web

## Overview

Kế hoạch này chuyển `design.md` thành các bước code tăng dần cho Python (FastAPI, Pydantic v2, pytest, Hypothesis) và TypeScript (Vite, React, vitest, fast-check). Thứ tự bám PLAN.md: task 1–16 dựng lõi demo (khung dự án, ví sandbox, dashboard, bong bóng, VietQR Tier 1, Flow A, PII/prefilter/URL, LLMClient, Policy_Engine, Flow B, popup và F1). Sau checkpoint 16 mới làm F2–F7, Calm Shield, handoff, PWA, tài liệu và eval harness. Nếu chạy xuyên đêm bị kẹt, dừng ở checkpoint 16 vẫn có demo hoàn chỉnh.

Quy ước chung cho mọi task:

- Môi trường Windows PowerShell. Dùng `;` thay `&&`. Agent không chạy `uvicorn`, `npm run dev` hay watcher. Test chạy một lần: `cd backend; pytest` và `cd web; npx vitest --run`.
- Theo đúng bố cục module và API contract trong `design.md`. Mọi request model khai báo `extra="forbid"`. Văn bản hiển thị bằng tiếng Việt, code và comment bằng tiếng Anh.
- Property test Python đặt ở `backend/tests/property/test_p{NN}_*.py`, test TS ở `web/tests/*.property.test.ts`. Mỗi test có comment `# Feature: momo-guardian-web, Property N: ...` và chạy tối thiểu 100 lần (profile Hypothesis `ci`, fast-check `numRuns: 100`).
- Generator dùng chung nằm trong package `backend/tests/property/strategies/<area>.py`. Sub-task cài đặt module tạo luôn generator cho area đó; sub-task property chỉ import hoặc khai báo generator cục bộ, để các property test cùng wave không sửa chung một file.

## Tasks

- [x] 1. Dựng khung backend, web và cấu hình
  - [x] 1.1 Tạo khung package backend, Settings và endpoint health
    - Tạo `backend/pyproject.toml` (fastapi, uvicorn, pydantic>=2, pydantic-settings, anthropic, httpx; dev: pytest, pytest-asyncio, hypothesis) và cây thư mục `backend/guardian/` theo design (api, schemas, control_plane, policy, tools, features, providers, llm, stores) kèm `__init__.py`.
    - `guardian/config.py`: `Settings` đọc `.env` với mọi biến trong mục Cấu hình của design; `validate_startup()` in `Thiếu biến môi trường ANTHROPIC_API_KEY (LLM_PROVIDER=anthropic)` ra stderr và `sys.exit(2)`.
    - `guardian/main.py` có `create_app()` và lifespan gọi `validate_startup()`, dựng container; `guardian/container.py` bản tối thiểu.
    - `guardian/api/health.py`: `GET /api/health` trả `status`, `llm_provider`, `version`, `sandbox_now`, `debug`.
    - `guardian/api/deps.py`: đọc header `X-Guardian-Session` (uuid v4, sai thì `400 SESSION_REQUIRED`), cổng debug (`403 DEBUG_DISABLED` khi `GUARDIAN_DEBUG=false`).
    - `backend/tests/conftest.py`: đăng ký và nạp profile Hypothesis `ci` (`max_examples=100, deadline=None`), fixture app gọi qua `httpx.ASGITransport`, fixture settings bật `GUARDIAN_DEBUG` cho test cần debug. Thêm `backend/var/` vào gitignore.
    - _Requirements: 1.9, 12.1, 12.5, 12.7_
  - [x] 1.2 Tạo khung web Vite + React + TypeScript strict
    - Khởi tạo `web/` với Vite React TS (`strict: true`), Tailwind, Framer Motion, Recharts, jsQR, tesseract.js, `qrcode`, react-router.
    - `vite.config.ts` proxy `/api` → `http://localhost:8000`; cấu hình vitest (`jsdom`, Testing Library, fast-check).
    - `src/main.tsx`, `src/App.tsx`, `src/router.tsx` với route `/`, `/transfer`, `/demo` (trang placeholder); `web/.env.example` có `VITE_API_BASE_URL=/api`.
    - _Requirements: 2.1_
  - [x] 1.3 Viết README, `.env.example` và `.gitignore`
    - `.env.example` ở gốc repo theo mục Cấu hình của design, không chứa giá trị khóa thật.
    - `.gitignore`: `.env`, `backend/var/`, `node_modules/`, `dist/`, `__pycache__/`, `.hypothesis/`.
    - `README.md` (PowerShell): tạo venv và `pip install -e ".[dev]"`, `npm install`; người dùng tự chạy `uvicorn guardian.main:app --port 8000` và `npm run dev`; lệnh test `pytest`, `npx vitest --run`; lệnh eval `python -m eval.run_suite --runs 5 --k 3`; ghi chú HTTPS cho camera trên điện thoại, PWA chạy bằng `npm run build; npm run preview`; checklist kiểm thủ công trước demo (camera QR, OCR hóa đơn, Web Share Target, TTS vi-VN, clipboard Chrome/Safari); ghi rõ agent không chạy dev server.
    - _Requirements: 12.7_
  - [ ]* 1.4 Viết smoke test cấu hình
    - `tests/unit/test_config.py`: mọi trường `Settings` có trong `.env.example`; `.env.example` không chứa giá trị khóa; provider mặc định là `mock`; `LLM_PROVIDER=anthropic` thiếu key thì `SystemExit(2)` và stderr nêu `ANTHROPIC_API_KEY`; `/api/health` trả tên provider.
    - _Requirements: 1.9, 12.1, 12.5, 12.7_

- [x] 2. Enum dùng chung, Reason_Code_Registry, template và xử lý số tiền
  - [x] 2.1 Khai báo enum dùng chung
    - `schemas/enums.py`: toàn bộ enum trong mục Data Models (DecisionTier serialize bằng tên, SourceIntegrity, AccountOrigin, ContentOrigin, ContentMode, QrResult, QrFlag, ScamPlaybook, Cue, Confidence, Intent, ProductCategory, PromoBrand, StopCode) cùng `SpendCategory`/`SpendPeriod`/`SpendMetric` kèm nhãn tiếng Việt.
    - Đặt `HardSource` tại đây và re-export từ `policy/floors.py` để tránh vòng import giữa registry và floors.
    - _Requirements: 13.4, 13.5, 13.7, 14.3, 16.1, 25.1_
  - [x] 2.2 Cài đặt Reason_Code_Registry và template tiếng Việt
    - `guardian/reason_codes.py`: `ReasonCodeSpec` và `REGISTRY` (MappingProxyType) chứa đủ mọi mã trong bảng registry của design (gồm các mã bổ sung D11), mỗi mã có `min_tier`, `cooling_off`, `priority`, `hard_sources`, `bullet_vi` (≤ 160 ký tự), `meaning_vi`. Đây là module duy nhất khai báo hằng `RC_`.
    - `policy/templates_vi.py`: `SYSTEM2_QUESTIONS` cho `DEEPFAKE_RELATIVE_EMERGENCY`, `IMPERSONATE_AUTHORITY_VNEID`, `GREY_ZONE` (mỗi câu ≤ 180 ký tự); `ERRORS`; template trả lời F2 (RESOLVED, AMBIGUOUS, NOT_FOUND, NEEDS_AMOUNT, REPHRASE kèm `examples_vi`) và F6; gợi ý thanh toán an toàn (COD, kênh có bảo vệ người mua); banner Calm Shield.
    - _Requirements: 16.5, 23.3, 30.1, 30.2, 30.3_
  - [ ]* 2.3 Viết unit test cho registry và template
    - Mọi mã khớp `^RC_[A-Z0-9_]{3,40}$`; bullet ≤ 160, câu hỏi ≤ 180; cooling thuộc {0, 15, 30, 60, 300}; mã HARD có `hard_sources` khác rỗng; không template nào chứa "100% an toàn" hoặc "100% safe".
    - _Requirements: 8.1, 16.3, 30.2, 30.3_
  - [x] 2.4 Cài đặt Amount_Parser và Amount_Formatter
    - `tools/amount.py`: `parse_amount` theo bảng mẫu của design (lít, xị, củ, k, tr, `1tr5`, dấu nghìn, hậu tố đ/vnd; không nguyên hoặc âm thì `None`), `find_amounts` (dãy số trơn không bao giờ là số tiền), `format_vnd`.
    - Tạo `fixtures/amount_vectors.json` (cặp `n` → chuỗi định dạng và cặp tiếng lóng → giá trị) để bản Python và TS cùng kiểm.
    - Tạo `tests/property/strategies/amount.py`.
    - _Requirements: 19.1, 19.2, 19.3, 19.4, 19.5, 19.6_
  - [x] 2.5 Viết property test round trip số tiền (Python)
    - **Property 25: Round trip định dạng số tiền**
    - Kiểm thêm `format_vnd` khớp từng mục trong `fixtures/amount_vectors.json`.
    - **Validates: Requirements 16.9, 19.6, 19.7**
  - [ ]* 2.6 Viết property test công thức đơn vị số tiền
    - **Property 26: Công thức đơn vị số tiền**
    - **Validates: Requirements 19.4, 19.5**
  - [ ]* 2.7 Viết unit test ví dụ số tiền
    - "2 lít" → 200000, "5 xị" → 500000, "1 củ" → 1000000, "200k", "1tr5", "1.5tr", "1tr25"; `find_amounts` bỏ qua số tài khoản.
    - _Requirements: 19.1, 19.2, 19.3, 19.4_

- [x] 3. Dữ liệu sandbox, provider và API tổng quan ví
  - [x] 3.1 Khai báo interface provider và đồng hồ
    - `providers/base.py`: Protocol `RiskDataProvider`, `WalletDataProvider` và model `NameInquiryResult`, `RecipientRisk`, `PayerHistory`, `WalletTransaction`, `Contact`, `BillRecord`, `Subscription`, `Budget`, `TrustedContact`, `WalletProfile`.
    - `providers/clock.py`: `Clock`, `SystemClock`, `SandboxClock(SANDBOX_NOW)`; `tests/fakes.py` có `FakeClock`.
    - _Requirements: 31.1, 31.2_
  - [x] 3.2 Tạo fixture sandbox
    - `fixtures/banks.json` (BIN, tên, alias, domain chính thức, `deeplink_template: null`) và `tools/banks.py` (BIN ↔ tên/alias).
    - `fixtures/risk_sandbox.json` theo bảng tài khoản sandbox của design.
    - `fixtures/gen_wallet.py` (seed 2026, 2026-09-01 → 2026-11-30, khoảng 420 giao dịch, 12 danh mục) và `fixtures/wallet_sandbox.json` đã commit: danh bạ (Nguyễn Văn Minh, Trần Thị Lan, Phạm Ngọc Lan, Lê Quốc Bảo, Mẹ), hóa đơn EVN_HCMC/SAWACO/FPT_INTERNET, gói Netflix/Spotify/YouTube, ngân sách FOOD/CAFE/TRANSPORT, Trusted_Contact, profile 970436/0071000999888.
    - `fixtures/official_promos.json` (`MOMOXMAS26` hiệu lực từ 2026-11-15, `MOMOTET27`) và `fixtures/reference_prices.json` (iphone_15_pro_max, airpods_pro_2, ps5_slim).
    - _Requirements: 23.2, 24.2, 31.2, 31.3_
  - [x] 3.3 Cài đặt Sandbox_Provider
    - `providers/sandbox_risk.py` (tài khoản không có trong fixture: `found=false`, gnn 0.05, tuổi 365, không lịch sử) và `providers/sandbox_wallet.py`.
    - Nạp lúc khởi động; fixture thiếu hoặc hỏng thì dừng khởi động và nêu tên file. Đăng ký vào `container.py`. Chỉ `providers/` được đọc `fixtures/`.
    - _Requirements: 31.1, 31.2, 31.3, 31.4_
  - [x] 3.4 Cài đặt `GET /api/wallet/summary`
    - `features/wallet_summary.py`: chi tiêu theo danh mục tháng hiện tại (OUT), ngân sách với `percent_used = floor(spent*100/limit)` và `status` OK/WARNING/OVER bằng số nguyên, 10 giao dịch gần nhất giảm dần, hóa đơn, gói định kỳ, Trusted_Contact. `alerts` để rỗng cho đến khi task 18.5 nối Bill_Monitor.
    - `stores/shield_stats.py`: bộ đếm theo session (checks, ALLOW, SOFT_FRICTION, HARD_HOLD), trả trong `shield_stats`.
    - `api/wallet.py`, đăng ký router trong `main.py`. Tạo `tests/property/strategies/wallet.py`.
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_
  - [ ]* 3.5 Viết property test wallet summary
    - **Property 35: Wallet summary**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**
  - [ ]* 3.6 Viết unit test provider và kiến trúc dữ liệu
    - Tài khoản lạ trả giá trị mặc định; fixture thiếu làm dừng khởi động; `tests/unit/test_architecture.py` kiểm chỉ `providers/` đọc `fixtures/`.
    - _Requirements: 31.3, 31.4_

- [x] 4. Dashboard, bong bóng Guardian và khung popup quét (web)
  - [x] 4.1 Dựng service, type và store nền của web
    - `src/types/api.ts` khớp `schemas/api_models.py` của design (CheckResponse, UiHints, Signals, các request/response).
    - `src/services/session.ts` (`crypto.randomUUID()` trong sessionStorage), `src/services/api.ts` (fetch có type, header `X-Guardian-Session`, timeout 10 s).
    - `src/lib/amount.ts` mirror `parse_amount`/`format_vnd`.
    - `src/state/guardianStore.tsx`: context + useReducer cho trạng thái popup (open, mode, status, linked transaction), verdict gần nhất, `shieldStats` (tăng đồng bộ khi nhận verdict, bỏ qua verdict `from_demo`).
    - _Requirements: 1.7, 1.8, 16.9_
  - [x] 4.2 Viết property test round trip số tiền (TypeScript)
    - **Property 25: Round trip định dạng số tiền**
    - `web/tests/amount.property.test.ts` với fast-check; kiểm thêm `formatVnd` cho cùng chuỗi với `fixtures/amount_vectors.json`.
    - **Validates: Requirements 16.9, 19.6, 19.7**
  - [x] 4.3 Cài đặt DashboardPage
    - `pages/DashboardPage.tsx` và `components/dashboard/`: `SpendingChart` (Recharts), `BudgetList` (vàng khi ≥ 80%, đỏ khi ≥ 100%), `RecentTransactions`, `BillsAndSubscriptions` (ngày đến hạn), `AlertsList` (có trạng thái rỗng), `ShieldCard` đọc `shieldStats`; `components/guardian/SandboxBadge.tsx` ("Dữ liệu mô phỏng"). Mobile-first, số tiền qua `lib/amount.ts`.
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 31.5_
  - [x] 4.4 Cài đặt GuardianBubble, ScanPopup và ScanAnimation
    - `lib/bubblePosition.ts`: `snapToEdge(pos, viewport)` thuần, lưu/đọc `localStorage["guardian.bubble.pos"]`.
    - `GuardianBubble.tsx`: Framer Motion `drag`, ngưỡng 6 px phân biệt chạm và kéo, chạm thì `openPopup()` đồng bộ, ẩn khi popup mở, hiện lại tại vị trí đã lưu khi đóng. Gắn vào layout của `App.tsx` cho mọi route.
    - `ScanPopup.tsx` (bottom sheet): ô dán, ô lệnh, nút chọn/chụp ảnh, nút quét QR, `ConsentToggle` mặc định tắt, công tắc Clipboard_Check mặc định tắt (chỉ UI, nối ở task 15.3).
    - `ScanAnimation.tsx`: radar + khiên (conic-gradient, Framer Motion), hiện khi `status ∈ {ocr, stage1, stage2}`.
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.1, 29.5_
  - [ ]* 4.5 Viết property test bong bóng bám cạnh
    - **Property 45: Bong bóng bám cạnh và lưu vị trí**
    - **Validates: Requirements 2.2, 2.3**
  - [ ]* 4.6 Viết property test bộ đếm Shield_Card
    - **Property 47: Bộ đếm Shield_Card**
    - **Validates: Requirements 1.7**
  - [ ]* 4.7 Viết unit test component dashboard và bong bóng
    - Chạm bong bóng mở popup đồng bộ; popup có đủ điểm vào; ScanAnimation hiện khi xử lý; ConsentToggle mặc định tắt; trạng thái màu của BudgetList.
    - _Requirements: 1.3, 1.4, 2.4, 2.5, 2.6, 29.5_

- [x] 5. VietQR Tier 1: verifier và encoder
  - [x] 5.1 Cài đặt `tools/vietqr.py`
    - `crc16_ccitt_false` (0x1021, init 0xFFFF) trên byte UTF-8 đến hết `6304`; kiểm CRC trước khi parse.
    - `parse_tlv`: parse theo code point trước, thất bại thì parse theo byte UTF-8 và chỉ chấp nhận khi kết thúc đúng tại Tag 63, gắn `UTF8_BYTE_FALLBACK`.
    - `verify_vietqr_emvco` theo bước 1–7 của design: AID nước ngoài / Tag 53 / Tag 58 → `FOREIGN_OR_NON_VND`; thiếu tag bắt buộc, Tag 00/01 sai, Tag 38 sai, Tag 54 không phải số nguyên → `INVALID_FORMAT`; thiếu 38.02 → `QRIBFTTA` + `LEGACY_DEFAULT_SERVICE_CODE`; Tag 62 parse thành subtag và chỉ trả như dữ liệu. Không bao giờ ném lỗi.
    - `encode_vietqr(bin, account, amount_vnd|None, memo, poi="12")` với ràng buộc đầu vào của design; `fold_ascii(memo)`.
    - Tạo `tests/property/strategies/vietqr.py` (`vietqr_fields()` có memo tiếng Việt và emoji).
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.13, 5.1, 5.2_
  - [x] 5.2 Viết property test encode → verify round trip
    - **Property 1: VietQR encode → verify round trip**
    - **Validates: Requirements 4.1, 4.2, 4.7, 5.1, 5.2, 5.3**
  - [x] 5.3 Viết property test phát hiện sửa đổi QR
    - **Property 3: Phát hiện sửa đổi QR**
    - **Validates: Requirements 4.3, 5.5**
  - [ ]* 5.4 Viết property test parse → encode → parse
    - **Property 2: VietQR parse → encode → parse**
    - **Validates: Requirements 5.4**
  - [ ]* 5.5 Viết property test fallback độ dài byte UTF-8
    - **Property 4: Fallback độ dài byte UTF-8**
    - **Validates: Requirements 4.7, 4.8**
  - [ ]* 5.6 Viết property test phân loại payload sai
    - **Property 5: Phân loại payload sai và tính toàn phần của verifier**
    - **Validates: Requirements 4.4, 4.5, 4.6**
  - [x] 5.7 Tạo mẫu QR và `POST /api/qr/verify`
    - `fixtures/gen_qr.py` sinh tất định `fixtures/qr_samples.json` và PNG mẫu: T13 hợp lệ, T14 bị sửa, T15 Tag 62 tính theo byte, T16a PromptPay, T16b Tag 54 "150000.50", T20 Tag 62 chứa lệnh, T22 hợp lệ, T28 merchant cũ thiếu 38.02, T31 người nhận lần đầu.
    - `api/qr.py`: `POST /api/qr/verify` (payload ≤ 512 ký tự) trả `result`, `flags`, `fields`, `crc`. Đăng ký router.
    - _Requirements: 4.10, 31.6_
  - [ ]* 5.8 Viết unit test VietQR
    - `crc16("123456789") == 0x29B1`; từng mẫu trong `qr_samples.json` cho đúng kết quả; chạy lại `gen_qr.py` cho file giống hệt; contract endpoint (happy path và payload quá dài).
    - _Requirements: 4.1, 4.3, 4.4, 4.5, 4.8, 4.9, 4.10, 31.6_

- [x] 6. Nền tảng policy: floor, trace, composer và store
  - [x] 6.1 Cài đặt Floor, FloorSet, Trace và RequestContext
    - `policy/floors.py`: `Floor` (raise khi HARD thiếu `hard_source`, mã phải có trong registry), `FloorSet` chỉ thêm, `final_tier = max`, chỉ gỡ được floor có `removable_by` chứa `FAST_UNBLOCK` hoặc `CONTEXT_IN_STORE`; `allow_fast_unblock()`; `cooling_off_seconds()` = max cooling.
    - `schemas/trace.py`: `TraceStep`, `RuleFiring`, `TraceRecorder` (`kind`, `status`, `detail` chỉ chứa enum/số/boolean/domain).
    - `control_plane/session.py`: kiểm uuid, `payer_session_hash` HMAC-SHA256 với `SESSION_HASH_SECRET`; dataclass `RequestContext`.
    - Tạo `tests/property/strategies/signals.py` (`signals()`, `floorsets()`, giá trị đúng ngưỡng 0.85, 9.000.000, 10.000.000, 20.000.000).
    - _Requirements: 15.6, 15.7, 15.9, 16.4_
  - [x] 6.2 Cài đặt ToolRunner và allowlist
    - `control_plane/tool_runner.py`: `ALLOWED_TOOLS`, `ToolRunner.call()` kiểm allowlist (`ToolNotAllowed`, trace `denied`), gọi hook `before_call`/`after_call` của policy qua Protocol, đo thời gian và ghi `TraceStep`.
    - _Requirements: 13.2, 17.8_
  - [x] 6.3 Khai báo GuardianVerdict và envelope API
    - `schemas/verdict.py`: `GuardianVerdict` với `ReasonCode` validator kiểm registry, DecisionTier serialize bằng tên.
    - `schemas/api_models.py`: `CheckResponse`, `UiHints`, `Signals`, request/response cho mọi endpoint trong design, `DebugOverrides` (`simulate_llm_delay_ms`, `simulate_skip_qr_verify`, `force_llm_output`, `simulate_redactor_failure`).
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.8_
  - [x] 6.4 Cài đặt VerdictComposer và UI hints
    - `policy/composer.py`: sắp floor theo (tier giảm, priority tăng), bỏ trùng, tối đa 6 mã (phần dư vào audit), bullet của 4 mã đầu, tối đa 2 câu System 2 theo thứ tự ưu tiên, honesty filter sau NFC, `requires_user_account_confirm`, `model_validate` lỗi thì `COMPOSER_INVALID`.
    - `policy/ui_hints.py`: `calm_shield`, `show_context_elicitation`, `safe_payment_tips`, `show_transfer_now`, `missing_fields`, `handoff_allowed`, `trusted_contacts`, `hotline` theo bảng của design; giờ đêm tính theo `client_time` quy về GMT+7.
    - _Requirements: 6.12, 8.1, 16.2, 16.3, 16.4, 16.5, 16.6, 20.2, 20.6, 27.1, 27.2_
  - [x] 6.5 Viết property test verdict luôn hợp lệ
    - **Property 22: Verdict luôn hợp lệ**
    - **Validates: Requirements 6.12, 16.2, 16.3, 16.4**
  - [x] 6.6 Cài đặt các store trong bộ nhớ
    - `stores/risk_memory.py`: khóa `acct:{bin}:{digits}`, `acct:*:{digits}`, `dom:{domain}`; TTL `RISK_MEMORY_TTL_HOURS`; ghi trùng giữ priority cao hơn và `expires_at` lớn hơn; bỏ qua mục hết hạn và dọn lười; clock inject được.
    - `stores/audit.py`: ghi thêm `audit.jsonl` (UTF-8, lock, `flush` + `os.fsync`), không có API sửa/xóa, `OSError` thì log stderr và báo `audit: "degraded"` ở health; trường `content_sha256` / `evidence_redacted` theo consent.
    - `stores/ledger.py`, `control_plane/verdict_store.py`, `control_plane/pending_confirm.py` (kèm confirmation token TTL 30 phút gắn session, BIN, số tài khoản). Mọi store dùng `threading.Lock`; đăng ký vào container.
    - Tạo `tests/property/strategies/risk_memory.py` (`risk_memory_ops()`).
    - _Requirements: 18.1, 18.3, 18.4, 18.5, 18.6, 29.1, 29.2, 29.3_
  - [x] 6.7 Viết property test Risk_Memory theo mô hình tham chiếu
    - **Property 30: Risk_Memory theo mô hình tham chiếu**
    - **Validates: Requirements 18.3, 18.4, 18.5, 18.6**
  - [ ]* 6.8 Viết unit test audit và store
    - Audit chỉ ghi thêm; lỗi ghi không chặn verdict và health báo `degraded`; verdict store và token hết hạn đúng TTL.
    - _Requirements: 29.1, 29.2_

- [x] 7. Flow A, Fast Unblock và Context Elicitation (backend)
  - [x] 7.1 Cài đặt luật Policy_Engine cho Flow A
    - `policy/engine.py`: `before_call` (allowlist, R2 abort với `UNCONFIRMED_ACCOUNT_ABORTED` + Stop `ABORT_WAIT_NAPAS_NAME_USER_CONFIRM` + floor `RC_OCR_ACCOUNT_NEEDS_CONFIRM`), `after_call` (TIER1 S1–S3, R4 S5–S7 với GNN/velocity `removable_by FAST_UNBLOCK`, MEMORY S9), `before_emit` (R6 S4, R5 S10 cộng Ledger 24 h, grey zone S8 kèm câu hỏi GREY_ZONE, baseline X3/X4), `before_persist` (R1 consent: thiếu consent chỉ ghi hash, yêu cầu lưu bằng chứng thì Stop `LAW_91_CONSENT_REQUIRED`). Ghi `rules_fired`.
    - `policy/mapping.py`: các hàng S1–S10, X3, X4 của bảng ánh xạ.
    - _Requirements: 4.11, 4.12, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 8.2, 9.5, 9.6, 15.1, 15.3, 15.4, 15.5, 15.9, 18.2_
  - [x] 7.2 Cài đặt FlowAGate và `POST /api/flow-a/check`
    - `control_plane/flow_a.py`: constructor không nhận `LLMClient`; giải Source_Integrity theo D4 (thiếu token khớp thì coi `OCR_UNCONFIRMED`); có QR thì `verify_vietqr_emvco` là tool đầu tiên; nhánh R2 abort; ngược lại `risk_memory_lookup`, `lookup_recipient_risk_and_simo`, `lookup_payer_history`; `before_emit`, compose, lưu VerdictStore, `before_persist`, audit, tăng ShieldStats, `latency_ms`. `memo` không được luật nào đọc.
    - `api/flow_a.py`: endpoint, `debug.simulate_skip_qr_verify` chỉ khi debug bật; lỗi không lường trước trả `500 FLOW_A_ERROR`. Đăng ký vào container và router.
    - _Requirements: 6.1, 6.2, 6.4, 6.12, 9.1, 9.2, 15.5, 18.2, 29.1_
  - [x] 7.3 Viết property test bảng quyết định Flow A
    - **Property 6: Bảng quyết định Flow A**
    - **Validates: Requirements 4.11, 4.12, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 8.2**
  - [x] 7.4 Viết property test R6
    - **Property 12: R6 – QR phải được kiểm tra trước khi ghép verdict**
    - **Validates: Requirements 15.5**
  - [x] 7.5 Viết property test Flow A không gọi LLM
    - **Property 13: Flow A không gọi LLM**
    - Dùng spy `LLMClient` ném lỗi nếu bị gọi; thêm kiểm tĩnh `control_plane/flow_a.py` không import `guardian.llm`.
    - **Validates: Requirements 6.2**
  - [x] 7.6 Cài đặt fast-unblock, context và transfer commit
    - `POST /api/flow-a/fast-unblock` trong `api/flow_a.py`: OTP sandbox `123456` (sai thì `400 IDENTITY_CHECK_FAILED`), `purpose` từ danh sách cố định, verdict gốc phải có `allow_fast_unblock` (không thì `409 FAST_UNBLOCK_NOT_ALLOWED`), gỡ floor GNN/velocity, thêm `RC_FAST_UNBLOCK_VERIFIED` (SOFT, 30 s) và giữ các floor SOFT còn lại; audit `original_reason_codes`, `purpose`, `unblocked_at`.
    - `POST /api/flow-a/context`: bốn context theo bảng của design, verdict gốc phải chứa `RC_COLD_START_NEEDS_CONTEXT` (không thì `409 CONTEXT_NOT_APPLICABLE`).
    - `api/transfer.py`: `POST /api/transfer/commit` (HARD → 403, SOFT chưa hết cooldown theo đồng hồ server hoặc chưa trả lời đủ câu hỏi → 409, thành công ghi Ledger và đánh dấu `cooldown_completed`).
    - _Requirements: 7.3, 7.5, 8.4, 8.5, 8.6, 8.7, 27.5, 27.6, 28.1_
  - [ ]* 7.7 Viết property test Fast Unblock
    - **Property 10: Điều kiện và kết quả Fast Unblock**
    - **Validates: Requirements 6.5, 6.6, 7.3**
  - [x] 7.8 Cài đặt scenario loader và matcher
    - `eval/scenario_loader.py`: đọc `fixtures/scenarios/*.json` (bỏ file bắt đầu bằng `_`), thay placeholder `{{qr:<ID>}}` và `{{prev.<path>}}`, đánh dấu `requires_debug`.
    - `eval/matcher.py`: `decision_tier` bằng hoặc `{"min": ...}`, `reason_codes_include`/`exclude`, `qr_result`, `qr_flags_include`, `stop_codes_include`, `trace_tools_subset_of_allowlist`, `assert[]` với `eq|lt|gt|in|contains|absent|matches_reference` (registry hàm tham chiếu), trả danh sách mismatch.
    - `tests/scenarios/runner.py`: chạy từng case qua `httpx.ASGITransport`, mỗi lần chạy một session mới.
    - _Requirements: 33.1, 33.8, 34.4_
  - [x] 7.9 Tạo fixture và test kịch bản Flow A
    - `fixtures/scenarios/` T13, T14, T15, T16, T22, T23, T25, T27, T28, T31 theo bảng tóm tắt của design; `tests/scenarios/test_flow_a_scenarios.py` chạy tham số hóa và kiểm `latency_ms < 200` cho T25.
    - Unit test bốn nhánh context và bản ghi audit của fast-unblock.
    - _Requirements: 6.3, 7.5, 8.2, 8.4, 8.5, 8.6, 8.7, 33.1, 33.8_

- [x] 8. Màn chuyển tiền (web)
  - [x] 8.1 Cài đặt TransferPage và các component kết quả
    - `pages/TransferPage.tsx`, `components/transfer/TransferForm.tsx`, `TwoStepConfirm.tsx` (bước "Kiểm tra thông tin" rồi "Xác nhận chuyển" trước khi gọi Flow A), `FastUnblockDialog.tsx` (OTP sandbox + mục đích).
    - `components/guardian/ResultCard.tsx` (màu tier, bullet, SandboxBadge), `DecisionTrace.tsx` (trace, `rules_fired`, thời gian stage), `CooldownGate.tsx`, `System2Questions.tsx`, `ContextElicitation.tsx` (bốn nút gọi `/api/flow-a/context`; lời mời chia sẻ ảnh chat nối ở task 15.3).
    - SOFT hiện nút "Kiểm tra cùng Guardian": dispatch `openPopup` kèm `linked_transaction`; `allow_fast_unblock` hiện "Mở chặn nhanh", ngược lại ẩn; sau cooldown gọi `/api/transfer/commit`. Nhận prefill qua router state; số tiền qua Amount_Formatter; dispatch verdict vào store.
    - _Requirements: 6.1, 6.11, 7.1, 7.2, 7.4, 8.3, 8.4, 8.5, 8.6, 8.7, 16.9, 17.10, 27.5, 27.6, 31.5_
  - [ ]* 8.2 Viết unit test component màn chuyển tiền
    - CooldownGate với fake timers khóa nút đến khi hết giờ và trả lời xong câu hỏi; hiện/ẩn "Mở chặn nhanh"; ContextElicitation có bốn nút; TwoStepConfirm cần hai bước.
    - _Requirements: 7.1, 7.4, 8.3, 27.5, 27.6_

- [x] 9. Checkpoint – luồng Flow A chạy được
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Che PII, prefilter, hijack, kiểm tra URL và quét thực thể
  - [x] 10.1 Cài đặt PII_Redactor
    - `tools/pii.py`: `detect_pii` là bộ phát hiện duy nhất (OTP có từ khóa, CCCD 12 số, CMND 9 số, SĐT, tên từ danh bạ WalletDataProvider trừ từ xưng hô thân tộc, tên sau danh xưng, chuỗi IN HOA sau số tài khoản); ngoại lệ số tài khoản theo ngữ cảnh 25 ký tự và bị vô hiệu bởi từ khóa PII mạnh; token `[CCCD_1]`… idempotent; `redact_pii_local` trả văn bản và số đếm; `Tokenizer` đảo ngược được trong bộ nhớ request. Không import `httpx`/`socket`.
    - Tạo `tests/property/strategies/pii.py` (`vn_text_with_pii()`, số tài khoản dạng SĐT có ngữ cảnh `stk`).
    - _Requirements: 10.1, 10.3, 10.4, 10.5, 10.6_
  - [x] 10.2 Viết property test che PII đầy đủ
    - **Property 16: Che PII đầy đủ và giữ số tài khoản**
    - **Validates: Requirements 10.1, 10.4, 10.5**
  - [x] 10.3 Viết property test che PII idempotent
    - **Property 17: Che PII idempotent**
    - **Validates: Requirements 10.3**
  - [x] 10.4 Cài đặt Prefilter và hijack detector
    - `tools/prefilter.py`: regex biên dịch sẵn với trọng số theo design, `score = 1 - Π(1 - w_i)`, `PREFILTER_SOFT_THRESHOLD`.
    - `tools/hijack.py`: phát hiện tên tool trong `ALLOWED_TOOLS`, mã `RC_` giả, khung JSON giống GuardianVerdict (≥ 2 khóa).
    - _Requirements: 11.1, 11.4, 15.2_
  - [x] 10.5 Cài đặt URL_Checker
    - `tools/url_checker.py`: trích URL kể cả dạng defang `[.]`, chuẩn hóa (lower, IDNA, bỏ `www.`, registrable domain theo danh sách TLD cố định), cờ `APK_DOWNLOAD`, `GOV_SPOOF`, `BRAND_LOOKALIKE`, `RISKY_TLD`, `PUNYCODE`, `IP_LITERAL`, `SHORTENER`; `SafeBrowsingClient` chỉ chạy khi có `GOOGLE_SAFE_BROWSING_API_KEY`, timeout 800 ms, lỗi thì trace `error`.
    - Tạo `tests/property/strategies/urls.py` (`urls_with_features()`).
    - _Requirements: 11.5, 11.7_
  - [ ]* 10.6 Viết property test URL_Checker
    - **Property 42: URL_Checker chuẩn hóa và gắn cờ**
    - **Validates: Requirements 11.5**
  - [x] 10.7 Cài đặt entity scanner
    - `tools/entity_scanner.py`: STK theo cùng ngữ cảnh với ngoại lệ PII, alias ngân hàng → BIN theo bảng của design, số tiền qua `find_amounts`, URL qua URL_Checker.
    - _Requirements: 10.5, 20.1_
  - [x] 10.8 Cài đặt `POST /api/precheck`
    - `api/precheck.py`: trả `redacted_text`, `redaction_counts`, `prompt_guard_cpu_score`, `urls`, `hijack_detected`, `duration_ms`. Đăng ký router.
    - _Requirements: 11.8_
  - [ ]* 10.9 Viết unit test PII, prefilter và URL
    - Benchmark prefilter có marker `perf` (4.000 ký tự, 200 lần, p95 < 20 ms); kiểm tĩnh `tools/pii.py` không import mạng; ví dụ domain T02/T12; contract `/api/precheck`.
    - _Requirements: 10.6, 11.1, 11.5, 11.6, 11.8_

- [x] 11. Schema LLM và LLMClient (Mock, Anthropic, Bedrock stub)
  - [x] 11.1 Khai báo QuarantinedExtraction và PlannerIntent
    - `schemas/extraction.py` đúng như design (`reasoning_summary` là trường đầu tiên, `Strict` với `extra="forbid"` ở mọi model lồng, `PaymentRequest`, `ReceiptItems`, `Listing`, `PromoClaim`, `FALLBACK_EXTRACTION`).
    - `schemas/planner.py`: `TransferSlots`, `SpendSlots`, `SplitSlots`, `PlannerIntent` với validator slot khớp intent.
    - Tạo `tests/property/strategies/extractions.py` (`extractions()`, `planner_intents()`, `verdicts()`).
    - _Requirements: 13.3, 13.4, 13.5, 13.6, 13.7, 13.8, 13.9, 14.3, 14.4_
  - [ ]* 11.2 Viết property test round trip và tính chặt của schema
    - **Property 21: Round trip và tính chặt của schema**
    - **Validates: Requirements 13.9, 13.11, 14.6, 16.8**
  - [x] 11.3 Cài đặt LLMClient, MockLLM, Bedrock stub và factory
    - `llm/base.py`: Protocol `LLMClient`, `LLMResult` với các status, `ProviderNotImplementedError`.
    - `llm/mock.py`, `llm/mock_rules.py`: hàm thuần theo design (chuẩn hóa không dấu, injection, cue theo thứ tự, playbook theo bảng ưu tiên, entity qua `entity_scanner`, mở rộng `payment_request`/`receipt_items`/`listing`/`promo_claim`, `confidence_level`, `reasoning_summary` dạng `mock: ...`); Mock Planner cho TRANSFER, SPEND_QUERY, SPLIT_BILL, CHECK_PROMO, SHOP_CHECK, CHECK_CONTENT, UNKNOWN; độ trễ `MOCK_LLM_DELAY_MS`. Bộ luật phải cho đúng playbook/cue của các đầu vào T01–T12, T18, T26, T29, T30 và A01–A10.
    - `llm/bedrock_stub.py` raise `ProviderNotImplementedError("provider chưa được cài đặt")`; `llm/factory.py` `build_llm(settings)`; đăng ký vào container.
    - _Requirements: 12.1, 12.2, 12.6, 13.2, 13.12_
  - [ ]* 11.4 Viết property test tính tất định của MockLLM
    - **Property 19: Tính tất định với MockLLM**
    - **Validates: Requirements 12.2, 15.10**
  - [x] 11.5 Cài đặt AnthropicClient
    - `llm/anthropic_client.py`: `messages.create` với `max_tokens=280`, tool `emit_quarantined_extraction` / `emit_planner_intent` có `input_schema` từ Pydantic, `tool_choice` ép tool, không gửi `temperature`/`top_p`; `wrap_untrusted` với boundary ngẫu nhiên; ánh xạ `stop_reason` sang `OK`/`INVALID_SCHEMA`/`TRUNCATED`/`REFUSAL`/`NO_TOOL_CALL`/`ERROR`; SDK timeout `LLM_TIMEOUT_MS + 500`. Nối nhánh `anthropic` trong factory.
    - _Requirements: 12.3, 12.4_
  - [ ]* 11.6 Viết property test đầu ra LLM không hợp lệ
    - **Property 20: Đầu ra LLM không hợp lệ**
    - **Validates: Requirements 12.4, 13.10, 14.5**
  - [x] 11.7 Cài đặt CircuitBreaker
    - `llm/circuit_breaker.py`: `asyncio.wait_for` với `LLM_TIMEOUT_MS`, mở 60 s sau 3 lần liên tiếp timeout/lỗi (trả `SKIPPED` với `breaker="open"`), half-open một lời gọi thử, clock inject được.
    - _Requirements: 17.6_
  - [ ]* 11.8 Viết unit test LLM client
    - AnthropicClient với SDK giả: tham số gửi đi, từng `stop_reason` (`refusal`, `max_tokens`, `end_turn`, `pause_turn`); Bedrock stub; breaker open/half-open với FakeClock; MockLLM điền đúng tiếng lóng số tiền; schema walker (mọi model `extra="forbid"`, mọi `str` có `max_length` hoặc `pattern`, `reasoning_summary` đứng đầu).
    - _Requirements: 12.3, 12.4, 12.6, 13.3, 13.8, 13.12, 14.4, 17.6_

- [x] 12. Luật Flow B và bộ kiểm tra F4/F5
  - [x] 12.1 Mở rộng Policy_Engine cho Flow B
    - `before_call`: R1 egress chạy `detect_pii` trước `quarantined_extract` và `plan`, còn PII thì Abort với Stop `PII_EGRESS_BLOCKED` + floor `RC_PII_EGRESS_BLOCKED`.
    - `after_call` và `mapping.py`: S11–S16 (R3 mức mềm/cứng, hijack, URL), P1–P10, C1–C4 theo D2 (cue chỉ tạo sàn SOFT; `RC_BANK_COACHING_DETECTED`/`RC_REMOTE_SCREEN_TAKEOVER` chỉ khi playbook thuộc nhóm HARD; `UNKNOWN_SUSPICIOUS` tối đa SOFT), X1 đổi tài khoản, X2 OCR chưa xác nhận, L1–L4.
    - Heuristic dự phòng khi LLM timeout/lỗi chỉ được phát P8, P9, C3, C4.
    - _Requirements: 10.2, 11.3, 11.4, 11.6, 13.10, 15.2, 15.4, 15.7, 15.8, 15.11, 17.6, 17.9, 17.11_
  - [x] 12.2 Cài đặt Shop_Checker và Promo_Checker
    - `features/shop_checker.py`: tra giá theo `product_key` rồi `category`, cờ `listed*100 <= reference*60` → SOFT `RC_PRICE_TOO_GOOD_TO_BE_TRUE`, không có giá → `RC_NO_REFERENCE_PRICE`, gộp cờ URL, bật `safe_payment_tips` khi đặt cọc.
    - `features/promo_checker.py`: bảng quyết định F5a–F5d (HARD dùng `hard_source = PROMO_FAKE`), so mã không phân biệt hoa thường, ngày hiệu lực theo SandboxClock, `official_promo` lấy từ fixture.
    - Tạo `tests/property/strategies/promo.py` (`promo_claims()`).
    - _Requirements: 23.2, 23.3, 23.4, 23.5, 24.2, 24.3, 24.4, 24.5_
  - [x] 12.3 Viết property test bảng floor tất định của Flow B
    - **Property 7: Bảng floor tất định của Flow B**
    - **Validates: Requirements 4.11, 4.12, 11.3, 11.6, 15.2, 15.4, 15.8**
  - [x] 12.4 Viết property test HARD_HOLD cần nguồn HARD hợp lệ
    - **Property 9: HARD_HOLD cần nguồn HARD hợp lệ**
    - **Validates: Requirements 11.4, 15.7, 17.6**
  - [ ]* 12.5 Viết property test kiểm tra giá F4
    - **Property 36: Kiểm tra giá F4**
    - **Validates: Requirements 23.2, 23.5**
  - [ ]* 12.6 Viết property test bảng quyết định F5
    - **Property 37: Bảng quyết định F5**
    - **Validates: Requirements 24.2, 24.3, 24.4, 24.5**

- [x] 13. Flow B orchestrator, streaming NDJSON và API xác nhận tên
  - [x] 13.1 Cài đặt grounding check
    - `control_plane/grounding.py`: chuỗi trích từ LLM chỉ được dùng khi (sau NFC và chuẩn hóa khoảng trắng) là chuỗi con của văn bản đã che PII và không chứa `[`, `]`, `<`, `>`.
    - _Requirements: 16.5, 16.7_
  - [x] 13.2 Cài đặt FlowBOrchestrator
    - `control_plane/flow_b.py` theo thứ tự cố định: `label_untrusted` → `redact_pii_local` → `scan_entities` → `detect_hijack` → `verify_vietqr_emvco` (nếu có QR) → `check_urls` → `napas_name_inquiry_readonly` (OCR, lưu PendingConfirm) hoặc `lookup_recipient_risk_and_simo` + `risk_memory_lookup` → song song `prompt_guard_cpu_score` (`asyncio.to_thread`) và `quarantined_extract` qua CircuitBreaker → `before_emit` → compose → `before_persist` → audit.
    - Chỉ có QR thì bỏ LLM (`status=skipped`, `reason="qr_only"`, D6). Văn bản dán dùng `account_origin = PASTE` và `USER_TYPED` cho cổng R2 (D3). LLM trích số tài khoản khác kết quả quét thì tra rủi ro bổ sung (`reason="llm_entity"`).
    - Mở rộng: receipt (grounding từng món), listing qua Shop_Checker, promo qua Promo_Checker; phát hiện đổi tài khoản với `linked_transaction`, prefill giữ tài khoản người dùng; `prefill` có `account_origin` và `source_integrity_for_flow_a`.
    - HARD thì ghi Risk_Memory cho tài khoản và domain; audit kèm `reasoning_summary`, consent theo `before_persist`; `stage_timings_ms`; debug override chỉ khi debug bật; lỗi không lường trước trả SOFT `RC_LLM_UNAVAILABLE_FALLBACK`, không bao giờ ALLOW.
    - _Requirements: 3.8, 9.1, 9.2, 9.7, 10.1, 10.2, 11.2, 13.1, 13.10, 16.6, 17.5, 17.6, 17.7, 17.8, 17.9, 17.11, 18.1, 20.1, 22.1, 23.1, 23.4, 24.1, 29.1, 29.3, 29.4_
  - [x] 13.3 Cài đặt API Flow B, xác nhận tên và debug extract
    - `api/flow_b.py`: `POST /api/flow-b/check` mặc định NDJSON (`stage2` với `provisional_tier`, `red_alert` khi `BAD_CRC` hoặc SIMO, rồi `final`), `?stream=false` trả JSON; kiểm `text` ≤ 4.000 (`422 CONTENT_TOO_LONG`), `qr_payload` ≤ 512, có ít nhất một trong hai.
    - `api/name.py`: `POST /api/name/inquiry` (giữ `pending_id`, cập nhật số khi người dùng sửa) và `POST /api/name/confirm` (cấp `confirmation_token`, đánh giá lại với `OCR_CONFIRMED_BY_USER`; `confirmed=false` trả `OCR_UNCONFIRMED`).
    - `api/debug.py`: `POST /api/debug/extract`, trả 404 khi debug tắt. Đăng ký router.
    - _Requirements: 9.3, 9.4, 9.8, 17.1, 17.3, 17.4_
  - [x] 13.4 Viết property test LLM không hạ được tier
    - **Property 8: LLM không hạ được tier**
    - **Validates: Requirements 15.3, 15.6**
  - [x] 13.5 Viết property test R2 cho tài khoản OCR
    - **Property 11: R2 – tài khoản OCR chưa xác nhận**
    - Phủ cả Flow A (thiếu token) và Flow B (origin OCR).
    - **Validates: Requirements 9.1, 9.2, 9.5, 9.6, 9.7**
  - [x] 13.6 Viết property test tách vai CaMeL và allowlist
    - **Property 14: Tách vai CaMeL và allowlist tool**
    - **Validates: Requirements 3.8, 4.13, 13.1, 14.1, 14.2, 17.8**
  - [x] 13.7 Viết property test văn bản hiển thị chỉ từ template
    - **Property 23: Văn bản hiển thị chỉ đến từ template**
    - **Validates: Requirements 16.5, 16.6, 16.7**
  - [x] 13.8 Viết property test không hiển thị "100% an toàn"
    - **Property 24: Không bao giờ hiển thị "100% an toàn"**
    - Phủ Flow A, Flow B, context và fast-unblock với template bị monkeypatch.
    - **Validates: Requirements 8.1**
  - [ ]* 13.9 Viết property test thứ tự Trace
    - **Property 15: Thứ tự Trace và ghi luật đã kích hoạt**
    - **Validates: Requirements 6.4, 15.9, 17.7**
  - [ ]* 13.10 Viết property test chặn PII egress
    - **Property 18: Chặn PII egress**
    - **Validates: Requirements 10.2**
  - [ ]* 13.11 Viết property test dán là chuyển điền đúng
    - **Property 27: Dán là chuyển điền đúng**
    - **Validates: Requirements 13.12, 20.1**
  - [ ]* 13.12 Viết property test đổi tài khoản
    - **Property 28: Đổi tài khoản giữ tài khoản người dùng**
    - **Validates: Requirements 17.9**
  - [ ]* 13.13 Viết property test cảnh báo đỏ Stage 2
    - **Property 29: Cảnh báo đỏ ở Stage 2**
    - **Validates: Requirements 17.4**
  - [ ]* 13.14 Viết property test chuyển giao Flow B → Flow A
    - **Property 31: Chuyển giao Flow B → Flow A**
    - **Validates: Requirements 18.1, 18.2**
  - [ ]* 13.15 Viết property test audit tôn trọng đồng thuận
    - **Property 41: Audit tôn trọng đồng thuận**
    - **Validates: Requirements 15.1, 29.3, 29.4**
  - [x] 13.16 Tạo fixture và test kịch bản Flow B
    - `fixtures/scenarios/` T01–T12, T17–T21, T24, T26, T29, T30 theo bảng tóm tắt của design (T22 đã làm ở task 7.9). `tests/scenarios/test_flow_b_scenarios.py` chạy tham số hóa; T29 kiểm `stage2 < 250` và `total < 4600`.
    - Test tích hợp handoff: Flow B HARD cho `1903777888999` TCB rồi Flow A cùng session trả `RC_FLOWB_FLAGGED_RECENTLY`, session khác thì không.
    - _Requirements: 9.7, 10.1, 10.2, 15.2, 15.3, 17.3, 17.6, 17.8, 17.9, 18.1, 18.2, 27.1, 27.2, 33.1, 33.8_

- [x] 14. Checkpoint – backend lõi hoàn chỉnh
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Popup Flow B và F1 "Dán là chuyển" (web)
  - [x] 15.1 Cài đặt service đầu vào của web
    - `services/ndjson.ts` (đọc `ReadableStream` theo dòng), `services/qrDecode.ts` (jsQR trên frame `getUserMedia` hoặc ảnh; camera bị từ chối thì gợi ý chọn ảnh), `services/ocr.ts` (worker tesseract.js `vie` tạo lười và tái sử dụng, `langPath` trỏ `public/tessdata` nếu có).
    - `services/clipboard.ts` `readClipboardOnce(event)` không dùng `setInterval`/`setTimeout` để đọc; `lib/clipboardDedupe.ts` so SHA-256 với lần trước; `lib/digits.ts` tách chữ số.
    - _Requirements: 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_
  - [ ]* 15.2 Viết property test clipboard
    - **Property 46: Clipboard đọc đúng một lần mỗi sự kiện và chống gửi trùng**
    - **Validates: Requirements 3.2, 3.4**
  - [x] 15.3 Nối ScanPopup với Flow B
    - Gửi nội dung dán, clipboard (khi bật: lúc mở popup và `visibilitychange → visible`, lưu `localStorage["guardian.clipboard.optin"]`, `NotAllowedError` thì hiện thông báo và focus ô dán), ảnh qua OCR, QR qua jsQR, đều với `origin` tương ứng. Sự kiện `onPaste` trong ô lệnh chuyển sang Flow B, không gửi Planner.
    - Stage 1 cục bộ trong 100 ms kèm ScanAnimation; nhận `stage2` thì hiện cảnh báo đỏ khi `red_alert`; `final` thì hiện ResultCard + DecisionTrace; stream đứt thì giữ Stage 2 và không mở khóa nút chuyển.
    - NameConfirm (`components/guardian/NameConfirm.tsx`): tên NAPAS sandbox, chữ số tách rời, "Đúng người nhận" gọi `/api/name/confirm`, "Sai, sửa số" gọi lại `/api/name/inquiry`.
    - `explicit_consent_flag` lấy từ ConsentToggle; `linked_transaction` từ nút "Kiểm tra cùng Guardian"; ảnh chat từ ContextElicitation gửi với `origin = CONTEXT_CHAT`; dispatch verdict vào store để Shield_Card cập nhật.
    - _Requirements: 2.5, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 6.11, 8.8, 9.3, 9.4, 9.8, 17.2, 17.4, 17.10, 29.5_
  - [x] 15.4 Cài đặt F1 "Chuyển ngay"
    - `TransferNowButton.tsx`: hiện khi `ui_hints.show_transfer_now`, ẩn khi HARD; thiếu trường thì hiện form theo `missing_fields`.
    - Chạm "Chuyển ngay" mở TransferPage với prefill và `origin_verdict_id`; TwoStepConfirm rồi gửi Flow A với `source_integrity_for_flow_a` (`USER_TYPED` sau xác nhận, hoặc `OCR_CONFIRMED_BY_USER` kèm `confirmation_token`).
    - _Requirements: 20.2, 20.3, 20.4, 20.5, 20.6_
  - [ ]* 15.5 Viết unit test popup Flow B
    - Clipboard bị từ chối thì focus ô dán; kiểm tĩnh `clipboard.ts` không có `setInterval`; NameConfirm tách chữ số; ResultCard ẩn "Chuyển ngay" khi HARD; cảnh báo đỏ hiện trước `final`.
    - _Requirements: 3.3, 3.5, 9.3, 17.4, 20.5_
  - [x] 15.6 Tạo fixture và test kịch bản F1
    - `fixtures/scenarios/` A01 (dán rồi Flow A với `{{prev.prefill}}`) và A02 (5 cụm tiếng lóng); `tests/scenarios/test_f1_scenarios.py`.
    - _Requirements: 13.12, 19.1, 19.2, 19.3, 19.4, 20.1, 33.1, 33.2_

- [x] 16. Checkpoint – demo lõi hoàn chỉnh
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. F2 lệnh bằng câu nói, F4 mua sắm an toàn, F5 khuyến mãi
  - [x] 17.1 Cài đặt phân giải liên hệ
    - `features/contacts.py` `match(query, contacts)`: so không dấu theo tên đầy đủ, tên gọi, alias hoặc dãy từ liên tiếp; trả `RESOLVED`/`AMBIGUOUS`/`NOT_FOUND`.
    - _Requirements: 21.2, 21.3, 21.4_
  - [ ]* 17.2 Viết property test phân giải liên hệ F2
    - **Property 38: Phân giải liên hệ F2**
    - **Validates: Requirements 21.2, 21.3, 21.4, 21.5**
  - [x] 17.3 Cài đặt AssistantService và `POST /api/assistant/command`
    - `control_plane/assistant.py`: chỉ nhận Trusted_Command (≤ 200 ký tự), tokenize PII bằng `Tokenizer`, R1 egress, gọi Planner qua LLMClient (stub hoặc lỗi thì dùng luật Mock Planner, trace `fallback="mock_rules"`), đảo token trong slot.
    - Định tuyến: TRANSFER → contacts (`NEEDS_AMOUNT` khi thiếu tiền, prefill `USER_TYPED`, `message_vi` từ template với `format_vnd` và `display_name` từ danh bạ); SPLIT_BILL/SHOP_CHECK/CHECK_PROMO/CHECK_CONTENT → `OPEN_MODE`; UNKNOWN hoặc Planner lỗi → `REPHRASE`. SPEND_QUERY tạm trả `REPHRASE` cho đến task 18.3.
    - `api/assistant.py`, đăng ký router.
    - _Requirements: 14.1, 14.2, 14.5, 21.1, 21.2, 21.3, 21.4, 21.5_
  - [x] 17.4 Nối ô lệnh của popup với trợ lý
    - Ô lệnh gửi `/api/assistant/command`; `RESOLVED` mở TransferPage điền sẵn rồi đi Flow A; `AMBIGUOUS` hiện `ContactPicker.tsx`; `NOT_FOUND`, `NEEDS_AMOUNT`, `REPHRASE` hiện `message_vi` (kèm ví dụ); `OPEN_MODE` chuyển popup sang mode SHOP/PROMO/SPLIT_BILL/GENERAL để người dùng dán hoặc chụp nội dung vào Flow B.
    - _Requirements: 14.5, 21.2, 21.3, 21.4, 21.5, 21.6, 25.5_
  - [x] 17.5 Hiển thị kết quả F4 và F5 trong ResultCard
    - `extensions.listing`: giá rao, giá tham chiếu, phần trăm rẻ hơn, gợi ý COD / kênh có bảo vệ người mua khi `safe_payment_tips`.
    - `extensions.promo`: thông tin khuyến mãi chính thức lấy từ response (không lấy từ LLM) và trạng thái khớp.
    - _Requirements: 8.5, 23.1, 23.3, 24.1, 24.2_
  - [x] 17.6 Tạo fixture và test kịch bản F2, F4, F5
    - `fixtures/scenarios/` A03, A04, A05, A08, A09, A10; `tests/scenarios/test_f2_f4_f5_scenarios.py`.
    - _Requirements: 21.1, 21.2, 21.3, 21.4, 21.5, 23.2, 23.3, 24.2, 24.3, 24.4, 33.1, 33.2_

- [x] 18. F3 chia hóa đơn, F6 hỏi chi tiêu, F7 hóa đơn bất thường và gói định kỳ
  - [x] 18.1 Cài đặt Bill_Splitter và `POST /api/split/compute`
    - `features/bill_splitter.py`: `split_equal` (phần dư cho người đầu danh sách), `split_by_item` (thứ tự cố định); kiểm `items_sum == receipt_total` (khác thì `TOTAL_MISMATCH`, `mismatch_vnd`, `shares=[]`); `UNASSIGNED_ITEMS` 422; giới hạn 1–20 người, 1–30 món.
    - `api/split.py`: payee `SELF` lấy từ `WalletDataProvider.profile()`; QR mỗi người qua `encode_vietqr` (memo ASCII) rồi `verify_vietqr_emvco`, không đạt thì `qr_payload=null`, `qr_status="QR_ERROR"`. Đăng ký router.
    - Tạo `tests/property/strategies/receipts.py` (`receipts()`).
    - _Requirements: 22.2, 22.3, 22.4, 22.5, 22.6, 22.7_
  - [x] 18.2 Viết property test chia hóa đơn bảo toàn tổng
    - **Property 32: Chia hóa đơn bảo toàn tổng**
    - **Validates: Requirements 22.3, 22.4, 22.7**
  - [x] 18.3 Cài đặt Spend_Query_Engine và `POST /api/spend/query`
    - `features/spend_query.py` `compute(txns, slots, now)` thuần theo bảng category/period/metric của design (series theo ngày hoặc theo tuần cho `LAST_3_MONTHS`, `COMPARE_PREVIOUS`); `answer_vi` từ template.
    - `api/spend.py`; AssistantService định tuyến SPEND_QUERY → `SPEND_ANSWER`. Đăng ký router.
    - _Requirements: 25.1, 25.2, 25.3, 25.4, 25.5_
  - [ ]* 18.4 Viết property test hỏi chi tiêu
    - **Property 33: Hỏi chi tiêu khớp hàm tham chiếu**
    - **Validates: Requirements 25.2, 25.3**
  - [x] 18.5 Cài đặt Bill_Monitor và nối vào wallet summary
    - `features/bill_monitor.py` `alerts(bills, subs, now)`: spike bằng số nguyên (`current*3*100 >= 130*sum3`, bỏ qua khi ít hơn 3 kỳ), `RENEWAL_SOON` trong 0–7 ngày, `UNUSED_SUBSCRIPTION` ≥ 30 ngày. `features/wallet_summary.py` trả `alerts` từ Bill_Monitor.
    - _Requirements: 26.1, 26.2, 26.3, 26.4_
  - [ ]* 18.6 Viết property test Bill_Monitor
    - **Property 34: Bill_Monitor**
    - **Validates: Requirements 26.1, 26.2, 26.3, 26.4**
  - [x] 18.7 Cài đặt UI chia hóa đơn, câu trả lời chi tiêu và cảnh báo
    - `components/split/BillSplit.tsx` và `SplitShareCard.tsx`: chụp hóa đơn ở mode SPLIT_BILL → OCR → Flow B → danh sách món sửa được, thêm người, gán món hoặc chia đều, hiện chênh lệch khi `TOTAL_MISMATCH`, QR bằng `qrcode` cho từng người, ẩn QR lỗi.
    - `components/guardian/SpendAnswer.tsx`: câu trả lời template và biểu đồ nhỏ theo ngày hoặc tuần.
    - `AlertsList` hiển thị BILL_SPIKE (phần trăm tăng), RENEWAL_SOON (số tiền, ngày), UNUSED_SUBSCRIPTION (gợi ý hủy).
    - _Requirements: 22.1, 22.2, 22.6, 22.7, 25.4, 26.1, 26.2, 26.3_
  - [x] 18.8 Tạo fixture và test kịch bản F3, F6, F7
    - `fixtures/receipts/lau_3_nguoi.txt`; `fixtures/scenarios/` A06 (3 case), A07 (thêm hàm tham chiếu `matches_reference` trong `eval/matcher.py`), A11, A12; `tests/scenarios/test_f3_f6_f7_scenarios.py`.
    - _Requirements: 22.1, 22.3, 22.4, 22.7, 25.1, 25.3, 26.1, 26.2, 26.3, 26.4, 33.1, 33.2_

- [x] 19. Calm Shield, TTS, chuyển sang app ngân hàng và PWA
  - [x] 19.1 Cài đặt Calm Shield và TTS
    - `components/guardian/CalmShield.tsx`: bật theo `ui_hints.calm_shield`; chữ `text-[1.125rem]`–`text-[1.25rem]` tương phản cao, tối đa 3 bullet, ẩn khuyến mãi; nút chính "Tạm dừng & xác minh", nút tiếp tục dạng mờ; banner "MoMo không bao giờ gọi điện yêu cầu bạn chuyển tiền"; nút `tel:` tới hotline và Trusted_Contact. Bọc ResultCard trong ScanPopup và TransferPage.
    - `services/tts.ts`: giọng `vi-VN`, `rate = 0.8`, chờ `voiceschanged` tối đa 1 s; không có giọng thì ẩn nút đọc.
    - _Requirements: 27.1, 27.2, 27.3, 27.4, 27.7, 27.8, 27.9, 27.10_
  - [x] 19.2 Cài đặt Bank_Handoff và `POST /api/qr/encode`
    - `api/qr.py`: `purpose ∈ {BANK_HANDOFF, SPLIT_BILL}`; BANK_HANDOFF cần `verdict_id` cùng session, HARD (hoặc không thấy verdict) → `403 HANDOFF_BLOCKED_HARD_HOLD` + audit `HANDOFF_DENIED`, SOFT chưa `cooldown_completed` → `409 COOLDOWN_NOT_FINISHED`; payload tự kiểm bằng `verify_vietqr_emvco` (lỗi → `500 ENCODER_SELF_CHECK_FAILED`); memo qua `fold_ascii`; `deeplink` từ `deeplink_template` nếu khác null.
    - `components/transfer/BankHandoff.tsx`: hiện/tải QR, deep link khi có; vô hiệu khi `handoff_allowed = false`. Gắn vào ResultCard và TransferPage.
    - _Requirements: 28.1, 28.2, 28.3, 28.4_
  - [ ]* 19.3 Viết property test UI hints
    - **Property 39: UI hints**
    - **Validates: Requirements 20.2, 20.6, 23.3, 27.1, 27.2**
  - [ ]* 19.4 Viết property test HARD_HOLD chặn Bank_Handoff
    - **Property 40: HARD_HOLD chặn Bank_Handoff**
    - **Validates: Requirements 20.5, 28.1, 28.3, 28.4**
  - [x] 19.5 Cài đặt PWA và Web Share Target
    - `public/manifest.webmanifest` có `share_target` (POST, multipart, text/url/ảnh) và icon; `public/sw.js` chặn `POST /share-target`, lưu vào Cache Storage `share-inbox`, `Response.redirect("/?share=1", 303)`; chỉ đăng ký service worker ở bản build production.
    - `services/share.ts` đọc hộp thư; `App.tsx` thấy `?share=1` thì mở popup, OCR ảnh nếu có và gửi Flow B với `origin = SHARE_TARGET`.
    - _Requirements: 3.9, 32.5_
  - [x]* 19.6 Viết unit test Calm Shield, TTS và manifest
    - CalmShield: tối đa 3 bullet, banner, nút `tel:`; `tts.ts` với `speechSynthesis` giả (rate 0.8, ẩn khi không có vi-VN); `web/tests/manifest.test.ts` kiểm `share_target` nhận text, url, image.
    - _Requirements: 27.3, 27.7, 27.8, 27.9, 27.10, 32.5_

- [x] 20. Tài liệu luồng và thuật ngữ
  - [x] 20.1 Viết `docs/FLOWS_AND_GLOSSARY.md`
    - Sơ đồ mermaid cho Flow A, Flow B (progressive disclosure, circuit breaker), Risk_Memory và từng tính năng F1–F7; bảng Thật / Sandbox; bảng thuật ngữ (APP fraud, VietQR, EMVCo, NAPAS 247, SIMO, GNN mule, CaMeL, AgentSpec, Thông tư 50, Luật 91/2025); danh sách mọi Reason_Code kèm `meaning_vi` từ registry; danh sách Stop_Code; lộ trình mobile (Android share sheet, NotificationListener opt-in, bong bóng `SYSTEM_ALERT_WINDOW`, iOS Share Extension, lý do không dùng Accessibility Service).
    - _Requirements: 32.1, 32.2, 32.3, 32.4_
  - [x] 20.2 Viết test registry và tài liệu
    - `tests/docs/test_reason_codes_registry.py`: mọi mã trong REGISTRY xuất hiện trong `docs/FLOWS_AND_GLOSSARY.md`; mọi chuỗi `RC_[A-Z0-9_]{3,40}` trong `backend/guardian/**/*.py` có trong REGISTRY; chỉ `reason_codes.py` khai báo hằng `RC_`.
    - `tests/docs/test_docs.py`: có mermaid cho Flow A, Flow B, Risk_Memory, F1–F7; có bảng Thật/Sandbox, bảng thuật ngữ và mục lộ trình mobile.
    - _Requirements: 30.1, 30.4, 30.5, 32.1, 32.2, 32.3, 32.4_

- [x] 21. Eval harness và trang "Kịch bản demo"
  - [x] 21.1 Cài đặt Eval_Harness và API eval
    - `eval/run_suite.py --runs N --k K`: chạy mỗi fixture N lần, mỗi lần một session mới, qua route handler in-process; `eval/report.py` tính pass^k = trung bình `C(c_i,k)/C(n,k)` tổng và theo nhóm (red-risk, injection, PII, cold-start, assistant), danh sách không đạt kèm mismatch, p95 `latency_ms` Flow A và p95 `stage2` Flow B, tên provider, thời điểm, câu ranh giới bằng chứng cố định; ghi `eval_report.md`.
    - `api/eval.py`: `GET /api/eval/scenarios` (ẩn `debug` khi debug tắt, đánh dấu `requires_debug`), `POST /api/eval/run`. Đăng ký router.
    - _Requirements: 33.3, 33.4, 33.5, 33.6, 33.7_
  - [ ]* 21.2 Viết property test công thức pass^k
    - **Property 43: Công thức pass^k**
    - **Validates: Requirements 33.3**
  - [x] 21.3 Viết test độ phủ fixture và hồi quy toàn bộ kịch bản
    - `tests/scenarios/test_fixtures.py`: đủ T01–T31 và A01–A12; A01–A12 phủ F1–F7; tier và mã kỳ vọng của T01–T31 khớp Phụ lục A đọc từ `requirements.md`; `gen_qr.py` tái tạo đúng `qr_samples.json`.
    - `tests/scenarios/test_suite_mock.py`: chạy harness `--runs 1` với MockLLM, mọi kịch bản đạt.
    - _Requirements: 31.6, 33.1, 33.2, 33.5, 33.8_
  - [x] 21.4 Cài đặt DemoScenariosPage
    - `lib/expectation.ts` mirror `eval/matcher.py`; `pages/DemoScenariosPage.tsx` liệt kê kịch bản từ `GET /api/eval/scenarios` (mô tả, kết quả mong đợi), nút "Chạy" gọi trực tiếp endpoint nghiệp vụ, "Chạy tất cả" chạy lần lượt và hiện số đạt/tổng, kịch bản không đạt hiện tier và mã thực tế cạnh kỳ vọng. Verdict từ trang này gắn `from_demo` để không tính vào Shield_Card.
    - _Requirements: 34.1, 34.2, 34.3, 34.4_
  - [ ]* 21.5 Viết property test matcher Python/TS
    - **Property 44: Ngữ nghĩa matcher và tính tương đương Python/TS**
    - Sinh và commit `fixtures/scenarios/_matcher_vectors.json` bằng Hypothesis; test Python và `web/tests/expectation.test.ts` cùng chạy trên bộ vector.
    - **Validates: Requirements 34.4**

- [x] 22. Checkpoint cuối – toàn bộ test và eval đạt
  - Ensure all tests pass, ask the user if questions arise.
  - Chạy `cd backend; pytest`, `cd backend; python -m eval.run_suite --runs 5 --k 3` (pass^3 = 100% với MockLLM) và `cd web; npx vitest --run`.

- [x] 23. Tiện ích Chrome – lớp Guardian trên nền tảng khác
  - [x] 23.1 Backend nhận origin của tiện ích
    - Thêm `EXTENSION_SELECTION`, `EXTENSION_PAGE_TEXT` vào `ContentOrigin`, xử lý như PASTE (`account_origin = PASTE`); kịch bản `fixtures/scenarios/A13.json` (T01 qua `EXTENSION_SELECTION` → HARD_HOLD); cập nhật docs và test.
    - _Requirements: 35.10_
  - [x] 23.2 Khung tiện ích MV3
    - `extension/` (Vite, React, TS strict, Tailwind), `manifest.json`, service worker, trang tùy chọn, session uuid v4 và địa chỉ backend trong `chrome.storage.local`; `npm run build` ra `extension/dist`.
    - _Requirements: 35.1, 35.8_
  - [x] 23.3 Bong bóng và lớp quét trên trang
    - Shadow DOM, bong bóng kéo thả, lấy selection hoặc văn bản hiển thị, hiệu ứng quét, ResultPanel, Calm Shield rút gọn, menu chuột phải, phím tắt Alt+G.
    - _Requirements: 35.2, 35.3, 35.4, 35.5, 35.6, 35.7_
  - [x] 23.4 Streaming và xử lý lỗi qua service worker
    - Port `guardian-check`, NDJSON `stage2` → `final`; lỗi mạng hoặc backend → thông báo tiếng Việt, không hiển thị ALLOW.
    - _Requirements: 35.5, 35.8, 35.9_
  - [x] 23.5 Trang chat giả để trình diễn
    - `web/public/demo-chat.html` giao diện kiểu Zalo với tin nhắn T01, T07, A01.
    - _Requirements: 35.1_
  - [x] 23.6 Test và build tiện ích
    - vitest cho `capture.ts`, `ndjson.ts`, settings, ResultPanel (không có "100% an toàn", chỉ text từ verdict), lỗi backend; `npm run build` thành công; README hướng dẫn "Load unpacked".
    - _Requirements: 35.3, 35.4, 35.6, 35.9_
  - [ ]* 23.7 Quét ảnh chụp màn hình
    - `chrome.tabs.captureVisibleTab` + OCR tesseract.js đóng gói cục bộ, gửi với origin OCR.

- [x] 24. Checkpoint – tiện ích Chrome
  - Chạy toàn bộ test backend, web, extension và eval; build extension.

- [x] 25. Sửa lỗi từ thử nghiệm thật: tin "người quen đổi tài khoản, nhờ chuyển gấp"
  - [x] 25.1 Không hiển thị kết luận sơ bộ ALLOW ở Stage 2 (web)
    - Stage 2 chỉ hiện "Đang phân tích tiếp…" hoặc cảnh báo đỏ khi `red_alert`; không hiện nhãn xanh trước khi có `final`; stream đứt thì hiện thông báo lỗi trung tính, không hiện màu xanh.
    - _Requirements: 16.6, 17.2, 17.4_
  - [x] 25.2 Nhận diện "đổi tài khoản + chuyển gấp" rõ ràng hơn
    - Mở rộng luật MockLLM và heuristic dự phòng (đổi tài khoản, tài khoản mới, stk mới, chuyển vào tài khoản này, nick bị hack, mượn tạm); kết quả SOFT_FRICTION với `RC_ACCOUNT_SWAP_REQUEST`, cooling-off 30 s và câu hỏi System 2 "gọi điện hoặc gọi video qua số cũ để xác minh"; kịch bản `A14` và test.
    - _Requirements: 15.11, 16.4, 33.2_
  - [x] 25.3 Hướng dẫn bật LLM thật
    - README và `.env.example`: cách đặt `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`; nêu rõ MockLLM chỉ là luật từ khóa.
    - _Requirements: 12.1, 12.5_

- [x] 26. Provider LLM tương thích OpenAI (OpenCode và các nhà cung cấp khác)
  - [x] 26.1 `OpenAICompatClient` và cấu hình
    - `llm/openai_compat_client.py`, `LLM_PROVIDER=openai_compat`, biến `OPENAI_COMPAT_*`, chế độ JSON `json_schema`/`tools`/`json_object`, ánh xạ lỗi 401/403/429/5xx → `ERROR`, không log khóa; health trả provider + model; test với HTTP giả; README.
    - _Requirements: 36.1, 36.2, 36.3, 36.4, 36.5_

- [x] 27. Kiểm tra một chạm, giảm thao tác dán
  - [x] 27.1 Nút "Dán & kiểm tra" trong popup web
    - _Requirements: 37.1_
  - [x] 27.2 "Tự động bảo vệ" trong tiện ích Chrome
    - Bật theo tên miền (mặc định tắt), MutationObserver theo dõi tin nhắn mới, chấm điểm cục bộ không gọi mạng, nhãn "Guardian: nên kiểm tra" cạnh tin nhắn, chạm nhãn gửi Flow B; trang chat giả có tin nhắn mới xuất hiện để trình diễn; test.
    - _Requirements: 37.2, 37.3, 37.4_

- [x] 28. Quét khung hội thoại một chạm và tài liệu đầu vào / đầu ra cho người dùng
  - [x] 28.1 Quét khung hội thoại chính trong tiện ích
    - Xác định vùng hội thoại chính, lấy tối đa 15 tin gần nhất, bỏ thanh bên/điều hướng/ô nhập/mốc thời gian; dự phòng về cách cũ; hiện "Guardian đã đọc N tin nhắn" và danh sách xem lại; test và cập nhật trang chat giả cho có thanh bên.
    - _Requirements: 38.1, 38.2, 38.3, 38.4_
  - [x] 28.2 Mục "Người dùng đưa vào gì, nhận lại gì" trong `docs/FLOWS_AND_GLOSSARY.md`
    - Bảng cho từng điểm vào (web, tiện ích, chia sẻ, QR, ảnh) và từng tính năng F1–F7, Flow A, Flow B: đầu vào, đầu ra người dùng thấy, hành động tiếp theo, dữ liệu rời thiết bị; test tài liệu.
    - _Requirements: 38.5_

## Notes

- Task có dấu `*` là tùy chọn và có thể bỏ qua để kịp MVP. Theo yêu cầu, 18 property ưu tiên của design (1, 3, 6, 7, 8, 9, 11, 12, 13, 14, 16, 17, 22, 23, 24, 25, 30, 32) là sub-task bắt buộc. Property 25 có hai sub-task (Python 2.5 và TypeScript 4.2) vì design kiểm nó trên hai runtime. Các property còn lại là tùy chọn; nếu chưa làm, đánh dấu `@pytest.mark.skip(reason="P1 – chưa hiện thực")` thay vì xóa.
- Fixture kịch bản và test tương ứng nằm ngay sau tính năng của chúng (7.9, 13.16, 15.6, 17.6, 18.8) và là bắt buộc, vì Req 33.5 cần pass^3 = 100%.
- Thứ tự ưu tiên: task 1–16 là lõi demo. Task 17–22 chỉ bắt đầu sau checkpoint 16.
- Quyết định đã đưa ra khi lập kế hoạch:
  - `HardSource` đặt trong `schemas/enums.py` và re-export từ `policy/floors.py` để tránh vòng import giữa `reason_codes.py` và `floors.py`.
  - Thêm `stores/shield_stats.py` cho bộ đếm ShieldStats (design có store này nhưng chưa nêu file).
  - Policy_Engine được làm theo hai đợt: luật Flow A ở task 7.1, luật Flow B ở task 12.1. Shop_Checker và Promo_Checker làm ở task 12.2 (trước Flow B) vì T04 và T12 cần chúng; phần UI F4/F5 để sau checkpoint lõi.
  - Scenario loader và matcher làm sớm ở task 7.8 để test kịch bản chạy được ngay theo từng tính năng; harness pass^k làm ở task 21.
  - `fixtures/amount_vectors.json` là nguồn vector chung để bản Python và TS của Property 25 cho cùng chuỗi.
  - `UNKNOWN_SUSPICIOUS` không thuộc nhóm playbook HARD (tối đa SOFT_FRICTION), khớp design D2/D7 và Req 15.7/15.11/17.11.
- Checkpoint 9 (sau Flow A), 14 (sau backend lõi), 16 (sau demo lõi) và 22 (cuối) giúp phát hiện lỗi sớm.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["1.4", "2.1", "2.4"] },
    { "id": 2, "tasks": ["2.2", "2.5", "2.6", "2.7", "3.1"] },
    { "id": 3, "tasks": ["2.3", "3.2", "4.1"] },
    { "id": 4, "tasks": ["3.3", "4.2", "5.1"] },
    { "id": 5, "tasks": ["3.4", "4.3", "5.2", "5.3", "5.4", "5.5", "5.6"] },
    { "id": 6, "tasks": ["3.5", "3.6", "4.4", "5.7"] },
    { "id": 7, "tasks": ["4.5", "4.6", "4.7", "5.8", "6.1"] },
    { "id": 8, "tasks": ["6.2", "6.3"] },
    { "id": 9, "tasks": ["6.4", "6.6"] },
    { "id": 10, "tasks": ["6.5", "6.7", "6.8", "7.1"] },
    { "id": 11, "tasks": ["7.2"] },
    { "id": 12, "tasks": ["7.3", "7.4", "7.5", "7.6", "7.8"] },
    { "id": 13, "tasks": ["7.7", "7.9", "8.1"] },
    { "id": 14, "tasks": ["8.2"] },
    { "id": 15, "tasks": ["9"] },
    { "id": 16, "tasks": ["10.1", "10.4", "10.5", "11.1"] },
    { "id": 17, "tasks": ["10.2", "10.3", "10.6", "10.7", "11.2"] },
    { "id": 18, "tasks": ["10.8", "11.3"] },
    { "id": 19, "tasks": ["10.9", "11.4", "11.5", "11.7"] },
    { "id": 20, "tasks": ["11.6", "11.8", "12.1", "12.2"] },
    { "id": 21, "tasks": ["12.3", "12.4", "12.5", "12.6", "13.1"] },
    { "id": 22, "tasks": ["13.2"] },
    { "id": 23, "tasks": ["13.3"] },
    { "id": 24, "tasks": ["13.4", "13.5", "13.6", "13.7", "13.8", "13.9", "13.10", "13.11", "13.12", "13.13", "13.14", "13.15", "13.16"] },
    { "id": 25, "tasks": ["14"] },
    { "id": 26, "tasks": ["15.1"] },
    { "id": 27, "tasks": ["15.2", "15.3"] },
    { "id": 28, "tasks": ["15.4"] },
    { "id": 29, "tasks": ["15.5", "15.6"] },
    { "id": 30, "tasks": ["16"] },
    { "id": 31, "tasks": ["17.1", "17.5"] },
    { "id": 32, "tasks": ["17.2", "17.3"] },
    { "id": 33, "tasks": ["17.4", "18.1"] },
    { "id": 34, "tasks": ["17.6", "18.2", "18.3"] },
    { "id": 35, "tasks": ["18.4", "18.5"] },
    { "id": 36, "tasks": ["18.6", "18.7", "18.8"] },
    { "id": 37, "tasks": ["19.1"] },
    { "id": 38, "tasks": ["19.2", "19.3"] },
    { "id": 39, "tasks": ["19.4", "19.5"] },
    { "id": 40, "tasks": ["19.6", "20.1"] },
    { "id": 41, "tasks": ["20.2", "21.1"] },
    { "id": 42, "tasks": ["21.2", "21.3", "21.4"] },
    { "id": 43, "tasks": ["21.5"] },
    { "id": 44, "tasks": ["22"] }
  ]
}
```
