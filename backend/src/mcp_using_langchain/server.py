import asyncio
import json
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import docx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_groq import ChatGroq
from pydantic import BaseModel

from mcp_using_langchain.agents.database_agent import build_database_agents
from mcp_using_langchain.agents.rag_agent import build_rag_agent
from mcp_using_langchain.agents.supervisor import build_supervisor
from mcp_using_langchain.mcp.postgres_client import open_postgres_session
from mcp_using_langchain.rag.embeddings import _configure_huggingface_auth
from mcp_using_langchain.rag.loader import DOCUMENTS_DIR
from mcp_using_langchain.tracing import (
    CallbackHandler,
    flush_langfuse,
    get_client,
    observe,
    propagate_attributes,
)

load_dotenv()

app_state: Dict[str, Any] = {
    "llm": None,
    "supervisor": None,
    "mcp_client": None,
    "mcp_tools": None,
    "database_tools": None,
    "rag_tool": None,
}

rebuild_lock = asyncio.Lock()


def _rebuild_supervisor_sync():
    """Synchronous core for rebuilding vector index and supervisor."""
    llm = app_state["llm"]
    database_tools = app_state["database_tools"]
    if not llm or not database_tools:
        return

    rag_tool = build_rag_agent(llm, rebuild=True)
    app_state["rag_tool"] = rag_tool
    all_agent_tools = database_tools + [rag_tool]
    app_state["supervisor"] = build_supervisor(llm, all_agent_tools)


async def rebuild_supervisor():
    """Rebuilds RAG tool and supervisor with latest document index in worker thread without blocking the event loop."""
    async with rebuild_lock:
        await asyncio.to_thread(_rebuild_supervisor_sync)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 0. Configure Hugging Face Hub authentication
    _configure_huggingface_auth()

    # Verify Langfuse connectivity if configured
    try:
        langfuse_client = get_client()
        if langfuse_client.auth_check():
            print("Langfuse client authenticated successfully.")
        else:
            print("Warning: Langfuse client authentication check returned False.")
    except Exception as e:
        print(f"Warning: Langfuse auth check: {e}")

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is missing from environment")

    # 1. Initialize LLM with max_tokens capped to stay within OTPM rate limits
    max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "800"))
    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b"),
        api_key=api_key,
        max_tokens=max_tokens,
    )
    app_state["llm"] = llm

    # 2. Connect PostgreSQL MCP with a persistent session across the lifespan
    async with open_postgres_session() as (client, mcp_tools):
        app_state["mcp_client"] = client
        app_state["mcp_tools"] = mcp_tools

        # 3. Build specialist agents
        database_tools = build_database_agents(llm, mcp_tools)
        app_state["database_tools"] = database_tools

        rag_tool = build_rag_agent(llm, rebuild=False)
        app_state["rag_tool"] = rag_tool

        # 4. Build supervisor
        all_agent_tools = database_tools + [rag_tool]
        supervisor = build_supervisor(llm, all_agent_tools)
        app_state["supervisor"] = supervisor

        print("FastAPI Backend initialized with Supervisor & PostgreSQL MCP (persistent session)")
        try:
            yield
        finally:
            flush_langfuse()


app = FastAPI(title="PostgreSQL RAG MCP API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MessageItem(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[MessageItem]] = []
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    tags: Optional[List[str]] = None


class ChatResponse(BaseModel):
    response: str
    role: str = "assistant"


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "mcp_connected": app_state["mcp_tools"] is not None,
        "supervisor_ready": app_state["supervisor"] is not None,
    }


@app.get("/api/documents")
async def list_documents():
    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    docs = []
    for f in DOCUMENTS_DIR.iterdir():
        if f.is_file() and not f.name.startswith("."):
            docs.append(
                {
                    "name": f.name,
                    "size_bytes": f.stat().st_size,
                    "modified": f.stat().st_mtime,
                    "extension": f.suffix.lower(),
                }
            )
    docs.sort(key=lambda x: x["name"])
    return {"documents": docs}


