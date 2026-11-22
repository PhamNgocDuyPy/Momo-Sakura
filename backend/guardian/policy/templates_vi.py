"""Vietnamese display templates. Only text defined here (or in the reason-code registry) reaches the UI.

Templates that take values expect already formatted strings (``format_vnd`` for money,
``display_name`` from the sandbox contact list). Nothing here is derived from LLM output.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from guardian.schemas.enums import SpendMetric

# System 2 questions per playbook (each <= 180 chars, at most 2 are shown).
SYSTEM2_QUESTIONS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "DEEPFAKE_RELATIVE_EMERGENCY": (
            "Bạn đã gọi lại cho người thân bằng số điện thoại quen thuộc chưa?",
            "Tài khoản nhận có đúng là tài khoản của chính người thân bạn không?",
        ),
        "IMPERSONATE_AUTHORITY_VNEID": (
            "Bạn có được yêu cầu chuyển tiền để 'xác minh' hay 'phục vụ điều tra' không?",
            "Bạn đã gọi đường dây nóng của cơ quan đó, hoặc đến trụ sở để hỏi trực tiếp chưa?",
        ),
        "ACCOUNT_SWAP": (
            "Bạn đã gọi điện hoặc gọi video cho người này qua số điện thoại cũ để xác minh chưa?",
        ),
        "GREY_ZONE": (
            "Bạn biết người nhận này ngoài đời hoặc qua kênh đáng tin không?",
            "Bạn đã kiểm tra tên chủ tài khoản khớp với người bạn định trả tiền chưa?",
        ),
    }
)

# Error envelope messages: {"error": CODE, "message_vi": ERRORS[CODE]}.
ERRORS: Mapping[str, str] = MappingProxyType(
    {
        "SESSION_REQUIRED": "Phiên làm việc không hợp lệ. Hãy tải lại trang để tiếp tục.",
        "VALIDATION_ERROR": "Dữ liệu gửi lên chưa đúng định dạng. Bạn kiểm tra lại rồi thử nhé.",
        "CONTENT_TOO_LONG": "Nội dung quá dài. Hãy rút gọn hoặc chia thành nhiều phần.",
        "DEBUG_DISABLED": "Chức năng gỡ lỗi đang tắt.",
        "FLOW_A_ERROR": "Chưa kiểm tra được, hãy thử lại.",
        "COMPOSER_INVALID": "Guardian gặp lỗi, đừng chuyển tiền lúc này.",
        "TOOL_NOT_ALLOWED": "Guardian gặp lỗi nội bộ, đừng chuyển tiền lúc này.",
        "VERDICT_NOT_FOUND": "Không tìm thấy kết quả kiểm tra này. Bạn kiểm tra lại giao dịch nhé.",
        "IDENTITY_CHECK_FAILED": "Mã xác thực chưa đúng. Bạn kiểm tra lại rồi thử nhé.",
        "FAST_UNBLOCK_NOT_ALLOWED": "Giao dịch này không thể mở chặn nhanh.",
        "CONTEXT_NOT_APPLICABLE": "Giao dịch này không cần bổ sung ngữ cảnh.",
        "HANDOFF_BLOCKED_HARD_HOLD": (
            "Giao dịch đang bị tạm giữ vì rủi ro cao nên Guardian không tạo mã chuyển tiền."
        ),
        "TRANSFER_BLOCKED_HARD_HOLD": "Giao dịch đang bị tạm giữ vì rủi ro cao nên không thể thực hiện.",
        "COOLDOWN_NOT_FINISHED": (
            "Bạn cần chờ hết thời gian suy nghĩ và trả lời các câu hỏi trước khi chuyển."
        ),
        "PENDING_NOT_FOUND": "Phiên xác nhận tên đã hết hạn. Bạn kiểm tra lại nội dung nhé.",
        "UNASSIGNED_ITEMS": "Còn món chưa được gán cho người nào. Bạn gán đủ các món rồi thử lại nhé.",
        "ENCODER_SELF_CHECK_FAILED": "Guardian không tạo được mã QR hợp lệ. Bạn đừng dùng mã này.",
        "QR_ERROR": "Không tạo được mã QR cho khoản này.",
        "INTERNAL_ERROR": "Có lỗi xảy ra. Hãy thử lại sau.",
    }
)

# F2 (assistant command) templates.
F2_RESOLVED = "Đã điền sẵn giao dịch {amount} cho {name}. Bạn kiểm tra lại rồi xác nhận nhé."
F2_AMBIGUOUS = "Có {count} người tên \"{query}\" trong danh bạ. Bạn chọn đúng người nhận nhé."
F2_NOT_FOUND = (
    "Guardian không tìm thấy \"{query}\" trong danh bạ. Bạn nhập số tài khoản và ngân hàng để chuyển nhé."
)
F2_NEEDS_AMOUNT = "Bạn muốn chuyển bao nhiêu cho {name}?"
F2_REPHRASE = "Guardian chưa hiểu yêu cầu này. Bạn thử diễn đạt lại theo các ví dụ dưới đây nhé."
F2_REPHRASE_EXAMPLES: tuple[str, ...] = (
    "chuyển 200k cho Minh tiền cà phê",
    "tháng này cà phê hết bao nhiêu?",
    "chia hóa đơn lẩu cho 3 người",
)
F2_OPEN_MODE: Mapping[str, str] = MappingProxyType(
    {
        "SPLIT_BILL": "Hãy dán hoặc chụp hóa đơn để Guardian chia tiền giúp bạn.",
        "SHOP": "Hãy dán tin bán hàng hoặc đường link để Guardian kiểm tra giúp bạn.",
        "PROMO": "Hãy dán nội dung khuyến mãi để Guardian đối chiếu với danh sách chính thức.",
        "GENERAL": "Hãy dán hoặc chụp nội dung bạn muốn Guardian kiểm tra.",
    }
)

# F6 (spend answer) templates: period/category are Vietnamese labels, values are pre-formatted.
F6_ANSWERS: Mapping[SpendMetric, str] = MappingProxyType(
    {
        SpendMetric.TOTAL: "{period} bạn đã chi {value} cho {category} ({count} giao dịch).",
        SpendMetric.COUNT: "{period} bạn có {value} lần chi cho {category}.",
        SpendMetric.AVERAGE_PER_TXN: "{period} mỗi lần chi cho {category} trung bình {value}.",
        SpendMetric.AVERAGE_PER_DAY: "{period} mỗi ngày bạn chi trung bình {value} cho {category}.",
        SpendMetric.MAX_TXN: "{period} lần chi lớn nhất cho {category} là {value}.",
        SpendMetric.COMPARE_PREVIOUS: "{period} bạn đã chi {value} cho {category}, kỳ trước là {previous}. {delta}",
    }
)
F6_ALL_CATEGORIES = "tất cả danh mục"
F6_DELTA_UP = "Tăng {percent}% so với kỳ trước."
F6_DELTA_DOWN = "Giảm {percent}% so với kỳ trước."
F6_DELTA_SAME = "Không đổi so với kỳ trước."
F6_DELTA_UNKNOWN = "Kỳ trước chưa có khoản chi nào để so sánh."
F6_NO_DATA = "{period} bạn chưa có khoản chi nào cho {category}."
F6_REPHRASE = (
    "Guardian chỉ trả lời được câu hỏi về chi tiêu theo danh mục và khoảng thời gian có sẵn. "
    "Bạn thử hỏi lại theo ví dụ dưới đây nhé."
)
F6_REPHRASE_EXAMPLES: tuple[str, ...] = (
    "tháng này cà phê hết bao nhiêu?",
    "tuần trước đi grab mấy lần?",
)

# Safe payment hints (Shop_Checker / deposit cues / ONLINE_ORDER context).
SAFE_PAYMENT_TIPS: tuple[str, ...] = (
    "Ưu tiên thanh toán khi nhận hàng (COD) để kiểm tra hàng trước khi trả tiền.",
    "Nếu mua online, hãy dùng kênh thanh toán có bảo vệ người mua của sàn thay vì chuyển khoản trực tiếp.",
    "Đừng đặt cọc hay trả phí trước cho người bán chưa xác minh.",
)

# Calm Shield.
CALM_SHIELD_BANNER = "MoMo không bao giờ gọi điện yêu cầu bạn chuyển tiền"
CALM_SHIELD_PRIMARY_ACTION = "Tạm dừng & xác minh"
