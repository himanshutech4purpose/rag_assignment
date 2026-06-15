import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';
const api = axios.create({ baseURL: API_BASE });

export const uploadFiles = (files) => {
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));
  return api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const listDocuments = () => api.get('/documents');
export const deleteDocument = (id) => api.delete(`/documents/${id}`);

export const createConversation = (title) => api.post('/conversations', { title });
export const listConversations = () => api.get('/conversations');
export const getConversation = (id) => api.get(`/conversations/${id}`);
export const deleteConversation = (id) => api.delete(`/conversations/${id}`);

export async function streamQuestion(
  conversationId,
  question,
  { provider, model, apiKey, onToken, onSources, onDone, onError }
) {
  try {
    const response = await fetch(`${API_BASE}/conversations/${conversationId}/ask/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question,
        provider: provider || 'groq',
        model: model || undefined,
        api_key: apiKey?.trim() || undefined,
      }),
    });
    if (!response.ok) {
      onError(new Error(`HTTP ${response.status}`));
      return;
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (line.startsWith('data: [DONE]')) {
          onDone();
          return;
        }
        if (line.startsWith('event: sources')) continue;
        if (line.startsWith('event: error')) {
          onError(new Error('LLM service temporarily unavailable'));
          return;
        }
        if (line.startsWith('data: ')) {
          const payload = line.slice(6);
          if (payload.startsWith('[')) {
            onSources(JSON.parse(payload));
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
