import { useState, useRef, useEffect, useCallback, memo } from 'react';
import './index.css';
import adyuLogo from './assets/adyu-logo.png';

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ── Markdown Renderer ─────────────────────────────────────────────────────────
function applyInline(text) {
  // Split on bold (**text**) and inline code (`code`)
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} className="md-code">{part.slice(1, -1)}</code>;
    }
    return part;
  });
}

function renderMarkdown(text) {
  if (!text) return [];
  const lines = text.split('\n');
  const elements = [];
  let listBuffer = [];
  let numberedBuffer = [];

  const flushList = () => {
    if (listBuffer.length > 0) {
      elements.push(
        <ul key={`ul-${elements.length}`} className="md-list">
          {listBuffer.map((item, i) => <li key={i}>{applyInline(item)}</li>)}
        </ul>
      );
      listBuffer = [];
    }
    if (numberedBuffer.length > 0) {
      elements.push(
        <ol key={`ol-${elements.length}`} className="md-list md-ol">
          {numberedBuffer.map((item, i) => <li key={i}>{applyInline(item)}</li>)}
        </ol>
      );
      numberedBuffer = [];
    }
  };

  lines.forEach((line, i) => {
    // Horizontal rule
    if (line.match(/^---+$/) || line.match(/^\*\*\*+$/)) {
      flushList();
      elements.push(<hr key={i} className="md-hr" />);
    } else if (line.match(/^#{1,3}\s/)) {
      flushList();
      const lvl = line.match(/^(#{1,3})/)[1].length;
      const content = line.replace(/^#{1,3}\s/, '');
      const Tag = `h${lvl + 2}`;
      elements.push(<Tag key={i} className={`md-h${lvl}`}>{applyInline(content)}</Tag>);
    } else if (line.match(/^[-*]\s/)) {
      flushList();
      listBuffer.push(line.replace(/^[-*]\s/, ''));
    } else if (line.match(/^\d+\.\s/)) {
      flushList();
      numberedBuffer.push(line.replace(/^\d+\.\s/, ''));
    } else if (line.trim() === '') {
      flushList();
    } else {
      flushList();
      elements.push(<p key={i} className="md-p">{applyInline(line)}</p>);
    }
  });
  flushList();
  return elements;
}

// ── Time formatter ────────────────────────────────────────────────────────────
function formatTime(ts) {
  const d = new Date(ts);
  return d.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
}

// ── Suggestion Chips ───────────────────────────────────────────────────────────
const SUGGESTIONS = [
  { emoji: "🍽️", text: "Bugünkü yemek menüsü nedir?" },
  { emoji: "📅", text: "Akademik takvim bilgisi" },
  { emoji: "💰", text: "Burs başvurusu nasıl yapılır?" },
  { emoji: "✈️", text: "Erasmus programı hakkında bilgi ver" },
  { emoji: "🏛️", text: "Hangi fakülteler var?" },
  { emoji: "📞", text: "Öğrenci işleri iletişim bilgileri" },
  { emoji: "📚", text: "Kütüphane çalışma saatleri" },
  { emoji: "🎓", text: "Mezuniyet işlemleri nasıl yapılır?" },
];

// ── Copy Button ───────────────────────────────────────────────────────────────
function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      console.error('Copy failed');
    }
  }, [text]);

  return (
    <button
      onClick={handleCopy}
      className={`copy-btn ${copied ? 'copied' : ''}`}
      title={copied ? 'Kopyalandı!' : 'Kopyala'}
      aria-label="Kopyala"
    >
      {copied ? (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      ) : (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
        </svg>
      )}
      <span className="copy-label">{copied ? 'Kopyalandı!' : 'Kopyala'}</span>
    </button>
  );
}