@app.post("/api/upload")
@observe(name="document-upload-and-index", as_type="span", capture_input=False, capture_output=False)
async def upload_document(file: UploadFile = File(...)):
    langfuse = get_client()
    filename = file.filename or "uploaded_document"
    ext = Path(filename).suffix.lower()

    langfuse.update_current_span(input={"filename": filename, "extension": ext})

    allowed = {".pdf", ".docx", ".txt", ".md"}
    if ext not in allowed:
        err_msg = f"Unsupported file type '{ext}'. Allowed: {', '.join(allowed)}"
        langfuse.update_current_span(level="WARNING", status_message=err_msg, output={"error": err_msg})
        raise HTTPException(
            status_code=400,
            detail=err_msg,
        )

    DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    destination = DOCUMENTS_DIR / filename

    # Save uploaded file
    with destination.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # If DOCX, extract text to .txt so existing loader can read without backend modifications
    if ext == ".docx":
        try:
            doc = docx.Document(destination)
            text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            txt_destination = destination.with_suffix(".txt")
            txt_destination.write_text(text, encoding="utf-8")
        except Exception as e:
            err_msg = f"Failed to process DOCX file: {e}"
            langfuse.update_current_span(level="ERROR", status_message=err_msg, output={"error": err_msg})
            raise HTTPException(
                status_code=500, detail=err_msg
            )

    # Rebuild index and supervisor in worker thread without blocking event loop
    try:
        await rebuild_supervisor()
    except Exception as e:
        err_msg = f"File saved, but indexing failed: {e}"
        langfuse.update_current_span(level="ERROR", status_message=err_msg, output={"error": err_msg})
        raise HTTPException(
            status_code=500, detail=err_msg
        )

    response_payload = {
        "filename": filename,
        "status": "success",
        "message": f"'{filename}' uploaded and indexed successfully.",
    }
    langfuse.update_current_span(output=response_payload)
    flush_langfuse()
    return response_payload


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    supervisor = app_state["supervisor"]
    if not supervisor:
        raise HTTPException(status_code=503, detail="Supervisor not initialized")

    session_id = request.session_id or "web-session-default"
    user_id = request.user_id or "web-user"
    tags = ["chat-stream", "postgres-rag-mcp"] + (request.tags or [])

    messages = []
    if request.history:
        for item in request.history:
            messages.append({"role": item.role, "content": item.content})
    messages.append({"role": "user", "content": request.message})

    async def event_generator():
        langfuse = get_client()
        with langfuse.start_as_current_observation(
            name="chat-stream-turn",
            as_type="agent",
        ) as stream_span:
            stream_span.update(input={"user_message": request.message})
            with propagate_attributes(
                trace_name="chat-stream-turn",
                session_id=session_id,
                user_id=user_id,
                tags=tags,
            ):
                handler = CallbackHandler()
                try:
                    tokens_streamed_count = 0
                    fallback_final_content = ""
                    accumulated_tokens = []
                    yield f"data: {json.dumps({'type': 'status', 'message': 'Processing question...'})}\n\n"
                    async for event in supervisor.astream_events(
                        {"messages": messages},
                        version="v2",
                        config={"callbacks": [handler], "run_name": "supervisor-stream-agent"}
                    ):
                        kind = event.get("event")
                        if kind == "on_tool_start":
                            name = event.get("name", "")
                            if "query" in name or "database" in name:
                                status_text = "Querying PostgreSQL database..."
                            elif "analytics" in name:
                                status_text = "Computing analytics on database..."
                            elif "rag" in name or "knowledge" in name:
                                status_text = "Searching knowledge base documents..."
                            elif "schema" in name:
                                status_text = "Inspecting database schema..."
                            else:
                                status_text = "Executing specialist tool..."
                            yield f"data: {json.dumps({'type': 'status', 'message': status_text})}\n\n"
                        elif kind == "on_tool_end":
                            yield f"data: {json.dumps({'type': 'status', 'message': 'Synthesizing response...'})}\n\n"
                        elif kind == "on_chain_end":
                            out = event.get("data", {}).get("output")
                            if isinstance(out, dict) and "messages" in out and out["messages"]:
                                last_msg = out["messages"][-1]
                                if hasattr(last_msg, "content") and last_msg.content:
                                    fallback_final_content = str(last_msg.content)
                        elif kind == "on_chat_model_stream":
                            # Stream tokens from the supervisor agent node speaking to the user
                            node = event.get("metadata", {}).get("langgraph_node")
                            if node == "agent":
                                chunk = event.get("data", {}).get("chunk")
                                if chunk and hasattr(chunk, "content") and chunk.content:
                                    if not getattr(chunk, "tool_calls", None) and not getattr(chunk, "tool_call_chunks", None):
                                        tokens_streamed_count += 1
                                        token_str = str(chunk.content)
                                        accumulated_tokens.append(token_str)
                                        yield f"data: {json.dumps({'type': 'token', 'content': token_str})}\n\n"

                    # Guaranteed delivery: if token streaming was bypassed/empty, deliver the complete final content
                    final_response = "".join(accumulated_tokens) if tokens_streamed_count > 0 else fallback_final_content
                    if tokens_streamed_count == 0 and fallback_final_content:
                        yield f"data: {json.dumps({'type': 'token', 'content': fallback_final_content})}\n\n"

                    stream_span.update(output={"assistant_response": final_response})
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    yield "data: [DONE]\n\n"
                    flush_langfuse()
                except Exception as e:
                    stream_span.update(
                        level="ERROR",
                        status_message=str(e),
                        output={"error": str(e)}
                    )
                    flush_langfuse()
                    yield f"data: {json.dumps({'type': 'token', 'content': f'⚠️ Error: {str(e)}'})}\n\n"
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat", response_model=ChatResponse)
@observe(name="chat-turn", as_type="agent", capture_input=False, capture_output=False)
async def chat(request: ChatRequest):
    supervisor = app_state["supervisor"]
    if not supervisor:
        raise HTTPException(status_code=503, detail="Supervisor not initialized")

    session_id = request.session_id or "web-session-default"
    user_id = request.user_id or "web-user"
    tags = ["chat-json", "postgres-rag-mcp"] + (request.tags or [])

    langfuse = get_client()
    langfuse.update_current_span(input={"user_message": request.message})

    messages = []
    if request.history:
        for item in request.history:
            messages.append({"role": item.role, "content": item.content})
    messages.append({"role": "user", "content": request.message})

    try:
        with propagate_attributes(
            trace_name="chat-turn",
            session_id=session_id,
            user_id=user_id,
            tags=tags,
        ):
            handler = CallbackHandler()
            result = await supervisor.ainvoke(
                {"messages": messages},
                config={"callbacks": [handler], "run_name": "supervisor-agent"}
            )
            content = result["messages"][-1].content
            langfuse.update_current_span(output={"assistant_response": content})
            flush_langfuse()
            return ChatResponse(response=content, role="assistant")
    except Exception as e:
        langfuse.update_current_span(
            level="ERROR",
            status_message=str(e),
            output={"error": str(e)}
        )
        flush_langfuse()
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


def start():
    import uvicorn

    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("mcp_using_langchain.server:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    start()
