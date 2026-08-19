# FOR jo — Phase 6 Breakdown: The FastAPI Web Server & Concurrency

## Step 1: What approach did you take, and why?
We wrapped our modular `RAGEngine` inside a high-performance **FastAPI** web application with two core endpoints:
- `POST /ingest`: Triggers the parsing, chunking, embedding, and indexing pipeline.
- `POST /chat`: Receives user queries, runs the hybrid retrieval + reranking pipeline, and returns the LLM-generated answer.

To make this production-ready, we used the **`lifespan` context manager** to initialize the `RAGEngine` once on startup and store it in `app.state`, and a **`ThreadPoolExecutor`** to offload CPU-heavy tasks without blocking the asynchronous event loop.

## Step 2: What other approaches did you consider but abandon?
- **Instantiating the Engine inside route handlers**: Abandoned because loading embedding models, Cross-Encoders, and reading disk indices takes seconds and gigabytes of RAM if repeated on every HTTP request.
- **Running CPU-heavy ingestion directly on the async event loop**: Abandoned because Python's `asyncio` event loop is single-threaded. Running synchronous CPU-heavy regex, chunking, and vector math directly on the loop freezes the server, making it unable to respond to any other user.
- **Putting Pydantic models in `main.py`**: Abandoned in favor of keeping all request/response data contracts in `app/models/schemas.py` to maintain a clean, modular architecture.

## Step 3: How do the different parts connect?
1. **Startup (`lifespan`)**:
   - `RAGEngine` is initialized once and placed into RAM via `app.state.rag`.
   - `ThreadPoolExecutor` is created and attached to `app.state.executer`.
2. **When an HTTP request arrives (`/chat` or `/ingest`)**:
   - FastAPI parses and validates the incoming JSON against Pydantic models (`QueryRequest`, `IngestRequest`).
   - The route handler pulls `rag` from `app.state.rag`.
   - `loop.run_in_executor` sends the execution to a background worker thread.
   - Once finished, the result is packaged into a clean JSON response and returned to the client.

## Step 4: What tools, methods, or frameworks did you use?
- **FastAPI**: Modern, fast web framework for building APIs with Python based on standard type hints.
- **Pydantic (`BaseModel`)**: Validates input data structures before our business logic ever touches them.
- **`asyncio` & `concurrent.futures.ThreadPoolExecutor`**: Enables cooperative multitasking where I/O operations (network, waiting) don't block CPU operations (math, embeddings).
- **`contextlib.asynccontextmanager` (`lifespan`)**: The modern, officially supported pattern for FastAPI startup and shutdown lifecycle events.

## Step 5: What tradeoffs did you make?
- **`await` in ThreadPool vs True Asynchronous Task Queue**: In `/ingest`, we `await` the thread pool execution, meaning the HTTP client waits until ingestion is complete before receiving a response. For huge files in enterprise production, you would return a `202 Accepted` immediately and offload the work to a distributed worker pool like Celery/RabbitMQ. For our local project, awaiting makes verification and debugging immediate and straightforward.

## Step 6: What mistakes are commonly made when implementing this?
- **Blocking the Event Loop**: Calling synchronous functions with heavy computation inside `async def` endpoints without using `run_in_executor`.
- **Global Variable Spaghetti**: Using loose global variables across files instead of attaching long-lived services to `app.state` or using FastAPI dependency injection (`Depends`).
- **Ignoring Type Hints**: Omitting `: RAGEngine` type hints, which causes IDEs to lose autocomplete and static type validation.

## Step 7: What pitfalls should I watch out for?
- **Thread Pool Starvation**: If you set `max_workers=1` and a long-running ingestion is executing, any other task sent to that same executor must wait in line. In high-traffic systems, calibrate `max_workers` based on available CPU cores.
- **Uncontrolled Memory Usage**: If multiple massive transcripts are ingested simultaneously, memory usage will spike during chunking and embedding generation.

## Step 8: Expert vs Beginner thinking
A beginner mixes web framework code, database queries, and AI prompts into a single messy file.
An expert treats the web API as a thin, replaceable **transport layer**. The entire core application logic (`RAGEngine`) remains pure Python and completely decoupled from FastAPI. You could swap FastAPI for Flask, a CLI tool, a Discord bot, or AWS Lambda without changing a single line inside `app/rag/`.

## Step 9: What lessons can I apply to other projects?
- **Separate I/O-bound from CPU-bound logic**: Use `async`/`await` for network requests and API calls; use worker threads or processes for math, data parsing, and model inference.
- **Centralize Data Contracts**: Keep schemas in a dedicated `models/` directory so frontend and backend teams have a single source of truth for request and response payloads.
- **Leverage Lifecycles**: Always initialize expensive resources (DB connection pools, AI models, caches) during server startup, never per-request.
