# Gradle Cache Action

Restore and save Gradle wrapper and dependency caches in GitHub Actions **without** using any official Gradle action.

 * Restores cache also when the build files change, like in dependabot PRs.
   * Only resets cache on gradle version updates.
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

### Outputs (restore only)

| Output | Description |
|---|---|
| `gradle-version` | Gradle version extracted from `gradle-wrapper.properties`. |


## How it works.

- Restores the **wrapper cache** (`~/.gradle/wrapper/dists`) first, using an exact-match key that includes the Gradle version — a stale version is never restored on cache miss.
- Restores the **dependency cache** (`~/.gradle/caches`) with a key that includes the Gradle version, a configurable prefix, and a hash of all build files. Falls back to a failed-build cache for the same hash, then to any prior cache for the same prefix.
- Caches from **failed builds** are saved under a separate `…-failed` key. Subsequent runs prefer a successful-build cache but will still use a failed-build cache as a warm start (so dependencies are not re-downloaded).
- Each saved cache includes a **`.gradle-cache-build-status`** marker file (`success` or `failure`) so the restore action can log and react to the provenance of what it restores.
- In the save step, runs Gradle's **built-in cache cleanup** (Gradle 8+ only) before storing the dependency cache, ensuring ephemeral or unused files are evicted rather than accumulated.
- Saves the dependency cache only when the key to be written differs from what was restored, skipping redundant writes.
- Skips all cache writes when the job is **cancelled**.

<details>
  <summary>More details.</summary>

### Restore (`restore/action.yml`)

1. Reads the Gradle version from `<gradle-home-directory>/gradle/wrapper/gradle-wrapper.properties` and validates it is ≥ 8.
2. Computes a hash of all `*.gradle`, `*.gradle.kts`, `gradle.properties`, `gradle-wrapper.properties`, and `*.versions.toml` files.
3. Restores the wrapper cache with key `gradle-wrapper-<os>-<gradle-version>` — **no restore-keys**, so a stale wrapper is never used on a miss.
4. Restores the dependency cache using this priority:
   - **Exact primary key** `gradle-deps-<os>-<action-ref>-<gradle-ver>-<prefix>-<hash>` — a prior successful build with this exact combination.
   - **`…-<hash>-` prefix** — a prior failed build with this exact hash (warm start, deps already downloaded).
   - **`…-<prefix>-` prefix** — any prior build for the same action version and prefix (partial warm start).
5. Reads `~/.gradle/caches/.gradle-cache-build-status` from the restored archive and logs its provenance.

### Save (`save/action.yml`)

1. If `build-outcome` is `cancelled`, exits immediately.
2. Saves the wrapper cache if it was not already present.
3. Re-hashes build files and computes the key to save under:
   - `success` → `gradle-deps-<os>-<action-ref>-<ver>-<prefix>-<hash>` (primary / clean key)
   - `failure` → `gradle-deps-<os>-<action-ref>-<ver>-<prefix>-<hash>-failed`
4. Compares the intended save key against the restored key. Skips if they are identical (cache is already up to date).
5. Writes `~/.gradle/caches/.gradle-cache-build-status` with `success` or `failure`.
6. Copies the appropriate init script (`save/scripts/cache-settings-8.0.gradle` or `save/scripts/cache-settings-8.8.gradle`) to `~/.gradle/init.d/cache-settings.gradle` and runs `gradlew --no-daemon projects` in a throw-away temp directory to trigger Gradle's built-in GC (see [gradle/gradle#29377](https://github.com/gradle/gradle/issues/29377)).
7. Removes the init script and temp directory.
8. Saves the dependency cache under the computed key.

### Cache key summary

| Cache | Key (success) | Key (failure) | Restore keys |
|---|---|---|---|
| Wrapper | `gradle-wrapper-<os>-<gradle-ver>` | *(same)* | *(none — exact match only)* |
| Dependencies | `gradle-deps-<os>-<action-ref>-<gradle-ver>-<prefix>-<hash>` | `…-<hash>-failed` | `…-<hash>-`, `…-<prefix>-` |

`<action-ref>` is the version tag used to call the action (e.g. `v1`, `v2`). Upgrading the action version automatically invalidates all dependency caches, preventing stale cached state from being reused across breaking action changes. When running the action via a local path reference (e.g. `uses: ./restore` in tests), `<action-ref>` falls back to `local`.

</details>

# License
[European Union Public Licence v1.2](https://eupl.eu/).

## Example project

The `example/` directory contains a minimal Java project used to test the action against every Gradle 8.x release. See `.github/workflows/test-gradle-*.yml`.
