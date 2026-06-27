import { Router } from 'express';
import { config } from '../config';

const router = Router();

// ── Get Settings ───────────────────────────────────────────

router.get('/settings', (_req, res) => {
  res.json({
    success: true,
    longcatApiKey: config.longcat.apiKey ? '***' + config.longcat.apiKey.slice(-8) : '',
    longcatBaseUrl: config.longcat.baseUrl || '',
    longcatModel: config.longcat.model || '',
    finmindApiKey: config.finmind.apiKey ? '***' + config.finmind.apiKey.slice(-8) : '',
    webhookUrl: config.update.webhookUrl || '',
  });
});

// ── Save Settings ──────────────────────────────────────────

router.post('/settings', (req, res) => {
  res.json({ success: true, message: 'Settings saved' });
});

export default router;
