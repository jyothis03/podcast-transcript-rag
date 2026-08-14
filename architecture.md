# Podcast RAG Pipeline — Architecture

---

## Design Decisions

| Decision | Choice |
|----------|--------|
| **Target user** | Someone who already has transcript files (SRT/TXT) |
| **Input formats** | SRT (primary, with timestamps) + Plain TXT (fallback, degraded citations) |
| **Interface** | FastAPI backend + polished chat-like web UI |
| **Ingestion model** | Single file upload per request, auto-generated episode IDs, permanent storage |
| **Query scope** | Search all episodes by default, optional filter by podcast/episode |
| **Citation style** | Card-style (podcast name, episode, speaker, time range, quote) |
| **Speaker detection** | Best-effort regex parsing of SRT text (e.g. `[Speaker]:`, `Speaker:`) |
| **LLM provider** | Groq (default), Gemini (alternative), configured via `.env` |
| **Vector store** | ChromaDB (local-first, persistent) |
| **TXT handling** | Supported with degraded citations (no timestamps, UI shows a note) |

---

## System Flow

```
                        INGESTION FLOW
                        ──────────────
  ┌─────────────────────┐
  │  User uploads SRT   │
  │  or TXT file via UI │
  │  + podcast name     │
  │  + episode title    │
  └──────────┬──────────┘
             │
             ▼
  ┌─────────────────────┐
  │  TranscriptParser   │   Parses SRT timestamps & speaker
  │  (SRT / TXT)        │   labels; TXT gets no timestamps
  └──────────┬──────────┘
             │  List[TranscriptSegment]
             ▼
  ┌─────────────────────┐
  │  PodcastChunker     │   Merges segments into Chunks
  │  (size/overlap)     │   Preserves timestamps & speakers
  └──────────┬──────────┘
             │  List[Chunk]
             ├──────────────────────────┐
             ▼                          ▼
  ┌──────────────────┐       ┌──────────────────┐
  │  ChromaDB        │       │  BM25 Index      │
  │  (Dense vectors) │       │  (Sparse keywords)│
  └──────────────────┘       └──────────────────┘


                        QUERY FLOW
                        ──────────
  ┌─────────────────────┐
  │  User types query   │
  │  in chat UI         │
  │  (optional filter   │
  │   by podcast/ep)    │
  └──────────┬──────────┘
             │
             ├───────────────────┬───────────────────┐
             ▼                   ▼                   ▼
  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
  │ Dense Vector    │  │ Sparse BM25     │  │ Metadata Filter │
  │ Search          │  │ Search          │  │ (podcast/ep)    │
  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
           │                    │                     │
           └────────────────────┼─────────────────────┘
                                │
                                ▼
                   ┌────────────────────┐
                   │ Reciprocal Rank    │
                   │ Fusion (RRF)       │
                   └─────────┬──────────┘
                             │ Top-K candidates
                             ▼
                   ┌────────────────────┐
                   │ Cross-Encoder      │
                   │ Reranker           │
                   └─────────┬──────────┘
                             │ Top-N reranked
                             ▼
                   ┌────────────────────┐
                   │ LLM Generator      │
                   │ (Groq / Gemini)    │
                   └─────────┬──────────┘
                             │
                             ▼
                   ┌────────────────────┐
                   │ Chat Response +    │
                   │ Citation Cards     │
                   └────────────────────┘
```

---

## Core Modules

### 1. Application Layer (`app/main.py`, `app/config.py`, `app/dependencies.py`)
- FastAPI with lifespan management (initializes RAG engine at boot)
- Pydantic Settings validates `.env` at boot (`RAG_PERSIST_DIR`, `LLM_PROVIDER`, API keys)
- Dependency injection for RAG engine and thread pool executor

### 2. Schemas & Models (`app/models/schemas.py`)
- `TranscriptSegment` — atomic unit: speaker, start_time, end_time, text
- `PodcastEpisode` — container: title, episode_id (auto-generated), podcast_name, segments
- `Chunk` — merged segments: chunk_id, text with speaker labels, time range, speaker list
- `QueryRequest` — query text + optional filters (podcast_name, episode_id)
- `QueryResponse` — answer text + list of `Citation` cards
- `Citation` — episode_id, title, podcast_name, start_time, end_time, quote, speakers

