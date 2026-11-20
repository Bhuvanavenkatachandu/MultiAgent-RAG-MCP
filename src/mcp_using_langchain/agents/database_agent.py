
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent


def build_database_agents(llm, mcp_tools):

    available_tools = {
        item.name: item for item in mcp_tools
    }

    def select_tools(names):

        selected = [
            available_tools[name]
            for name in names
            if name in available_tools
        ]

        if not selected:
            raise RuntimeError(
                f"Required MCP tools unavailable: {names}"
            )

        return selected

    # Schema Agent
    schema_agent = create_react_agent(
        model=llm,
        tools=select_tools([
            "list_schemas",
            "list_tables",
            "describe_table"
        ]),
        prompt="""
        You are a PostgreSQL schema specialist.

        Understand database schemas, tables,
        columns, data types and relationships.

        Use MCP tools to inspect the database.
        Never invent schema information.
        """
    )

    # Query Agent
    query_agent = create_react_agent(
        model=llm,
        tools=select_tools(["query"]),
        prompt="""
        You are a PostgreSQL query specialist.

        Retrieve records using read-only SQL.

        Generate SQL carefully.
        Only retrieve the data requested.
        Never attempt INSERT, UPDATE or DELETE.
        """
    )

    # Analytics Agent
    analytics_agent = create_react_agent(
        model=llm,
        tools=select_tools([
            "query",
            "list_tables",
            "describe_table"
        ]),
        prompt="""
        You are a PostgreSQL analytics specialist.

        Analyze database records and calculate
        totals, averages, counts and rankings.

        Use SQL queries to obtain accurate results.
        Explain your findings clearly.
        """
    )

    @tool
    async def ask_schema_agent(question: str) -> str:
        """Delegate database structure questions to Schema Agent."""

        result = await schema_agent.ainvoke({
            "messages": [
                {"role": "user", "content": question}
            ]
        })

        return str(result["messages"][-1].content)

    @tool
    async def ask_query_agent(question: str) -> str:
        """Delegate data retrieval questions to Query Agent."""

        result = await query_agent.ainvoke({
            "messages": [
                {"role": "user", "content": question}
            ]
        })

        return str(result["messages"][-1].content)

    @tool
    async def ask_analytics_agent(question: str) -> str:
        """Delegate analytical questions to Analytics Agent."""

        result = await analytics_agent.ainvoke({
            "messages": [
                {"role": "user", "content": question}
            ]
        })

        return str(result["messages"][-1].content)

    return [
        ask_schema_agent,
        ask_query_agent,
        ask_analytics_agent
    ]
