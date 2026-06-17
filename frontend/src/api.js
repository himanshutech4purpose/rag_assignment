import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';
const api = axios.create({ baseURL: API_BASE });

export const uploadFiles = (files, { chunkSize, chunkOverlap } = {}) => {
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));

  const params = new URLSearchParams();
  if (chunkSize != null) params.append('chunk_size', String(chunkSize));
  if (chunkOverlap != null) params.append('chunk_overlap', String(chunkOverlap));

  return api.post(`/upload?${params.toString()}`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const listDocuments = () => api.get('/documents');
export const getDocumentChunks = (id) => api.get(`/documents/${id}/chunks`);
export const deleteDocument = (id) => api.delete(`/documents/${id}`);

export const createConversation = (title) => api.post('/conversations', { title });
export const listConversations = () => api.get('/conversations');
export const getConversation = (id) => api.get(`/conversations/${id}`);
export const deleteConversation = (id) => api.delete(`/conversations/${id}`);
export const getMessageDebug = (conversationId, messageId) =>
  api.get(`/conversations/${conversationId}/messages/${messageId}/debug`);

export async function streamQuestion(
  conversationId,
  question,
  { provider, model, apiKey, systemPrompt, maxTokens, historyLimit, onToken, onSources, onDone, onError }
) {
  try {
    const payload = {
      question,
      provider: provider || 'groq',
      model: model || undefined,
      api_key: apiKey?.trim() || undefined,
      system_prompt: systemPrompt?.trim() || undefined,
      max_tokens: maxTokens ?? undefined,
      history_limit: historyLimit ?? undefined,
    };

    const response = await fetch(`${API_BASE}/conversations/${conversationId}/ask/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      onError(new Error(`HTTP ${response.status}`));
      return;
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let currentEvent = null;
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (line === '') {
          currentEvent = null;
          continue;
        }
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim();
          continue;
        }
        if (line.startsWith('data: ')) {
          const payload = line.slice(6);
          if (payload === '[DONE]') {
            onDone();
            return;
          }
          if (currentEvent === 'sources') {
            onSources(JSON.parse(payload));
          } else if (currentEvent === 'error') {
            onError(new Error('LLM service temporarily unavailable'));
            return;
          } else {
            onToken(payload);
          }
        }
      }
    }
    onDone();
  } catch (err) {
    onError(err);
  }
}
