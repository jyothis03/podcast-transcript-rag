# FOR jo — Phase 3 Breakdown: Storage Layer (ChromaDB + BM25)

## Step 1: What approach did you take, and why?
We built two separate storage engines inside a single file (`store.py`):
- **ChromaStore** wraps ChromaDB for dense semantic search (finds chunks by meaning).
- **BM25Store** wraps rank_bm25 for sparse keyword search (finds chunks by exact words).

The starting point was: "How will the retriever find the right chunks later?" The answer is hybrid search — two engines that complement each other's weaknesses. ChromaDB understands meaning but misses exact keywords. BM25 finds exact keywords but doesn't understand meaning. Together they cover both cases.

## Step 2: What other approaches did you consider but abandon?
- **Single-store approach (ChromaDB only)**: Simpler, but would miss keyword matches. If a user searches for "RLHF" and the chunk says "reinforcement learning from human feedback" without the acronym, ChromaDB catches it. But if the chunk DOES contain "RLHF", BM25 would rank it higher because it's an exact match. Dropping BM25 sacrifices precision on specific terms.
- **Elasticsearch instead of BM25**: Elasticsearch is a production-grade search engine that does what BM25 does (and more). I rejected it because it requires running a separate server process, which adds deployment complexity for a learning project. `rank_bm25` gives us the same algorithm in a single Python import.
- **FAISS instead of ChromaDB**: FAISS (by Facebook) is faster for pure vector search but has no built-in persistence, no metadata filtering, and no automatic embedding. ChromaDB handles all of that out of the box.

## Step 3: How do the different parts connect?
1. During **ingestion** (`/ingest` endpoint, Phase 6):
   - Parser produces `List[TranscriptSegment]`
   - Chunker produces `List[Chunk]`
   - `ChromaStore.add_chunks()` embeds and stores vectors + metadata
   - `BM25Store.add_chunks()` tokenizes and indexes keywords
   - `BM25Store.save()` persists the keyword index to disk

2. During **querying** (`/query` endpoint, Phase 6):
   - `ChromaStore.search()` returns chunks ranked by semantic similarity
   - `BM25Store.search()` returns chunks ranked by keyword relevance
   - Both feed into the Retriever (Phase 4) which fuses the results

3. During **server startup** (`main.py` lifespan):
   - ChromaDB auto-loads from `persist_dir` (built-in persistence)
   - `BM25Store.load()` manually reads the pickle file and rebuilds the index

## Step 4: What tools, methods, or frameworks did you use?
- **ChromaDB**: Chosen for its all-in-one design (embedding + storage + search + persistence). It uses HNSW (Hierarchical Navigable Small World) graphs internally for fast approximate nearest neighbor search.
- **SentenceTransformers (`all-MiniLM-L6-v2`)**: A small, fast embedding model that converts text into 384-dimensional vectors. Chosen because it's lightweight enough to run on CPU without a GPU.
- **rank_bm25 (`BM25Okapi`)**: The Okapi BM25 variant, which is the standard in information retrieval. It improves on basic TF-IDF by adding document length normalization.
- **pickle**: Python's built-in serialization. Used for BM25 persistence because the data structures (lists of dicts, lists of lists) are simple Python types that pickle handles perfectly.

## Step 5: What tradeoffs did you make?
- **Tradeoff 1**: We store chunk data as plain dictionaries in BM25Store, not Pydantic models. This makes pickling reliable but loses type validation on load. We accepted this because the data was already validated by Pydantic when it entered the system.
- **Tradeoff 2**: We rebuild the entire BM25 index on every `add_chunks()` call. This is O(n) where n is the total corpus size. For millions of chunks this would be slow, but for our podcast-scale data (thousands of chunks) it's instant.
- **Tradeoff 3**: ChromaDB metadata only supports primitive types, so we flatten `speakers: List[str]` into a comma-separated string. This adds parse/unparse logic but keeps us within Chroma's constraints.

## Step 6: What mistakes are commonly made?
- **Forgetting the metadata type constraint**: Passing a Python list directly into ChromaDB metadata causes a silent failure or crash. Always convert lists to strings.
- **Not handling empty results**: ChromaDB returns `{"ids": [[]], ...}` when nothing matches. If you don't check for this, you get index errors when accessing `results["ids"][0][0]`.
- **Building BM25 only in `load()`**: This creates a gap where freshly ingested data isn't searchable until a server restart. Always rebuild the index in `add_chunks()` too.

## Step 7: What pitfalls should I watch out for?
- **Cosine distance vs. cosine similarity**: ChromaDB returns distance (0 = identical), but humans think in similarity (1 = identical). Always convert with `score = 1.0 - distance`. Mixing these up means your "best" results show up last.
- **BM25 scores are NOT between 0 and 1**: They can be any positive number (3.8, 12.5, etc.). You cannot directly compare a BM25 score with a ChromaDB score. This is why Phase 4 uses Reciprocal Rank Fusion (based on rankings, not scores).
- **Pickle security**: Never load pickle files from untrusted sources. Pickle can execute arbitrary code during deserialization. In our case it's safe because we only load files we created ourselves.

## Step 8: What would an expert notice?
- **Standardized output format**: Both `ChromaStore.search()` and `BM25Store.search()` return `List[Dict[str, Any]]` with identical keys. This is a deliberate design choice (Data Contract pattern) that makes the retriever's job trivial — it doesn't need to know which store a result came from.
- **Separation of concerns**: The stores know nothing about retrieval strategy, ranking fusion, or LLM generation. They just store and search. This makes each component independently testable and replaceable.

## Step 9: What lessons can I apply to other projects?
- **Design your output format before your implementation**: If two components need to feed into the same downstream system, agree on the dictionary/schema shape first. This saves hours of refactoring later.
- **Persistence is not optional**: Any in-memory data structure (like BM25) needs an explicit save/load strategy. Ask yourself early: "What happens when the process restarts?"
- **Use sentinel values for missing data**: We use `-1.0` for unavailable timestamps and `""` for missing speakers. Sentinels are cleaner than `None` because they don't require null-checking everywhere downstream.
