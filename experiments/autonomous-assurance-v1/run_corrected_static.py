#!/usr/bin/env python3
"""Run the static audit with Amendment 002's repository-URL correction.

The original instrument and its failed 495-case output remain preserved.
"""
from __future__ import annotations

import analyze_bugsinpy as base

_original_github_repo = base.github_repo


def github_repo(url: str) -> str | None:
    """Normalize an optional trailing slash before repository parsing."""
    return _original_github_repo(url.strip().rstrip("/"))


base.github_repo = github_repo


if __name__ == "__main__":
    raise SystemExit(base.main())
