"""Hypothesis strategies for Promo_Checker / Shop_Checker tests (Properties 36, 37)."""
from __future__ import annotations

from datetime import date, timedelta

from hypothesis import strategies as st

from guardian.features.promo_checker import OfficialPromo
from guardian.schemas.enums import Cue, PromoBrand
from guardian.schemas.extraction import PromoClaim

_codes = st.text(alphabet="ABCDEFGHXMOTE0123456789", min_size=3, max_size=10)


@st.composite
def official_promo_lists(draw: st.DrawFn) -> list[OfficialPromo]:
    out: list[OfficialPromo] = []
    for code in draw(st.lists(_codes, max_size=4, unique=True)):
        start = date(2026, 1, 1) + timedelta(days=draw(st.integers(0, 400)))
        end = start + timedelta(days=draw(st.integers(0, 60)))
        out.append(
            OfficialPromo(
                brand=draw(st.sampled_from([b.value for b in PromoBrand])),
                promo_code=code,
                title_vi="Khuyến mãi thử",
                valid_from=start,
                valid_to=end,
            )
        )
    return out


@st.composite
def promo_claims(draw: st.DrawFn, promos: list[OfficialPromo] | None = None) -> PromoClaim:
    """Claim that sometimes reuses an official code (random case) to exercise the match row."""
    code: str | None
    if promos and draw(st.booleans()):
        code = draw(st.sampled_from(promos)).promo_code
        code = "".join(c.lower() if draw(st.booleans()) else c for c in code)
    else:
        code = draw(st.one_of(st.none(), _codes))
    return PromoClaim(
        brand=draw(st.sampled_from(list(PromoBrand))),
        promo_code=code,
        requires_fee=draw(st.booleans()),
    )


promo_cues = st.lists(st.sampled_from(list(Cue)), max_size=3, unique=True)
