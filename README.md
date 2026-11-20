# PostgreSQL RAG MCP Multi-Agent System

A hierarchical multi-agent system combining **PostgreSQL database queries** via the Model Context Protocol (MCP) and **document retrieval** with FAISS RAG, featuring a modern React + Recharts frontend.

## Technologies

- **Backend**: Python 3.14, FastAPI, LangGraph, LangChain, Groq LLM, FAISS Vector Store, HuggingFace Embeddings
- **Database**: PostgreSQL with MCP (`mcp-postgres-server`) via `MultiServerMCPClient`
- **Frontend**: React 18, Vite, TypeScript, Tailwind CSS, Recharts, Lucide Icons

---

## Agents Architecture

```
User / Web Frontend
         │
    Supervisor (LangGraph ReAct)
         ├──── Schema Agent     (PostgreSQL structural inspection)
         ├──── Query Agent      (Read-only SQL retrieval)
         ├──── Analytics Agent  (Aggregations, rankings & totals)
         └──── RAG Agent        (FAISS vector search over PDF, DOCX, TXT, MD)
```

---

## 🗄️ Database Setup & Restoration

The repository includes a complete e-commerce dataset ([ecommerce_db.sql](ecommerce_db.sql)) featuring 11 tables, 100 users, and 2,530+ related records (orders, payments, shipments, products, categories, reviews, carts).

To seed or restore your PostgreSQL database in the future:

```bash
# Seed or restore using your database connection string
psql "$DATABASE_URL" -f ecommerce_db.sql
```

*(You can also load environment variables first if running directly from bash: `export $(grep -v '^#' .env | xargs) && psql "$DATABASE_URL" -f ecommerce_db.sql`)*

---

## Running the Application

### ⚡ Quick Start (Run Both with a Single Command)
```bash
./start.sh
```
This launches both the backend server (`http://localhost:8001`) and frontend app (`http://localhost:5173`), and cleanly closes both when you press <kbd>Ctrl</kbd> + <kbd>C</kbd>.

---

### Separate Terminal Windows

#### Terminal 1: Backend API Server
```bash
uv run mcp-server
# Runs FastAPI on http://localhost:8001
```

#### Terminal 2: Frontend Web Application
```bash
cd frontend
npm run dev
# Runs Vite React app on http://localhost:5173
```

---

### Terminal CLI Mode (Interactive Terminal Chat)
```bash
uv run python -m mcp_using_langchain.main
```
Open **http://localhost:5173** in your browser.

---

## Web Frontend Features

- **Document Upload**: Drag-and-drop or browse PDF and DOCX files to automatically index into the RAG vectorstore.
- **AI Chatbot**: Real-time conversation with the multi-agent supervisor.
- **Dynamic Recharts Visualizations**:
  - Automatically renders **Bar**, **Line**, **Area**, or **Pie** charts when database query results contain numerical & categorical data.
  - Interactive **[Bar | Line | Area | Pie | Table]** view switcher on all data answers.
- **Dark & Light Mode**: Built-in theme switcher with clean, minimalist ChatGPT/Perplexity-inspired UI.
