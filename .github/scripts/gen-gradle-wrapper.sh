#!/usr/bin/env bash
#
# Generate a Gradle wrapper for a project directory, pinned to a version.
#
# Why not just `cd <dir> && gradle wrapper --gradle-version X`?
#
# Because `gradle wrapper` configures the project first, which loads its
# plugins - and the whole reason we are pinning a version is that those
# plugins do not run on the Gradle that happens to be installed. GitHub's
# runners ship Gradle 9.x; AGP 8.7 still references
# org.gradle.util.VersionNumber, which Gradle 9 removed, so the command
# dies with "org/gradle/util/VersionNumber" before it can write anything.
# Chicken and egg.
#
# Generating the wrapper in an empty directory sidesteps it: no build
# script means no plugins, so any Gradle can emit the bootstrap files.
# They are version-agnostic - the wrapper's only job is to download the
# distribution named in gradle-wrapper.properties and hand off to it.
#
# Usage: gen-gradle-wrapper.sh <project-dir> <gradle-version>

set -euo pipefail

project_dir=${1:?usage: gen-gradle-wrapper.sh <project-dir> <gradle-version>}
gradle_version=${2:?usage: gen-gradle-wrapper.sh <project-dir> <gradle-version>}

[ -d "$project_dir" ] || { echo "no such directory: $project_dir" >&2; exit 1; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

# An empty settings file marks the temp dir as a Gradle project without
# pulling in a single plugin.
: > "$tmp/settings.gradle"
( cd "$tmp" && gradle wrapper --gradle-version "$gradle_version" --quiet )

mkdir -p "$project_dir/gradle/wrapper"
cp "$tmp/gradlew" "$tmp/gradlew.bat" "$project_dir/"
cp "$tmp/gradle/wrapper/gradle-wrapper.jar" \
   "$tmp/gradle/wrapper/gradle-wrapper.properties" \
   "$project_dir/gradle/wrapper/"
chmod +x "$project_dir/gradlew"

# Prove the pin took before anything downstream depends on it - a wrapper
# that silently resolved to the wrong version would fail much later, with
# a far less obvious message.
echo "--- $project_dir/gradlew --version ---"
( cd "$project_dir" && ./gradlew --version )
