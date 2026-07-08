"""GitHub Action entrypoint for change consequence certificates."""

from __future__ import annotations

import json
import os
from pathlib import Path

import change_consequence_certificate as certificate


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def split_changed_files(value: str) -> tuple[str, ...]:
    if not value:
        return ()
    normalized = value.replace(",", "\n")
    return tuple(line.strip() for line in normalized.splitlines() if line.strip())


def path_input(name: str, repo_root: Path, default: Path | None = None) -> Path:
    value = env(name)
    if not value:
        if default is None:
            raise ValueError(f"{name} is required")
        return default
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def optional_report_path(name: str, repo_root: Path, default: Path) -> Path:
    value = env(name)
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def append_github_output(values: dict[str, str]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with Path(output_path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def append_step_summary(markdown: str) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with Path(summary_path).open("a", encoding="utf-8") as handle:
        handle.write(markdown)
        handle.write("\n")


def main() -> None:
    repo_root = Path(env("INPUT_REPO_ROOT") or os.environ.get("GITHUB_WORKSPACE", ".")).resolve()
    output_path = path_input(
        "INPUT_OUTPUT",
        repo_root,
        repo_root / "change-consequence.json",
    )
    comment_path = path_input(
        "INPUT_COMMENT_OUTPUT",
        repo_root,
        repo_root / "change-consequence.md",
    )
    report = certificate.build_report(
        repo_root=repo_root,
        changed_files=split_changed_files(env("INPUT_CHANGED_FILES")),
        base_ref=env("INPUT_BASE") or None,
        head_ref=env("INPUT_HEAD") or None,
        hosted_trace_report_path=optional_report_path(
            "INPUT_HOSTED_TRACE_REPORT",
            repo_root,
            certificate.DEFAULT_HOSTED_TRACE_REPORT_PATH,
        ),
        revolutionary_gate_path=optional_report_path(
            "INPUT_REVOLUTIONARY_GATE",
            repo_root,
            certificate.DEFAULT_REVOLUTIONARY_GATE_PATH,
        ),
        action_proof_path=optional_report_path(
            "INPUT_ACTION_PROOF",
            repo_root,
            certificate.DEFAULT_ACTION_PROOF_PATH,
        ),
        pr_proof_path=optional_report_path(
            "INPUT_PR_PROOF",
            repo_root,
            certificate.DEFAULT_PR_PROOF_PATH,
        ),
        semgrep_report_path=optional_report_path(
            "INPUT_SEMGREP_REPORT",
            repo_root,
            certificate.DEFAULT_SEMGREP_REPORT_PATH,
        ),
        osv_report_path=optional_report_path(
            "INPUT_OSV_REPORT",
            repo_root,
            certificate.DEFAULT_OSV_REPORT_PATH,
        ),
    )
    certificate.write_report(report, output_path, comment_path)
    cert = report["certificate"]
    outputs = {
        "certificate-id": cert["certificate_id"],
        "content-address": cert["content_address"],
        "policy-status": cert["policy_result"]["status"],
        "gate": str(report["change_consequence_certificate_gate"]).lower(),
        "report-path": str(output_path),
        "comment-path": str(comment_path),
        "affected-test-count": str(cert["evidence"]["tests"]["affected_test_count"]),
        "unknown-count": str(len(cert["unknowns"])),
    }
    append_github_output(outputs)
    append_step_summary(report["pr_comment_markdown"])
    print(json.dumps({"outputs": outputs, "report_id": report["report_id"]}, sort_keys=True))


if __name__ == "__main__":
    main()
