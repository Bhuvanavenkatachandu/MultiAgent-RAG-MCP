
from pathlib import Path

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader
)


DOCUMENTS_DIR = (
    Path(__file__).parent / "documents"
)


def load_documents():

    documents = []

    DOCUMENTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    for file_path in DOCUMENTS_DIR.rglob("*"):

        if not file_path.is_file():
            continue

        suffix = file_path.suffix.lower()

        if suffix == ".pdf":

            loader = PyPDFLoader(str(file_path))
            documents.extend(loader.load())

        elif suffix in [".txt", ".md"]:

            loader = TextLoader(
                str(file_path),
                encoding="utf-8"
            )

            documents.extend(loader.load())

    if not documents:
        raise ValueError(
            "No documents found inside rag/documents/"
        )

    print(f"\nLoaded {len(documents)} document pages/files")

    return documents
