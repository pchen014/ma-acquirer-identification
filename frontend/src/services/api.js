const API_BASE = '/api';

export async function getDatabaseStats() {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) throw new Error('Failed to load database stats');
  return res.json();
}

export async function uploadDealsCsv(file) {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/deals/upload`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
    throw new Error(err.detail || 'Upload failed');
  }

  return res.json();
}

export async function recommendAcquirers(targetInput, topK = 10) {
  const res = await fetch(`${API_BASE}/recommend`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      target_input: targetInput,
      top_k: Number(topK),
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Recommendation failed' }));
    throw new Error(err.detail || 'Failed to identify potential acquirers');
  }

  return res.json();
}
