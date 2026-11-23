import React from 'react';
import {
  Award,
  TrendingUp,
  ArrowLeftRight,
  AlertTriangle,
  Lightbulb,
  CheckCircle2,
} from 'lucide-react';
import { AnalyticalInsightItem, InsightType } from '../utils/reportParser';

interface InsightCardsProps {
  insights: AnalyticalInsightItem[];
}

function getInsightConfig(type: InsightType) {
  switch (type) {
    case 'top_performer':
      return {
        icon: <Award className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />,
        badgeBg: 'bg-emerald-100/80 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300',
        borderColor: 'border-emerald-200/80 dark:border-emerald-900/50',
      };
    case 'trend':
      return {
        icon: <TrendingUp className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />,
        badgeBg: 'bg-blue-100/80 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300',
        borderColor: 'border-blue-200/80 dark:border-blue-900/50',
      };
    case 'comparison':
      return {
        icon: <ArrowLeftRight className="w-3.5 h-3.5 text-purple-600 dark:text-purple-400" />,
        badgeBg: 'bg-purple-100/80 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300',
        borderColor: 'border-purple-200/80 dark:border-purple-900/50',
      };
    case 'anomaly':
      return {
        icon: <AlertTriangle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />,
        badgeBg: 'bg-amber-100/80 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300',
        borderColor: 'border-amber-200/80 dark:border-amber-900/50',
      };
    case 'recommendation':
      return {
        icon: <Lightbulb className="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />,
        badgeBg: 'bg-indigo-100/80 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300',
        borderColor: 'border-indigo-200/80 dark:border-indigo-900/50',
      };
    default:
      return {
        icon: <CheckCircle2 className="w-3.5 h-3.5 text-slate-600 dark:text-slate-400" />,
        badgeBg: 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300',
        borderColor: 'border-slate-200 dark:border-slate-800',
      };
  }
}

export const InsightCards: React.FC<InsightCardsProps> = ({ insights }) => {
  if (!insights || insights.length === 0) return null;

  return (
    <div className="my-4 space-y-2.5">
      <div className="flex items-center gap-2 mb-2">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Analytical Insights & Recommendations
        </h4>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
        {insights.map((item, idx) => {
          const config = getInsightConfig(item.type);
          return (
            <div
              key={idx}
              className={`p-3.5 rounded-xl border ${config.borderColor} bg-white/70 dark:bg-slate-900/70 backdrop-blur-xs shadow-xs hover:shadow-sm transition-all`}
            >
              <div className="flex items-center gap-1.5 mb-1.5">
                <span className={`flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-semibold tracking-wide ${config.badgeBg}`}>
                  {config.icon}
                  {item.title}
                </span>
              </div>
              <p className="text-xs md:text-sm text-slate-700 dark:text-slate-300 leading-relaxed">
                {item.content}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
};
