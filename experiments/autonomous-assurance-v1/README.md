# Autonomous Assurance Laboratory v1

A history-grounded experiment that does not require maintainer enrollment or feedback.

## Components

- `analyze_bugsinpy.py` parses the complete BugsInPy metadata and patch corpus, classifies test-evidence states, and runs simple policy and mapping baselines.
- `run_pysnooper_cases.py` executes three compact PySnooper fixed-versus-mutant counterfactual cases.
- `tests/test_lab.py` validates parsers, path classification, and mutation application.
- `PREREGISTRATION.md` freezes hypotheses, denominators, and course-change rules before the full corpus is inspected.

## Local static run

```bash
git clone --depth 1 https://github.com/soarsmu/BugsInPy.git /tmp/BugsInPy
python analyze_bugsinpy.py /tmp/BugsInPy \
  --json-output results/bugsinpy-static.json \
  --markdown-output results/bugsinpy-static.md \
  --csv-output results/bugsinpy-cases.csv
```

## Local executable run

```bash
python run_pysnooper_cases.py \
  --json-output results/pysnooper-executable.json \
  --markdown-output results/pysnooper-executable.md
```

The GitHub Actions workflow runs the complete static corpus, a Python 3.8 primary executable environment, and a Python 3.11 transfer environment. Artifacts preserve raw case records, summaries, and logs.
