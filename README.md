# 🧠 MultiAgent-RAG-MCP

A hierarchical **multi-agent AI system** that lets you chat with your **PostgreSQL e-commerce database** and **uploaded documents** using natural language. Powered by LangGraph, MCP (Model Context Protocol), FAISS vector search, Groq LLMs, and a React + Recharts frontend.

---

## 📖 Project Overview

This project answers questions like:

> *"Who are the top 5 customers by spending?"*  
> *"What is the return policy mentioned in the uploaded document?"*  
> *"Show me the revenue breakdown by product category."*

The system automatically decides whether to query the **live PostgreSQL database** or **search the document knowledge base** — or both — and returns a clear, structured answer, optionally rendered as an interactive chart.

---

## 🧩 Problem Being Solved

Normally, to get answers from a database or a document, a developer must:

1. Write SQL queries manually
2. Parse and read PDF/DOCX files manually
3. Build separate tools for database vs. document search

This system **unifies** all of that behind a single chat interface. You type a question in plain English and the multi-agent system handles routing, SQL generation, document retrieval, and answer synthesis automatically.

---

## ✅ Implemented Features

| Feature | Status |
|---|---|
| Multi-agent supervisor routing (LangGraph) | ✅ Implemented |
| PostgreSQL queries via MCP (`mcp-postgres-server`) | ✅ Implemented |
| Schema inspection (list schemas, tables, columns) | ✅ Implemented |
| Read-only SQL query execution | ✅ Implemented |
| Analytics & aggregation queries | ✅ Implemented |
| Document upload (PDF, DOCX, TXT, MD) | ✅ Implemented |
| FAISS local vector store with HuggingFace embeddings | ✅ Implemented |
| RAG retrieval from uploaded documents | ✅ Implemented |
| Auto-rebuild FAISS index on document upload | ✅ Implemented |
| FastAPI REST API backend | ✅ Implemented |
| React + Vite + TypeScript frontend | ✅ Implemented |
| Interactive charts (Bar, Line, Pie, Area via Recharts) | ✅ Implemented |
| Markdown table → chart auto-detection | ✅ Implemented |
| Dark/Light mode toggle | ✅ Implemented |
| Conversation history context (last 8 messages) | ✅ Implemented |
| Terminal CLI mode | ✅ Implemented |
| E-commerce PostgreSQL database (100 users, 2,530+ records) | ✅ Implemented |

---

## 🛠️ Technologies Used

| Technology | Why It's Used |
|---|---|
| **Python 3.14** | Backend language; modern async support |
| **FastAPI** | High-performance REST API for the chat, upload, and health endpoints |
| **LangGraph** | Builds the multi-agent supervisor that routes questions to specialist agents |
| **LangChain** | Provides the tool-calling framework and agent utilities |
| **Groq + `langchain-groq`** | Cloud LLM API for fast inference (default model: `openai/gpt-oss-120b`) |
| **MCP (`mcp-postgres-server`)** | Model Context Protocol — exposes PostgreSQL as AI-readable tools |
| **`langchain-mcp-adapters`** | Bridges MCP tools into LangChain-compatible tool format |
| **FAISS** | Local vector store for fast semantic document search |
| **HuggingFace Embeddings** | `sentence-transformers/all-MiniLM-L6-v2` model, runs on CPU, free |
| **`uv`** | Fast Python package manager and project runner |
| **React 18** | Frontend UI framework |
| **Vite** | Fast frontend build tool and dev server |
| **TypeScript** | Type-safe JavaScript for the frontend |
| **Recharts** | Charts rendered from AI-returned markdown tables |
| **Tailwind CSS** | Utility-first CSS framework for styling |
| **PostgreSQL (Neon)** | Cloud-hosted relational database (or any PostgreSQL instance) |

---

## 🏗️ Architecture & Workflow

```
User Question (browser or terminal)
         │
         ▼
   FastAPI /api/chat
         │
         ▼
   Supervisor Agent  (LangGraph ReAct)
   ┌──────────────────────────────────────┐
   │  Decides which agent(s) to use:      │
   │                                      │
   │  ask_schema_agent   ──► Schema Agent │  → list_schemas, list_tables, describe_table
   │  ask_query_agent    ──► Query Agent  │  → query (read-only SQL)
   │  ask_analytics_agent ► Analytics    │  → query, list_tables, describe_table
   │  ask_rag_agent      ──► RAG Agent   │  → search_knowledge_base (FAISS)
   └──────────────────────────────────────┘
         │
         ▼
   Final Answer → Frontend → Rendered as markdown, table, or chart
```

**Document Upload Flow:**
```
User uploads PDF/DOCX/TXT/MD
         │
         ▼
   /api/upload  (FastAPI)
         │  extracts text if DOCX
         ▼
   rag/documents/ (saved to disk)
         │
         ▼
   load_documents() → split into 500-char chunks (100 overlap)
         │
         ▼
   HuggingFace Embeddings (all-MiniLM-L6-v2)
         │
         ▼
   FAISS index (.faiss_index/) saved locally
         │
         ▼
   Supervisor rebuilt with fresh RAG tool
```

