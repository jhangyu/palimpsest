import React, { useEffect, useState } from 'react';
import { api } from './api';

const API_BASE = "";

const DashboardOverview = () => {
  const [sites, setSites] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchSites = async () => {
    setLoading(true);
    try {
      const data = await api.getSites();
      setSites(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSites();
  }, []);

  const handleDelete = async (id) => {
    if(!window.confirm("Are you sure you want to delete this feed?")) return;
    try {
      await api.deleteSite(id);
      fetchSites();
    } catch (err) {
      alert("Failed to delete");
    }
  };

  const copyToClipboard = (url) => {
    navigator.clipboard.writeText(url);
    alert('RSS URL copied to clipboard!');
  };

  const normalizeUrl = (name) => {
    return name.replace(/ /g, '_').replace(/[^a-zA-Z0-9_\-]/g, '').toLowerCase();
  };

  return (
    <div>
      <div className="overview-grid">
        <div className="metric-card bg-blue">
          <div>
            <h3>Total Feeds</h3>
            <div className="value">{sites.length}</div>
          </div>
          <span style={{ fontSize: '32px' }}>📰</span>
        </div>
        <div className="metric-card bg-green">
          <div>
            <h3>System Status</h3>
            <div className="value">Healthy</div>
          </div>
          <span style={{ fontSize: '32px' }}>📊</span>
        </div>
        <div className="metric-card bg-purple">
          <div>
            <h3>Active Services</h3>
            <div className="value">3</div>
          </div>
          <span style={{ fontSize: '32px' }}>📋</span>
        </div>
      </div>

      <div className="content-grid">
        <div className="panel-section">
          <div className="panel-header">
            <h2>Active Feeds</h2>
            <a href="/add" className="btn btn-primary">+ Add New</a>
          </div>

          {loading ? (
            <p>Loading feeds...</p>
          ) : (
            <div className="feed-list">
              {sites.length === 0 && <p style={{color: 'var(--text-muted)'}}>No feeds found. Create one!</p>}
              {sites.map(site => {
                const rssUrl = `${API_BASE}/rss/${normalizeUrl(site.name)}`;
                return (
                  <div className="feed-item" key={site.id}>
                    <div className="feed-info">
                      <h4>{site.name}</h4>
                      <a href={site.url} target="_blank" rel="noreferrer">{site.url}</a>
                    </div>
                    <div className="feed-actions">
                      <a href={`/edit/${site.id}`} className="btn-icon" title="Edit Site">
                        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
                      </a>
                      <button className="btn-icon" onClick={() => copyToClipboard(rssUrl)} title="Copy RSS Link">
                        <span>📋</span>
                      </button>
                      <button className="btn-icon danger" onClick={() => handleDelete(site.id)} title="Delete Feed">
                        <span>🗑️</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="panel-section">
          <div className="panel-header">
            <h2>System Activity</h2>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ padding: '16px', background: 'var(--bg-primary)', borderRadius: '8px' }}>
              <p style={{ fontWeight: 500, fontSize: '14px' }}>Crawler Scheduler</p>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Runs every 1 hour.</p>
            </div>
            <div style={{ padding: '16px', background: 'var(--bg-primary)', borderRadius: '8px' }}>
              <p style={{ fontWeight: 500, fontSize: '14px' }}>AI Model</p>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>MiniMax-M2.7 (Active)</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DashboardOverview;
