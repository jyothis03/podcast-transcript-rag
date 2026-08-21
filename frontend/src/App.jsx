import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  Sparkles,
  Shield,
  Cpu,
  BookOpen,
  UploadCloud,
  RotateCcw,
  ArrowUp,
  FileText,
  Radio,
  Layers,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react';

const API_BASE = 'http://127.0.0.1:8000';

export default function App() {
  const [threadId, setThreadId] = useState(() => Math.random().toString(36).substring(2, 10));
  const [messages, setMessages] = useState([]);
  const [inputQuery, setInputQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [systemStatus, setSystemStatus] = useState({
    status: 'online',
    indexed_chunks: 3,
  });
  const [activePodcast, setActivePodcast] = useState('Lex Fridman Podcast #1');
  const [uploadStatus, setUploadStatus] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

  const chatEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // Fetch system status on load
  useEffect(() => {
    fetch(`${API_BASE}/status`)
      .then((res) => res.json())
      .then((data) => {
        if (data && data.indexed_chunks !== undefined) {
          setSystemStatus(data);
        }
      })
      .catch(() => {
        // Fallback default status
      });
  }, []);

  // Auto-scroll on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSendMessage = async (textToSend) => {
    const query = (textToSend || inputQuery).trim();
    if (!query || isLoading) return;

    setInputQuery('');
    const newMessages = [...messages, { role: 'user', content: query }];
    setMessages(newMessages);
    setIsLoading(true);

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

      if (!res.ok) {
        throw new Error(`HTTP Error ${res.status}`);
      }

      const data = await res.json();
      setMessages([...newMessages, { role: 'assistant', content: data.answer || 'No response generated.' }]);
    } catch (err) {
      setMessages([
        ...newMessages,
        {
          role: 'assistant',
          content: `Connection error: Unable to reach backend server at ${API_BASE}. Please ensure FastAPI is running.`,
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

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadStatus({ type: 'loading', msg: 'Indexing transcript into database...' });

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
      setUploadStatus({ type: 'success', msg: `Indexed ${data.chunks_ingested} segments successfully.` });
      setTimeout(() => setUploadStatus(null), 4000);
    } catch (err) {
      setUploadStatus({ type: 'error', msg: 'Failed to upload and index SRT file.' });
      setTimeout(() => setUploadStatus(null), 4000);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Starter Prompts matching the screenshot design
  const starterCards = [
    {
      icon: <Sparkles size={18} color="#00f090" />,
      title: 'AI Alignment & Human Intent',
      desc: 'What is the core challenge with ensuring models understand human intent?',
      query: 'What is the key challenge with AI alignment according to Sam?',
    },
    {
      icon: <Cpu size={18} color="#00f090" />,
      title: 'RLHF & Superintelligence',
      desc: 'Why is reinforcement learning from human feedback not a silver bullet?',
      query: 'What does Sam say about RLHF and why it is not a silver bullet?',
    },
    {
      icon: <Shield size={18} color="#00f090" />,
      title: 'Autonomous Systems & Risk',
      desc: 'What keeps Sam up at night regarding moving too fast with subgoals?',
      query: 'What keeps Sam up at night regarding existential risk and unintended subgoals?',
    },
    {
      icon: <BookOpen size={18} color="#00f090" />,
      title: 'Conversation Synthesis',
      desc: 'Summarize the complete progression of Sam’s viewpoint throughout the episode.',
      query: 'Summarize the complete progression of Sam’s viewpoint from the opening greeting to his final warning.',
    },
  ];

  return (
    <div className="app-wrapper">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="brand-header">
          <div className="brand-logo-wrap">
            <Radio size={20} color="#00f090" />
            <span className="brand-title">TRANSCRIPT RAG</span>
          </div>
          <span className="brand-badge">COPILOT</span>
        </div>

        {/* New Chat Button */}
        <button className="btn-secondary" onClick={handleNewChat} style={{ width: '100%' }}>
          <RotateCcw size={16} />
          <span>New Conversation</span>
        </button>

        {/* Upload SRT Transcript Box */}
        <div className="glass-panel">
          <div className="panel-title">
            <UploadCloud size={15} color="#00f090" />
            <span>Upload Podcast Transcript</span>
          </div>

          <input
            type="file"
            accept=".srt"
            ref={fileInputRef}
            onChange={handleFileUpload}
            style={{ display: 'none' }}
          />

          <div
            className="upload-dropzone"
            onClick={() => fileInputRef.current?.click()}
            style={{ pointerEvents: isUploading ? 'none' : 'auto' }}
          >
            <FileText size={20} color="#00f090" style={{ margin: '0 auto 6px', display: 'block' }} />
            <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#ffffff' }}>
              {isUploading ? 'Indexing File...' : 'Upload Subtitle (.srt)'}
            </div>
            <div style={{ fontSize: '0.72rem', color: '#8fa89e', marginTop: '2px' }}>
              Select or drop an SRT transcript
            </div>
          </div>

          {uploadStatus && (
            <div
              style={{
                marginTop: '10px',
                padding: '8px 10px',
                borderRadius: '8px',
                fontSize: '0.75rem',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                background: uploadStatus.type === 'error' ? 'rgba(255, 70, 70, 0.15)' : 'rgba(0, 240, 144, 0.12)',
                color: uploadStatus.type === 'error' ? '#ff6b6b' : '#00f090',
                border: `1px solid ${uploadStatus.type === 'error' ? 'rgba(255, 70, 70, 0.3)' : 'rgba(0, 240, 144, 0.3)'}`,
              }}
            >
              {uploadStatus.type === 'error' ? <AlertTriangle size={14} /> : <CheckCircle2 size={14} />}
              <span>{uploadStatus.msg}</span>
            </div>
          )}
        </div>

        {/* Active Episode & Knowledge Base Information */}
        <div className="glass-panel">
          <div className="panel-title">
            <Layers size={15} color="#00f090" />
            <span>Active Episode</span>
          </div>
          <div
            style={{
              fontSize: '0.9rem',
              fontWeight: 700,
              color: '#ffffff',
              marginBottom: '6px',
              wordBreak: 'break-word',
            }}
          >
            {activePodcast}
          </div>
          <div style={{ fontSize: '0.78rem', color: '#8fa89e', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span className="status-dot"></span>
            <span>{systemStatus.indexed_chunks} Knowledge Segments Indexed</span>
          </div>
        </div>
      </aside>

      {/* Main Interactive Stage */}
      <main className="main-stage">
        {/* Top App Bar */}
        <header className="top-bar">
          <div className="top-bar-title" title={activePodcast}>
            <span>{activePodcast}</span>
          </div>
          <div className="status-indicator">
            <span className="status-dot"></span>
            <span>Knowledge Base Ready</span>
          </div>
        </header>

        {/* Chat Feed */}
        <div className="chat-scroll-area">
          <div className="chat-inner-wrap">
            {messages.length === 0 ? (
              <div className="welcome-container">
                <div className="welcome-badge">
                  <Sparkles size={13} color="#00f090" />
                  <span>TRANSCRIPT INTELLIGENCE</span>
                </div>
                <h1 className="welcome-title">WHAT DO YOU WANT TO EXPLORE TODAY?</h1>
                <p className="welcome-subtitle">
                  Ask nuanced questions across multi-speaker dialogue, verify technical quotes, or investigate timestamps from the podcast transcript.
                </p>

                <div className="starter-grid">
                  {starterCards.map((card, idx) => (
                    <div
                      key={idx}
                      className="starter-card"
                      onClick={() => handleSendMessage(card.query)}
                    >
                      <div className="starter-card-top">
                        {card.icon}
                        <span>{card.title}</span>
                      </div>
                      <div className="starter-card-desc">{card.desc}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg, index) => (
                <div
                  key={index}
                  className={msg.role === 'user' ? 'msg-user-wrap' : 'msg-assistant-wrap'}
                >
                  {msg.role === 'user' ? (
                    <div className="msg-user">{msg.content}</div>
                  ) : (
                    <div className="msg-assistant">
                      <div className="msg-assistant-header">
                        <Sparkles size={14} color="#00f090" />
                        <span>Transcript Answer</span>
                      </div>
                      <div style={{ lineHeight: 1.65 }}>
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}

            {isLoading && (
              <div className="msg-assistant-wrap">
                <div className="msg-assistant pulsing" style={{ padding: '16px 20px' }}>
                  <div className="msg-assistant-header">
                    <Sparkles size={14} color="#00f090" />
                    <span>Searching Transcripts & Generating Grounded Answer...</span>
                  </div>
                </div>
              </div>
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
              placeholder="What is on your mind?"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSendMessage();
              }}
              disabled={isLoading}
            />
            <button
              className="send-btn"
              onClick={() => handleSendMessage()}
              disabled={!inputQuery.trim() || isLoading}
            >
              <ArrowUp size={20} strokeWidth={2.5} />
            </button>
          </div>
        </footer>
      </main>
    </div>
  );
}
