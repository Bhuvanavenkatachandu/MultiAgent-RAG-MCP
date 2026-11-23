import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AnalyticalReport } from '../utils/reportParser';
import { ExecutiveSummary } from './ExecutiveSummary';
import { MetricCards } from './MetricCards';
import { DynamicChart } from './DynamicChart';
import { DataTable } from './DataTable';
import { InsightCards } from './InsightCards';
import { EmptyState } from './EmptyState';

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