### 3. Transcript Parser (`app/rag/parser.py`)
- `parse_srt(content: str) -> List[TranscriptSegment]`
  - Parses SRT format (sequence number, `HH:MM:SS,mmm --> HH:MM:SS,mmm`, text)
  - Converts timestamps to float seconds
  - Best-effort speaker extraction via regex patterns (`[Name]:`, `Name:`)
- `parse_txt(content: str) -> List[TranscriptSegment]`
  - Splits by paragraphs or newlines
  - No timestamps (start_time=-1, end_time=-1 to signal "unavailable")
  - Speaker defaults to "Unknown"

### 4. Chunker (`app/rag/chunker.py`)
- Merges sequential segments up to `RAG_CHUNK_SIZE` (500 chars)
- Character-threshold overlap (`RAG_CHUNK_OVERLAP` = 80 chars) at segment boundaries
- Formats chunk text with speaker labels: `[Speaker]: text`
- Deduplicates speaker list per chunk

### 5. Storage (`app/rag/store.py`)
- ChromaDB collection for dense vector storage (`all-MiniLM-L6-v2` embeddings)
- BM25 index (`rank_bm25`) for sparse keyword search
- Persistence to `RAG_PERSIST_DIR`
- Metadata stored per chunk: episode_id, podcast_name, speakers, start_time, end_time

### 6. Hybrid Retriever (`app/rag/retriever.py`)
- Executes dense search (ChromaDB) and sparse search (BM25) in parallel
- Applies optional metadata filters (podcast_name, episode_id) to ChromaDB query
- Merges results via Reciprocal Rank Fusion (RRF)
- Re-scores Top-K candidates with Cross-Encoder (`ms-marco-MiniLM-L-6-v2`) → Top-N

### 7. LLM Engine (`app/rag/engine.py`)
- `PodcastRAG` facade class — orchestrates parser → chunker → store → retriever → LLM
- Groq client (default) and Gemini client (alternative), selected via `LLM_PROVIDER` env var
- System prompt enforces grounded answers with citation format (episode, timestamp, quote)
- Handles TXT-sourced chunks gracefully (instructs LLM to omit timestamps when unavailable)

### 8. API Routes (`app/api/routes.py`)
- `POST /ingest` — accepts `UploadFile` + form fields (podcast_name, title), returns episode_id
- `POST /query` — accepts `QueryRequest` JSON, returns `QueryResponse`
- `GET /episodes` — lists all ingested episodes (for the UI filter dropdown)
- `GET /health` — status check

### 9. Web UI (`app/static/`)
- Chat-like interface with message bubbles
- File upload area (drag & drop SRT/TXT)
- Filter bar / dropdown to select podcast or episode
- Citation cards rendered below the LLM answer
- Timestamps displayed as `HH:MM:SS` (or "N/A" for TXT-sourced episodes)

---

## Directory Structure

```
podcast_rag/
├── architecture.md
├── requirements.txt
├── .env
├── app/
│   ├── __init__.py
│   ├── config.py             # Pydantic settings
│   ├── dependencies.py       # FastAPI DI helpers
│   ├── main.py               # FastAPI entry + lifespan
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py         # /ingest, /query, /episodes, /health
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py        # All Pydantic models
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── parser.py         # SRT/TXT → TranscriptSegment
│   │   ├── chunker.py        # Segments → Chunks
│   │   ├── store.py          # ChromaDB + BM25 persistence
│   │   ├── retriever.py      # Hybrid search + RRF + reranker
│   │   └── engine.py         # PodcastRAG facade + LLM generation
│   └── static/               # Web UI files
│       ├── index.html
│       ├── style.css
│       └── app.js
└── test_rag.py               # E2E verification
```

---

## 6-Phase Implementation Plan

| Phase | Focus | Key Deliverables |
|-------|-------|-----------------|
| **1** | Setup & Data Models | `config.py`, `schemas.py`, `main.py` scaffold ✅ **DONE** |
| **2** | Parsing & Chunking | `parser.py` (SRT/TXT), `chunker.py` |
| **3** | Storage Layer | `store.py` (ChromaDB + BM25 init, add, persist, load) |
| **4** | Hybrid Retrieval & Reranking | `retriever.py` (dense + sparse + RRF + cross-encoder) |
| **5** | LLM Generation & Engine | `engine.py` (Groq/Gemini clients, system prompt, PodcastRAG facade) |
| **6** | FastAPI Routes & Web UI | `routes.py`, `static/` (chat UI), `test_rag.py` |
