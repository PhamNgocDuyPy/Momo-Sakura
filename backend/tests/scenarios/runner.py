"""Compatibility shim: the scenario runner lives in ``eval.runner``."""

from __future__ import annotations

from eval.runner import CaseResult, RunResult, make_settings, run_scenario

__all__ = ["CaseResult", "RunResult", "make_settings", "run_scenario"]
