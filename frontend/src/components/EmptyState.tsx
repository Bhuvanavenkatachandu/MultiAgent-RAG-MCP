import React from 'react';
import { Database, SearchX, HelpCircle } from 'lucide-react';

interface EmptyStateProps {
  message?: string;
  onExploreSchema?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ message }) => {
  return (
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
};
