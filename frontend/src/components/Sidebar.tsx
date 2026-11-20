import React from 'react';
import {
  Database,
  Plus,
  FileText,
  FileCode,
  CheckCircle,
  Moon,
  Sun,
  X,
  RefreshCw,
} from 'lucide-react';
import { DocumentItem } from '../services/api';
import { FileUpload } from './FileUpload';

interface SidebarProps {
  documents: DocumentItem[];
  isLoadingDocs: boolean;
  onRefreshDocs: () => void;
  onNewChat: () => void;
  onUploadSuccess: (filename: string) => void;
  isOpen: boolean;
  onClose: () => void;
  isDarkMode: boolean;
  onToggleTheme: () => void;
  backendHealthy: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({
  documents,
  isLoadingDocs,
  onRefreshDocs,
  onNewChat,
  onUploadSuccess,
  isOpen,
  onClose,
  isDarkMode,
  onToggleTheme,
  backendHealthy,
}) => {
  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getDocIcon = (ext: string) => {
    if (ext === '.pdf') return <FileText className="w-4 h-4 text-rose-500" />;
    if (ext === '.docx') return <FileText className="w-4 h-4 text-blue-500" />;
    return <FileCode className="w-4 h-4 text-emerald-500" />;
  };

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          onClick={onClose}
          className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-40 lg:hidden"
        />
      )}

      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-72 md:w-80 bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col transition-transform duration-200 lg:static lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Header / Brand */}
        <div className="p-4 border-b border-slate-100 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center text-white shadow-sm shadow-emerald-500/20">
              <Database className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold tracking-tight text-slate-900 dark:text-white">
                PostgreSQL MCP
              </h2>
              <div className="flex items-center gap-1.5 text-[11px] text-slate-500 dark:text-slate-400">
                <span
                  className={`w-2 h-2 rounded-full ${
                    backendHealthy ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'
                  }`}
                />
                <span>{backendHealthy ? 'MCP + RAG Ready' : 'Connecting...'}</span>
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 lg:hidden"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Action: New Chat */}
        <div className="p-3">
          <button
            onClick={() => {
              onNewChat();
              onClose();
            }}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700/80 text-slate-700 dark:text-slate-200 text-xs font-semibold transition-all shadow-xs active:scale-98"
          >
            <Plus className="w-4 h-4" />
            <span>New Chat</span>
          </button>
        </div>

        {/* Upload Widget */}
        <div className="px-3 pb-3">
          <FileUpload onUploadSuccess={onUploadSuccess} />
        </div>

        {/* Knowledge Base Document List */}
        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
          <div className="flex items-center justify-between px-2 pb-1.5 text-[11px] font-semibold tracking-wider text-slate-400 dark:text-slate-500 uppercase">
            <span>Indexed Documents ({documents.length})</span>
            <button
              onClick={onRefreshDocs}
              disabled={isLoadingDocs}
              className="hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
              title="Refresh list"
            >
              <RefreshCw className={`w-3 h-3 ${isLoadingDocs ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {documents.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-slate-400 dark:text-slate-500 border border-dashed border-slate-200 dark:border-slate-800 rounded-lg">
              No documents indexed yet.
            </div>
          ) : (
            documents.map((doc) => (
              <div
                key={doc.name}
                className="group flex items-center gap-2.5 p-2 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/60 text-xs text-slate-700 dark:text-slate-300 transition-colors border border-transparent hover:border-slate-200/60 dark:hover:border-slate-700/60"
              >
                <div className="shrink-0">{getDocIcon(doc.extension)}</div>
                <div className="flex-1 min-w-0">
                  <p className="truncate font-medium text-slate-800 dark:text-slate-200 text-xs">
                    {doc.name}
                  </p>
                  <p className="text-[10px] text-slate-400 dark:text-slate-500">
                    {formatFileSize(doc.size_bytes)}
                  </p>
                </div>
                <CheckCircle className="w-3.5 h-3.5 text-emerald-500 shrink-0 opacity-80" />
              </div>
            ))
          )}
        </div>

        {/* Footer / Theme Toggle */}
        <div className="p-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
          <span className="text-[11px]">PostgreSQL MCP • Groq</span>
          <button
            onClick={onToggleTheme}
            className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500 dark:text-slate-400 transition-colors"
            title="Toggle Theme"
          >
            {isDarkMode ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-slate-600" />}
          </button>
        </div>
      </aside>
    </>
  );
};
