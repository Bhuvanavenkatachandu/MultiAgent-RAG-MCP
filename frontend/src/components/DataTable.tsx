import React, { useState, useMemo } from 'react';
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Search,
  Download,
  Copy,
  Check,
  Table as TableIcon,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { ParsedTableData } from '../utils/reportParser';

interface DataTableProps {
  data: ParsedTableData;
  title?: string;
}

function cleanNumericValue(val: any): number | null {
  if (val === null || val === undefined) return null;
  const str = String(val).replace(/[$€£₹,]/g, '').replace(/%/g, '').trim();
  if (str === '' || isNaN(Number(str))) return null;
  return Number(str);
}

export const DataTable: React.FC<DataTableProps> = ({ data, title }) => {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [searchQuery, setSearchQuery] = useState('');
  const [pageSize, setPageSize] = useState<number>(10);
  const [currentPage, setCurrentPage] = useState(1);
  const [copied, setCopied] = useState(false);

  if (!data || !data.headers || data.headers.length === 0) return null;

  // Toggle sorting
  const handleSort = (header: string) => {
    if (sortKey === header) {
      if (sortDir === 'asc') {
        setSortDir('desc');
      } else {
        setSortKey(null);
        setSortDir('asc');
      }
    } else {
      setSortKey(header);
      setSortDir('asc');
    }
    setCurrentPage(1);
  };

  // Filter rows by search query
  const filteredRows = useMemo(() => {
    if (!searchQuery.trim()) return data.rows;
    const query = searchQuery.toLowerCase();
    return data.rows.filter((row) =>
      data.headers.some((h) => String(row[h] ?? '').toLowerCase().includes(query))
    );
  }, [data.rows, data.headers, searchQuery]);

  // Sort rows
  const sortedRows = useMemo(() => {
    if (!sortKey) return filteredRows;
    return [...filteredRows].sort((a, b) => {
      const valA = a[sortKey];
      const valB = b[sortKey];

      const numA = cleanNumericValue(valA);
      const numB = cleanNumericValue(valB);

      if (numA !== null && numB !== null) {
        return sortDir === 'asc' ? numA - numB : numB - numA;
      }

      const strA = String(valA ?? '').toLowerCase();
      const strB = String(valB ?? '').toLowerCase();
      return sortDir === 'asc' ? strA.localeCompare(strB) : strB.localeCompare(strA);
    });
  }, [filteredRows, sortKey, sortDir]);

  // Paginate
  const totalPages = pageSize > 0 ? Math.ceil(sortedRows.length / pageSize) : 1;
  const paginatedRows = useMemo(() => {
    if (pageSize <= 0) return sortedRows;
    const start = (currentPage - 1) * pageSize;
    return sortedRows.slice(start, start + pageSize);
  }, [sortedRows, currentPage, pageSize]);

  // Export to CSV
  const handleExportCSV = () => {
    const csvHeader = data.headers.map((h) => `"${h.replace(/"/g, '""')}"`).join(',');
    const csvRows = sortedRows.map((row) =>
      data.headers.map((h) => `"${String(row[h] ?? '').replace(/"/g, '""')}"`).join(',')
    );
    const csvContent = [csvHeader, ...csvRows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `data_export_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Copy as TSV
  const handleCopy = () => {
    const tsvHeader = data.headers.join('\t');
    const tsvRows = sortedRows.map((row) =>
      data.headers.map((h) => String(row[h] ?? '')).join('\t')
    );
    navigator.clipboard.writeText([tsvHeader, ...tsvRows].join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="w-full my-4 overflow-hidden rounded-2xl border border-slate-200/90 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-xs transition-all">
      {/* Table Toolbar */}
      <div className="p-3 md:p-4 border-b border-slate-100 dark:border-slate-800 flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
            <TableIcon className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-xs md:text-sm font-semibold text-slate-900 dark:text-slate-100">
              {title || 'Structured Data Table'}
            </h4>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              {sortedRows.length} {sortedRows.length === 1 ? 'row' : 'rows'}
              {searchQuery && ` (filtered from ${data.rows.length})`}
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Search Box */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search rows..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setCurrentPage(1);
              }}
              className="pl-8 pr-2.5 py-1 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50/70 dark:bg-slate-800 text-slate-800 dark:text-slate-200 placeholder:text-slate-400 focus:outline-hidden focus:ring-1 focus:ring-emerald-500 w-28 sm:w-36 transition-all"
            />
          </div>

          {/* Copy Button */}
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition-colors cursor-pointer"
            title="Copy as TSV"
          >
            {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
            <span className="hidden sm:inline">{copied ? 'Copied' : 'Copy'}</span>
          </button>

          {/* CSV Export */}
          <button
            onClick={handleExportCSV}
            className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 transition-colors cursor-pointer"
            title="Download CSV"
          >
            <Download className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">CSV</span>
          </button>
        </div>
      </div>

      {/* Table Container */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs md:text-sm">
          <thead>
            <tr className="bg-slate-50/90 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-300 font-semibold select-none">
              {data.headers.map((header, idx) => {
                const isSorted = sortKey === header;
                return (
                  <th
                    key={idx}
                    onClick={() => handleSort(header)}
                    className="px-3.5 py-2.5 whitespace-nowrap cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors group"
                  >
                    <div className="flex items-center justify-between gap-1.5">
                      <span className="capitalize">{header.replace(/_/g, ' ')}</span>
                      <span className="text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-200">
                        {isSorted ? (
                          sortDir === 'asc' ? (
                            <ArrowUp className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                          ) : (
                            <ArrowDown className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
                          )
                        ) : (
                          <ArrowUpDown className="w-3 h-3 opacity-40 group-hover:opacity-100 transition-opacity" />
                        )}
                      </span>
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60 font-sans text-slate-700 dark:text-slate-300">
            {paginatedRows.length === 0 ? (
              <tr>
                <td colSpan={data.headers.length} className="px-4 py-8 text-center text-slate-400 text-xs">
                  No matching records in table
                </td>
              </tr>
            ) : (
              paginatedRows.map((row, rowIdx) => (
                <tr
                  key={rowIdx}
                  className="hover:bg-emerald-500/5 dark:hover:bg-emerald-500/5 transition-colors"
                >
                  {data.headers.map((header, colIdx) => {
                    const val = String(row[header] ?? '');
                    const isNum = cleanNumericValue(val) !== null;
                    return (
                      <td
                        key={colIdx}
                        className={`px-3.5 py-2 whitespace-nowrap text-xs ${
                          isNum ? 'text-right font-mono' : 'text-left'
                        }`}
                      >
                        {val}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      {sortedRows.length > 5 && (
        <div className="px-4 py-2.5 bg-slate-50/70 dark:bg-slate-900/60 border-t border-slate-200 dark:border-slate-800 flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500 dark:text-slate-400">
          <div className="flex items-center gap-1.5">
            <span>Show</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setCurrentPage(1);
              }}
              className="px-1.5 py-0.5 rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-xs"
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={-1}>All</option>
            </select>
            <span>per page</span>
          </div>

          {pageSize > 0 && totalPages > 1 && (
            <div className="flex items-center gap-2">
              <span>
                Page {currentPage} of {totalPages}
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage === 1}
                  className="p-1 rounded-md border border-slate-200 dark:border-slate-700 disabled:opacity-40 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage === totalPages}
                  className="p-1 rounded-md border border-slate-200 dark:border-slate-700 disabled:opacity-40 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                >
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
