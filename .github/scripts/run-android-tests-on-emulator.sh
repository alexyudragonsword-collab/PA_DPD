#!/usr/bin/env bash
#
# Run the instrumented tests against a booted emulator, then collect the
# reports. Invoked as the single line of android-emulator-runner's
# `script:`.
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
# Usage: run-android-tests-on-emulator.sh <buildPython>

set -uo pipefail   # deliberately NOT -e: collection must run after a
                   # failing test, which is exactly when it is worth most

build_python=${1:?usage: run-android-tests-on-emulator.sh <buildPython>}

root=${GITHUB_WORKSPACE:-$(cd "$(dirname "$0")/../.." && pwd)}
out="$root/android-test-artifacts"
mkdir -p "$out"

echo "=== instrumented test run starting ==="
echo "root=$root"
adb devices

cd "$root/android" || { echo "cannot cd to $root/android"; exit 1; }

./gradlew :app:connectedDebugAndroidTest \
    -PpadpdAbis=x86_64 \
    -PpadpdBuildPython="$build_python" \
    2>&1 | tee "$out/gradle-test.log"
status=${PIPESTATUS[0]}

# Dumped before the screenshot collection below, which greps it: an
# earlier version of this file read logcat.txt several lines before it
# was written, so the grep silently matched nothing.
#
# Collect whether or not the assertions passed - a failing run is exactly
# when its output is worth reading. The app tags its Python-side messages
# so they can be separated from the framework's noise.
adb logcat -d > "$out/logcat.txt"

# Screenshots. The tests write them to the directory AGP names in the
# `additionalTestOutputDir` instrumentation argument, and AGP pulls that
# off the device into connected_android_test_additional_output. Where
# that argument is absent the helper falls back to the app's own external
# files directory, which is why the adb pull below runs too - it is a
# second chance, not a duplicate. Both are best effort: a run with no
# screenshots is a run whose assertions still mean what they say.
shots="$out/screenshots"
mkdir -p "$shots"
find app/build/outputs/connected_android_test_additional_output \
    -name '*.png' -exec cp {} "$shots/" \; 2>/dev/null || true
adb pull /sdcard/Android/data/com.padpd/files/screenshots "$shots" \
    >/dev/null 2>&1 || true
# The tests print every path they write, so the log says what was
# attempted even when nothing arrives here.
grep -a "padpd-screenshot:" "$out/logcat.txt" | tail -n 40 || true
echo "=== screenshots collected: $(find "$shots" -name '*.png' | wc -l) ==="

cp -r app/build/reports/androidTests "$out/reports" 2>/dev/null || true

# Gradle's console does print the assertion message for a failing
# instrumented test - an earlier note here claimed it printed only the
# exception class, which was wrong and cost a round of blind fixing.
# What it does not print is anything the app wrote to logcat, so a Python
# traceback raised inside a coroutine is invisible unless it happens to
# reach an assertion. Both are extracted below; the XML pass stays
# because it also catches failures Gradle truncates.
if [ "$status" -ne 0 ]; then
    echo "=== instrumented test failure messages ==="
    for xml in app/build/outputs/androidTest-results/connected/*.xml \
               app/build/outputs/androidTest-results/connected/*/*.xml; do
        [ -f "$xml" ] || continue
        python3 - "$xml" <<'PY'
import sys, xml.etree.ElementTree as ET
for case in ET.parse(sys.argv[1]).iter("testcase"):
    for bad in list(case.iter("failure")) + list(case.iter("error")):
        print(f"--- {case.get('classname')}.{case.get('name')} ---")
        text = (bad.get("message") or "") + "\n" + (bad.text or "")
        print(text.strip()[:4000])
PY
    done

    # Chaquopy routes Python stdout/stderr to logcat, so an exception in
    # a background chart build shows up here and nowhere else.
    echo "=== app-side logcat (python + crashes) ==="
    grep -aE "python\.(stdout|stderr)|AndroidRuntime|com\.padpd" \
        "$out/logcat.txt" | tail -n 200 || echo "(no matching lines)"
fi

echo "--- collected ---"
ls -l "$out"
exit "$status"
