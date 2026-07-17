#!/usr/bin/env python3
"""Run the seeded 500-case finalizer with Amendment 003's public transport."""
from __future__ import annotations

import finalize_seeded_static as finalizer

_original_fetch_commit = finalizer.base.fetch_commit


def public_fetch_commit(repo: str, sha: str, _token: str):
    """Read the five public HTTPie commits without a repository-scoped token."""
    return _original_fetch_commit(repo, sha, "")


finalizer.base.fetch_commit = public_fetch_commit


if __name__ == "__main__":
    raise SystemExit(finalizer.main())
