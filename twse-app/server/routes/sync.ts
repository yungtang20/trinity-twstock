import { Router } from 'express';
import { getSyncStatus, startBackgroundSync } from '../services/syncService';
import { config } from '../config';

const router = Router();

// ── Sync Daily ──────────────────────────────────────────────

router.post('/sync-daily', (req, res) => {
  res.json({ success: true, message: 'Daily sync triggered' });
});

// ── Trigger Update ─────────────────────────────────────────

router.post('/trigger-update', async (req, res) => {
  const webhookUrl = config.update.webhookUrl;
  const result = await startBackgroundSync(webhookUrl);

  if (result.alreadyRunning) {
    return res.json({ success: true, message: '同步流程已在中途執行', alreadyRunning: true });
  }

  res.json({ success: true, message: '同步指令已送達！', alreadyRunning: false });
});

// ── Sync Status ────────────────────────────────────────────

router.get('/sync-status', (_req, res) => {
  const status = getSyncStatus();
  res.json({ success: true, ...status });
});

// ── Backfill FinMind ───────────────────────────────────────

router.post('/backfill-finmind', (req, res) => {
  res.json({ success: false, error: 'Not implemented' });
});

// ── Upload TDCC ────────────────────────────────────────────

router.post('/upload-tdcc', (req, res) => {
  res.json({ success: false, error: 'Not implemented' });
});

// ── Auto Download TDCC ─────────────────────────────────────

router.post('/auto-download-tdcc', (req, res) => {
  res.json({ success: false, error: 'Not implemented' });
});

export default router;
