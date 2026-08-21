import os
import sys
import uuid
import streamlit as st

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.config import get_settings
from app.rag.engine import RAGEngine
from app.rag.graph import PodcastRAGGraph

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION & STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Podcast Transcript Copilot",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Dark Emerald / Mint Glassmorphic CSS (Matching Visual Design Reference)
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap');

:root {
    --bg-main: #060b09;
    --bg-secondary: #0b1410;
    --bg-card: rgba(13, 24, 20, 0.72);
    --border-card: rgba(0, 240, 144, 0.12);
    --border-card-hover: rgba(0, 240, 144, 0.35);
    --primary-mint: #00f090;
    --primary-mint-dark: #00b86c;
    --text-main: #f0f7f4;
    --text-muted: #8fa89e;
    --text-dark: #04120a;
}

html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--bg-main) !important;
    background-image: 
        radial-gradient(circle at 15% 20%, rgba(0, 240, 144, 0.08) 0%, transparent 40%),
        radial-gradient(circle at 85% 80%, rgba(0, 184, 108, 0.06) 0%, transparent 45%) !important;
    color: var(--text-main) !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}

[data-testid="stHeader"] {
    background: transparent !important;
}

[data-testid="stSidebar"] {
    background-color: var(--bg-secondary) !important;
    border-right: 1px solid var(--border-card) !important;
}

/* Custom Scrollbars */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: #060b09;
}
::-webkit-scrollbar-thumb {
    background: rgba(0, 240, 144, 0.2);
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
    background: rgba(0, 240, 144, 0.4);
}

/* Header Typography */
.brand-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.75rem;
    font-weight: 700;
    letter-spacing: -0.02em;
    color: #ffffff;
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 4px;
}
.brand-badge {
    background: rgba(0, 240, 144, 0.15);
    border: 1px solid var(--primary-mint);
    color: var(--primary-mint);
    font-size: 0.7rem;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 12px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}

.welcome-heading {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.5rem;
    font-weight: 800;
    letter-spacing: -0.03em;
    color: #ffffff;
    margin-top: 1.5rem;
    margin-bottom: 0.25rem;
    text-transform: uppercase;
}

.welcome-sub {
    font-size: 1.1rem;
    color: var(--text-muted);
    margin-bottom: 2rem;
    font-weight: 400;
}

/* Starter Topic Cards */
.starter-card-btn {
    background: var(--bg-card) !important;
    border: 1px solid var(--border-card) !important;
    border-radius: 16px !important;
    padding: 18px 20px !important;
    text-align: left !important;
    transition: all 0.25s ease !important;
    backdrop-filter: blur(12px) !important;
    margin-bottom: 12px !important;
    cursor: pointer !important;
}
.starter-card-btn:hover {
    border-color: var(--primary-mint) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(0, 240, 144, 0.12) !important;
}

/* Chat Message Bubbles */
.chat-container {
    display: flex;
    flex-direction: column;
    gap: 16px;
    margin-top: 1.5rem;
    margin-bottom: 5rem;
}

.user-bubble-wrapper {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 8px;
}

