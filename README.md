# 🎙️ Podcast Transcript RAG Pipeline

A modular, high-performance Retrieval-Augmented Generation (RAG) backend engineered specifically for timestamped audio transcripts and subtitle files (`.srt`, `.txt`).

Built from first principles using a **Two-Stage Coarse-to-Fine Hybrid Retrieval** architecture combining **ChromaDB Dense Vector Search**, **BM25 Sparse Keyword Search**, **Reciprocal Rank Fusion (RRF)**, **Cross-Encoder Neural Reranking**, and **Groq (Llama-3)** generation wrapped in an asynchronous **FastAPI** web server.

---

## 🏛️ High-Level System Design (HLSD)

```
                            INGESTION PIPELINE
                            ──────────────────
     ┌──────────────────────┐
     │ Raw Transcript File  │ (SRT with timestamps or plain TXT)
     └──────────┬───────────┘
                │
                ▼
     ┌──────────────────────┐
     │   TranscriptParser   │ Extracts timestamps & detects speaker tags (`[Speaker]:`)
     └──────────┬───────────┘
                │ List[TranscriptSegment]
                ▼
     ┌──────────────────────┐
     │    PodcastChunker    │ Sliding window chunking (500 chars) with segment overlap
     └──────────┬───────────┘
                │ List[Chunk]
        ┌───────┴───────────────────┐
        ▼                           ▼
┌───────────────┐           ┌───────────────┐
│  ChromaStore  │           │   BM25Store   │
│ (Dense Index) │           │(Sparse Index) │
└───────────────┘           └───────────────┘


                              QUERY PIPELINE
                              ──────────────
     ┌──────────────────────┐
     │  User Question Query │
     └──────────┬───────────┘
        ┌───────┴───────────────────┐
        ▼                           ▼
┌───────────────┐           ┌───────────────┐
│ Dense Search  │           │ Sparse Search │
│ (ChromaDB)    │           │ (BM25Okapi)   │
└───────┬───────┘           └───────┬───────┘
        │ Top-20                    │ Top-20
        └─────────────┬─────────────┘
                      │
                      ▼
        ┌───────────────────────────┐
        │  Reciprocal Rank Fusion   │  RRF Score = 1 / (60 + rank)
        │  (Unified Candidate Pool) │
        └─────────────┬─────────────┘
                      │ Top-20 Fused Candidates
                      ▼
        ┌───────────────────────────┐
        │   Cross-Encoder Reranker  │  `ms-marco-MiniLM-L-6-v2`
        │   (Deep Attention Score)  │
        └─────────────┬─────────────┘
                      │ Top-5 Verified Chunks
                      ▼
        ┌───────────────────────────┐
        │   Groq LLM Generation     │  `llama3-8b-8192` with strict grounding
        └─────────────┬─────────────┘
                      │
                      ▼
        ┌───────────────────────────┐
        │ Final Answer + Timestamps │
        └───────────────────────────┘
```

---

## 🔬 Low-Level System Design (LLSD) & Modules

### 1. Ingestion & Parsing (`app/rag/parser.py`)
- **`TranscriptParser`**: Uses compiled regular expressions to extract start/end seconds and speaker dialogue tags from `.srt` subtitles. TXT files fall back to sentinel timestamp values (`-1.0`).

### 2. Segment-Aware Chunking (`app/rag/chunker.py`)
- **`PodcastChunker`**: Preserves sentence and dialogue turns by grouping whole `TranscriptSegment`s up to a configurable target (default 500 characters) and maintaining a character-threshold overlap (default 80 characters) by carrying over the trailing segments.

### 3. Dual Storage Layer (`app/rag/store.py`)
- **`ChromaStore` (Dense)**: Wraps `chromadb.PersistentClient` using the `all-MiniLM-L6-v2` embedding model (384 dimensions) with cosine distance metrics. Stores metadata (timestamps, episode ID, podcast name, speakers).
- **`BM25Store` (Sparse)**: Wraps `rank_bm25.BM25Okapi` for exact keyword and acronym matching. Serializes state to disk via `pickle` for persistence across restarts.

