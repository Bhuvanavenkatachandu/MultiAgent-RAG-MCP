import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { User, Sparkles, Copy, Check, Terminal } from 'lucide-react';
import { parseAnalyticalReport } from '../utils/reportParser';
import { StructuredReportView } from './StructuredReportView';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  isError?: boolean;
}

interface ChatMessageProps {
  message: Message;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const isUser = message.role === 'user';
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  const handleCopyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  // Inspect message content for structured analytical report
  const report = !isUser && !message.isError ? parseAnalyticalReport(message.content) : null;

  return (
    <div
      className={`py-6 px-4 md:px-6 transition-colors ${
        isUser
          ? 'bg-transparent'
          : 'bg-slate-100/50 dark:bg-slate-900/40 border-y border-slate-200/60 dark:border-slate-800/60'
      }`}
    >
      <div className="max-w-4xl mx-auto flex gap-4 md:gap-5">
        {/* Avatar */}
        <div
          className={`shrink-0 w-8 h-8 rounded-xl flex items-center justify-center text-sm shadow-xs ${
            isUser
              ? 'bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300'
              : message.isError
              ? 'bg-rose-100 dark:bg-rose-950/80 text-rose-600 dark:text-rose-400'
              : 'bg-emerald-600 text-white shadow-emerald-500/20'
          }`}
        >
          {isUser ? (
            <User className="w-4 h-4" />
          ) : message.isError ? (
            <Terminal className="w-4 h-4" />
          ) : (
            <Sparkles className="w-4 h-4" />
          )}
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-hidden space-y-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-900 dark:text-slate-100">
              {isUser ? 'You' : 'PostgreSQL MCP Assistant'}
            </span>
            {message.isError && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-100 dark:bg-rose-950 text-rose-600 dark:text-rose-400 font-medium">
                Error
              </span>
            )}
          </div>

          {/* User message rendering */}
          {isUser ? (
            <p className="text-sm md:text-base text-slate-800 dark:text-slate-200 whitespace-pre-wrap leading-relaxed">
              {message.content}
            </p>
          ) : message.isError ? (
            <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-900 text-rose-700 dark:text-rose-300 text-sm">
              {message.content}
            </div>
          ) : report && report.isStructuredReport ? (
            /* Structured Business Intelligence Report */
            <StructuredReportView report={report} />
          ) : (
            /* Standard Markdown rendering */
            <div className="prose dark:prose-invert prose-sm md:prose-base max-w-none text-slate-800 dark:text-slate-200 leading-relaxed">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  // Code block with copy button
                  code({ node, className, children, ...props }: any) {
                    const match = /language-(\w+)/.exec(className || '');
                    const codeString = String(children).replace(/\n$/, '');
                    const isInline = !match && !String(children).includes('\n');

                    if (isInline) {
                      return (
                        <code
                          className="px-1.5 py-0.5 rounded-md bg-slate-200/70 dark:bg-slate-800 font-mono text-xs text-emerald-600 dark:text-emerald-400"
                          {...props}
                        >
                          {children}
                        </code>
                      );
                    }

                    return (
                      <div className="relative my-3 rounded-xl overflow-hidden border border-slate-200 dark:border-slate-800 bg-slate-900 text-slate-100 font-mono text-xs">
                        <div className="flex items-center justify-between px-3.5 py-2 bg-slate-950/70 border-b border-slate-800 text-[11px] text-slate-400">
                          <span>{match ? match[1] : 'code'}</span>
                          <button
                            onClick={() => handleCopyCode(codeString)}
                            className="flex items-center gap-1 hover:text-white transition-colors"
                          >
                            {copiedCode === codeString ? (
                              <>
                                <Check className="w-3.5 h-3.5 text-emerald-400" />
                                <span>Copied</span>
                              </>
                            ) : (
                              <>
                                <Copy className="w-3.5 h-3.5" />
                                <span>Copy</span>
                              </>
                            )}
                          </button>
                        </div>
                        <pre className="p-3.5 overflow-x-auto">
                          <code>{codeString}</code>
                        </pre>
                      </div>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
