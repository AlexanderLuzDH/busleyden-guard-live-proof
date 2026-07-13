# Busleyden Guard public beta

The paid launch is closed. This beta exists to determine whether Guard is genuinely useful on real pull requests before anyone is asked to pay.

## Who can participate

Maintainers of public Python repositories can participate without a card, contract, call, or meeting. Install Guard on one selected repository, review and merge its setup pull request, then leave it running for up to two weeks.

[Enroll a public repository](https://github.com/AlexanderLuzDH/busleyden-guard-live-proof/issues/new?template=beta.yml)

## What to report

For each evaluated pull request, add one row to the enrollment issue:

| Pull request | Useful, noisy, or missed something | Changed the review decision? | What should improve? |
|---|---|---|---|
| `owner/repo#123` | Useful | Yes | The missing replay test was actionable. |

Do not paste private code, secrets, vulnerability details, or personal information. Public pull-request URLs and maintainer-authored summaries are enough.

## Release gate

Paid checkout stays closed until all of these conditions are met:

- 5 independently maintained public Python repositories complete an installation;
- at least 50 real pull-request results receive a maintainer label;
- useful-result precision and missed-risk recall are reported separately, with the sampling method published;
- nuisance blockers are measured and the remaining failure modes are disclosed;
- at least 3 maintainers independently confirm that Guard improved a real review decision;
- the checkout, cancellation, entitlement, and private-repository paths pass an end-to-end payment test; and
- the website, App permissions, security boundary, and install documentation agree.

Meeting the gate permits a paid launch; it does not prove that Guard is bug-free or universally useful.

## Current evidence

The repository's red-to-green fixture proves that the product can produce and clear one targeted blocker. It is controlled product evidence, not independent customer validation. Independent beta progress will be linked from enrollment issues so the evidence remains attributable and auditable.

## Removal

Participants can uninstall the GitHub App and remove `.github/workflows/change-consequence-certificate.yml` at any time. There is no automatic conversion to a paid plan.
