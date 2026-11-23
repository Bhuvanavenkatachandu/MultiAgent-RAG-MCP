export interface ParsedTableData {
  headers: string[];
  rows: Record<string, any>[];
  rawRows: string[][];
}

export type ChartType = 'bar' | 'line' | 'pie' | 'area';

export interface ChartRecommendation {
  type: ChartType;
  categoryKey: string;
  dataKeys: string[];
  isTimeBased: boolean;
  isDistribution: boolean;
}

export interface DetectedVisual {
  hasVisual: boolean;
  tableData: ParsedTableData | null;
  chartRecommendation: ChartRecommendation | null;
  textBefore: string;
  textAfter: string;
}

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
 * Strips common currencies, commas, and percentage signs to parse clean numbers.
 */
function parseNumericValue(val: string): number | null {
  if (!val || typeof val !== 'string') return null;
  const cleaned = val.replace(/[$€£₹,]/g, '').replace(/%/g, '').trim();
  if (cleaned === '' || isNaN(Number(cleaned))) return null;
  return Number(cleaned);
}

/**
 * Checks if a string represents a date, time, or chronological sequence.
 */
function isDateOrTime(val: string): boolean {
  if (!val) return false;
  const lower = val.toLowerCase();
  const timeKeywords = ['year', 'month', 'day', 'date', 'quarter', 'hour', 'week', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
  return timeKeywords.some((k) => lower.includes(k)) || /^\d{4}[-/]\d{1,2}([-/]\d{1,2})?/.test(val);
}

/**
 * Analyzes markdown content to identify structured tables and recommend visualizations.
 */
export function detectVisualData(markdown: string): DetectedVisual {
  const lines = markdown.split('\n');
  const tableLines: { index: number; line: string }[] = [];
  let tableStartIndex = -1;
  let tableEndIndex = -1;

  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    const isPipeLine =
      !trimmed.startsWith('- ') &&
      !trimmed.startsWith('* ') &&
      (trimmed.startsWith('|') || (trimmed.endsWith('|') && trimmed.split('|').length >= 3));

    if (isPipeLine) {
      if (tableStartIndex === -1) tableStartIndex = i;
      tableLines.push({ index: i, line: trimmed });
      tableEndIndex = i;
    } else {
      if (tableLines.length >= 2) break;
      tableLines.length = 0;
      tableStartIndex = -1;
      tableEndIndex = -1;
    }
  }

  if (tableLines.length < 2 || tableStartIndex === -1) {
    return { hasVisual: false, tableData: null, chartRecommendation: null, textBefore: markdown, textAfter: '' };
  }

  const rawRows: string[][] = [];
  for (const { line } of tableLines) {
    let content = line;
    if (content.startsWith('|')) content = content.slice(1);
    if (content.endsWith('|')) content = content.slice(0, -1);
    rawRows.push(content.split('|').map((c) => c.trim()));
  }

  const headers = rawRows[0];
  if (headers.length < 2) {
    return { hasVisual: false, tableData: null, chartRecommendation: null, textBefore: markdown, textAfter: '' };
  }

  const isSeparatorPresent = rawRows.length > 1 && rawRows[1].every((c) => /^:?-+:?$/.test(c));
  const dataRowsRaw = isSeparatorPresent ? rawRows.slice(2) : rawRows.slice(1);
  if (dataRowsRaw.length === 0) {
    return { hasVisual: false, tableData: null, chartRecommendation: null, textBefore: markdown, textAfter: '' };
  }

  const rows: Record<string, any>[] = dataRowsRaw.map((rowCells) => {
    const rowObj: Record<string, any> = {};
    headers.forEach((header, idx) => {
      rowObj[header] = rowCells[idx] !== undefined ? rowCells[idx] : '';
    });
    return rowObj;
  });

  const tableData: ParsedTableData = { headers, rows, rawRows: dataRowsRaw };

  let categoryKey: string | null = null;
  const numericKeys: string[] = [];

  headers.forEach((header) => {
    let numericCount = 0;
    rows.forEach((r) => {
      if (parseNumericValue(String(r[header])) !== null) numericCount++;
    });
    if (numericCount / rows.length >= 0.7) {
      numericKeys.push(header);
    } else if (!categoryKey) {
      categoryKey = header;
    }
  });

  if (!categoryKey && headers.length > 1) categoryKey = headers[0];

  let chartRecommendation: ChartRecommendation | null = null;
  if (categoryKey && numericKeys.length > 0 && rows.length >= 2) {
    const isTime = isDateOrTime(categoryKey) || rows.some((r) => isDateOrTime(String(r[categoryKey!])));
    const lowerCat = categoryKey.toLowerCase();
    const isDist =
      rows.length >= 2 &&
      rows.length <= 8 &&
      ['status', 'method', 'category', 'type', 'share', 'distribution'].some((k) => lowerCat.includes(k));

    chartRecommendation = {
      type: isTime ? 'line' : isDist ? 'pie' : 'bar',
      categoryKey,
      dataKeys: numericKeys,
      isTimeBased: isTime,
      isDistribution: isDist,
    };
  }

  return {
    hasVisual: true,
    tableData,
    chartRecommendation,
    textBefore: lines.slice(0, tableStartIndex).join('\n').trim(),
    textAfter: lines.slice(tableEndIndex + 1).join('\n').trim(),
  };
}

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

