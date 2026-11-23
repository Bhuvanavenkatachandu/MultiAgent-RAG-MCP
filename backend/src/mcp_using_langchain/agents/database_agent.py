import re
from typing import Any, List
from langchain_core.tools import BaseTool, tool
from mcp_using_langchain.tracing import CallbackHandler, get_client, observe
from mcp_using_langchain.guardrails import sanitize_tool_result, validate_sql_query_safety
from mcp_using_langchain.llm import extract_text_content
from mcp_using_langchain.cache import cache_manager

DATABASE_SCHEMA_SUMMARY = """
PostgreSQL Tables & Schema Details:
- users (id BIGINT PK, first_name VARCHAR(50), last_name VARCHAR(50), email VARCHAR(120) UNIQUE, phone VARCHAR(15), password_hash TEXT, is_active BOOLEAN, created_at TIMESTAMP)
- addresses (id BIGINT PK, user_id BIGINT FK users, address_line VARCHAR(200), city VARCHAR(80), state VARCHAR(80), postal_code VARCHAR(10), country VARCHAR(50), address_type VARCHAR(20))
- categories (id BIGINT PK, name VARCHAR(100) UNIQUE, description TEXT)
- products (id BIGINT PK, category_id BIGINT FK categories, name VARCHAR(150), description TEXT, sku VARCHAR(50) UNIQUE, price NUMERIC(10,2), stock_quantity INTEGER, brand VARCHAR(80), created_at TIMESTAMP)
- carts (id BIGINT PK, user_id BIGINT UNIQUE FK users, created_at TIMESTAMP)
- cart_items (id BIGINT PK, cart_id BIGINT FK carts, product_id BIGINT FK products, quantity INTEGER)
- orders (id BIGINT PK, user_id BIGINT FK users, address_id BIGINT FK addresses, order_date TIMESTAMP, status VARCHAR(30) ['PENDING','PROCESSING','SHIPPED','DELIVERED','CANCELLED'], total_amount NUMERIC(10,2), shipping_fee NUMERIC(10,2), tax_amount NUMERIC(10,2))
- order_items (id BIGINT PK, order_id BIGINT FK orders, product_id BIGINT FK products, quantity INTEGER, unit_price NUMERIC(10,2), subtotal NUMERIC(10,2))
- payments (id BIGINT PK, order_id BIGINT FK orders, amount NUMERIC(10,2), payment_method VARCHAR(30), status VARCHAR(30), transaction_id VARCHAR(100), created_at TIMESTAMP)
- shipments (id BIGINT PK, order_id BIGINT FK orders, tracking_number VARCHAR(100), carrier VARCHAR(50), status VARCHAR(30), estimated_delivery TIMESTAMP, shipped_at TIMESTAMP, delivered_at TIMESTAMP)
- reviews (id BIGINT PK, product_id BIGINT FK products, user_id BIGINT FK users, rating INTEGER (1-5), comment TEXT, created_at TIMESTAMP)
- NOTE: Customers are represented by the 'users' table (join orders.user_id = users.id).
"""

SQL_CODE_BLOCK_PATTERN = re.compile(r"```(?:sql)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def extract_sql_query(raw_text: Any) -> str:
    """Extract clean SQL string from model output."""
    normalized = extract_text_content(raw_text)
    match = SQL_CODE_BLOCK_PATTERN.search(normalized)
    if match:
        return match.group(1).strip()
    return normalized.strip().strip("`").strip()


def validate_read_only_sql(sql: str) -> bool:
    """Ensures SQL is strictly read-only SELECT/WITH statements."""
    clean = sql.strip().upper()
    if not (clean.startswith("SELECT") or clean.startswith("WITH")):
        return False
    disallowed_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "GRANT", "REVOKE"]
    for kw in disallowed_keywords:
        if re.search(rf"\b{kw}\b", clean):
            return False
    return True


