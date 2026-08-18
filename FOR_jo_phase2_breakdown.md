# FOR jo - Phase 2 Breakdown: Parsing & Chunking

## Step 1: What approach did you take, and why?
The goal was to convert raw transcript files into small, semantic chunks for the LLM. 
- I started with parsing because we need structured data (timestamps + text) before we can group anything. 
- For parsing, I used regex because SRT files are highly patterned but slightly messy (e.g., `,` vs `.`).
- For chunking, I took a "segment-aware overlap" approach. I grouped whole segments until hitting a character limit, then carried over the last few segments. I chose this because splitting text mid-sentence destroys the context the LLM needs to understand the meaning.

## Step 2: What other approaches did you consider but abandon? 
- **Fixed Word/Character Overlap**: Instead of overlapping by whole segments, we could have blindly overlapped by exactly 80 characters. I rejected this because it chops sentences in half (e.g., "the problem with AI i..."). The LLM would see broken text and get confused.
- **Library parsers (e.g., `pysrt`)**: I could have used an external library to parse SRT files. I rejected it because it adds a dependency for something that takes 20 lines of regex to do ourselves, and custom regex gives us full control over edge cases (like extracting `[Speaker]: ` labels, which `pysrt` doesn't do out of the box).

## Step 3: How do the different parts connect? 
1. **Raw File (`.srt`)** enters the system.
2. **`TranscriptParser`** splits it by blank lines, uses regex to extract the timestamps, and outputs `TranscriptSegment` objects.
3. **`PodcastChunker`** takes a list of those segments. It packs them into a buffer until the text reaches 500 characters.
4. It flushes the buffer into a `Chunk` (which is what we will save to the Vector DB in Phase 3) and keeps the last ~80 characters of segments to seed the next buffer.

## Step 4: What tools, methods, or frameworks did you use? 
- **Python `re` (Regex)**: For extracting data from strings. It's the standard tool for text extraction.
- **Pydantic (`Chunk`, `TranscriptSegment`)**: For data validation. If I just used raw dictionaries (e.g., `{"speaker": "Lex"}`), a typo in a key name would crash the app. Pydantic ensures our data is exactly what we expect.
- **Generator expressions & Zip**: E.g., `zip(reversed(buffer), reversed(formatted_texts))`. Walking backwards in tandem is much cleaner with `zip` than manually tracking index numbers.

## Step 5: What tradeoffs did you make?
- **Tradeoff**: I prioritized semantic coherence (keeping sentences whole) over strict chunk sizes.
- **Cost**: Our chunks aren't perfectly sized. Some might be 520 characters, some might be 480. 
- **Benefit**: The LLM gets complete thoughts. In RAG, broken context is a leading cause of hallucinations.

## Step 6: What mistakes are commonly made when implementing this?
- **Forgetting to deduplicate speakers**: If a chunk has Lex, Sam, Lex, Sam, beginners often save the speaker list as `["Lex", "Sam", "Lex", "Sam"]`. This bloats the metadata. I used a `set` to deduplicate it.
- **Off-by-one errors in char counting**: When joining texts with `" "`, you add 1 space per segment. If you forget to add that `+ 1` in your length calculation, your chunks will silently grow larger than your limit.

## Step 7: What pitfalls should I watch out for? 
- **The "Unavailable Timestamp" trap**: If you parse a TXT file, you don't have timestamps. If you set them to `0.0`, the system will think the user was speaking at the very beginning of the podcast. Always use a sentinel value like `-1.0` so the UI knows to display "Timestamp Unavailable" instead of "00:00:00".

## Step 8: Expert vs Beginner thinking
A beginner focuses on *getting the data into the database*. 
An expert focuses on *how the LLM will read the data later*. 
Notice how we prepended the speaker's name to the text (`[Lex]: Hello`). Without that, the LLM just sees a wall of text and doesn't know a conversation is happening. Preparing the data specifically for the LLM's eyes is what separates a good RAG pipeline from a bad one.

## Step 9: What lessons can I apply to other projects?
- **Use Regex compiling**: Always use `re.compile` at the class level for patterns you use in loops. It's a free performance boost for any text-processing app.
- **Maintain a single source of truth for logic**: We separated `_format_segment` from the main loop so if we ever change how speakers are formatted, we only change it in one place.
