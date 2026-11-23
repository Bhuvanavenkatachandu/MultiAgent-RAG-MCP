from pathlib import Path
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from mcp_using_langchain.rag.retriever import get_retriever
from mcp_using_langchain.tracing import CallbackHandler, observe
from mcp_using_langchain.guardrails import mask_pii_text
from mcp_using_langchain.llm import extract_text_content


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

        for idx, doc in enumerate(documents, start=1):
            source = doc.metadata.get("source", "Unknown")
            title = doc.metadata.get("title") or Path(source).stem
            sanitized_content = mask_pii_text(doc.page_content)

            results.append(
                f"[Document {idx}: {title} | Source: {source}]\n"
                f"{sanitized_content}"
            )

        return "\n\n".join(results)

    rag_agent = create_react_agent(
        model=llm,
        tools=[search_knowledge_base],
        prompt="""You are a precise Document Knowledge Specialist.
Your task is to search the knowledge base and answer user questions factually and concisely using ONLY the retrieved facts.

Strict Guidelines:
1. Grounding: Base answers strictly on the retrieved document context. Never invent, speculate, or introduce outside assumptions.
2. Negative Conditions: Pay strict attention to negative conditions (e.g., 'not charged', 'free', 'cannot be cancelled', 'exempt'). Never invert or alter the negative meaning.
3. Numerical Precision: Cite exact timeframes, percentages, fees, and rules exactly as written in the text.
4. Abstention: If the retrieved documents do not contain the answer, or if the question asks for policies not documented, explicitly state: "The provided documentation does not contain this information." Do not provide speculative answers.
5. Multi-Chunk Synthesis: When multiple rules or steps apply, state each clearly without conflating distinct conditions."""
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

        return extract_text_content(result["messages"][-1].content)

    return ask_rag_agent
