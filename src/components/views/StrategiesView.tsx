import React, { useState } from 'react';
import { Zap, TrendingUp, Users, ShieldCheck, Activity, ChevronLeft, Search, ArrowUpDown } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { SRPanel } from './SRPanel';
import { MAPanel } from './MAPanel';
import { ChipsPanel } from './ChipsPanel';
import { PredictionPanel } from './PredictionPanel';
import { PatternPanel } from './PatternPanel';
import { fetchStockSearch, type StockMeta } from '../../lib/api';
import {
  fetchSRScan, fetchMAScan, fetchChipsScan, fetchPredictionScan, fetchPatternScan,
  type SRScanItem, type MAScanItem, type ChipsScanItem, type PredictionScanItem, type PatternScanItem
} from '../../lib/api';

const strategies = [
  { id: 'support-resistance', name: '撐壓分析策略', icon: TrendingUp, desc: '析出多空區間關鍵價位，計算並定位最近、短期與長期之支撐與阻力核心水位。', color: 'text-amber-400', bg: 'bg-amber-400/10' },
  { id: 'ma-trend', name: '均線趨勢策略', icon: Activity, desc: '追蹤均線排列及各週期扣抵判定，利用精密扣抵模型（MA-Deduction）透析多空強勢區。', color: 'text-blue-400', bg: 'bg-blue-400/10' },
  { id: 'chips-flow', name: '籌碼流向策略', icon: Users, desc: '全面同步三大法人買賣超及大戶持股，鎖定連續性主力金流焦點個股。', color: 'text-purple-400', bg: 'bg-purple-400/10' },
  { id: 'ai-forecast', name: 'AI預估策略', icon: Zap, desc: '採用 Kronos 模型加權推理，動態對照預估未來多日 T+1 到 T+5 的偏好路徑。', color: 'text-emerald-400', bg: 'bg-emerald-400/10' },
  { id: 'pattern-shape', name: '型態分析策略', icon: ShieldCheck, desc: '智能對比 W 底與關鍵頸線防線，動態測算起漲黃金交叉區與止盈止損防守水位。', color: 'text-rose-400', bg: 'bg-rose-400/10' },
];

interface ScanConfig {
  id: string;
  minVolume: number;
  sort: string;
  // MA specific
  maType?: string;
  // Chips specific
  chipsType?: string;
}

