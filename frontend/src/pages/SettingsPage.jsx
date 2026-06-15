import { useEffect, useState } from 'react';

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
  apiKey: 'llm_api_key',
};

export default function SettingsPage() {
  const [provider, setProvider] = useState('groq');
  const [model, setModel] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const storedProvider = localStorage.getItem(STORAGE_KEYS.provider) || 'groq';
    const storedApiKey = localStorage.getItem(STORAGE_KEYS.apiKey) || '';
    const defaultModel = PROVIDERS[storedProvider].models[0];
    const storedModel = localStorage.getItem(STORAGE_KEYS.model) || defaultModel;

    setProvider(storedProvider);
    setModel(PROVIDERS[storedProvider].models.includes(storedModel) ? storedModel : defaultModel);
    setApiKey(storedApiKey);
  }, []);

  const handleProviderChange = (newProvider) => {
    setProvider(newProvider);
    setModel(PROVIDERS[newProvider].models[0]);
    setSaved(false);
  };

  const handleSave = (e) => {
    e.preventDefault();
    localStorage.setItem(STORAGE_KEYS.provider, provider);
    localStorage.setItem(STORAGE_KEYS.model, model);
    localStorage.setItem(STORAGE_KEYS.apiKey, apiKey.trim());
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
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
            onChange={(e) => {
              setModel(e.target.value);
              setSaved(false);
            }}
            className="w-full border border-slate-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
          >
            {PROVIDERS[provider].models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-4 pt-2">
          <button
            type="submit"
            className="px-6 py-2.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 font-medium transition"
          >
            Save Settings
          </button>
          {saved && (
            <span className="text-sm text-green-600 font-medium">Saved successfully</span>
          )}
        </div>
      </form>
    </div>
  );
}
