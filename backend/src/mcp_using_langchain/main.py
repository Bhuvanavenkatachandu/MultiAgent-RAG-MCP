
import asyncio
import os
import uuid

from langchain_groq import ChatGroq
from mcp_using_langchain.tracing import (
    CallbackHandler,
    flush_langfuse,
    get_client,
    observe,
    propagate_attributes,
)

from mcp_using_langchain.mcp.postgres_client import (
    get_postgres_tools
)

from mcp_using_langchain.agents.rag_agent import (
    build_rag_agent
)

from mcp_using_langchain.agents.database_agent import (
    build_database_agents
)

from mcp_using_langchain.agents.supervisor import (
    build_supervisor
)



async def run():

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY is missing")

    # 1. Initialize Groq with capped max_tokens for free-tier rate limits
    max_tokens = int(os.getenv("GROQ_MAX_TOKENS", "800"))
    llm = ChatGroq(
        model=os.getenv(
            "GROQ_MODEL",
            "qwen/qwen3.8-27b"
        ),
        api_key=api_key,
        max_tokens=max_tokens,
    )

    print("Groq initialized")

    # 2. Connect to PostgreSQL MCP
    client, mcp_tools = await get_postgres_tools()

    print("PostgreSQL MCP connected")

    # 3. Build database agents
    database_tools = build_database_agents(
        llm,
        mcp_tools
    )

    print("Database agents initialized")

    # 4. Build RAG agent
    rebuild = (
        os.getenv("REBUILD_VECTORSTORE", "false").lower()
        == "true"
    )

    rag_tool = build_rag_agent(
        llm,
        rebuild=rebuild
    )

    print("RAG agent initialized")

    # 5. Combine all specialist agents
    all_agent_tools = database_tools + [
        rag_tool
    ]

    # 6. Build supervisor
    supervisor = build_supervisor(
        llm,
        all_agent_tools
    )

    langfuse = get_client()
    try:
        langfuse.auth_check()
    except Exception as e:
        print(f"Langfuse auth check warning: {e}")

    cli_session_id = f"cli-session-{uuid.uuid4().hex[:8]}"

    print("\nMulti-Agent System Ready!")
    print("Ask questions or type 'exit' to quit.")

    # 7. Dynamic user interaction
    while True:

        question = input("\nYou: ").strip()

        if question.lower() in ["exit", "quit"]:
            print("Flushing Langfuse traces before exiting...")
            langfuse.flush()
            print("Goodbye!")
            break

        if not question:
            continue

        try:
            with langfuse.start_as_current_observation(
                name="cli-chat-turn",
                as_type="agent",
            ) as span:
                span.update(input={"user_message": question})
                with propagate_attributes(
                    trace_name="cli-chat-turn",
                    session_id=cli_session_id,
                    tags=["cli", "postgres-rag-mcp"],
                ):
                    handler = CallbackHandler()
                    response = await supervisor.ainvoke(
                        {
                            "messages": [
                                {
                                    "role": "user",
                                    "content": question
                                }
                            ]
                        },
                        config={"callbacks": [handler], "run_name": "supervisor-agent"}
                    )

                    content = response["messages"][-1].content
                    span.update(output={"assistant_response": content})
                    langfuse.flush()

                    print("\nAssistant:")
                    print(content)

        except Exception as error:
            print(f"\nError: {error}")
            try:
                langfuse.flush()
            except Exception:
                pass



if __name__ == "__main__":
    asyncio.run(run())
