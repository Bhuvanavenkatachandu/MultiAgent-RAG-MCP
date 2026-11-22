export interface DocumentItem {
  name: string;
  size_bytes: number;
  modified: number;
  extension: string;
}

export interface ChatMessageItem {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatResponse {
  response: string;
  role: string;
}

const API_BASE = import.meta.env.VITE_API_URL || '';

export async function checkHealth(): Promise<{ status: string; mcp_connected: boolean }> {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error('Backend health check failed');
  return res.json();
}

export async function fetchDocuments(): Promise<DocumentItem[]> {
  const res = await fetch(`${API_BASE}/api/documents`);
  if (!res.ok) throw new Error('Failed to fetch documents');
  const data = await res.json();
  return data.documents || [];
}

export async function uploadDocument(file: File): Promise<{ filename: string; status: string; message: string }> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/api/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(errorData.detail || 'Upload failed');
  }

  return res.json();
}

export async function sendChatMessage(
  message: string,
  history: ChatMessageItem[] = []
): Promise<string> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      history: history.slice(-8), // Send recent context for follow-ups
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Chat request failed' }));
    throw new Error(err.detail || 'Chat request failed');
  }

  const data: ChatResponse = await res.json();
  return data.response;
}

export async function sendChatMessageStream(
  message: string,
  history: ChatMessageItem[] = [],
  onToken: (token: string) => void,
  onStatus?: (status: string) => void
): Promise<string> {
  const res = await fetch(`${API_BASE}/api/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      history: history.slice(-8),
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Chat request failed' }));
    throw new Error(err.detail || 'Chat request failed');
  }

  if (!res.body) throw new Error('ReadableStream not supported');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let fullText = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || !trimmed.startsWith('data:')) continue;
      const dataStr = trimmed.replace(/^data:\s*/, '').trim();
      if (dataStr === '[DONE]') continue;

      try {
        const payload = JSON.parse(dataStr);
        if (payload.type === 'token' && payload.content) {
          fullText += payload.content;
          onToken(payload.content);
        } else if (payload.type === 'status' && payload.message && onStatus) {
          onStatus(payload.message);
        } else if (payload.type === 'error' && payload.message) {
          throw new Error(payload.message);
        }
      } catch (e: any) {
        if (dataStr.includes('"type":"error"') || dataStr.includes('"type": "error"')) {
          throw e;
        }
      }
    }
  }

  return fullText;
}
