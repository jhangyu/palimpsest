import React, { useState, useImperativeHandle, forwardRef } from 'react';
import { api } from './api';

const PreviewTable = forwardRef(({ url, listRules, contentRules, debugMode = false, onDebugModeChange = null }, ref) => {
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [mode, setMode] = useState('both'); // 'list', 'content', 'both'
  const [debugDir, setDebugDir] = useState(null);

  useImperativeHandle(ref, () => ({
    triggerTest: (testMode, customUrl = null) => {
      handlePreview(testMode, customUrl);
    }
  }));

  const handlePreview = async (testMode = 'both', customUrl = null) => {
    const targetUrl = customUrl || url;

    if (testMode === 'list' && (!targetUrl || !listRules?.item)) {
        setError("Please ensure Target URL and List Item rules are filled.");
        return;
    }
    if (testMode === 'content' && !targetUrl) {
        setError("Please enter a Sample URL to test content extraction.");
        return;
    }

    setMode(testMode);
    setLoading(true);
    setError(null);
    setResults(null);
    setDebugDir(null);

    document.getElementById('live-preview-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });

    try {
      const payload = {
        url: targetUrl,
        list_rules: listRules,
        content_rules: contentRules || {},
        mode: testMode,
        target_url: customUrl
      };

      const res = await api.previewCrawl(payload, debugMode);
      if (res.status === 'success') {
         if (res.data && res.data.length > 0 && res.data[0].error) {
             setError(res.data[0].error);
         } else {
             setResults(res.data);
             if (debugMode && res.debug_dir) {
               setDebugDir(res.debug_dir);
             }
         }
      }
    } catch (err) {
      setError(err.message || 'Preview failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="preview-container" id="live-preview-section">
      <div className="preview-header">
        <div className="preview-title">
          <h3>Live Crawl Preview</h3>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {onDebugModeChange && (
            <label className="debug-toggle" title="Enable debug mode to save intermediate artifacts">
              <span>🐛</span>
              <span style={{ fontSize: '14px', fontWeight: 500 }}>Debug</span>
              <input
                type="checkbox"
                checked={debugMode}
                onChange={e => onDebugModeChange(e.target.checked)}
                style={{ display: 'none' }}
              />
              <div className={`toggle-switch ${debugMode ? 'on' : ''}`} />
            </label>
          )}
          <button className="btn btn-primary" style={{ padding: '0 24px' }} onClick={() => handlePreview('both')} disabled={loading}>
            {loading ? <span className="animate-spin">⏳</span> : <span>▶️</span>}
            Test Both List & Content Crawl
          </button>
        </div>
      </div>

      {debugDir && (
        <div className="debug-dir-banner">
          <span>🐛</span>
          <span>Debug artifacts saved to:</span>
          <code>{debugDir}</code>
          <a href={`file://${debugDir}`} target="_blank" rel="noreferrer" title="Open debug directory">
            🔗
          </a>
        </div>
      )}

      {error && (
        <div className="preview-error">
          <span>⚠️</span> {error}
        </div>
      )}

      {loading && (
        <div className="preview-loading">
            <span className="animate-spin" style={{ fontSize: '32px' }}>⏳</span>
            <p>Crawling and analyzing {mode === 'both' ? 'everything' : mode}...</p>
        </div>
      )}
      {results && results.length > 0 && (
        <div className="preview-table-wrapper">
          <table className="preview-table">
            <thead>
              <tr>
                <th style={{ width: mode === 'list' ? '40%' : '25%' }}>Title</th>
                <th style={{ width: mode === 'list' ? '60%' : '15%' }}>{mode === 'list' ? 'URL' : 'Time'}</th>
                {mode !== 'list' && <th style={{ width: '60%' }}>Content Preview</th>}
              </tr>
            </thead>
            <tbody>
              {results.map((r, i) => (
                <tr key={i}>
                  <td>
                    <span className="preview-link-text">{r.title}</span>
                  </td>
                  <td>
                    {mode === 'list' ? (
                        <a href={r.url} target="_blank" rel="noreferrer" className="preview-url-text">{r.url}</a>
                    ) : (
                        <span className="preview-time">{r.published_at || 'N/A'}</span>
                    )}
                  </td>
                  {mode !== 'list' && (
                    <td>
                      <div className="preview-content-scroll">
                        {r.content ? (
                            <div dangerouslySetInnerHTML={{ __html: r.content.substring(0, 500) + (r.content.length > 500 ? '...' : '') }} />
                        ) : 'No content extracted'}
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && results && results.length === 0 && (
        <div className="preview-empty">No results found. Please check your rules.</div>
      )}
    </div>
  );
});

export default PreviewTable;