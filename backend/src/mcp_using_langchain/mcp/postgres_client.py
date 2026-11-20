
import os

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient


load_dotenv()


def create_mcp_client():

    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL is missing from .env")

    client = MultiServerMCPClient(
        {
            "postgres": {
                "command": "npx",
                "args": [
                    "-y",
                    "mcp-postgres-server"
                ],
                "transport": "stdio",
                "env": {
                    **os.environ,
                    "DATABASE_URL": database_url,
                    "PG_ALLOW_WRITE": os.getenv(
                        "PG_ALLOW_WRITE", "false"
                    )
                }
            }
        }
    )

    return client


async def get_postgres_tools():

    client = create_mcp_client()

    tools = await client.get_tools()

    if not tools:
        raise RuntimeError("No PostgreSQL MCP tools found")

    print("\nPostgreSQL MCP tools:")

    for tool in tools:
        print(f"- {tool.name}")

    return client, tools
