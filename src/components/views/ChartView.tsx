import React, { useState, useEffect, useMemo } from 'react';
import { supabase } from '../../lib/supabase';
import {
  CandlestickChart,
  Settings2,
  ChevronDown,
  TrendingUp,
  BarChart3,
  Users,
  Building2,
  Activity
} from 'lucide-react';

// Types
interface PriceData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface IndicatorData {
  date: string;
  k: number;
  d: number;
}

interface ChipData {
  date: string;
  foreign: number;
  trust: number;
  dealer: number;
}

interface WhaleData {
  date: string;
  ratio: number;
  count: number;
  shares: number;
}

interface MA {
  period: number;
  values: { date: string; value: number }[];
  color: string;
}

// Simple candlestick SVG component
const Candlestick: React.FC<{
  x: number;
  open: number;
  high: number;
  low: number;
  close: number;
  width: number;
  scale: (price: number) => number;
}> = ({ x, open, high, low, close, width, scale }) => {
  const isUp = close >= open;
  const color = isUp ? '#ef4444' : '#22c55e';
  const bodyTop = scale(Math.max(open, close));
  const bodyBottom = scale(Math.min(open, close));
  const wickTop = scale(high);
  const wickBottom = scale(low);

  return (
    <g>
      {/* Wick */}
      <line
        x1={x + width / 2}
        y1={wickTop}
        x2={x + width / 2}
        y2={wickBottom}
        stroke={color}
        strokeWidth={1}
      />
      {/* Body */}
      <rect
        x={x}
        y={bodyTop}
        width={width}
        height={Math.max(bodyBottom - bodyTop, 1)}
        fill={color}
      />
    </g>
  );
};

// Volume bar component
const VolumeBar: React.FC<{
  x: number;
  volume: number;
  close: number;
  open: number;
  width: number;
  scaleY: (vol: number) => number;
}> = ({ x, volume, close, open, width, scaleY }) => {
  const isUp = close >= open;
  const height = scaleY(volume);
  return (
    <rect
      x={x}
      y={300 - height}
      width={width}
      height={height}
      fill={isUp ? '#ef4444' : '#22c55e'}
      opacity={0.7}
    />
  );
};