.user-bubble {
    background: linear-gradient(135deg, #00f090 0%, #00b86c 100%);
    color: #04120a;
    font-weight: 600;
    font-size: 0.95rem;
    line-height: 1.45;
    padding: 12px 20px;
    border-radius: 20px 20px 4px 20px;
    max-width: 75%;
    box-shadow: 0 4px 16px rgba(0, 240, 144, 0.2);
}

.assistant-bubble-wrapper {
    display: flex;
    justify-content: flex-start;
    margin-bottom: 12px;
}

.assistant-bubble {
    background: rgba(14, 24, 20, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(16px);
    color: #e6f0ec;
    font-size: 0.95rem;
    line-height: 1.6;
    padding: 18px 22px;
    border-radius: 4px 20px 20px 20px;
    max-width: 82%;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
}

.timestamp-pill {
    display: inline-block;
    background: rgba(0, 240, 144, 0.12);
    border: 1px solid rgba(0, 240, 144, 0.3);
    color: var(--primary-mint);
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 600;
    margin: 0 2px;
}

/* Sidebar Styles */
.sidebar-panel {
    background: rgba(13, 24, 20, 0.6);
    border: 1px solid var(--border-card);
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 14px;
}

.sidebar-label {
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 6px;
}

.sidebar-value {
    font-size: 0.95rem;
    font-weight: 600;
    color: #ffffff;
}

/* Status Indicator Dot */
.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: var(--primary-mint);
    box-shadow: 0 0 8px var(--primary-mint);
    margin-right: 6px;
}

/* Input Area Fixes */
[data-testid="stChatInput"] {
    border-radius: 28px !important;
    border: 1px solid var(--border-card) !important;
    background: rgba(13, 24, 20, 0.8) !important;
    backdrop-filter: blur(16px) !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: var(--primary-mint) !important;
    box-shadow: 0 0 16px rgba(0, 240, 144, 0.25) !important;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# SVG ICONS (Zero Emojis - Premium Vector System)
# -----------------------------------------------------------------------------
ICON_SPARKLE = """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00f090" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>"""
ICON_BOOK = """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00f090" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/><path d="M6 6h10"/><path d="M6 10h10"/></svg>"""
ICON_SHIELD = """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00f090" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>"""
ICON_CPU = """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00f090" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/></svg>"""
ICON_SEARCH = """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00f090" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>"""
ICON_UPLOAD = """<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00f090" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>"""
ICON_REFRESH = """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/></svg>"""

# -----------------------------------------------------------------------------
# SESSION INITIALIZATION
# -----------------------------------------------------------------------------
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())[:8]

if "messages" not in st.session_state:
    st.session_state.messages = []

if "active_podcast" not in st.session_state:
    st.session_state.active_podcast = "Lex Fridman Podcast #1"

if "total_chunks" not in st.session_state:
    st.session_state.total_chunks = 0


@st.cache_resource(show_spinner=False)
def load_rag_pipeline():
    """Initializes and caches the RAGEngine and LangGraph workflow with visible progress."""
    progress = st.empty()
    bar = st.progress(0, text="Initializing vector store and embedding models...")

    engine = RAGEngine(persist_dir="./data")
    bar.progress(55, text="Loading Cross-Encoder reranker...")

    graph = PodcastRAGGraph(engine=engine)
    bar.progress(80, text="Compiling LangGraph state machine...")

    # Skip ingestion if collection already has data (avoids re-embedding on restart)
    try:
        collection_info = engine.qdrant_store.client.get_collection(
            engine.qdrant_store.collection_name
        )
        existing_points = collection_info.points_count or 0
    except Exception:
        existing_points = 0

    if existing_points == 0:
        default_srt = "data/sample_podcast.srt"
        if os.path.exists(default_srt):
            bar.progress(90, text="Indexing default transcript into Qdrant...")
            num_chunks = engine.ingest_podcast(
                file_path=default_srt,
                podcast_name="Lex Fridman Podcast",
                episode_id=1,
            )
            st.session_state.total_chunks = num_chunks
    else:
        st.session_state.total_chunks = existing_points

    bar.progress(100, text="Ready.")
    bar.empty()
    progress.empty()

    return engine, graph


rag_engine, rag_graph = load_rag_pipeline()

# -----------------------------------------------------------------------------
# SIDEBAR CONTROLS & TELEMETRY
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;">
            <div class="brand-title">{ICON_SPARKLE} TRANSCRIPT RAG</div>
            <span class="brand-badge">v2.0 CRAG</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Active Session Card
    st.markdown(
        f"""
        <div class="sidebar-panel">
            <div class="sidebar-label">Session ID</div>
            <div class="sidebar-value"><code>{st.session_state.thread_id}</code></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # New Chat Button
    if st.button("New Conversation", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())[:8]
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")

    # Transcript Ingestion Uploader
    st.markdown(
        f"""
        <div class="sidebar-label" style="display: flex; align-items: center; gap: 8px;">
            {ICON_UPLOAD} Ingest SRT Transcript
        </div>
        """,
        unsafe_allow_html=True,
    )

    uploaded_file = st.file_uploader(
        "Upload Subtitle (.srt)",
        type=["srt"],
        label_visibility="collapsed",
    )

    if uploaded_file is not None:
        save_dir = "data/uploads"
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, uploaded_file.name)

        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        podcast_title = uploaded_file.name.replace(".srt", "").replace("_", " ").title()

        with st.spinner("Indexing into Qdrant..."):
            chunks_count = rag_engine.ingest_podcast(
                file_path=save_path,
                podcast_name=podcast_title,
                episode_id=str(uuid.uuid4())[:4],
            )
            st.session_state.active_podcast = podcast_title
            st.session_state.total_chunks = chunks_count
            st.success(f"Indexed {chunks_count} chunks successfully.")

    # Architecture Status Panel
    settings = get_settings()
    st.markdown("---")
    st.markdown(
        f"""
        <div class="sidebar-panel">
            <div class="sidebar-label">Active Episode</div>
            <div class="sidebar-value">{st.session_state.active_podcast}</div>
            <div style="margin-top: 8px;" class="sidebar-label">Indexed Passages</div>
            <div class="sidebar-value">{st.session_state.total_chunks} Chunks</div>
        </div>

        <div class="sidebar-panel">
            <div class="sidebar-label">Pipeline Architecture</div>
            <div style="font-size: 0.85rem; color: #b3c9c0; line-height: 1.5;">
                <div><span class="status-dot"></span><b>Vector DB:</b> Qdrant Dense + BM25</div>
                <div><span class="status-dot"></span><b>Reranker:</b> ms-marco Cross-Encoder</div>
                <div><span class="status-dot"></span><b>Primary LLM:</b> {settings.GEMINI_MODEL_NAME}</div>
                <div><span class="status-dot"></span><b>Failover LLM:</b> {settings.GROQ_MODEL_NAME}</div>
                <div><span class="status-dot"></span><b>Guardrails:</b> Zero-Token Injection Gate</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# -----------------------------------------------------------------------------
# MAIN VIEWPORT: CHAT & STARTER TOPICS
# -----------------------------------------------------------------------------
st.markdown(
    f"""
    <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border-card); margin-bottom: 1.5rem;">
        <div style="font-size: 1.1rem; font-weight: 700; color: #ffffff; letter-spacing: -0.01em;">
            {st.session_state.active_podcast}
        </div>
        <div style="font-size: 0.85rem; color: var(--text-muted);">
            Thread: <code>{st.session_state.thread_id}</code>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Empty State: Display Greeting & Topic Discovery Cards
if not st.session_state.messages:
    st.markdown(
        """
        <div class="welcome-heading">INTELLIGENT TRANSCRIPT COPILOT</div>
        <div class="welcome-sub">What would you like to explore from this podcast conversation today?</div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "AI Alignment & Safety\nWhat is the core challenge with models understanding human intent?",
            key="starter_1",
            use_container_width=True,
        ):
            st.session_state.pending_query = "What is the key challenge with AI alignment according to Sam?"
            st.rerun()

        if st.button(
            "RLHF & Superintelligence\nWhy is reinforcement learning from human feedback not a silver bullet?",
            key="starter_2",
            use_container_width=True,
        ):
            st.session_state.pending_query = "What does Sam say about RLHF and why it is not a silver bullet?"
            st.rerun()

    with col2:
        if st.button(
            "Autonomous Systems & Subgoals\nWhat keeps Sam up at night regarding moving too fast?",
            key="starter_3",
            use_container_width=True,
        ):
            st.session_state.pending_query = "What keeps Sam up at night regarding existential risk and unintended subgoals?"
            st.rerun()

        if st.button(
            "Discussion Summary\nSynthesize the main takeaways between Lex and Sam.",
            key="starter_4",
            use_container_width=True,
        ):
            st.session_state.pending_query = "Summarize the complete progression of Sam's viewpoint in this conversation."
            st.rerun()

# -----------------------------------------------------------------------------
# MESSAGE STREAM RENDERING
# -----------------------------------------------------------------------------
for msg in st.session_state.messages:
    role = msg["role"]
    content = msg["content"]

    if role == "user":
        st.markdown(
            f"""
            <div class="user-bubble-wrapper">
                <div class="user-bubble">{content}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="assistant-bubble-wrapper">
                <div class="assistant-bubble">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 0.78rem; font-weight: 700; color: var(--primary-mint); text-transform: uppercase;">
                        {ICON_SPARKLE} Transcript Answer
                    </div>
                    <div>{content}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# -----------------------------------------------------------------------------
# QUERY PROCESSING & CHAT INPUT
# -----------------------------------------------------------------------------
# Check if a starter card was triggered
active_input = None
if "pending_query" in st.session_state and st.session_state.pending_query:
    active_input = st.session_state.pending_query
    st.session_state.pending_query = None

user_prompt = st.chat_input("Ask anything from the transcript...")

query_to_run = active_input or user_prompt

if query_to_run:
    # 1. Append and render User message
    st.session_state.messages.append({"role": "user", "content": query_to_run})
    st.markdown(
        f"""
        <div class="user-bubble-wrapper">
            <div class="user-bubble">{query_to_run}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 2. Invoke LangGraph Corrective RAG state machine
    with st.spinner("Analyzing transcript & generating citation..."):
        try:
            bot_response = rag_graph.chat(
                query=query_to_run,
                thread_id=st.session_state.thread_id,
                podcast_name=st.session_state.active_podcast if st.session_state.active_podcast != "Lex Fridman Podcast #1" else None,
            )
        except Exception as e:
            bot_response = f"Error processing query: {str(e)}"

    # 3. Append and render Assistant response
    st.session_state.messages.append({"role": "assistant", "content": bot_response})
    st.markdown(
        f"""
        <div class="assistant-bubble-wrapper">
            <div class="assistant-bubble">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 0.78rem; font-weight: 700; color: var(--primary-mint); text-transform: uppercase;">
                    {ICON_SPARKLE} Transcript Answer
                </div>
                <div>{bot_response}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.rerun()
