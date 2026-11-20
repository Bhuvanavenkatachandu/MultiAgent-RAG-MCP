# PostgreSQL RAG MCP Multi-Agent System

A hierarchical multi-agent system combining **PostgreSQL database queries** via the Model Context Protocol (MCP) and **document retrieval** with FAISS RAG, featuring an interactive React + Recharts frontend.

The project is structured into independent **`backend/`** and **`frontend/`** folders for simplified modular deployment.

---

## 📁 Repository Structure

```text
MultiAgent-RAG-MCP/
├── backend/                    # Python Backend (FastAPI + LangGraph + MCP + FAISS)
│   ├── src/
│   │   └── mcp_using_langchain/
│   │       ├── server.py       # FastAPI HTTP REST API
│   │       ├── main.py         # Terminal CLI chat loop
│   │       ├── agents/         # Supervisor, Database, and RAG agents
│   │       ├── mcp/            # PostgreSQL MCP client
│   │       └── rag/            # Vector store, embeddings, loader
│   ├── pyproject.toml          # uv package definition
│   ├── requirements.txt        # Standard pip requirements for cloud hosting
│   └── ecommerce_db.sql        # Database schema and seed data
│
├── frontend/                   # React Frontend (Vite + TypeScript + Recharts)
│   ├── src/
│   │   ├── components/         # Chat, Charts, Tables, Upload widgets
│   │   ├── services/           # Backend API integration
│   │   └── utils/              # Intelligent chart detection logic
│   ├── package.json            # Node.js dependencies
│   └── vite.config.ts          # Vite build config with backend proxy
│
├── ecommerce_db.sql            # Root copy of database schema and seed data
├── start.sh                    # Single-command local startup script
└── README.md
```

---

## 🚀 Easy Cloud Deployment (No Docker Needed)

### 1. Deploy the Backend (Render, Railway, Fly.io, etc.)
- **Root Directory**: `backend`
- **Python Version**: `3.14` (or 3.11+)
- **Build Command**:
  ```bash
  pip install -r requirements.txt
  ```
- **Start Command**:
  ```bash
  uvicorn mcp_using_langchain.server:app --host 0.0.0.0 --port $PORT
  ```
- **Environment Variables**:
  - `GROQ_API_KEY`: Your Groq API key
  - `GROQ_MODEL`: `openai/gpt-oss-120b` (or your preferred Groq model)
  - `DATABASE_URL`: Your PostgreSQL connection string (e.g. Neon)
  - `PG_ALLOW_WRITE`: `false`

### 2. Deploy the Frontend (Vercel, Netlify, Cloudflare Pages)
- **Root Directory**: `frontend`
- **Framework Preset**: `Vite`
- **Build Command**:
  ```bash
  npm run build
  ```
- **Output Directory**: `dist`
- **Environment Variables**:
  - `VITE_API_URL`: URL of your deployed backend (e.g. `https://your-backend.onrender.com`)

---

## 💻 Local Development

### Option A: Run Both with One Command
```bash
./start.sh
```
Launches backend on `http://localhost:8001` and frontend on `http://localhost:5173`. Press <kbd>Ctrl</kbd> + <kbd>C</kbd> to stop both.

### Option B: Run in Separate Terminals

#### Terminal 1 (Backend):
```bash
cd backend
uv run mcp-server
# Runs FastAPI on http://localhost:8001
```

#### Terminal 2 (Frontend):
```bash
cd frontend
npm run dev
# Runs Vite React app on http://localhost:5173
```

### Option C: Terminal CLI Chat Mode
```bash
cd backend
uv run python -m mcp_using_langchain.main
```

---

## 🗄️ Database Setup & Restoration

To seed or restore your PostgreSQL instance with the 100 users, 11 tables, and 2,530+ e-commerce records:

```bash
psql "$DATABASE_URL" -f ecommerce_db.sql
```
