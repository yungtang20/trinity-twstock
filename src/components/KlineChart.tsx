import React, { useMemo, useState, useCallback } from 'react';
import {
  ComposedChart, BarChart, LineChart, Line, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Cell
} from 'recharts';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { PriceData, calcMA, calcMACD, calcRSI, calcKD } from '../lib/indicators';

export interface KlineOverlay {
  /** 水平線：支撐壓力、均線目標等 */
  hLines?: { value: number; color: string; label?: string; dash?: boolean }[];
  /** 額外 MA 覆蓋（優先於內建 MA） */
  extraMAs?: { period: number; color: string; label: string }[];
}

interface KlineChartProps {
  data: PriceData[];
  overlay?: KlineOverlay;
  /** 控制內建 MA 週期，預設 [5, 25, 60] */
  defaultMaPeriods?: number[];
}

type TabType = 'kline' | 'macd' | 'rsi' | 'kd';
const WINDOW_OPTIONS = [30, 60, 90] as const;

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const isUp = d.close >= d.open;
  const change = d.close - d.open;
  const changePct = (change / d.open) * 100;
  return (
    <div className="bg-slate-950/95 border border-slate-700 p-3 rounded-lg shadow-2xl font-mono text-xs text-slate-300 space-y-1 min-w-[190px]">
      <div className="text-slate-400 font-bold border-b border-slate-800 pb-1">{d.date}</div>
      <div className="space-y-0.5">
        {[['開盤', d.open, 'text-slate-200'], ['最高', d.high, 'text-red-400'], ['最低', d.low, 'text-emerald-400'],
          ['收盤', d.close, isUp ? 'text-red-400' : 'text-emerald-400']].map(([l, v, c]) => (
          <div key={l as string} className="flex justify-between">
            <span className="text-slate-500">{l}:</span>
            <span className={`font-bold ${c}`}>{(v as number).toFixed(2)}</span>
          </div>
        ))}
        <div className="flex justify-between border-t border-slate-800 pt-1">
          <span className="text-slate-500">漲跌:</span>
          <span className={change >= 0 ? 'text-red-400 font-bold' : 'text-emerald-400 font-bold'}>
            {change >= 0 ? '+' : ''}{change.toFixed(2)} ({changePct >= 0 ? '+' : ''}{changePct.toFixed(2)}%)
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500">成交量:</span>
          <span className="text-slate-100 font-semibold">{d.volume.toLocaleString()} 張</span>
        </div>
      </div>
    </div>
  );
};

