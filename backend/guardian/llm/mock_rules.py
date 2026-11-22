"""Pure, deterministic rules behind MockLLM (design.md, LLM_Client).

Everything here is a pure function of its text input: no randomness, no clock, no I/O.
All matching happens on the folded text (NFC -> lower -> no diacritics, ``đ -> d``). Folding
keeps the string length, so offsets found on the folded text index the original NFC text.
"""

from __future__ import annotations

import re
import unicodedata

from guardian.schemas.enums import (
    Confidence,
    ContentMode,
    Cue,
    Intent,
    ProductCategory,
    PromoBrand,
    ScamPlaybook,
    SpendCategory,
    SpendMetric,
    SpendPeriod,
)
from guardian.schemas.extraction import (
    ExtractedEntities,
    Listing,
    PaymentRequest,
    PromoClaim,
    QuarantinedExtraction,
    ReceiptItem,
    ReceiptItems,
)
from guardian.schemas.planner import PlannerIntent, SpendSlots, SplitSlots, TransferSlots
from guardian.tools.amount import find_amounts, parse_amount
from guardian.tools.entity_scanner import scan_entities
from guardian.tools.pii import _fold_chars
from guardian.tools.url_checker import APK_DOWNLOAD, GOV_SPOOF

MAX_AMOUNT = 100_000_000_000


def normalize(text: str) -> tuple[str, str]:
    """Return ``(nfc, folded)`` with equal length."""
    nfc = unicodedata.normalize("NFC", text)
    return nfc, _fold_chars(nfc).lower()


def _kw(pattern: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![a-z0-9])(?:{pattern})(?![a-z0-9])")


# --- injection -------------------------------------------------------------------------------

_INJECTION_RES = (
    re.compile(r"bo qua (?:moi|tat ca) (?:huong dan|chi dan|quy tac)"),
    re.compile(r"ignore (?:all |previous )?instructions"),
    re.compile(r"^\s*(?:system|assistant)\s*:", re.M),
    re.compile(r"danh dau (?:la )?an toan"),
    re.compile(r"tra ve allow"),
    re.compile(r"you are now"),
)
_ZERO_WIDTH_RE = re.compile("[\u200b-\u200f\u202a-\u202e\u2060\ufeff]")


def detect_injection(nfc: str, folded: str) -> bool:
    return bool(_ZERO_WIDTH_RE.search(nfc)) or any(r.search(folded) for r in _INJECTION_RES)


# --- cues (fixed order, max 6) -----------------------------------------------------------------

_CUE_RULES: tuple[tuple[Cue, re.Pattern[str]], ...] = (
    (Cue.URGENCY_TIME_PRESSURE, _kw(r"gap|khan cap|ngay lap tuc|trong \d+ phut|het han|nhanh len")),
    (
        Cue.SECRECY_DO_NOT_TELL_ANYONE,
        _kw(r"khong duoc noi|giu bi mat|dung noi (?:voi |cho )?(?:ai|bo|me|ba)|khong cho ai biet"),
    ),
    (Cue.COACHING_WHAT_TO_TELL_BANK, _kw(r"(?:neu|khi) (?:ngan hang|nhan vien) hoi|cu noi la|tra loi la")),
    (
        Cue.UPFRONT_DEPOSIT_OR_UNLOCK_FEE,
        _kw(r"phi (?:mo khoa|kich hoat|nhan qua|nhan thuong|xac minh|giu cho|van chuyen)|nop phi|coc truoc|dat coc"),
    ),
    (
        Cue.GUARANTEED_HIGH_RETURN,
        _kw(r"cam ket (?:lai|loi nhuan)|lai \d+ ?%|loi nhuan dam bao|x2 tai khoan|bao lo"),
    ),
    (Cue.SCREEN_SHARE_OR_REMOTE_APP, _kw(r"chia se man hinh|anydesk|teamviewer|ultraviewer|quicksupport")),
    (Cue.SPLIT_TRANSFER_UNDER_10M, _kw(r"chia (?:nho|lam nhieu lan)|duoi 10 trieu|tach (?:thanh|ra) .* lan")),
)


def detect_cues(folded: str) -> list[Cue]:
    return [cue for cue, rx in _CUE_RULES if rx.search(folded)][:6]


# --- playbook ----------------------------------------------------------------------------------

