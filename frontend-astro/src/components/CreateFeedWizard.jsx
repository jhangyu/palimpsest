import React, { useState } from 'react';
import { api } from './api';
import PreviewTable from './PreviewTable';

const DEFAULT_LIST_RULES = '{\n  "container": "",\n  "item": "",\n  "title": "",\n  "link": ""\n}';
const DEFAULT_CONTENT_RULES = '{\n  "title": "",\n  "body": "",\n  "date": "",\n  "is_vue_template": false,\n  "vue_json_field": ""\n}';

const CreateFeedWizard = () => {
  const previewRef = React.useRef();
  const [url, setUrl] = useState('');
  const [siteName, setSiteName] = useState('');
  const [sampleUrl, setSampleUrl] = useState('');

  const [listRules, setListRules] = useState(DEFAULT_LIST_RULES);
  const [contentRules, setContentRules] = useState(DEFAULT_CONTENT_RULES);
  const [debugMode, setDebugMode] = useState(false);

  const [loadingList, setLoadingList] = useState(false);
  const [loadingContent, setLoadingContent] = useState(false);
  const [saving, setSaving] = useState(false);
  const [rulesExpanded, setRulesExpanded] = useState(false);

  const handleAnalyzeList = async () => {
    if (!url) return alert("Please enter Target URL first");
    setLoadingList(true);
    try {
      const data = await api.analyzeList(url, debugMode);
      setListRules(JSON.stringify(data.rules, null, 2));
      if (debugMode && data.debug_dir) alert("Debug: " + data.debug_dir);
    } catch(err) {
      alert("Error analyzing list: " + err.message);
    } finally {
      setLoadingList(false);
    }
  };

  const handleAnalyzeContent = async () => {
    if (!sampleUrl) return alert("Please enter Sample Article URL first");
    setLoadingContent(true);
    try {
      const data = await api.analyzeContent(sampleUrl, debugMode);
      setContentRules(JSON.stringify(data.rules, null, 2));
      if (debugMode && data.debug_dir) alert("Debug: " + data.debug_dir);
    } catch(err) {
      alert("Error analyzing content: " + err.message);
    } finally {
      setLoadingContent(false);
    }
  };

  const handleSave = async () => {
    if (!url || !siteName) return alert("URL and Site Name are required");
    try {
      const parsedList = JSON.parse(listRules);
      const parsedContent = JSON.parse(contentRules);

      setSaving(true);
      await api.createSite({
        site: { url, name: siteName, refresh_frequency: 60 },
        rules: { list_rules: parsedList, content_rules: parsedContent }
      });
      alert("Feed created successfully!");
      window.location.href = '/';
    } catch (err) {
      alert("Error saving: " + err.message + "\n(Make sure rules are valid JSON)");
    } finally {
      setSaving(false);
    }
  };

  const getParsedRules = (rulesStr) => {
    try { return JSON.parse(rulesStr); } catch { return {}; }
  };

  return (
    <>
      <div className="wizard-container" style={rulesExpanded ? {} : { gridTemplateColumns: '1fr' }}>
        <div className="wizard-form">
          <h2 style={{ fontSize: '24px', fontWeight: 600 }}>Create New Feed</h2>
          <p style={{ color: 'var(--text-secondary)' }}>Provide the website details and let our AI figure out the extraction rules.</p>

          <div className="input-group">
            <label>Target Website URL</label>
            <input type="text" placeholder="https://example.com/blog" value={url} onChange={e => setUrl(e.target.value)} />
          </div>
          <div className="input-group">
            <label>Site Name</label>
            <input type="text" placeholder="Example Blog" value={siteName} onChange={e => setSiteName(e.target.value)} />
          </div>

          <hr style={{ border: 'none', borderTop: '1px solid var(--border-color)', margin: '12px 0' }} />

          <div className="input-group">
            <div className="action-row">
              <label>1. List Rules (AI Generation)</label>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-secondary" onClick={() => previewRef.current?.triggerTest('list')} title="Test only list extraction">
                  <span>📝</span> Test List
                </button>
                <button className="btn btn-primary" onClick={handleAnalyzeList} disabled={loadingList}>
                  {loadingList ? <><span className="animate-spin">⏳</span> Analyzing</> : '🧠 Analyze List'}
                </button>
              </div>
            </div>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Click analyze to automatically extract list selectors from the Target URL above.</p>
          </div>

          <div className="input-group" style={{ marginTop: '16px' }}>
            <div className="action-row">
              <label>2. Content Rules (AI Generation)</label>
              <div style={{ display: 'flex', gap: 8 }}>
                 <button className="btn btn-secondary" onClick={() => previewRef.current?.triggerTest('content', sampleUrl)} title="Test content extraction with sample URL">
                  <span>📄</span> Test Content
                </button>
                <button className="btn btn-primary" onClick={handleAnalyzeContent} disabled={loadingContent}>
                  {loadingContent ? <><span className="animate-spin">⏳</span> Analyzing</> : '🧠 Analyze Content'}
                </button>
              </div>
            </div>
            <input type="text" placeholder="Sample Article URL (e.g. https://example.com/blog/post-1)" value={sampleUrl} onChange={e => setSampleUrl(e.target.value)} style={{ marginTop: '8px' }} />
          </div>

          <div style={{ marginTop: 16 }}>
            <button className="btn btn-secondary" style={{ padding: '4px 12px', fontSize: '13px' }} onClick={() => setRulesExpanded(!rulesExpanded)}>
              {rulesExpanded ? '▶ Hide Rules JSON' : '◀ Show Rules JSON'}
            </button>
          </div>

          <div className="footer-actions">
            <button
              className="btn btn-success"
              style={{ padding: '0 32px' }}
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? <><span className="animate-spin">⏳</span> Saving...</> : '🚀 Start Crawling'}
            </button>
            <label className="debug-toggle" title="Enable debug mode to save intermediate artifacts">
              <span>🐛</span>
              <span style={{ fontSize: '14px', fontWeight: 500 }}>Debug</span>
              <input type="checkbox" checked={debugMode} onChange={e => setDebugMode(e.target.checked)} style={{ display: 'none' }} />
              <div className={`toggle-switch ${debugMode ? 'on' : ''}`} />
            </label>
          </div>
        </div>

        {rulesExpanded && (
          <div className="wizard-preview">
            <h2 style={{ fontSize: '20px', fontWeight: 600, color: 'white', marginBottom: '8px' }}>Rules Preview JSON</h2>
            <p style={{ color: '#9CA3AF', fontSize: '13px', marginBottom: '24px' }}>You can manually tweak the rules here before saving.</p>

            <div className="section-title">List Rules</div>
            <textarea
              className="preview-block"
              spellCheck="false"
              value={listRules}
              onChange={e => setListRules(e.target.value)}
              style={{ minHeight: '200px', background: '#1F2937', color: '#60A5FA', border: '1px solid #374151' }}
            />

            <div className="section-title" style={{ marginTop: '24px' }}>Content Rules</div>
            <textarea
              className="preview-block"
              spellCheck="false"
              value={contentRules}
              onChange={e => setContentRules(e.target.value)}
              style={{ minHeight: '220px', background: '#1F2937', color: '#34D399', border: '1px solid #374151' }}
            />
          </div>
        )}
      </div>

      <PreviewTable
        ref={previewRef}
        url={url}
        listRules={getParsedRules(listRules)}
        contentRules={getParsedRules(contentRules)}
        debugMode={debugMode}
        onDebugModeChange={setDebugMode}
      />
    </>
  );
};

export default CreateFeedWizard;