---

## 📁 Folder Structure

```
MultiAgent-RAG-MCP/
├── README.md                        ← You are here
├── PROJECT_LEARNING_GUIDE.html      ← Standalone learning guide
├── ecommerce_db.sql                 ← Root copy of DB schema + seed data
├── start.sh                         ← One-command local startup script
│
├── backend/                         ← Python backend
│   ├── pyproject.toml               ← uv project definition + dependencies
│   ├── requirements.txt             ← pip-compatible requirements for cloud
│   ├── ecommerce_db.sql             ← Backend copy of DB schema
│   └── src/
│       └── mcp_using_langchain/
│           ├── server.py            ← FastAPI app + API endpoints
│           ├── main.py              ← Terminal CLI chat mode
│           ├── agents/
│           │   ├── supervisor.py    ← LangGraph supervisor agent
│           │   ├── database_agent.py← Schema, Query, Analytics agents
│           │   └── rag_agent.py     ← RAG document search agent
│           ├── mcp/
│           │   └── postgres_client.py ← MCP client (mcp-postgres-server)
│           └── rag/
│               ├── loader.py        ← Loads PDF, TXT, MD files
│               ├── embeddings.py    ← HuggingFace embedding model
│               ├── vectorstore.py   ← FAISS create/load/save
│               ├── retriever.py     ← Chunking + retriever setup
│               └── documents/       ← Drop your files here for RAG
│
└── frontend/                        ← React frontend
    ├── package.json                 ← Node.js dependencies
    ├── vite.config.ts               ← Vite + proxy config
    ├── tailwind.config.js           ← Tailwind CSS config
    └── src/
        ├── App.tsx                  ← Main application root
        ├── components/
        │   ├── ChatMessage.tsx      ← Message rendering + charts
        │   ├── ChatInput.tsx        ← Input bar
        │   ├── Sidebar.tsx          ← Sidebar with docs list
        │   ├── FileUpload.tsx       ← File upload widget
        │   ├── DynamicChart.tsx     ← Recharts chart renderer
        │   └── DataTable.tsx        ← Table renderer
        ├── services/
        │   └── api.ts               ← API calls to backend
        └── utils/
            └── chartDetector.ts     ← Parses markdown tables → chart data
```

---

## 🔧 Prerequisites

Install these tools before starting:

