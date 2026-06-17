import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getConversation, streamQuestion, listDocuments, createConversation, getMessageDebug } from '../api';
import Citation from './Citation';

const BugIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    className="w-4 h-4"
  >
    <path d="m8 2 1.88 1.88" />
    <path d="M14.12 3.88 16 2" />
    <path d="M9 7.13v-1a3.003 3.003 0 1 1 6 0v1" />
    <path d="M12 20c-3.3 0-6-2.7-6-6v-3a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v3c0 3.3-2.7 6-6 6" />
    <path d="M12 20v-9" />
    <path d="M6.53 9C4.6 8.8 3 7.1 3 5" />
    <path d="M6 13H2" />
    <path d="M3 21c0-2.1 1.7-3.9 3.8-4" />
    <path d="M20.97 5c0 2.1-1.6 3.8-3.5 4" />
    <path d="M22 13h-4" />
    <path d="M17.2 17c2.1.1 3.8 1.9 3.8 4" />
  </svg>
);

export default function Chat({ conversationId, onConversationsChange }) {
  const navigate = useNavigate();
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [hasDocs, setHasDocs] = useState(true);
  const [streaming, setStreaming] = useState(false);
  const [partialAnswer, setPartialAnswer] = useState('');
  const [partialSources, setPartialSources] = useState([]);
  const [debugData, setDebugData] = useState(null);
  const [debugLoading, setDebugLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    listDocuments().then(({ data }) => setHasDocs(data.documents.length > 0));
  }, []);

  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      return;
    }
    getConversation(conversationId).then(({ data }) => setMessages(data.messages));
  }, [conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, partialAnswer]);

  const handleAsk = async () => {
    if (!question.trim()) return;

    let convId = conversationId;
    if (!convId) {
      const { data } = await createConversation(question.slice(0, 40));
      convId = data.id;
      navigate(`/chat/${convId}`);
      onConversationsChange();
    }

    const currentQuestion = question;
    const provider = localStorage.getItem('llm_provider') || 'groq';
    const model = localStorage.getItem('llm_model') || undefined;
    const apiKey = localStorage.getItem('llm_api_key') || undefined;
    const systemPrompt = localStorage.getItem('rag_system_prompt') || undefined;
    const maxTokens = localStorage.getItem('rag_max_tokens')
      ? parseInt(localStorage.getItem('rag_max_tokens'), 10)
      : undefined;
    const historyLimit = localStorage.getItem('rag_history_limit')
      ? parseInt(localStorage.getItem('rag_history_limit'), 10)
      : undefined;

    setQuestion('');
    setLoading(true);
    setStreaming(true);
    setError(null);
    setPartialAnswer('');
    setPartialSources([]);

    await streamQuestion(convId, currentQuestion, {
      provider,
      model,
      apiKey,
      systemPrompt,
      maxTokens,
      historyLimit,
      onToken: (token) => setPartialAnswer((prev) => prev + token),
      onSources: (sources) => setPartialSources(sources),
      onDone: () => {
        setStreaming(false);
        setLoading(false);
        setPartialAnswer('');
        setPartialSources([]);
        getConversation(convId).then(({ data }) => setMessages(data.messages));
        onConversationsChange();
      },
      onError: (err) => {
        setStreaming(false);
        setLoading(false);
        setError(err.message || 'Something went wrong. The LLM service may be temporarily unavailable.');
      },
    });
  };

  const handleRetry = () => {
    if (!conversationId) return;
    const lastUserMessage = [...messages].reverse().find((m) => m.role === 'user');
    if (lastUserMessage) {
      setQuestion(lastUserMessage.content);
    }
  };

  const handleDebug = async (messageId) => {
    if (!conversationId) return;
    setDebugLoading(true);
    setDebugData(null);
    try {
      const { data } = await getMessageDebug(conversationId, messageId);
      setDebugData(data);
    } catch (err) {
      setDebugData({ error: err.response?.data?.detail || 'Failed to load debug context' });
    } finally {
      setDebugLoading(false);
    }
  };

  if (!hasDocs) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center p-8">
        <h2 className="text-xl font-semibold text-slate-700">No documents uploaded yet</h2>
        <p className="mt-2 text-slate-500">Upload PDFs first to start asking questions.</p>
        <button
          onClick={() => navigate('/')}
          className="mt-6 px-5 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
        >
          Upload Documents
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto">
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-3xl rounded-2xl px-5 py-3 relative ${
                msg.role === 'user'
                  ? 'bg-indigo-600 text-white rounded-br-none'
                  : 'bg-white border border-slate-200 text-slate-800 rounded-bl-none shadow-sm'
              }`}
            >
              {msg.role === 'assistant' && msg.has_debug_context && (
                <button
                  onClick={() => handleDebug(msg.id)}
                  title="Show LLM debug context"
                  className="absolute top-2 right-2 p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-md transition"
                >
                  <BugIcon />
                </button>
              )}
              <p className="whitespace-pre-wrap pr-6">{msg.content}</p>
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-4 space-y-2">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Sources</p>
                  {msg.sources.map((s, i) => (
                    <Citation key={i} source={s} />
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {streaming && (
          <div className="flex justify-start">
            <div className="max-w-3xl bg-white border border-slate-200 rounded-2xl rounded-bl-none px-5 py-3 shadow-sm">
              <p className="whitespace-pre-wrap">{partialAnswer}</p>
              {partialSources.length > 0 && (
                <div className="mt-4 space-y-2">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Sources</p>
                  {partialSources.map((s, i) => (
                    <Citation key={i} source={s} />
                  ))}
                </div>
              )}
              <span className="inline-block mt-2 w-2 h-4 bg-indigo-500 animate-pulse" />
            </div>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-700 text-sm">{error}</p>
            <button
              onClick={handleRetry}
              className="mt-2 text-sm font-medium text-red-700 hover:text-red-900 underline"
            >
              Retry
            </button>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="p-4 border-t border-slate-200 bg-white">
        <div className="flex gap-3 max-w-4xl mx-auto">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !loading && handleAsk()}
            disabled={loading}
            placeholder="Ask a question about your documents..."
            className="flex-1 border border-slate-300 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-slate-100"
          />
          <button
            onClick={handleAsk}
            disabled={loading || !question.trim()}
            className="px-6 py-3 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Ask
          </button>
        </div>
      </div>

      {debugData && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setDebugData(null)}
        >
          <div
            className="bg-white rounded-xl shadow-xl w-full max-w-3xl max-h-[85vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200">
              <h3 className="text-lg font-semibold text-slate-800">LLM Debug Context</h3>
              <button
                onClick={() => setDebugData(null)}
                className="text-slate-500 hover:text-slate-800 text-2xl leading-none"
              >
                &times;
              </button>
            </div>
            <div className="overflow-y-auto p-5 space-y-4 text-sm">
              {debugData.error ? (
                <p className="text-red-600">{debugData.error}</p>
              ) : (
                <>
                  <DebugSection title="System Prompt" content={debugData.system_prompt} />
                  <DebugSection title="Question" content={debugData.question} />
                  <DebugSection title="History" content={debugData.history} />
                  <DebugSection title="Context" content={debugData.context} />
                  <DebugSection title="Raw LLM Input" content={debugData.raw_input} />
                  <DebugSection title="Raw LLM Response" content={debugData.raw_response} />
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DebugSection({ title, content }) {
  const isMissing = content === undefined;
  return (
    <div>
      <h4 className="font-semibold text-slate-700 mb-1">{title}</h4>
      <pre className="bg-slate-50 border border-slate-200 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap text-slate-800 font-mono">
        {isMissing
          ? '(not captured — available for messages created after this feature was added; ask a new question)'
          : content || '(empty)'}
      </pre>
    </div>
  );
}
