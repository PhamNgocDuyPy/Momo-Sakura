"""Reason_Code_Registry: the single module that declares every ``RC_`` constant.

Each code carries its minimum tier, cooling-off, display priority, allowed HARD sources and the
Vietnamese bullet shown to the user (templates only, never LLM text).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from guardian.schemas.enums import DecisionTier, HardSource

CoolingOff = Literal[0, 15, 30, 60, 300]

@dataclass(frozen=True)
class ReasonCodeSpec:
    code: str
    min_tier: DecisionTier
    cooling_off: CoolingOff
    priority: int  # lower = shown first within the same tier
    hard_sources: frozenset[HardSource]  # empty when min_tier < HARD_HOLD
    bullet_vi: str  # <= 160 chars, never contains "100% an toàn"
    meaning_vi: str  # mirrored in docs/FLOWS_AND_GLOSSARY.md


RC_PROMPT_INJECTION_BLOCKED = "RC_PROMPT_INJECTION_BLOCKED"
RC_QR_CHECK_BYPASS_DETECTED = "RC_QR_CHECK_BYPASS_DETECTED"
RC_VIETQR_TAMPERED_BAD_CRC = "RC_VIETQR_TAMPERED_BAD_CRC"
RC_SIMO_OR_MULE_HIGH_RISK = "RC_SIMO_OR_MULE_HIGH_RISK"
RC_FAN_IN_VELOCITY_HIGH = "RC_FAN_IN_VELOCITY_HIGH"
RC_FLOWB_FLAGGED_RECENTLY = "RC_FLOWB_FLAGGED_RECENTLY"
RC_UNOFFICIAL_APK_PHISHING = "RC_UNOFFICIAL_APK_PHISHING"
RC_AUTHORITY_COERCION = "RC_AUTHORITY_COERCION"
RC_BANK_COACHING_DETECTED = "RC_BANK_COACHING_DETECTED"
RC_URGENT_THIRD_PARTY_ACCT = "RC_URGENT_THIRD_PARTY_ACCT"
RC_REMOTE_SCREEN_TAKEOVER = "RC_REMOTE_SCREEN_TAKEOVER"
RC_FAKE_SHIPPER_RECALL = "RC_FAKE_SHIPPER_RECALL"
RC_UNVERIFIED_INBOUND_RECEIPT = "RC_UNVERIFIED_INBOUND_RECEIPT"
RC_TASK_SCAM_UNLOCK_FEE = "RC_TASK_SCAM_UNLOCK_FEE"
RC_GUARANTEED_RETURN_PIG_BUTCHERING = "RC_GUARANTEED_RETURN_PIG_BUTCHERING"
RC_FAKE_PROMO_REFUND = "RC_FAKE_PROMO_REFUND"
RC_BRAND_IMPERSONATION_MOMO = "RC_BRAND_IMPERSONATION_MOMO"
RC_CIRCULAR50_STRUCTURING_RISK = "RC_CIRCULAR50_STRUCTURING_RISK"
RC_ACCOUNT_SWAP_REQUEST = "RC_ACCOUNT_SWAP_REQUEST"
RC_C2C_DEPOSIT_URGENCY = "RC_C2C_DEPOSIT_URGENCY"
RC_UPFRONT_FEE_REQUEST = "RC_UPFRONT_FEE_REQUEST"
RC_CONTEXT_RELATIVE_URGENT_DECLARED = "RC_CONTEXT_RELATIVE_URGENT_DECLARED"
RC_CONTEXT_AUTHORITY_DECLARED = "RC_CONTEXT_AUTHORITY_DECLARED"
RC_FAST_UNBLOCK_VERIFIED = "RC_FAST_UNBLOCK_VERIFIED"
RC_GREY_ZONE_RECIPIENT = "RC_GREY_ZONE_RECIPIENT"
RC_PRICE_TOO_GOOD_TO_BE_TRUE = "RC_PRICE_TOO_GOOD_TO_BE_TRUE"
RC_PROMO_NOT_IN_OFFICIAL_LIST = "RC_PROMO_NOT_IN_OFFICIAL_LIST"
RC_VIETQR_FOREIGN_OR_NON_VND = "RC_VIETQR_FOREIGN_OR_NON_VND"
RC_VIETQR_INVALID_FORMAT = "RC_VIETQR_INVALID_FORMAT"
RC_SUSPECT_INJECTION_REVIEW = "RC_SUSPECT_INJECTION_REVIEW"
RC_RISKY_URL_DETECTED = "RC_RISKY_URL_DETECTED"
RC_MANIPULATION_CUE_REVIEW = "RC_MANIPULATION_CUE_REVIEW"
RC_SUSPICIOUS_UNCLASSIFIED = "RC_SUSPICIOUS_UNCLASSIFIED"
RC_LLM_OUTPUT_INVALID = "RC_LLM_OUTPUT_INVALID"
RC_LLM_TIMEOUT_FALLBACK = "RC_LLM_TIMEOUT_FALLBACK"
RC_LLM_UNAVAILABLE_FALLBACK = "RC_LLM_UNAVAILABLE_FALLBACK"
RC_PII_EGRESS_BLOCKED = "RC_PII_EGRESS_BLOCKED"
RC_CONTEXT_ONLINE_ORDER_DECLARED = "RC_CONTEXT_ONLINE_ORDER_DECLARED"
RC_COLD_START_NEEDS_CONTEXT = "RC_COLD_START_NEEDS_CONTEXT"
RC_OCR_ACCOUNT_NEEDS_CONFIRM = "RC_OCR_ACCOUNT_NEEDS_CONFIRM"
RC_TRUSTED_PAYEE_HISTORY = "RC_TRUSTED_PAYEE_HISTORY"
RC_CONTEXT_IN_STORE_DECLARED = "RC_CONTEXT_IN_STORE_DECLARED"
RC_PROMO_MATCHES_OFFICIAL_LIST = "RC_PROMO_MATCHES_OFFICIAL_LIST"
RC_NO_REFERENCE_PRICE = "RC_NO_REFERENCE_PRICE"
RC_NO_SCAM_SIGNAL_FOUND = "RC_NO_SCAM_SIGNAL_FOUND"

_H = HardSource
_T = DecisionTier

_SPECS: tuple[ReasonCodeSpec, ...] = (
    ReasonCodeSpec(
        RC_PROMPT_INJECTION_BLOCKED, _T.HARD_HOLD, 60, 10,
        frozenset({_H.PROMPT_INJECTION, _H.CONTROL_PLANE_HIJACK}),
        "Nội dung có câu lệnh tìm cách điều khiển Guardian. Đây là dấu hiệu lừa đảo có chủ đích.",
        "Nội dung chứa câu lệnh cố điều khiển Guardian hoặc giả mạo khung điều khiển nội bộ.",
    ),
    ReasonCodeSpec(
        RC_QR_CHECK_BYPASS_DETECTED, _T.HARD_HOLD, 60, 20,
        frozenset({_H.R6_MISSING_QR_CHECK}),
        "Mã QR chưa được kiểm tra đúng quy trình nên Guardian tạm giữ giao dịch.",
        "Có QR nhưng trace thiếu bước verify_vietqr_emvco (luật R6).",
    ),
    ReasonCodeSpec(
        RC_VIETQR_TAMPERED_BAD_CRC, _T.HARD_HOLD, 60, 30,
        frozenset({_H.QR_BAD_CRC}),
        "Mã QR đã bị chỉnh sửa (sai mã kiểm tra CRC). Đừng chuyển tiền theo mã này.",
        "Mã QR VietQR có CRC sai, nghi bị sửa đổi.",
    ),
    ReasonCodeSpec(
        RC_SIMO_OR_MULE_HIGH_RISK, _T.HARD_HOLD, 60, 40,
        frozenset({_H.SIMO_HIT, _H.GNN_MULE}),
        "Tài khoản nhận nằm trong danh sách cảnh báo hoặc có dấu hiệu tài khoản trung gian nhận tiền lừa đảo.",
        "Tài khoản nhận trùng SIMO hoặc điểm GNN mule từ 0.85 trở lên.",
    ),
    ReasonCodeSpec(
        RC_FAN_IN_VELOCITY_HIGH, _T.HARD_HOLD, 60, 50,
        frozenset({_H.FAN_IN_VELOCITY}),
        "Tài khoản nhận đang nhận tiền từ rất nhiều người trong thời gian ngắn.",
        "Số người gửi mỗi giờ vào tài khoản nhận vượt ngưỡng cấu hình.",
    ),
    ReasonCodeSpec(
        RC_FLOWB_FLAGGED_RECENTLY, _T.HARD_HOLD, 60, 60,
        frozenset({_H.RISK_MEMORY}),
        "Guardian vừa cảnh báo tài khoản này trong nội dung bạn kiểm tra gần đây.",
        "Risk_Memory của phiên có mục chưa hết hạn cho tài khoản hoặc tên miền này.",
    ),
    ReasonCodeSpec(
        RC_UNOFFICIAL_APK_PHISHING, _T.HARD_HOLD, 60, 70,
        frozenset({_H.URL_APK_OR_GOV_SPOOF, _H.PLAYBOOK_HARD}),
        "Liên kết giả mạo cơ quan hoặc bắt tải ứng dụng ngoài kho chính thức. Đừng bấm và đừng cài đặt.",
        "Liên kết tải APK, giả mạo cơ quan nhà nước hoặc kịch bản phishing/malware.",
    ),
    ReasonCodeSpec(
        RC_AUTHORITY_COERCION, _T.HARD_HOLD, 60, 80,
        frozenset({_H.PLAYBOOK_HARD}),
        "Công an và cơ quan nhà nước không yêu cầu chuyển tiền qua ví hay qua điện thoại.",
        "Kịch bản mạo danh công an, cơ quan nhà nước, VNeID để ép chuyển tiền.",
    ),
    ReasonCodeSpec(
        RC_BANK_COACHING_DETECTED, _T.HARD_HOLD, 60, 90,
        frozenset({_H.PLAYBOOK_HARD}),
        "Có người đang dặn bạn phải trả lời ngân hàng thế nào. Kẻ gian thường làm vậy để qua mặt kiểm tra.",
        "Nội dung dặn nạn nhân cách trả lời ngân hàng, kèm kịch bản thuộc nhóm HARD.",
    ),
    ReasonCodeSpec(
        RC_URGENT_THIRD_PARTY_ACCT, _T.HARD_HOLD, 60, 100,
        frozenset({_H.PLAYBOOK_HARD}),
        "Người thân cần tiền gấp nhưng lại nhờ chuyển vào tài khoản của người khác. Hãy gọi lại số quen để kiểm tra.",
        "Kịch bản giả người thân (deepfake) cần tiền gấp và đưa tài khoản của bên thứ ba.",
    ),
    ReasonCodeSpec(
        RC_REMOTE_SCREEN_TAKEOVER, _T.HARD_HOLD, 60, 110,
        frozenset({_H.PLAYBOOK_HARD}),
        "Có yêu cầu chia sẻ màn hình hoặc cài ứng dụng điều khiển từ xa. Kẻ gian có thể chiếm tài khoản của bạn.",
        "Yêu cầu chia sẻ màn hình hoặc cài ứng dụng điều khiển từ xa, kèm kịch bản HARD.",
    ),
    ReasonCodeSpec(
        RC_FAKE_SHIPPER_RECALL, _T.HARD_HOLD, 60, 120,
        frozenset({_H.PLAYBOOK_HARD}),
        "Shipper thật không yêu cầu chuyển khoản để thu hồi hay hoàn đơn.",
        "Kịch bản giả shipper đòi chuyển khoản để thu hồi hoặc hoàn đơn.",
    ),
    ReasonCodeSpec(
        RC_UNVERIFIED_INBOUND_RECEIPT, _T.HARD_HOLD, 60, 130,
        frozenset({_H.PLAYBOOK_HARD}),
        "Ảnh biên lai không chứng minh tiền đã vào tài khoản. Hãy kiểm tra số dư thật trước khi hoàn tiền.",
        "Người gửi tự nhận đã chuyển tiền bằng ảnh biên lai chưa được xác minh.",
    ),
    ReasonCodeSpec(
        RC_TASK_SCAM_UNLOCK_FEE, _T.HARD_HOLD, 60, 140,
        frozenset({_H.PLAYBOOK_HARD}),
        "Việc làm online đòi nạp tiền hoặc phí mở khóa là kiểu lừa đảo nhiệm vụ.",
        "Lừa đảo việc làm nhiệm vụ online đòi nạp tiền hoặc phí mở khóa.",
    ),
    ReasonCodeSpec(
        RC_GUARANTEED_RETURN_PIG_BUTCHERING, _T.HARD_HOLD, 60, 150,
        frozenset({_H.PLAYBOOK_HARD}),
        "Lời hứa lãi cao, cam kết không lỗ là dấu hiệu lừa đảo đầu tư.",
        "Lừa đảo đầu tư hoặc tình cảm hứa lãi cao, cam kết không lỗ.",
    ),
    ReasonCodeSpec(
        RC_FAKE_PROMO_REFUND, _T.HARD_HOLD, 60, 160,
        frozenset({_H.PROMO_FAKE}),
        "Khuyến mãi hoặc hoàn tiền thật không bắt bạn trả phí trước để nhận.",
        "Khuyến mãi không có trong danh sách chính thức và đòi phí trước.",
    ),
    ReasonCodeSpec(
        RC_BRAND_IMPERSONATION_MOMO, _T.HARD_HOLD, 60, 170,
        frozenset({_H.PROMO_FAKE}),
        "Chương trình nhân danh MoMo này không có trong danh sách khuyến mãi chính thức.",
        "Chương trình mạo danh MoMo không khớp danh sách khuyến mãi chính thức.",
    ),
    ReasonCodeSpec(
        RC_CIRCULAR50_STRUCTURING_RISK, _T.SOFT_FRICTION, 30, 180,
        frozenset(),
        "Giao dịch gần 10 triệu và tổng 24 giờ vượt 20 triệu, giống kiểu chia nhỏ để né kiểm tra.",
        "Dấu hiệu chia nhỏ giao dịch theo Thông tư 50 (luật R5).",
    ),
    ReasonCodeSpec(
        RC_ACCOUNT_SWAP_REQUEST, _T.SOFT_FRICTION, 30, 190,
        frozenset(),
        "Tin nhắn nhờ bạn chuyển tiền vào một tài khoản mới hoặc khác tài khoản cũ. Kẻ gian hay dùng chiêu này.",
        "Nội dung yêu cầu đổi tài khoản nhận so với tài khoản người dùng đã nhập.",
    ),
    ReasonCodeSpec(
        RC_C2C_DEPOSIT_URGENCY, _T.SOFT_FRICTION, 30, 200,
        frozenset(),
        "Người bán đòi đặt cọc trước và hối thúc. Hãy ưu tiên thanh toán khi nhận hàng.",
        "Người bán cá nhân đòi đặt cọc trước và hối thúc.",
    ),
    ReasonCodeSpec(
        RC_UPFRONT_FEE_REQUEST, _T.SOFT_FRICTION, 30, 210,
        frozenset(),
        "Nội dung đòi bạn trả phí trước. Hãy xác minh qua kênh chính thức.",
        "Nội dung đòi trả phí hoặc đặt cọc trước.",
    ),
    ReasonCodeSpec(
        RC_CONTEXT_RELATIVE_URGENT_DECLARED, _T.SOFT_FRICTION, 30, 220,
        frozenset(),
        "Bạn cho biết đây là chuyển gấp cho người thân. Hãy gọi lại số quen trước khi chuyển.",
        "Người dùng khai báo đang chuyển gấp cho người thân.",
    ),
    ReasonCodeSpec(
        RC_CONTEXT_AUTHORITY_DECLARED, _T.SOFT_FRICTION, 60, 230,
        frozenset(),
        "Bạn cho biết cơ quan nhà nước yêu cầu chuyển tiền. Cơ quan thật không làm vậy qua ví.",
        "Người dùng khai báo cơ quan nhà nước yêu cầu chuyển tiền.",
    ),
    ReasonCodeSpec(
        RC_FAST_UNBLOCK_VERIFIED, _T.SOFT_FRICTION, 30, 240,
        frozenset(),
        "Bạn đã xác minh danh tính và mục đích. Hãy chờ hết thời gian rồi kiểm tra lại người nhận.",
        "Người dùng đã qua Fast Unblock (OTP sandbox và mục đích chuyển).",
    ),
    ReasonCodeSpec(
        RC_GREY_ZONE_RECIPIENT, _T.SOFT_FRICTION, 15, 250,
        frozenset(),
        "Tài khoản nhận còn mới hoặc có vài tín hiệu chưa rõ ràng.",
        "Tài khoản nhận nằm trong vùng xám: GNN từ 0.6 đến dưới 0.85 hoặc tuổi dưới 30 ngày.",
    ),
    ReasonCodeSpec(
        RC_PRICE_TOO_GOOD_TO_BE_TRUE, _T.SOFT_FRICTION, 15, 260,
        frozenset(),
        "Giá rao thấp hơn giá tham chiếu từ 40% trở lên.",
        "Giá rao thấp hơn giá tham chiếu từ 40% trở lên.",
    ),
    ReasonCodeSpec(
        RC_PROMO_NOT_IN_OFFICIAL_LIST, _T.SOFT_FRICTION, 15, 270,
        frozenset(),
        "Khuyến mãi này không có trong danh sách chính thức Guardian đang có.",
        "Khuyến mãi không khớp danh sách chính thức và không đòi phí.",
    ),
    ReasonCodeSpec(
        RC_VIETQR_FOREIGN_OR_NON_VND, _T.SOFT_FRICTION, 15, 280,
        frozenset(),
        "Mã QR không phải VietQR thanh toán bằng VND.",
        "Mã QR của hệ thống nước ngoài hoặc không dùng VND.",
    ),
    ReasonCodeSpec(
        RC_VIETQR_INVALID_FORMAT, _T.SOFT_FRICTION, 15, 290,
        frozenset(),
        "Mã QR sai định dạng VietQR (ví dụ số tiền có phần thập phân).",
        "Mã QR sai định dạng VietQR.",
    ),
    ReasonCodeSpec(
        RC_SUSPECT_INJECTION_REVIEW, _T.SOFT_FRICTION, 15, 300,
        frozenset(),
        "Nội dung có đoạn văn lạ giống câu lệnh cho máy. Guardian đánh dấu để bạn xem kỹ.",
        "Điểm prefilter CPU từ ngưỡng mềm trở lên (luật R3 mức mềm).",
    ),
    ReasonCodeSpec(
        RC_RISKY_URL_DETECTED, _T.SOFT_FRICTION, 15, 310,
        frozenset(),
        "Liên kết dùng tên miền rủi ro hoặc giống thương hiệu nhưng không phải trang chính thức.",
        "URL có cờ rủi ro: TLD rủi ro, punycode, giống thương hiệu, rút gọn, IP hoặc Safe Browsing.",
    ),
    ReasonCodeSpec(
        RC_MANIPULATION_CUE_REVIEW, _T.SOFT_FRICTION, 15, 320,
        frozenset(),
        "Nội dung có dấu hiệu hối thúc hoặc dặn giữ bí mật.",
        "Nội dung có dấu hiệu thao túng tâm lý như hối thúc hoặc giữ bí mật.",
    ),
    ReasonCodeSpec(
        RC_SUSPICIOUS_UNCLASSIFIED, _T.SOFT_FRICTION, 15, 330,
        frozenset(),
        "Nội dung có điểm đáng ngờ chưa khớp kiểu lừa đảo nào đã biết.",
        "Nội dung đáng ngờ nhưng không khớp playbook nào.",
    ),
    ReasonCodeSpec(
        RC_LLM_OUTPUT_INVALID, _T.SOFT_FRICTION, 15, 340,
        frozenset(),
        "Guardian chưa phân tích được nội dung này đầy đủ, nên hãy thận trọng.",
        "Đầu ra LLM sai schema, bị từ chối, bị cắt hoặc không gọi tool.",
    ),
    ReasonCodeSpec(
        RC_LLM_TIMEOUT_FALLBACK, _T.SOFT_FRICTION, 15, 350,
        frozenset(),
        "Phân tích AI quá chậm. Kết quả dựa trên các kiểm tra nhanh của Guardian.",
        "LLM quá thời gian chờ nên dùng kết quả dự phòng.",
    ),
    ReasonCodeSpec(
        RC_LLM_UNAVAILABLE_FALLBACK, _T.SOFT_FRICTION, 15, 360,
        frozenset(),
        "Phân tích AI đang không sẵn sàng. Kết quả dựa trên các kiểm tra nhanh của Guardian.",
        "LLM lỗi, chưa cài đặt hoặc circuit breaker đang mở.",
    ),
    ReasonCodeSpec(
        RC_PII_EGRESS_BLOCKED, _T.SOFT_FRICTION, 15, 370,
        frozenset(),
        "Guardian giữ lại dữ liệu cá nhân và không gửi nội dung này đi phân tích.",
        "Còn dữ liệu cá nhân sau khi che nên không gửi nội dung tới LLM (luật R1).",
    ),
    ReasonCodeSpec(
        RC_CONTEXT_ONLINE_ORDER_DECLARED, _T.SOFT_FRICTION, 15, 380,
        frozenset(),
        "Bạn cho biết đây là đơn hàng online. Hãy dùng kênh thanh toán có bảo vệ người mua.",
        "Người dùng khai báo đây là đơn hàng online.",
    ),
    ReasonCodeSpec(
        RC_COLD_START_NEEDS_CONTEXT, _T.SOFT_FRICTION, 0, 390,
        frozenset(),
        "Đây là lần đầu bạn chuyển cho người nhận này và Guardian chưa có đủ thông tin để đánh giá.",
        "Người nhận lần đầu, không có lịch sử và không có tín hiệu rủi ro.",
    ),
    ReasonCodeSpec(
        RC_OCR_ACCOUNT_NEEDS_CONFIRM, _T.SOFT_FRICTION, 0, 400,
        frozenset(),
        "Số tài khoản đọc từ ảnh cần bạn xác nhận tên người nhận trước.",
        "Số tài khoản từ OCR chưa được người dùng xác nhận tên người nhận (luật R2).",
    ),
    ReasonCodeSpec(
        RC_TRUSTED_PAYEE_HISTORY, _T.ALLOW, 0, 410,
        frozenset(),
        "Bạn đã từng chuyển tiền cho người nhận này.",
        "Người nhận có lịch sử giao dịch và không có tín hiệu rủi ro.",
    ),
    ReasonCodeSpec(
        RC_CONTEXT_IN_STORE_DECLARED, _T.ALLOW, 0, 420,
        frozenset(),
        "Bạn xác nhận đang thanh toán trực tiếp tại cửa hàng.",
        "Người dùng khai báo đang thanh toán trực tiếp tại cửa hàng.",
    ),
    ReasonCodeSpec(
        RC_PROMO_MATCHES_OFFICIAL_LIST, _T.ALLOW, 0, 430,
        frozenset(),
        "Khuyến mãi khớp danh sách chính thức. Hãy nhập mã trong ứng dụng, không qua đường link lạ.",
        "Khuyến mãi khớp danh sách chính thức còn hiệu lực.",
    ),
    ReasonCodeSpec(
        RC_NO_REFERENCE_PRICE, _T.ALLOW, 0, 440,
        frozenset(),
        "Chưa có giá tham chiếu cho sản phẩm này nên Guardian không so giá.",
        "Không có giá tham chiếu cho danh mục sản phẩm.",
    ),
    ReasonCodeSpec(
        RC_NO_SCAM_SIGNAL_FOUND, _T.ALLOW, 0, 450,
        frozenset(),
        "Guardian chưa thấy dấu hiệu lừa đảo quen thuộc. Bạn vẫn nên kiểm tra tên người nhận.",
        "Không phát hiện tín hiệu lừa đảo quen thuộc.",
    ),
)

REGISTRY: Mapping[str, ReasonCodeSpec] = MappingProxyType({spec.code: spec for spec in _SPECS})


def get_spec(code: str) -> ReasonCodeSpec:
    """Return the spec for ``code`` or raise ``KeyError`` when it is not registered."""
    return REGISTRY[code]


def is_registered(code: str) -> bool:
    return code in REGISTRY
