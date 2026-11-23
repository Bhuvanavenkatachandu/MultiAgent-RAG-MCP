import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Sparkles, FileText } from 'lucide-react';

interface ExecutiveSummaryProps {
  summary: string;
}

export const ExecutiveSummary: React.FC<ExecutiveSummaryProps> = ({ summary }) => {
  if (!summary || !summary.trim()) return null;

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
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {summary}
        </ReactMarkdown>
      </div>
    </div>
  );
};
