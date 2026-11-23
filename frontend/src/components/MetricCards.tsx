import React from 'react';
import { TrendingUp, TrendingDown, Minus, BarChart3, DollarSign, Package, Users, Activity } from 'lucide-react';
import { MetricCardItem } from '../utils/reportParser';

interface MetricCardsProps {
  metrics: MetricCardItem[];
}

function getMetricIcon(label: string) {
  const lower = label.toLowerCase();
  if (lower.includes('revenue') || lower.includes('sales') || lower.includes('spent') || lower.includes('$')) {
    return <DollarSign className="w-3.5 h-3.5 text-emerald-500" />;
  }
  if (lower.includes('order') || lower.includes('quantity') || lower.includes('count') || lower.includes('product')) {
    return <Package className="w-3.5 h-3.5 text-blue-500" />;
  }
  if (lower.includes('customer') || lower.includes('user') || lower.includes('client')) {
    return <Users className="w-3.5 h-3.5 text-purple-500" />;
  }
  if (lower.includes('rate') || lower.includes('growth') || lower.includes('margin') || lower.includes('%')) {
    return <Activity className="w-3.5 h-3.5 text-amber-500" />;
  }
  return <BarChart3 className="w-3.5 h-3.5 text-emerald-500" />;
}

export const MetricCards: React.FC<MetricCardsProps> = ({ metrics }) => {
  if (!metrics || metrics.length === 0) return null;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 my-3">
      {metrics.map((item, idx) => (
        <div
          key={idx}
          className="p-3.5 rounded-xl border border-slate-200/80 dark:border-slate-800/80 bg-white/80 dark:bg-slate-900/80 backdrop-blur-xs shadow-xs hover:shadow-sm transition-all flex flex-col justify-between"
        >
          {/* Header */}
          <div className="flex items-center justify-between gap-1 mb-1.5">
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 truncate uppercase tracking-wider">
              {item.label}
            </span>
            <div className="p-1 rounded-md bg-slate-100 dark:bg-slate-800/80 shrink-0">
              {getMetricIcon(item.label)}
            </div>
          </div>

          {/* Metric Value */}
          <div className="text-lg md:text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 font-mono">
            {item.value}
          </div>

          {/* Context / Trend */}
          {item.context && (
            <div className="mt-2 flex items-center gap-1 text-[11px]">
              {item.trend === 'up' ? (
                <TrendingUp className="w-3 h-3 text-emerald-600 dark:text-emerald-400 shrink-0" />
              ) : item.trend === 'down' ? (
                <TrendingDown className="w-3 h-3 text-rose-600 dark:text-rose-400 shrink-0" />
              ) : (
                <Minus className="w-3 h-3 text-slate-400 shrink-0" />
              )}
              <span
                className={`truncate ${
                  item.trend === 'up'
                    ? 'text-emerald-600 dark:text-emerald-400 font-medium'
                    : item.trend === 'down'
                    ? 'text-rose-600 dark:text-rose-400 font-medium'
                    : 'text-slate-500 dark:text-slate-400'
                }`}
              >
                {item.context}
              </span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
