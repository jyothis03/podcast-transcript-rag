import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  Sparkles,
  Search,
  ArrowUpRight,
  ChevronRight,
  Copy,
  Check,
  RotateCcw,
  Volume2,
  ThumbsUp,
  Plus,
  Mic,
  MoreVertical,
  Menu,
  ArrowLeft,
  UploadCloud,
  FileText,
  Radio,
  ArrowUp,
  X,
  Layers,
  Cpu,
  Shield,
  BookOpen
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

export default function App() {
  const [threadId, setThreadId] = useState(() => Math.random().toString(36).substring(2, 10));
  const [messages, setMessages] = useState([]);
  const [inputQuery, setInputQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [searchFilter, setSearchFilter] = useState('');
  const [copiedIndex, setCopiedIndex] = useState(null);
  const [showVoiceOrb, setShowVoiceOrb] = useState(false);
  const [queryHistory, setQueryHistory] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('podcast_rag_history') || '[]');
    } catch {
      return [];
    }
  });
  const [systemStatus, setSystemStatus] = useState({
    status: 'online',
    indexed_chunks: 138,
  });
  const [activePodcast, setActivePodcast] = useState('Lex Fridman Podcast #1');
  const [uploadStatus, setUploadStatus] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

  const chatEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const sidebarRef = useRef(null);

  // Starter Suggested Topics shown in the main view
  const starterPrompts = [
    {
      icon: <Sparkles size={18} color="#d946ef" />,
      title: 'AI Alignment & Intent',
      desc: 'What is the core challenge with ensuring models follow human intent?',
      query: 'What is the key challenge with AI alignment according to Sam?',
    },
    {
      icon: <Cpu size={18} color="#d946ef" />,
      title: 'RLHF & Superintelligence',
      desc: 'Why is RLHF considered a great first step but not a silver bullet?',
      query: 'What does Sam say about RLHF and why it is not a silver bullet?',
    },
    {
      icon: <Shield size={18} color="#d946ef" />,
      title: 'Autonomous Risk & Subgoals',
      desc: 'What keeps Sam up at night regarding moving too fast with subgoals?',
      query: 'What keeps Sam up at night regarding existential risk and unintended subgoals?',
    },
    {
      icon: <BookOpen size={18} color="#d946ef" />,
      title: 'Full Progression Summary',
      desc: 'Synthesize Sam’s viewpoint from opening greeting to his final warning.',
      query: 'Summarize the complete progression of Sam’s viewpoint from the opening greeting to his final warning.',
    },
  ];

  // Save history to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('podcast_rag_history', JSON.stringify(queryHistory));
    } catch {}
  }, [queryHistory]);

  // Fetch status on load
  useEffect(() => {
    fetch(`${API_BASE}/status`)
      .then((res) => res.json())
      .then((data) => {
        if (data && data.indexed_chunks !== undefined) {
          setSystemStatus(data);
        }
      })
      .catch(() => {});
  }, []);

  // Auto-scroll chat area only when conversation is active
  useEffect(() => {
    if (messages.length > 0) {
      chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [messages, isLoading]);

  const handleSendMessage = async (textToSend) => {
    const query = (textToSend || inputQuery).trim();
    if (!query || isLoading) return;

    setInputQuery('');
    const newMessages = [...messages, { role: 'user', content: query }];
    setMessages(newMessages);
    setIsLoading(true);

    // Save actual user query to History
    setQueryHistory((prev) => {
      const exists = prev.some((h) => h.query.toLowerCase() === query.toLowerCase());
      if (exists) return prev;
      const newEntry = {
        title: query.length > 32 ? query.substring(0, 32) + '...' : query,
        sub: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        query: query,
      };
      return [newEntry, ...prev].slice(0, 15);
    });

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query,
          thread_id: threadId,
          podcast_name: activePodcast.includes('Lex') ? null : activePodcast,
        }),
      });

      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);

      const data = await res.json();
      setMessages([
        ...newMessages,
        { role: 'assistant', content: data.answer || 'No response generated from transcript.' },
      ]);
    } catch (err) {
      setMessages([
        ...newMessages,
        {
          role: 'assistant',
          content: `Connection error: Unable to communicate with backend server at ${API_BASE}.`,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewChat = () => {
    setThreadId(Math.random().toString(36).substring(2, 10));
    setMessages([]);
    setInputQuery('');
  };

  const handleClearHistory = () => {
    setQueryHistory([]);
    try {
      localStorage.removeItem('podcast_rag_history');
    } catch {}
  };

  const handleCopyText = (text, index) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadStatus({ type: 'loading', msg: 'Indexing transcript into Qdrant...' });

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

      setActivePodcast(podcastTitle);
      setSystemStatus((prev) => ({ ...prev, indexed_chunks: data.chunks_ingested }));
      setUploadStatus({ type: 'success', msg: `Indexed ${data.chunks_ingested} chunks.` });
      setTimeout(() => setUploadStatus(null), 4000);
    } catch (err) {
      setUploadStatus({ type: 'error', msg: 'Failed to upload SRT file.' });
      setTimeout(() => setUploadStatus(null), 4000);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const filteredHistory = queryHistory.filter((item) =>
    item.title.toLowerCase().includes(searchFilter.toLowerCase())
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

      {/* Left Sidebar (Explore / History Drawer) */}
      <aside className="sidebar" ref={sidebarRef}>
        {/* Top Header */}
        <div className="sidebar-header">
          <div className="icon-circle-btn" onClick={handleNewChat} title="New Chat">
            <Menu size={18} />
          </div>
          <button className="btn-pill-premium" onClick={() => fileInputRef.current?.click()}>
            <UploadCloud size={14} color="#d946ef" />
            <span>Upload SRT</span>
          </button>
        </div>

        {/* Hero Title */}
        <h1 className="sidebar-hero-title">
          Create, explore,<br />be inspired
        </h1>

        {/* Search Bar */}
        <div className="sidebar-search-wrap">
          <Search size={16} className="sidebar-search-icon" />
          <input
            type="text"
            className="sidebar-search-input"
            placeholder="Search past queries..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
          />
        </div>

        {/* Horizontal Mode Cards */}
        <div className="modes-slider">
          <div
            className="mode-card"
            onClick={() => handleSendMessage('What is the core challenge with AI alignment according to Sam?')}
          >
            <div className="mode-card-title">AI transcript<br />copilot</div>
            <ArrowUpRight size={18} className="mode-card-arrow" />
          </div>
          <div
            className="mode-card"
            onClick={() => handleSendMessage('Summarize the key takeaways and warnings from this podcast episode.')}
          >
            <div className="mode-card-title">Key takeaway<br />summary</div>
            <ArrowUpRight size={18} className="mode-card-arrow" />
          </div>
          <div
            className="mode-card"
            onClick={() => handleSendMessage('Verify technical quotes regarding RLHF and automated alignment with timestamps.')}
          >
            <div className="mode-card-title">Timestamp<br />verifier</div>
            <ArrowUpRight size={18} className="mode-card-arrow" />
          </div>
        </div>

        {/* Real User History Section */}
        <div className="section-header">
          <span className="section-title">History</span>
          {queryHistory.length > 0 && (
            <span className="section-link" onClick={handleClearHistory}>
              Clear all
            </span>
          )}
        </div>

        <div className="history-list">
          {filteredHistory.length > 0 ? (
            filteredHistory.map((item, idx) => (
              <div
                key={idx}
                className="history-item"
                onClick={() => handleSendMessage(item.query)}
              >
                <div className="history-item-left">
                  <div className="history-icon-badge">
                    <Sparkles size={13} color="#d946ef" />
                  </div>
                  <div className="history-text-wrap">
                    <div className="history-item-title">{item.title}</div>
                    <div className="history-item-sub">{item.sub}</div>
                  </div>
                </div>
                <ChevronRight size={15} color="#64748b" />
              </div>
            ))
          ) : (
            <div className="history-empty-state">
              No recent conversations yet. Ask a question to build history.
            </div>
          )}
        </div>

        {/* Upload Transcript Dropzone */}
        <div
          className="upload-card-compact"
          onClick={() => fileInputRef.current?.click()}
        >
          <FileText size={18} color="#d946ef" style={{ margin: '0 auto 4px', display: 'block' }} />
          <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#ffffff' }}>
            {isUploading ? 'Indexing Transcript...' : 'Drop or Add Subtitles'}
          </div>
          <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '2px' }}>
            {activePodcast} ({systemStatus.indexed_chunks} chunks)
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

      {/* Middle & Right Screen Main Container */}
      <main className="main-stage">
        {/* Top App Bar (Matching Middle Screen Header) */}
        <header className="top-bar">
          <div className="top-bar-center">
            <div className="icon-circle-btn" onClick={handleNewChat} title="Reset Conversation">
              <ArrowLeft size={18} />
            </div>
            <div className="sparkle-icon-wrap">
              <Sparkles size={18} color="#ffffff" />
            </div>
            <div className="top-bar-titles">
              <span className="top-bar-main-title">Transcript Copilot</span>
              <span className="top-bar-sub-title">{activePodcast}</span>
            </div>
          </div>

          <div className="top-bar-actions">
            <div
              className="action-icon-btn"
              onClick={() => setShowVoiceOrb(!showVoiceOrb)}
              title="Toggle Ambient Audio Orb"
              style={{
                background: showVoiceOrb ? 'rgba(217, 70, 239, 0.25)' : undefined,
                borderColor: showVoiceOrb ? '#d946ef' : undefined,
              }}
            >
              <Mic size={18} color={showVoiceOrb ? '#d946ef' : '#94a3b8'} />
            </div>
            <div className="action-icon-btn" onClick={handleNewChat} title="Options">
              <MoreVertical size={18} />
            </div>
          </div>
        </header>

        {/* Ambient Wave Orb Overlay (Matching Right Screen) */}
        {showVoiceOrb && (
          <div className="ambient-orb-wrapper">
            <div className="pulsing-wave-orb"></div>
            <div style={{ fontFamily: 'Space Grotesk', fontSize: '1.25rem', fontWeight: 700, color: '#fff', marginBottom: '6px' }}>
              Voice & Audio Transcript Mode
            </div>
            <div style={{ fontSize: '0.88rem', color: '#94a3b8', maxWidth: '420px', marginBottom: '18px' }}>
              Type or select a topic to query the grounded transcript with neural hybrid retrieval.
            </div>
            <div style={{ display: 'flex', gap: '12px' }}>
              <div className="action-icon-btn" onClick={handleNewChat} title="Reload">
                <RotateCcw size={18} />
              </div>
              <div className="send-gradient-btn" style={{ width: '56px', height: '56px' }}>
                <Mic size={24} />
              </div>
              <div className="action-icon-btn" onClick={() => setShowVoiceOrb(false)} title="Close">
                <X size={18} />
              </div>
            </div>
          </div>
        )}

        {/* Chat Feed */}
        <div className="chat-scroll-area">
          <div className="chat-inner-wrap">
            {messages.length === 0 ? (
              <div className="welcome-center-container">
                <div className="welcome-sparkle-orb">
                  <Sparkles size={32} color="#ffffff" />
                </div>
                <h2 className="welcome-title">Transcript Intelligence</h2>
                <p className="welcome-subtitle">
                  Ask questions across speakers, extract key concepts, or verify quotes with exact timestamps from <code>{activePodcast}</code>.
                </p>

                {/* Starter Prompts Grid */}
                <div className="starter-prompts-grid">
                  {starterPrompts.map((prompt, idx) => (
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
              </div>
            ) : (
              messages.map((msg, index) => (
                <div key={index}>
                  {msg.role === 'user' ? (
                    <div className="msg-user-wrap">
                      <div className="msg-user">{msg.content}</div>
                      <div className="avatar-circle">
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#ffffff' }}>YOU</span>
                      </div>
                    </div>
                  ) : (
                    <div className="msg-assistant-wrap">
                      <div className="sparkle-icon-wrap" style={{ width: '32px', height: '32px', flexShrink: 0 }}>
                        <Sparkles size={16} color="#ffffff" />
                      </div>
                      <div className="msg-assistant">
                        <ReactMarkdown>{msg.content}</ReactMarkdown>

                        {/* Action Bar (Copy, ThumbsUp, Speaker, Retry) */}
                        <div className="msg-actions-bar">
                          <button
                            className="msg-action-btn"
                            onClick={() => handleCopyText(msg.content, index)}
                            title="Copy answer"
                          >
                            {copiedIndex === index ? <Check size={16} color="#d946ef" /> : <Copy size={16} />}
                          </button>
                          <button className="msg-action-btn" title="Helpful">
                            <ThumbsUp size={16} />
                          </button>
                          <button className="msg-action-btn" title="Read aloud">
                            <Volume2 size={16} />
                          </button>
                          <button
                            className="msg-action-btn"
                            style={{ marginLeft: 'auto' }}
                            onClick={() => handleSendMessage(messages[index - 1]?.content || '')}
                            title="Regenerate"
                          >
                            <RotateCcw size={16} />
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
                <div className="msg-assistant" style={{ padding: '18px 24px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div className="pulsing-dots">
                      <span className="dot"></span>
                      <span className="dot"></span>
                      <span className="dot"></span>
                    </div>
                    <span style={{ fontSize: '0.88rem', color: '#94a3b8' }}>
                      Retrieving transcript segments & generating answer...
                    </span>
                  </div>
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>
        </div>

        {/* Floating Bottom Input Bar (Matching Middle Screen Input Bar) */}
        <footer className="bottom-bar">
          <div className="input-container">
            <input
              type="text"
              className="chat-input"
              placeholder="Send message..."
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
                onClick={() => setShowVoiceOrb(!showVoiceOrb)}
                title="Voice / Ambient Mode"
              >
                <Mic size={18} />
              </div>
              <div
                className="action-icon-btn"
                onClick={() => fileInputRef.current?.click()}
                title="Upload Transcript"
              >
                <Plus size={20} />
              </div>
              <button
                className="send-gradient-btn"
                onClick={() => handleSendMessage()}
                disabled={!inputQuery.trim() || isLoading}
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
