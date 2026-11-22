"""Deterministically regenerate fixtures/wallet_sandbox.json (seed 2026).

Run: python fixtures/gen_wallet.py
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

SEED = 2026
TZ = timezone(timedelta(hours=7))
OUT = Path(__file__).with_name("wallet_sandbox.json")
SANDBOX_NOW = datetime(2026, 11, 30, 20, 0, tzinfo=TZ)

MONTHS = [(2026, 9), (2026, 10), (2026, 11)]

# category -> (OUT count per month, merchants, monthly total target (vnd) by month)
RANDOM_CATEGORIES: dict[str, tuple[int, list[str], tuple[int, int, int]]] = {
    "CAFE": (28, ["Highlands Coffee", "The Coffee House", "Phúc Long", "Cộng Cà Phê", "Trà sữa Gong Cha"], (980_000, 1_120_000, 1_250_000)),
    "FOOD": (45, ["Cơm tấm Ba Ghiền", "Phở Hòa", "Bún bò Huế O Xuân", "Bánh mì Huynh Hoa", "GrabFood", "ShopeeFood"], (2_700_000, 2_900_000, 2_550_000)),
    "GROCERY": (14, ["Bách Hóa Xanh", "WinMart", "Co.opmart", "Circle K"], (1_800_000, 2_100_000, 1_950_000)),
    "TRANSPORT": (22, ["Grab", "Be", "Xanh SM", "Petrolimex"], (640_000, 720_000, 600_000)),
    "SHOPPING": (7, ["Shopee", "Lazada", "Tiki", "Uniqlo"], (1_500_000, 2_200_000, 1_800_000)),
    "ENTERTAINMENT": (5, ["CGV", "Lotte Cinema", "Steam", "Karaoke Nice"], (450_000, 600_000, 520_000)),
    "HEALTH": (3, ["Nhà thuốc Long Châu", "Phòng khám Vigor", "Pharmacity"], (300_000, 450_000, 380_000)),
    "EDUCATION": (1, ["Udemy"], (299_000, 399_000, 349_000)),
}
TRANSFER_OUT_COUNT = 6
TRANSFER_IN_COUNT = 3
FIXED_NOV_CAFE = {"id_hint": "highlands_last", "at": datetime(2026, 11, 30, 12, 10, tzinfo=TZ), "counterparty": "Highlands Coffee", "amount_vnd": 55_000}

SUBSCRIPTIONS = [
    ("sub_netflix", "Netflix", 260_000, 3, "2026-12-03", "2026-11-29T21:00:00+07:00"),
    ("sub_spotify", "Spotify", 59_000, 20, "2026-12-20", "2026-10-16T09:30:00+07:00"),
    ("sub_youtube", "YouTube Premium", 79_000, 10, "2026-12-10", "2026-11-30T18:45:00+07:00"),
]
EVN_AMOUNTS = {"2026-08": 600_000, "2026-09": 620_000, "2026-10": 580_000, "2026-11": 840_000}
FPT_AMOUNT = 220_000


def split_total(rng: random.Random, total: int, n: int) -> list[int]:
    """Split total into n positive amounts rounded to 1,000 that sum exactly to total."""
    if n == 1:
        return [total]
    weights = [rng.uniform(0.4, 1.6) for _ in range(n)]
    scale = total / sum(weights)
    parts = [max(1_000, round(w * scale / 1_000) * 1_000) for w in weights]
    parts[-1] = max(1_000, total - sum(parts[:-1]))
    diff = total - sum(parts)
    # absorb any rounding drift into the largest part
    parts[parts.index(max(parts))] += diff
    return parts


def random_time(rng: random.Random, year: int, month: int, last_day: int, cutoff: datetime | None = None) -> datetime:
    while True:
        day = rng.randint(1, last_day)
        at = datetime(year, month, day, rng.randint(7, 22), rng.choice([0, 5, 10, 15, 20, 30, 35, 40, 45, 50, 55]), tzinfo=TZ)
        if cutoff is None or at < cutoff:
            return at


def days_in(year: int, month: int) -> int:
    nxt = datetime(year + (month == 12), month % 12 + 1, 1)
    return (nxt - timedelta(days=1)).day


def build() -> dict:
    rng = random.Random(SEED)
    txns: list[dict] = []

    for mi, (year, month) in enumerate(MONTHS):
        last_day = days_in(year, month)
        cutoff = SANDBOX_NOW if (year, month) == (2026, 11) else None
        last = 30 if cutoff else last_day  # November data stops at 2026-11-30 20:00

        for category, (count, merchants, targets) in RANDOM_CATEGORIES.items():
            total = targets[mi]
            fixed = 0
            n = count
            if category == "CAFE" and cutoff:
                txns.append({"at": FIXED_NOV_CAFE["at"], "direction": "OUT", "category": "CAFE", "counterparty": FIXED_NOV_CAFE["counterparty"], "amount_vnd": FIXED_NOV_CAFE["amount_vnd"]})
                fixed, n = FIXED_NOV_CAFE["amount_vnd"], count - 1
            for amount in split_total(rng, total - fixed, n):
                at = random_time(rng, year, month, last, cutoff)
                txns.append({"at": at, "direction": "OUT", "category": category, "counterparty": rng.choice(merchants), "amount_vnd": amount})

        # BILLS: EVN (previous period), FPT internet, mobile top-up
        prev_period = f"{year}-{month - 1:02d}" if month > 1 else f"{year - 1}-12"
        for counterparty, amount, day in (("EVN TP.HCM", EVN_AMOUNTS[prev_period], 8), ("FPT Internet", FPT_AMOUNT, 12), ("Nạp tiền điện thoại", rng.choice([50_000, 100_000, 200_000]), 15)):
            txns.append({"at": datetime(year, month, day, rng.randint(8, 20), 0, tzinfo=TZ), "direction": "OUT", "category": "BILLS", "counterparty": counterparty, "amount_vnd": amount})

        # SUBSCRIPTION: one renewal per service per month
        for _sid, name, amount, day, _renew, _last_used in SUBSCRIPTIONS:
            txns.append({"at": datetime(year, month, day, 6, 0, tzinfo=TZ), "direction": "OUT", "category": "SUBSCRIPTION", "counterparty": name, "amount_vnd": amount})

        # TRANSFER_OUT / IN
        people = ["Nguyễn Văn Minh", "Trần Thị Lan", "Lê Quốc Bảo", "Mẹ"]
        for _ in range(TRANSFER_OUT_COUNT):
            txns.append({"at": random_time(rng, year, month, last, cutoff), "direction": "OUT", "category": "TRANSFER_OUT", "counterparty": rng.choice(people), "amount_vnd": rng.choice([100_000, 200_000, 300_000, 500_000, 1_000_000])})
        txns.append({"at": datetime(year, month, 5, 9, 0, tzinfo=TZ), "direction": "IN", "category": "TRANSFER_OUT", "counterparty": "Công ty Lương", "amount_vnd": 15_000_000})
        for _ in range(TRANSFER_IN_COUNT - 1):
            txns.append({"at": random_time(rng, year, month, last, cutoff), "direction": "IN", "category": "TRANSFER_OUT", "counterparty": rng.choice(people), "amount_vnd": rng.choice([100_000, 150_000, 250_000, 500_000])})

    txns.sort(key=lambda t: (t["at"], t["counterparty"], t["amount_vnd"]))
    transactions = [
        {"id": f"tx_{i:04d}", "at": t["at"].isoformat(), "direction": t["direction"], "category": t["category"], "counterparty": t["counterparty"], "amount_vnd": t["amount_vnd"]}
        for i, t in enumerate(txns, start=1)
    ]

    contacts = [
        {"id": "c_minh", "display_name": "Nguyễn Văn Minh", "aliases": [], "bank_bin": "970436", "account_number": "0123456789"},
        {"id": "c_lan_tran", "display_name": "Trần Thị Lan", "aliases": [], "bank_bin": "970415", "account_number": "0441234501"},
        {"id": "c_lan_pham", "display_name": "Phạm Ngọc Lan", "aliases": [], "bank_bin": "970418", "account_number": "0441234502"},
        {"id": "c_bao", "display_name": "Lê Quốc Bảo", "aliases": [], "bank_bin": "970423", "account_number": "00001234567"},
        {"id": "c_me", "display_name": "Mẹ", "aliases": ["má", "mẹ yêu"], "bank_bin": "970405", "account_number": "0901234567"},
    ]

    bills: list[dict] = []
    for period, amount in EVN_AMOUNTS.items():
        bills.append(_bill("EVN_HCMC", "Điện lực TP.HCM", period, amount))
    for period in ("2026-10", "2026-11"):
        bills.append(_bill("SAWACO", "Cấp nước Sài Gòn", period, 150_000 if period == "2026-10" else 155_000))
    for period in EVN_AMOUNTS:
        bills.append(_bill("FPT_INTERNET", "FPT Internet", period, FPT_AMOUNT))

    subscriptions = [
        {"id": sid, "name": name, "amount_vnd": amount, "renewal_date": renew, "last_used_at": last_used}
        for sid, name, amount, _day, renew, last_used in SUBSCRIPTIONS
    ]

    return {
        "as_of": SANDBOX_NOW.isoformat(),
        "transactions": transactions,
        "contacts": contacts,
        "bills": bills,
        "subscriptions": subscriptions,
        "budgets": [
            {"category": "FOOD", "limit_vnd": 3_000_000},
            {"category": "CAFE", "limit_vnd": 1_000_000},
            {"category": "TRANSPORT", "limit_vnd": 1_500_000},
        ],
        "trusted_contacts": [{"name": "Mẹ", "phone": "0901234567"}],
        "profile": {"display_name": "DEMO USER", "bank_bin": "970436", "account_number": "0071000999888"},
    }


def _bill(provider_id: str, provider_name: str, period: str, amount: int) -> dict:
    year, month = map(int, period.split("-"))
    due_year, due_month = (year + (month == 12), month % 12 + 1)
    return {
        "provider_id": provider_id,
        "provider_name": provider_name,
        "period": period,
        "amount_vnd": amount,
        "due_date": f"{due_year}-{due_month:02d}-05",
        "status": "UNPAID" if period == "2026-11" else "PAID",
    }


def main() -> None:
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
