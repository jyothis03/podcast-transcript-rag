# FOR jo — Phase 5 Breakdown: The RAG Engine

## Step 1: What approach did you take, and why?
We built the `RAGEngine` class to act as the "Orchestrator" or "Facade". Its entire purpose is to hide the massive complexity of our pipeline (Parser, Chunker, ChromaDB, BM25, RRF, Cross-Encoder) behind two simple commands: `ingest_podcast` and `ask_question`. 

I took this approach because of the **Facade Design Pattern**. If we ever need to swap ChromaDB for Pinecone, or swap Groq for OpenAI, the frontend API doesn't care. The Web API only knows about `engine.ask_question()`.

## Step 2: What other approaches did you consider but abandon?
- **Putting all this code directly in `main.py` (FastAPI)**: I abandoned this because it makes the web server bloated and impossible to test. By keeping the Engine in pure Python, we can test it completely independently of the web server.
- **Using LangChain's `RetrievalQA` chain**: I abandoned this because LangChain abstracts away the prompt creation. We want total control over exactly how the podcast chunks are formatted and presented to the LLM.

## Step 3: How do the different parts connect?
The Engine is the central nervous system:
- **Ingestion**: It takes a raw file path $\rightarrow$ hands it to the Parser $\rightarrow$ hands segments to the Chunker $\rightarrow$ hands chunks to ChromaDB and BM25 $\rightarrow$ saves BM25 to disk.
- **Querying**: It takes a query $\rightarrow$ hands it to the Retriever $\rightarrow$ gets the Top 5 chunks $\rightarrow$ formats them into a clean string $\rightarrow$ injects them into a System Prompt $\rightarrow$ sends it to Groq $\rightarrow$ returns the text.

## Step 4: What tools, methods, or frameworks did you use?
- **Groq API**: We used Groq because their Llama-3 endpoints use LPUs (Language Processing Units) which are drastically faster than standard GPUs. For RAG, where you want an instant chat feel, Groq's generation speed is unbeatable.
- **Prompt Engineering**: We used a strict system prompt (`Do not guess`) to forcefully ground the LLM in the provided context, heavily reducing hallucinations.

## Step 5: What tradeoffs did you make?
- **Hardcoded Prompts**: We hardcoded the system prompt directly into the Python code. In a massive enterprise app, you might store prompts in a database or a configuration file so non-engineers can tweak them without pushing code. For our scale, hardcoding is much easier to read.
- **No Chat History**: Our `ask_question` method is currently "stateless". It doesn't remember the user's previous question. Adding memory (chat history) requires saving past messages to a database, which we skipped for simplicity.

## Step 6: What mistakes are commonly made when implementing this?
- **Formatting errors**: Sending a raw Python list/dictionary straight into the LLM prompt. LLMs are trained on human-readable text. If you feed them JSON or Python dictionaries, they get confused. We explicitly loop through and format it cleanly (`--- Chunk 1 --- \n text`).
- **Forgetting the early exit check**: If the database is empty, the retriever returns `[]`. If you feed `[]` to the LLM without checking, the LLM will hallucinate. Always check `if not context: return "I don't know"`.

## Step 7: What pitfalls should I watch out for?
- **Context Window Limits**: We are grabbing the Top 5 chunks. If we grabbed the Top 50 chunks, the resulting `context_string` might exceed the LLM's maximum token limit (e.g., 8192 tokens for Llama-3-8b). Always be aware of how many tokens you are cramming into the prompt!
- **Rate Limits**: Groq's free tier has strict rate limits. If you fire off 20 questions a second, your API key will get temporarily blocked.

## Step 8: Expert vs Beginner thinking
A beginner tries to write the RAG prompt, the vector search, and the web endpoints all in one massive 500-line `app.py` file.
An expert heavily decouples their code. Notice how our Engine has zero idea that it's running inside a web app. It just takes strings and returns strings. This means we could easily use this exact same `RAGEngine` in a Discord bot, a Slack bot, or a command-line tool without changing a single line of code!

## Step 9: What lessons can I apply to other projects?
- **String joining**: Using `"\n".join(list)` is the most efficient and Pythonic way to combine text. It's vastly faster and cleaner than doing `string += text` inside a loop.
- **The Facade Pattern**: Whenever you have a complex system with 5+ interacting classes, build a single "Manager" or "Engine" class that acts as the front door for the rest of your app.