| Tool | Version | Install |
|---|---|---|
| **Python** | 3.14+ | [python.org](https://www.python.org/downloads/) |
| **uv** | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Node.js** | 18+ | [nodejs.org](https://nodejs.org/) |
| **npm** | bundled with Node.js | — |
| **npx** | bundled with npm | — |
| **psql** | any recent | Install PostgreSQL client |

You also need:
- A **Groq API key** — get it free at [console.groq.com](https://console.groq.com)
- A **PostgreSQL database URL** — Neon (free tier), Supabase, or local PostgreSQL

---

## ⚙️ Environment Variable Setup

### Backend — create `backend/.env`

```env
# Required: Groq LLM API key
GROQ_API_KEY=your_groq_api_key_here

# Optional: Groq model name (default shown below)
GROQ_MODEL=openai/gpt-oss-120b

# Required: PostgreSQL connection string
DATABASE_URL=postgresql://user:password@host:port/dbname

# Optional: Allow write SQL (default false — keep false for safety)
PG_ALLOW_WRITE=false

# Optional: Force FAISS index rebuild on startup
REBUILD_VECTORSTORE=false

# Optional: Backend port (default 8001)
PORT=8001
```

> **Never commit your `.env` file.** It is listed in `.gitignore`.

### Frontend — create `frontend/.env` (optional for local dev)

```env
# Backend URL — only needed if not using Vite proxy (e.g. for cloud deployment)
VITE_API_URL=http://localhost:8001
```

For **local development**, the Vite proxy in `vite.config.ts` automatically forwards `/api` requests to `http://localhost:8001`, so you do not need `VITE_API_URL` locally.

---

## 🗄️ PostgreSQL Setup

### Seed the database (100 users, 2,530+ records, 11 tables)

Run this command once to populate your PostgreSQL instance:

```bash
psql "$DATABASE_URL" -f ecommerce_db.sql
```

Replace `$DATABASE_URL` with your actual connection string if not set as an environment variable, for example:

```bash
psql "postgresql://user:password@host:5432/dbname" -f ecommerce_db.sql
```

The script creates these tables: `users`, `addresses`, `categories`, `products`, `carts`, `cart_items`, `orders`, `order_items`, `payments`, `shipments`, `reviews`.

---

## 🚀 Running Locally

### Option A — One command (recommended)

```bash
./start.sh
```

This starts:
- **Backend** at `http://localhost:8001`
- **Frontend** at `http://localhost:5173`

Press `Ctrl + C` to stop both.

### Option B — Two separate terminals

**Terminal 1 — Backend:**
```bash
cd backend
uv run mcp-server
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm install        # First time only
npm run dev
```

Then open your browser at: **http://localhost:5173**

### Option C — Terminal CLI (no browser)

```bash
cd backend
uv run python -m mcp_using_langchain.main
```

This starts an interactive terminal where you type questions and get answers directly.

---

## 📄 How to Upload Documents and Ask Questions

### Upload via the web interface

1. Open **http://localhost:5173**
2. Click the **sidebar** (top-left ☰ on mobile)
3. Find the **Upload Document** section
4. Select a `.pdf`, `.docx`, `.txt`, or `.md` file
5. Wait for the confirmation message: *"File uploaded and indexed successfully"*
6. Ask questions in the chat about the document content

### Drop files directly

You can also drop files directly into:
```
backend/src/mcp_using_langchain/rag/documents/
```
Then restart the backend with `REBUILD_VECTORSTORE=true` in your `.env`.

---

## 💬 Example Questions

**Database questions:**
- `Who are the top 5 customers with the highest total spending? Show their names, email, and amount.`
- `What is the total revenue and order item count for each product category? Display as a comparison table.`
- `What is the distribution of orders by their status? Provide a breakdown table.`
- `List all products in the Electronics category with their price and stock.`
- `Show me all orders placed in November 2026 with their status.`
- `Which product has the highest average rating?`

**Schema questions:**
- `What tables exist in this database?`
- `Describe the structure of the orders table.`
- `What columns does the users table have?`

**Document questions:**
- `What business rules are defined in the knowledge base documents?`
- `What is the return policy?`
- `Summarize the database schema document.`

---

## ☁️ Cloud Deployment

### Deploy Backend (Render, Railway, Fly.io, etc.)

- **Root Directory**: `backend`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `PYTHONPATH=src uvicorn mcp_using_langchain.server:app --host 0.0.0.0 --port $PORT`
- **Environment Variables**: `GROQ_API_KEY`, `GROQ_MODEL`, `DATABASE_URL`, `PG_ALLOW_WRITE`

### Deploy Frontend (Vercel, Netlify, Cloudflare Pages)

- **Root Directory**: `frontend`
- **Framework Preset**: `Vite`
- **Build Command**: `npm run build`
- **Output Directory**: `dist`
- **Environment Variables**: `VITE_API_URL=https://your-backend-url.com`

---

## 🐛 Common Errors & Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'mcp_using_langchain'` | `src` folder not in `PYTHONPATH` during deployment | Add `PYTHONPATH=src` to the start command: `PYTHONPATH=src uvicorn mcp_using_langchain.server:app --host 0.0.0.0 --port $PORT` or run `pip install -e .` |
| `GROQ_API_KEY is missing from environment` | `.env` not found or empty | Create `backend/.env` with your Groq key |
| `DATABASE_URL is missing from .env` | PostgreSQL URL not set | Add `DATABASE_URL=postgresql://...` to `backend/.env` |
| `No documents found inside rag/documents/` | No files in the RAG folder | Add at least one `.txt`, `.pdf`, or `.md` file to `backend/src/mcp_using_langchain/rag/documents/` |
| `No PostgreSQL MCP tools found` | MCP server failed to start | Ensure `npx` is in your PATH; run `npx -y mcp-postgres-server` manually to test |
| `FAISS index does not exist. Build it first.` | No FAISS index built yet | Set `REBUILD_VECTORSTORE=true` in `.env` or upload a document via the UI |
| `Port 8001 already in use` | Another process on port 8001 | Change `PORT=8002` in `.env`, or kill the other process |
| Backend shows `503 Supervisor not initialized` | Agents not ready yet | Backend is still starting; wait a moment and retry |
| Frontend shows `Backend connection warning` | Backend not running | Start the backend first with `uv run mcp-server` |
| `npx: command not found` | Node.js/npm not installed | Install Node.js from [nodejs.org](https://nodejs.org) |
| Vite proxy error in frontend | Backend not running | Ensure `cd backend && uv run mcp-server` is running before starting frontend |

---

## 🔮 Future Improvements

These features are **not yet implemented** and are planned for future versions:

- [ ] **User authentication** — login/logout, user sessions
- [ ] **Write operations** — ability to INSERT/UPDATE/DELETE via chat (with confirmation)
- [ ] **Multi-database support** — switch between multiple database connections
- [ ] **Persistent conversation history** — save and resume chat sessions
- [ ] **Cloud vector store** — replace local FAISS with pgvector (PostgreSQL extension) or Pinecone
- [ ] **Streaming responses** — show LLM output word by word (like ChatGPT)
- [ ] **Agent memory** — remember context across separate chat sessions
- [ ] **More chart types** — scatter plots, heatmaps, combined charts
- [ ] **Export functionality** — download query results as CSV or PDF
- [ ] **Role-based access** — admin vs. read-only user permissions
- [ ] **Docker support** — containerized deployment with `docker-compose`
- [ ] **More LLM providers** — OpenAI, Anthropic, local models via Ollama

---

## 👨‍💻 Author

**Bhuvana Venkata Chandu**  
GitHub: [Bhuvanavenkatachandu/MultiAgent-RAG-MCP](https://github.com/Bhuvanavenkatachandu/MultiAgent-RAG-MCP)