_AUTHORITY_RE = _kw(r"cong an|co quan dieu tra|vien kiem sat|toa an|lenh bat|vneid|dinh danh muc 2")
_RELATIVE_RE = re.compile(r"(?<![a-z0-9])(?:(?:me|bo|ba|con|chau|anh|chi) oi|con dang)(?![a-z0-9])")
_EMERGENCY_RE = _kw(r"cap cuu|tai nan|benh vien|bi bat")
_INSTALL_APP_RE = _kw(r"tai (?:app|ung dung)|cai dat ung dung")
_TASK_RE = _kw(r"viec lam online|cong tac vien|lam nhiem vu|tha tim|hoa hong")
_INVEST_RE = _kw(r"dau tu|san giao dich|forex|coin|tien ao")
_SHIPPER_RE = _kw(r"shipper|giao hang|buu ta")
_RECALL_RE = _kw(r"thu hoi|hoan don|phi (?:ship|giao) lai|chuyen khoan truoc")
_C2C_RE = _kw(r"coc|giu hang|chuyen truoc|da chuyen (?:khoan )?(?:roi|nham|du)|bien lai|hoan lai phan (?:du|thua)")


def classify_playbook(
    folded: str,
    cues: list[Cue],
    *,
    has_account: bool,
    url_flags: frozenset[str],
    has_url: bool,
) -> ScamPlaybook:
    has_apk = APK_DOWNLOAD in url_flags
    if _AUTHORITY_RE.search(folded) and not has_apk:
        return ScamPlaybook.IMPERSONATE_AUTHORITY_VNEID
    if (
        _RELATIVE_RE.search(folded)
        and _EMERGENCY_RE.search(folded)
        and (has_account or "tai khoan cua ban" in folded)
    ):
        return ScamPlaybook.DEEPFAKE_RELATIVE_EMERGENCY
    if (
        has_apk
        or GOV_SPOOF in url_flags
        or (_INSTALL_APP_RE.search(folded) and has_url)
        or Cue.SCREEN_SHARE_OR_REMOTE_APP in cues
    ):
        return ScamPlaybook.PHISHING_LINK_OR_APK_MALWARE
    if _TASK_RE.search(folded):
        return ScamPlaybook.TASK_SCAM_JOB_ONLINE
    if _INVEST_RE.search(folded) and Cue.GUARANTEED_HIGH_RETURN in cues:
        return ScamPlaybook.INVESTMENT_ROMANCE_PIG_BUTCHERING
    if _SHIPPER_RE.search(folded) and _RECALL_RE.search(folded):
        return ScamPlaybook.FAKE_SHIPPER_RECALL
    if _C2C_RE.search(folded):
        return ScamPlaybook.C2C_DEPOSIT_OR_FAKE_RECEIPT
    if cues:
        return ScamPlaybook.UNKNOWN_SUSPICIOUS
    return ScamPlaybook.NONE_DETECTED


# --- amounts and memo --------------------------------------------------------------------------

_AMOUNT_KEYWORD_RE = re.compile(r"(?<![a-z0-9])(?:ck|chuyen|gui|coc|phi)(?![a-z0-9])")
_AMOUNT_AFTER_RE = _kw(r"coc|phi")
_PRICE_KEYWORD_RE = _kw(r"gia|ban|thanh ly|pass lai")
_MEMO_NOISE_PREV = frozenset({"chuyen", "hoan", "gui", "nhan", "ck", "nop", "phi", "coc", "nap", "mat", "gia", "so"})
_MEMO_NOI_DUNG_RE = re.compile(r"(?<![a-z0-9])(?:noi dung|nd)\s*:?\s*")
_MEMO_TIEN_RE = re.compile(r"(?<![a-z0-9])tien(?![a-z0-9])")


def _first_amount_after(nfc: str, folded: str, rx: re.Pattern[str], window: int = 40) -> int | None:
    for m in rx.finditer(folded):
        found = find_amounts(nfc[m.end() : m.end() + window])
        if found:
            return found[0]
    return None


def pick_amount(nfc: str, folded: str) -> int | None:
    """Prefer the amount right after ck/chuyen/gui/coc/phi, else the first amount."""
    preferred = _first_amount_after(nfc, folded, _AMOUNT_KEYWORD_RE)
    if preferred is not None and 0 <= preferred <= MAX_AMOUNT:
        return preferred
    for value in find_amounts(nfc):
        if 0 <= value <= MAX_AMOUNT:
            return value
    return None


