#!/usr/bin/env bash
#
# Run the Phase 0 probe as an instrumented test against a booted emulator,
# then collect its output. Invoked as the single line of
# android-emulator-runner's `script:`.
#
# Why a file rather than an inline script: the action executes the
# `script:` input ONE LINE AT A TIME, each in its own `/usr/bin/sh -c`.
# Nothing carries between lines - not variables, not `cd`, not `set +e`.
# That is not obvious from the action's docs and it silently broke four
# consecutive runs here:
#
#     [command]/usr/bin/sh -c out="${GITHUB_WORKSPACE:-$(pwd)}/probe-artifacts"
#     [command]/usr/bin/sh -c mkdir -p "$out" && echo "collecting into $out"
#     mkdir: cannot create directory ''
#
# and, earlier and more damagingly, a bare `cd android` line that did
# nothing, so `./gradlew` ran from the repo root where no wrapper exists.
# One line calling one file has none of these problems.
#
# Usage: run-probe-on-emulator.sh <buildPython>

set -uo pipefail   # deliberately NOT -e: collection must run after a
                   # failing test, which is exactly when it is worth most

build_python=${1:?usage: run-probe-on-emulator.sh <buildPython>}

root=${GITHUB_WORKSPACE:-$(cd "$(dirname "$0")/../.." && pwd)}
out="$root/probe-artifacts"
mkdir -p "$out"

echo "=== probe script started ==="
echo "root=$root"
adb devices

cd "$root/android" || { echo "cannot cd to $root/android"; exit 1; }

./gradlew :app:connectedDebugAndroidTest \
    -PpadpdAbis=x86_64 \
    -PpadpdBuildPython="$build_python" \
    2>&1 | tee "$out/gradle-test.log"
status=${PIPESTATUS[0]}

# Collect whether or not the assertions passed - a failing probe is
# exactly when its output is worth reading.
adb logcat -d -s padpd-probe:I > "$out/probe-logcat.txt"
adb pull /sdcard/Android/data/com.padpd.spike/files/probe-report.txt \
    "$out/probe-report.txt"

echo "--- collected ---"
ls -l "$out"
exit "$status"
