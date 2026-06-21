import React, { useState, useEffect, useMemo } from 'react';
import { Zap, TrendingUp, Users, ShieldCheck, Activity, ChevronLeft, Search, ArrowUpDown } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { SRPanel } from './SRPanel';
import { MAPanel } from './MAPanel';
import { ChipsPanel } from './ChipsPanel';
import { PredictionPanel } from './PredictionPanel';
import { PatternPanel } from './PatternPanel';
import { KlineChart, type KlineOverlay } from '../KlineChart';
import { ChipsBarChart } from '../ChipsBarChart';
import {
  fetchStockSearch, fetchStockHistory, fetchStockInstitutional,
  type StockMeta, type PriceData, type InstitutionalRow,
} from '../../lib/api';
import {
  fetchSRScan, fetchMAScan, fetchChipsScan, fetchPredictionScan, fetchPatternScan,
  fetchSRAnalysis, fetchMAAnalysis,
  type SRScanItem, type MAScanItem, type ChipsScanItem, type PredictionScanItem, type PatternScanItem,
  type SRAnalysis, type MAAnalysis,
} from '../../lib/api';

const strategies = [
  { id: 'support-resistance', name: '撐壓分析',   icon: TrendingUp, desc: '析出關鍵支撐與阻力水位，並標記在 K 線圖上。', color: 'text-amber-400',  bg: 'bg-amber-400/10'  },
  { id: 'ma-trend',          name: '均線趨勢',   icon: Activity,   desc: '扣抵模型（MA-Deduction）透析多空強勢區，圖表顯示 MA25/60/200。', color: 'text-blue-400',   bg: 'bg-blue-400/10'   },
  { id: 'chips-flow',        name: '籌碼動能',   icon: Users,      desc: '三大法人連買賣天數與大戶集保分佈，柱狀圖一目了然。', color: 'text-purple-400', bg: 'bg-purple-400/10' },
  { id: 'ai-forecast',       name: 'AI 預測',   icon: Zap,        desc: 'Kronos 模型推算 T+1~T+5 偏好路徑。',                color: 'text-emerald-400',bg: 'bg-emerald-400/10'},
  { id: 'pattern-shape',     name: '型態偵測',   icon: ShieldCheck,desc: 'W 底、頸線、黃金交叉區智能辨識。',                   color: 'text-rose-400',  bg: 'bg-rose-400/10'  },
];

interface ScanConfig { maType?: string; chipsType?: string; }

// ── 根據策略產生 K 線覆蓋層 ──────────────────────────────
function buildOverlay(
  strategy: string,
  srData: SRAnalysis | null,
  maData: MAAnalysis | null,
): KlineOverlay {
  if (strategy === 'support-resistance' && srData) {
    const hLines: KlineOverlay['hLines'] = [];
    const { support, pressure } = srData;
    // 壓力：紅色虛線
    [pressure.near, pressure.mid, pressure.far].forEach((v, i) => {
      if (v) hLines.push({ value: v, color: '#f87171', dash: true,
        label: ['近壓', '中壓', '長壓'][i] });
    });
    // 支撐：綠色虛線
    [support.near, support.mid, support.far].forEach((v, i) => {
      if (v) hLines.push({ value: v, color: '#34d399', dash: true,
        label: ['近撐', '中撐', '長撐'][i] });
    });
    return { hLines };
  }
  if (strategy === 'ma-trend') {
    // 顯示 MA25/60/200 取代預設 MA
    return {
      extraMAs: [
        { period: 25,  color: '#f59e0b', label: 'MA25'  },
        { period: 60,  color: '#3b82f6', label: 'MA60'  },
        { period: 200, color: '#a855f7', label: 'MA200' },
      ],
    };
  }
  return {};
}

