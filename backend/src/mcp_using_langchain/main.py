import asyncio
import os

from dotenv import load_dotenv
from langchain_groq import ChatGroq

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

from mcp_using_langchain.tracing import (
    CallbackHandler,
    flush_langfuse,
    propagate_attributes,
)

load_dotenv()


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

    print("\nMulti-Agent System Ready (with Langfuse Tracing)!")
    print("Ask questions or type 'exit' to quit.")

    # 7. Dynamic user interaction
    while True:

        question = input("\nYou: ").strip()

        if question.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break

        if not question:
            continue

        try:
            handler = CallbackHandler()
            with propagate_attributes(
                trace_name="cli-turn",
                session_id="cli-interactive-session",
                tags=["cli", "postgres-rag-mcp"],
            ):
                response = await supervisor.ainvoke(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": question
                            }
                        ]
                    },
                    config={"callbacks": [handler], "run_name": "supervisor-cli"}
                )

            print("\nAssistant:")
            print(response["messages"][-1].content)
            flush_langfuse()

        except Exception as error:
            print(f"\nError: {error}")
            flush_langfuse()


if __name__ == "__main__":
    asyncio.run(run())