export function StrategiesView() {
  const [selectedStrategy, setSelectedStrategy] = useState<string | null>(null);
  const [stockId, setStockId] = useState<string>('');
  const [stockName, setStockName] = useState<string>('');
  const [searchResults, setSearchResults] = useState<StockMeta[]>([]);
  const [searching, setSearching] = useState(false);

  // Scan state
  const [showScanOptions, setShowScanOptions] = useState(false);
  const [minVolume, setMinVolume] = useState('500');
  const [scanning, setScanning] = useState(false);
  const [scanResults, setScanResults] = useState<any[] | null>(null);
  const [scanSort, setScanSort] = useState('1');
  const [scanConfig, setScanConfig] = useState<ScanConfig>({
    id: '', minVolume: 500, sort: '1',
  });

  const [selectedStockForScan, setSelectedStockForScan] = useState<string | null>(null);

  const activeStrategy = strategies.find(s => s.id === selectedStrategy);

  const handleSearch = async (query: string) => {
    setStockId(query);
    if (query.length < 2) {
      setSearchResults([]);
      return;
    }
    setSearching(true);
    try {
      const results = await fetchStockSearch(query);
      setSearchResults(results);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  const selectStock = (stock: StockMeta) => {
    setStockId(stock.stock_id);
    setStockName(stock.stock_name);
    setSearchResults([]);
    setScanResults(null);
    setSelectedStockForScan(stock.stock_id);
  };

  // Handle input for scan or stock search
  const handleInputAction = async () => {
    const query = stockId.trim();
    if (!query) return;

    if (query === '1') {
      // Show scan options
      setShowScanOptions(true);
      setScanResults(null);
      setSearchResults([]);
      return;
    }

    // Try stock search
    if (query.length >= 2) {
      try {
        const results = await fetchStockSearch(query);
        if (results.length > 0) {
          selectStock(results[0]);
        }
      } catch {}
    }
  };

  // Execute scan
  const executeScan = async () => {
    if (!selectedStrategy) return;
    setScanning(true);
    setScanResults(null);
    const mv = parseInt(minVolume) || 500;
    try {
      let results: any[] = [];
      switch (selectedStrategy) {
        case 'support-resistance':
          results = await fetchSRScan(mv, scanSort);
          break;
        case 'ma-trend':
          results = await fetchMAScan(mv, scanConfig.maType || '1', scanSort);
          break;
        case 'chips-flow':
          results = await fetchChipsScan(scanConfig.chipsType || '1', scanSort);
          break;
        case 'ai-forecast':
          results = await fetchPredictionScan(mv, scanSort);
          break;
        case 'pattern-shape':
          results = await fetchPatternScan(mv, scanSort);
          break;
      }
      setScanResults(results);
    } catch {
      setScanResults([]);
    } finally {
      setScanning(false);
    }
  };

  const selectFromScan = (item: any) => {
    setStockId(item.stock_id);
    setStockName(item.stock_name);
    setSelectedStockForScan(item.stock_id);
    setScanResults(null);
    setShowScanOptions(false);
  };

  const renderPanel = () => {
    if (!stockId || !selectedStrategy) return null;
    // Only render if we have a stock selected from scan or direct search
    if (!selectedStockForScan && !stockName && stockId.length !== 4) return null;
    const sid = selectedStockForScan || stockId;
    switch (selectedStrategy) {
      case 'support-resistance':
        return <SRPanel stockId={sid} />;
      case 'ma-trend':
        return <MAPanel stockId={sid} change={0} changePercent={0} />;
      case 'chips-flow':
        return <ChipsPanel stockId={sid} />;
      case 'ai-forecast':
        return <PredictionPanel stockId={sid} />;
      case 'pattern-shape':
        return <PatternPanel stockId={sid} />;
      default:
        return null;
    }
  };

  const getScanResultKey = (item: any) => `${item.stock_id}-${item.stock_name}`;

  // Render scan results table based on strategy
  const renderScanTable = () => {
    if (scanning) {
      return (
        <div className="text-center py-8">
          <div className="inline-block w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
          <p className="text-slate-400 text-sm mt-2">掃描中...</p>
        </div>
      );
    }

    if (!scanResults || scanResults.length === 0) {
      return (
        <div className="text-center py-8 text-slate-500 text-sm">
          無掃描結果，請調整條件後重試
        </div>
      );
    }

    switch (selectedStrategy) {
      case 'support-resistance':
        return renderSRTable(scanResults as SRScanItem[]);
      case 'ma-trend':
        return renderMATable(scanResults as MAScanItem[]);
      case 'chips-flow':
        return renderChipsTable(scanResults as ChipsScanItem[]);
      case 'ai-forecast':
        return renderPredictionTable(scanResults as PredictionScanItem[]);
      case 'pattern-shape':
        return renderPatternTable(scanResults as PatternScanItem[]);
      default:
        return null;
    }
  };

  const renderSRTable = (items: SRScanItem[]) => (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="text-slate-500 border-b border-slate-800">
            <th className="text-left py-2 px-2">強</th>
            <th className="text-left py-2 px-2">代號</th>
            <th className="text-left py-2 px-2">名稱</th>
            <th className="text-right py-2 px-2">收盤</th>
            <th className="text-right py-2 px-2">量(張)</th>
            <th className="text-right py-2 px-2">額(億)</th>
            <th className="text-left py-2 px-2">動態</th>
            <th className="text-right py-2 px-2">距支撐</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.stock_id}
              onClick={() => selectFromScan(item)}
              className="border-b border-slate-800/50 hover:bg-blue-500/5 cursor-pointer transition-colors"
            >
              <td className="py-2 px-2 text-cyan-400">{item.score}</td>
              <td className="py-2 px-2 text-fuchsia-400">{item.stock_id}</td>
              <td className="py-2 px-2 text-white">{item.stock_name}</td>
              <td className="py-2 px-2 text-right text-yellow-400">{item.close.toFixed(2)}</td>
              <td className="py-2 px-2 text-right text-green-400">{item.volume.toLocaleString()}</td>
              <td className="py-2 px-2 text-right text-yellow-300">{item.amount.toFixed(2)}</td>
              <td className="py-2 px-2 text-blue-300 max-w-[160px] truncate">{item.tags}</td>
              <td className="py-2 px-2 text-right text-red-400">{item.dist > 0 ? '+' : ''}{item.dist.toFixed(2)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const renderMATable = (items: MAScanItem[]) => (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="text-slate-500 border-b border-slate-800">
            <th className="text-left py-2 px-2">代號</th>
            <th className="text-left py-2 px-2">名稱</th>
            <th className="text-right py-2 px-2">收盤</th>
            <th className="text-right py-2 px-2">量(張)</th>
            <th className="text-right py-2 px-2">額(億)</th>
            <th className="text-right py-2 px-2">{items[0]?.targetLabel || '目標'}</th>
            <th className="text-right py-2 px-2">乖離率</th>
            <th className="text-right py-2 px-2">曾回踩</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.stock_id}
              onClick={() => selectFromScan(item)}
              className="border-b border-slate-800/50 hover:bg-blue-500/5 cursor-pointer transition-colors"
            >
              <td className="py-2 px-2 text-fuchsia-400">{item.stock_id}</td>
              <td className="py-2 px-2 text-white">{item.stock_name}</td>
              <td className="py-2 px-2 text-right text-yellow-400">{item.close.toFixed(2)}</td>
              <td className="py-2 px-2 text-right text-green-400">{item.volume.toLocaleString()}</td>
              <td className="py-2 px-2 text-right text-yellow-300">{item.amount.toFixed(2)}</td>
              <td className="py-2 px-2 text-right text-white">{item.targetMA.toFixed(2)}</td>
              <td className="py-2 px-2 text-right text-red-400">{item.bias > 0 ? '+' : ''}{item.bias.toFixed(2)}%</td>
              <td className="py-2 px-2 text-right text-cyan-400">{item.touchCount}次</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const renderChipsTable = (items: ChipsScanItem[]) => (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="text-slate-500 border-b border-slate-800">
            <th className="text-left py-2 px-2">代號</th>
            <th className="text-left py-2 px-2">名稱</th>
            <th className="text-right py-2 px-2">收盤</th>
            <th className="text-right py-2 px-2">量(張)</th>
            <th className="text-right py-2 px-2">額(億)</th>
            <th className="text-right py-2 px-2">{items[0]?.type || '類型'}</th>
            <th className="text-right py-2 px-2">連買/賣(天)</th>
            <th className="text-right py-2 px-2">淨額(千張)</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.stock_id}
              onClick={() => selectFromScan(item)}
              className="border-b border-slate-800/50 hover:bg-blue-500/5 cursor-pointer transition-colors"
            >
              <td className="py-2 px-2 text-fuchsia-400">{item.stock_id}</td>
              <td className="py-2 px-2 text-white">{item.stock_name}</td>
              <td className="py-2 px-2 text-right text-yellow-400">{item.close.toFixed(2)}</td>
              <td className="py-2 px-2 text-right text-green-400">{item.volume.toLocaleString()}</td>
              <td className="py-2 px-2 text-right text-yellow-300">{item.amount.toFixed(2)}</td>
              <td className="py-2 px-2 text-right text-purple-400">{item.type}</td>
              <td className="py-2 px-2 text-right text-cyan-400">{item.consecutive}</td>
              <td className="py-2 px-2 text-right text-green-300">{item.netTotal}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const renderPredictionTable = (items: PredictionScanItem[]) => (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="text-slate-500 border-b border-slate-800">
            <th className="text-left py-2 px-2">代號</th>
            <th className="text-left py-2 px-2">名稱</th>
            <th className="text-right py-2 px-2">收盤</th>
            <th className="text-right py-2 px-2">量(張)</th>
            <th className="text-right py-2 px-2">額(億)</th>
            <th className="text-center py-2 px-2">AI方向</th>
            <th className="text-right py-2 px-2">AI分數</th>
            <th className="text-right py-2 px-2">預估(T+1)</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.stock_id}
              onClick={() => selectFromScan(item)}
              className="border-b border-slate-800/50 hover:bg-blue-500/5 cursor-pointer transition-colors"
            >
              <td className="py-2 px-2 text-fuchsia-400">{item.stock_id}</td>
              <td className="py-2 px-2 text-white">{item.stock_name}</td>
              <td className="py-2 px-2 text-right text-yellow-400">{item.close.toFixed(2)}</td>
              <td className="py-2 px-2 text-right text-green-400">{item.volume.toLocaleString()}</td>
              <td className="py-2 px-2 text-right text-yellow-300">{item.amount.toFixed(2)}</td>
              <td className="py-2 px-2 text-center text-emerald-400">{item.aiStrength}</td>
              <td className="py-2 px-2 text-right text-white">{item.aiScore.toFixed(2)}</td>
              <td className="py-2 px-2 text-right text-cyan-400">{item.predPrice.toFixed(2)} ({item.predPct > 0 ? '+' : ''}{item.predPct.toFixed(2)}%)</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const renderPatternTable = (items: PatternScanItem[]) => (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="text-slate-500 border-b border-slate-800">
            <th className="text-left py-2 px-2">代號</th>
            <th className="text-left py-2 px-2">名稱</th>
            <th className="text-right py-2 px-2">收盤</th>
            <th className="text-right py-2 px-2">量(張)</th>
            <th className="text-right py-2 px-2">額(億)</th>
            <th className="text-left py-2 px-2">型態</th>
            <th className="text-right py-2 px-2">信心度</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.stock_id}
              onClick={() => selectFromScan(item)}
              className="border-b border-slate-800/50 hover:bg-blue-500/5 cursor-pointer transition-colors"
            >
              <td className="py-2 px-2 text-fuchsia-400">{item.stock_id}</td>
              <td className="py-2 px-2 text-white">{item.stock_name}</td>
              <td className="py-2 px-2 text-right text-yellow-400">{item.close.toFixed(2)}</td>
              <td className="py-2 px-2 text-right text-green-400">{item.volume.toLocaleString()}</td>
              <td className="py-2 px-2 text-right text-yellow-300">{item.amount.toFixed(2)}</td>
              <td className="py-2 px-2 text-rose-400">{item.patternName}</td>
              <td className="py-2 px-2 text-right text-cyan-400">{(item.confidence * 100).toFixed(0)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  const renderScanSettings = () => {
    if (!showScanOptions) return null;
    const isChips = selectedStrategy === 'chips-flow';
    const isMA = selectedStrategy === 'ma-trend';

    return (
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-4"
      >
        <h4 className="text-sm font-bold text-white">全市場掃描設定</h4>
        <div className="flex flex-wrap gap-3 items-end">
          {!isChips && (
            <div>
              <label className="text-xs text-slate-400 block mb-1">最小成交量 (張)</label>
              <input
                type="number"
                value={minVolume}
                onChange={(e) => setMinVolume(e.target.value)}
                className="w-28 bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-white text-sm outline-none focus:border-blue-500/50"
              />
            </div>
          )}
          {isMA && (
            <div>
              <label className="text-xs text-slate-400 block mb-1">掃描類型</label>
              <select
                value={scanConfig.maType || '1'}
                onChange={(e) => setScanConfig({ ...scanConfig, maType: e.target.value })}
                className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-white text-sm outline-none focus:border-blue-500/50"
              >
                <option value="1">突破年線(200MA)</option>
                <option value="2">突破季線(60MA)</option>
                <option value="3">2560戰法</option>
              </select>
            </div>
          )}
          {isChips && (
            <div>
              <label className="text-xs text-slate-400 block mb-1">掃描類型</label>
              <select
                value={scanConfig.chipsType || '1'}
                onChange={(e) => setScanConfig({ ...scanConfig, chipsType: e.target.value })}
                className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-white text-sm outline-none focus:border-blue-500/50"
              >
                <option value="1">投信動向</option>
                <option value="2">外資動向</option>
                <option value="3">集保大戶</option>
              </select>
            </div>
          )}
          <div>
            <label className="text-xs text-slate-400 block mb-1">排序方式</label>
            <select
              value={scanSort}
              onChange={(e) => setScanSort(e.target.value)}
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-white text-sm outline-none focus:border-blue-500/50"
            >
              <option value="1">策略優先</option>
              <option value="2">成交金額大→小</option>
            </select>
          </div>
          <button
            onClick={executeScan}
            disabled={scanning}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 text-white px-4 py-1.5 rounded-lg text-sm transition-colors"
          >
            {scanning ? '掃描中...' : '開始掃描'}
          </button>
        </div>
      </motion.div>
    );
  };

  return (
    <div className="flex flex-col gap-8 h-full">
      <AnimatePresence mode="wait">
        {!selectedStrategy ? (
          <motion.div 
            key="list"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            transition={{ duration: 0.2 }}
            className="flex flex-col gap-8"
          >
            <div>
              <h2 className="text-2xl font-bold text-white tracking-tight mb-1">五大策略模組</h2>
              <p className="text-slate-400 text-sm">TRINITY 的核心選股策略庫</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {strategies.map(s => (
                <div 
                  key={s.id} 
                  onClick={() => setSelectedStrategy(s.id)}
                  className="bg-slate-900 border border-slate-800 rounded-xl p-6 hover:border-blue-500/50 hover:shadow-[0_0_15px_rgba(59,130,246,0.1)] transition-all cursor-pointer group"
                >
                  <div className={`w-12 h-12 rounded-lg ${s.bg} flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}>
                    <s.icon className={s.color} size={24} />
                  </div>
                  <h3 className="text-lg font-medium text-white mb-2">{s.name}</h3>
                  <p className="text-sm text-slate-400 leading-relaxed">{s.desc}</p>
                </div>
              ))}
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="detail"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            transition={{ duration: 0.2 }}
            className="flex flex-col gap-6"
          >
            {/* Header */}
            <div className="flex items-center gap-4 border-b border-slate-800 pb-6">
              <button 
                onClick={() => {
                  setSelectedStrategy(null);
                  setStockId('');
                  setStockName('');
                  setSearchResults([]);
                  setScanResults(null);
                  setShowScanOptions(false);
                  setSelectedStockForScan(null);
                }}
                className="w-10 h-10 rounded-full bg-slate-900 border border-slate-800 hover:bg-slate-800 hover:text-white text-slate-400 flex items-center justify-center transition-colors"
              >
                <ChevronLeft size={20} />
              </button>
              <div className={`w-12 h-12 rounded-lg ${activeStrategy?.bg} flex items-center justify-center`}>
                {activeStrategy && <activeStrategy.icon className={activeStrategy.color} size={24} />}
              </div>
              <div>
                <h2 className="text-2xl font-bold text-white tracking-tight">{activeStrategy?.name}</h2>
                <p className="text-slate-400 text-sm mt-1">{activeStrategy?.desc}</p>
              </div>
            </div>

            {/* Search / Scan Input */}
            <div className="relative">
              <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 focus-within:border-blue-500/50 transition-colors">
                <Search size={18} className="text-slate-500" />
                <input
                  type="text"
                  placeholder="輸入 4 碼股號，或輸入 1 進行全市場掃描"
                  value={stockId}
                  onChange={(e) => handleSearch(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      const query = stockId.trim();
                      if (query === '1') {
                        setShowScanOptions(true);
                        setSearchResults([]);
                      } else if (query.length === 4 && /^\d{4}$/.test(query)) {
                        handleInputAction();
                      } else if (query.length >= 2) {
                        // trigger search
                        handleSearch(query);
                      }
                    }
                  }}
                  className="flex-1 bg-transparent text-white placeholder-slate-500 outline-none text-sm"
                />
                {stockName && (
                  <span className="text-xs text-slate-400 bg-slate-800 px-2 py-1 rounded">
                    {stockName}
                  </span>
                )}
                <button
                  onClick={() => {
                    const query = stockId.trim();
                    if (query === '1') {
                      setShowScanOptions(true);
                      setSearchResults([]);
                    } else if (query.length === 4 && /^\d{4}$/.test(query)) {
                      handleInputAction();
                    }
                  }}
                  className="bg-blue-600 hover:bg-blue-500 text-white px-3 py-1 rounded-lg text-xs transition-colors"
                >
                  查詢
                </button>
              </div>
              {searchResults.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-slate-900 border border-slate-800 rounded-xl overflow-hidden z-50 shadow-xl">
                  {searchResults.map((stock) => (
                    <div
                      key={stock.stock_id}
                      onClick={() => selectStock(stock)}
                      className="flex items-center justify-between px-4 py-3 hover:bg-slate-800/60 cursor-pointer transition-colors border-b border-slate-800/50 last:border-0"
                    >
                      <div className="flex items-center gap-3">
                        <span className="font-mono font-bold text-white">{stock.stock_id}</span>
                        <span className="text-slate-300">{stock.stock_name}</span>
                      </div>
                      <span className="text-xs text-slate-500">{stock.market === 'OTC' ? '櫃買' : '上市'}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Quick info hint */}
            {!showScanOptions && !scanResults && !selectedStockForScan && (
              <div className="text-xs text-slate-500 px-1">
                💡 輸入 4 碼股號查詢個股，或輸入 <kbd className="bg-slate-800 px-1.5 py-0.5 rounded text-blue-400">1</kbd> 進行全市場掃描
              </div>
            )}

            {/* Scan Settings */}
            {renderScanSettings()}

            {/* Scan Results */}
            {scanResults && !selectedStockForScan && (
              <div className="bg-slate-950/50 border border-slate-800 rounded-xl p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <ArrowUpDown size={14} className="text-blue-400" />
                    掃描結果 ({scanResults.length} 筆)
                  </h3>
                  <div className="flex gap-2">
                    <button
                      onClick={() => { setScanSort('1'); executeScan(); }}
                      className={`text-xs px-2 py-1 rounded ${scanSort === '1' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400'} transition-colors`}
                    >
                      {selectedStrategy === 'chips-flow' ? '策略優先' : selectedStrategy === 'ma-trend' ? '距目標近' : selectedStrategy === 'ai-forecast' ? 'AI分數' : '距支撐近'}
                    </button>
                    <button
                      onClick={() => { setScanSort('2'); executeScan(); }}
                      className={`text-xs px-2 py-1 rounded ${scanSort === '2' ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400'} transition-colors`}
                    >
                      成交金額
                    </button>
                  </div>
                </div>
                {renderScanTable()}
              </div>
            )}

            {/* Detail Panel */}
            {selectedStockForScan && renderPanel()}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}