export function ChartView() {
  const [stockId, setStockId] = useState('2330');
  const [searchQuery, setSearchQuery] = useState('2330');
  const [priceData, setPriceData] = useState<PriceData[]>([]);
  const [indicatorData, setIndicatorData] = useState<IndicatorData[]>([]);
  const [chipData, setChipData] = useState<ChipData[]>([]);
  const [whaleData, setWhaleData] = useState<WhaleData[]>([]);
  const [loading, setLoading] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [chartType, setChartType] = useState<'candlestick' | 'line'>('candlestick');
  const [timeRange, setTimeRange] = useState('120'); // days

  // MA periods to display
  const maPeriods = [20, 60, 200];
  const maColors = ['#f59e0b', '#3b82f6', '#a855f7'];

  // Calculate MAs
  const maData = useMemo(() => {
    return maPeriods.map((period, idx) => {
      const values: { date: string; value: number }[] = [];
      for (let i = period - 1; i < priceData.length; i++) {
        const sum = priceData.slice(i - period + 1, i + 1).reduce((acc, d) => acc + d.close, 0);
        values.push({
          date: priceData[i].date,
          value: sum / period
        });
      }
      return { period, values, color: maColors[idx] };
    });
  }, [priceData]);

  // Calculate KD indicators
  const calculateKD = (data: PriceData[], period: 9): IndicatorData[] => {
    const result: IndicatorData[] = [];
    for (let i = period - 1; i < data.length; i++) {
      const slice = data.slice(i - period + 1, i + 1);
      const high = Math.max(...slice.map(d => d.high));
      const low = Math.min(...slice.map(d => d.low));
      const rsv = high !== low ? ((data[i].close - low) / (high - low)) * 100 : 50;

      if (i === period - 1) {
        result.push({ date: data[i].date, k: 50, d: 50 });
      } else {
        const prevK = result[result.length - 1].k;
        const prevD = result[result.length - 1].d;
        const k = (2 / 3) * prevK + (1 / 3) * rsv;
        const d = (2 / 3) * prevD + (1 / 3) * k;
        result.push({ date: data[i].date, k, d });
      }
    }
    return result;
  };

  // Load data
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        // Load price data from local API
        const priceRes = await fetch(`/api/stock/${stockId}/history?days=${timeRange}`);
        const priceJson = await priceRes.json();
        if (priceJson.success && priceJson.data.length > 0) {
          setPriceData(priceJson.data);
          setIndicatorData(calculateKD(priceJson.data, 9));
        }

        // Try to load chip data from Supabase
        if (supabase) {
          const { data: instData } = await supabase
            .from('stock_institutional')
            .select('*')
            .eq('stock_id', stockId)
            .order('date', { ascending: false })
            .limit(parseInt(timeRange));

          if (instData) {
            setChipData(instData.map(d => ({
              date: d.date,
              foreign: d.foreign_net || 0,
              trust: d.trust_net || 0,
              dealer: d.dealer_net || 0
            })));
          }

          const { data: whale } = await supabase
            .from('stock_features')
            .select('*')
            .eq('stock_id', stockId)
            .order('date', { ascending: false })
            .limit(parseInt(timeRange));

          if (whale) {
            setWhaleData(whale.map(d => ({
              date: d.date,
              ratio: d.whale_ratio || 0,
              count: d.whale_count || 0,
              shares: d.whale_shares || 0
            })));
          }
        }
      } catch (err) {
        console.error('Failed to load chart data:', err);
      } finally {
        setLoading(false);
      }
    };

    if (stockId) {
      loadData();
    }
  }, [stockId, timeRange, supabase]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      setStockId(searchQuery.trim());
    }
  };

  // Chart rendering helpers
  const chartWidth = 1200;
  const chartHeight = 400;
  const volumeHeight = 100;
  const indicatorHeight = 120;
  const chipHeight = 100;
  const whaleHeight = 80;
  const padding = { top: 20, right: 80, bottom: 30, left: 10 };

  const effectiveWidth = chartWidth - padding.left - padding.right;
  const candleWidth = Math.max(1, effectiveWidth / priceData.length - 1);

  const priceScale = (price: number) => {
    if (priceData.length === 0) return 0;
    const prices = priceData.flatMap(d => [d.high, d.low]);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;
    return padding.top + chartHeight - ((price - min) / range) * (chartHeight - 2 * padding.top);
  };

  const volumeScale = (vol: number) => {
    if (priceData.length === 0) return 0;
    const maxVol = Math.max(...priceData.map(d => d.volume));
    return (vol / maxVol) * (volumeHeight - 10);
  };

  const indicatorScale = (val: number) => {
    return padding.top + indicatorHeight - (val / 100) * (indicatorHeight - 2 * padding.top);
  };

  const chipScale = (val: number) => {
    const max = Math.max(
      ...chipData.flatMap(d => [Math.abs(d.foreign), Math.abs(d.trust), Math.abs(d.dealer)]),
      1
    );
    return padding.top + chipHeight - (Math.abs(val) / max) * (chipHeight - 2 * padding.top);
  };

  const whaleScale = (val: number) => {
    return padding.top + whaleHeight - (val / 100) * (whaleHeight - 2 * padding.top);
  };

  const getX = (index: number) => {
    return padding.left + (index / priceData.length) * effectiveWidth;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-cyan-400 font-mono">載入圖表數據中...</div>
      </div>
    );
  }

  if (priceData.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-8">
        <div className="text-center">
          <Activity className="mx-auto text-slate-600 mb-4" size={48} />
          <p className="text-slate-400">請輸入股票代號查看K線圖</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header Controls */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <div className="flex flex-wrap items-center gap-4">
          <form onSubmit={handleSearch} className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="股票代號"
              className="w-24 bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm text-white font-mono"
            />
            <button
              type="submit"
              className="px-4 py-1.5 bg-cyan-500 hover:bg-cyan-400 text-slate-950 rounded font-bold text-sm"
            >
              查詢
            </button>
          </form>

          <div className="h-6 w-px bg-slate-700" />

          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-sm text-white"
          >
            <option value="60">60天</option>
            <option value="120">120天</option>
            <option value="240">240天</option>
          </select>

          <button
            onClick={() => setShowSettings(!showSettings)}
            className="p-1.5 hover:bg-slate-800 rounded transition-colors"
          >
            <Settings2 size={18} className="text-slate-400" />
          </button>

          <div className="ml-auto flex items-center gap-4 text-xs">
            {maData.map((ma) => (
              <div key={ma.period} className="flex items-center gap-1.5">
                <div className="w-3 h-0.5" style={{ backgroundColor: ma.color }} />
                <span className="text-slate-400">{ma.period}MA</span>
                <span className="text-white font-mono">
                  {ma.values[ma.values.length - 1]?.value.toFixed(0)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Main Chart Container */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        {/* Stock Info Bar */}
        <div className="bg-slate-950 px-4 py-2 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="text-white font-bold">{stockId}</span>
            <span className="text-slate-400">台積電</span>
          </div>
          <div className="text-xs text-slate-400">
            {priceData[priceData.length - 1]?.date}
          </div>
        </div>

        {/* Price Chart */}
        <div className="relative bg-slate-950" style={{ height: chartHeight + volumeHeight }}>
          <svg width={chartWidth} height={chartHeight + volumeHeight}>
            {/* Grid lines */}
            {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
              const y = padding.top + chartHeight * ratio;
              const price = priceData.length > 0
                ? Math.max(...priceData.flatMap(d => [d.high, d.low])) -
                  (ratio * (Math.max(...priceData.flatMap(d => [d.high, d.low])) -
                           Math.min(...priceData.flatMap(d => [d.high, d.low]))))
                : 0;
              return (
                <g key={ratio}>
                  <line
                    x1={padding.left}
                    y1={y}
                    x2={chartWidth - padding.right}
                    y2={y}
                    stroke="#334155"
                    strokeDasharray="2,2"
                  />
                  <text
                    x={chartWidth - padding.right + 5}
                    y={y + 4}
                    fill="#64748b"
                    fontSize="10"
                    fontFamily="monospace"
                  >
                    {price.toFixed(0)}
                  </text>
                </g>
              );
            })}

            {/* MA Lines */}
            {maData.map((ma) => (
              <polyline
                key={ma.period}
                points={ma.values
                  .map((v, i) => `${getX(i + (priceData.length - ma.values.length))},${priceScale(v.value)}`)
                  .join(' ')}
                fill="none"
                stroke={ma.color}
                strokeWidth={1.5}
              />
            ))}

            {/* Candlesticks */}
            {priceData.map((d, i) => (
              <g key={d.date} transform={`translate(${getX(i)}, 0)`}>
                <Candlestick
                  x={0}
                  open={d.open}
                  high={d.high}
                  low={d.low}
                  close={d.close}
                  width={candleWidth}
                  scale={priceScale}
                />
              </g>
            ))}

            {/* Volume Bars */}
            {priceData.map((d, i) => (
              <g key={`vol-${d.date}`} transform={`translate(${getX(i)}, ${chartHeight})`}>
                <VolumeBar
                  x={0}
                  volume={d.volume}
                  close={d.close}
                  open={d.open}
                  width={candleWidth}
                  scaleY={volumeScale}
                />
              </g>
            ))}

            {/* Volume separator line */}
            <line
              x1={padding.left}
              y1={chartHeight}
              x2={chartWidth - padding.right}
              y2={chartHeight}
              stroke="#475569"
              strokeWidth={1}
            />
          </svg>
        </div>

        {/* Indicator Panels */}
        <div className="border-t border-slate-800">
          {/* KD Indicator */}
          <div className="border-b border-slate-800" style={{ height: indicatorHeight }}>
            <div className="flex items-center justify-between px-4 py-1 bg-slate-900/50">
              <span className="text-xs text-slate-400">KD(9)</span>
              <div className="flex gap-4 text-xs">
                <span className="text-red-400">K:{indicatorData[indicatorData.length - 1]?.k.toFixed(2)}</span>
                <span className="text-blue-400">D:{indicatorData[indicatorData.length - 1]?.d.toFixed(2)}</span>
              </div>
            </div>
            <svg width={chartWidth} height={indicatorHeight - 20}>
              {[0, 25, 50, 75, 100].map((val) => {
                const y = indicatorScale(val);
                return (
                  <g key={val}>
                    <line
                      x1={padding.left}
                      y1={y}
                      x2={chartWidth - padding.right}
                      y2={y}
                      stroke="#1e293b"
                    />
                    <text
                      x={chartWidth - padding.right + 5}
                      y={y + 3}
                      fill="#64748b"
                      fontSize="9"
                    >
                      {val}
                    </text>
                  </g>
                );
              })}
              {/* K Line */}
              {indicatorData.length > 0 && (
                <polyline
                  points={indicatorData
                    .map((d, i) => `${getX(i + (priceData.length - indicatorData.length))},${indicatorScale(d.k)}`)
                    .join(' ')}
                  fill="none"
                  stroke="#ef4444"
                  strokeWidth={1}
                />
              )}
              {/* D Line */}
              {indicatorData.length > 0 && (
                <polyline
                  points={indicatorData
                    .map((d, i) => `${getX(i + (priceData.length - indicatorData.length))},${indicatorScale(d.d)}`)
                    .join(' ')}
                  fill="none"
                  stroke="#3b82f6"
                  strokeWidth={1}
                />
              )}
            </svg>
          </div>

          {/* Chip/Institutional */}
          <div className="border-b border-slate-800" style={{ height: chipHeight }}>
            <div className="flex items-center justify-between px-4 py-1 bg-slate-900/50">
              <span className="text-xs text-slate-400">法人籌碼</span>
              <div className="flex gap-4 text-xs">
                <span className="text-cyan-400">外資:{chipData[0]?.foreign.toLocaleString()}</span>
                <span className="text-orange-400">投信:{chipData[0]?.trust.toLocaleString()}</span>
              </div>
            </div>
            <svg width={chartWidth} height={chipHeight - 20}>
              <line
                x1={padding.left}
                y1={chipHeight / 2}
                x2={chartWidth - padding.right}
                y2={chipHeight / 2}
                stroke="#334155"
              />
              {chipData.slice(0, priceData.length).map((d, i) => {
                const x = getX(i + (priceData.length - chipData.length));
                return (
                  <g key={d.date}>
                    {d.foreign !== 0 && (
                      <rect
                        x={x - candleWidth / 2}
                        y={chipScale(d.foreign)}
                        width={candleWidth}
                        height={chipHeight / 2 - chipScale(d.foreign)}
                        fill={d.foreign > 0 ? '#06b6d4' : '#ef4444'}
                        opacity={0.7}
                      />
                    )}
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Whale Holdings */}
          <div style={{ height: whaleHeight }}>
            <div className="flex items-center justify-between px-4 py-1 bg-slate-900/50">
              <span className="text-xs text-slate-400">大戶持股</span>
              <div className="text-xs">
                <span className="text-white">
                  {whaleData[0]?.ratio.toFixed(2)}%
                </span>
                <span className="text-slate-500 ml-2">
                  人數:{whaleData[0]?.count.toLocaleString()}
                </span>
              </div>
            </div>
            <svg width={chartWidth} height={whaleHeight - 20}>
              {whaleData.length > 0 && (
                <polyline
                  points={whaleData
                    .map((d, i) => `${getX(i)},${whaleScale(d.ratio)}`)
                    .join(' ')}
                  fill="none"
                  stroke="#8b5cf6"
                  strokeWidth={1.5}
                />
              )}
              {whaleData.map((d, i) => (
                <circle
                  key={d.date}
                  cx={getX(i)}
                  cy={whaleScale(d.ratio)}
                  r={2}
                  fill="#8b5cf6"
                />
              ))}
            </svg>
          </div>
        </div>

        {/* Date Axis */}
        <div className="bg-slate-950 px-4 py-2 border-t border-slate-800">
          <div className="relative" style={{ width: chartWidth - padding.left - padding.right, marginLeft: padding.left }}>
            {priceData.filter((_, i) => i % Math.ceil(priceData.length / 6) === 0).map((d, i) => {
              const x = (i * Math.ceil(priceData.length / 6) / priceData.length) * effectiveWidth;
              return (
                <div
                  key={d.date}
                  className="absolute text-[10px] text-slate-500 transform -translate-x-1/2"
                  style={{ left: x }}
                >
                  {d.date.slice(5)}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}