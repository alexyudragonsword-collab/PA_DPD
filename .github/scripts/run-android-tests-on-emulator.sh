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
# Usage: run-android-tests-on-emulator.sh <buildPython> [navShell] [compiled]
#
# navShell picks which navigation shell the app under test wears
# (classic|drawer, default classic). The shell is a build-time choice, so
# testing both means building both - see android/README.md.
#
# Pass the literal word `compiled` as the third argument to test the
# build whose padpd ships as Cython .so instead of .py. That build needs
# an x86_64 padpd wheel already sitting in android/app/pysrc; Gradle
# fails at configuration time, naming the command, if it is not there.

set -uo pipefail   # deliberately NOT -e: collection must run after a
                   # failing test, which is exactly when it is worth most

build_python=${1:?usage: run-android-tests-on-emulator.sh <buildPython> [navShell] [compiled]}
nav_shell=${2:-classic}
compiled=false
case "${3:-}" in
    ""|interpreted) ;;
    compiled) compiled=true ;;
    *) echo "third argument must be 'compiled' or empty, got '${3}'"; exit 2 ;;
esac

root=${GITHUB_WORKSPACE:-$(cd "$(dirname "$0")/../.." && pwd)}
out="$root/android-test-artifacts"
mkdir -p "$out"

echo "=== instrumented test run starting ==="
echo "root=$root  nav=$nav_shell  compiled=$compiled"
adb devices

cd "$root/android" || { echo "cannot cd to $root/android"; exit 1; }

./gradlew :app:connectedDebugAndroidTest \
    -PpadpdAbis=x86_64 \
    -PpadpdNav="$nav_shell" \
    -PpadpdCompiled="$compiled" \
    -PpadpdBuildPython="$build_python" \
    2>&1 | tee "$out/gradle-test.log"
status=${PIPESTATUS[0]}

# What actually got installed, on the device. The tests exercise the
# app through its UI and would pass just as well against an interpreted
# build that quietly ignored -PpadpdCompiled, so ask the APK rather than
# the flag. Cheap, and it is the assertion the whole variant rests on.
apk=$(find app/build/outputs/apk/debug -name '*.apk' 2>/dev/null | head -1)
if [ -n "$apk" ]; then
    echo "=== what this APK ships ==="
    # The shell first. A matrix leg named "drawer" that built the classic
    # shell would run all 41 tests, pass every one of them, and report
    # nothing wrong - the tests are written to work on both.
    python3 "$root/scripts/android/apk_build_stamp.py" "$apk" \
        --nav "$nav_shell" --compiled "$compiled" || status=1
    if [ "$compiled" = true ]; then
        # An assertion, because this is the one claim the compiled
        # variant makes and the UI tests cannot see it: they would pass
        # just as happily against a build that ignored the flag.
        python3 "$root/scripts/android/inspect_apk.py" "$apk" --native padpd \
            || status=1
    else
        # Reported, not asserted. The interpreted/compiled distinction is
        # asserted in android-compiled.yml's build job, where both APKs
        # exist side by side; making it a gate here too would put a new
        # way for the ordinary Android workflow to redden in the path of
        # a change that has nothing to do with it.
        python3 "$root/scripts/android/inspect_apk.py" "$apk" || true
    fi
fi

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
# attempted even when nothing arrives here. The measured metric-card
# bounds go the same way: they are evidence about the layout, and
# evidence that only exists inside a downloadable artifact is invisible
# to anyone reading the run.
grep -a "padpd-screenshot:" "$out/logcat.txt" | tail -n 40 || true
echo "=== measured metric card bounds (LayoutBoundsTest) ==="
grep -a "padpd-metric-card:" "$out/logcat.txt" | tail -n 20 || true
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
