
import os
from dotenv import load_dotenv
from huggingface_hub import login
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings

load_dotenv()


def _configure_huggingface_auth():
    """Configures Hugging Face Hub authentication using HF_TOKEN environment variable."""
    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        try:
            login(token=hf_token, add_to_git_credential=False)
        except Exception:
            pass


def get_embeddings():
    _configure_huggingface_auth()

    embeddings = FastEmbedEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    return embeddings

