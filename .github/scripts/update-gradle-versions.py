#!/usr/bin/env python3
"""
Check https://services.gradle.org/versions/all for Gradle releases that are
not yet covered by a test workflow, and generate the missing workflow files
and corresponding example project directories.

Exit codes:
  0 – one or more new workflow/example files were written
  1 – everything is already up to date (no new files)
"""

import json
import re
import stat
import sys
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

VERSIONS_API = "https://services.gradle.org/versions/all"
WORKFLOWS_DIR = Path(".github/workflows")
EXAMPLES_DIR  = Path("examples")
MIN_MAJOR = 8  # Gradle 8+ required for built-in cache cleanup

# Java version to use when running Gradle in CI (runner JDK).
# All supported versions run fine on Java 21.
def java_version_for(major: int, minor: int) -> str:
    return "21"


# Java language version to target in the example build.gradle.kts (toolchain).
# Gradle 8.0-8.3 predate Java 21 GA (Sep 2023) and do not support it as a
# toolchain compilation target; use Java 17 (LTS) for those versions.
def java_toolchain_version_for(major: int, minor: int) -> int:
    if major == 8 and minor < 4:
        return 17
    return 21


# ── version helpers ──────────────────────────────────────────────────────────

def is_stable(v: dict) -> bool:
    """Return True for final releases only (no snapshot, nightly, RC, milestone)."""
    version_str = v.get("version", "")
    return (
        not v.get("snapshot")
        and not v.get("nightly")
        and not v.get("releaseNightly")
        and bool(version_str)
        and re.fullmatch(r"\d+\.\d+(\.\d+)?", version_str) is not None
    )


def parse_version(version_str: str) -> tuple[int, ...]:
    return tuple(int(x) for x in version_str.split("."))


def latest_patch_per_minor(versions: list[dict]) -> dict[tuple[int, int], str]:
    """
    Return {(major, minor): latest_patch_version_string} for all stable
    releases at or above MIN_MAJOR.
    """
    latest: dict[tuple[int, int], str] = {}
    for v in versions:
        ver = v["version"]
        parts = ver.split(".")
        if len(parts) < 2:
            continue
        major, minor = int(parts[0]), int(parts[1])
        if major < MIN_MAJOR:
            continue
        key = (major, minor)
        if key not in latest or parse_version(ver) > parse_version(latest[key]):
            latest[key] = ver
    return latest


def covered_versions() -> set[tuple[int, int]]:
    """Return the (major, minor) pairs that already have a test workflow."""
    covered: set[tuple[int, int]] = set()
    for f in WORKFLOWS_DIR.glob("test-gradle-*.yml"):
        m = re.fullmatch(r"test-gradle-(\d+)-(\d+)\.yml", f.name)
        if m:
            covered.add((int(m.group(1)), int(m.group(2))))
    return covered


# ── example project templates ─────────────────────────────────────────────────

def build_gradle(toolchain_java: int) -> str:
    return f"""\
plugins {{
    java
    application
}}

repositories {{
    mavenCentral()
}}

dependencies {{
    implementation("com.google.guava:guava:33.2.1-jre")
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.3")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}}

application {{
    mainClass = "com.example.App"
}}

java {{
    toolchain {{
        languageVersion = JavaLanguageVersion.of({toolchain_java})
    }}
}}

tasks.test {{
    useJUnitPlatform()
}}
"""

APP_JAVA = """\
package com.example;

import com.google.common.collect.ImmutableList;

public class App {
    public static void main(String[] args) {
        ImmutableList<String> messages = ImmutableList.of("Hello", "from", "Gradle", "cache", "action!");
        System.out.println(String.join(" ", messages));
    }

    public static String greeting() {
        return "Hello, World!";
    }
}
"""

APP_TEST_JAVA = """\
package com.example;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;

class AppTest {
    @Test
    void greetingIsCorrect() {
        assertEquals("Hello, World!", App.greeting());
    }
}
"""


def gh_tag(version: str) -> str:
    """Return the GitHub tag for a given Gradle version string."""
    parts = version.split(".")
    # Versions without a patch number (e.g. "8.8") need ".0" for GitHub tags.
    return f"v{version}.0" if len(parts) == 2 else f"v{version}"


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()


