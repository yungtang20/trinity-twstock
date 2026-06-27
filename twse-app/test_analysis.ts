import { initializeDatabase, getDb } from './server/db';
import { getSRAnalysis, getMAAnalysis, getChipsAnalysis, getPredictionAnalysis, getPatternAnalysis } from './server/services/technicalAnalysisService';

initializeDatabase();
const db = getDb();
if (!db) { console.log('DB null'); process.exit(1); }

console.log('=== SR Analysis (2330) ===');
const sr = getSRAnalysis(db, '2330');
if (sr) { console.log('price:', sr.currentPrice, 'supports:', sr.supports.length, 'resistances:', sr.resistances.length); }
else console.log('null');

console.log('=== MA Analysis (2330) ===');
const ma = getMAAnalysis(db, '2330');
if (ma) { console.log('ma5:', ma.ma5, 'ma20:', ma.ma20, 'arr:', ma.arrangementLabel); }
else console.log('null');

console.log('=== Chips Analysis (2330) ===');
const chips = getChipsAnalysis(db, '2330');
if (chips) { console.log('foreign today:', chips.foreign.today, 'trust today:', chips.trust.today); }
else console.log('null');

console.log('=== Prediction (2330) ===');
const pred = getPredictionAnalysis(db, '2330');
if (pred) { console.log('score:', pred.score, '/', pred.maxScore, pred.directionLabel); }
else console.log('null');

console.log('=== Pattern (2330) ===');
const pat = getPatternAnalysis(db, '2330');
if (pat) { console.log('patterns:', pat.patterns.length, '-', pat.summary?.slice(0, 60)); }
else console.log('null');

process.exit(0);
