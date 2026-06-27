import { Router } from 'express';

const router = Router();

// ── AI Analysis ────────────────────────────────────────────

router.post('/ai-analysis', async (req, res) => {
  const { stockId, template = 'goldman' } = req.body;

  if (!stockId) {
    return res.status(400).json({ success: false, error: 'stockId is required' });
  }

  try {
    // Dynamic import to avoid circular dependencies
    const { getAIAnalysis } = await import('../services/analysisService');
    const result = await getAIAnalysis(stockId, template);

    if (!result) {
      return res.json({
        success: false,
        error: 'Unable to build AI context - no data available',
      });
    }

    res.json({
      success: true,
      result: result.result,
      data_version: result.data_version,
      prompt_version: result.prompt_version,
      model_version: result.model_version,
    });
  } catch (err: any) {
    res.status(500).json({ success: false, error: err.message });
  }
});

export default router;
