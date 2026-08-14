from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    RAG_PERSIST_DIR : str = "./rag_store"
    RAG_CHUNK_SIZE :  int = 500
    RAG_CHUNK_OVERLAP : int = 80 
    RAG_TOP_K : int = 20
    RAG_TOP_N : int = 5

    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    RERANKER_MODEL_NAME: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    LLM_PROVIDER : str = 'gemini'
    GEMINI_API_KEY : Optional[str] = None
    GROQ_API_KEY : Optional[str] = None

    
    API_KEY : str
    ENV : str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
@lru_cache
def get_settings() -> Settings:
    return Settings()