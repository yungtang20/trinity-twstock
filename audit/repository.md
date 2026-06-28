# TWSE-ANYTARA Repository Cleanup Audit (`audit/repository.md`)

This audit reviews files in the repository to identify redundant or cleanable files, legacy code fragments, temporary caches, and AI assistant residuals, explaining why each is retained or queued for purging.

## 1. Debris & Temporary File Status

A thorough traversal of the project files has been executed to find unwanted leftovers, IDE/editor configurations, cache files, and test files:

| File Pattern / Category | Specific File | Presence / Status | Risk/Impact & Action | Estimated Saving |
| :--- | :--- | :--- | :--- | :--- |
| **MacOS Metadata** | `.DS_Store` | **Clean** / Excluded by `.gitignore` | None. Correctly blocked from repository commits. | 0 KB |
| **Log Dumps** | `*.log`, `npm-debug.log` | **Clean** | No residual build logs or crash dumps found on root. | 0 KB |
| **Build Residuals** | `/dist` folder | **Clean** / Excluded | Excluded correctly in gitignore. Production compilations are kept ephemeral. | 0 KB |
| **Diagnostic Leftovers** | `tofixed-check.txt` | **Deleted** | This temporary dump file from past queries was successfully pruned. | ~17.0 KB |
| **Vite Sandbox Trails** | `dev-server-*.log` | **Clean** | No runtime PM2 or Vite crashlogs persisted at the root level. | 0 KB |
| **SQLite WAL Buffers** | `taiwan_stock_unified.db-wal` | **Active Temp** | Part of SQLite performance enhancement. Self-evaporating on close under correct system hooks. | ~1.2 MB |
| **SQLite Shared Memory** | `taiwan_stock_unified.db-shm` | **Active Temp** | WAL concurrent read support buffers. Volatile and safe. | 32 KB |
| **Legacy fetchers** | `fetch.cjs` | **Retained (Legacy)** | This helper is retained since it provides fallback sync rules for SQLite database rebuilds. | ~3.5 KB |
| **Corporate specification assets** | `/股市` files | **Retained (Requirements)** | These requirement documents contain complex expert parameters used by deep LLMs in `src/api/ai.ts`. | ~120 KB |
| **Dev-Test Typings** | `*.test-d.ts` | **Clean** | No active debug definition files left in compilation folders. | 0 KB |

## 2. `.gitignore` Configuration Analysis

The configuration in `.gitignore` was reviewed to determine if any runtime patterns are improperly tracked:

```
# Core exclusions present in git:
node_modules/
dist/
.env
*.db-journal
*.db-wal
*.db-shm
__pycache__/
*.pyc
```

### Exclusions Verification:
1. **Node Dependencies**: `/node_modules` is properly excluded.
2. **Compiled Bundles**: `/dist` (both TS backend and React artifacts) is excluded, preventing bloating deployment images.
3. **Environmental Secrets**: `.env` is blocked, protecting API keys (FinMind, Supabase, Gemini) from being leaked.
4. **Python Artifacts**: `__pycache__` and `.pyc` files are blocked, maintaining compatibility on multi-platform runtimes.

## 3. Database Purging Strategy Analysis

The project holds a local transactional SQLite database `taiwan_stock_unified.db` standing at **~4.8 MB** (post vacuum). 
Inside `server.ts` (lines 485-490), there is an active auto-compaction trigger executing on startup:

```ts
// Purge queries tracking historical records >30 days to sustain container lightweight footprint
tempDb.prepare(`DELETE FROM stock_history WHERE date < date('now', '-30 days')`).run();
tempDb.prepare(`DELETE FROM institutional_data WHERE date < date('now', '-30 days')`).run();
```

*   **Positive impact**: Keeps memory and directory footprint ultra-lean and compatible with instant server restarts.
*   **Limitation**: If some offline analytical views inside `StrategiesView.tsx` try to do a 60-day MA (Moving Average) or 200-day trend scanning, they will detect a data cap and report "Insufficient data" unless the online fetch queries Supabase first. Fortunately, the client query system handles this bypass.

## 4. Remedial Actions & Standard Policy

1.  **Enforce Clean Pre-build Command**: Introduce `/scripts` cleaning pipeline:
    *   Add an explicit cleanup step in `package.json` with standard glob scripts to ensure CJS bundling doesn't carry residual files.
2.  **Verify Wal/Shm Deletion on Process SigTerm**: Make sure database connections handle `db.close()` cleanly during container shutdown events to prevent leftover `-wal` lock files when running on short-lived Cloud Run instances.
