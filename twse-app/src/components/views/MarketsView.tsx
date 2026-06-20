import { useState, useEffect, useCallback } from 'react';
import { Search, RotateCw, CheckCircle, Brain, Loader2, Calendar, Clock, Database, AlertTriangle, RefreshCw } from "lucide-react";
import { fetchStockQuote, fetchStockHistory, fetchFinMindQuote, fetchFinMindHistory, fetchFinMindRealtime, type StockQuote, type PriceData } from '../../lib/api';
import { formatTaipeiTime } from '../../lib/utils';
import { KlineChart } from '../KlineChart';
import { ChipChart } from '../ChipChart';
import { ErrorAlert } from '../ui/ErrorAlert';
import { LoadingSpinner, ChartSkeleton } from '../ui/LoadingSpinner';
import { useRetry } from '../../hooks/useRetry';

type ChipTab = 'institutional' | 'whale' | 'custody';

export function MarketsView() {
  const [ticker, setTicker] = useState('2330');
  const [searchQuery, setSearchQuery] = useState('2330');

  // Database Date states
  const [latestDate, setLatestDate] = useState<string | null>(null);
  const [isDateLoading, setIsDateLoading] = useState(true);
  const [dateError, setDateError] = useState<string | null>(null);

  // 即時數據狀態
  const [realtimeEnabled, setRealtimeEnabled] = useState(false);
  const [realtimeData, setRealtimeData] = useState<{ price: number; prev_close: number; change: number; changePercent: number; volume: number; time: string } | null>(null);
  const [realtimeError, setRealtimeError] = useState<string | null>(null);
  const [realtimeCountdown, setRealtimeCountdown] = useState(5);

  // 個股數據狀態
  const [stockData, setStockData] = useState<StockQuote | null>(null);
  const [stockLoading, setStockLoading] = useState(false);
  const [stockError, setStockError] = useState<string | null>(null);

  // K 線圖數據
  const [klineData, setKlineData] = useState<PriceData[]>([]);
  const [klineLoading, setKlineLoading] = useState(false);
  const [klineError, setKlineError] = useState<string | null>(null);

  // 法人/大戶狀態
  const [chipTab, setChipTab] = useState<ChipTab>('institutional');
  const [chipData, setChipData] = useState<any>(null);
  const [chipLoading, setChipLoading] = useState(false);
  const [chipError, setChipError] = useState<string | null>(null);

  // ── 搜尋 ────────────────────────────────────────────────
  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (ticker.trim()) setSearchQuery(ticker.trim());
  };

  // ── 日期狀態（含重試）────────────────────────────────────
  const fetchLatestDate = useCallback(async () => {
    try {
      const res = await fetch('/api/update/status');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      if (json.success && json.latestDate) {
        setLatestDate(json.latestDate);
        setDateError(null);
      } else {
        setDateError('無法取得資料庫日期');
      }
    } catch (e: any) {
      setDateError(e.message || '無法連接伺服器');
    } finally {
      setIsDateLoading(false);
    }
  }, []);

  const { execute: fetchLatestDateWithRetry } = useRetry(fetchLatestDate, {
    maxRetries: 3,
    baseDelay: 2000,
  });

  // ── 即時數據（含錯誤處理）────────────────────────────────
  const fetchRealtimeStock = useCallback(async () => {
    setRealtimeError(null);

    try {
      const finmindData = await fetchFinMindRealtime(searchQuery);
      if (finmindData) {
        setRealtimeData({
          price: finmindData.price,
          prev_close: finmindData.prev_close,
          change: finmindData.change,
          changePercent: finmindData.changePercent || 0,
          volume: finmindData.volume,
          time: finmindData.time
        });
        return;
      }
    } catch (e: any) {
      console.warn('[Realtime] FinMind failed:', e.message);
    }

    try {
      const res = await fetch(`/api/stock/${searchQuery}/realtime`);
      if (!res.ok) {
        throw new Error(`伺服器回應錯誤: ${res.status}`);
      }
      const json = await res.json();
      if (json.success && json.data) {
        setRealtimeData({
          price: json.data.price,
          prev_close: json.data.prev_close,
          change: json.data.change,
          changePercent: json.data.changePercent || json.data.change_percent,
          volume: json.data.volume,
          time: json.data.time
        });
      } else {
        setRealtimeError(json.error || '無法取得即時數據（可能為非交易時間）');
        setRealtimeData(null);
      }
    } catch (e: any) {
      setRealtimeError(e.message || '網路連線失敗，請稍後再試');
      setRealtimeData(null);
    }
  }, [searchQuery]);

  const {
    execute: fetchRealtimeWithRetry,
    isRetrying: isRealtimeRetrying,
    retry: retryRealtime
  } = useRetry(fetchRealtimeStock, {
    maxRetries: 3,
    baseDelay: 3000,
    shouldRetry: (error) => {
      if (error.message.includes('非交易時間')) return false;
      return true;
    },
  });

  // ── 個股數據（含重試）────────────────────────────────────
  const fetchStockData = useCallback(async (stockId: string) => {
    if (!stockId.trim()) return;

    setStockLoading(true);
    setStockError(null);

    try {
      const finmindData = await fetchFinMindQuote(stockId.trim());
      if (finmindData) {
        const localData = await fetchStockQuote(stockId.trim());
        setStockData(localData
          ? { ...localData, ...finmindData, name: localData.name, market: localData.market, industry: localData.industry }
          : finmindData
        );
        return;
      }

      const data = await fetchStockQuote(stockId.trim());
      if (data) {
        setStockData(data);
      } else {
        setStockData(null);
        setStockError('查無此個股資料，請確認股票代號是否正確');
      }
    } catch (e: any) {
      try {
        const data = await fetchStockQuote(stockId.trim());
        if (data) {
          setStockData(data);
        } else {
          setStockData(null);
          setStockError('載入個股資料失敗，請稍後再試');
        }
      } catch (fallbackError: any) {
        setStockData(null);
        setStockError(fallbackError.message || '載入個股資料失敗');
      }
    } finally {
      setStockLoading(false);
    }
  }, []);

  const {
    execute: fetchStockWithRetry,
    retry: retryStock
  } = useRetry(() => fetchStockData(searchQuery), {
    maxRetries: 3,
    baseDelay: 1500,
    shouldRetry: (error) => {
      if (error.message.includes('查無此個股')) return false;
      return true;
    },
  });

  // ── K 線歷史（含重試）────────────────────────────────────
  const fetchKlineData = useCallback(async (stockId: string) => {
    if (!stockId.trim()) return;

    setKlineLoading(true);
    setKlineError(null);

    try {
      let data = await fetchFinMindHistory(stockId.trim(), 4380);
      if (data.length > 0) {
        setKlineData(data);
        return;
      }

      data = await fetchStockHistory(stockId.trim(), 4380);
      setKlineData(data);
    } catch (e: any) {
      try {
        const data = await fetchStockHistory(stockId.trim(), 1095);
        setKlineData(data);
      } catch (fallbackError: any) {
        setKlineError(fallbackError.message || '載入 K 線資料失敗');
        setKlineData([]);
      }
    } finally {
      setKlineLoading(false);
    }
  }, []);

  const {
    execute: fetchKlineWithRetry,
    retry: retryKline
  } = useRetry(() => fetchKlineData(searchQuery), {
    maxRetries: 2,
    baseDelay: 2000,
  });

  // ── 法人/大戶數據（含錯誤處理）──────────────────────────
  const fetchChipData = useCallback(async (stockId: string, tab: ChipTab) => {
    if (!stockId.trim()) return;

    setChipLoading(true);
    setChipError(null);

    try {
      if (tab === 'institutional') {
        const res = await fetch(`/api/stock/${stockId}/institutional`);
        if (!res.ok) throw new Error(`伺服器回應錯誤: ${res.status}`);
        const json = await res.json();
        const data = json.success ? (Array.isArray(json.data) ? json.data : [json.data]) : [];
        setChipData(data);
      } else {
        const res = await fetch(`/api/stock/${stockId}/chips-analysis`);
        if (!res.ok) throw new Error(`伺服器回應錯誤: ${res.status}`);
        const json = await res.json();
        if (json.success && json.data && json.data.chipHistory) {
          setChipData(json.data.chipHistory);
        } else {
          setChipData([]);
          setChipError('無法取得法人/大戶數據');
        }
      }
    } catch (e: any) {
      setChipError(e.message || '載入法人數據失敗');
      setChipData([]);
    } finally {
      setChipLoading(false);
    }
  }, []);

  const {
    execute: fetchChipWithRetry,
    retry: retryChip
  } = useRetry(() => fetchChipData(searchQuery, chipTab), {
    maxRetries: 2,
    baseDelay: 1500,
  });

  // ── 生命週期 ────────────────────────────────────────────
  useEffect(() => {
    fetchLatestDateWithRetry();
    const timer = setInterval(fetchLatestDateWithRetry, 30000);
    return () => clearInterval(timer);
  }, [fetchLatestDateWithRetry]);

  useEffect(() => {
    if (searchQuery) {
      fetchStockWithRetry();
      fetchKlineWithRetry();
      fetchChipWithRetry();
    }
  }, [searchQuery, fetchStockWithRetry, fetchKlineWithRetry, fetchChipWithRetry]);

  useEffect(() => {
    if (searchQuery) {
      fetchChipWithRetry();
    }
  }, [chipTab, searchQuery, fetchChipWithRetry]);

  useEffect(() => {
    if (!realtimeEnabled) {
      setRealtimeCountdown(5);
      setRealtimeError(null);
      return;
    }
    fetchRealtimeWithRetry();
    const timer = setInterval(() => {
      setRealtimeCountdown(prev => {
        if (prev <= 1) {
          fetchRealtimeWithRetry();
          return 5;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [realtimeEnabled, searchQuery, fetchRealtimeWithRetry]);

  // ── 計算顯示值 ──────────────────────────────────────────
  const useRealtime = realtimeData?.price != null && realtimeData.price > 0;
  const displayPrice = useRealtime ? realtimeData!.price : (stockData?.close ?? 0);
  const displayChange = useRealtime ? (realtimeData!.change ?? stockData?.change ?? 0) : (stockData?.change ?? 0);
  const rawChangePercent = useRealtime ? (realtimeData!.changePercent ?? stockData?.changePercent ?? 0) : (stockData?.changePercent ?? 0);
  const displayChangePercent = isNaN(rawChangePercent) ? 0 : rawChangePercent;
  const isUp = displayChange >= 0;

  const isLoading = stockLoading || klineLoading || chipLoading;

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSearch} className="flex items-center gap-3 bg-slate-950 border border-white/[0.06] rounded-2xl p-4">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" size={16} />
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="輸入股票代號或名稱…"
            className="w-full bg-white/[0.04] border border-white/[0.08] rounded-xl pl-10 pr-4 py-2.5 text-sm text-white outline-none focus:border-cyan-500/40 transition-all font-mono placeholder:text-slate-600"
          />
        </div>
        <button
          type="submit"
          disabled={isLoading}
          className="px-5 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-500 text-white text-sm font-semibold rounded-xl hover:from-cyan-400 hover:to-blue-400 transition-all shadow-lg shadow-cyan-500/10 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <span className="flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              載入中
            </span>
          ) : '搜尋'}
        </button>
        <a
          href="#ai-analysis"
          className="px-4 py-2.5 bg-purple-600 hover:bg-purple-500 text-white text-sm font-semibold rounded-xl transition-all flex items-center gap-2"
        >
          <Brain size={14} /> AI 分析
        </a>
        <div className="flex items-center gap-2 px-3 text-[11px] text-slate-500">
          {isDateLoading ? (
            <RotateCw className="w-3 h-3 animate-spin" />
          ) : dateError ? (
            <span className="text-red-400/70 flex items-center gap-1" title={dateError}>
              <AlertTriangle size={12} />
              <span>DB 錯誤</span>
            </span>
          ) : latestDate ? (
            <>
              <CheckCircle size={12} className="text-emerald-500" />
              <span className="text-emerald-400/70">DB: {latestDate}</span>
            </>
          ) : (
            <span className="text-amber-400/70">DB 未知</span>
          )}
        </div>
      </form>

      {stockError && (
        <ErrorAlert
          type="error"
          title="載入股票資料失敗"
          message={stockError}
          onRetry={retryStock}
          showRetry={true}
        />
      )}

      {klineError && (
        <ErrorAlert
          type="warning"
          title="載入 K 線資料失敗"
          message={klineError}
          onRetry={retryKline}
          showRetry={true}
        />
      )}

      {realtimeError && (
        <ErrorAlert
          type="info"
          title="即時數據"
          message={realtimeError}
          onRetry={retryRealtime}
          showRetry={!realtimeError.includes('非交易時間')}
          autoDismiss={realtimeError.includes('非交易時間') ? 5000 : undefined}
        />
      )}

      {stockData && !stockError && (
        <div className="flex flex-wrap items-center gap-4 bg-slate-950 border border-white/[0.06] rounded-2xl px-5 py-3">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold text-white">{stockData.name}</h2>
            <span className="text-xs font-mono text-slate-500">{stockData.stock_id}</span>
            <span className="text-[9px] bg-emerald-500/15 text-emerald-400 px-2 py-0.5 rounded-full font-bold flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />FinMind
            </span>
          </div>
          <div className="flex items-center gap-6 text-xs text-slate-500">
            <span className="flex items-center gap-1"><Calendar size={11} /> {stockData.date}</span>
            <span className="flex items-center gap-1"><Clock size={11} /> {formatTaipeiTime(new Date())}</span>
            <span className="flex items-center gap-1">
              <Database size={11} /> {useRealtime ? '即時數據' : '收盤價'}
              {isRealtimeRetrying && <Loader2 size={10} className="animate-spin ml-1" />}
            </span>
          </div>
          <div className="flex items-baseline gap-3 ml-auto">
            <span className="text-3xl font-black font-mono text-white">{displayPrice.toFixed(2)}</span>
            <span className={`text-sm font-bold font-mono ${isUp ? 'text-rose-400' : 'text-emerald-400'}`}>
              {isUp ? '＋' : ''}{displayChangePercent.toFixed(2)}% ({isUp ? '＋' : ''}{displayChange.toFixed(2)})
            </span>
          </div>
        </div>
      )}

      <div className="bg-slate-950 border border-white/[0.06] rounded-2xl p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[10px] text-slate-500 mr-1">K線</span>
          {(['daily', 'weekly', 'monthly'] as const).map(kp => (
            <button key={kp} className="px-3 py-1 text-[11px] rounded-lg bg-white/[0.04] text-slate-400 border border-white/[0.08] hover:bg-white/[0.08]">
              {kp === 'daily' ? '日' : kp === 'weekly' ? '週' : '月'}
            </button>
          ))}
          <div className="w-px h-6 bg-white/[0.06] mx-1" />
          <span className="text-[10px] text-slate-500 mr-1">MA</span>
          {[5, 25, 60, 200].map(p => (
            <button key={p} className="px-3 py-1 text-[11px] rounded-lg bg-white/[0.04] text-slate-400 border border-white/[0.08] hover:bg-white/[0.08]">{p}</button>
          ))}
          <div className="w-px h-6 bg-white/[0.06] mx-1" />
          <span className="text-[10px] text-slate-500 mr-1">支撐壓力</span>
          {([['near', '前高/前低'], ['short', '短期'], ['long', '長期'], ['poc', 'POC'], ['vsbc', 'VSBC']] as const).map(([key, label]) => (
            <button key={key} className="px-3 py-1 text-[11px] rounded-lg bg-white/[0.04] text-slate-400 border border-white/[0.08] hover:bg-white/[0.08]">{label}</button>
          ))}
        </div>
      </div>

      <div>
        <div className="flex items-center gap-2 mb-3">
          <BarChart3 className="text-cyan-400" size={16} />
          <h3 className="text-sm font-bold text-white">技術圖表</h3>
          {klineData.length > 0 && (
            <span className="text-[10px] text-slate-600 font-mono">
              {stockData?.name} ({stockData?.stock_id}) · {klineData.length} 筆
            </span>
          )}
        </div>

        {klineLoading ? (
          <ChartSkeleton height={300} />
        ) : klineData.length > 0 ? (
          <div className="bg-slate-950 border border-white/[0.06] rounded-2xl overflow-hidden">
            <KlineChart data={klineData} />
          </div>
        ) : !klineError ? (
          <div className="bg-slate-950 border border-white/[0.06] rounded-2xl p-16 text-center text-slate-600 text-sm">
            尚無 K 線資料
            <button
              onClick={retryKline}
              className="block mx-auto mt-3 text-cyan-400 hover:text-cyan-300 text-xs"
            >
              重新載入
            </button>
          </div>
        ) : null}
      </div>

      <div>
        <div className="flex items-center gap-2 mb-3">
          <span className="w-1 h-5 bg-gradient-to-b from-cyan-400 to-blue-500 rounded-full" />
          <h3 className="text-sm font-bold text-white">法人 / 大戶 / 集保</h3>
        </div>

        <div className="flex gap-2 mb-3">
          {([['institutional', '法人投信/外資'], ['whale', '千張大戶/集保人數']] as const).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setChipTab(key)}
              className={`px-4 py-2 text-xs font-medium rounded-xl transition-all ${
                chipTab === key
                  ? 'bg-cyan-600/20 text-cyan-400 border border-cyan-500/30'
                  : 'bg-white/[0.04] text-slate-400 border border-white/[0.08]'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="bg-slate-950 border border-white/[0.06] rounded-2xl p-4">
          {chipLoading ? (
            <LoadingSpinner size="sm" text="載入法人數據中..." className="py-8" />
          ) : chipError ? (
            <div className="text-center py-8">
              <p className="text-red-400 text-xs mb-3">{chipError}</p>
              <button
                onClick={retryChip}
                className="text-cyan-400 hover:text-cyan-300 text-xs flex items-center gap-1 mx-auto"
              >
                <RefreshCw size={12} />
                重新載入
              </button>
            </div>
          ) : chipData && chipData.length > 0 ? (
            <div className="space-y-4">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[10px] text-slate-500">
                    {chipTab === 'institutional' ? '外資買賣超（張）' : '千戶大戶占比（%）'}
                  </span>
                </div>
                <ChipChart data={chipData} tab={chipTab} />
              </div>
              <div className="grid grid-cols-4 gap-3 text-center">
                {chipTab === 'institutional' && chipData[0] && (
                  <>
                    <div className="bg-slate-900 rounded-lg p-2">
                      <div className="text-[10px] text-slate-500">外資</div>
                      <div className={`text-sm font-bold ${(chipData[0].foreign || 0) >= 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                        {(chipData[0].foreign || 0) > 0 ? '+' : ''}{(chipData[0].foreign || 0).toLocaleString()}
                      </div>
                    </div>
                    <div className="bg-slate-900 rounded-lg p-2">
                      <div className="text-[10px] text-slate-500">投信</div>
                      <div className={`text-sm font-bold ${(chipData[0].trust || 0) >= 0 ? 'text-rose-400' : 'text-emerald-400'}`}>
                        {(chipData[0].trust || 0) > 0 ? '+' : ''}{(chipData[0].trust || 0).toLocaleString()}
                      </div>
                    </div>
                  </>
                )}
                {chipTab === 'whale' && chipData[0] && (
                  <>
                    <div className="bg-slate-900 rounded-lg p-2">
                      <div className="text-[10px] text-slate-500">千張大戶比例</div>
                      <div className="text-sm font-bold text-rose-400">
                        {chipData[0].whaleRatio != null ? `${chipData[0].whaleRatio.toFixed(2)}%` : 'N/A'}
                      </div>
                    </div>
                    <div className="bg-slate-900 rounded-lg p-2">
                      <div className="text-[10px] text-slate-500">集保人數</div>
                      <div className="text-sm font-bold text-white">
                        {chipData[0].whaleShares != null ? Math.floor(chipData[0].whaleShares / 1000).toLocaleString() : 'N/A'}
                      </div>
                    </div>
                    <div className="bg-slate-900 rounded-lg p-2">
                      <div className="text-[10px] text-slate-500">集保張數</div>
                      <div className="text-sm font-bold text-cyan-400">
                        {chipData[0].whaleShares != null ? (chipData[0].whaleShares / 1000).toLocaleString() : 'N/A'}
                      </div>
                    </div>
                    <div className="bg-slate-900 rounded-lg p-2">
                      <div className="text-[10px] text-slate-500">總發行張數</div>
                      <div className="text-sm font-bold text-slate-400">
                        {chipData[0].totalShares != null ? (chipData[0].totalShares / 1000).toLocaleString() : 'N/A'}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-slate-500 text-xs">
              暫無資料
              <button
                onClick={retryChip}
                className="block mx-auto mt-2 text-cyan-400 hover:text-cyan-300 text-xs"
              >
                重新載入
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="text-center text-[10px] text-slate-700 font-mono py-2">
        {formatTaipeiTime(new Date())}
      </div>
    </div>
  );
}
