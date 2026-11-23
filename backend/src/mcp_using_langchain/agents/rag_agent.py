
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langfuse import get_client, observe
from langfuse.langchain import CallbackHandler

from mcp_using_langchain.rag.retriever import get_retriever


def build_rag_agent(llm, rebuild=False):

    retriever = get_retriever(rebuild=rebuild)

    @tool
    @observe(name="search-knowledge-base", as_type="retriever", capture_input=False, capture_output=False)
    def search_knowledge_base(question: str) -> str:
        """Search PDF, TXT and Markdown documents for relevant information."""
        langfuse = get_client()
        langfuse.update_current_span(input={"query": question})

        documents = retriever.invoke(question)

        if not documents:
            langfuse.update_current_span(
                output={"documents_found": 0, "result": "No relevant documents found."}
            )
            return "No relevant documents found."

        results = []
        sources = []
        for doc in documents:
            source = doc.metadata.get("source", "Unknown")
            sources.append(source)
            results.append(
                f"Source: {source}\n"
                f"Content: {doc.page_content}"
            )

        output_text = "\n\n".join(results)
        langfuse.update_current_span(
            output={
                "documents_found": len(documents),
                "sources": sources,
                "preview": output_text[:1000]
            }
        )
        return output_text

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
    @observe(name="rag-agent", as_type="agent", capture_input=False, capture_output=False)
    async def ask_rag_agent(question: str) -> str:
        """Delegate document-related questions to the RAG agent."""
        langfuse = get_client()
        langfuse.update_current_span(input={"question": question})

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

        final_content = str(result["messages"][-1].content)
        langfuse.update_current_span(output={"response": final_content})
        return final_content

    return ask_rag_agent

