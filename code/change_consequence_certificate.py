"""Generate a consequence certificate for AI-authored code changes.

The product surface is intentionally narrow: for a proposed change, emit a
content-addressed JSON certificate and a PR-comment summary that say what is
known, what must be reviewed, and what is still unknown.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from platonic_core.hashing import stable_hash


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = ROOT / "notes" / "change_consequence_certificate_report.json"
DEFAULT_COMMENT_PATH = ROOT / "notes" / "change_consequence_pr_comment.md"
DEFAULT_HOSTED_TRACE_REPORT_PATH = (
    ROOT / "notes" / "github_upstream_pytest_runtime_trace_fanout_proof_report.json"
)
DEFAULT_REVOLUTIONARY_GATE_PATH = ROOT / "notes" / "revolutionary_result_gate_report.json"
DEFAULT_ACTION_PROOF_PATH = ROOT / "notes" / "github_change_consequence_action_proof_report.json"
DEFAULT_PR_PROOF_PATH = ROOT / "notes" / "github_change_consequence_pr_proof_report.json"
DEFAULT_SEMGREP_REPORT_PATH = ROOT / "notes" / "semgrep_report.json"
DEFAULT_OSV_REPORT_PATH = ROOT / "notes" / "osv_report.json"
CODEOWNERS_CANDIDATES = (
    "CODEOWNERS",
    ".github/CODEOWNERS",
    "docs/CODEOWNERS",
)


@dataclass(frozen=True)
class CodeownersRule:
    line_number: int
    pattern: str
    owners: tuple[str, ...]


@dataclass(frozen=True)
class CodeownersIndex:
    path: str | None
    rules: tuple[CodeownersRule, ...]


def relative_path(path: Path, root: Path = ROOT) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def normalize_changed_file(path: str) -> str:
    normalized = Path(path.replace("\\", "/")).as_posix()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def normalize_owner(owner: str) -> str:
    return owner.strip().lower()


def strip_inline_comment(line: str) -> str:
    escaped = False
    output: list[str] = []
    for char in line:
        if char == "\\" and not escaped:
            escaped = True
            output.append(char)
            continue
        if char == "#" and not escaped:
            break
        escaped = False
        output.append(char)
    return "".join(output).strip()


def parse_codeowners_text(text: str) -> tuple[CodeownersRule, ...]:
    rules: list[CodeownersRule] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = strip_inline_comment(raw_line)
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        pattern = parts[0].replace("\\#", "#")
        owners = tuple(normalize_owner(owner) for owner in parts[1:] if owner.strip())
        if owners:
            rules.append(CodeownersRule(line_number=line_number, pattern=pattern, owners=owners))
    return tuple(rules)


def find_codeowners(repo_root: Path) -> tuple[Path | None, tuple[CodeownersRule, ...]]:
    for candidate in CODEOWNERS_CANDIDATES:
        path = repo_root / candidate
        if path.exists() and path.is_file():
            return path, parse_codeowners_text(path.read_text(encoding="utf-8", errors="replace"))
    return None, ()


def match_codeowners_pattern(pattern: str, filename: str) -> bool:
    path = normalize_changed_file(filename)
    pattern = pattern.strip()
    if not pattern or pattern.startswith("!"):
        return False
    rooted = pattern.startswith("/")
    pattern = pattern.lstrip("/")
    if pattern.endswith("/"):
        prefix = pattern.rstrip("/")
        return path == prefix or path.startswith(f"{prefix}/")
    if "/" not in pattern:
        return fnmatch.fnmatch(Path(path).name, pattern) or fnmatch.fnmatch(path, f"**/{pattern}")
    if rooted:
        return fnmatch.fnmatch(path, pattern)
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, f"**/{pattern}")


def codeowners_for_file(rules: tuple[CodeownersRule, ...], filename: str) -> tuple[str, ...]:
    matched: tuple[str, ...] = ()
    for rule in rules:
        if match_codeowners_pattern(rule.pattern, filename):
            matched = rule.owners
    return matched


def build_codeowners_index(repo_root: Path) -> CodeownersIndex:
    path, rules = find_codeowners(repo_root)
    relative = path.relative_to(repo_root).as_posix() if path else None
    return CodeownersIndex(path=relative, rules=rules)


def run_git(repo_root: Path, args: list[str]) -> tuple[int, str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return completed.returncode, completed.stdout.strip()


def changed_files_from_git(repo_root: Path, base_ref: str | None, head_ref: str | None) -> tuple[str, ...]:
    if base_ref and head_ref:
        code, output = run_git(repo_root, ["diff", "--name-only", f"{base_ref}...{head_ref}"])
        if code == 0:
            return tuple(normalize_changed_file(line) for line in output.splitlines() if line.strip())
    code, output = run_git(repo_root, ["status", "--short"])
    if code != 0:
        return ()
    changed: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        item = line[3:].strip()
        if " -> " in item:
            item = item.split(" -> ", 1)[1]
        changed.append(normalize_changed_file(item))
    return tuple(sorted(set(changed)))


def load_json_if_present(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_hosted_trace(report: dict[str, Any] | None, report_path: Path) -> dict[str, Any]:
    if not report:
        return {
            "status": "missing",
            "path": relative_path(report_path),
            "impact": "No hosted runtime-trace proof was found.",
        }
    payload = report.get("external_payload", {})
    summary = payload.get("external_report_summary", {})
    accounting = summary.get("fanout_accounting", {})
    substrate = summary.get("selected_substrate", {})
    trace = summary.get("trace_summary", {})
    external_repo = report.get("external_repo", {})
    verifier_repo = report.get("verifier_repo", {})
    workflow_run = report.get("workflow_run", {})
    return {
        "status": "available",
        "path": relative_path(report_path),
        "report_id": report.get("report_id"),
        "workflow_run_url": (
            external_repo.get("workflow_run_url")
            or workflow_run.get("workflow_run_url")
            or workflow_run.get("url")
        ),
        "public_repo": (
            external_repo.get("repo_url")
            or external_repo.get("repo_html_url")
            or verifier_repo.get("repo_url")
        ),
        "hosted_gate": bool(report.get("github_upstream_pytest_runtime_trace_fanout_gate")),
        "runtime_trace_event_count": trace.get("runtime_trace_event_count"),
        "upstream_test_count": trace.get("upstream_test_count"),
        "traced_file_count": trace.get("traced_file_count"),
        "selected_plan": substrate.get("plan_id"),
        "snapshot_fanout_speedup": accounting.get("snapshot_fanout_speedup"),
        "low_request_speedup": accounting.get("low_request_speedup"),
        "claim_boundary": report.get("claim_boundary") or payload.get("claim_boundary"),
    }


def summarize_revolutionary_gate(report: dict[str, Any] | None, report_path: Path) -> dict[str, Any]:
    if not report:
        return {
            "status": "missing",
            "path": relative_path(report_path),
            "impact": "No aggregate result gate report was found.",
        }
    positives = report.get("positive_evidence", [])
    return {
        "status": "available",
        "path": relative_path(report_path),
        "report_id": report.get("report_id"),
        "classification": report.get("classification"),
        "computational_revolution_candidate": bool(report.get("computational_revolution_candidate")),
        "production_business_revolution_proven": bool(report.get("production_business_revolution_proven")),
        "positive_evidence_count": len(positives),
        "failed_positive_evidence_count": len(report.get("failed_positive_evidence", [])),
        "claim_boundary": report.get("claim_boundary"),
    }


def summarize_action_proof(report: dict[str, Any] | None, report_path: Path) -> dict[str, Any]:
    if not report:
        return {
            "status": "missing",
            "path": relative_path(report_path),
            "impact": "No hosted GitHub Action packaging proof was found.",
        }
    workflow = report.get("workflow_run", {})
    repo = report.get("verifier_repo", {})
    metrics = report.get("hosted_metrics", {})
    return {
        "status": "available",
        "path": relative_path(report_path),
        "report_id": report.get("report_id"),
        "public_repo": repo.get("repo_url"),
        "workflow_run_url": workflow.get("workflow_run_url"),
        "workflow_conclusion": workflow.get("workflow_conclusion"),
        "hosted_action_gate": bool(report.get("github_change_consequence_action_gate")),
        "affected_test_count": metrics.get("affected_test_count"),
        "formal_owner_file_count": metrics.get("formal_owner_file_count"),
        "hosted_trace_speedup": metrics.get("hosted_trace_speedup"),
        "claim_boundary": report.get("claim_boundary"),
    }


def summarize_pr_proof(report: dict[str, Any] | None, report_path: Path) -> dict[str, Any]:
    if not report:
        return {
            "status": "missing",
            "path": relative_path(report_path),
            "impact": "No hosted pull-request proof was found.",
        }
    workflow = report.get("workflow_run", {})
    pr = report.get("pull_request", {})
    comment = report.get("pr_comment", {})
    metrics = report.get("hosted_metrics", {})
    return {
        "status": "available",
        "path": relative_path(report_path),
        "report_id": report.get("report_id"),
        "pull_request_url": pr.get("url"),
        "comment_url": comment.get("comment_url"),
        "workflow_run_url": workflow.get("workflow_run_url"),
        "workflow_conclusion": workflow.get("workflow_conclusion"),
        "hosted_pr_gate": bool(report.get("github_change_consequence_pr_gate")),
        "affected_test_count": metrics.get("affected_test_count"),
        "formal_owner_file_count": metrics.get("formal_owner_file_count"),
        "semgrep_finding_count": metrics.get("semgrep_finding_count"),
        "osv_vulnerability_count": metrics.get("osv_vulnerability_count"),
        "hosted_trace_speedup": metrics.get("hosted_trace_speedup"),
        "claim_boundary": report.get("claim_boundary"),
    }


def top_git_authors(repo_root: Path, filename: str, limit: int = 5) -> tuple[str, ...]:
    code, output = run_git(repo_root, ["log", "--format=%ae", "--", filename])
    if code != 0 or not output:
        return ()
    counts: dict[str, int] = {}
    for email in output.splitlines():
        email = email.strip().lower()
        if email:
            counts[email] = counts.get(email, 0) + 1
    return tuple(email for email, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit])


def ownership_evidence(repo_root: Path, changed_files: tuple[str, ...]) -> dict[str, Any]:
    codeowners = build_codeowners_index(repo_root)
    rows: list[dict[str, Any]] = []
    formal_count = 0
    git_count = 0
    for filename in changed_files:
        formal = codeowners_for_file(codeowners.rules, filename)
        authors = top_git_authors(repo_root, filename)
        if formal:
            formal_count += 1
        if authors:
            git_count += 1
        rows.append(
            {
                "file": filename,
                "formal_codeowners": list(formal),
                "git_history_authors": list(authors),
                "owner_source": "codeowners" if formal else ("git_history" if authors else "unknown"),
            }
        )
    return {
        "codeowners_path": codeowners.path,
        "codeowners_rule_count": len(codeowners.rules),
        "changed_file_count": len(changed_files),
        "formal_owner_file_count": formal_count,
        "git_history_owner_file_count": git_count,
        "unowned_file_count": len(changed_files) - len({row["file"] for row in rows if row["owner_source"] != "unknown"}),
        "files": rows,
    }


def generic_direct_test_for_source(repo_root: Path, path: str) -> str | None:
    if not path.endswith(".py"):
        return None
    filename = Path(path).name
    if filename.startswith("test_"):
        return path
    candidates = (
        Path(path).with_name(f"test_{filename}"),
        Path("tests") / f"test_{filename}",
        Path("test") / f"test_{filename}",
    )
    for candidate in candidates:
        if (repo_root / candidate).is_file():
            return candidate.as_posix()
    return None


def direct_test_for_repo(repo_root: Path, path: str) -> str | None:
    if repo_root.resolve() == ROOT.resolve():
        try:
            import verify

            mapped = verify.direct_test_for_source(path)
            if mapped:
                return mapped
        except Exception:
            pass
    return generic_direct_test_for_source(repo_root, path)


def affected_tests_for_repo(repo_root: Path, changed_files: tuple[str, ...]) -> tuple[str, ...]:
    if repo_root.resolve() == ROOT.resolve():
        try:
            import verify

            return verify.affected_tests_for_paths(changed_files)
        except Exception:
            pass
    selected: list[str] = []
    seen: set[str] = set()
    for filename in changed_files:
        mapped = direct_test_for_repo(repo_root, filename)
        if mapped and mapped not in seen:
            selected.append(mapped)
            seen.add(mapped)
    return tuple(selected)


def test_impact_evidence(repo_root: Path, changed_files: tuple[str, ...]) -> dict[str, Any]:
    affected = affected_tests_for_repo(repo_root, changed_files)
    direct: dict[str, str] = {}
    for filename in changed_files:
        mapped = direct_test_for_repo(repo_root, filename)
        if mapped:
            direct[filename] = mapped
    return {
        "affected_tests": list(affected),
        "affected_test_count": len(affected),
        "direct_test_map": direct,
        "direct_test_count": len(direct),
        "selector": "repo_native_mapping_with_platonic_verify_fast_path",
        "claim_boundary": "This is a local mapped-test signal. It is not full dynamic coverage for every runtime path.",
    }


def first_existing_report(repo_root: Path, explicit_path: Path | None, pattern: str) -> Path | None:
    if explicit_path and explicit_path.is_file():
        return explicit_path
    notes = repo_root / "notes"
    candidates = sorted(notes.glob(pattern)) if notes.is_dir() else []
    return candidates[-1] if candidates else None


def semgrep_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("results"), list):
        return list(payload["results"])
    sarif_results: list[dict[str, Any]] = []
    for run in payload.get("runs", []):
        rules = {
            rule.get("id"): rule
            for tool in [run.get("tool", {})]
            for driver in [tool.get("driver", {})]
            for rule in driver.get("rules", [])
        }
        for result in run.get("results", []):
            rule = rules.get(result.get("ruleId"), {})
            locations = result.get("locations", [])
            location = locations[0].get("physicalLocation", {}) if locations else {}
            artifact = location.get("artifactLocation", {})
            region = location.get("region", {})
            sarif_results.append(
                {
                    "check_id": result.get("ruleId"),
                    "path": artifact.get("uri"),
                    "start": {"line": region.get("startLine")},
                    "extra": {
                        "severity": result.get("level") or rule.get("defaultConfiguration", {}).get("level"),
                        "message": result.get("message", {}).get("text"),
                    },
                }
            )
    return sarif_results


def normalize_semgrep_severity(value: Any) -> str:
    severity = str(value or "unknown").strip().lower()
    if severity in {"error", "critical", "high"}:
        return "high"
    if severity in {"warning", "medium"}:
        return "medium"
    if severity in {"note", "info", "informational", "low"}:
        return "low"
    return severity or "unknown"


def optional_security_evidence(repo_root: Path, report_path: Path | None = None) -> dict[str, Any]:
    selected = first_existing_report(repo_root, report_path, "*semgrep*.json")
    if not selected:
        return {
            "semgrep": {
                "status": "not_configured",
                "finding_count": None,
                "blocking_finding_count": None,
                "required_next_step": "Run Semgrep in CI and attach SARIF or JSON to this certificate.",
            }
        }
    payload = load_json_if_present(selected) or {}
    results = semgrep_results(payload)
    severity_counts: dict[str, int] = {}
    findings: list[dict[str, Any]] = []
    for result in results:
        extra = result.get("extra", {})
        severity = normalize_semgrep_severity(extra.get("severity") or result.get("level"))
        severity_counts[severity] = severity_counts.get(severity, 0) + 1
        findings.append(
            {
                "rule_id": result.get("check_id") or result.get("ruleId"),
                "path": result.get("path"),
                "line": (result.get("start") or {}).get("line"),
                "severity": severity,
                "message": extra.get("message") or result.get("message"),
            }
        )
    blocking = severity_counts.get("high", 0)
    return {
        "semgrep": {
            "status": "available",
            "path": relative_path(selected, repo_root),
            "finding_count": len(results),
            "blocking_finding_count": blocking,
            "severity_counts": severity_counts,
            "top_findings": findings[:10],
        }
    }


def osv_vulnerabilities(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("vulns"), list):
        return list(payload["vulns"])
    vulnerabilities: list[dict[str, Any]] = []
    for result in payload.get("results", []):
        for package in result.get("packages", []):
            package_info = package.get("package", {})
            for vuln in package.get("vulnerabilities", []):
                vulnerabilities.append(
                    {
                        "id": vuln.get("id"),
                        "summary": vuln.get("summary"),
                        "package": package_info.get("name"),
                        "version": package_info.get("version"),
                    }
                )
        for vuln in result.get("vulnerabilities", []):
            vulnerabilities.append(vuln)
    return vulnerabilities


def optional_dependency_evidence(repo_root: Path, report_path: Path | None = None) -> dict[str, Any]:
    selected = first_existing_report(repo_root, report_path, "*osv*.json")
    if not selected:
        return {
            "osv": {
                "status": "not_configured",
                "vulnerability_count": None,
                "required_next_step": "Run OSV-Scanner or equivalent dependency audit in CI and attach the output.",
            }
        }
    payload = load_json_if_present(selected) or {}
    vulns = osv_vulnerabilities(payload)
    return {
        "osv": {
            "status": "available",
            "path": relative_path(selected, repo_root),
            "vulnerability_count": len(vulns),
            "blocking_vulnerability_count": len(vulns),
            "top_vulnerabilities": vulns[:10],
        }
    }


def repository_subject(repo_root: Path, changed_files: tuple[str, ...], base_ref: str | None, head_ref: str | None) -> dict[str, Any]:
    _remote_code, remote_url = run_git(repo_root, ["config", "--get", "remote.origin.url"])
    _sha_code, head_sha = run_git(repo_root, ["rev-parse", "HEAD"])
    return {
        "repo_root": str(repo_root.resolve()),
        "remote_url": remote_url or None,
        "base_ref": base_ref,
        "head_ref": head_ref,
        "head_sha": head_sha or None,
        "changed_files": list(changed_files),
        "changed_file_count": len(changed_files),
    }


def build_unknowns(
    *,
    owners: dict[str, Any],
    security: dict[str, Any],
    dependencies: dict[str, Any],
    hosted_trace: dict[str, Any],
    revolutionary_gate: dict[str, Any],
    action_proof: dict[str, Any],
) -> list[str]:
    unknowns: list[str] = []
    if owners["formal_owner_file_count"] < owners["changed_file_count"]:
        unknowns.append("Some changed files lack formal CODEOWNERS coverage.")
    if security["semgrep"]["status"] != "available":
        unknowns.append("Static security findings are unknown because Semgrep output is not attached.")
    if dependencies["osv"]["status"] != "available":
        unknowns.append("Dependency vulnerability impact is unknown because OSV output is not attached.")
    if hosted_trace["status"] != "available" or not hosted_trace.get("hosted_gate"):
        unknowns.append("Hosted runtime-trace impact proof is missing or did not pass.")
    if not revolutionary_gate.get("production_business_revolution_proven", False):
        unknowns.append("Business value is not production-proven by this certificate; it is a gated PR-decision artifact.")
    if action_proof["status"] == "available" and not action_proof.get("hosted_action_gate"):
        unknowns.append("Hosted GitHub Action packaging proof is attached but did not pass.")
    return unknowns


def required_review_surfaces(owners: dict[str, Any], tests: dict[str, Any], unknowns: list[str]) -> list[str]:
    surfaces = ["human reviewer reads the changed files"]
    if owners["formal_owner_file_count"] or owners["git_history_owner_file_count"]:
        surfaces.append("owner review")
    else:
        surfaces.append("explicit owner assignment")
    if tests["affected_test_count"]:
        surfaces.append("affected mapped tests")
    else:
        surfaces.append("manual test plan")
    if any("Semgrep" in item for item in unknowns):
        surfaces.append("security scan")
    if any("OSV" in item for item in unknowns):
        surfaces.append("dependency audit")
    return surfaces


def policy_result(
    owners: dict[str, Any],
    tests: dict[str, Any],
    security: dict[str, Any],
    dependencies: dict[str, Any],
    unknowns: list[str],
) -> dict[str, Any]:
    merge_blockers = [
        item
        for item in unknowns
        if item.startswith("Static security") or item.startswith("Dependency vulnerability")
    ]
    semgrep_blocking = security["semgrep"].get("blocking_finding_count") or 0
    osv_blocking = dependencies["osv"].get("blocking_vulnerability_count") or 0
    if semgrep_blocking:
        merge_blockers.append(f"Semgrep has {semgrep_blocking} high-severity blocking finding(s).")
    if osv_blocking:
        merge_blockers.append(f"OSV has {osv_blocking} dependency vulnerability finding(s).")
    if merge_blockers or not tests["affected_test_count"] or owners["formal_owner_file_count"] == 0:
        status = "attention_required"
    elif unknowns:
        status = "review_with_unknowns"
    else:
        status = "ready_for_standard_review"
    return {
        "status": status,
        "required_review_surfaces": required_review_surfaces(owners, tests, unknowns),
        "merge_blockers": merge_blockers,
    }


def monetizable_path() -> dict[str, Any]:
    return {
        "product": "AI PR consequence certificate",
        "buyer": "engineering platform, AppSec, compliance, and release owners",
        "job_to_be_done": "Turn fast AI code generation into reviewable, auditable, policy-gated changes.",
        "why_people_pay": [
            "Every AI-generated PR creates uncertainty about tests, owners, security, and downstream blast radius.",
            "The certificate converts that uncertainty into a stable artifact that CI, auditors, and humans can inspect.",
            "The hosted trace evidence shows the underlying impact substrate can fan out consequences orders of magnitude faster than repeated recomputation.",
        ],
        "initial_pricing_hypothesis_usd": {
            "team_monthly": 500,
            "business_monthly": 2500,
            "enterprise_annual_floor": 25000,
        },
    }


def build_certificate(
    *,
    repo_root: Path = ROOT,
    changed_files: tuple[str, ...] = (),
    base_ref: str | None = None,
    head_ref: str | None = None,
    hosted_trace_report_path: Path = DEFAULT_HOSTED_TRACE_REPORT_PATH,
    revolutionary_gate_path: Path = DEFAULT_REVOLUTIONARY_GATE_PATH,
    action_proof_path: Path = DEFAULT_ACTION_PROOF_PATH,
    pr_proof_path: Path = DEFAULT_PR_PROOF_PATH,
    semgrep_report_path: Path | None = None,
    osv_report_path: Path | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    normalized_changed = tuple(sorted(set(normalize_changed_file(path) for path in changed_files)))
    if not normalized_changed:
        normalized_changed = changed_files_from_git(repo_root, base_ref, head_ref)
    hosted_trace = summarize_hosted_trace(load_json_if_present(hosted_trace_report_path), hosted_trace_report_path)
    revolutionary = summarize_revolutionary_gate(load_json_if_present(revolutionary_gate_path), revolutionary_gate_path)
    action_proof = summarize_action_proof(load_json_if_present(action_proof_path), action_proof_path)
    pr_proof = summarize_pr_proof(load_json_if_present(pr_proof_path), pr_proof_path)
    owners = ownership_evidence(repo_root, normalized_changed)
    tests = test_impact_evidence(repo_root, normalized_changed)
    security = optional_security_evidence(repo_root, semgrep_report_path)
    dependencies = optional_dependency_evidence(repo_root, osv_report_path)
    unknowns = build_unknowns(
        owners=owners,
        security=security,
        dependencies=dependencies,
        hosted_trace=hosted_trace,
        revolutionary_gate=revolutionary,
        action_proof=action_proof,
    )
    certificate_body = {
        "schema_version": 1,
        "kind": "change_consequence_certificate",
        "subject": repository_subject(repo_root, normalized_changed, base_ref, head_ref),
        "evidence": {
            "tests": tests,
            "owners": owners,
            "security": security,
            "dependencies": dependencies,
            "hosted_runtime_trace": hosted_trace,
            "aggregate_revolutionary_gate": revolutionary,
            "hosted_github_action": action_proof,
            "hosted_pull_request": pr_proof,
        },
        "unknowns": unknowns,
        "limitations": [
            "The certificate is only as complete as attached CI evidence.",
            "Mapped tests do not replace full-suite, integration, or production canary validation.",
            "Owner evidence is advisory unless repository policy enforces it.",
            "This artifact is not a legal compliance attestation by itself.",
        ],
        "policy_result": policy_result(owners, tests, security, dependencies, unknowns),
        "monetizable_path": monetizable_path(),
    }
    certificate_id = stable_hash(certificate_body)
    in_toto_statement = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [
            {
                "name": "change-consequence-certificate",
                "digest": {"sha256": certificate_id.lower()},
            }
        ],
        "predicateType": "https://platonic.local/predicate/change-consequence/v1",
        "predicate": {
            "changed_file_count": len(normalized_changed),
            "policy_status": certificate_body["policy_result"]["status"],
            "affected_test_count": tests["affected_test_count"],
            "formal_owner_file_count": owners["formal_owner_file_count"],
            "unknown_count": len(unknowns),
        },
    }
    certificate = {
        **certificate_body,
        "certificate_id": certificate_id,
        "content_address": f"sha256:{certificate_id.lower()}",
        "digest_verified": stable_hash(certificate_body) == certificate_id,
        "in_toto_statement": in_toto_statement,
    }
    return certificate


def pr_comment(certificate: dict[str, Any]) -> str:
    subject = certificate["subject"]
    tests = certificate["evidence"]["tests"]
    owners = certificate["evidence"]["owners"]
    hosted = certificate["evidence"]["hosted_runtime_trace"]
    action_proof = certificate["evidence"]["hosted_github_action"]
    pr_proof = certificate["evidence"]["hosted_pull_request"]
    semgrep = certificate["evidence"]["security"]["semgrep"]
    osv = certificate["evidence"]["dependencies"]["osv"]
    policy = certificate["policy_result"]
    unknowns = certificate["unknowns"]
    affected_tests = tests["affected_tests"] or ["No mapped tests found"]
    owner_rows = [
        f"- `{row['file']}`: {', '.join(row['formal_codeowners'] or row['git_history_authors'] or ['unknown'])}"
        for row in owners["files"][:12]
    ]
    unknown_rows = [f"- {item}" for item in unknowns] or ["- No explicit unknowns recorded."]
    speedup = hosted.get("snapshot_fanout_speedup", "unknown")
    workflow_url = hosted.get("workflow_run_url") or "not attached"
    action_proof_url = action_proof.get("workflow_run_url") or "not attached"
    pr_proof_url = pr_proof.get("pull_request_url") or "not attached"
    semgrep_line = (
        f"`{semgrep['status']}`"
        if semgrep["status"] != "available"
        else (
            f"`available`, findings: {semgrep['finding_count']}, "
            f"blocking: {semgrep.get('blocking_finding_count', 0)}"
        )
    )
    osv_line = (
        f"`{osv['status']}`"
        if osv["status"] != "available"
        else (
            f"`available`, vulnerabilities: {osv['vulnerability_count']}, "
            f"blocking: {osv.get('blocking_vulnerability_count', 0)}"
        )
    )
    return "\n".join(
        [
            "## Change Consequence Certificate",
            "",
            f"- Certificate: `{certificate['content_address']}`",
            f"- Policy: `{policy['status']}`",
            f"- Changed files: {subject['changed_file_count']}",
            f"- Hosted trace speedup evidence: `{speedup}x`",
            f"- Hosted proof: {workflow_url}",
            f"- GitHub Action proof: {action_proof_url}",
            f"- Pull request proof: {pr_proof_url}",
            "",
            "### Tests To Run",
            *(f"- `{test}`" for test in affected_tests),
            "",
            "### Owners / Review Routing",
            *(owner_rows or ["- No owner evidence found."]),
            "",
            "### Required Review Surfaces",
            *(f"- {surface}" for surface in policy["required_review_surfaces"]),
            "",
            "### Scanner Evidence",
            f"- Semgrep: {semgrep_line}",
            f"- OSV: {osv_line}",
            "",
            "### Unknowns",
            *unknown_rows,
            "",
            "### Monetizable Product Thesis",
            "AI makes code cheap; this certificate makes AI changes reviewable, auditable, and policy-gated.",
            "",
        ]
    )


def build_report(
    *,
    repo_root: Path = ROOT,
    changed_files: tuple[str, ...] = (),
    base_ref: str | None = None,
    head_ref: str | None = None,
    hosted_trace_report_path: Path = DEFAULT_HOSTED_TRACE_REPORT_PATH,
    revolutionary_gate_path: Path = DEFAULT_REVOLUTIONARY_GATE_PATH,
    action_proof_path: Path = DEFAULT_ACTION_PROOF_PATH,
    pr_proof_path: Path = DEFAULT_PR_PROOF_PATH,
    semgrep_report_path: Path | None = None,
    osv_report_path: Path | None = None,
) -> dict[str, Any]:
    certificate = build_certificate(
        repo_root=repo_root,
        changed_files=changed_files,
        base_ref=base_ref,
        head_ref=head_ref,
        hosted_trace_report_path=hosted_trace_report_path,
        revolutionary_gate_path=revolutionary_gate_path,
        action_proof_path=action_proof_path,
        pr_proof_path=pr_proof_path,
        semgrep_report_path=semgrep_report_path,
        osv_report_path=osv_report_path,
    )
    comment = pr_comment(certificate)
    gate_checks = {
        "has_changed_files": certificate["subject"]["changed_file_count"] > 0,
        "digest_verified": bool(certificate["digest_verified"]),
        "has_policy_result": bool(certificate["policy_result"]["status"]),
        "has_explicit_unknowns": bool(certificate["unknowns"]),
        "has_monetizable_path": bool(certificate["monetizable_path"]["buyer"]),
        "integrates_hosted_trace_proof": certificate["evidence"]["hosted_runtime_trace"]["status"] == "available",
        "comment_has_tests": "### Tests To Run" in comment,
        "comment_has_unknowns": "### Unknowns" in comment,
    }
    report_body = {
        "kind": "change_consequence_certificate_report",
        "certificate": certificate,
        "pr_comment_markdown": comment,
        "gate_checks": gate_checks,
        "change_consequence_certificate_gate": all(gate_checks.values()),
    }
    report_id = stable_hash(report_body)
    return {
        **report_body,
        "report_id": report_id,
        "digest_verified": stable_hash(report_body) == report_id,
        "claim_boundary": "This proves a local product-shaped consequence certificate can be generated from repository evidence. It does not prove paid demand or production deployment.",
    }


def write_report(report: dict[str, Any], output_path: Path, comment_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    comment_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    comment_path.write_text(report["pr_comment_markdown"], encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--hosted-trace-report", type=Path, default=DEFAULT_HOSTED_TRACE_REPORT_PATH)
    parser.add_argument("--revolutionary-gate", type=Path, default=DEFAULT_REVOLUTIONARY_GATE_PATH)
    parser.add_argument("--action-proof", type=Path, default=DEFAULT_ACTION_PROOF_PATH)
    parser.add_argument("--pr-proof", type=Path, default=DEFAULT_PR_PROOF_PATH)
    parser.add_argument("--semgrep-report", type=Path)
    parser.add_argument("--osv-report", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--comment-output", type=Path, default=DEFAULT_COMMENT_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_report(
        repo_root=args.repo_root,
        changed_files=tuple(args.changed_file),
        base_ref=args.base,
        head_ref=args.head,
        hosted_trace_report_path=args.hosted_trace_report,
        revolutionary_gate_path=args.revolutionary_gate,
        action_proof_path=args.action_proof,
        pr_proof_path=args.pr_proof,
        semgrep_report_path=args.semgrep_report,
        osv_report_path=args.osv_report,
    )
    write_report(report, args.output, args.comment_output)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
