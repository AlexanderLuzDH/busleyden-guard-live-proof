from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


REPORT_MARKER = "PLATONIC_GITHUB_CHANGE_CONSEQUENCE_REAL_REPO_PR_REPORT_JSON="
CHANGED_FILE = "src/click/formatting.py"
EXPECTED_TEST = "tests/test_formatting.py"


def compact_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def main() -> None:
    report = json.loads(Path("change-consequence.json").read_text(encoding="utf-8"))
    comment = Path("change-consequence.md").read_text(encoding="utf-8")
    certificate = report["certificate"]
    tests = certificate["evidence"]["tests"]
    owners = certificate["evidence"]["owners"]
    hosted_trace = certificate["evidence"]["hosted_runtime_trace"]
    hosted_action = certificate["evidence"]["hosted_github_action"]
    hosted_pr = certificate["evidence"]["hosted_pull_request"]
    semgrep = certificate["evidence"]["security"]["semgrep"]
    osv = certificate["evidence"]["dependencies"]["osv"]
    subject = certificate["subject"]
    assert report["change_consequence_certificate_gate"] is True
    assert report["digest_verified"] is True
    assert certificate["digest_verified"] is True
    assert os.environ["ACTION_CERTIFICATE_ID"] == certificate["certificate_id"]
    assert os.environ["ACTION_CONTENT_ADDRESS"] == certificate["content_address"]
    assert os.environ["ACTION_POLICY_STATUS"] == certificate["policy_result"]["status"]
    assert subject["changed_files"] == [CHANGED_FILE]
    assert tests["affected_tests"] == [EXPECTED_TEST]
    assert tests["direct_test_map"][CHANGED_FILE] == EXPECTED_TEST
    assert owners["formal_owner_file_count"] == 1
    assert owners["files"][0]["formal_codeowners"] == ["@platform/team"]
    assert hosted_trace["hosted_gate"] is True
    assert hosted_trace["snapshot_fanout_speedup"] >= 1000.0
    assert hosted_action["hosted_action_gate"] is True
    assert hosted_pr["hosted_pr_gate"] is True
    assert semgrep["status"] == "available"
    assert semgrep["finding_count"] == 1
    assert osv["status"] == "available"
    assert isinstance(osv["vulnerability_count"], int)
    assert "### Scanner Evidence" in comment
    assert "Semgrep: `available`, findings: 1" in comment
    assert EXPECTED_TEST in comment
    payload = {
        "kind": "github_change_consequence_real_repo_pr_payload",
        "github_change_consequence_real_repo_pr_gate": True,
        "pr_number": int(os.environ["PR_NUMBER"]),
        "certificate_id": certificate["certificate_id"],
        "content_address": certificate["content_address"],
        "policy_status": certificate["policy_result"]["status"],
        "changed_files": subject["changed_files"],
        "affected_tests": tests["affected_tests"],
        "formal_owner_file_count": owners["formal_owner_file_count"],
        "unknown_count": len(certificate["unknowns"]),
        "hosted_trace_speedup": hosted_trace["snapshot_fanout_speedup"],
        "semgrep_finding_count": semgrep["finding_count"],
        "osv_vulnerability_count": osv["vulnerability_count"],
        "comment_headline_present": "## Change Consequence Certificate" in comment,
    }
    print(REPORT_MARKER + compact_json(payload))


if __name__ == "__main__":
    main()