def extract_memo(nfc: str, folded: str, limit: int) -> str | None:
    """``tiền ...`` phrase (keeps the word) up to a comma/end, or the phrase after ``nội dung|nd``."""
    m = _MEMO_NOI_DUNG_RE.search(folded)
    if m:
        phrase = re.split(r"[,\n]", nfc[m.end() :], maxsplit=1)[0].strip()
        if phrase:
            return phrase[:limit].strip() or None
    for m in _MEMO_TIEN_RE.finditer(folded):
        prev = folded[: m.start()].split()
        if prev and prev[-1] in _MEMO_NOISE_PREV:
            continue
        phrase = re.split(r"[,\n]", nfc[m.start() :], maxsplit=1)[0].strip()
        if phrase:
            return phrase[:limit].strip() or None
    return None


# --- product / brand dictionaries -------------------------------------------------------------

_PRODUCT_KEYS: tuple[tuple[str, str, ProductCategory], ...] = (
    ("iphone 15 pro max", "iphone_15_pro_max", ProductCategory.PHONE),
    ("airpods pro 2", "airpods_pro_2", ProductCategory.HEADPHONES),
    ("ps5 slim", "ps5_slim", ProductCategory.GAME_CONSOLE),
    ("ps5", "ps5_slim", ProductCategory.GAME_CONSOLE),
)
_CATEGORY_WORDS: tuple[tuple[re.Pattern[str], ProductCategory], ...] = (
    (_kw(r"iphone|samsung|dien thoai|xiaomi|oppo"), ProductCategory.PHONE),
    (_kw(r"laptop|macbook"), ProductCategory.LAPTOP),
    (_kw(r"ipad|may tinh bang"), ProductCategory.TABLET),
    (_kw(r"airpods|tai nghe"), ProductCategory.HEADPHONES),
    (_kw(r"apple watch|dong ho thong minh"), ProductCategory.SMARTWATCH),
    (_kw(r"playstation|ps4|ps5|xbox|nintendo"), ProductCategory.GAME_CONSOLE),
    (_kw(r"may anh"), ProductCategory.CAMERA),
    (_kw(r"giay"), ProductCategory.SNEAKERS),
    (_kw(r"ve (?:concert|show|su kien)"), ProductCategory.EVENT_TICKET),
)
_BRANDS: tuple[tuple[re.Pattern[str], PromoBrand], ...] = (
    (_kw(r"momo"), PromoBrand.MOMO),
    (_kw(r"shopee"), PromoBrand.SHOPEE),
    (_kw(r"lazada"), PromoBrand.LAZADA),
    (_kw(r"tiki"), PromoBrand.TIKI),
    (_kw(r"tiktok shop|tiktok"), PromoBrand.TIKTOK_SHOP),
    (_kw(r"grab"), PromoBrand.GRAB),
    (
        _kw(r"ngan hang|vietcombank|techcombank|bidv|vietinbank|mbbank|acb|vpbank|tpbank|agribank"),
        PromoBrand.BANK,
    ),
)
_BRAND_WORDS = frozenset({"momo", "shopee", "lazada", "tiki", "tiktok", "grab"})
_PROMO_TRIGGER_RE = _kw(r"khuyen mai|voucher|trung thuong|tri an|qua tang|hoan tien")
_PROMO_FEE_RE = re.compile(r"(?<![a-z0-9])phi(?![a-z0-9])|(?<![a-z0-9])chuyen .* de nhan")
_PROMO_CODE_RE = re.compile(r"\b[A-Z0-9]{5,30}\b")
_LISTING_RE = _kw(r"ban|thanh ly|pass lai")
_DEPOSIT_RE = _kw(r"coc")


