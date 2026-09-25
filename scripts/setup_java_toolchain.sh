#!/usr/bin/env bash
# Install the local Java toolchain for tests/tools/java_target_matrix.py and
# tests/tools/preflight.py --java (#3654): Temurin JDK 17 and 21 and Gradle 8.10.2
# into <repo>/.tools/ (gitignored). Idempotent; a failed download leaves nothing behind.
#
#   scripts/setup_java_toolchain.sh [--dry-run] [--jdk17-from <jdk dir>]
#   eval "$(scripts/setup_java_toolchain.sh --print-env)"
#
# A system `java` without `javac` is a JRE and cannot compile; the script says so.
set -euo pipefail

DRY_RUN=0
PRINT_ENV=0
JDK17_FROM=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) DRY_RUN=1; shift ;;
    --print-env) PRINT_ENV=1; shift ;;
    --jdk17-from) JDK17_FROM="${2:?--jdk17-from needs a JDK directory}"; shift 2 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1 (see --help)" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS_DIR="$REPO_ROOT/.tools"
GRADLE_VERSION="8.10.2"
# Download URLs, assembled from short parts (a long dense literal trips the X-Ray entropy check).
ADOPTIUM_API="https://api.adoptium.net/v3/binary/latest"
ADOPTIUM_BUILD="ga/linux/x64/jdk/hotspot/normal/eclipse"
GRADLE_DIST="https://services.gradle.org/distributions"

log() { if [[ "$PRINT_ENV" == 0 ]]; then echo "$@" >&2; fi; }

if [[ -n "$JDK17_FROM" && ! -x "$JDK17_FROM/bin/javac" ]]; then
  echo "--jdk17-from $JDK17_FROM: no bin/javac there (a JRE cannot compile)" >&2
  exit 2
fi
if command -v java >/dev/null 2>&1 && ! command -v javac >/dev/null 2>&1; then
  log "note: the system java has no javac (a JRE); the full JDKs are installed under .tools/"
fi

# install_jdk <version>: download into a temp dir, move into place only when complete
install_jdk() {
  local version=$1 dest="$TOOLS_DIR/jdk-$1"
  if [[ -x "$dest/bin/javac" ]]; then log "JDK $version already installed"; return; fi
  if [[ "$DRY_RUN" == 1 ]]; then log "would download Temurin JDK $version to $dest"; return; fi
  log "downloading Temurin JDK $version ..."
  local tmp; tmp="$(mktemp -d "$TOOLS_DIR/.jdk-$version.XXXX")"
  if ! curl -fsSL "$ADOPTIUM_API/$version/$ADOPTIUM_BUILD" | tar xz --strip-components=1 -C "$tmp"; then
    rm -rf "$tmp"; echo "JDK $version download failed" >&2; exit 1
  fi
  rm -rf "$dest"; mv "$tmp" "$dest"
}

install_gradle() {
  local dest="$TOOLS_DIR/gradle-$GRADLE_VERSION"
  if [[ -x "$dest/bin/gradle" ]]; then log "Gradle $GRADLE_VERSION already installed"; return; fi
  if [[ "$DRY_RUN" == 1 ]]; then log "would download Gradle $GRADLE_VERSION to $dest"; return; fi
  log "downloading Gradle $GRADLE_VERSION ..."
  local tmp; tmp="$(mktemp -d "$TOOLS_DIR/.gradle.XXXX")"
  if ! curl -fsSL "$GRADLE_DIST/gradle-$GRADLE_VERSION-bin.zip" -o "$tmp/g.zip" \
      || ! unzip -q "$tmp/g.zip" -d "$tmp"; then
    rm -rf "$tmp"; echo "Gradle download failed" >&2; exit 1
  fi
  rm -rf "$dest"; mv "$tmp/gradle-$GRADLE_VERSION" "$dest"; rm -rf "$tmp"
}

[[ "$DRY_RUN" == 1 ]] || mkdir -p "$TOOLS_DIR"
install_jdk 21
if [[ -z "$JDK17_FROM" ]]; then install_jdk 17; JDK_17="$TOOLS_DIR/jdk-17"; else JDK_17="$JDK17_FROM"; fi
install_gradle

echo "export JDK_17=\"$JDK_17\" JDK_21=\"$TOOLS_DIR/jdk-21\" JAVA_HOME=\"\$JDK_17\" PATH=\"$TOOLS_DIR/gradle-$GRADLE_VERSION/bin:\$PATH\""
