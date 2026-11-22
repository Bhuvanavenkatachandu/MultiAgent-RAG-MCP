import React, { useState, useEffect, useRef } from 'react';
import {
  Menu,
  Database,
  BarChart2,
  FileQuestion,
  Layers,
  Sparkles,
  Loader2,
} from 'lucide-react';
import { Sidebar } from './components/Sidebar';
import { ChatMessage, Message } from './components/ChatMessage';
import { ChatInput } from './components/ChatInput';
import {
  checkHealth,
  fetchDocuments,
  sendChatMessage,
  sendChatMessageStream,
  DocumentItem,
  ChatMessageItem,
} from './services/api';

const SUGGESTED_QUERIES = [
  {
    icon: <BarChart2 className="w-3.5 h-3.5 text-emerald-500" />,
    title: 'Category Revenue',
    prompt: 'What is the total revenue and order item count for each product category? Display as a comparison table.',
  },
  {
    icon: <Layers className="w-3.5 h-3.5 text-blue-500" />,
    title: 'Order Distribution',
    prompt: 'What is the distribution of orders by their status (DELIVERED, SHIPPED, PENDING, CANCELLED)? Provide a breakdown table.',
  },
  {
    icon: <Database className="w-3.5 h-3.5 text-violet-500" />,
    title: 'Top Customers',
    prompt: 'Who are the top 5 customers with the highest total spending? Show their names, email, and amount.',
  },
  {
    icon: <FileQuestion className="w-3.5 h-3.5 text-amber-500" />,
    title: 'Business Rules',
    prompt: 'What business rules are defined in the knowledge base documents?',
  },
];

export function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState(false);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [streamStatus, setStreamStatus] = useState('');
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [backendHealthy, setBackendHealthy] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(() => {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  const chatContainerRef = useRef<HTMLDivElement>(null);

  // Apply dark mode class to html element
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  // Load backend status and documents on mount
  useEffect(() => {
    loadHealthAndDocs();
  }, []);

  const loadHealthAndDocs = async () => {
    setIsLoadingDocs(true);
    try {
      const health = await checkHealth();
      setBackendHealthy(health.status === 'healthy');
      const docs = await fetchDocuments();
      setDocuments(docs);
    } catch (e) {
      console.warn('Backend connection warning:', e);
      setBackendHealthy(false);
    } finally {
      setIsLoadingDocs(false);
    }
  };

  // Scroll to bottom on new messages
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [messages, isChatLoading]);

  const handleSendMessage = async (text: string) => {
    const userMsgId = String(Date.now());
    const userMessage: Message = {
      id: userMsgId,
      role: 'user',
      content: text,
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsChatLoading(true);
    setStreamStatus('Specialist agents analyzing request...');

    const assistantMsgId = String(Date.now() + 1);
    let assistantMessageCreated = false;
    let accumulatedContent = '';

    try {
      // Build history for follow-up support
      const historyItems: ChatMessageItem[] = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      await sendChatMessageStream(
        text,
        historyItems,
        (token) => {
          accumulatedContent += token;
          if (!assistantMessageCreated) {
            assistantMessageCreated = true;
            setIsChatLoading(false);
            setMessages((prev) => [
              ...prev,
              {
                id: assistantMsgId,
                role: 'assistant',
                content: accumulatedContent,
              },
            ]);
          } else {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantMsgId
                  ? { ...msg, content: accumulatedContent }
                  : msg
              )
            );
          }
        },
        (status) => {
          setStreamStatus(status);
        }
      );

      if (!assistantMessageCreated) {
        setMessages((prev) => [
          ...prev,
          {
            id: assistantMsgId,
            role: 'assistant',
            content: accumulatedContent || 'Unable to generate analysis. Please try rephrasing your query.',
          },
        ]);
      }
    } catch (err: any) {
      const errorMsg: Message = {
        id: String(Date.now() + 2),
        role: 'assistant',
        content: `Error: ${err.message || 'Unable to communicate with the supervisor agent.'}`,
        isError: true,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsChatLoading(false);
      setStreamStatus('');
    }
  };

  const handleNewChat = () => {
    setMessages([]);
  };

  const handleUploadSuccess = () => {
    loadHealthAndDocs();
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-white dark:bg-slate-950 font-sans">
      {/* Sidebar */}
      <Sidebar
        documents={documents}
        isLoadingDocs={isLoadingDocs}
        onRefreshDocs={loadHealthAndDocs}
        onNewChat={handleNewChat}
        onUploadSuccess={handleUploadSuccess}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        isDarkMode={isDarkMode}
        onToggleTheme={() => setIsDarkMode(!isDarkMode)}
        backendHealthy={backendHealthy}
      />

      {/* Main Area */}
      <div className="flex-1 flex flex-col h-full overflow-hidden relative">
        {/* Mobile Header Bar */}
        <header className="lg:hidden flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
          <button
            onClick={() => setIsSidebarOpen(true)}
            className="p-1.5 rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
              PostgreSQL MCP + RAG
            </span>
            <span
              className={`w-2 h-2 rounded-full ${
                backendHealthy ? 'bg-emerald-500' : 'bg-amber-500'
              }`}
            />
          </div>
          <div className="w-5" />
        </header>

        {/* Chat Messages Container */}
        <div ref={chatContainerRef} className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            /* Welcome Area */
            <div className="min-h-full flex flex-col items-center justify-center p-6 text-center max-w-2xl mx-auto">
              <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 flex items-center justify-center mb-4 shadow-sm">
                <Sparkles className="w-6 h-6" />
              </div>
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-slate-900 dark:text-white mb-2">
                PostgreSQL MCP + RAG System
              </h1>
              <p className="text-sm text-slate-500 dark:text-slate-400 mb-8 max-w-lg leading-relaxed">
                Ask analytical queries over your live e-commerce database, inspect schemas, or query your uploaded knowledge base documents.
              </p>

              {/* Suggestion Chips */}
              <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-left">
                {SUGGESTED_QUERIES.map((item, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(item.prompt)}
                    className="p-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/70 hover:bg-slate-100 dark:bg-slate-900/60 dark:hover:bg-slate-800/80 transition-all text-xs group"
                  >
                    <div className="flex items-center gap-2 font-semibold text-slate-800 dark:text-slate-200 mb-1 group-hover:text-emerald-600 dark:group-hover:text-emerald-400">
                      {item.icon}
                      <span>{item.title}</span>
                    </div>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 line-clamp-2">
                      {item.prompt}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* Message List */
            <div className="divide-y divide-transparent">
              {messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}

              {/* Pending Assistant Response Loader */}
              {isChatLoading && (
                <div className="py-6 px-4 md:px-6 bg-slate-100/50 dark:bg-slate-900/40 border-y border-slate-200/60 dark:border-slate-800/60">
                  <div className="max-w-4xl mx-auto flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl bg-emerald-600 text-white flex items-center justify-center">
                      <Sparkles className="w-4 h-4" />
                    </div>
                    <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
                      <Loader2 className="w-4 h-4 animate-spin text-emerald-600 dark:text-emerald-400" />
                      <span>{streamStatus || 'Specialist agents analyzing database & documents...'}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Input Bar */}
        <ChatInput onSendMessage={handleSendMessage} isLoading={isChatLoading} />
      </div>
    </div>
  );
}

export default App;