def _build_listing(nfc: str, folded: str, mode: ContentMode, cues: list[Cue]) -> Listing | None:
    amounts = find_amounts(nfc)
    if not (mode == ContentMode.SHOP or (_LISTING_RE.search(folded) and amounts)):
        return None
    product_key: str | None = None
    category = ProductCategory.OTHER
    for needle, key, cat in _PRODUCT_KEYS:
        if _kw(re.escape(needle)).search(folded):
            product_key, category = key, cat
            break
    if product_key is None:
        for rx, cat in _CATEGORY_WORDS:
            if rx.search(folded):
                category = cat
                break
    price = _first_amount_after(nfc, folded, _PRICE_KEYWORD_RE, 120)
    if price is None and amounts:
        price = amounts[0]
    requires_deposit = Cue.UPFRONT_DEPOSIT_OR_UNLOCK_FEE in cues or bool(_DEPOSIT_RE.search(folded))
    deposit = _first_amount_after(nfc, folded, _DEPOSIT_RE) if requires_deposit else None
    return Listing(
        product_category=category,
        product_key=product_key,
        listed_price_vnd=price,
        requires_deposit=requires_deposit,
        deposit_vnd=deposit,
    )


def _build_promo(nfc: str, folded: str, mode: ContentMode) -> PromoClaim | None:
    if not (mode == ContentMode.PROMO or _PROMO_TRIGGER_RE.search(folded)):
        return None
    best: tuple[int, PromoBrand] | None = None
    for rx, brand in _BRANDS:
        m = rx.search(folded)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), brand)
    code: str | None = None
    for m in _PROMO_CODE_RE.finditer(nfc):
        token = m.group()
        if any(c.isalpha() for c in token) and token.lower() not in _BRAND_WORDS and token != "CCCD":
            code = token
            break
    requires_fee = bool(_PROMO_FEE_RE.search(folded))
    fee = _first_amount_after(nfc, folded, _AMOUNT_AFTER_RE) if requires_fee else None
    return PromoClaim(
        brand=best[1] if best else PromoBrand.OTHER,
        promo_code=code,
        requires_fee=requires_fee,
        fee_vnd=fee,
    )


_RECEIPT_LINE_RE = re.compile(r"^(.+?)\s+(\d{1,2})\s*[xX×]?\s+([\d.,]+)\s*(?:đ|d)?$")
_TOTAL_LINE_RE = re.compile(r"^\s*(?:tong cong|tong|total|thanh toan)\b[^\d]*([\d.,]+)")


def _build_receipt(nfc: str) -> ReceiptItems:
    items: list[ReceiptItem] = []
    total: int | None = None
    for line in nfc.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        folded_line = _fold_chars(stripped).lower()
        tm = _TOTAL_LINE_RE.match(folded_line)
        if tm:
            value = parse_amount(tm.group(1))
            if value is not None:
                total = value
            continue
        m = _RECEIPT_LINE_RE.match(stripped)
        if not m:
            continue
        qty = int(m.group(2))
        price = parse_amount(m.group(3))
        name = m.group(1).strip()[:60]
        if price is None or not 1 <= qty <= 99 or price > 100_000_000 or not name:
            continue
        if len(items) < 30:
            items.append(ReceiptItem(name=name, quantity=qty, unit_price_vnd=price))
    return ReceiptItems(items=items, total_vnd=total)


# --- extractor ---------------------------------------------------------------------------------

_ACCOUNT_CHANGE_RE = _kw(
    r"doi (?:so )?(?:tai khoan|stk|tk)"
    r"|(?:tai khoan|stk|tk) (?:moi|cu bi)"
    r"|so (?:tai khoan|stk|tk) (?:khac|moi)"
    r"|chuyen (?:vao|qua|sang) (?:so|tk|stk|tai khoan) (?:khac|nay|moi)"
    r"|nick (?:\w+ )?bi hack|bi hack nick|nick bi (?:hack|khoa)"
    r"|muon tam (?:tai khoan|stk|tk)?"
)
_INBOUND_RE = _kw(r"da chuyen|bien lai")


