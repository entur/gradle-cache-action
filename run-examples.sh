#!/usr/bin/env bash
# run-examples.sh — build every Gradle example project locally.
#
# Usage:
#   ./run-examples.sh              # run all examples
#   ./run-examples.sh 8.13 9.4     # run specific minor versions only
#
# Requirements: Java 21+, internet access (wrapper downloads Gradle on first run).
#
# Exit code: 0 if all examples pass, 1 if any fail.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="${SCRIPT_DIR}/examples"

# All available minor versions in order
ALL_MINORS=(
  8.0 8.1 8.2 8.3 8.4 8.5 8.6 8.7
  8.8 8.9 8.10 8.11 8.12 8.13 8.14
  9.0 9.1 9.2 9.3 9.4
)

# If arguments provided, run only those versions; otherwise run all.
if [[ $# -gt 0 ]]; then
  MINORS=("$@")
else
  MINORS=("${ALL_MINORS[@]}")
fi

PASS=()
FAIL=()

for MINOR in "${MINORS[@]}"; do
  DIR_NAME="gradle-${MINOR//./-}"
  EXAMPLE_DIR="${EXAMPLES_DIR}/${DIR_NAME}"

  if [[ ! -d "${EXAMPLE_DIR}" ]]; then
    echo "⚠  ${DIR_NAME}: directory not found, skipping"
    continue
  fi

  GRADLE_VERSION=$(sed -n 's/.*gradle-\([0-9][0-9.]*\)-\(bin\|all\).*/\1/p' \
    "${EXAMPLE_DIR}/gradle/wrapper/gradle-wrapper.properties")

  printf '\n━━━ Gradle %s (%s) ━━━\n' "${GRADLE_VERSION}" "${DIR_NAME}"

  if (cd "${EXAMPLE_DIR}" && ./gradlew build --no-daemon --info --stacktrace 2>&1); then
    PASS+=("${MINOR} (${GRADLE_VERSION})")
    echo "✔  Gradle ${GRADLE_VERSION} — PASSED"
  else
    FAIL+=("${MINOR} (${GRADLE_VERSION})")
    echo "✘  Gradle ${GRADLE_VERSION} — FAILED"
  fi
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Results: ${#PASS[@]} passed, ${#FAIL[@]} failed"

if [[ ${#PASS[@]} -gt 0 ]]; then
  for v in "${PASS[@]}"; do echo "  ✔  ${v}"; done
fi
if [[ ${#FAIL[@]} -gt 0 ]]; then
  for v in "${FAIL[@]}"; do echo "  ✘  ${v}"; done
  exit 1
fi
