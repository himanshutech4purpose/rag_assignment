import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getConversation, streamQuestion, listDocuments, createConversation } from '../api';
import Citation from './Citation';

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
              className={`max-w-3xl rounded-2xl px-5 py-3 ${
                msg.role === 'user'
                  ? 'bg-indigo-600 text-white rounded-br-none'
                  : 'bg-white border border-slate-200 text-slate-800 rounded-bl-none shadow-sm'
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
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
    </div>
  );
}
