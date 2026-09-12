#!/usr/bin/env python3
"""Read (and optionally assert) what an APK was built from.

Four release APKs come out of this repo - the classic and drawer shells
crossed with interpreted and compiled padpd - and Gradle calls every one
of them ``app-release.apk``. A filename is therefore a claim, not
evidence, and this repo has already shipped one wrong: the drawer build
was uploaded as ``padpd-arm64-release`` with its size reported as the
classic build's, and CI stayed green the whole way, because nothing
looked inside.

``android/app/build.gradle`` writes ``assets/padpd-build.json`` from the
Gradle properties the build was invoked with. This reads it back::

    python apk_build_stamp.py app.apk                      # report
    python apk_build_stamp.py app.apk --nav drawer         # assert
    python apk_build_stamp.py app.apk --compiled true

The stamp says what the build was ASKED for. Whether padpd really
shipped as ``.so`` is a separate question that ``inspect_apk.py``
answers from the payload; a workflow that checks both is checking that
the request and the result agree, which is the failure this whole family
of bugs is made of.

Exit status is 0 when every requested assertion holds.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

STAMP = "assets/padpd-build.json"


def read_stamp(apk: Path) -> dict:
    with zipfile.ZipFile(apk) as z:
        try:
            raw = z.read(STAMP)
        except KeyError:
            raise SystemExit(
                f"{apk.name}: no {STAMP}. Either this APK predates the "
                f"build stamp, or writePadpdBuildStamp did not run - check "
                f"that an assets task depends on it.") from None
    return json.loads(raw)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("apk", type=Path)
    ap.add_argument("--nav", choices=["classic", "drawer"],
                    help="the navigation shell this APK must declare")
    ap.add_argument("--compiled", choices=["true", "false"],
                    help="whether this APK must declare a compiled padpd")
    args = ap.parse_args(argv)

    stamp = read_stamp(args.apk)
    print(f"{args.apk.name}: navShell={stamp.get('navShell')!r} "
          f"compiled={stamp.get('compiled')!r}")

    ok = True
    if args.nav is not None and stamp.get("navShell") != args.nav:
        print(f"  FAIL expected navShell={args.nav!r}, "
              f"got {stamp.get('navShell')!r} -- this is not the APK its "
              f"name says it is")
        ok = False
    if args.compiled is not None:
        want = args.compiled == "true"
        if stamp.get("compiled") is not want:
            print(f"  FAIL expected compiled={want}, "
                  f"got {stamp.get('compiled')!r}")
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
