# HTTPie autonomous transfer case — preregistration

Date: 2026-07-17

## Purpose

Test whether the fixed-versus-mutant causal gate and dynamic call-mapping method transfer from PySnooper to an independently maintained project family.

## Frozen historical case

BugsInPy HTTPie bug 1:

- historical buggy commit: `001bda19450ad85c91345eea3cfa3991e1d492ba`
- human-fixed commit: `5300b0b490b8db48fac30b5e32164be93dc574b7`
- changed source: `httpie/downloads.py`
- benchmark-selected test: `tests/test_downloads.py`
- property: a filename longer than the filesystem name limit is trimmed before uniqueness suffixes are tested.

## Compact behavioral oracle

Patch `get_filename_max_length` to return 10, call `get_unique_filename` with a 20-character filename and an `exists` function that always returns false, and require the returned filename to contain exactly 10 characters.

## Target mutant

Restore the historical untrimmed uniqueness loop inside `get_unique_filename`:

```python
if not exists(filename + suffix):
    return filename + suffix
```

The mutant changes only the code path named by the historical fix.

## Dynamic mapping

Run the compact test from a real source file under the same `sys.setprofile` call profiler used by the corrected PySnooper mapping pilot. A mapping hit requires:

- the behavioral test passes; and
- `httpie/downloads.py` appears in the recorded repository-local call set.

## Preregistered hypotheses

### H7 — Cross-project causal transfer

The human-fixed HTTPie commit passes and the targeted mutant fails.

### H8 — Cross-project dynamic mapping transfer

The passing behavioral test maps to `httpie/downloads.py`.

The historical buggy result is secondary because old dependencies or runtime behavior may prevent exact reproduction.

## Decision rule

- If H7 and H8 pass, causal executable evidence and call-profile mapping have transferred to a second project family. The next experiment may scale dynamic mapping to a larger, automatically selected set.
- If either fails, repair the harness or narrow the claim before expanding.

## Claim boundary

One HTTPie case cannot establish corpus-wide mapping recall, defect-family breadth, production overhead, or human usefulness.