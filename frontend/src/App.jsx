import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  Sparkles,
  Search,
  ArrowUpRight,
  ChevronRight,
  Copy,
  Check,
  Plus,
  ArrowLeft,
  UploadCloud,
  FileText,
  ArrowUp,
  BookOpen,
  Cpu,
  Shield,
  Layers,
  Radio
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

export default function App() {
  // Navigation State: 'home' (general hub) or 'chat' (active podcast conversation)
  const [viewMode, setViewMode] = useState('home');
  const [activePodcast, setActivePodcast] = useState(null);
  const [threadId, setThreadId] = useState(() => Math.random().toString(36).substring(2, 10));
  const [messages, setMessages] = useState([]);
  const [inputQuery, setInputQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [searchFilter, setSearchFilter] = useState('');
  const [copiedIndex, setCopiedIndex] = useState(null);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

  // Available Indexed Podcasts Library (loaded dynamically from Qdrant)
  const [indexedPodcasts, setIndexedPodcasts] = useState([]);

  // Saved Chat Sessions History (persisted in localStorage)
  const [chatSessions, setChatSessions] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('podcast_rag_sessions') || '[]');
    } catch {
      return [];
    }
  });

  const chatEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // Verified benchmark questions ONLY for the Lex Fridman dataset
  const lexBenchmarkPrompts = [
    {
      icon: <Sparkles size={16} color="#d946ef" />,
      title: 'AI Alignment & Human Intent',
      desc: 'What is the core challenge with ensuring models understand human intent?',
      query: 'What is the key challenge with AI alignment according to Sam?',
    },
    {
      icon: <Cpu size={16} color="#d946ef" />,
      title: 'RLHF & Superintelligence',
      desc: 'Why is RLHF considered a great first step but not a silver bullet?',
      query: 'What does Sam say about RLHF and why it is not a silver bullet?',
    },
    {
      icon: <Shield size={16} color="#d946ef" />,
      title: 'Autonomous Systems & Risk',
      desc: 'What keeps Sam up at night regarding moving too fast with subgoals?',
      query: 'What keeps Sam up at night regarding existential risk and unintended subgoals?',
    },
    {
      icon: <BookOpen size={16} color="#d946ef" />,
      title: 'Full Progression Synthesis',
      desc: 'Synthesize Sam’s viewpoint from opening greeting to his final warning.',
      query: 'Summarize the complete progression of Sam’s viewpoint from the opening greeting to his final warning.',
    },
  ];

  // Fetch indexed podcasts from backend on mount
  const fetchPodcasts = async () => {
    try {
      const res = await fetch(`${API_BASE}/podcasts`);
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          const normalized = data.map((p) => ({
            podcast_name: p.podcast_name || 'Uploaded Episode',
            chunk_count: p.chunk_count || 0,
            description: p.podcast_name?.includes('Lex')
              ? 'Sam Altman on AI alignment, superintelligence, and scalable safety.'
              : 'Indexed subtitle transcript ready for neural hybrid retrieval.',
          }));
          setIndexedPodcasts(normalized);
        }
      }
    } catch {}
  };

  useEffect(() => {
    fetchPodcasts();
  }, []);

  // Persist sessions to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('podcast_rag_sessions', JSON.stringify(chatSessions));
    } catch {}
  }, [chatSessions]);

  // Auto-scroll chat area only when conversation is active
  useEffect(() => {
    if (messages.length > 0) {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [messages, isLoading]);

  // Helper to save current conversation into sessions
  const saveCurrentSessionToHistory = (newMsgs = messages, targetPod = activePodcast) => {
    if (!newMsgs || newMsgs.length === 0 || !targetPod) return;
    const firstUserMsg = newMsgs.find((m) => m.role === 'user')?.content || 'Conversation';
    const title = firstUserMsg.length > 32 ? firstUserMsg.substring(0, 32) + '...' : firstUserMsg;

    setChatSessions((prev) => {
      const filtered = prev.filter((s) => s.id !== threadId);
      const newSession = {
        id: threadId,
        podcastName: targetPod,
        title: title,
        messages: newMsgs,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      return [newSession, ...filtered].slice(0, 20);
    });
  };

  // Open a podcast chat session
  const handleOpenPodcastChat = (podcastName) => {
    if (messages.length > 0) {
      saveCurrentSessionToHistory();
    }
    const newThreadId = Math.random().toString(36).substring(2, 10);
    setThreadId(newThreadId);
    setActivePodcast(podcastName);
    setMessages([]);
    setInputQuery('');
    setViewMode('chat');
  };

  // Return to General Home / Start Page
  const handleGoToHome = () => {
    if (messages.length > 0) {
      saveCurrentSessionToHistory();
    }
    setViewMode('home');
    setMessages([]);
    setInputQuery('');
    setActivePodcast(null);
  };

  // Load a past chat session from history
  const handleSelectHistorySession = (session) => {
    if (messages.length > 0 && session.id !== threadId) {
      saveCurrentSessionToHistory();
    }
    setThreadId(session.id);
    setActivePodcast(session.podcastName || 'Lex Fridman Podcast #1');
    setMessages(session.messages || []);
    setInputQuery('');
    setViewMode('chat');
  };

  const handleSendMessage = async (textToSend) => {
    const query = (textToSend || inputQuery).trim();
    if (!query || isLoading) return;

    // If sending from home page without an active podcast selected, default to first available
    let currentPod = activePodcast;
    if (!currentPod) {
      currentPod = indexedPodcasts[0]?.podcast_name || 'Lex Fridman Podcast #1';
      setActivePodcast(currentPod);
      setViewMode('chat');
    }

    setInputQuery('');
    const updatedMessages = [...messages, { role: 'user', content: query }];
    setMessages(updatedMessages);
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          thread_id: threadId,
          podcast_name: currentPod.includes('Lex') ? null : currentPod,
        }),
      });

      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);

      const data = await res.json();
      const finalMsgs = [
        ...updatedMessages,
        { role: 'assistant', content: data.answer || 'No grounded response found in transcript.' },
      ];
      setMessages(finalMsgs);
      saveCurrentSessionToHistory(finalMsgs, currentPod);
    } catch (err) {
      setMessages([
        ...updatedMessages,
        {
          role: 'assistant',
          content: `Connection error: Unable to reach backend server at ${API_BASE}.`,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearHistory = () => {
    setChatSessions([]);
    try {
      localStorage.removeItem('podcast_rag_sessions');
    } catch {}
  };

  const handleCopyText = (text, index) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  // Upload new SRT file -> creates individual podcast page and opens its new chat immediately
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (messages.length > 0) {
      saveCurrentSessionToHistory();
    }

    setIsUploading(true);
    setUploadStatus({ type: 'loading', msg: `Indexing "${file.name}" into Qdrant...` });

    const formData = new FormData();
    formData.append('file', file);
    const podcastTitle = file.name.replace('.srt', '').replace(/_/g, ' ');
    formData.append('podcast_name', podcastTitle);
    formData.append('episode_id', '1');

    try {
      const res = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) throw new Error('Upload failed');
      const data = await res.json();

      // Refresh indexed list
      await fetchPodcasts();

      // Open new chat session strictly for this new podcast!
      const newThreadId = Math.random().toString(36).substring(2, 10);
      setThreadId(newThreadId);
      setActivePodcast(podcastTitle);
      setMessages([]);
      setInputQuery('');
      setViewMode('chat');
      setUploadStatus({ type: 'success', msg: `Indexed "${podcastTitle}" (${data.chunks_ingested} chunks). New chat started!` });
      setTimeout(() => setUploadStatus(null), 4000);
    } catch (err) {
      setUploadStatus({ type: 'error', msg: 'Failed to upload and index SRT file.' });
      setTimeout(() => setUploadStatus(null), 4000);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const filteredSessions = chatSessions.filter((s) =>
    s.title.toLowerCase().includes(searchFilter.toLowerCase()) ||
    s.podcastName.toLowerCase().includes(searchFilter.toLowerCase())
  );

  return (
    <div className="app-wrapper">
      <div className="aurora-glow-top"></div>
      <div className="aurora-glow-bottom"></div>

      {/* Hidden File Input */}
      <input
        type="file"
        accept=".srt"
        ref={fileInputRef}
        onChange={handleFileUpload}
        style={{ display: 'none' }}
      />

      {/* Left Sidebar */}
      <aside className="sidebar">
        {/* Top Header */}
        <div className="sidebar-header">
          <div className="icon-circle-btn" onClick={handleGoToHome} title="General Home / Library">
            <Plus size={18} />
          </div>
          <button className="btn-pill-premium" onClick={() => fileInputRef.current?.click()} title="Upload new subtitle file">
            <UploadCloud size={14} color="#d946ef" />
            <span>Upload SRT</span>
          </button>
        </div>

        {/* Hero Title */}
        <h1 className="sidebar-hero-title">
          Transcript<br />Copilot
        </h1>

        {/* Search Past Sessions */}
        <div className="sidebar-search-wrap">
          <Search size={16} className="sidebar-search-icon" />
          <input
            type="text"
            className="sidebar-search-input"
            placeholder="Search past chats..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
          />
        </div>

        {/* Real Chat History Section */}
        <div className="section-header">
          <span className="section-title">Chat History</span>
          {chatSessions.length > 0 && (
            <span className="section-link" onClick={handleClearHistory} title="Clear history">
              Clear all
            </span>
          )}
        </div>

        <div className="history-list">
          {filteredSessions.length > 0 ? (
            filteredSessions.map((session, idx) => (
              <div
                key={session.id || idx}
                className={`history-item ${viewMode === 'chat' && session.id === threadId ? 'active-history-item' : ''}`}
                onClick={() => handleSelectHistorySession(session)}
                title={`Podcast: ${session.podcastName}`}
              >
                <div className="history-item-left">
                  <div className="history-icon-badge">
                    <Sparkles size={13} color="#d946ef" />
                  </div>
                  <div className="history-text-wrap">
                    <div className="history-item-title">{session.title}</div>
                    <div className="history-item-sub">
                      {session.podcastName} · {session.timestamp}
                    </div>
                  </div>
                </div>
                <ChevronRight size={15} color="#64748b" />
              </div>
            ))
          ) : (
            <div className="history-empty-state">
              No previous chats saved. Select an episode or upload an SRT to start.
            </div>
          )}
        </div>

        {/* Upload Transcript Dropzone */}
        <div
          className="upload-card-compact"
          onClick={() => fileInputRef.current?.click()}
          title="Click to upload another podcast transcript (.srt)"
        >
          <FileText size={18} color="#d946ef" style={{ margin: '0 auto 4px', display: 'block' }} />
          <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#ffffff' }}>
            {isUploading ? 'Indexing Transcript...' : 'Drop or Add Subtitles'}
          </div>
          <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {activePodcast || 'Upload .srt file'}
          </div>
        </div>

        {uploadStatus && (
          <div
            style={{
              padding: '8px 12px',
              borderRadius: '12px',
              fontSize: '0.75rem',
              background: uploadStatus.type === 'error' ? 'rgba(244, 63, 94, 0.15)' : 'rgba(217, 70, 239, 0.15)',
              color: uploadStatus.type === 'error' ? '#f43f5e' : '#d946ef',
              border: `1px solid ${uploadStatus.type === 'error' ? 'rgba(244, 63, 94, 0.3)' : 'rgba(217, 70, 239, 0.3)'}`,
              textAlign: 'center',
            }}
          >
            {uploadStatus.msg}
          </div>
        )}
      </aside>

      {/* Main Content Stage */}
      <main className="main-stage">
        {/* Top App Bar */}
        <header className="top-bar">
          <div className="top-bar-center">
            {viewMode === 'chat' && (
              <div className="icon-circle-btn" onClick={handleGoToHome} title="Back to All Podcasts">
                <ArrowLeft size={18} />
              </div>
            )}
            <div className="sparkle-icon-wrap">
              <Sparkles size={18} color="#ffffff" />
            </div>
            <div className="top-bar-titles">
              <span className="top-bar-main-title">
                {viewMode === 'home' ? 'Podcast Library & Hub' : activePodcast}
              </span>
              <span className="top-bar-sub-title">
                {viewMode === 'home'
                  ? `${indexedPodcasts.length} podcast(s) indexed in Qdrant`
                  : `Session ID: ${threadId}`}
              </span>
            </div>
          </div>

          <div className="top-bar-actions">
            {viewMode === 'chat' ? (
              <button
                className="btn-pill-premium"
                style={{ fontSize: '0.76rem', padding: '6px 14px' }}
                onClick={handleGoToHome}
              >
                All Podcasts
              </button>
            ) : (
              <button
                className="btn-pill-premium"
                style={{ fontSize: '0.76rem', padding: '6px 14px' }}
                onClick={() => fileInputRef.current?.click()}
              >
                + New Upload
              </button>
            )}
          </div>
        </header>

        {/* Scroll Content Area */}
        <div className="chat-scroll-area">
          <div className="chat-inner-wrap">
            {/* VIEW 1: GENERAL HOME / ALL PODCASTS HUB */}
            {viewMode === 'home' ? (
              <div className="welcome-center-container">
                <div className="welcome-sparkle-orb">
                  <Sparkles size={30} color="#ffffff" />
                </div>
                <h2 className="welcome-title">Podcast Transcript Hub</h2>
                <p className="welcome-subtitle">
                  Select an individual podcast below to open its dedicated chat session, or upload a new subtitle file.
                </p>

                {/* Available Podcasts Library Grid or Empty Upload State */}
                {indexedPodcasts.length > 0 ? (
                  <div style={{ width: '100%', maxWidth: '780px', marginTop: '10px' }}>
                    <div style={{ fontSize: '0.86rem', fontWeight: 700, color: '#94a3b8', marginBottom: '12px', textAlign: 'left' }}>
                      Available Transcripts ({indexedPodcasts.length})
                    </div>
                    <div className="starter-prompts-grid">
                      {indexedPodcasts.map((pod, idx) => (
                        <div
                          key={idx}
                          className="starter-prompt-card"
                          onClick={() => handleOpenPodcastChat(pod.podcast_name)}
                        >
                          <div className="starter-prompt-card-top">
                            <span>{pod.podcast_name}</span>
                            <ArrowUpRight size={16} color="#d946ef" />
                          </div>
                          <div className="starter-prompt-card-desc">
                            {pod.description}
                          </div>
                          <div style={{ fontSize: '0.72rem', color: '#d946ef', fontWeight: 600, marginTop: '4px' }}>
                            {pod.chunk_count} chunks indexed
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div
                    style={{
                      marginTop: '20px',
                      padding: '36px 28px',
                      background: 'rgba(20, 20, 30, 0.7)',
                      border: '2px dashed rgba(217, 70, 239, 0.35)',
                      borderRadius: '24px',
                      maxWidth: '520px',
                      width: '100%',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      textAlign: 'center',
                    }}
                    onClick={() => fileInputRef.current?.click()}
                    title="Click to select an SRT file"
                  >
                    <UploadCloud size={40} color="#d946ef" style={{ margin: '0 auto 12px', display: 'block' }} />
                    <div style={{ fontSize: '1.05rem', fontWeight: 700, color: '#ffffff', marginBottom: '6px' }}>
                      {isUploading ? 'Indexing Transcript into Qdrant...' : 'Upload an SRT Transcript'}
                    </div>
                    <div style={{ fontSize: '0.82rem', color: '#94a3b8', lineHeight: 1.5 }}>
                      Click here to select and index a subtitle file from your computer. Once ingested, it will appear in your library and open a dedicated chat session.
                    </div>
                  </div>
                )}
              </div>
            ) : (
              /* VIEW 2: INDIVIDUAL PODCAST CHAT VIEW */
              <>
                {messages.length === 0 ? (
                  <div className="welcome-center-container">
                    <div className="welcome-sparkle-orb">
                      <Sparkles size={30} color="#ffffff" />
                    </div>
                    <h2 className="welcome-title">{activePodcast}</h2>
                    <p className="welcome-subtitle">
                      Ask questions across speakers, verify quotes with exact timestamps, or analyze key arguments from <code>{activePodcast}</code>.
                    </p>

                    {/* ONLY display recommended starter questions if it's the verified Lex Fridman podcast */}
                    {activePodcast?.includes('Lex') ? (
                      <div className="starter-prompts-grid">
                        {lexBenchmarkPrompts.map((prompt, idx) => (
                          <div
                            key={idx}
                            className="starter-prompt-card"
                            onClick={() => handleSendMessage(prompt.query)}
                          >
                            <div className="starter-prompt-card-top">
                              <span>{prompt.title}</span>
                              {prompt.icon}
                            </div>
                            <div className="starter-prompt-card-desc">{prompt.desc}</div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      /* For any other uploaded podcast: NO fake questions! Just a clean ready indicator */
                      <div
                        style={{
                          padding: '24px',
                          background: 'rgba(20, 20, 30, 0.75)',
                          border: '1px solid var(--border-card)',
                          borderRadius: '20px',
                          maxWidth: '560px',
                          margin: '0 auto',
                          textAlign: 'center',
                          backdropFilter: 'blur(16px)',
                        }}
                      >
                        <div style={{ fontSize: '0.92rem', fontWeight: 700, color: '#ffffff', marginBottom: '4px' }}>
                          Transcript Indexed & Isolated
                        </div>
                        <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                          The retrieval engine is locked to this transcript. Type your question below to begin.
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  messages.map((msg, index) => (
                    <div key={index}>
                      {msg.role === 'user' ? (
                        <div className="msg-user-wrap">
                          <div className="msg-user">{msg.content}</div>
                          <div className="avatar-circle">
                            <span style={{ fontSize: '0.72rem', fontWeight: 700, color: '#ffffff' }}>YOU</span>
                          </div>
                        </div>
                      ) : (
                        <div className="msg-assistant-wrap">
                          <div className="sparkle-icon-wrap" style={{ width: '32px', height: '32px', flexShrink: 0 }}>
                            <Sparkles size={16} color="#ffffff" />
                          </div>
                          <div className="msg-assistant">
                            <ReactMarkdown>{msg.content}</ReactMarkdown>

                            {/* Action Bar */}
                            <div className="msg-actions-bar">
                              <button
                                className="msg-action-btn"
                                onClick={() => handleCopyText(msg.content, index)}
                                title="Copy answer"
                              >
                                {copiedIndex === index ? (
                                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#d946ef', fontSize: '0.75rem' }}>
                                    <Check size={14} /> Copied
                                  </span>
                                ) : (
                                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem' }}>
                                    <Copy size={14} /> Copy
                                  </span>
                                )}
                              </button>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  ))
                )}

                {isLoading && (
                  <div className="msg-assistant-wrap">
                    <div className="sparkle-icon-wrap" style={{ width: '32px', height: '32px', flexShrink: 0 }}>
                      <Sparkles size={16} color="#ffffff" />
                    </div>
                    <div className="msg-assistant" style={{ padding: '16px 22px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div className="pulsing-dots">
                          <span className="dot"></span>
                          <span className="dot"></span>
                          <span className="dot"></span>
                        </div>
                        <span style={{ fontSize: '0.86rem', color: '#94a3b8' }}>
                          Searching {activePodcast} & synthesizing grounded answer...
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}

            <div ref={chatEndRef} />
          </div>
        </div>

        {/* Floating Bottom Input Bar */}
        <footer className="bottom-bar">
          <div className="input-container">
            <input
              type="text"
              className="chat-input"
              placeholder={
                viewMode === 'chat'
                  ? `Ask anything about ${activePodcast}...`
                  : `Ask a question or select an indexed podcast above...`
              }
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSendMessage();
              }}
              disabled={isLoading}
            />

            <div className="input-actions">
              <div
                className="action-icon-btn"
                onClick={() => fileInputRef.current?.click()}
                title="Upload new SRT transcript"
              >
                <Plus size={18} />
              </div>
              <button
                className="send-gradient-btn"
                onClick={() => handleSendMessage()}
                disabled={!inputQuery.trim() || isLoading}
                title="Send query"
              >
                <ArrowUp size={20} strokeWidth={2.5} />
              </button>
            </div>
          </div>
        </footer>
      </main>
    </div>
  );
}
