"""Guards on android/app/build.gradle's compiled-variant wiring.

The Android build is only compiled in CI, so nothing else in this suite
sees these lines. They are guarded here because the way they break is
silent: a compiled build that also stages ``src/padpd`` ships the .py
in the app payload, which precedes the requirements on sys.path, so
Python imports the source and ignores the .so. The APK is bigger, the
build log is identical, and the app behaves correctly - it is just not
compiled. ``inspect_apk.py --native`` catches that in CI; these catch it
before a 40-minute run does.

Text checks on Gradle source, deliberately. Evaluating the build file
would need Gradle; the failure mode being guarded is a structural one
(which branch a statement sits in), and brace matching answers that
exactly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GRADLE = ROOT / "android" / "app" / "build.gradle"


@pytest.fixture(scope="module")
def gradle() -> str:
    return GRADLE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def gradle_code(gradle: str) -> str:
    """The same file with whole-line ``//`` comments dropped.

    A substring check cannot tell code from a comment, and the first
    version of the dependsOn guard below could not: commenting the line
    out left the string in the file and the test stayed green. Only
    whole-line comments go - a trailing one after real code is rare here
    and removing it would mean parsing quotes, which `https://` breaks.
    """
    return "\n".join(line for line in gradle.splitlines()
                     if not line.lstrip().startswith("//"))


def _block_after(text: str, opener: str) -> str:
    """The braced block introduced by `opener`, by brace matching.

    Returns the text between the opener's `{` and its matching `}`.
    Naive about braces inside strings and comments, which is fine for
    the blocks this file looks at and would be a lie to claim otherwise.
    """
    start = text.index(opener) + len(opener)
    depth = 1
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i]
    raise AssertionError(f"unbalanced braces after {opener!r}")


def test_padpd_is_staged_only_when_it_is_not_compiled(gradle: str) -> None:
    """The whole variant rests on these two being mutually exclusive."""
    guarded = _block_after(gradle, "if (!compiled) {")
    assert "include 'padpd/**'" in guarded, (
        "staging src/padpd must sit inside `if (!compiled)`; outside it, "
        "the compiled build ships .py that shadows its own .so")
    # ...and nowhere else. One occurrence in the file, and it is that one.
    assert gradle.count("include 'padpd/**'") == 1


def test_the_wheel_is_installed_by_find_links_not_by_path(gradle: str) -> None:
    """pip does ABI tag matching only when choosing from a link set.

    Handed a path it installs what it was given, so the arm64 wheel goes
    into the x86_64 build too - installing cleanly and dying at import.
    """
    assert 'options "--find-links", pysrc.absolutePath' in gradle
    assert 'install "padpd"' in gradle
    for bad in ("install file(", 'install "pysrc', "install pysrc"):
        assert bad not in gradle, f"{bad!r} installs a wheel by path"


def test_installing_padpd_is_conditional(gradle: str) -> None:
    compiled_only = _block_after(gradle, "                if (compiled) {")
    assert 'install "padpd"' in compiled_only
    assert gradle.count('install "padpd"') == 1


def test_the_wheel_check_names_the_command_that_produces_one(
        gradle: str) -> None:
    """pip's own error here names neither the ABI nor the fix.

    "No matching distribution found for padpd" after a 20-minute
    configure is not a message anyone can act on, so the build fails
    earlier with the command in it.
    """
    assert "android_wheel.py" in gradle
    assert "--strip-requires" in gradle
    assert "-PpadpdCompiled=true, but" in gradle


def test_the_vendored_scripts_are_present() -> None:
    """CI runs these; the skill they came from is not in the repo."""
    for name in ("android_wheel.py", "inspect_apk.py", "apk_build_stamp.py",
                 "README.md"):
        assert (ROOT / "scripts" / "android" / name).is_file(), name


def test_the_build_stamp_is_written_and_reaches_the_assets(
        gradle_code: str) -> None:
    """Four release APKs, all named app-release.apk until renamed.

    The stamp is the only thing in the APK that says which of them it
    is: both shells compile into both builds, so grepping the DEX for
    "drawer" matches a classic build too.
    """
    assert "writePadpdBuildStamp" in gradle_code
    assert 'padpd-assets/padpd-build.json' in gradle_code
    # The generated directory has to be an assets source dir, or the file
    # is written and packaged by nothing.
    assert 'assets.srcDirs += layout.buildDirectory.dir("padpd-assets")' \
        in gradle_code
    # ...and some assets task has to depend on it, or it is written after
    # the merge that would have picked it up.
    hook = _block_after(gradle_code, "tasks.configureEach { t ->")
    assert "dependsOn buildStamp" in hook and "assets" in hook


def test_the_stamp_records_both_build_time_choices(
        gradle_code: str) -> None:
    """navShell alone would leave the compiled/interpreted pair
    indistinguishable, which is the pair CI builds back to back in one
    workspace."""
    stamp = _block_after(gradle_code, "doLast {")
    assert "navShell" in stamp and "compiled" in stamp