def create_example(major: int, minor: int, version: str) -> str:
    """Create examples/gradle-{major}-{minor}/ with correct wrapper files."""
    tag      = gh_tag(version)
    safe     = f"{major}-{minor}"
    ex_dir   = EXAMPLES_DIR / f"gradle-{safe}"

    # Directory tree
    (ex_dir / "gradle" / "wrapper").mkdir(parents=True, exist_ok=True)
    (ex_dir / "src" / "main" / "java" / "com" / "example").mkdir(parents=True, exist_ok=True)
    (ex_dir / "src" / "test" / "java" / "com" / "example").mkdir(parents=True, exist_ok=True)

    # Project-specific settings
    (ex_dir / "settings.gradle.kts").write_text(
        f'rootProject.name = "gradle-cache-action-{major}.{minor}"\n'
    )
    (ex_dir / "build.gradle.kts").write_text(build_gradle(java_toolchain_version_for(major, minor)))
    (ex_dir / "src" / "main" / "java" / "com" / "example" / "App.java").write_text(APP_JAVA)
    (ex_dir / "src" / "test" / "java" / "com" / "example" / "AppTest.java").write_text(APP_TEST_JAVA)

    # gradle-wrapper.properties (version-specific)
    (ex_dir / "gradle" / "wrapper" / "gradle-wrapper.properties").write_text(
        f"distributionBase=GRADLE_USER_HOME\n"
        f"distributionPath=wrapper/dists\n"
        f"distributionUrl=https\\://services.gradle.org/distributions/gradle-{version}-bin.zip\n"
        f"networkTimeout=10000\n"
        f"validateDistributionUrl=true\n"
        f"zipStoreBase=GRADLE_USER_HOME\n"
        f"zipStorePath=wrapper/dists\n"
    )

    # Download gradlew from the Gradle GitHub repository for this exact version
    gradlew_path = ex_dir / "gradlew"
    gradlew_path.write_bytes(
        fetch(f"https://raw.githubusercontent.com/gradle/gradle/{tag}/gradlew")
    )
    gradlew_path.chmod(gradlew_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    # Download gradle-wrapper.jar from the Gradle GitHub repository
    (ex_dir / "gradle" / "wrapper" / "gradle-wrapper.jar").write_bytes(
        fetch(f"https://raw.githubusercontent.com/gradle/gradle/{tag}/gradle/wrapper/gradle-wrapper.jar")
    )

    return f"gradle-{safe}  (Gradle {version})"


# ── workflow template ─────────────────────────────────────────────────────────

def workflow_content(major: int, minor: int, version: str) -> str:
    safe = f"{major}-{minor}"
    java = java_version_for(major, minor)
    GH   = "${{{{ {0} }}}}"  # renders as ${{ <expr> }} in the output YAML

    return f"""\
name: Test Gradle {version}

on:
  push:
    branches: ["main"]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - name: Set up Java {java}
        uses: actions/setup-java@v5
        with:
          distribution: temurin
          java-version: "{java}"

      # ── First restore ─────────────────────────────────────────────────────
      - name: Restore Gradle cache
        uses: ./restore
        with:
          gradle-home-directory: examples/gradle-{safe}

      - name: Build and test
        run: ./gradlew build --no-daemon
        working-directory: examples/gradle-{safe}

      # Plant sentinel files in both cache directories.  After the cache is
      # saved and the local directories are deleted, a second restore must
      # bring them back for the verification step to pass.
      - name: Add custom files to Gradle cache directories
        run: |
          mkdir -p ~/.gradle/caches ~/.gradle/wrapper/dists
          echo "gradle-{version}-deps-marker" > ~/.gradle/caches/.test-marker
          echo "gradle-{version}-wrapper-marker" > ~/.gradle/wrapper/dists/.test-marker

      - name: Save Gradle cache
        if: always()
        uses: ./save
        with:
          gradle-home-directory: examples/gradle-{safe}
          build-outcome: {GH.format("job.status")}

      # Wipe the local Gradle home so the second restore starts from scratch.
      - name: Delete local Gradle cache directories
        run: rm -rf ~/.gradle/caches ~/.gradle/wrapper/dists

      # ── Second restore ────────────────────────────────────────────────────
      - name: Restore Gradle cache (verify round-trip)
        uses: ./restore
        with:
          gradle-home-directory: examples/gradle-{safe}

      - name: Verify custom files survived the save/delete/restore cycle
        run: |
          FAIL=0

          if [[ ! -f ~/.gradle/wrapper/dists/.test-marker ]]; then
            echo "::error::Wrapper cache marker not found after restore — wrapper cache round-trip failed."
            FAIL=1
          else
            echo "Wrapper cache marker: $(cat ~/.gradle/wrapper/dists/.test-marker)"
          fi

          if [[ ! -f ~/.gradle/caches/.test-marker ]]; then
            echo "::error::Dependency cache marker not found after restore — dependency cache round-trip failed."
            FAIL=1
          else
            echo "Dependency cache marker: $(cat ~/.gradle/caches/.test-marker)"
          fi

          exit $FAIL
"""


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    print(f"Fetching Gradle version list from {VERSIONS_API} …")
    with urllib.request.urlopen(VERSIONS_API, timeout=30) as resp:
        all_versions: list[dict] = json.loads(resp.read())

    stable = [v for v in all_versions if is_stable(v)]
    print(f"  {len(stable)} stable releases found (out of {len(all_versions)} total)")

    latest          = latest_patch_per_minor(stable)
    already_covered = covered_versions()

    new_minors = sorted(
        [(major, minor) for (major, minor) in latest if (major, minor) not in already_covered]
    )

    if not new_minors:
        print("Everything is up to date — no new Gradle versions to add.")
        return 1  # signal "nothing changed" to the calling workflow

    print(f"\n{len(new_minors)} new major/minor version(s) found:")

    # Download wrapper files in parallel; write workflows serially (fast).
    def handle(major: int, minor: int) -> tuple[int, int, str]:
        version = latest[(major, minor)]
        create_example(major, minor, version)
        return major, minor, version

    EXAMPLES_DIR.mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(handle, maj, min_): (maj, min_) for maj, min_ in new_minors}
        results = []
        for fut in as_completed(futures):
            major, minor, version = fut.result()
            results.append((major, minor, version))

    for major, minor, version in sorted(results):
        safe     = f"{major}-{minor}"
        filename = f"test-gradle-{safe}.yml"
        (WORKFLOWS_DIR / filename).write_text(workflow_content(major, minor, version))
        print(f"  + {filename}  /  examples/gradle-{safe}  (Gradle {version}, Java {java_version_for(major, minor)})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
