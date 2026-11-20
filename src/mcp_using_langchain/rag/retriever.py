
from langchain_text_splitters import (
    RecursiveCharacterTextSplitter
)

from .loader import load_documents
from .embeddings import get_embeddings
from .vectorstore import (
    create_vectorstore,
    load_vectorstore
)


def get_retriever(rebuild=False):

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

    else:

        try:
            vectorstore = load_vectorstore(
                embeddings
            )

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

    retriever = vectorstore.as_retriever(
        search_kwargs={
            "k": 4
        }
    )

    return retriever
