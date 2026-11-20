
from pathlib import Path

from langchain_community.vectorstores import FAISS


VECTORSTORE_DIR = (
    Path(__file__).resolve().parents[3] / ".faiss_index"
)


def create_vectorstore(chunks, embeddings):

    if not chunks:
        raise ValueError("No document chunks to index")

    vectorstore = FAISS.from_documents(
        documents=chunks,
        embedding=embeddings
    )

    VECTORSTORE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    vectorstore.save_local(
        str(VECTORSTORE_DIR)
    )

    print("FAISS vectorstore created and saved")

    return vectorstore


def load_vectorstore(embeddings):

    if not (
        VECTORSTORE_DIR / "index.faiss"
    ).exists():
        raise FileNotFoundError(
            "FAISS index does not exist. Build it first."
        )

    vectorstore = FAISS.load_local(
        str(VECTORSTORE_DIR),
        embeddings,
        allow_dangerous_deserialization=True
    )

    print("FAISS vectorstore loaded")

    return vectorstore