function extractSections(markdown: string): Record<string, string[]> {
  const sections: Record<string, string[]> = {};
  let currentKey = 'intro';

  for (const line of markdown.split('\n')) {
    const headingMatch = line.match(/^#{1,4}\s+(.+)$/);
    if (headingMatch) {
      const heading = headingMatch[1].toLowerCase().trim();
      if (heading.includes('summary') || heading.includes('executive')) currentKey = 'summary';
      else if (heading.includes('metric') || heading.includes('kpi')) currentKey = 'metrics';
      else if (heading.includes('table') || heading.includes('data')) currentKey = 'table';
      else if (heading.includes('insight') || heading.includes('narrative') || heading.includes('takeaway')) currentKey = 'insights';
      else currentKey = heading;
      if (!sections[currentKey]) sections[currentKey] = [];
    } else {
      if (!sections[currentKey]) sections[currentKey] = [];
      sections[currentKey].push(line);
    }
  }
  return sections;
}

function parseMetrics(lines: string[]): MetricCardItem[] {
  const metrics: MetricCardItem[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed.startsWith('-') && !trimmed.startsWith('*')) continue;

    if (trimmed.includes('|')) {
      const parts = trimmed.replace(/^[*-]\s*/, '').split('|').map((p) => p.trim());
      let label = '', value = '', context = '';
      for (const part of parts) {
        if (/^metric\s*:/i.test(part)) label = part.replace(/^metric\s*:/i, '').trim();
        else if (/^value\s*:/i.test(part)) value = part.replace(/^value\s*:/i, '').trim();
        else if (/^context\s*:/i.test(part)) context = part.replace(/^context\s*:/i, '').trim();
        else if (!label) label = part;
        else if (!value) value = part;
        else if (!context) context = part;
      }

      if (label && value) {
        const trend = (value.includes('+') || context.includes('+') || /growth|increase/i.test(context))
          ? 'up'
          : (value.includes('-') || context.includes('-') || /drop|decline/i.test(context))
          ? 'down'
          : 'neutral';
        metrics.push({ label, value, context: context || undefined, trend });
      }
    } else {
      const bulletMatch = trimmed.match(/^[*-]\s*(?:\*\*)?([^:*]+?)(?:\*\*)?:\s*(.+)$/);
      if (bulletMatch) {
        const label = bulletMatch[1].replace(/^metric\s+/i, '').trim();
        let rawVal = bulletMatch[2].trim();
        let context = '';
        const parenMatch = rawVal.match(/^([^()]+)\s*\(([^)]+)\)$/);
        if (parenMatch) {
          rawVal = parenMatch[1].trim();
          context = parenMatch[2].trim();
        }
        if (rawVal.length <= 40 && label.length <= 40) {
          const trend = (context.includes('+') || /growth|up/i.test(context))
            ? 'up'
            : (context.includes('-') || /decline|down/i.test(context))
            ? 'down'
            : 'neutral';
          metrics.push({ label, value: rawVal, context: context || undefined, trend });
        }
      }
    }
  }
  return metrics;
}

