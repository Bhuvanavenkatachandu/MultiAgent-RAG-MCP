import {
  ChartRecommendation,
  detectVisualData,
  ParsedTableData,
} from './chartDetector';

export interface MetricCardItem {
  label: string;
  value: string;
  context?: string;
  change?: string;
  trend?: 'up' | 'down' | 'neutral';
}

export type InsightType =
  | 'top_performer'
  | 'trend'
  | 'comparison'
  | 'anomaly'
  | 'recommendation'
  | 'observation';

export interface AnalyticalInsightItem {
  type: InsightType;
  title: string;
  content: string;
}

export interface AnalyticalReport {
  summary: string;
  metrics: MetricCardItem[];
  tableData: ParsedTableData | null;
  chartRecommendation: ChartRecommendation | null;
  insights: AnalyticalInsightItem[];
  isStructuredReport: boolean;
  isEmptyResult: boolean;
  rawMarkdown: string;
}

/**
 * Normalizes insight string to a standard InsightType and clean title.
 */
function classifyInsight(rawType: string): { type: InsightType; title: string } {
  const lower = rawType.toLowerCase().replace(/[^a-z]/g, '');
  if (lower.includes('topperformer') || lower.includes('top') || lower.includes('leader')) {
    return { type: 'top_performer', title: 'Top Performer' };
  }
  if (lower.includes('trend') || lower.includes('growth') || lower.includes('pattern')) {
    return { type: 'trend', title: 'Observed Trend' };
  }
  if (lower.includes('comparison') || lower.includes('vs') || lower.includes('compare')) {
    return { type: 'comparison', title: 'Comparative Analysis' };
  }
  if (lower.includes('anomaly') || lower.includes('outlier') || lower.includes('warning') || lower.includes('alert')) {
    return { type: 'anomaly', title: 'Anomaly / Outlier' };
  }
  if (lower.includes('recommendation') || lower.includes('action') || lower.includes('suggestion') || lower.includes('takeaway')) {
    return { type: 'recommendation', title: 'Actionable Recommendation' };
  }
  return { type: 'observation', title: 'Key Finding' };
}

/**
 * Extracts structured sections from markdown using heading boundaries.
 */
function extractSections(markdown: string): Record<string, string[]> {
  const sections: Record<string, string[]> = {};
  let currentKey = 'intro';
  const lines = markdown.split('\n');

  for (const line of lines) {
    const headingMatch = line.match(/^#{1,4}\s+(.+)$/);
    if (headingMatch) {
      const heading = headingMatch[1].toLowerCase().trim();
      if (heading.includes('summary') || heading.includes('executive')) {
        currentKey = 'summary';
      } else if (heading.includes('metric') || heading.includes('kpi')) {
        currentKey = 'metrics';
      } else if (heading.includes('table') || heading.includes('data')) {
        currentKey = 'table';
      } else if (heading.includes('insight') || heading.includes('narrative') || heading.includes('takeaway')) {
        currentKey = 'insights';
      } else {
        currentKey = heading;
      }
      if (!sections[currentKey]) sections[currentKey] = [];
    } else {
      if (!sections[currentKey]) sections[currentKey] = [];
      sections[currentKey].push(line);
    }
  }

  return sections;
}

/**
 * Parses metrics from lines matching standard structured pipe format or bullet points.
 */
function parseMetrics(lines: string[]): MetricCardItem[] {
  const metrics: MetricCardItem[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed.startsWith('-') && !trimmed.startsWith('*')) continue;

    // Format 1: - Metric: [Label] | Value: [Value] | Context: [Context]
    if (trimmed.includes('|')) {
      const parts = trimmed.replace(/^[*-]\s*/, '').split('|').map((p) => p.trim());
      let label = '';
      let value = '';
      let context = '';

      for (const part of parts) {
        if (/^metric\s*:/i.test(part)) {
          label = part.replace(/^metric\s*:/i, '').trim();
        } else if (/^value\s*:/i.test(part)) {
          value = part.replace(/^value\s*:/i, '').trim();
        } else if (/^context\s*:/i.test(part)) {
          context = part.replace(/^context\s*:/i, '').trim();
        } else if (!label) {
          label = part;
        } else if (!value) {
          value = part;
        } else if (!context) {
          context = part;
        }
      }

      if (label && value) {
        let trend: 'up' | 'down' | 'neutral' = 'neutral';
        if (value.includes('+') || context.includes('+') || context.toLowerCase().includes('growth') || context.toLowerCase().includes('increase')) {
          trend = 'up';
        } else if (value.includes('-') || context.includes('-') || context.toLowerCase().includes('drop') || context.toLowerCase().includes('decline')) {
          trend = 'down';
        }

        metrics.push({ label, value, context: context || undefined, trend });
        continue;
      }
    }

    // Format 2: - **[Label]:** [Value] ([Context])
    const bulletMatch = trimmed.match(/^[*-]\s*(?:\*\*)?([^:*]+?)(?:\*\*)?:\s*(.+)$/);
    if (bulletMatch) {
      const label = bulletMatch[1].replace(/^metric\s+/i, '').trim();
      let rawVal = bulletMatch[2].trim();
      let context = '';

      // Check for parenthetical context e.g. "$1,234 (15% increase)"
      const parenMatch = rawVal.match(/^([^()]+)\s*\(([^)]+)\)$/);
      if (parenMatch) {
        rawVal = parenMatch[1].trim();
        context = parenMatch[2].trim();
      }

      // Check if value is reasonably short (metrics shouldn't be long paragraphs)
      if (rawVal.length <= 40 && label.length <= 40) {
        let trend: 'up' | 'down' | 'neutral' = 'neutral';
        if (context.includes('+') || context.toLowerCase().includes('growth') || context.toLowerCase().includes('up')) {
          trend = 'up';
        } else if (context.includes('-') || context.toLowerCase().includes('decline') || context.toLowerCase().includes('down')) {
          trend = 'down';
        }
        metrics.push({ label, value: rawVal, context: context || undefined, trend });
      }
    }
  }

  return metrics;
}

