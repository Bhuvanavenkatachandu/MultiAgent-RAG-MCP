
import re
from typing import List
from langchain_core.tools import BaseTool, tool

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


def extract_sql_query(raw_text: str) -> str:
    """Extract clean SQL string from model output."""
    match = SQL_CODE_BLOCK_PATTERN.search(raw_text)
    if match:
        return match.group(1).strip()
    # Strip backticks or quotes if bare
    return raw_text.strip().strip("`").strip()


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
    list_tables_tool = available_tools.get("list_tables")

    @tool
    async def ask_schema_agent(question: str) -> str:
        """Delegate database structure, tables, and column questions to Schema Agent."""
        q_lower = question.lower()
        if describe_tool:
            for tbl in ["users", "addresses", "categories", "products", "carts", "cart_items", "orders", "order_items", "payments", "shipments", "reviews"]:
                if tbl in q_lower:
                    try:
                        return str(await describe_tool.ainvoke({"tableName": tbl}))
                    except Exception:
                        pass
        return f"Database Schema Details:\n{DATABASE_SCHEMA_SUMMARY}"

    @tool
    async def ask_query_agent(question: str) -> str:
        """Delegate data retrieval questions to Query Agent."""
        prompt = f"""You are a PostgreSQL query specialist.
Write a single read-only PostgreSQL query (SELECT or WITH) to answer the user's question.
{DATABASE_SCHEMA_SUMMARY}
Rules:
- Generate standard PostgreSQL SQL.
- Keep the SQL focused, clean, and concise using direct aggregations.
- Output ONLY the raw SQL query with no explanation, markdown comments, or formatting text.
Question: {question}"""

        llm_response = await llm.ainvoke(prompt)
        raw_content = llm_response.content if hasattr(llm_response, "content") else str(llm_response)
        sql = extract_sql_query(raw_content)

        if not validate_read_only_sql(sql):
            return f"Error: Only read-only queries are permitted. Refusing: {sql}"

        try:
            result = await query_tool.ainvoke({"sql": sql})
            return f"Executed SQL: {sql}\n\nQuery Result:\n{result}"
        except Exception as e:
            return f"Database query failed for SQL '{sql}': {str(e)}"

    @tool
    async def ask_analytics_agent(question: str) -> str:
        """Delegate analytical questions (aggregations, sums, counts, rankings, revenue, statistics) to Analytics Agent."""
        prompt = f"""You are a PostgreSQL analytics specialist.
Write an analytical PostgreSQL query using aggregations, rankings, or groupings to answer the user's question.
{DATABASE_SCHEMA_SUMMARY}
Rules:
- Generate standard PostgreSQL SQL.
- Keep the SQL focused, clean, and concise using direct aggregations.
- Output ONLY the raw SQL query with no explanation, markdown comments, or formatting text.
Question: {question}"""

        llm_response = await llm.ainvoke(prompt)
        raw_content = llm_response.content if hasattr(llm_response, "content") else str(llm_response)
        sql = extract_sql_query(raw_content)

        if not validate_read_only_sql(sql):
            return f"Error: Only read-only queries are permitted. Refusing: {sql}"

        try:
            result = await query_tool.ainvoke({"sql": sql})
            return f"Executed SQL: {sql}\n\nAnalytics Result:\n{result}"
        except Exception as e:
            return f"Analytics query failed for SQL '{sql}': {str(e)}"

    return [
        ask_schema_agent,
        ask_query_agent,
        ask_analytics_agent
    ]
