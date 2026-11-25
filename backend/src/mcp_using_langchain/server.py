import asyncio
import json
import logging
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

import docx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_groq import ChatGroq
from pydantic import BaseModel

from mcp_using_langchain.agents.database_agent import build_database_agents
from mcp_using_langchain.agents.rag_agent import build_rag_agent
from mcp_using_langchain.agents.supervisor import build_supervisor
from mcp_using_langchain.llm import extract_text_content, get_configured_llm
from mcp_using_langchain.task_manager import chat_task_manager
from mcp_using_langchain.guardrails import (
    OutputGuardrailViolation,
    StreamingGuardrailBuffer,
    check_output_safety,
    run_input_guardrails,
    validate_and_sanitize_output,
)
from mcp_using_langchain.mcp.postgres_client import open_postgres_session
from mcp_using_langchain.cache import cache_manager
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
    llm = app_state.get("llm")
    if not llm:
        return

    # Invalidate stale RAG search cache when documents are modified or re-indexed
    cache_manager.invalidate_rag_cache()

    rag_tool = build_rag_agent(llm, rebuild=True)
    app_state["rag_tool"] = rag_tool
    database_tools = app_state.get("database_tools") or []
    all_agent_tools = database_tools + [rag_tool]
    app_state["supervisor"] = build_supervisor(llm, all_agent_tools)


async def rebuild_supervisor():
    """Rebuilds RAG tool and supervisor with latest document index in worker thread without blocking the event loop."""
    async with rebuild_lock:
        await asyncio.to_thread(_rebuild_supervisor_sync)


