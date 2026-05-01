const API_BASE = "";

export const api = {
  getSites: async () => {
    const res = await fetch(`${API_BASE}/sites/`);
    if (!res.ok) throw new Error('Failed to fetch sites');
    return await res.json();
  },
  getSite: async (id) => {
    const res = await fetch(`${API_BASE}/sites/${id}`);
    if (!res.ok) throw new Error('Failed to fetch site');
    return await res.json();
  },
  deleteSite: async (id) => {
    const res = await fetch(`${API_BASE}/sites/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete site');
    return await res.json();
  },
  updateSite: async (id, payload) => {
    const res = await fetch(`${API_BASE}/sites/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Failed to update site');
    return await res.json();
  },
  duplicateSite: async (id) => {
    const res = await fetch(`${API_BASE}/sites/${id}/duplicate`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to duplicate site');
    return await res.json();
  },
  triggerCrawl: async (id, debug = false) => {
    const params = debug ? `?debug=true` : '';
    const res = await fetch(`${API_BASE}/crawl/${id}${params}`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to trigger crawl');
    return await res.json();
  },
  analyzeList: async (url, debug = false) => {
    const debugParam = debug ? '&debug=true' : '';
    const res = await fetch(`${API_BASE}/analyze/list?url=${encodeURIComponent(url)}${debugParam}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    return data;
  },
  analyzeContent: async (url, debug = false) => {
    const debugParam = debug ? '&debug=true' : '';
    const res = await fetch(`${API_BASE}/analyze/content?url=${encodeURIComponent(url)}${debugParam}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    return data;
  },
  createSite: async (payload) => {
    const res = await fetch(`${API_BASE}/sites/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to create site');
    return data;
  },
  previewCrawl: async (payload, debug = false) => {
    const res = await fetch(`${API_BASE}/crawl/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...payload, debug })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to preview crawl');
    return data;
  }
};
