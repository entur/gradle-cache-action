# Gradle Cache Action

Restore and save Gradle wrapper and dependency caches in GitHub Actions **without** using any official Gradle action.

 * Restores cache also when the build files change, like in dependabot PRs.
   * Only resets cache on Gradle version updates.
 * Clears unused dependencies before saving cache.

Supports Gradle **8.0 or higher**.

## Usage
Add **TWO** steps:

```yaml
steps:
  - uses: actions/checkout@v6

  - uses: actions/setup-java@v5
    with:
      distribution: temurin
      java-version: "25"

  - name: Restore Gradle cache
    uses: entur/gradle-cache-action/restore@v1

  - name: Build
    run: ./gradlew build

  - name: Save Gradle cache
    if: always()                  # run even on failure so failed-build caches are stored
    uses: entur/gradle-cache-action/save@v1
    with:
      build-outcome: ${{ job.status }}
```

## Inputs

### Restore (`restore/`)

| Input | Default | Description |
|---|---|---|
| `gradle-home-directory` | `.` | Root directory of the Gradle project (where `gradlew` lives). |
| `cache-prefix` | `default` | String included in the dependency cache key. Bump to manually invalidate the cache. |

### Save (`save/`)

| Input | Default | Description |
|---|---|---|
| `gradle-home-directory` | `.` | Must match the restore action value. |
| `cache-prefix` | `default` | Must match the restore action value. |
| `build-outcome` | *(required)* | Pass `${{ job.status }}`. Accepted values: `success`, `failure`, `cancelled`. |

## How it works

- Restores the **wrapper cache** (`~/.gradle/wrapper/dists`) first
- Restores the **dependency cache** (`~/.gradle/caches`) with a key that includes the Gradle version, a configurable prefix, and a hash of all build files.
- Saves the **dependency cache** when build files changes. Runs Gradle's **built-in cache cleanup** (Gradle 8+ only) first.

# License
[European Union Public Licence v1.2](https://eupl.eu/).

## Example project

The `example/` directory contains a minimal Java project used to test the action against every Gradle 8.x release. See `.github/workflows/test-gradle-*.yml`.
