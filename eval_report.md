# Eval report

- LLM provider: `mock`
- Thời điểm: 2026-11-22T11:56:33+00:00
- Số lần chạy mỗi kịch bản (n): 5
- k: 3
- Số kịch bản: 45

> pass^k với MockLLM chỉ chứng minh Control Plane chạy đúng; độ ổn định của LLM thật phải đo lại với provider thật.

## pass^3

Tổng: **100.0%**

| Nhóm | Số kịch bản | pass^3 |
|---|---|---|
| red-risk | 25 | 100.0% |
| injection | 5 | 100.0% |
| PII | 1 | 100.0% |
| cold-start | 2 | 100.0% |
| assistant | 12 | 100.0% |

## Độ trễ

- Flow A `latency_ms` p95 (70 mẫu): 9 ms (đạt mục tiêu < 200 ms)
- Flow B `stage2` p95 (195 mẫu): 3 ms (đạt mục tiêu < 250 ms)

Độ trễ đo trên máy local với Sandbox_Provider, không đại diện cho production.

## Kịch bản không đạt

Không có. Mọi kịch bản đạt 5/5 lần.
