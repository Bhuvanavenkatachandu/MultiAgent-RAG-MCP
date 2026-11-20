import React from 'react';
import { ParsedTableData } from '../utils/chartDetector';

interface DataTableProps {
  data: ParsedTableData;
}

export const DataTable: React.FC<DataTableProps> = ({ data }) => {
  if (!data || !data.headers || data.headers.length === 0) return null;

  return (
    <div className="w-full my-4 overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs md:text-sm">
          <thead>
            <tr className="bg-slate-100/80 dark:bg-slate-800/80 border-b border-slate-200 dark:border-slate-800 font-semibold text-slate-700 dark:text-slate-300">
              {data.headers.map((header, idx) => (
                <th key={idx} className="px-4 py-3 whitespace-nowrap">
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-mono text-slate-600 dark:text-slate-300">
            {data.rows.map((row, rowIdx) => (
              <tr
                key={rowIdx}
                className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 transition-colors"
              >
                {data.headers.map((header, colIdx) => {
                  const val = String(row[header] ?? '');
                  const isNumber = !isNaN(Number(val.replace(/[$€£₹,]/g, '')));
                  return (
                    <td
                      key={colIdx}
                      className={`px-4 py-2.5 whitespace-nowrap ${
                        isNumber ? 'text-right' : 'text-left'
                      }`}
                    >
                      {val}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="px-4 py-2 bg-slate-50/60 dark:bg-slate-900/60 border-t border-slate-200 dark:border-slate-800 text-[11px] text-slate-400 dark:text-slate-500 flex justify-between">
        <span>{data.rows.length} records</span>
        <span>PostgreSQL Query Result</span>
      </div>
    </div>
  );
};