// ── Memoized Message Component ───────────────────────────────────────────────
const MessageItem = memo(({ msg }) => (
  <div className={`message-wrapper ${msg.role}`}>
    {msg.role === 'bot' && (
      <div className="bot-avatar">
        <img src={adyuLogo} alt="AÜ" />
      </div>
    )}
    <div className="message-content">
      <div className="message-bubble">
        {msg.content === '' && msg.role === 'bot' ? (
          <div className="typing">
            <span /><span /><span />
          </div>
        ) : (
          renderMarkdown(msg.content)
        )}
      </div>

      {msg.ts && (
        <span className="msg-time">{formatTime(msg.ts)}</span>
      )}

      {msg.sources && msg.sources.length > 0 && (
        <div className="sources">
          <span className="sources-label">📎 Kaynaklar:</span>
          {msg.sources.map((src, i) => {
            let hostname = src;
            try { hostname = new URL(src).hostname; } catch {}
            return (
              <a key={i} href={src} target="_blank" rel="noopener noreferrer" className="source-tag" title={src}>
                {hostname}
              </a>
            );
          })}
        </div>
      )}

      {msg.role === 'bot' && msg.content && (
        <div className="bot-actions">
          <CopyButton text={msg.content} />
        </div>
      )}
    </div>
  </div>
));

// ── Main App ──────────────────────────────────────────────────────────────────
const WELCOME_MSG = {
  id: 1,
  role: 'bot',
  content: 'Merhaba! 👋 Ben **Adıyaman Üniversitesi** yapay zeka asistanıyım.\n\nSize üniversitemizle ilgili her konuda yardımcı olmaktan mutluluk duyarım. Aşağıdaki konulardan birini seçebilir ya da kendi sorunuzu yazabilirsiniz.',
  sources: [],
  ts: Date.now(),
};

