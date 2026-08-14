from fastapi import FastAPI
import asyncio
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from app.config import get_settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    executer = ThreadPoolExecutor(max_workers=1)
    loop = asyncio.get_event_loop()
    rag = PodcastRAG(
        persist_dir=settings.RAG_PERSIST_DIR,
        chunk_size=settings.RAG_CHUNK_SIZE,
        chunk_overlap=settings.RAG_CHUNK_OVERLAP,
        top_k=settings.RAG_TOP_K,
        top_n=settings.RAG_TOP_N
    )
    await loop.run_in_executor(executer,rag.load_state)
    app.state.rag = rag
    app.state.executer = executer

    yield

    executer.shutdown(wait=True)    

app = FastAPI(lifespan=lifespan)

@app.get("/")
def health():
    return {"message":"server is running"}