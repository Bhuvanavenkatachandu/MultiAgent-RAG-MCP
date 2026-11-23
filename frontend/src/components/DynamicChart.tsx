import React, { useState } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import {
  BarChart2,
  LineChart as LineIcon,
  PieChart as PieIcon,
  TrendingUp,
  Table as TableIcon,
} from 'lucide-react';
import { ChartRecommendation, ChartType, ParsedTableData } from '../utils/reportParser';
import { DataTable } from './DataTable';

interface DynamicChartProps {
  tableData: ParsedTableData;
  recommendation: ChartRecommendation;
}

const COLOR_PALETTE = [
  '#10b981', // emerald
  '#3b82f6', // blue
  '#8b5cf6', // violet
  '#f59e0b', // amber
  '#06b6d4', // cyan
  '#ec4899', // pink
  '#f97316', // orange
  '#6366f1', // indigo
];

function formatTooltipValue(value: any, name: any): [string, string] {
  const labelStr = String(name || '').replace(/_/g, ' ');
  const lower = labelStr.toLowerCase();

  if (typeof value === 'number') {
    if (lower.includes('revenue') || lower.includes('sales') || lower.includes('spent') || lower.includes('price') || lower.includes('amount') || lower.includes('cost')) {
      return [`$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, labelStr];
    }
    if (lower.includes('rate') || lower.includes('percent') || lower.includes('share') || lower.includes('margin')) {
      return [`${value.toFixed(1)}%`, labelStr];
    }
    return [value.toLocaleString(), labelStr];
  }

  return [String(value), labelStr];
}

export const DynamicChart: React.FC<DynamicChartProps> = ({ tableData, recommendation }) => {
  const [selectedType, setSelectedType] = useState<ChartType | 'table'>(recommendation.type);

  // Sanitize numeric data for recharts
  const chartData = tableData.rows.map((row) => {
    const item: Record<string, any> = {
      [recommendation.categoryKey]: String(row[recommendation.categoryKey] ?? ''),
    };

    recommendation.dataKeys.forEach((key) => {
      const rawVal = String(row[key] ?? '');
      const cleaned = rawVal.replace(/[$€£₹,]/g, '').replace(/%/g, '').trim();
      const num = Number(cleaned);
      item[key] = isNaN(num) ? 0 : num;
    });

    return item;
  });

  const categoryKey = recommendation.categoryKey;
  const primaryDataKey = recommendation.dataKeys[0] || 'value';

  // For pie charts with more than 7 slices, aggregate tail items into "Other" to avoid overcrowding
  const pieData = React.useMemo(() => {
    if (chartData.length <= 7) return chartData;
    const sorted = [...chartData].sort((a, b) => (b[primaryDataKey] || 0) - (a[primaryDataKey] || 0));
    const top6 = sorted.slice(0, 6);
    const otherSum = sorted.slice(6).reduce((acc, curr) => acc + (curr[primaryDataKey] || 0), 0);
    return [
      ...top6,
      {
        [categoryKey]: 'Other',
        [primaryDataKey]: otherSum,
      },
    ];
  }, [chartData, primaryDataKey, categoryKey]);

  return (
    <div className="my-4 w-full rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs p-4 md:p-5 transition-all">
      {/* Header and Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3.5 border-b border-slate-100 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <h4 className="text-xs md:text-sm font-semibold text-slate-800 dark:text-slate-200 capitalize">
              {primaryDataKey.replace(/_/g, ' ')} by {categoryKey.replace(/_/g, ' ')}
            </h4>
          </div>
          <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5 ml-4">
            Interactive visualization based on live query results
          </p>
        </div>

        {/* Chart View Switcher */}
        <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800/80 p-1 rounded-xl text-xs">
          <button
            onClick={() => setSelectedType('bar')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-medium transition-all cursor-pointer ${
              selectedType === 'bar'
                ? 'bg-white dark:bg-slate-700 text-emerald-600 dark:text-emerald-400 shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
            title="Bar Chart"
          >
            <BarChart2 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Bar</span>
          </button>

          <button
            onClick={() => setSelectedType('line')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-medium transition-all cursor-pointer ${
              selectedType === 'line'
                ? 'bg-white dark:bg-slate-700 text-emerald-600 dark:text-emerald-400 shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
            title="Line Chart"
          >
            <LineIcon className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Line</span>
          </button>

          <button
            onClick={() => setSelectedType('area')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-medium transition-all cursor-pointer ${
              selectedType === 'area'
                ? 'bg-white dark:bg-slate-700 text-emerald-600 dark:text-emerald-400 shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
            title="Area Chart"
          >
            <TrendingUp className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Area</span>
          </button>

          <button
            onClick={() => setSelectedType('pie')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-medium transition-all cursor-pointer ${
              selectedType === 'pie'
                ? 'bg-white dark:bg-slate-700 text-emerald-600 dark:text-emerald-400 shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
            title="Pie Chart"
          >
            <PieIcon className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Pie</span>
          </button>

          <div className="w-px h-3.5 bg-slate-300 dark:bg-slate-700 mx-0.5" />

          <button
            onClick={() => setSelectedType('table')}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg font-medium transition-all cursor-pointer ${
              selectedType === 'table'
                ? 'bg-white dark:bg-slate-700 text-emerald-600 dark:text-emerald-400 shadow-xs'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
            }`}
            title="View Raw Table"
          >
            <TableIcon className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Table</span>
          </button>
        </div>
      </div>

      {/* Visualization Canvas */}
      <div className="mt-4 w-full h-72 sm:h-80">
        {selectedType === 'table' ? (
          <div className="h-full overflow-y-auto">
            <DataTable data={tableData} />
          </div>
        ) : selectedType === 'pie' ? (
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Tooltip
                formatter={formatTooltipValue}
                contentStyle={{
                  backgroundColor: 'rgba(15, 23, 42, 0.95)',
                  borderColor: '#334155',
                  borderRadius: '0.75rem',
                  color: '#fff',
                  fontSize: '12px',
                  boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
                }}
              />
              <Legend verticalAlign="bottom" height={36} wrapperStyle={{ fontSize: '11px' }} />
              <Pie
                data={pieData}
                dataKey={primaryDataKey}
                nameKey={categoryKey}
                cx="50%"
                cy="50%"
                outerRadius={95}
                innerRadius={50}
                paddingAngle={3}
                label={({ name, percent }) =>
                  typeof percent === 'number' ? `${String(name).slice(0, 10)} (${(percent * 100).toFixed(0)}%)` : String(name)
                }
              >
                {pieData.map((_, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={COLOR_PALETTE[index % COLOR_PALETTE.length]}
                  />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        ) : selectedType === 'line' ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 30 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#64748b" opacity={0.15} />
              <XAxis
                dataKey={categoryKey}
                tick={{ fontSize: 10 }}
                tickFormatter={(val) => (typeof val === 'string' && val.length > 12 ? `${val.slice(0, 10)}...` : String(val))}
                stroke="#94a3b8"
                interval={0}
                angle={-20}
                textAnchor="end"
              />
              <YAxis
                tick={{ fontSize: 10 }}
                stroke="#94a3b8"
                tickFormatter={(val) => (typeof val === 'number' ? val.toLocaleString() : String(val))}
              />
              <Tooltip
                formatter={formatTooltipValue}
                contentStyle={{
                  backgroundColor: 'rgba(15, 23, 42, 0.95)',
                  borderColor: '#334155',
                  borderRadius: '0.75rem',
                  color: '#fff',
                  fontSize: '12px',
                }}
              />
              <Legend verticalAlign="top" height={30} wrapperStyle={{ fontSize: '11px' }} />
              {recommendation.dataKeys.map((key, idx) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={COLOR_PALETTE[idx % COLOR_PALETTE.length]}
                  strokeWidth={2.5}
                  dot={{ r: 4 }}
                  activeDot={{ r: 6 }}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        ) : selectedType === 'area' ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 30 }}>
              <defs>
                {recommendation.dataKeys.map((key, idx) => (
                  <linearGradient key={`grad-${key}`} id={`areaGrad-${idx}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={COLOR_PALETTE[idx % COLOR_PALETTE.length]} stopOpacity={0.6} />
                    <stop offset="95%" stopColor={COLOR_PALETTE[idx % COLOR_PALETTE.length]} stopOpacity={0.05} />
                  </linearGradient>
                ))}
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#64748b" opacity={0.15} />
              <XAxis
                dataKey={categoryKey}
                tick={{ fontSize: 10 }}
                tickFormatter={(val) => (typeof val === 'string' && val.length > 12 ? `${val.slice(0, 10)}...` : String(val))}
                stroke="#94a3b8"
                interval={0}
                angle={-20}
                textAnchor="end"
              />
              <YAxis
                tick={{ fontSize: 10 }}
                stroke="#94a3b8"
                tickFormatter={(val) => (typeof val === 'number' ? val.toLocaleString() : String(val))}
              />
              <Tooltip
                formatter={formatTooltipValue}
                contentStyle={{
                  backgroundColor: 'rgba(15, 23, 42, 0.95)',
                  borderColor: '#334155',
                  borderRadius: '0.75rem',
                  color: '#fff',
                  fontSize: '12px',
                }}
              />
              <Legend verticalAlign="top" height={30} wrapperStyle={{ fontSize: '11px' }} />
              {recommendation.dataKeys.map((key, idx) => (
                <Area
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={COLOR_PALETTE[idx % COLOR_PALETTE.length]}
                  fill={`url(#areaGrad-${idx})`}
                  strokeWidth={2}
                />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          /* Default: Bar Chart */
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 30 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#64748b" opacity={0.15} />
              <XAxis
                dataKey={categoryKey}
                tick={{ fontSize: 10 }}
                tickFormatter={(val) => (typeof val === 'string' && val.length > 12 ? `${val.slice(0, 10)}...` : String(val))}
                stroke="#94a3b8"
                interval={0}
                angle={-20}
                textAnchor="end"
              />
              <YAxis
                tick={{ fontSize: 10 }}
                stroke="#94a3b8"
                tickFormatter={(val) => (typeof val === 'number' ? val.toLocaleString() : String(val))}
              />
              <Tooltip
                formatter={formatTooltipValue}
                contentStyle={{
                  backgroundColor: 'rgba(15, 23, 42, 0.95)',
                  borderColor: '#334155',
                  borderRadius: '0.75rem',
                  color: '#fff',
                  fontSize: '12px',
                }}
              />
              <Legend verticalAlign="top" height={30} wrapperStyle={{ fontSize: '11px' }} />
              {recommendation.dataKeys.map((key, idx) => (
                <Bar
                  key={key}
                  dataKey={key}
                  fill={COLOR_PALETTE[idx % COLOR_PALETTE.length]}
                  radius={[4, 4, 0, 0]}
                  maxBarSize={45}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
};
