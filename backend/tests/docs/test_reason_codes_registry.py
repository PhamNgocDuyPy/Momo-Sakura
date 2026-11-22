"""Registry <-> docs <-> code consistency for Reason_Codes."""

from __future__ import annotations

import re
from pathlib import Path

from guardian.reason_codes import REGISTRY

BACKEND = Path(__file__).resolve().parents[2]
GUARDIAN_DIR = BACKEND / "guardian"
DOC = BACKEND.parent / "docs" / "FLOWS_AND_GLOSSARY.md"
RC_PATTERN = re.compile(r"RC_[A-Z0-9_]{3,40}")
RC_DECL = re.compile(r"^RC_[A-Z0-9_]{3,40}\s*(?::[^=]+)?=", re.MULTILINE)


def _py_files() -> list[Path]:
    return [p for p in GUARDIAN_DIR.rglob("*.py") if "__pycache__" not in p.parts]


def test_every_registry_code_is_documented() -> None:
    text = DOC.read_text(encoding="utf-8")
    missing = [code for code in REGISTRY if code not in text]
    assert not missing, f"codes missing from docs/FLOWS_AND_GLOSSARY.md: {missing}"


def test_every_registry_code_has_meaning_in_docs() -> None:
    text = DOC.read_text(encoding="utf-8")
    missing = [c for c, s in REGISTRY.items() if s.meaning_vi not in text]
    assert not missing, f"meaning_vi not mirrored in docs for: {missing}"


def test_every_rc_string_in_code_is_registered() -> None:
    unknown: dict[str, list[str]] = {}
    for path in _py_files():
        for match in RC_PATTERN.findall(path.read_text(encoding="utf-8")):
            if match not in REGISTRY:
                unknown.setdefault(match, []).append(path.relative_to(BACKEND).as_posix())
    assert not unknown, f"RC_ strings not in REGISTRY: {unknown}"


def test_only_reason_codes_module_declares_rc_constants() -> None:
    offenders = [
        path.relative_to(BACKEND).as_posix()
        for path in _py_files()
        if path.name != "reason_codes.py" and RC_DECL.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"RC_ constants declared outside reason_codes.py: {offenders}"
    assert RC_DECL.search((GUARDIAN_DIR / "reason_codes.py").read_text(encoding="utf-8"))
