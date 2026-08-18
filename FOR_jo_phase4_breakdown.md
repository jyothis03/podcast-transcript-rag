# FOR jo — Phase 4 Breakdown: Hybrid Retrieval & Reranking

## Step 1: What approach did you take, and why?
We built a "Two-Stage Pipeline" (also known as Coarse-to-Fine retrieval). 
1. **Stage 1 (Coarse Filter)**: We use ChromaDB and BM25 to quickly filter thousands of chunks down to ~20 candidates, merging them using Reciprocal Rank Fusion (RRF).
2. **Stage 2 (Fine Filter)**: We use a Cross-Encoder neural network to deeply read the query and the 20 candidates together, picking the absolute best 5 chunks.

I took this approach because it balances speed and accuracy. You can't run a deep neural network on 10,000 chunks (it would take minutes), but running it on 20 chunks takes milliseconds and drastically improves the quality of the data we send to the LLM.

## Step 2: What other approaches did you consider but abandon?
- **Adding the scores directly (`chroma_score + bm25_score`)**: I abandoned this because BM25 scores can be anything (e.g., 14.2) while Chroma scores are between 0 and 1. The BM25 score would completely overpower the Chroma score. We used RRF instead because it only looks at rank positions, ignoring the incompatible score scales.
- **Cross-Encoding the entire database**: I abandoned this because Cross-Encoders are too slow. They must process the query and the document simultaneously, meaning we can't pre-compute the vectors like we do with ChromaDB.
- **Single-store retrieval (Vectors only)**: I abandoned this because vectors are bad at finding exact names, acronyms, or specific ID numbers.

## Step 3: How do the different parts connect?
The `HybridRetriever` acts as the conductor. 
- It asks `ChromaStore` for 20 semantic matches.
- It asks `BM25Store` for 20 keyword matches.
- It calls `reciprocal_rank_fusion` to combine both lists, heavily rewarding chunks that appeared in both, and outputs a single list of unique candidates.
- It passes those candidates to `_rerank`, where the Cross-Encoder scores them out of 10.
- It returns the final Top 5 chunks to the main Engine (Phase 5).

## Step 4: What tools, methods, or frameworks did you use?
- **Reciprocal Rank Fusion (RRF)**: An industry-standard mathematical formula `1 / (60 + rank)`. It's a zero-configuration algorithm that democratically merges lists from completely different search engines.
- **CrossEncoder (`ms-marco-MiniLM-L-6-v2`)**: A neural network from the `sentence-transformers` library. It was specifically trained on the MS MARCO dataset (which contains Bing search queries and passages) to predict how well a passage actually *answers* a query, not just if they share words.

## Step 5: What tradeoffs did you make?
- **Speed vs. Precision**: Adding a Cross-Encoder adds about ~100-200 milliseconds to the search time. We traded a tiny bit of speed for a massive boost in accuracy. In RAG, sending bad chunks to the LLM causes hallucinations, so precision is worth the slight delay.
- **Memory usage**: Loading the Cross-Encoder model takes up an extra ~100MB of RAM.

## Step 6: What mistakes are commonly made when implementing this?
- **Forgetting the BM25 loop in RRF**: If a chunk is ONLY found by BM25, beginners often forget to add it to the final candidate pool. We handled this with the `if chunk_id not in chunk_map` check.
- **Mismatching the `[Query, Text]` pairs**: The Cross-Encoder requires exactly that order. If you flip it to `[Text, Query]`, the model gets confused and returns terrible scores.

## Step 7: What pitfalls should I watch out for?
- **NameErrors on parameters**: Always double-check your function signatures! If you use a variable like `top_n` inside your function but forget to put it in the `def retrieve(...)` arguments, Python will crash.
- **Empty search results**: If the user searches an empty database, Chroma and BM25 return `[]`. If you feed an empty list to the Cross-Encoder, it will throw an error. We added `if not candidates: return []` in `_rerank` to prevent this.

## Step 8: Expert vs Beginner thinking
A beginner assumes that "Semantic Similarity" (Vector Search) is the same thing as "Relevance". It isn't. A chunk that says "AI is very safe" is semantically similar to the query "Is AI dangerous?", but it doesn't answer the question. 
An expert uses Vector Search merely as a net to catch *related* concepts, and relies on a Cross-Encoder to judge true *relevance*.

## Step 9: What lessons can I apply to other projects?
- **The "Coarse-to-Fine" funnel**: This two-stage pipeline architecture is everywhere in tech. E-commerce sites use it (filter millions of shoes by size/color fast $\rightarrow$ run heavy ML to rank the top 50 for your feed). Recommender systems use it. Learn this pattern well!
- **Data Contracts**: Notice how easy it was to merge ChromaDB and BM25 results because we made sure they both returned dictionaries with the exact same keys in Phase 3. Consistent data schemas make complex systems easy to orchestrate.
