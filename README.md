# Busleyden Guard live proof

Busleyden Guard gives a pull request one evidence-based answer: **merge after normal human review, or wait for an exact missing proof**.

This repository is the public, reproducible product fixture. It is not a mock dashboard.

## See the red-to-green result

In [PR #3](https://github.com/AlexanderLuzDH/busleyden-guard-live-proof/pull/3), a change to authentication session handling had:

- a verified Git diff;
- a matching CODEOWNER and owner approval;
- one mapped test;
- Semgrep results scoped to changed files; and
- OSV findings separated from an unrelated dependency history.

Guard blocked the change for exactly one reason:

> Prove that a replayed or reused token is rejected.

- [Open the blocking GitHub Check](https://github.com/AlexanderLuzDH/busleyden-guard-live-proof/runs/86260113501)
- [Inspect the one-blocker certificate](https://www.busleyden.com/live-auth-proof-required-certificate.json)

After the mapped replay test was added, the next App-triggered run had zero blockers:

- [Open the passing GitHub Check](https://github.com/AlexanderLuzDH/busleyden-guard-live-proof/runs/86260496674)
- [Inspect the zero-blocker certificate](https://www.busleyden.com/live-auth-evidence-satisfied-certificate.json)

Both decisions used engine SHA-256 `9fb8b150812efa7e25cc90e974b1596ab7b5c38b99143da7d88aa92eaba071cc`. Repository owners retained the final merge decision.

## What runs on every PR

1. The GitHub App receives the pull-request webhook.
2. It dispatches the repository-owned, pinned workflow.
3. The workflow verifies the exact base/head diff and engine hash.
4. Guard maps owners, affected tests, risk surfaces, and scanner evidence.
5. One final GitHub Check and content-addressed certificate record the decision.

The installed workflow is at [`.github/workflows/change-consequence-certificate.yml`](.github/workflows/change-consequence-certificate.yml).

## Try it on one repository

- [Start the $99 self-service pilot](https://www.busleyden.com/#pricing)
- [Install the GitHub App](https://github.com/apps/busleyden-guard/installations/new)
- [Read the security boundary](https://www.busleyden.com/security-review.json)

The founding pilot covers one repository, up to ten real pull requests, and 30 days. No sales call is required.

## What Guard does not claim

Guard verifies available evidence and policy conditions. It does not prove code is bug-free, replace human review, or establish that every repository uses the same test and ownership conventions.

## Fixture provenance

This repository uses source from the [Pallets Click project](https://github.com/pallets/click) as a realistic Python fixture. Click remains under its original BSD license. The Busleyden-specific workflow, authentication fixture, certificates, and proof PRs exist to demonstrate Guard behavior; this repository is not an alternative distribution of Click.
