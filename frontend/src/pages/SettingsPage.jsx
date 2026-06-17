import { useEffect, useState } from 'react';

export const MODEL_MAX_TOKENS = {
  'llama-3.1-8b-instant': 8192,
  'mixtral-8x7b-32768': 32768,
  'gpt-4o-mini': 8192,
  'gpt-4o': 16384,
};

const PROVIDERS = {
  groq: {
    label: 'Groq',
    models: ['llama-3.1-8b-instant', 'mixtral-8x7b-32768'],
  },
  openai: {
    label: 'OpenAI',
    models: ['gpt-4o-mini', 'gpt-4o'],
  },
};

const STORAGE_KEYS = {
  provider: 'llm_provider',
  model: 'llm_model',
  systemPrompt: 'rag_system_prompt',
  chunkSize: 'rag_chunk_size',
  chunkOverlap: 'rag_chunk_overlap',
  maxTokens: 'rag_max_tokens',
  historyLimit: 'rag_history_limit',
};

const apiKeyFor = (provider) => `llm_api_key_${provider}`;

export const DEFAULT_SYSTEM_PROMPT = `You are a helpful assistant. Answer the question using the provided context and previous conversation.
If the question asks about earlier parts of the conversation, use the previous conversation.
Cite the source document name, page number, and chunk index for each fact you use from the context.

Context:
{context}

Previous conversation:
{history}

Question: {question}

Answer:`;

export const DEFAULT_CHUNK_SIZE = 1000;
export const DEFAULT_CHUNK_OVERLAP = 200;
export const DEFAULT_MAX_TOKENS = MODEL_MAX_TOKENS['llama-3.1-8b-instant'];
export const DEFAULT_HISTORY_LIMIT = 2;

function parseIntOrDefault(value, defaultValue) {
  const parsed = parseInt(value, 10);
  return Number.isNaN(parsed) ? defaultValue : parsed;
}

