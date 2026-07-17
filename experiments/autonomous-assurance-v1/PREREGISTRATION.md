# Autonomous Assurance Laboratory v1 — preregistration

## Objective

Test whether an evidence-first assurance workflow can make objective progress without waiting for maintainer feedback. The experiment uses real Python bug histories from BugsInPy and three executable PySnooper counterfactual cases.

The static phase uses benchmark metadata and human patches as historical outcomes. The executable phase uses compact behavioral tests derived from the human regression tests and compares the human-fixed commit with a single targeted mutant and the recorded historical buggy commit.

## Frozen primary questions

1. How often is the benchmark-selected test file changed by the human fix, versus already present and unchanged?
2. How often does a generic `source changed -> add a regression test` rule overstate the evidence gap?
3. Can filename-only source-to-test mapping recover the benchmark-selected test path?
4. Do compact behavioral tests distinguish human-fixed code from a single targeted counterfactual mutant?

## Preregistered hypotheses

### H1 — Existing evidence is common

At least 25% of eligible BugsInPy cases will have a benchmark-selected test file that is not changed by the human patch. This is treated as a proxy for relevant test evidence that already existed in the buggy checkout.

### H2 — `any test changed` is an inadequate evidence state

At least 10% of eligible cases will be misrepresented by a binary `any test file changed` signal because the benchmark-selected test is pre-existing or only unrelated test files changed.

### H3 — Filename mapping is insufficient

A generated exact test-path candidate based only on changed source filenames will recover fewer than 70% of benchmark-selected test files.

### H4 — Executable counterfactual gate

At least two of the three PySnooper cases will satisfy:

- human-fixed commit passes the compact behavioral test; and
- a single targeted mutant of the fixed commit fails the same test.

Historical buggy commits are reported separately because old environments and dependencies can rot.

## Population and exclusions

The static population is every BugsInPy directory containing both `bug.info` and `bug_patch.txt`. Primary proportion denominators require:

- at least one benchmark test path from `bug.info` or `run_test.sh`; and
- at least one changed source file in the patch.

No project or bug is excluded based on the observed result.

## Evidence-state proxies

- `present_changed`: the benchmark-selected test file appears in the human patch.
- `present_existing_proxy`: the benchmark-selected test file is selected by the benchmark but absent from the human patch.
- `unrelated_test_change_only`: some test file changed, but no benchmark-selected test file changed.

These are historical proxies. They do not establish causal sufficiency or reviewer visibility.

## Compared policies

1. **Obligation-first:** emit `add a regression test` for every source-changing bug.
2. **Suppress on any test:** emit only when the patch changes no test file.
3. **Evidence-state oracle upper bound:** use benchmark-selected test paths to distinguish changed from existing evidence. This is not deployable; it quantifies the value of correct evidence discovery.

## Mapping baselines

- Same source/test stem.
- Exact generated paths such as `tests/test_<source-stem>.py`.
- Lexical overlap between source-diff identifiers and newly added test names.

## Intervals

Key proportions receive 90% Wilson intervals and deterministic 90% project-cluster bootstrap intervals with seed `61065` and 5,000 resamples.

## Decision rules

- If H1 passes, Guard should not describe an unlocated test as missing. Repository test discovery and `present_unverified` become higher priority than new-test obligations.
- If H2 passes, a binary changed-test flag is rejected as the evidence model.
- If H3 passes, pure filename mapping is rejected as the primary test selector; dynamic coverage, history, or execution traces become the next path.
- If H4 fails, executable-harness reliability is repaired before expanding the corpus.
- No new constitutional layer is admitted from these results. The next expansion must be an executable failure, a cross-system disagreement, or a transfer result on a new project family.

## Claim boundary

The experiment can establish static corpus frequencies and bounded executable counterfactual behavior. It cannot establish human usefulness, commercial value, or complete defect-family recall.
