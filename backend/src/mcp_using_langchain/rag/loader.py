
from pathlib import Path
import docx

from langchain_core.documents import Document
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
            for doc in loader.load():
                doc.metadata["title"] = file_path.stem
                documents.append(doc)

        elif suffix in [".txt", ".md"]:

            loader = TextLoader(
                str(file_path),
                encoding="utf-8"
            )
            for doc in loader.load():
                doc.metadata["title"] = file_path.stem
                documents.append(doc)

        elif suffix == ".docx":
            # Avoid duplicate loading if extracted .txt companion already exists
            if file_path.with_suffix(".txt").exists():
                continue
            try:
                doc_obj = docx.Document(str(file_path))
                text_parts = [p.text for p in doc_obj.paragraphs if p.text.strip()]
                for table in doc_obj.tables:
                    for row in table.rows:
                        row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                        if row_text:
                            text_parts.append(row_text)
                if text_parts:
                    documents.append(
                        Document(
                            page_content="\n".join(text_parts),
                            metadata={"source": str(file_path), "title": file_path.stem}
                        )
                    )
            except Exception as e:
                print(f"Warning: Failed to load docx {file_path}: {e}")

    if not documents:
        raise ValueError(
            "No documents found inside rag/documents/"
        )

    print(f"\nLoaded {len(documents)} document pages/files")

    return documents
