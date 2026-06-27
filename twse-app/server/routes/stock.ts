import { Router, Request, Response } from 'express';
import {
  searchStocks,
  getHistory,
  getIndicators,
  getInstitutional,
  getShareholding,
  getQuote,
  getSRAnalysis,
  getMAAnalysis,
  getChipsAnalysis,
  getPredictionAnalysis,
  getPatternAnalysis,
} from '../controllers/stockController';

const router = Router();

router.get('/search', searchStocks);
router.get('/:id/history', getHistory);
router.get('/:id/indicators', getIndicators);
router.get('/:id/institutional', getInstitutional);
router.get('/:id/shareholding', getShareholding);
router.get('/:id/quote', getQuote);
router.get('/:id/sr-analysis', getSRAnalysis);
router.get('/:id/ma-analysis', getMAAnalysis);
router.get('/:id/chips-analysis', getChipsAnalysis);
router.get('/:id/prediction-analysis', getPredictionAnalysis);
router.get('/:id/pattern-analysis', getPatternAnalysis);

export default router;
