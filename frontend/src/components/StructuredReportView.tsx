import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Sparkles,
  TrendingUp,
  TrendingDown,
  Minus,
  BarChart3,
  DollarSign,
  Package,
  Users,
  Activity,
  Award,
  ArrowLeftRight,
  AlertTriangle,
  Lightbulb,
  CheckCircle2,
  Database,
  SearchX,
  HelpCircle,
} from 'lucide-react';
import {
  AnalyticalReport,
  MetricCardItem,
  AnalyticalInsightItem,
  InsightType,
} from '../utils/reportParser';
import { DynamicChart } from './DynamicChart';
import { DataTable } from './DataTable';

// ---------------------------------------------------------------------------
// 1. Executive Briefing Sub-Component
// ---------------------------------------------------------------------------
const ExecutiveSummary: React.FC<{ summary: string }> = ({ summary }) => {
  if (!summary?.trim()) return null;
  return (
    <div className="my-3 p-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 dark:bg-emerald-500/5 relative overflow-hidden">
      <div className="absolute top-0 left-0 bottom-0 w-1 bg-emerald-500" />
      <div className="flex items-center gap-2 mb-2">
        <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-wider uppercase bg-emerald-100 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300">
          <Sparkles className="w-3 h-3" />
          Executive Briefing
        </span>
      </div>
      <div className="prose dark:prose-invert prose-sm max-w-none text-slate-800 dark:text-slate-200 leading-relaxed font-sans">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{summary}</ReactMarkdown>
      </div>
    </div>
  );
};

// ---------------------------------------------------------------------------
// 2. Key KPI Metric Cards Sub-Component
// ---------------------------------------------------------------------------
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

const MetricCards: React.FC<{ metrics: MetricCardItem[] }> = ({ metrics }) => {
  if (!metrics?.length) return null;
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 my-3">
      {metrics.map((item, idx) => (
        <div
          key={idx}
          className="p-3.5 rounded-xl border border-slate-200/80 dark:border-slate-800/80 bg-white/80 dark:bg-slate-900/80 backdrop-blur-xs shadow-xs hover:shadow-sm transition-all flex flex-col justify-between"
        >
          <div className="flex items-center justify-between gap-1 mb-1.5">
            <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 truncate uppercase tracking-wider">
              {item.label}
            </span>
            <div className="p-1 rounded-md bg-slate-100 dark:bg-slate-800/80 shrink-0">
              {getMetricIcon(item.label)}
            </div>
          </div>
          <div className="text-lg md:text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 font-mono">
            {item.value}
          </div>
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

// ---------------------------------------------------------------------------
// 3. Categorized Business Insights Sub-Component
// ---------------------------------------------------------------------------
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

const InsightCards: React.FC<{ insights: AnalyticalInsightItem[] }> = ({ insights }) => {
  if (!insights?.length) return null;
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

// ---------------------------------------------------------------------------
// 4. Empty State Sub-Component
// ---------------------------------------------------------------------------
const EmptyState: React.FC<{ message?: string }> = ({ message }) => (
  <div className="my-4 p-6 rounded-2xl border border-dashed border-slate-300 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/30 text-center flex flex-col items-center justify-center">
    <div className="w-10 h-10 rounded-xl bg-slate-200/60 dark:bg-slate-800 text-slate-500 dark:text-slate-400 flex items-center justify-center mb-3">
      <SearchX className="w-5 h-5" />
    </div>
    <h4 className="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-1">
      No Matching Records Found
    </h4>
    <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md leading-relaxed mb-3">
      {message || 'The database executed the query successfully, but returned 0 rows matching your criteria.'}
    </p>
    <div className="flex flex-wrap items-center justify-center gap-2 text-[11px] text-slate-500 dark:text-slate-400">
      <span className="flex items-center gap-1">
        <HelpCircle className="w-3 h-3 text-emerald-500" />
        Tip: Verify category names or date ranges
      </span>
      <span>•</span>
      <span className="flex items-center gap-1">
        <Database className="w-3 h-3 text-blue-500" />
        Ask "What tables exist?" to inspect schema
      </span>
    </div>
  </div>
);

// ---------------------------------------------------------------------------
// 5. Main Structured Report View
// ---------------------------------------------------------------------------
interface StructuredReportViewProps {
  report: AnalyticalReport;
}

export const StructuredReportView: React.FC<StructuredReportViewProps> = ({ report }) => {
  return (
    <div className="w-full space-y-4">
      {/* 1. Executive Summary */}
      {report.summary && <ExecutiveSummary summary={report.summary} />}

      {/* 2. Key KPI Metric Cards */}
      {report.metrics && report.metrics.length > 0 && (
        <MetricCards metrics={report.metrics} />
      )}

      {/* 3. Empty State if database returned 0 matching records */}
      {report.isEmptyResult && (
        <EmptyState message="The database query executed without errors, but returned 0 rows matching your criteria." />
      )}

      {/* 4. Interactive Chart */}
      {report.tableData && report.tableData.rows.length >= 2 && report.chartRecommendation && (
        <DynamicChart
          tableData={report.tableData}
          recommendation={report.chartRecommendation}
        />
      )}

      {/* 5. Sortable Structured Data Table */}
      {report.tableData && report.tableData.rows.length > 0 && (
        <DataTable data={report.tableData} />
      )}

      {/* 6. Categorized Business Insights & Recommendations */}
      {report.insights && report.insights.length > 0 && (
        <InsightCards insights={report.insights} />
      )}

      {/* 7. Fallback standard markdown if non-structured or extra narrative text */}
      {!report.isStructuredReport && report.rawMarkdown && (
        <div className="prose dark:prose-invert prose-sm md:prose-base max-w-none text-slate-800 dark:text-slate-200 leading-relaxed">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {report.rawMarkdown}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
};
