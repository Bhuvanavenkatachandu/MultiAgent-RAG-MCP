
from langchain_community.embeddings.fastembed import FastEmbedEmbeddings


def get_embeddings():

    embeddings = FastEmbedEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    return embeddings

