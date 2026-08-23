#!/usr/bin/env bash
#
# Re-print the interesting part of a captured Gradle build log.
#
# Gradle emits "FAILURE: ... * What went wrong: <the one useful line>"
# and only then the stack trace, so on a long build the message ends up
# hundreds of lines above the end of the job log - exactly where a reader
# skimming the tail will not look. Running this from a later `if: failure()`
# step puts the message at the bottom of the job log and in the run summary.
#
# Usage: surface-gradle-failure.sh <gradle-log-file>

set -uo pipefail

log=${1:?usage: surface-gradle-failure.sh <gradle-log-file>}

if [ ! -s "$log" ]; then
    echo "No Gradle log captured at $log - the build likely died before it started."
    exit 0
fi

emit() {
    # Both to stdout (lands at the end of the job log) and to the run
    # summary (readable without opening the log at all).
    if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
        tee -a "$GITHUB_STEP_SUMMARY"
    else
        cat
    fi
}

{
    echo "## Gradle failure"
    echo

    # The "What went wrong" block, when Gradle produced one.
    if grep -q '^FAILURE: Build failed' "$log"; then
        echo '### What went wrong'
        echo '```'
        sed -n '/^FAILURE: Build failed/,$p' "$log" \
            | grep -v $'^\tat ' \
            | head -40
        echo '```'
        echo
    fi

    # Which task died, plus the output just before it - for Chaquopy that
    # is where pip's own error text appears, and pip's message is usually
    # the real answer.
    if grep -q '^> Task .* FAILED' "$log"; then
        echo '### Failing task, in context'
        echo '```'
        grep -n '^> Task .* FAILED' "$log" | tail -3
        echo '...'
        line=$(grep -n '^> Task .* FAILED' "$log" | tail -1 | cut -d: -f1)
        start=$(( line > 60 ? line - 60 : 1 ))
        sed -n "${start},$(( line + 30 ))p" "$log"
        echo '```'
        echo
    fi

    echo '### Last 80 lines'
    echo '```'
    grep -v $'^\tat ' "$log" | tail -80
    echo '```'
} | emit
