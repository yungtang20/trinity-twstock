// SQLite-backed multi-framework analysis job queue
// Solves: user switching browser tabs stops the old serial for-loop analysis.
//   Long-running work runs in a detached async IIFE; state is persisted to SQLite.
//   Polling reads the same state.  Server restart resumes interrupted jobs.
import { getDb } from "../db";
import { runFrameworkAnalysis } from "../mvpMcpRoutes";

export type JobStatus = "pending" | "running" | "done" | "error";
export type FrameworkStatus = "pending" | "running" | "done" | "error";

export interface FrameworkProgress {
  status: FrameworkStatus;
  report?: string;
  error?: string;
  startedAt?: number;
  endedAt?: number;
}

export interface Job {
  id: string;
  stockId: string;
  stockName?: string;
  frameworkIds: string[];
  status: JobStatus;
  perFramework: Record<string, FrameworkProgress>;
  error?: string;
  startedAt: number;
  updatedAt: number;
}

const TABLE_SQL = `
CREATE TABLE IF NOT EXISTS analysis_jobs (
  id TEXT PRIMARY KEY,
  stock_id TEXT NOT NULL,
  stock_name TEXT,
  framework_ids TEXT NOT NULL,
  framework_count INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  per_framework TEXT NOT NULL DEFAULT '{}',
  error TEXT,
  started_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_analysis_jobs_status ON analysis_jobs(status);
CREATE INDEX IF NOT EXISTS idx_analysis_jobs_updated ON analysis_jobs(updated_at DESC);
`;

let initialized = false;
function ensureTable() {
  if (initialized) return;
  const db = getDb();
  db.exec(TABLE_SQL);
  try {
    db.exec(`ALTER TABLE analysis_jobs ADD COLUMN stock_name TEXT;`);
  } catch(e) {}
  // Auto-cleanup jobs older than 24 hours
  try {
    db.exec(`DELETE FROM analysis_jobs WHERE updated_at < ${(Date.now() - 86400000)}`);
  } catch(e) {}
  initialized = true;
}

function nowMs(): number { return Date.now(); }

function mapRowToJob(row: any): Job {
  return {
    id: row.id,
    stockId: row.stock_id,
    stockName: row.stock_name || "",
    frameworkIds: JSON.parse(row.framework_ids),
    status: row.status as JobStatus,
    perFramework: JSON.parse(row.per_framework),
    error: row.error,
    startedAt: row.started_at,
    updatedAt: row.updated_at,
  };
}

export function listJobs(limit = 20): Job[] {
  ensureTable();
  const rows = getDb().prepare(`SELECT * FROM analysis_jobs ORDER BY updated_at DESC LIMIT ?`).all(limit);
  return rows.map(mapRowToJob);
}

export function getJob(id: string): Job | null {
  ensureTable();
  const row = getDb().prepare(`SELECT * FROM analysis_jobs WHERE id = ?`).get(id);
  return row ? mapRowToJob(row) : null;
}

export function deleteJob(id: string): boolean {
  ensureTable();
  const result = getDb().prepare("DELETE FROM analysis_jobs WHERE id = ?").run(id);
  return result.changes > 0;
}

export function deleteAllJobs(): number {
  ensureTable();
  const result = getDb().prepare("DELETE FROM analysis_jobs").run();
  return result.changes;
}

function upsertJob(job: Job) {
  try {
    getDb().exec(`ALTER TABLE analysis_jobs ADD COLUMN error TEXT;`);
  } catch(e) {} // Ignore if already exists
  try {
    getDb().exec(`ALTER TABLE analysis_jobs ADD COLUMN stock_name TEXT;`);
  } catch(e) {} // Ignore if already exists

  getDb()
    .prepare(
      `INSERT INTO analysis_jobs
        (id, stock_id, stock_name, framework_ids, framework_count, status, per_framework, error, started_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
       ON CONFLICT(id) DO UPDATE SET
         stock_name=excluded.stock_name,
         status=excluded.status,
         per_framework=excluded.per_framework,
         error=excluded.error,
         updated_at=excluded.updated_at`
    )
    .run(
      job.id,
      job.stockId,
      job.stockName || null,
      JSON.stringify(job.frameworkIds),
      job.frameworkIds.length,
      job.status,
      JSON.stringify(job.perFramework),
      job.error || null,
      job.startedAt,
      job.updatedAt
    );
}