function parseInsights(lines: string[]): AnalyticalInsightItem[] {
  const insights: AnalyticalInsightItem[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed.startsWith('-') && !trimmed.startsWith('*')) continue;
    const contentLine = trimmed.replace(/^[*-]\s*/, '').trim();
    const prefixMatch = contentLine.match(/^([A-Za-z\s/]+?):\s*(.+)$/);

    if (prefixMatch) {
      const { type, title } = classifyInsight(prefixMatch[1].trim());
      insights.push({ type, title, content: prefixMatch[2].trim() });
    } else if (contentLine.length > 15) {
      insights.push({ type: 'observation', title: 'Key Finding', content: contentLine });
    }
  }
  return insights;
}

function deriveMetricsFromTable(table: ParsedTableData): MetricCardItem[] {
  if (!table || table.rows.length === 0) return [];
  const metrics: MetricCardItem[] = [
    { label: 'Total Records', value: table.rows.length.toLocaleString(), context: 'Rows retrieved from database', trend: 'neutral' },
  ];

  let primaryNumericCol: string | null = null;
  let primaryCategoryCol: string | null = null;

  for (const h of table.headers) {
    const numericCount = table.rows.filter((r) => parseNumericValue(String(r[h])) !== null).length;
    if (numericCount / table.rows.length >= 0.7 && !primaryNumericCol) {
      primaryNumericCol = h;
    } else if (!primaryCategoryCol) {
      primaryCategoryCol = h;
    }
  }

  if (primaryNumericCol) {
    const isCurrency = table.rows.some((r) => String(r[primaryNumericCol!]).includes('$'));
    const isPercent = table.rows.some((r) => String(r[primaryNumericCol!]).includes('%'));
    let sum = 0, maxVal = -Infinity, maxRow: Record<string, any> | null = null;

    table.rows.forEach((r) => {
      const num = parseNumericValue(String(r[primaryNumericCol!]));
      if (num !== null) {
        sum += num;
        if (num > maxVal) {
          maxVal = num;
          maxRow = r;
        }
      }
    });

    const isSumMeaningful = !/id|year|rate/i.test(primaryNumericCol);
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

  const lower = markdown.toLowerCase();
  const isEmptyResult = ['0 records', 'no records found', 'no data found', 'query returned 0 rows', 'no matching records'].some((k) => lower.includes(k));

  const sections = extractSections(markdown);
  let summary = sections['summary'] ? sections['summary'].join('\n').trim() : '';
  let metrics = sections['metrics'] ? parseMetrics(sections['metrics']) : [];
  let insights = sections['insights'] ? parseInsights(sections['insights']) : [];

  const visual = detectVisualData(markdown);
  const tableData = visual.tableData;
  const chartRecommendation = visual.chartRecommendation;

  if (!summary && visual.textBefore) summary = visual.textBefore;
  if (insights.length === 0 && visual.textAfter) insights = parseInsights(visual.textAfter.split('\n'));
  if (metrics.length === 0 && tableData && tableData.rows.length > 0) metrics = deriveMetricsFromTable(tableData);

  const isStructuredReport = Boolean(tableData && tableData.rows.length > 0) || metrics.length > 0 || insights.length > 0 || isEmptyResult;

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
