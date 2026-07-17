# Amendment 002 — complete population and property-aligned oracle

Date: 2026-07-17

This amendment is recorded after corrected run `29553292522` and before any rerun using the corrections below.

## Five omitted HTTPie cases

The corrected upstream-commit audit resolved 495 cases across 16 projects rather than the 500 metadata cases and 17 projects seen by the pilot parser. The cause was not an API failure. `projects/httpie/project.info` records a GitHub URL with a trailing slash:

```text
https://github.com/jakubroztocil/httpie/
```

The repository parser required the repository name at end-of-string and therefore silently excluded all five HTTPie cases before the API-resolution denominator was formed.

Correction:

- strip trailing slashes before parsing GitHub repository identity;
- add a regression test covering `.git`, no-suffix, and trailing-slash forms;
- require the final metadata population to include all 500 eligible records and all 17 projects before interpreting H1–H3.

The preregistered thresholds remain unchanged.

## PySnooper string-path oracle

The third executable case tests whether a caller-supplied string path is used for trace output. The initial compact oracle additionally required the literal return value `15` to appear in the trace file. The upstream regression test does not make that requirement; it checks that tracing to the supplied path works and that expected trace entries are written.

The human-fixed commit created and populated the correct file, but the extra `15` assertion failed. The historical bug and exact mutant both raised `NameError: output_path` before writing the intended trace.

Correction:

- require the supplied path to exist;
- require the trace file to be non-empty; and
- require a stable executed-source fragment (`x = 7`) in the trace.

This aligns the executable oracle with the declared property. The H4 threshold remains two of three causal gates.

## Preservation

The 495-case result and the overconstrained executable result remain preserved as failed measurement states. They are not replaced or counted as evidence for the final hypotheses.