def build_database_agents(llm, mcp_tools: List[BaseTool]):
    available_tools = {item.name: item for item in mcp_tools}

    query_tool = available_tools.get("query")
    if not query_tool:
        raise RuntimeError("Required MCP tool 'query' unavailable in PostgreSQL MCP server")

    describe_tool = available_tools.get("describe_table")

    @tool
    @observe(name="schema-agent", as_type="tool")
    async def ask_schema_agent(question: str) -> str:
        """Delegate database structure, tables, and column questions to Schema Agent."""
        q_lower = question.lower()
        if describe_tool:
            tables = ["users", "addresses", "categories", "products", "carts", "cart_items", "orders", "order_items", "payments", "shipments", "reviews"]
            for tbl in tables:
                if tbl in q_lower:
                    try:
                        return str(await describe_tool.ainvoke({"tableName": tbl}))
                    except Exception:
                        pass
        return f"Database Schema Details:\n{DATABASE_SCHEMA_SUMMARY}"

    async def _run_sql_agent(question: str, role_title: str, instruction: str, span_name: str) -> str:
        langfuse = get_client()
        langfuse.update_current_span(input={"question": question})

        # Check Cache (Component 1: SQL Query Results, ~15 MB target allocation)
        # Avoids ~1,600 ms of repeated LLM generation and database roundtrips
        cached = cache_manager.get_sql_result(question)
        if cached and isinstance(cached, dict):
            cached_sql = cached.get("sql", "")
            cached_result = cached.get("result", "")
            output_text = f"Executed SQL (Cached): {cached_sql}\n\nQuery Result:\n{cached_result}"
            langfuse.update_current_span(
                output={"sql": cached_sql, "result": str(cached_result)[:2000], "cache_hit": True}
            )
            return output_text

        prompt = f"""You are a PostgreSQL {role_title}.
{instruction}
{DATABASE_SCHEMA_SUMMARY}
Rules:
- Generate standard PostgreSQL SQL.
- Keep the SQL focused, clean, and concise using direct aggregations.
- Output ONLY the raw SQL query with no explanation, markdown comments, or formatting text.
Question: {question}"""

        handler = CallbackHandler()
        llm_response = await llm.ainvoke(
            prompt,
            config={"callbacks": [handler], "run_name": f"generate-{role_title.replace(' ', '-')}-sql"}
        )
        raw_content = llm_response.content if hasattr(llm_response, "content") else str(llm_response)
        sql = extract_sql_query(raw_content)

        if not validate_read_only_sql(sql):
            err_msg = f"Error: Only read-only queries are permitted. Refusing: {sql}"
            langfuse.update_current_span(
                level="WARNING",
                status_message="Non-read-only SQL rejected",
                output={"error": err_msg, "sql": sql}
            )
            return err_msg

        is_safe, sec_err = validate_sql_query_safety(sql)
        if not is_safe:
            err_msg = f"Security Policy Refusal: {sec_err}"
            langfuse.update_current_span(
                level="WARNING",
                status_message="Sensitive column access rejected",
                output={"error": err_msg, "sql": sql}
            )
            return err_msg

        try:
            with langfuse.start_as_current_observation(name=span_name, as_type="tool") as query_span:
                query_span.update(input={"sql": sql})
                result = await query_tool.ainvoke({"sql": sql})
                sanitized_result = sanitize_tool_result(result)
                query_span.update(output={"result": str(sanitized_result)[:2000]})

            output_text = f"Executed SQL: {sql}\n\nQuery Result:\n{sanitized_result}"
            # Cache analytical query and sanitized result for 10 minutes (TTL)
            cache_manager.set_sql_result(question, sql=sql, result=str(sanitized_result))
            langfuse.update_current_span(output={"sql": sql, "result": str(sanitized_result)[:2000], "cache_hit": False})
            return output_text
        except Exception as e:
            err = f"Database query failed for SQL '{sql}': {str(e)}"
            langfuse.update_current_span(
                level="ERROR",
                status_message=str(e),
                output={"error": err, "sql": sql}
            )
            return err

    @tool
    @observe(name="query-agent", as_type="agent", capture_input=False, capture_output=False)
    async def ask_query_agent(question: str) -> str:
        """Delegate data retrieval questions to Query Agent."""
        return await _run_sql_agent(
            question=question,
            role_title="query specialist",
            instruction="Write a single read-only PostgreSQL query (SELECT or WITH) to answer the user's question.",
            span_name="execute-postgres-query",
        )

    @tool
    @observe(name="analytics-agent", as_type="agent", capture_input=False, capture_output=False)
    async def ask_analytics_agent(question: str) -> str:
        """Delegate analytical questions (aggregations, sums, counts, rankings, revenue, statistics) to Analytics Agent."""
        return await _run_sql_agent(
            question=question,
            role_title="analytics specialist",
            instruction="Write an analytical PostgreSQL query using aggregations, rankings, or groupings to answer the user's question.",
            span_name="execute-analytics-query",
        )

    return [
        ask_schema_agent,
        ask_query_agent,
        ask_analytics_agent
    ]
