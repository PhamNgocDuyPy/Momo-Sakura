# CLAUDE.md – Hướng dẫn cho AI agent làm việc trong repo MoMo Guardian

## Dự án là gì

MoMo Guardian là trợ lý thanh toán và mua sắm có lớp chống lừa đảo APP (Authorized Push Payment) tích hợp sẵn, dự thi MoMo TechDay 2026. Bản hiện tại là web mobile-first; app mobile làm sau, dùng chung backend.

## Nguồn sự thật (đọc trước khi code)

1. `MoMo Guardian — Technical Verification & Architecture Specification (v2.1).pdf` – kiến trúc gốc (Flow A/B, CaMeL, AgentSpec R1–R6, schema §7.1, kịch bản T01–T31).
2. `PLAN.md` – kế hoạch triển khai đã chốt, bảng Thật/Sandbox.
3. `.kiro/specs/momo-guardian-web/` – requirements, design, tasks. Khi có mâu thuẫn, spec này thắng PLAN.md.
4. `docs/FLOWS_AND_GLOSSARY.md` – luồng và thuật ngữ nghiệp vụ.

## Stack

- Backend: Python 3.11+, FastAPI, Pydantic v2, pytest. Thư mục `backend/`.
- Web: Vite, React, TypeScript (strict), Tailwind, Recharts, jsQR, tesseract.js, `qrcode`, Framer Motion. Thư mục `web/`.
- Dữ liệu sandbox và kịch bản test: `fixtures/`. Tài liệu: `docs/`.

## Lệnh thường dùng (Windows PowerShell)

Các lệnh chính xác sẽ được chốt trong README khi dựng khung. Nguyên tắc:
- Không chạy dev server hay watcher trong agent; để người dùng tự chạy.
- Test chạy một lần: `pytest` (backend), `npx vitest --run` (web).
- Dùng `;` thay cho `&&` trong PowerShell 5.

## Bất biến bảo mật – KHÔNG được vi phạm

1. **Flow A không gọi LLM.** Cổng chặn lúc thanh toán chỉ dùng luật, điểm rủi ro, SIMO/GNN (sandbox) và `risk_memory`.
2. **Tách vai CaMeL.** Lệnh người dùng gõ → Planner. Mọi nội dung dán/OCR/QR/clipboard là UNTRUSTED → chỉ Quarantined LLM. Quarantined LLM không có tool.
3. **Đầu ra LLM bị ràng buộc schema.** Pydantic `extra="forbid"`, enum/boolean/số nguyên/chuỗi có `max_length`. Sai schema hoặc `stop_reason` bất thường → `UNKNOWN_SUSPICIOUS`.
4. **UI không hiển thị văn bản tự do do LLM sinh từ dữ liệu không tin cậy.** Bullet bằng chứng và câu hỏi System 2 lấy từ template tiếng Việt. `reasoning_summary` chỉ vào audit log.
5. **Control Plane Python giữ quyền gọi tool.** LLM không bao giờ trực tiếp gọi `verify_vietqr_emvco`, `lookup_recipient_risk_and_simo`, v.v.
6. **R1:** che PII (CCCD 12 số, CMND 9 số, SĐT, OTP, tên) trước mọi lời gọi LLM; chỉ lưu bằng chứng khi `explicit_consent_flag == True` (Luật 91/2025).
7. **R2:** không tra rủi ro người nhận khi `source_integrity == "OCR_UNCONFIRMED"`.
8. **R3:** CPU pre-filter chỉ nâng lên SOFT_FRICTION; HARD_HOLD chỉ khi `contains_prompt_injection == true` hoặc phát hiện hijack control plane.
9. **R4:** SIMO hit hoặc `gnn_mule_score >= 0.85` → HARD_HOLD; LLM không được hạ cấp.
10. **R5:** structuring theo Thông tư 50 (9–10M, tổng ≥20M/24h, hoặc cue `SPLIT_TRANSFER_UNDER_10M`) → tối thiểu SOFT_FRICTION.
11. **R6:** có QR payload thì trace phải chứa `verify_vietqr_emvco`, nếu không thì dừng.
12. **Honesty invariant:** không bao giờ hiển thị "100% an toàn". Người nhận lần đầu + không có ngữ cảnh → `RC_COLD_START_NEEDS_CONTEXT`.
13. **HARD_HOLD chặn** mọi deep link / xuất QR sang app ngân hàng.
14. **Không commit key.** Cấu hình qua `.env`; luôn cập nhật `.env.example`.

## Quy ước code

- Mã lý do theo pattern `^RC_[A-Z0-9_]{3,40}$`, khai báo tập trung ở một module duy nhất; mọi mã phải có trong `docs/FLOWS_AND_GLOSSARY.md` (có test kiểm tra).
- Dữ liệu không khả thi (SIMO, GNN, NAPAS, lịch sử ví) chỉ đi qua interface `RiskDataProvider` / `WalletDataProvider`. Không hard-code dữ liệu sandbox trong logic nghiệp vụ.
- LLM chỉ đi qua interface `LLMClient`; chọn bằng `LLM_PROVIDER=mock|anthropic|bedrock`. Mặc định `mock` để chạy không cần key.
- Mọi verdict ghi audit (`audit.jsonl`) kèm reason code, rule đã kích hoạt, timestamp và trace.
- Text hiển thị cho người dùng bằng tiếng Việt; code, tên biến, comment bằng tiếng Anh.
- Python: type hints đầy đủ, async cho endpoint. Web: component nhỏ, không `any`.
- Không thêm tính năng ngoài spec khi chưa hỏi.

## Kiểm thử

- Mỗi kịch bản T01–T31 và A01–A12 có fixture trong `fixtures/scenarios/` và test tương ứng.
- Eval harness: `backend/eval/run_suite.py --runs 5 --k 3` tính pass^3 (τ-bench).
- Thay đổi policy hoặc schema phải chạy lại toàn bộ test trước khi báo xong.

## Evidence boundary

pass^3 trên MockLLM chỉ chứng minh Control Plane đúng. Không trình bày nó như độ ổn định của LLM thật. Số liệu latency/chi phí trong PDF là mô phỏng trước triển khai.