def mock_extract(redacted_text: str, mode: ContentMode) -> QuarantinedExtraction:
    nfc, folded = normalize(redacted_text)
    injection = detect_injection(nfc, folded)
    cues = detect_cues(folded)
    entities = scan_entities(nfc)
    account = entities.accounts[0] if entities.accounts else None
    url_flags: frozenset[str] = frozenset().union(*(u.flags for u in entities.urls)) if entities.urls else frozenset()
    playbook = classify_playbook(
        folded,
        cues,
        has_account=account is not None,
        url_flags=url_flags,
        has_url=bool(entities.urls),
    )
    amount = pick_amount(nfc, folded)
    bank = (account.bank_bin if account and account.bank_bin else None) or (
        entities.bank_bins[0] if entities.bank_bins else None
    )
    domains = [u.domain for u in entities.urls if len(u.domain) <= 120]
    domains = list(dict.fromkeys(domains))[:5]
    ents = ExtractedEntities(
        bank_bin_or_name=bank,
        account_digits_raw=account.account_number if account else None,
        amount_vnd=amount,
        urls_redacted_domains=domains,
    )

    payment: PaymentRequest | None = None
    account_change = bool(_ACCOUNT_CHANGE_RE.search(folded))
    if account is not None or amount is not None or account_change:
        payment = PaymentRequest(
            bank_bin_or_name=bank,
            account_digits_raw=ents.account_digits_raw,
            amount_vnd=amount,
            memo=extract_memo(nfc, folded, 25),
            claims_inbound_payment=bool(_INBOUND_RE.search(folded)),
            requests_account_change=account_change,
        )
    receipt = _build_receipt(nfc) if mode == ContentMode.SPLIT_BILL else None
    listing = _build_listing(nfc, folded, mode, cues)
    promo = _build_promo(nfc, folded, mode)

    hits = len(cues) + (1 if playbook not in (ScamPlaybook.NONE_DETECTED, ScamPlaybook.UNKNOWN_SUSPICIOUS) else 0)
    hits += 1 if injection else 0
    confidence = Confidence.HIGH if hits >= 2 else Confidence.MEDIUM if hits == 1 else Confidence.LOW
    summary = f"mock: playbook={playbook.value}; cues={','.join(c.value for c in cues)}; hits={hits}"
    return QuarantinedExtraction(
        reasoning_summary=summary[:400],
        scam_playbook=playbook,
        manipulation_cues=cues,
        extracted_entities=ents,
        contains_prompt_injection=injection,
        confidence_level=confidence,
        payment_request=payment,
        receipt_items=receipt,
        listing=listing,
        promo_claim=promo,
    )


# --- planner -----------------------------------------------------------------------------------

_TRANSFER_START_RE = re.compile(r"^\s*(?:chuyen|ck|gui|bank)(?![a-z0-9])")
_SPEND_RE = _kw(r"het bao nhieu|chi bao nhieu|tieu bao nhieu|bao nhieu lan|may lan|trung binh|nhieu nhat|so voi")
_SPLIT_RE = _kw(r"chia (?:hoa don|bill|tien)")
_PROMO_INTENT_RE = _kw(r"khuyen mai|voucher|trung thuong")
_SHOP_RE = _kw(r"mua|link|shop|san pham|thanh ly")
_CONTENT_RE = _kw(r"kiem tra|lua dao|co an toan")
_RECIPIENT_RE = re.compile(
    r"(?<![a-z0-9])cho\s+(.+?)(?=\s+\d|\s+tien(?![a-z0-9])|\s+noi dung|\s+nd(?![a-z0-9])|[,\n]|$)"
)

_CATEGORY_KEYWORDS: tuple[tuple[SpendCategory, tuple[str, ...]], ...] = (
    (SpendCategory.CAFE, ("ca phe", "cafe", "coffee", "tra sua")),
    (SpendCategory.FOOD, ("an uong", "an", "com", "do an", "nha hang")),
    (SpendCategory.GROCERY, ("di cho", "sieu thi", "bach hoa")),
    (SpendCategory.TRANSPORT, ("di chuyen", "grab", "xe", "xang", "be", "taxi")),
    (SpendCategory.SHOPPING, ("mua sam", "shopee", "lazada", "quan ao")),
    (SpendCategory.BILLS, ("hoa don", "tien dien", "tien nuoc", "internet", "wifi")),
    (SpendCategory.SUBSCRIPTION, ("goi", "netflix", "spotify", "youtube", "dang ky")),
    (SpendCategory.ENTERTAINMENT, ("giai tri", "xem phim", "game", "karaoke")),
    (SpendCategory.HEALTH, ("thuoc", "benh vien", "kham")),
    (SpendCategory.EDUCATION, ("hoc", "hoc phi", "sach")),
    (SpendCategory.TRANSFER_OUT, ("chuyen tien", "chuyen khoan", "ck")),
)
_PERIOD_KEYWORDS: tuple[tuple[SpendPeriod, tuple[str, ...]], ...] = (
    (SpendPeriod.TODAY, ("hom nay",)),
    (SpendPeriod.YESTERDAY, ("hom qua",)),
    (SpendPeriod.THIS_WEEK, ("tuan nay",)),
    (SpendPeriod.LAST_WEEK, ("tuan truoc", "tuan roi")),
    (SpendPeriod.THIS_MONTH, ("thang nay",)),
    (SpendPeriod.LAST_MONTH, ("thang truoc", "thang roi")),
    (SpendPeriod.LAST_7_DAYS, ("7 ngay",)),
    (SpendPeriod.LAST_30_DAYS, ("30 ngay",)),
    (SpendPeriod.LAST_3_MONTHS, ("3 thang",)),
)
# Checked in order: more specific metrics first.
_METRIC_KEYWORDS: tuple[tuple[SpendMetric, tuple[str, ...]], ...] = (
    (SpendMetric.COMPARE_PREVIOUS, ("so voi", "tang hay giam")),
    (SpendMetric.AVERAGE_PER_DAY, ("trung binh moi ngay", "moi ngay")),
    (SpendMetric.AVERAGE_PER_TXN, ("trung binh moi lan", "trung binh")),
    (SpendMetric.MAX_TXN, ("nhieu nhat", "lon nhat")),
    (SpendMetric.COUNT, ("bao nhieu lan", "may lan")),
)