export default function SettingsPage() {
  const [provider, setProvider] = useState('groq');
  const [model, setModel] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_SYSTEM_PROMPT);
  const [chunkSize, setChunkSize] = useState(DEFAULT_CHUNK_SIZE);
  const [chunkOverlap, setChunkOverlap] = useState(DEFAULT_CHUNK_OVERLAP);
  const [maxTokens, setMaxTokens] = useState(DEFAULT_MAX_TOKENS);
  const [historyLimit, setHistoryLimit] = useState(DEFAULT_HISTORY_LIMIT);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const storedProvider = localStorage.getItem(STORAGE_KEYS.provider) || 'groq';
    const storedApiKey = localStorage.getItem(apiKeyFor(storedProvider)) || '';
    const defaultModel = PROVIDERS[storedProvider].models[0];
    const storedModel = localStorage.getItem(STORAGE_KEYS.model) || defaultModel;

    const resolvedModel = PROVIDERS[storedProvider].models.includes(storedModel) ? storedModel : defaultModel;
    setProvider(storedProvider);
    setModel(resolvedModel);
    setApiKey(storedApiKey);
    setSystemPrompt(localStorage.getItem(STORAGE_KEYS.systemPrompt) || DEFAULT_SYSTEM_PROMPT);
    setChunkSize(parseIntOrDefault(localStorage.getItem(STORAGE_KEYS.chunkSize), DEFAULT_CHUNK_SIZE));
    setChunkOverlap(parseIntOrDefault(localStorage.getItem(STORAGE_KEYS.chunkOverlap), DEFAULT_CHUNK_OVERLAP));
    const savedMax = localStorage.getItem(STORAGE_KEYS.maxTokens);
    setMaxTokens(savedMax ? parseIntOrDefault(savedMax, DEFAULT_MAX_TOKENS) : (MODEL_MAX_TOKENS[resolvedModel] ?? DEFAULT_MAX_TOKENS));
    setHistoryLimit(parseIntOrDefault(localStorage.getItem(STORAGE_KEYS.historyLimit), DEFAULT_HISTORY_LIMIT));
  }, []);

  const handleProviderChange = (newProvider) => {
    setProvider(newProvider);
    const defaultModel = PROVIDERS[newProvider].models[0];
    setModel(defaultModel);
    setMaxTokens(MODEL_MAX_TOKENS[defaultModel] ?? DEFAULT_MAX_TOKENS);
    setApiKey(localStorage.getItem(apiKeyFor(newProvider)) || '');
    setSaved(false);
  };

  const handleModelChange = (newModel) => {
    setModel(newModel);
    setMaxTokens(MODEL_MAX_TOKENS[newModel] ?? DEFAULT_MAX_TOKENS);
    setSaved(false);
  };

  const handleSave = (e) => {
    e.preventDefault();
    localStorage.setItem(STORAGE_KEYS.provider, provider);
    localStorage.setItem(STORAGE_KEYS.model, model);
    localStorage.setItem(apiKeyFor(provider), apiKey.trim());
    localStorage.setItem(STORAGE_KEYS.systemPrompt, systemPrompt.trim());
    localStorage.setItem(STORAGE_KEYS.chunkSize, String(chunkSize));
    localStorage.setItem(STORAGE_KEYS.chunkOverlap, String(chunkOverlap));
    localStorage.setItem(STORAGE_KEYS.maxTokens, String(maxTokens));
    localStorage.setItem(STORAGE_KEYS.historyLimit, String(historyLimit));
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const handleResetDefaults = () => {
    setSystemPrompt(DEFAULT_SYSTEM_PROMPT);
    setChunkSize(DEFAULT_CHUNK_SIZE);
    setChunkOverlap(DEFAULT_CHUNK_OVERLAP);
    setMaxTokens(MODEL_MAX_TOKENS[model] ?? DEFAULT_MAX_TOKENS);
    setHistoryLimit(DEFAULT_HISTORY_LIMIT);
    setSaved(false);
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Settings</h1>

      <form onSubmit={handleSave} className="space-y-6 bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
        {/* Provider selection */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            LLM Provider
          </label>
          <div className="flex gap-3">
            {Object.entries(PROVIDERS).map(([key, { label }]) => (
              <button
                key={key}
                type="button"
                onClick={() => handleProviderChange(key)}
                className={`flex-1 px-4 py-2 rounded-lg border text-sm font-medium transition ${
                  provider === key
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Default provider is Groq. The backend will fall back to its environment variable keys if you leave the API key empty.
          </p>
        </div>

        {/* API Key */}
        <div>
          <label htmlFor="apiKey" className="block text-sm font-medium text-slate-700 mb-2">
            API Key
          </label>
          <div className="relative">
            <input
              id="apiKey"
              type={showKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => {
                setApiKey(e.target.value);
                setSaved(false);
              }}
              placeholder={`Optional — uses backend ${provider === 'groq' ? 'GROQ_API_KEY' : 'OPENAI_API_KEY'} if blank`}
              className="w-full border border-slate-300 rounded-lg px-4 py-2.5 pr-20 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <button
              type="button"
              onClick={() => setShowKey((s) => !s)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-indigo-600 hover:text-indigo-800 font-medium"
            >
              {showKey ? 'Hide' : 'Show'}
            </button>
          </div>
          <p className="mt-1.5 text-xs text-slate-500">
            Stored only in your browser&apos;s localStorage.
          </p>
        </div>

        {/* Model selection */}
        <div>
          <label htmlFor="model" className="block text-sm font-medium text-slate-700 mb-2">
            Model
          </label>
          <select
            id="model"
            value={model}
            onChange={(e) => handleModelChange(e.target.value)}
            className="w-full border border-slate-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
          >
            {PROVIDERS[provider].models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>

        <hr className="border-slate-200" />

        {/* System Prompt */}
        <div>
          <label htmlFor="systemPrompt" className="block text-sm font-medium text-slate-700 mb-2">
            System Prompt
          </label>
          <textarea
            id="systemPrompt"
            rows={8}
            value={systemPrompt}
            onChange={(e) => {
              setSystemPrompt(e.target.value);
              setSaved(false);
            }}
            className="w-full border border-slate-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono text-sm"
          />
          <p className="mt-1.5 text-xs text-slate-500">
            Default prompt sent to the LLM. Use {'{context}'}, {'{history}'}, and {'{question}'} placeholders.
          </p>
        </div>

        {/* Max Tokens */}
        <div>
          <label htmlFor="maxTokens" className="block text-sm font-medium text-slate-700 mb-2">
            Max Tokens
          </label>
          <input
            id="maxTokens"
            type="number"
            min={1}
            max={MODEL_MAX_TOKENS[model] ?? 32768}
            value={maxTokens}
            onChange={(e) => {
              setMaxTokens(parseIntOrDefault(e.target.value, DEFAULT_MAX_TOKENS));
              setSaved(false);
            }}
            className="w-full border border-slate-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <p className="mt-1.5 text-xs text-slate-500">
            Maximum tokens the LLM can generate. Model max for <strong>{model || '…'}</strong> is{' '}
            <strong>{(MODEL_MAX_TOKENS[model] ?? 32768).toLocaleString()}</strong>.
          </p>
        </div>

        <hr className="border-slate-200" />

        {/* Chat History Context Limit */}
        <div>
          <label htmlFor="historyLimit" className="block text-sm font-medium text-slate-700 mb-2">
            Chat History Context
          </label>
          <input
            id="historyLimit"
            type="number"
            min={1}
            max={50}
            value={historyLimit}
            onChange={(e) => {
              setHistoryLimit(parseIntOrDefault(e.target.value, DEFAULT_HISTORY_LIMIT));
              setSaved(false);
            }}
            className="w-full border border-slate-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          />
          <p className="mt-1.5 text-xs text-slate-500">
            Number of recent user+assistant turns to include in the LLM context. Default is {DEFAULT_HISTORY_LIMIT}.
          </p>
        </div>

        <hr className="border-slate-200" />

        {/* Chunking */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="chunkSize" className="block text-sm font-medium text-slate-700 mb-2">
              Chunk Size (characters)
            </label>
            <input
              id="chunkSize"
              type="number"
              min={100}
              max={4000}
              value={chunkSize}
              onChange={(e) => {
                setChunkSize(parseIntOrDefault(e.target.value, DEFAULT_CHUNK_SIZE));
                setSaved(false);
              }}
              className="w-full border border-slate-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <p className="mt-1.5 text-xs text-slate-500">
              Number of characters per chunk. Default: {DEFAULT_CHUNK_SIZE}
            </p>
          </div>

          <div>
            <label htmlFor="chunkOverlap" className="block text-sm font-medium text-slate-700 mb-2">
              Chunk Overlap (characters)
            </label>
            <input
              id="chunkOverlap"
              type="number"
              min={0}
              max={1000}
              value={chunkOverlap}
              onChange={(e) => {
                setChunkOverlap(parseIntOrDefault(e.target.value, DEFAULT_CHUNK_OVERLAP));
                setSaved(false);
              }}
              className="w-full border border-slate-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
            <p className="mt-1.5 text-xs text-slate-500">
              Number of overlapping characters between chunks. Default: {DEFAULT_CHUNK_OVERLAP}
            </p>
          </div>
        </div>
        <p className="text-xs text-slate-500">
          Chunking settings are applied when new PDFs are uploaded. Existing chunks are not re-indexed.
        </p>

        {/* Actions */}
        <div className="flex items-center gap-4 pt-2">
          <button
            type="submit"
            className="px-6 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-medium transition"
          >
            Save Settings
          </button>
          <button
            type="button"
            onClick={handleResetDefaults}
            className="px-6 py-2.5 bg-white text-slate-700 border border-slate-300 rounded-lg hover:bg-slate-50 font-medium transition"
          >
            Reset to Defaults
          </button>
          {saved && (
            <span className="text-sm text-green-600 font-medium">Saved successfully</span>
          )}
        </div>
      </form>
    </div>
  );
}
