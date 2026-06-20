import { useState, useEffect } from 'react';
import { fetchPatternAnalysis, type PatternAnalysis } from '../../lib/api';

interface PatternPanelProps {
  stockId: string;
}

export function PatternPanel({ stockId }: PatternPanelProps) {
  const [data, setData] = useState<PatternAnalysis | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!stockId) return;
    setLoading(true);
    fetchPatternAnalysis(stockId)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [stockId]);

  return (
    <div className="bg-slate-950/50 border border-slate-800 rounded-xl p-4 sm:p-5 hover:border-slate-700/80 transition-all font-mono text-xs sm:text-[13px]">
      <h3 className="text-sm sm:text-base font-bold text-white mb-4 flex items-center gap-2 border-b border-slate-800 pb-2">
        <span className="font-mono text-cyan-400 select-none">5 ⚡</span>
        幾何型態 (Chart Patterns)
      </h3>

      {loading && <div className="text-slate-500 text-center py-4 text-xs">分析中...</div>}
      {!loading && !data && <div className="text-slate-500 text-center py-4 text-xs">無資料</div>}

      {data && (
      <div className="space-y-4">
        <div className="bg-slate-950 p-3 rounded-lg border border-slate-850">
          <div className="flex items-center gap-2 mb-2">
            <span className={`text-base font-bold ${data.patternDirection === 'up' ? 'text-red-400' : data.patternDirection === 'down' ? 'text-emerald-400' : 'text-slate-400'} flex items-center gap-0.5`}>
              🔴 {data.patternName}
            </span>
            {data.confidence > 0 && (
              <span className="text-[10px] text-slate-500">信心度 {(data.confidence * 100).toFixed(0)}%</span>
            )}
          </div>
          <div className="grid grid-cols-3 gap-2 text-xs text-slate-400 mt-2">
            <div>
              <div>頸線</div>
              <div className="text-slate-100 font-bold">{data.neckline.toFixed(2)}</div>
            </div>
            <div>
              <div>目標</div>
              <div className="text-emerald-400 font-bold">{data.target.toFixed(2)}</div>
            </div>
            <div>
              <div>停損</div>
              <div className="text-rose-400 font-bold">{data.stopLoss.toFixed(2)}</div>
            </div>
          </div>
        </div>
      </div>
      )}
    </div>
  );
}
