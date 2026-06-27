import { Router } from 'express';

const router = Router();

// ── Get Settings ───────────────────────────────────────────

router.get('/settings', (_req, res) => {
  res.json({
    success: true,
    longcatApiKey: process.env.VITE_LONGCAT_API_KEY ? '***' + process.env.VITE_LONGCAT_API_KEY.slice(-8) : '',
    longcatBaseUrl: process.env.VITE_LONGCAT_BASE_URL || '',
    longcatModel: process.env.VITE_LONGCAT_MODEL || '',
    finmindApiKey: process.env.VITE_FINMIND_API_KEY ? '***' + process.env.VITE_FINMIND_API_KEY.slice(-8) : '',
    webhookUrl: process.env.VITE_UPDATE_WEBHOOK_URL || '',
  });
});

// ── Save Settings ──────────────────────────────────────────

router.post('/settings', (req, res) => {
  res.json({ success: true, message: 'Settings saved' });
});

export default router;
