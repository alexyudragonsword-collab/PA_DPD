#!/usr/bin/env python3
"""Fail when a Compose preview rendered an error instead of a chart.

The screenshot plugin reports a preview that threw as one line -
"There were some issues with rendering one or more previews" - and then
exits zero. That is how a green step produced twenty-eight blank images
of about 800 bytes each: every preview raised while loading its fixture,
every image was written, and nothing failed.

The per-preview result file is the only place that outcome is a fact
rather than a hint, so it is read here.

Named to match the workflow's ``paths:`` filter (it globs
``.github/scripts/*android*``). A fix to a script the workflow shells
out to that cannot itself trigger the workflow is the worst shape for
this kind of file - the repository has been bitten by exactly that.

Usage: check-android-preview-renders.py <results.json>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def errors(node, path="$"):
    """Every truthy value under a key that mentions an error.

    Walked generically rather than against a fixed schema: this file is
    written by an alpha plugin, and a schema change should show up as a
    missed error rather than as a crash here.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if "error" in key.lower() and value:
                yield f"{path}.{key} = {value!r}"[:400]
            yield from errors(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, item in enumerate(node):
            yield from errors(item, f"{path}[{i}]")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    results = Path(argv[1])
    if not results.is_file():
        print(f"no {results}: the render task produced no results",
              file=sys.stderr)
        return 1

    data = json.loads(results.read_text(encoding="utf-8"))
    found = list(errors(data))
    rendered = len(data.get("screenshotResults", []))
    print(f"{rendered} previews rendered, {len(found)} carrying an error")
    for line in found[:20]:
        print("  " + line)
    if found:
        print("previews failed to render; the images they wrote are not "
              "charts", file=sys.stderr)
        return 1
    if rendered == 0:
        print("no previews were rendered at all", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