/**
 * Parses analytical insights from bullet points with type prefixes.
 */
function parseInsights(lines: string[]): AnalyticalInsightItem[] {
  const insights: AnalyticalInsightItem[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed.startsWith('-') && !trimmed.startsWith('*')) continue;

    const contentLine = trimmed.replace(/^[*-]\s*/, '').trim();
    const prefixMatch = contentLine.match(/^([A-Za-z\s/]+?):\s*(.+)$/);

    if (prefixMatch) {
      const rawCategory = prefixMatch[1].trim();
      const insightText = prefixMatch[2].trim();
      const { type, title } = classifyInsight(rawCategory);

      insights.push({
        type,
        title,
        content: insightText,
      });
    } else if (contentLine.length > 15) {
      // General observation without explicit prefix
      insights.push({
        type: 'observation',
        title: 'Key Finding',
        content: contentLine,
      });
    }
  }

  return insights;
}

/**
 * Auto-derives key metrics from a parsed table if none were explicitly provided.
 */
function deriveMetricsFromTable(table: ParsedTableData): MetricCardItem[] {
  if (!table || table.rows.length === 0) return [];
  const metrics: MetricCardItem[] = [];

  // Metric 1: Record Count
  metrics.push({
    label: 'Total Records',
    value: table.rows.length.toLocaleString(),
    context: 'Rows retrieved from database',
    trend: 'neutral',
  });

  // Metric 2: Identify primary numeric column and compute total or top
  const headers = table.headers;
  let primaryNumericCol: string | null = null;
  let primaryCategoryCol: string | null = null;

  for (const h of headers) {
    let numericCount = 0;
    for (const r of table.rows) {
      const raw = String(r[h] ?? '').replace(/[$€£₹,]/g, '').replace(/%/g, '').trim();
      if (raw !== '' && !isNaN(Number(raw))) numericCount++;
    }
    if (numericCount / table.rows.length >= 0.7 && !primaryNumericCol) {
      primaryNumericCol = h;
    } else if (!primaryCategoryCol) {
      primaryCategoryCol = h;
    }
  }

  if (primaryNumericCol) {
    const isCurrency = table.rows.some((r) => String(r[primaryNumericCol!]).includes('$'));
    const isPercent = table.rows.some((r) => String(r[primaryNumericCol!]).includes('%'));

    let sum = 0;
    let maxVal = -Infinity;
    let maxRow: Record<string, any> | null = null;

    table.rows.forEach((r) => {
      const clean = String(r[primaryNumericCol!] ?? '').replace(/[$€£₹,]/g, '').replace(/%/g, '').trim();
      const num = Number(clean);
      if (!isNaN(num)) {
        sum += num;
        if (num > maxVal) {
          maxVal = num;
          maxRow = r;
        }
      }
    });

    const isSumMeaningful = !primaryNumericCol.toLowerCase().includes('id') &&
      !primaryNumericCol.toLowerCase().includes('year') &&
      !primaryNumericCol.toLowerCase().includes('rate');

    if (isSumMeaningful && sum > 0) {
      const formattedTotal = isCurrency
        ? `$${sum.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
        : isPercent
        ? `${sum.toFixed(1)}%`
        : sum.toLocaleString();

      metrics.push({
        label: `Total ${primaryNumericCol.replace(/_/g, ' ')}`,
        value: formattedTotal,
        context: 'Aggregated sum',
        trend: 'neutral',
      });
    }

    if (maxRow && primaryCategoryCol && maxVal !== -Infinity) {
      const topEntity = String(maxRow[primaryCategoryCol] ?? '');
      if (topEntity && topEntity.length <= 25) {
        metrics.push({
          label: `Top by ${primaryNumericCol.replace(/_/g, ' ')}`,
          value: topEntity,
          context: isCurrency ? `$${maxVal.toLocaleString()}` : `${maxVal.toLocaleString()}`,
          trend: 'up',
        });
      }
    }
  }

  return metrics.slice(0, 4);
}

/**
 * Main parser that parses Markdown agent output into a structured AnalyticalReport.
 */
export function parseAnalyticalReport(markdown: string): AnalyticalReport {
  if (!markdown || !markdown.trim()) {
    return {
      summary: '',
      metrics: [],
      tableData: null,
      chartRecommendation: null,
      insights: [],
      isStructuredReport: false,
      isEmptyResult: false,
      rawMarkdown: markdown,
    };
  }

  // 1. Check for empty database results
  const lower = markdown.toLowerCase();
  const isEmptyResult =
    lower.includes('0 records') ||
    lower.includes('no records found') ||
    lower.includes('no data found') ||
    lower.includes('query returned 0 rows') ||
    lower.includes('no matching records');

  // 2. Extract sections based on headers
  const sections = extractSections(markdown);

  // Summary
  let summary = '';
  if (sections['summary'] && sections['summary'].length > 0) {
    summary = sections['summary'].join('\n').trim();
  }

  // Metrics
  let metrics: MetricCardItem[] = [];
  if (sections['metrics'] && sections['metrics'].length > 0) {
    metrics = parseMetrics(sections['metrics']);
  }

  // Insights
  let insights: AnalyticalInsightItem[] = [];
  if (sections['insights'] && sections['insights'].length > 0) {
    insights = parseInsights(sections['insights']);
  }

  // Visual & Table Detection
  const visual = detectVisualData(markdown);
  const tableData = visual.tableData;
  const chartRecommendation = visual.chartRecommendation;

  // Fallback for summary if explicit section not found
  if (!summary && visual.textBefore) {
    summary = visual.textBefore;
  }

  // Fallback for insights if explicit section not found
  if (insights.length === 0 && visual.textAfter) {
    const afterLines = visual.textAfter.split('\n');
    insights = parseInsights(afterLines);
  }

  // If no explicit metrics were supplied but table exists, auto-derive KPI metrics
  if (metrics.length === 0 && tableData && tableData.rows.length > 0) {
    metrics = deriveMetricsFromTable(tableData);
  }

  const isStructuredReport =
    Boolean(tableData && tableData.rows.length > 0) ||
    metrics.length > 0 ||
    insights.length > 0 ||
    isEmptyResult;

  return {
    summary,
    metrics,
    tableData,
    chartRecommendation,
    insights,
    isStructuredReport,
    isEmptyResult,
    rawMarkdown: markdown,
  };
}
