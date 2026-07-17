#!/usr/bin/env python3
"""Run the dynamic mapping pilot with a real behavioral source file."""
from __future__ import annotations

import run_dynamic_mapping_pilot as pilot


def corrected_profile_script(test_code: str) -> str:
    """Create the behavior file, profile calls, and execute it through runpy."""
    return f'''from __future__ import annotations
import json
import runpy
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BEHAVIOR = ROOT / "autonomous_assurance_behavior.py"
BEHAVIOR.write_text({test_code!r}, encoding="utf-8")
SEEN = set()
ERROR = None


def profiler(frame, event, arg):
    if event != "call":
        return
    filename = frame.f_code.co_filename
    if not filename or filename.startswith("<"):
        return
    try:
        relative = Path(filename).resolve().relative_to(ROOT).as_posix()
    except (OSError, ValueError):
        return
    if relative.endswith(".py") and not relative.startswith("autonomous_assurance_"):
        SEEN.add(relative)


sys.setprofile(profiler)
try:
    runpy.run_path(str(BEHAVIOR), run_name="__main__")
except BaseException:
    ERROR = traceback.format_exc()
finally:
    sys.setprofile(None)
    Path("executed-files.json").write_text(
        json.dumps({{"executed_files": sorted(SEEN), "error": ERROR}}, indent=2, sort_keys=True) + "\\n",
        encoding="utf-8",
    )

if ERROR:
    raise SystemExit(ERROR)
'''


pilot.profile_script = corrected_profile_script


if __name__ == "__main__":
    raise SystemExit(pilot.main())