export function StrategiesView() {
  const [selectedStrategy, setSelectedStrategy] = useState<string | null>(null);
  const [stockId,     setStockId]     = useState('');
  const [stockName,   setStockName]   = useState('');
  const [searchResults, setSearchResults] = useState<StockMeta[]>([]);
  const [searching,   setSearching]   = useState(false);

  // 掃描
  const [showScanOptions, setShowScanOptions] = useState(false);
  const [minVolume,   setMinVolume]   = useState('500');
  const [scanning,    setScanning]    = useState(false);
  const [scanResults, setScanResults] = useState<any[] | null>(null);
  const [scanSort,    setScanSort]    = useState('1');
  const [scanConfig,  setScanConfig]  = useState<ScanConfig>({});
  const [selectedStockForScan, setSelectedStockForScan] = useState<string | null>(null);

  // 圖表資料
  const [priceData,   setPriceData]   = useState<PriceData[]>([]);
  const [instData,    setInstData]    = useState<InstitutionalRow[]>([]);
  const [shareholding,setShareholding]= useState<{ date: string; ratio: number }[]>([]);
  const [loadingChart,setLoadingChart]= useState(false);

  // 策略分析資料（用於 K 線覆蓋）
  const [srData, setSrData] = useState<SRAnalysis | null>(null);
  const [maDataResult, setMaDataResult] = useState<MAAnalysis | null>(null);

  const activeStrategy = strategies.find(s => s.id === selectedStrategy);
  const activeSid = selectedStockForScan || (stockId.length >= 4 ? stockId : '');

  // ── 載入圖表與籌碼資料 ────────────────────────────────
  useEffect(() => {
    if (!activeSid) return;
    setLoadingChart(true);
    Promise.all([
      fetchStockHistory(activeSid, 250),
      fetchStockInstitutional(activeSid),
      fetch(`/api/stock/${activeSid}/shareholding`).then(r => r.json()).catch(() => ({ data: [] })),
    ]).then(([price, inst, whale]) => {
      setPriceData(price);
      setInstData(inst);
      setShareholding(whale?.data ?? []);
    }).finally(() => setLoadingChart(false));
  }, [activeSid]);

  // ── 載入策略覆蓋資料（SR / MA）─────────────────────────
  useEffect(() => {
    if (!activeSid || !selectedStrategy) return;
    if (selectedStrategy === 'support-resistance') {
      fetchSRAnalysis(activeSid).then(setSrData).catch(() => setSrData(null));
    }
    if (selectedStrategy === 'ma-trend') {
      fetchMAAnalysis(activeSid).then(setMaDataResult).catch(() => setMaDataResult(null));
    }
  }, [activeSid, selectedStrategy]);

  const overlay = useMemo(
    () => buildOverlay(selectedStrategy ?? '', srData, maDataResult),
    [selectedStrategy, srData, maDataResult]
  );

  // ── 搜尋 ─────────────────────────────────────────────
  const handleSearch = async (query: string) => {
    setStockId(query);
    if (query.length < 2) { setSearchResults([]); return; }
    setSearching(true);
    try { setSearchResults(await fetchStockSearch(query)); }
    catch { setSearchResults([]); }
    finally { setSearching(false); }
  };

  const selectStock = (stock: StockMeta) => {
    setStockId(stock.stock_id);
    setStockName(stock.stock_name);
    setSearchResults([]);
    setScanResults(null);
    setSelectedStockForScan(stock.stock_id);
  };

  // ── 掃描 ─────────────────────────────────────────────
  const executeScan = async () => {
    if (!selectedStrategy) return;
    setScanning(true); setScanResults(null);
    const mv = parseInt(minVolume) || 500;
    try {
      let results: any[] = [];
      switch (selectedStrategy) {
        case 'support-resistance': results = await fetchSRScan(mv, scanSort); break;
        case 'ma-trend':           results = await fetchMAScan(mv, scanConfig.maType || '1', scanSort); break;
        case 'chips-flow':         results = await fetchChipsScan(scanConfig.chipsType || '1', scanSort); break;
        case 'ai-forecast':        results = await fetchPredictionScan(mv, scanSort); break;
        case 'pattern-shape':      results = await fetchPatternScan(mv, scanSort); break;
      }
      setScanResults(results);
    } catch { setScanResults([]); }
    finally { setScanning(false); }
  };

  const selectFromScan = (item: any) => {
    setStockId(item.stock_id);
    setStockName(item.stock_name || '');
    setSelectedStockForScan(item.stock_id);
    setScanResults(null);
    setShowScanOptions(false);
  };

  const resetStock = () => {
    setStockId(''); setStockName('');
    setSearchResults([]); setScanResults(null);
    setShowScanOptions(false);
    setSelectedStockForScan(null);
    setPriceData([]); setInstData([]); setShareholding([]);
    setSrData(null); setMaDataResult(null);
  };

  // ── 策略分析面板 ─────────────────────────────────────
  const renderPanel = () => {
    if (!activeSid || !selectedStrategy) return null;
    switch (selectedStrategy) {
      case 'support-resistance': return <SRPanel stockId={activeSid} />;
      case 'ma-trend':           return <MAPanel stockId={activeSid} change={0} changePercent={0} />;
      case 'chips-flow':         return <ChipsPanel stockId={activeSid} />;
      case 'ai-forecast':        return <PredictionPanel stockId={activeSid} />;
      case 'pattern-shape':      return <PatternPanel stockId={activeSid} />;
    }
  };

  // ── 掃描結果表格 ─────────────────────────────────────
  const renderScanTable = () => {
    if (scanning) return <div className="text-center py-8"><div className="inline-block w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" /><p className="text-slate-400 text-sm mt-2">掃描中...</p></div>;
    if (!scanResults?.length) return <div className="text-center py-8 text-slate-500 text-sm">無掃描結果，請調整條件後重試</div>;
    switch (selectedStrategy) {
      case 'support-resistance': return renderSRTable(scanResults as SRScanItem[]);
      case 'ma-trend':           return renderMATable(scanResults as MAScanItem[]);
      case 'chips-flow':         return renderChipsTable(scanResults as ChipsScanItem[]);
      case 'ai-forecast':        return renderPredictionTable(scanResults as PredictionScanItem[]);
      case 'pattern-shape':      return renderPatternTable(scanResults as PatternScanItem[]);
    }
  };

  const thCls = "text-left py-2 px-2 text-slate-500 text-[10px] font-semibold";
  const trCls = "border-b border-slate-800/50 hover:bg-blue-500/5 cursor-pointer transition-colors";

  const renderSRTable = (items: SRScanItem[]) => (
    <table className="w-full text-xs font-mono"><thead><tr className="border-b border-slate-800">
      {['強','代號','名稱','收盤','量(張)','額(億)','動態','距支撐'].map(h => <th key={h} className={thCls}>{h}</th>)}
    </tr></thead><tbody>
      {items.map(item => (<tr key={item.stock_id} onClick={() => selectFromScan(item)} className={trCls}>
        <td className="py-1.5 px-2 text-cyan-400">{item.score}</td>
        <td className="py-1.5 px-2 text-fuchsia-400">{item.stock_id}</td>
        <td className="py-1.5 px-2 text-white">{item.stock_name}</td>
        <td className="py-1.5 px-2 text-right text-yellow-400">{item.close.toFixed(2)}</td>
        <td className="py-1.5 px-2 text-right text-green-400">{item.volume.toLocaleString()}</td>
        <td className="py-1.5 px-2 text-right text-yellow-300">{item.amount.toFixed(2)}</td>
        <td className="py-1.5 px-2 text-blue-300 max-w-[140px] truncate">{item.tags}</td>
        <td className="py-1.5 px-2 text-right text-red-400">{item.dist > 0 ? '+' : ''}{item.dist.toFixed(2)}%</td>
      </tr>))}
    </tbody></table>
  );

  const renderMATable = (items: MAScanItem[]) => (
    <table className="w-full text-xs font-mono"><thead><tr className="border-b border-slate-800">
      {['代號','名稱','收盤','量(張)','額(億)',items[0]?.targetLabel||'目標','乖離率','曾回踩'].map(h => <th key={h} className={thCls}>{h}</th>)}
    </tr></thead><tbody>
      {items.map(item => (<tr key={item.stock_id} onClick={() => selectFromScan(item)} className={trCls}>
        <td className="py-1.5 px-2 text-fuchsia-400">{item.stock_id}</td>
        <td className="py-1.5 px-2 text-white">{item.stock_name}</td>
        <td className="py-1.5 px-2 text-right text-yellow-400">{item.close.toFixed(2)}</td>
        <td className="py-1.5 px-2 text-right text-green-400">{item.volume.toLocaleString()}</td>
        <td className="py-1.5 px-2 text-right text-yellow-300">{item.amount.toFixed(2)}</td>
        <td className="py-1.5 px-2 text-right text-white">{item.targetMA.toFixed(2)}</td>
        <td className="py-1.5 px-2 text-right text-red-400">{item.bias > 0 ? '+' : ''}{item.bias.toFixed(2)}%</td>
        <td className="py-1.5 px-2 text-right text-cyan-400">{item.touchCount}次</td>
      </tr>))}
    </tbody></table>
  );

  const renderChipsTable = (items: ChipsScanItem[]) => (
    <table className="w-full text-xs font-mono"><thead><tr className="border-b border-slate-800">
      {['代號','名稱','收盤','量(張)','額(億)',items[0]?.type||'類型','連買/賣(天)','淨額(千張)'].map(h => <th key={h} className={thCls}>{h}</th>)}
    </tr></thead><tbody>
      {items.map(item => (<tr key={item.stock_id} onClick={() => selectFromScan(item)} className={trCls}>
        <td className="py-1.5 px-2 text-fuchsia-400">{item.stock_id}</td>
        <td className="py-1.5 px-2 text-white">{item.stock_name}</td>
        <td className="py-1.5 px-2 text-right text-yellow-400">{item.close.toFixed(2)}</td>
        <td className="py-1.5 px-2 text-right text-green-400">{item.volume.toLocaleString()}</td>
        <td className="py-1.5 px-2 text-right text-yellow-300">{item.amount.toFixed(2)}</td>
        <td className="py-1.5 px-2 text-right text-purple-400">{item.type}</td>
        <td className="py-1.5 px-2 text-right text-cyan-400">{item.consecutive}</td>
        <td className="py-1.5 px-2 text-right text-green-300">{item.netTotal}</td>
      </tr>))}
    </tbody></table>
  );

  const renderPredictionTable = (items: PredictionScanItem[]) => (
    <table className="w-full text-xs font-mono"><thead><tr className="border-b border-slate-800">
      {['代號','名稱','收盤','量(張)','額(億)','AI方向','AI分數','預估(T+1)'].map(h => <th key={h} className={thCls}>{h}</th>)}
    </tr></thead><tbody>
      {items.map(item => (<tr key={item.stock_id} onClick={() => selectFromScan(item)} className={trCls}>
        <td className="py-1.5 px-2 text-fuchsia-400">{item.stock_id}</td>
        <td className="py-1.5 px-2 text-white">{item.stock_name}</td>
        <td className="py-1.5 px-2 text-right text-yellow-400">{item.close.toFixed(2)}</td>
        <td className="py-1.5 px-2 text-right text-green-400">{item.volume.toLocaleString()}</td>
        <td className="py-1.5 px-2 text-right text-yellow-300">{item.amount.toFixed(2)}</td>
        <td className="py-1.5 px-2 text-center text-emerald-400">{item.aiStrength}</td>
        <td className="py-1.5 px-2 text-right text-white">{item.aiScore.toFixed(2)}</td>
        <td className="py-1.5 px-2 text-right text-cyan-400">{item.predPrice.toFixed(2)} ({item.predPct > 0 ? '+' : ''}{item.predPct.toFixed(2)}%)</td>
      </tr>))}
    </tbody></table>
  );

  const renderPatternTable = (items: PatternScanItem[]) => (
    <table className="w-full text-xs font-mono"><thead><tr className="border-b border-slate-800">
      {['代號','名稱','收盤','量(張)','額(億)','型態','信心度'].map(h => <th key={h} className={thCls}>{h}</th>)}
    </tr></thead><tbody>
      {items.map(item => (<tr key={item.stock_id} onClick={() => selectFromScan(item)} className={trCls}>
        <td className="py-1.5 px-2 text-fuchsia-400">{item.stock_id}</td>
        <td className="py-1.5 px-2 text-white">{item.stock_name}</td>
        <td className="py-1.5 px-2 text-right text-yellow-400">{item.close.toFixed(2)}</td>
        <td className="py-1.5 px-2 text-right text-green-400">{item.volume.toLocaleString()}</td>
        <td className="py-1.5 px-2 text-right text-yellow-300">{item.amount.toFixed(2)}</td>
        <td className="py-1.5 px-2 text-rose-400">{item.patternName}</td>
        <td className="py-1.5 px-2 text-right text-cyan-400">{(item.confidence * 100).toFixed(0)}%</td>
      </tr>))}
    </tbody></table>
  );

  // ── 掃描設定面板 ─────────────────────────────────────
  const renderScanSettings = () => {
    if (!showScanOptions) return null;
    const isChips = selectedStrategy === 'chips-flow';
    const isMA    = selectedStrategy === 'ma-trend';
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-4">
        <h4 className="text-sm font-bold text-white">全市場掃描設定</h4>
        <div className="flex flex-wrap gap-3 items-end">
          {!isChips && (
            <div>
              <label className="text-xs text-slate-400 block mb-1">最小成交量 (張)</label>
              <input type="number" value={minVolume} onChange={e => setMinVolume(e.target.value)}
                className="w-28 bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-white text-sm outline-none focus:border-blue-500/50" />
            </div>
          )}
          {isMA && (
            <div>
              <label className="text-xs text-slate-400 block mb-1">掃描類型</label>
              <select value={scanConfig.maType||'1'} onChange={e => setScanConfig({...scanConfig, maType: e.target.value})}
                className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-white text-sm outline-none">
                <option value="1">突破年線 (200MA)</option>
                <option value="2">突破季線 (60MA)</option>
                <option value="3">2560 戰法</option>
              </select>
            </div>
          )}
          {isChips && (
            <div>
              <label className="text-xs text-slate-400 block mb-1">掃描類型</label>
              <select value={scanConfig.chipsType||'1'} onChange={e => setScanConfig({...scanConfig, chipsType: e.target.value})}
                className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-white text-sm outline-none">
                <option value="1">投信動向</option>
                <option value="2">外資動向</option>
                <option value="3">集保大戶</option>
              </select>
            </div>
          )}
          <div>
            <label className="text-xs text-slate-400 block mb-1">排序方式</label>
            <select value={scanSort} onChange={e => setScanSort(e.target.value)}
              className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-white text-sm outline-none">
              <option value="1">策略優先</option>
              <option value="2">成交金額大→小</option>
            </select>
          </div>
          <button onClick={executeScan} disabled={scanning}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 text-white px-4 py-1.5 rounded-lg text-sm transition-colors">
            {scanning ? '掃描中...' : '開始掃描'}
          </button>
        </div>
      </div>
    );
  };

  // ─────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-6">
      <AnimatePresence mode="wait">
        {!selectedStrategy ? (
          /* ── 策略選單首頁 ── */
          <motion.div key="list" initial={{opacity:0,x:-20}} animate={{opacity:1,x:0}} exit={{opacity:0,x:-20}} transition={{duration:0.2}} className="flex flex-col gap-8">
            <div>
              <h2 className="text-2xl font-bold text-white tracking-tight mb-1">五大策略模組</h2>
              <p className="text-slate-400 text-sm">TRINITY 的核心選股策略庫</p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {strategies.map(s => (
                <div key={s.id} onClick={() => setSelectedStrategy(s.id)}
                  className="bg-slate-900 border border-slate-800 rounded-xl p-6 hover:border-blue-500/50 hover:shadow-[0_0_15px_rgba(59,130,246,0.1)] transition-all cursor-pointer group">
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
          /* ── 策略詳細分頁 ── */
          <motion.div key="detail" initial={{opacity:0,x:20}} animate={{opacity:1,x:0}} exit={{opacity:0,x:20}} transition={{duration:0.2}} className="flex flex-col gap-5">

            {/* Header */}
            <div className="flex items-center gap-4 border-b border-slate-800 pb-5">
              <button onClick={() => { setSelectedStrategy(null); resetStock(); }}
                className="w-10 h-10 rounded-full bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-400 hover:text-white flex items-center justify-center transition-colors">
                <ChevronLeft size={20} />
              </button>
              <div className={`w-12 h-12 rounded-lg ${activeStrategy?.bg} flex items-center justify-center`}>
                {activeStrategy && <activeStrategy.icon className={activeStrategy.color} size={24} />}
              </div>
              <div className="flex-1 min-w-0">
                <h2 className="text-xl font-bold text-white tracking-tight">{activeStrategy?.name}</h2>
                {activeSid && (
                  <p className="text-slate-400 text-sm mt-0.5">
                    {activeSid} {stockName && `· ${stockName}`}
                  </p>
                )}
              </div>
              {/* 策略切換 Tab（小型） */}
              <div className="hidden md:flex gap-1">
                {strategies.map(s => (
                  <button key={s.id} onClick={() => { setSelectedStrategy(s.id); setSrData(null); setMaDataResult(null); }}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                      s.id === selectedStrategy ? `${s.bg} ${s.color}` : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800'
                    }`}>
                    {s.name}
                  </button>
                ))}
              </div>
            </div>

            {/* 搜尋框 */}
            <div className="relative">
              <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 rounded-xl px-4 py-3 focus-within:border-blue-500/50 transition-colors">
                <Search size={18} className="text-slate-500 shrink-0" />
                <input
                  type="text"
                  placeholder="輸入 4 碼股號，或輸入 1 進行全市場掃描"
                  value={stockId}
                  onChange={e => handleSearch(e.target.value)}
                  onKeyDown={e => {
                    if (e.key !== 'Enter') return;
                    const q = stockId.trim();
                    if (q === '1') { setShowScanOptions(true); setSearchResults([]); }
                    else if (q.length >= 4) handleSearch(q);
                  }}
                  className="flex-1 bg-transparent text-white placeholder-slate-500 outline-none text-sm"
                />
                {stockName && <span className="text-xs text-slate-400 bg-slate-800 px-2 py-1 rounded shrink-0">{stockName}</span>}
                <button
                  onClick={() => {
                    const q = stockId.trim();
                    if (q === '1') { setShowScanOptions(true); setSearchResults([]); }
                    else if (q.length >= 2) handleSearch(q);
                  }}
                  className="bg-blue-600 hover:bg-blue-500 text-white px-3 py-1 rounded-lg text-xs transition-colors shrink-0"
                >
                  查詢
                </button>
              </div>
              {searchResults.length > 0 && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-slate-900 border border-slate-800 rounded-xl overflow-hidden z-50 shadow-xl">
                  {searchResults.map(stock => (
                    <div key={stock.stock_id} onClick={() => selectStock(stock)}
                      className="flex items-center justify-between px-4 py-3 hover:bg-slate-800/60 cursor-pointer transition-colors border-b border-slate-800/50 last:border-0">
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

            {!showScanOptions && !scanResults && !activeSid && (
              <div className="text-xs text-slate-500 px-1">
                💡 輸入 4 碼股號查詢個股，或輸入 <kbd className="bg-slate-800 px-1.5 py-0.5 rounded text-blue-400">1</kbd> 全市場掃描
              </div>
            )}

            {renderScanSettings()}

            {/* 掃描結果 */}
            {scanResults && !selectedStockForScan && (
              <div className="bg-slate-950/50 border border-slate-800 rounded-xl p-4 overflow-x-auto">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <ArrowUpDown size={14} className="text-blue-400" />
                    掃描結果 ({scanResults.length} 筆)
                  </h3>
                  <div className="flex gap-2">
                    {['1','2'].map(v => (
                      <button key={v} onClick={() => { setScanSort(v); executeScan(); }}
                        className={`text-xs px-2 py-1 rounded transition-colors ${scanSort===v ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400'}`}>
                        {v==='1' ? '策略優先' : '成交金額'}
                      </button>
                    ))}
                  </div>
                </div>
                {renderScanTable()}
              </div>
            )}

            {/* ── 股票詳細分析區 ── */}
            {activeSid && (
              <div className="flex flex-col gap-5">
                {/* K 線圖（帶策略覆蓋） */}
                <div>
                  {loadingChart ? (
                    <div className="bg-slate-900 border border-slate-800 rounded-xl flex items-center justify-center h-[420px]">
                      <div className="flex flex-col items-center gap-2">
                        <div className="w-6 h-6 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                        <span className="text-slate-400 text-xs">載入 K 線資料...</span>
                      </div>
                    </div>
                  ) : priceData.length > 0 ? (
                    <KlineChart data={priceData} overlay={overlay} />
                  ) : (
                    <div className="bg-slate-900 border border-slate-800 rounded-xl flex items-center justify-center h-[200px] text-slate-500 text-sm">
                      無歷史價格資料，請先執行「手動更新」
                    </div>
                  )}
                </div>

                {/* 策略分析面板 */}
                {renderPanel()}

                {/* 法人 + 集保柱狀圖 */}
                {(instData.length > 0 || shareholding.length > 0) && (
                  <ChipsBarChart
                    chipHistory={instData.map(r => ({ date: r.date, foreign: r.foreign_net, trust: r.trust_net }))}
                    shareholding={shareholding}
                  />
                )}

                {/* 策略行動切換（手機版，header 的切換 tab 只在 md+ 顯示） */}
                <div className="flex md:hidden gap-1 flex-wrap">
                  {strategies.map(s => (
                    <button key={s.id} onClick={() => { setSelectedStrategy(s.id); setSrData(null); setMaDataResult(null); }}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                        s.id === selectedStrategy ? `${s.bg} ${s.color}` : 'text-slate-500 bg-slate-800'
                      }`}>
                      {s.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