### 4. Two-Stage Hybrid Retrieval & Reranking (`app/rag/retriever.py`)
- **Stage 1 (Coarse Filter)**: Executes parallel dense and sparse searches, fetching Top-20 candidates from each engine. Merges them via **Reciprocal Rank Fusion (RRF)**:
  $$\text{RRF Score} = \sum_{m \in \{\text{Dense}, \text{Sparse}\}} \frac{1}{60 + \text{rank}_m}$$
- **Stage 2 (Fine Filter)**: Passes fused candidate pairs `[Query, Chunk Text]` to the `cross-encoder/ms-marco-MiniLM-L-6-v2` model. The cross-attention mechanism re-scores candidates and extracts the Top-5 most relevant chunks.

### 5. Orchestration Engine (`app/rag/engine.py`)
- **`RAGEngine`**: Acts as a **Facade Pattern** coordinator. Formats retrieved chunks with timestamp labels (`[at 14.5s]`), constructs the grounded system prompt, and calls the Groq LPU API (`llama3-8b-8192`) at `temperature=0.0`.

### 6. Transport & API Layer (`app/main.py`)
- **FastAPI Web Server**:
  - Uses `lifespan` context management to initialize models and connections once during startup into `app.state`.
  - Uses a `ThreadPoolExecutor` to offload CPU-intensive parsing and embedding math without blocking the asynchronous `asyncio` event loop.
  - Exposes interactive OpenAPI documentation at `/docs` and CORS middleware for frontend integrations.

---

## 📂 Project Directory Structure

```
podcast_rag/
├── README.md                 # System Architecture & Documentation
├── requirements.txt          # Production dependencies
├── .env                      # Environment variables & API keys
├── .gitignore                # Git filtering rules
├── data/
│   └── sample_podcast.srt    # Sample transcript for testing
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI application & endpoints
│   ├── config.py             # Pydantic Settings & environment validation
│   ├── dependencies.py       # FastAPI dependency injection
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py        # Pydantic schemas (IngestRequest, QueryRequest, Chunk, etc.)
│   └── rag/
│       ├── __init__.py
│       ├── parser.py         # SRT / TXT regex parsing
│       ├── chunker.py        # Segment-aware overlapping chunker
│       ├── store.py          # ChromaDB & BM25Okapi dual-store
│       ├── retriever.py      # Hybrid RRF + Cross-Encoder reranker
│       └── engine.py         # RAGEngine facade & Groq LLM integration
```

---

## ⚡ Quickstart Guide

### 1. Prerequisites & Environment Setup

Clone the repository and activate your virtual environment:

```powershell
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

Install all dependencies:

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create or edit your `.env` file in the project root:

```env
GROQ_API_KEY=gsk_your_groq_api_key_here
API_KEY=dev-api-key-12345
ENV=development
RAG_PERSIST_DIR=./data
```

---

## 🚀 Running the Application

Start the FastAPI server:

```powershell
.\venv\Scripts\uvicorn.exe app.main:app --reload
```

Once running, access the services:
- **Interactive Swagger API Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative Redoc API Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **Health Check Endpoint**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)

---

## 🔌 API Endpoints & Usage

### 1. Ingest a Transcript (`POST /ingest`)
Parses, chunks, embeds, and indexes a podcast file into both vector and keyword storage.

**Request Body (`application/json`):**
```json
{
  "file_path": "data/sample_podcast.srt",
  "podcast_name": "Lex Fridman Podcast",
  "episode_id": 1
}
```

**Response (`200 OK`):**
```json
{
  "status": "success",
  "message": "Successfully ingested 3 chunks from 'Lex Fridman Podcast'",
  "chunks_ingested": 3,
  "podcast_name": "Lex Fridman Podcast",
  "episode_id": 1
}
```

---

### 2. Ask a Question (`POST /chat`)
Executes hybrid retrieval, cross-encoder reranking, and generates an answer with timestamps.

**Request Body (`application/json`):**
```json
{
  "query": "What did Sam say about RLHF and automated alignment?",
  "podcast_name": "Lex Fridman Podcast",
  "top_k": 20,
  "top_n": 5
}
```

**Response (`200 OK`):**
```json
{
  "query": "What did Sam say about RLHF and automated alignment?",
  "answer": "According to the transcript, Sam stated that RLHF (reinforcement learning from human feedback) is a great first step, but it is not a silver bullet. He emphasized that scalable automated alignment techniques will be necessary as models become superintelligent [at 26.5s]."
}
```