export function KlineChart({ data, overlay, defaultMaPeriods = [5, 25, 60] }: KlineChartProps) {
  const [activeTab, setActiveTab] = useState<TabType>('kline');
  const [maPeriods, setMaPeriods] = useState<number[]>(defaultMaPeriods);
  const [windowSize, setWindowSize] = useState<30 | 60 | 90>(60);
  // windowOffset: 0 = 最新，往右 shift 看越舊的資料
  const [windowOffset, setWindowOffset] = useState(0);

  const totalLen = data.length;
  // 計算當前視窗的起終 index
  const endIdx   = Math.max(0, totalLen - 1 - windowOffset);
  const startIdx = Math.max(0, endIdx - windowSize + 1);
  const windowData = useMemo(() => data.slice(startIdx, endIdx + 1), [data, startIdx, endIdx]);

  const canGoLeft  = startIdx > 0;
  const canGoRight = windowOffset > 0;

  const shift = useCallback((dir: 'left' | 'right') => {
    const step = Math.max(1, Math.floor(windowSize / 5));
    setWindowOffset(prev => dir === 'left'
      ? Math.min(prev + step, totalLen - windowSize)
      : Math.max(0, prev - step));
  }, [windowSize, totalLen]);

  // 全量資料計算指標，然後切片（確保 MA 有足夠期數）
  const closes = useMemo(() => data.map(d => d.close), [data]);
  const allMA = useMemo(() => {
    const periods = overlay?.extraMAs
      ? overlay.extraMAs.map(e => e.period)
      : maPeriods;
    const unique = [...new Set([...maPeriods, ...periods])];
    const result: Record<number, (number | null)[]> = {};
    unique.forEach(p => { result[p] = calcMA(closes, p); });
    return result;
  }, [closes, maPeriods, overlay]);

  const macdData = useMemo(() => calcMACD(closes), [closes]);
  const rsiData  = useMemo(() => calcRSI(closes), [closes]);
  const kdData   = useMemo(() => calcKD(data), [data]);

  // 計算 chartData 用全量再切片，保證指標值正確
  const allChartData = useMemo(() => data.map((d, i) => {
    const isUp = d.close >= d.open;
    const color = isUp ? '#ef4444' : '#22c55e';
    const upper = Math.max(d.open, d.close);
    const lower = Math.min(d.open, d.close);
    const row: any = {
      date: d.date, open: d.open, high: d.high, low: d.low, close: d.close, volume: d.volume,
      color, upper, lower,
      boxRange: [lower, upper],
      wickRange: [d.low, d.high],
      macd: macdData.macd[i],
      dif: macdData.dif[i],
      dea: macdData.dea[i],
      rsi: rsiData[i],
      k: kdData.k[i],
      d: kdData.d[i],
      isUp,
    };
    Object.keys(allMA).forEach(p => { row[`ma${p}`] = allMA[+p][i]; });
    return row;
  }), [data, allMA, macdData, rsiData, kdData]);

  const chartData = useMemo(() => allChartData.slice(startIdx, endIdx + 1), [allChartData, startIdx, endIdx]);

  const displayMAs = overlay?.extraMAs
    ? overlay.extraMAs
    : maPeriods.map((p, idx) => ({
        period: p,
        label: `MA${p}`,
        color: ['#f43f5e', '#f59e0b', '#3b82f6'][idx % 3],
      }));

  const tabs: { key: TabType; label: string }[] = [
    { key: 'kline', label: 'K 線' },
    { key: 'macd', label: 'MACD' },
    { key: 'rsi', label: 'RSI' },
    { key: 'kd', label: 'KD' },
  ];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-lg shadow-black/40">
      {/* ── Header: tabs + MA toggles + 視窗控制 ── */}
      <div className="flex items-center border-b border-slate-800 bg-slate-950/30 flex-wrap gap-y-1">
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2.5 text-xs font-medium transition-colors shrink-0 ${
              activeTab === tab.key
                ? 'text-cyan-400 border-b-2 border-cyan-400 bg-cyan-950/20'
                : 'text-slate-500 hover:text-slate-300'
            }`}
          >
            {tab.label}
          </button>
        ))}

        {/* MA period toggles（僅在 kline tab 且無外部 extraMAs 時顯示） */}
        {activeTab === 'kline' && !overlay?.extraMAs && (
          <div className="flex items-center gap-1 px-3">
            {[5, 25, 60].map(p => (
              <button
                key={p}
                onClick={() => setMaPeriods(prev =>
                  prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p].sort((a, b) => a - b))}
                className={`px-2 py-1 text-[10px] rounded transition-all font-mono ${
                  maPeriods.includes(p)
                    ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                    : 'text-slate-600 hover:text-slate-400'
                }`}
              >
                MA{p}
              </button>
            ))}
          </div>
        )}

        {/* 日期視窗控制 */}
        <div className="ml-auto flex items-center gap-1 px-3">
          {WINDOW_OPTIONS.map(w => (
            <button
              key={w}
              onClick={() => { setWindowSize(w); setWindowOffset(0); }}
              className={`px-2 py-1 text-[10px] rounded font-mono transition-all ${
                windowSize === w
                  ? 'bg-slate-700 text-white'
                  : 'text-slate-500 hover:text-slate-300'
              }`}
            >
              {w}天
            </button>
          ))}
          <button
            onClick={() => shift('left')}
            disabled={!canGoLeft}
            className="p-1 rounded text-slate-500 hover:text-slate-300 disabled:opacity-30 transition-colors"
            title="往前（舊）"
          >
            <ChevronLeft size={14} />
          </button>
          <button
            onClick={() => shift('right')}
            disabled={!canGoRight}
            className="p-1 rounded text-slate-500 hover:text-slate-300 disabled:opacity-30 transition-colors"
            title="往後（新）"
          >
            <ChevronRight size={14} />
          </button>
          <span className="text-[10px] text-slate-600 font-mono ml-1">
            {windowData[0]?.date?.slice(5)} ~ {windowData[windowData.length - 1]?.date?.slice(5)}
          </span>
        </div>
      </div>

      {/* ── Chart Area ── */}
      <div className="p-3" style={{ height: activeTab === 'kline' ? 400 : 280 }}>
        {activeTab === 'kline' && (
          <div className="h-full flex flex-col gap-1">
            {/* 主圖：K 線 + MA + 水平標記線 */}
            <div style={{ flex: '0 0 72%' }}>
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barGap="-100%">
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.6} />
                  <XAxis dataKey="date" tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false}
                    tickFormatter={v => v?.slice(5) ?? ''} interval="preserveStartEnd" />
                  <YAxis domain={['auto', 'auto']} tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false} width={46} />
                  <Tooltip content={<CustomTooltip />} />

                  {/* 影線 */}
                  <Bar dataKey="wickRange" barSize={1.5}>
                    {chartData.map((e, i) => <Cell key={`w${i}`} fill={e.color} />)}
                  </Bar>
                  {/* 實體 */}
                  <Bar dataKey="boxRange" barSize={Math.max(3, Math.floor(600 / windowSize) - 2)}>
                    {chartData.map((e, i) => <Cell key={`b${i}`} fill={e.color} />)}
                  </Bar>

                  {/* MA 線 */}
                  {displayMAs.map(ma => (
                    <Line key={`ma${ma.period}`} type="monotone" dataKey={`ma${ma.period}`}
                      stroke={ma.color} dot={false} strokeWidth={1.5} name={ma.label} connectNulls={false} />
                  ))}

                  {/* 策略水平標記線（支撐壓力等） */}
                  {overlay?.hLines?.map((hl, i) => (
                    <ReferenceLine
                      key={`hl${i}`} y={hl.value}
                      stroke={hl.color}
                      strokeDasharray={hl.dash ? '4 3' : undefined}
                      strokeWidth={1.2}
                      label={hl.label ? { value: `${hl.label} ${hl.value}`, fill: hl.color, fontSize: 9, position: 'right' } : undefined}
                    />
                  ))}
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            {/* 副圖：成交量 */}
            <div style={{ flex: '0 0 25%' }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 2, right: 8, left: 0, bottom: 0 }}>
                  <XAxis dataKey="date" tick={false} tickLine={false} axisLine={false} />
                  <YAxis domain={[0, 'auto']} tick={{ fill: '#475569', fontSize: 8 }} tickLine={false} axisLine={false} width={46} />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="volume">
                    {chartData.map((e, i) => <Cell key={`v${i}`} fill={e.color} opacity={0.6} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {activeTab === 'macd' && (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => v?.slice(5) ?? ''} />
              <YAxis tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false} width={46} />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#f1f5f9', fontSize: '11px' }} />
              <ReferenceLine y={0} stroke="#334155" strokeDasharray="3 3" />
              <Bar dataKey="macd" fill="#64748b" opacity={0.7}>
                {chartData.map((e, i) => <Cell key={`m${i}`} fill={(e.macd ?? 0) >= 0 ? '#ef4444' : '#22c55e'} opacity={0.7} />)}
              </Bar>
              <Line type="monotone" dataKey="dif" stroke="#06b6d4" dot={false} strokeWidth={1.5} name="DIF" />
              <Line type="monotone" dataKey="dea" stroke="#f59e0b" dot={false} strokeWidth={1.5} name="DEA" />
            </ComposedChart>
          </ResponsiveContainer>
        )}

        {activeTab === 'rsi' && (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => v?.slice(5) ?? ''} />
              <YAxis domain={[0, 100]} tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false} width={32} />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#f1f5f9', fontSize: '11px' }} />
              <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="3 3" label={{ value: '70', fill: '#ef4444', fontSize: 9 }} />
              <ReferenceLine y={30} stroke="#22c55e" strokeDasharray="3 3" label={{ value: '30', fill: '#22c55e', fontSize: 9 }} />
              <Line type="monotone" dataKey="rsi" stroke="#06b6d4" dot={false} strokeWidth={2} name="RSI" />
            </LineChart>
          </ResponsiveContainer>
        )}

        {activeTab === 'kd' && (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="date" tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false} tickFormatter={v => v?.slice(5) ?? ''} />
              <YAxis domain={[0, 100]} tick={{ fill: '#475569', fontSize: 9 }} tickLine={false} axisLine={false} width={32} />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px', color: '#f1f5f9', fontSize: '11px' }} />
              <ReferenceLine y={80} stroke="#ef4444" strokeDasharray="3 3" label={{ value: '80', fill: '#ef4444', fontSize: 9 }} />
              <ReferenceLine y={20} stroke="#22c55e" strokeDasharray="3 3" label={{ value: '20', fill: '#22c55e', fontSize: 9 }} />
              <Line type="monotone" dataKey="k" stroke="#06b6d4" dot={false} strokeWidth={1.5} name="K" />
              <Line type="monotone" dataKey="d" stroke="#f59e0b" dot={false} strokeWidth={1.5} name="D" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
