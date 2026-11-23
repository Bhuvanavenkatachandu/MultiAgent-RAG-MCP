from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from mcp_using_langchain.rag.retriever import get_retriever
from mcp_using_langchain.tracing import CallbackHandler, observe


def build_rag_agent(llm, rebuild=False):

    retriever = get_retriever(rebuild=rebuild)

    @tool
    @observe(name="knowledge-base-retriever", as_type="retriever")
    def search_knowledge_base(question: str) -> str:
        """Search PDF, TXT and Markdown documents for relevant information."""

        documents = retriever.invoke(question)

        if not documents:
            return "No relevant documents found."

        results = []

        for doc in documents:

            source = doc.metadata.get(
                "source", "Unknown"
            )

            results.append(
                f"Source: {source}\n"
                f"Content: {doc.page_content}"
            )

        return "\n\n".join(results)

    rag_agent = create_react_agent(
        model=llm,
        tools=[search_knowledge_base],
        prompt="""
        You are a document knowledge specialist.

        Your responsibilities:

        1. Understand the user's document-related question.
        2. Search the knowledge base.
        3. Use retrieved information to answer.
        4. Mention the document source when possible.
        5. Never invent information.

        If the retrieved documents do not contain
        the answer, clearly say so.
        """
    )

    @tool
    @observe(name="rag-agent", as_type="agent")
    async def ask_rag_agent(question: str) -> str:
        """Delegate document-related questions to the RAG agent."""

        handler = CallbackHandler()
        result = await rag_agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": question
                    }
                ]
            },
            config={"callbacks": [handler], "run_name": "rag-specialist-agent"}
        )

        return str(result["messages"][-1].content)

    return ask_rag_agent