function App() {
  const [messages, setMessages] = useState([WELCOME_MSG]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [isOnline, setIsOnline] = useState(true);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // ── Health check ──────────────────────────────────────────────────────────
  useEffect(() => {
    const checkOnline = async () => {
      try {
        const res = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(15000) });
        setIsOnline(res.ok);
      } catch {
        setIsOnline(false);
      }
    };
    checkOnline();
    const interval = setInterval(checkOnline, 30_000);
    return () => clearInterval(interval);
  }, []);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const sendQuestion = useCallback(async (question) => {
    if (!question.trim() || isLoading) return;

    const trimmed = question.trim();
    setInputValue('');
    setShowSuggestions(false);
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', content: trimmed, sources: [], ts: Date.now() }]);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: trimmed }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${response.status}`);
      }

      const contentType = response.headers.get("content-type") || "";

      // JSON response (cache hit or blocked)
      if (contentType.includes("application/json")) {
        const data = await response.json();
        setMessages(prev => [...prev, {
          id: Date.now() + 1,
          role: 'bot',
          content: data.answer,
          sources: data.sources || [],
          ts: Date.now(),
        }]);
        return;
      }

      // Streaming response — add placeholder immediately so typing indicator shows
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      const botId = Date.now() + 1;
      setMessages(prev => [...prev, { id: botId, role: 'bot', content: '', sources: [], ts: Date.now() }]);
      setIsLoading(false); // streaming started; use per-message indicator

      let accumulated = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        accumulated += decoder.decode(value, { stream: true });

        const sentinelIdx = accumulated.indexOf('\n###SOURCES###');
        if (sentinelIdx !== -1) {
          const answerPart  = accumulated.slice(0, sentinelIdx);
          const sourcesPart = accumulated.slice(sentinelIdx + '\n###SOURCES###'.length);
          const sources = sourcesPart.split('|').map(s => s.trim()).filter(Boolean);
          setMessages(prev => prev.map(msg =>
            msg.id === botId ? { ...msg, content: answerPart, sources } : msg
          ));
          while (true) {
            const { done: d2 } = await reader.read();
            if (d2) break;
          }
          break;
        }

        setMessages(prev => prev.map(msg =>
          msg.id === botId ? { ...msg, content: accumulated } : msg
        ));
      }
      return; // early return to skip finally setIsLoading(false) duplication
    } catch (error) {
      console.error('Chat error:', error);
      const msg = error.message || '';
      const isRateLimit = msg.includes('429') || msg.toLowerCase().includes('çok fazla');
      const isTimeout   = msg.includes('timeout') || msg.includes('AbortError');
      const isNetwork   = msg.includes('Failed to fetch') || msg.includes('NetworkError');

      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'bot',
        content: isRateLimit
          ? '⏳ Çok fazla istek gönderdiniz. Lütfen bir dakika bekleyip tekrar deneyin.'
          : isTimeout
            ? '⌛ Sunucu yanıt vermedi (zaman aşımı). Lütfen tekrar deneyin.'
            : isNetwork
              ? '🔌 Sunucuya ulaşılamadı. İnternet bağlantınızı kontrol edip tekrar deneyin.'
              : '⚠️ Beklenmeyen bir hata oluştu. Sayfayı yenileyip tekrar deneyin.',
        sources: [],
        ts: Date.now(),
      }]);
    } finally {
      setIsLoading(false);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isLoading]);

  const handleSend = useCallback(async (e) => {
    e.preventDefault();
    await sendQuestion(inputValue);
  }, [inputValue, sendQuestion]);

  // Shift+Enter = new line; Enter alone = send
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendQuestion(inputValue);
    }
  }, [inputValue, sendQuestion]);

  const handleClearChat = useCallback(() => {
    setMessages([{ ...WELCOME_MSG, id: Date.now(), ts: Date.now() }]);
    setInputValue('');
    setShowSuggestions(true);
    setTimeout(() => inputRef.current?.focus(), 100);
  }, []);

  const charCount   = inputValue.length;
  const charLimit   = 500;
  const charPercent = Math.min((charCount / charLimit) * 100, 100);
  const charWarning = charCount > charLimit * 0.85;

  return (
    <div className="app-container">
      {/* Header */}
      <header className="chat-header">
        <div className="logo-container">
          <img src={adyuLogo} alt="AÜ Logosu" />
        </div>
        <div className="header-title">
          <h1>Adıyaman Üniversitesi Asistanı</h1>
          <p>adiyaman.edu.tr tabanlı anlık bilgi sistemi</p>
        </div>
        <div className="header-actions">
          <div className={`header-badge ${isOnline ? 'online' : 'offline'}`}>
            <span className="status-dot" />
            {isOnline ? 'Çevrimiçi' : 'Uyanıyor…'}
          </div>
          <button
            onClick={handleClearChat}
            className="clear-chat-btn"
            title="Sohbeti Temizle"
            aria-label="Sohbeti Temizle"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 6h18" />
              <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
              <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
            </svg>
          </button>
        </div>
      </header>

      {/* Chat Area */}
      <div className="chat-messages">
        {messages.map((msg) => (
          <MessageItem key={msg.id} msg={msg} />
        ))}

        {/* Global loading indicator (only before streaming placeholder is added) */}
        {isLoading && (
          <div className="message-wrapper bot">
            <div className="bot-avatar">
              <img src={adyuLogo} alt="AÜ" />
            </div>
            <div className="message-content">
              <div className="message-bubble">
                <div className="typing">
                  <span /><span /><span />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Suggestion Chips */}
        {showSuggestions && messages.length === 1 && !isLoading && (
          <div className="suggestions-container">
            {SUGGESTIONS.map((s, i) => (
              <button
                key={i}
                className="suggestion-chip"
                onClick={() => sendQuestion(s.text)}
              >
                <span className="chip-emoji">{s.emoji}</span>
                {s.text}
              </button>
            ))}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="chat-input-container">
        <form onSubmit={handleSend} className="input-wrapper">
          <textarea
            ref={inputRef}
            id="chat-input"
            className="chat-input"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value.slice(0, charLimit))}
            onKeyDown={handleKeyDown}
            placeholder="Üniversite hakkında sorunuzu yazın… (Enter: gönder, Shift+Enter: yeni satır)"
            disabled={isLoading}
            autoComplete="off"
            rows={1}
          />
          {charCount > 0 && (
            <div className={`char-counter ${charWarning ? 'warning' : ''}`}>
              <svg viewBox="0 0 36 36" className="char-ring">
                <circle className="char-ring-bg"   cx="18" cy="18" r="14" />
                <circle
                  className="char-ring-fill"
                  cx="18" cy="18" r="14"
                  strokeDasharray={`${charPercent * 0.88} 88`}
                  strokeDashoffset="22"
                />
              </svg>
            </div>
          )}
          <button
            type="submit"
            id="send-btn"
            className={`send-btn ${isLoading ? 'loading' : ''}`}
            disabled={!inputValue.trim() || isLoading}
            aria-label="Gönder"
          >
            {isLoading ? (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="spin-icon">
                <path d="M21 12a9 9 0 1 1-6.219-8.56" />
              </svg>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            )}
          </button>
        </form>
        <p className="input-hint">
          Adıyaman Üniversitesi hakkında sorular için tasarlanmıştır. <br />
          &copy; Copyright by yusufkur
        </p>
      </div>
    </div>
  );
}

export default App;