async def _initialize_services_background(llm: Any, shutdown_event: asyncio.Event):
    """Initializes heavy external services (MCP, agents, vectorstore) in the background so the HTTP port binds immediately."""
    try:
        # 0. Configure Hugging Face Hub authentication
        _configure_huggingface_auth()

        # Verify Langfuse connectivity if configured
        try:
            langfuse_client = get_client()
            if langfuse_client.auth_check():
                print("[startup] Langfuse client authenticated successfully.")
            else:
                print("[startup] Warning: Langfuse client authentication check returned False.")
        except Exception as e:
            print(f"[startup] Warning: Langfuse auth check: {e}")

        # Build RAG knowledge base agent
        rag_tool = None
        try:
            print("[startup] Initializing RAG knowledge base agent...")
            rag_tool = build_rag_agent(llm, rebuild=False)
            app_state["rag_tool"] = rag_tool
            print("[startup] RAG knowledge base agent ready.")
        except Exception as rag_err:
            logger.warning(f"[startup] Warning during RAG initialization: {rag_err}")
            print(f"[startup] Warning: RAG initialization: {rag_err}")

        # Connect PostgreSQL MCP with a persistent session and build the complete supervisor
        print("[startup] Connecting to PostgreSQL MCP server...")
        try:
            async with open_postgres_session() as (client, mcp_tools):
                app_state["mcp_client"] = client
                app_state["mcp_tools"] = mcp_tools

                # Build specialist agents
                print("[startup] Building database specialist tools...")
                database_tools = build_database_agents(llm, mcp_tools)
                app_state["database_tools"] = database_tools

                # Assemble complete multi-agent supervisor with all 4 specialist agents
                all_agent_tools = database_tools + ([rag_tool] if rag_tool else [])
                supervisor = build_supervisor(llm, all_agent_tools)
                app_state["supervisor"] = supervisor
                print("[startup] FastAPI Backend fully ready: Multi-Agent Supervisor online with Database (Query, Analytics, Schema) & RAG agents!")

                # Keep persistent MCP session active until application shutdown
                await shutdown_event.wait()
        except asyncio.CancelledError:
            raise
        except Exception as mcp_err:
            logger.error(f"[startup] Critical: PostgreSQL MCP connection failed: {mcp_err}", exc_info=True)
            print(f"[startup] Critical: PostgreSQL MCP connection failed ({mcp_err}).")
            await shutdown_event.wait()

    except asyncio.CancelledError:
        print("[shutdown] Background services initialization cancelled.")
    except Exception as e:
        logger.error(f"[startup] Critical error during background services initialization: {e}", exc_info=True)
        print(f"[startup] ERROR: Background services initialization failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[startup] Lifespan: Server startup initiated...")

    # 1. Initialize LLM (Groq primary with optional Gemini automatic fallback)
    llm = get_configured_llm()
    app_state["llm"] = llm

    # 2. Launch background initialization so Uvicorn opens the port IMMEDIATELY (<1s)
    shutdown_event = asyncio.Event()
    init_task = asyncio.create_task(_initialize_services_background(llm, shutdown_event))
    print("[startup] HTTP port will now open immediately. Background services initializing concurrently.")

    try:
        yield
    finally:
        shutdown_event.set()
        init_task.cancel()
        try:
            await asyncio.wait_for(init_task, timeout=5.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        flush_langfuse()


app = FastAPI(title="PostgreSQL RAG MCP API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


logger = logging.getLogger("mcp_using_langchain.server")


class MessageItem(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[MessageItem]] = []
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    chat_id: Optional[str] = None
    tags: Optional[List[str]] = None


class CancelChatRequest(BaseModel):
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    chat_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    role: str = "assistant"
    chat_id: Optional[str] = None


@app.post("/api/chat/cancel")
async def cancel_chat(request: CancelChatRequest):
    """Cancels any currently running chat generation task for the session scope."""
    session_id = request.session_id or "web-session-default"
    user_id = request.user_id or "web-user"
    session_key = chat_task_manager.get_session_key(session_id, user_id)
    cancelled_id = await chat_task_manager.cancel_active_task(session_key, new_chat_id=request.chat_id)
    return {
        "status": "cancelled",
        "session_id": session_id,
        "cancelled_chat_id": cancelled_id,
    }


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
async def chat_stream(request: ChatRequest, raw_request: Request):
    chat_id = request.chat_id or f"chat_{uuid.uuid4().hex[:10]}"
    session_id = request.session_id or "web-session-default"
    user_id = request.user_id or "web-user"
    session_key = chat_task_manager.get_session_key(session_id, user_id)

    # Cancel any previous active task for this user/session before starting the new stream
    await chat_task_manager.cancel_active_task(session_key, new_chat_id=chat_id)

    # Execute layered input guardrails before invoking supervisor
    passed, rejection_msg, cleaned_query = run_input_guardrails(request.message)
    if not passed:
        async def rejection_generator():
            yield f"data: {json.dumps({'type': 'status', 'message': 'Evaluating request...', 'chat_id': chat_id})}\n\n"
            yield f"data: {json.dumps({'type': 'token', 'content': rejection_msg or 'Request rejected by system guardrails.', 'chat_id': chat_id})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'chat_id': chat_id})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            rejection_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    supervisor = app_state["supervisor"]
    if not supervisor:
        raise HTTPException(status_code=503, detail="Supervisor not initialized")

    tags = ["chat-stream", "postgres-rag-mcp"] + (request.tags or [])

    messages = []
    if request.history:
        for item in request.history:
            messages.append({"role": item.role, "content": item.content})
    messages.append({"role": "user", "content": cleaned_query})

    async def event_generator():
        current_task = asyncio.current_task()
        cancel_event = asyncio.Event()
        if current_task:
            await chat_task_manager.register_task(session_key, chat_id, current_task, cancel_event)

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
                buffer_manager = StreamingGuardrailBuffer(
                    min_chunk_size=30,
                    max_chunk_size=120,
                    overlap_size=40,
                )
                tokens_streamed_count = 0
                fallback_final_content = ""
                accumulated_tokens = []
                violation_detected = False
                client_disconnected = False

                try:
                    if cancel_event.is_set() or not chat_task_manager.is_chat_active(session_key, chat_id):
                        return

                    yield f"data: {json.dumps({'type': 'status', 'message': 'Processing question...', 'chat_id': chat_id})}\n\n"
                    async for event in supervisor.astream_events(
                        {"messages": messages},
                        version="v2",
                        config={"callbacks": [handler], "run_name": "supervisor-stream-agent"}
                    ):
                        # Detect cancellation or client disconnection
                        if cancel_event.is_set() or not chat_task_manager.is_chat_active(session_key, chat_id):
                            client_disconnected = True
                            break

                        if await raw_request.is_disconnected():
                            client_disconnected = True
                            break

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
                            yield f"data: {json.dumps({'type': 'status', 'message': status_text, 'chat_id': chat_id})}\n\n"
                        elif kind == "on_tool_end":
                            yield f"data: {json.dumps({'type': 'status', 'message': 'Synthesizing response...', 'chat_id': chat_id})}\n\n"
                        elif kind == "on_chain_end":
                            out = event.get("data", {}).get("output")
                            if isinstance(out, dict) and "messages" in out and out["messages"]:
                                last_msg = out["messages"][-1]
                                if hasattr(last_msg, "content") and last_msg.content:
                                    fallback_final_content = extract_text_content(last_msg.content)
                        elif kind == "on_chat_model_stream":
                            # Stream tokens from the supervisor agent node speaking to the user
                            node = event.get("metadata", {}).get("langgraph_node")
                            if node == "agent":
                                chunk = event.get("data", {}).get("chunk")
                                if chunk and hasattr(chunk, "content") and chunk.content:
                                    if not getattr(chunk, "tool_calls", None) and not getattr(chunk, "tool_call_chunks", None):
                                        token_str = extract_text_content(chunk.content)
                                        if not token_str:
                                            continue
                                        try:
                                            ready_chunks = buffer_manager.add_token(token_str)
                                            for ready_chunk in ready_chunks:
                                                if cancel_event.is_set() or not chat_task_manager.is_chat_active(session_key, chat_id):
                                                    client_disconnected = True
                                                    break
                                                tokens_streamed_count += 1
                                                accumulated_tokens.append(ready_chunk)
                                                yield f"data: {json.dumps({'type': 'token', 'content': ready_chunk, 'chat_id': chat_id})}\n\n"
                                        except OutputGuardrailViolation as violation:
                                            violation_detected = True
                                            buffer_manager.clear()
                                            stream_span.update(
                                                level="ERROR",
                                                status_message=f"Output Guardrail Violation: {violation.reason}",
                                                output={"guardrail_violation": violation.reason}
                                            )
                                            yield f"data: {json.dumps({'type': 'error', 'message': violation.message, 'chat_id': chat_id})}\n\n"
                                            yield f"data: {json.dumps({'type': 'done', 'chat_id': chat_id})}\n\n"
                                            yield "data: [DONE]\n\n"
                                            break

                    # If task was cancelled, client disconnected or guardrail violation occurred
                    if cancel_event.is_set() or not chat_task_manager.is_chat_active(session_key, chat_id):
                        flush_langfuse()
                        return

                    if client_disconnected or violation_detected:
                        flush_langfuse()
                        return

                    # Validate and flush any remaining buffered text at end of stream
                    try:
                        remaining_chunks = buffer_manager.flush()
                        for remaining_chunk in remaining_chunks:
                            if cancel_event.is_set() or not chat_task_manager.is_chat_active(session_key, chat_id):
                                return
                            tokens_streamed_count += 1
                            accumulated_tokens.append(remaining_chunk)
                            yield f"data: {json.dumps({'type': 'token', 'content': remaining_chunk, 'chat_id': chat_id})}\n\n"
                    except OutputGuardrailViolation as violation:
                        violation_detected = True
                        buffer_manager.clear()
                        stream_span.update(
                            level="ERROR",
                            status_message=f"Output Guardrail Violation on flush: {violation.reason}",
                            output={"guardrail_violation": violation.reason}
                        )
                        yield f"data: {json.dumps({'type': 'error', 'message': violation.message, 'chat_id': chat_id})}\n\n"
                        yield f"data: {json.dumps({'type': 'done', 'chat_id': chat_id})}\n\n"
                        yield "data: [DONE]\n\n"
                        flush_langfuse()
                        return

                    # Guaranteed delivery: if token streaming was bypassed/empty, validate and deliver fallback content
                    if tokens_streamed_count == 0 and fallback_final_content:
                        if cancel_event.is_set() or not chat_task_manager.is_chat_active(session_key, chat_id):
                            return
                        validation = check_output_safety(fallback_final_content)
                        if not validation.is_safe:
                            stream_span.update(
                                level="ERROR",
                                status_message=f"Output Guardrail Violation on fallback: {validation.reason}",
                                output={"guardrail_violation": validation.reason}
                            )
                            yield f"data: {json.dumps({'type': 'error', 'message': validation.rejection_message or 'Output blocked by system guardrails.', 'chat_id': chat_id})}\n\n"
                            yield f"data: {json.dumps({'type': 'done', 'chat_id': chat_id})}\n\n"
                            yield "data: [DONE]\n\n"
                            flush_langfuse()
                            return

                        safe_fallback = validation.sanitized_text if validation.sanitized_text else fallback_final_content
                        accumulated_tokens.append(safe_fallback)
                        yield f"data: {json.dumps({'type': 'token', 'content': safe_fallback, 'chat_id': chat_id})}\n\n"

                    final_response = "".join(accumulated_tokens)
                    stream_span.update(output={"assistant_response": final_response})
                    yield f"data: {json.dumps({'type': 'done', 'chat_id': chat_id})}\n\n"
                    yield "data: [DONE]\n\n"
                    flush_langfuse()
                except asyncio.CancelledError:
                    # Task was cancelled (e.g. client aborted or New Chat started)
                    logger.info("Chat stream generation cancelled for session %s (chat_id: %s)", session_key, chat_id)
                    flush_langfuse()
                    return
                except Exception as e:
                    if cancel_event.is_set() or not chat_task_manager.is_chat_active(session_key, chat_id):
                        flush_langfuse()
                        return
                    stream_span.update(
                        level="ERROR",
                        status_message=str(e),
                        output={"error": str(e)}
                    )
                    flush_langfuse()
                    # Do not append error as token if tokens were already emitted to avoid mangling output
                    if tokens_streamed_count == 0:
                        yield f"data: {json.dumps({'type': 'token', 'content': f'⚠️ Error: {str(e)}', 'chat_id': chat_id})}\n\n"
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e), 'chat_id': chat_id})}\n\n"
                    yield f"data: {json.dumps({'type': 'done', 'chat_id': chat_id})}\n\n"
                    yield "data: [DONE]\n\n"
                finally:
                    await chat_task_manager.unregister_task(session_key, chat_id)

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
    chat_id = request.chat_id or f"chat_{uuid.uuid4().hex[:10]}"
    session_id = request.session_id or "web-session-default"
    user_id = request.user_id or "web-user"
    session_key = chat_task_manager.get_session_key(session_id, user_id)

    # Cancel previous task for this session
    await chat_task_manager.cancel_active_task(session_key, new_chat_id=chat_id)

    current_task = asyncio.current_task()
    cancel_event = asyncio.Event()
    if current_task:
        await chat_task_manager.register_task(session_key, chat_id, current_task, cancel_event)

    try:
        # Execute layered input guardrails before invoking supervisor
        passed, rejection_msg, cleaned_query = run_input_guardrails(request.message)
        if not passed:
            langfuse = get_client()
            langfuse.update_current_span(output={"guardrail_rejection": rejection_msg})
            flush_langfuse()
            return ChatResponse(response=rejection_msg or "Request rejected by system guardrails.", role="assistant", chat_id=chat_id)

        supervisor = app_state["supervisor"]
        if not supervisor:
            raise HTTPException(status_code=503, detail="Supervisor not initialized")

        tags = ["chat-json", "postgres-rag-mcp"] + (request.tags or [])

        langfuse = get_client()
        langfuse.update_current_span(input={"user_message": cleaned_query})

        messages = []
        if request.history:
            for item in request.history:
                messages.append({"role": item.role, "content": item.content})
        messages.append({"role": "user", "content": cleaned_query})

        if cancel_event.is_set() or not chat_task_manager.is_chat_active(session_key, chat_id):
            raise asyncio.CancelledError()

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
            if cancel_event.is_set() or not chat_task_manager.is_chat_active(session_key, chat_id):
                raise asyncio.CancelledError()

            content = extract_text_content(result["messages"][-1].content)
            sanitized_content = validate_and_sanitize_output(content)
            langfuse.update_current_span(output={"assistant_response": sanitized_content})
            flush_langfuse()
            return ChatResponse(response=sanitized_content, role="assistant", chat_id=chat_id)
    except asyncio.CancelledError:
        logger.info("Chat task cancelled for session %s (chat_id: %s)", session_key, chat_id)
        flush_langfuse()
        raise HTTPException(status_code=499, detail="Request cancelled")
    except Exception as e:
        langfuse.update_current_span(
            level="ERROR",
            status_message=str(e),
            output={"error": str(e)}
        )
        flush_langfuse()
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")
    finally:
        await chat_task_manager.unregister_task(session_key, chat_id)


def start():
    import uvicorn

    port = int(os.getenv("PORT", "8001"))
    uvicorn.run("mcp_using_langchain.server:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    start()
