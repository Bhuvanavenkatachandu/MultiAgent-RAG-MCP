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

/**
 * Strips common currencies, commas, and percentage signs to parse a clean number.
 */
function parseNumericValue(val: string): number | null {
  if (!val || typeof val !== 'string') return null;
  const cleaned = val.replace(/[$€£₹,]/g, '').replace(/%/g, '').trim();
  if (cleaned === '' || isNaN(Number(cleaned))) return null;
  return Number(cleaned);
}

/**
 * Checks if a string represents time, date, or chronological sequence.
 */
function isDateOrTime(val: string): boolean {
  if (!val) return false;
  const lower = val.toLowerCase();
  const timeKeywords = ['year', 'month', 'day', 'date', 'quarter', 'hour', 'week', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
  if (timeKeywords.some((k) => lower.includes(k))) return true;
  // ISO date like 2026-11-20 or 2024/01/15
  if (/^\d{4}[-/]\d{1,2}([-/]\d{1,2})?/.test(val)) return true;
  return false;
}

/**
 * Analyzes markdown content to find structured tables and recommend appropriate visualizations.
 */
export function detectVisualData(markdown: string): DetectedVisual {
  const lines = markdown.split('\n');
  const tableLines: { index: number; line: string }[] = [];

  // 1. Identify contiguous markdown table lines
  let inTable = false;
  let tableStartIndex = -1;
  let tableEndIndex = -1;

  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    const isPipeLine = trimmed.startsWith('|') || (trimmed.includes('|') && trimmed.split('|').length >= 3);

    if (isPipeLine) {
      if (!inTable) {
        inTable = true;
        tableStartIndex = i;
      }
      tableLines.push({ index: i, line: trimmed });
      tableEndIndex = i;
    } else if (inTable) {
      // Table ended
      break;
    }
  }

  // Need at least header, separator line, and at least 2 data rows for meaningful visual
  if (tableLines.length < 4 || tableStartIndex === -1) {
    return {
      hasVisual: false,
      tableData: null,
      chartRecommendation: null,
      textBefore: markdown,
      textAfter: '',
    };
  }

  // 2. Parse table lines
  const rawRows: string[][] = [];
  for (const { line } of tableLines) {
    // Strip leading and trailing pipes then split
    let content = line;
    if (content.startsWith('|')) content = content.slice(1);
    if (content.endsWith('|')) content = content.slice(0, -1);

    const cells = content.split('|').map((c) => c.trim());
    rawRows.push(cells);
  }

  const headers = rawRows[0];
  const separator = rawRows[1];

  // Validate separator row (e.g. --- | :---: | ---)
  const isSeparatorValid = separator.every((c) => /^:?-+:?$/.test(c));
  if (!isSeparatorValid || headers.length < 2) {
    return {
      hasVisual: false,
      tableData: null,
      chartRecommendation: null,
      textBefore: markdown,
      textAfter: '',
    };
  }

  const dataRowsRaw = rawRows.slice(2);
  const rows: Record<string, any>[] = [];

  for (const rowCells of dataRowsRaw) {
    const rowObj: Record<string, any> = {};
    headers.forEach((header, idx) => {
      rowObj[header] = rowCells[idx] !== undefined ? rowCells[idx] : '';
    });
    rows.push(rowObj);
  }

  const tableData: ParsedTableData = {
    headers,
    rows,
    rawRows: dataRowsRaw,
  };

  // 3. Inspect columns to see if numerical and categorical data exist for charts
  let categoryKey: string | null = null;
  const numericKeys: string[] = [];

  headers.forEach((header) => {
    let numericCount = 0;
    rows.forEach((r) => {
      const num = parseNumericValue(String(r[header]));
      if (num !== null) numericCount++;
    });

    // If more than 70% of rows have valid numbers, consider it a numeric metric column
    if (numericCount / rows.length >= 0.7) {
      numericKeys.push(header);
    } else if (!categoryKey) {
      categoryKey = header;
    }
  });

  // If no category key was assigned, use the first non-numeric or the first column
  if (!categoryKey && headers.length > 1) {
    categoryKey = headers[0];
  }

  let chartRecommendation: ChartRecommendation | null = null;

  // Only recommend a chart if we have at least 1 category key, at least 1 numeric key, and >= 2 rows
  if (categoryKey && numericKeys.length > 0 && rows.length >= 2) {
    const catKey = categoryKey;
    const isTime = isDateOrTime(catKey) || rows.some((r) => isDateOrTime(String(r[catKey])));

    const lowerCat = catKey.toLowerCase();
    const isDist =
      (rows.length >= 2 && rows.length <= 8) &&
      (lowerCat.includes('status') ||
        lowerCat.includes('method') ||
        lowerCat.includes('category') ||
        lowerCat.includes('type') ||
        lowerCat.includes('share') ||
        lowerCat.includes('distribution'));

    let type: ChartType = 'bar';
    if (isTime) {
      type = 'line';
    } else if (isDist) {
      type = 'pie';
    } else {
      type = 'bar';
    }

    chartRecommendation = {
      type,
      categoryKey,
      dataKeys: numericKeys,
      isTimeBased: isTime,
      isDistribution: isDist,
    };
  }

  const textBefore = lines.slice(0, tableStartIndex).join('\n').trim();
  const textAfter = lines.slice(tableEndIndex + 1).join('\n').trim();

  return {
    hasVisual: true,
    tableData,
    chartRecommendation,
    textBefore,
    textAfter,
  };
}