def _longest_match(folded: str, table: tuple[tuple[object, tuple[str, ...]], ...]) -> object | None:
    best: tuple[int, object] | None = None
    for value, words in table:
        for word in words:
            if _kw(re.escape(word)).search(folded) and (best is None or len(word) > best[0]):
                best = (len(word), value)
    return best[1] if best else None


def _spend_slots(folded: str) -> SpendSlots:
    category = _longest_match(folded, _CATEGORY_KEYWORDS)  # type: ignore[arg-type]
    period = _longest_match(folded, _PERIOD_KEYWORDS)  # type: ignore[arg-type]
    metric = _longest_match(folded, _METRIC_KEYWORDS)  # type: ignore[arg-type]
    return SpendSlots(
        category=category if isinstance(category, SpendCategory) else SpendCategory.ALL,
        period=period if isinstance(period, SpendPeriod) else SpendPeriod.THIS_MONTH,
        metric=metric if isinstance(metric, SpendMetric) else SpendMetric.TOTAL,
    )


def _split_slots(folded: str) -> SplitSlots | None:
    count_m = re.search(r"(\d{1,2})\s*(?:nguoi|ban)(?![a-z0-9])", folded)
    count = int(count_m.group(1)) if count_m and 2 <= int(count_m.group(1)) <= 20 else None
    mode: str | None = None
    if _kw(r"theo mon|tung mon").search(folded):
        mode = "BY_ITEM"
    elif _kw(r"chia deu|deu nhau|deu").search(folded):
        mode = "EQUAL"
    if count is None and mode is None:
        return None
    return SplitSlots(participants_count=count, mode=mode)  # type: ignore[arg-type]


def mock_plan(tokenized_command: str) -> PlannerIntent:
    nfc, folded = normalize(tokenized_command)
    if _TRANSFER_START_RE.match(folded):
        recipient: str | None = None
        m = _RECIPIENT_RE.search(folded)
        if m:
            recipient = nfc[m.start(1) : m.end(1)].strip()[:40] or None
        amount = pick_amount(nfc, folded)
        return PlannerIntent(
            intent=Intent.TRANSFER,
            transfer=TransferSlots(
                recipient_name=recipient,
                amount_vnd=amount,
                memo=extract_memo(nfc, folded, 60),
            ),
            confidence_level=Confidence.HIGH if recipient and amount is not None else Confidence.MEDIUM,
        )
    if _SPEND_RE.search(folded):
        return PlannerIntent(intent=Intent.SPEND_QUERY, spend=_spend_slots(folded), confidence_level=Confidence.HIGH)
    if _SPLIT_RE.search(folded):
        return PlannerIntent(intent=Intent.SPLIT_BILL, split=_split_slots(folded))
    if _PROMO_INTENT_RE.search(folded):
        return PlannerIntent(intent=Intent.CHECK_PROMO)
    if _SHOP_RE.search(folded):
        return PlannerIntent(intent=Intent.SHOP_CHECK)
    if _CONTENT_RE.search(folded):
        return PlannerIntent(intent=Intent.CHECK_CONTENT)
    return PlannerIntent(intent=Intent.UNKNOWN, confidence_level=Confidence.LOW)
