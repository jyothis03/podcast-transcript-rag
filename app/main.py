import asyncio
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import os

from app.config import get_settings
from app.rag.engine import RAGEngine
from app.rag.graph import PodcastRAGGraph
from app.models.schemas import QueryRequest, IngestRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    executer = ThreadPoolExecutor(max_workers=2)
    rag_engine = RAGEngine(persist_dir=settings.RAG_PERSIST_DIR)
    rag_graph = PodcastRAGGraph(engine=rag_engine)

    # Ingest default transcript on startup if empty
    try:
        pts = rag_engine.qdrant_store.client.get_collection(rag_engine.qdrant_store.collection_name).points_count or 0
    except Exception:
        pts = 0
    if pts == 0 and os.path.exists("data/sample_podcast.srt"):
        rag_engine.ingest_podcast("data/sample_podcast.srt", podcast_name="Lex Fridman Podcast", episode_id=1)

    app.state.rag = rag_engine
    app.state.graph = rag_graph
    app.state.executer = executer

    print("Podcast RAG Engine & LangGraph Conversation Router initialized.")
    yield

    print("Shutting down ThreadPoolExecutor...")
    executer.shutdown(wait=True)


app = FastAPI(
    title="Podcast Transcript RAG & LangGraph Agent API",
    description="Stateful Multi-Turn RAG API with LangGraph Routing, Qdrant Hybrid Search, Cross-Encoder Reranking, and Gemini/Groq Fallback.",
    version="2.0.0",
    lifespan=lifespan,
)

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
        "message": "Podcast RAG & LangGraph Server is running",
        "docs_url": "/docs",
    }


@app.get("/status")
def get_system_status():
    rag: RAGEngine = app.state.rag
    try:
        count = rag.qdrant_store.client.get_collection(rag.qdrant_store.collection_name).points_count or 0
    except Exception:
        count = 0
    return {
        "status": "online",
        "indexed_chunks": count,
        "primary_model": rag.settings.GEMINI_MODEL_NAME,
        "failover_model": rag.settings.GROQ_MODEL_NAME,
    }


@app.post("/upload")
async def upload_transcript(
    file: UploadFile = File(...),
    podcast_name: str = Form("Uploaded Podcast"),
    episode_id: str = Form("1"),
):
    save_dir = "./data/uploads"
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, file.filename)
    
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    rag: RAGEngine = app.state.rag
    loop = asyncio.get_event_loop()
    try:
        chunks_count = await loop.run_in_executor(
            app.state.executer,
            rag.ingest_podcast,
            file_path,
            podcast_name,
            episode_id,
        )
        return {
            "status": "success",
            "filename": file.filename,
            "chunks_ingested": chunks_count,
            "podcast_name": podcast_name,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest uploaded file: {str(e)}")


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
            "message": f"Successfully ingested {chunks_count} chunks from '{request.podcast_name}' into Qdrant",
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
    graph: PodcastRAGGraph = app.state.graph
    loop = asyncio.get_event_loop()

    thread_id = request.thread_id or "default_session"

    try:
        answer = await loop.run_in_executor(
            app.state.executer,
            graph.chat,
            request.query,
            thread_id,
            request.podcast_name,
        )
        return {
            "query": request.query,
            "answer": answer,
            "thread_id": thread_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat query failed: {str(e)}")