// Fire-and-forget: kicks off the per-framework loop in a detached async IIFE.
//   Returns immediately with the job record.  Polling via getJob(id) surfaces progress.
export function startJob(stockId: string, frameworkIds: string[]): Job {
  ensureTable();
  const t = nowMs();
  const perFramework: Record<string, FrameworkProgress> = {};
  for (const f of frameworkIds) perFramework[f] = { status: "pending" };

  let stockName = "";
  try {
    const meta = getDb().prepare("SELECT stock_name FROM stock_meta WHERE stock_id = ?").get(stockId) as any;
    if (meta?.stock_name) {
      stockName = meta.stock_name;
    } else {
      const names: Record<string, string> = {
        '2330': '台積電', '2317': '鴻海', '2454': '聯發科', '2303': '聯電', '2603': '長榮',
        '3231': '緯創', '2382': '廣達', '2308': '台達電', '2881': '富邦金', '2882': '國泰金', '0050': '元大台灣50'
      };
      stockName = names[stockId] || "";
    }
  } catch (e) {
    console.warn("[jobQueue] failed to fetch stockName during startJob", e);
  }

  const job: Job = {
    id: `job_${t}_${Math.random().toString(36).slice(2, 9)}`,
    stockId,
    stockName,
    frameworkIds,
    status: "running",
    perFramework,
    startedAt: t,
    updatedAt: t,
  };
  upsertJob(job);

  (async () => {
    let hasError = false;
    for (const fwId of frameworkIds) {
      try {
        job.perFramework[fwId] = { status: "running", startedAt: Date.now() };
        job.updatedAt = Date.now();
        upsertJob(job);

        const report = await runFrameworkAnalysis(stockId, fwId);

        job.perFramework[fwId] = {
          status: "done",
          report,
          endedAt: Date.now(),
          startedAt: job.perFramework[fwId].startedAt,
        };
      } catch (e: any) {
        console.error(`[jobQueue] Error analyzing ${fwId}:`, e);
        job.perFramework[fwId] = {
          status: "error",
          error: e.message?.slice(0, 200) || "unknown",
          endedAt: Date.now(),
          startedAt: job.perFramework[fwId]?.startedAt,
        };
        hasError = true;
      }
      job.updatedAt = Date.now();
      upsertJob(job);
    }
    job.status = hasError ? "error" : "done";
    job.updatedAt = Date.now();
    upsertJob(job);
  })().catch((e) => {
    console.error("[jobQueue] top-level error", e);
    job.status = "error";
    job.updatedAt = Date.now();
    upsertJob(job);
  });

  return job;
}

// Resume jobs marked 'running' interrupted by server restart.
export function resumeInterruptedJobs(): void {
  ensureTable();
  const rows = getDb()
    .prepare(`SELECT * FROM analysis_jobs WHERE status = 'running' ORDER BY updated_at DESC`)
    .all();
  for (const row of rows) {
    const job = mapRowToJob(row);
    const nonDone = job.frameworkIds.filter(
      (f) => job.perFramework[f]?.status !== "done"
    );
    if (nonDone.length === 0) {
      // everything actually finished — reconcile status
      job.status = Object.values(job.perFramework).every((p) => p.status === "done")
        ? "done" : "error";
      job.updatedAt = Date.now();
      upsertJob(job);
      continue;
    }
    console.log(`[jobQueue] resume job ${job.id} (${job.stockId}), ${nonDone.length} frameworks remaining`);
    // kick off detached loop for remaining frameworks
    (async () => {
      let hasError = false;
      for (const fwId of nonDone) {
        try {
          job.perFramework[fwId] = { status: "running", startedAt: Date.now() };
          job.updatedAt = Date.now();
          upsertJob(job);
          const report = await runFrameworkAnalysis(job.stockId, fwId);
          job.perFramework[fwId] = {
            status: "done",
            report,
            endedAt: Date.now(),
            startedAt: job.perFramework[fwId].startedAt,
          };
        } catch (e: any) {
          console.error(`[jobQueue] Resume error analyzing ${fwId}:`, e);
          job.perFramework[fwId] = {
            status: "error",
            error: e.message?.slice(0, 200) || "unknown",
            endedAt: Date.now(),
            startedAt: job.perFramework[fwId]?.startedAt,
          };
          hasError = true;
        }
        job.updatedAt = Date.now();
        upsertJob(job);
      }
      job.status = hasError ? "error" : "done";
      job.updatedAt = Date.now();
      upsertJob(job);
    })().catch((e) => {
      console.error("[jobQueue] resume error", e);
      job.status = "error";
      job.updatedAt = Date.now();
      upsertJob(job);
    });
  }
}
