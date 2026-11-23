
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter
)
from mcp_using_langchain.tracing import get_client, observe

from .loader import load_documents
from .embeddings import get_embeddings
from .vectorstore import (
    create_vectorstore,
    load_vectorstore
)


@observe(name="get-or-build-retriever", as_type="span", capture_input=False, capture_output=False)
def get_retriever(rebuild=False):
    langfuse = get_client()
    langfuse.update_current_span(input={"rebuild": rebuild})

    embeddings = get_embeddings()

    if rebuild:

        documents = load_documents()

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=100
        )

        chunks = splitter.split_documents(
            documents
        )

        print(f"Created {len(chunks)} chunks")

        vectorstore = create_vectorstore(
            chunks,
            embeddings
        )
        langfuse.update_current_span(output={"status": "rebuilt", "chunks_count": len(chunks)})

    else:

        try:
            vectorstore = load_vectorstore(
                embeddings
            )
            langfuse.update_current_span(output={"status": "loaded_existing"})

        except FileNotFoundError:

            documents = load_documents()

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=100
            )

            chunks = splitter.split_documents(
                documents
            )

            print(f"Created {len(chunks)} chunks")

            vectorstore = create_vectorstore(
                chunks,
                embeddings
            )
            langfuse.update_current_span(output={"status": "built_initial", "chunks_count": len(chunks)})

    retriever = vectorstore.as_retriever(
        search_kwargs={
            "k": 4
        }
    )

    return retriever

