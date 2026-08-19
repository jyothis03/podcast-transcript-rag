import asyncio
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.rag.engine import RAGEngine
from app.models.schemas import QueryRequest, IngestRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    executer = ThreadPoolExecutor(max_workers=2)
    rag = RAGEngine(persist_dir=settings.RAG_PERSIST_DIR)

    app.state.rag = rag
    app.state.executer = executer

    print("Podcast RAG Engine initialized successfully.")
    yield

    print("Shutting down ThreadPoolExecutor...")
    executer.shutdown(wait=True)


app = FastAPI(
    title="Podcast Transcript RAG API",
    description="Hybrid RAG pipeline combining ChromaDB Dense Search, BM25 Keyword Search, Cross-Encoder Reranking, and Groq LLM Generation.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local development and web frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    return {
        "status": "online",
        "message": "Podcast RAG Server is running",
        "docs_url": "/docs",
    }


@app.post("/ingest")
async def ingest_transcript(request: IngestRequest):
    rag: RAGEngine = app.state.rag
    loop = asyncio.get_event_loop()

    try:
        chunks_count = await loop.run_in_executor(
            app.state.executer,
            rag.ingest_podcast,
            request.file_path,
            request.podcast_name,
            request.episode_id,
        )
        return {
            "status": "success",
            "message": f"Successfully ingested {chunks_count} chunks from '{request.podcast_name}'",
            "chunks_ingested": chunks_count,
            "podcast_name": request.podcast_name,
            "episode_id": request.episode_id,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


@app.post("/chat")
async def chat_with_podcast(request: QueryRequest):
    rag: RAGEngine = app.state.rag
    loop = asyncio.get_event_loop()

    where_filter = None
    if request.podcast_name:
        where_filter = {"podcast_name": request.podcast_name}

    try:
        answer = await loop.run_in_executor(
            app.state.executer,
            rag.ask_question,
            request.query,
            where_filter,
            request.top_k,
            request.top_n,
        )
        return {
            "query": request.query,
            "answer": answer,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat query failed: {str(e)}")