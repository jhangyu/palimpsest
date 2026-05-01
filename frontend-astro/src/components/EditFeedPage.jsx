import React, { useState, useEffect } from 'react';
import { api } from './api';
import PreviewTable from './PreviewTable';

const getParsedRules = (rulesStr) => {
    try { return JSON.parse(rulesStr); } catch { return {}; }
};

const EditFeedPage = ({ initialSiteId = null }) => {
    const previewRef = React.useRef();

    // List state
    const [sites, setSites] = useState([]);
    const [loadingList, setLoadingList] = useState(true);

    // Editor state
    const [selectedSite, setSelectedSite] = useState(null);
    const [editData, setEditData] = useState({
        name: '',
        url: '',
        refresh_frequency: 60,
        list_rules: '',
        content_rules: '',
        sample_url: ''
    });

    const [saving, setSaving] = useState(false);
    const [analyzing, setAnalyzing] = useState(null); // 'list' or 'content'
    const [crawlingId, setCrawlingId] = useState(null);
    const [debugMode, setDebugMode] = useState(false);

    useEffect(() => {
        fetchSites();
    }, []);

    useEffect(() => {
        if (initialSiteId) {
            handleEdit(parseInt(initialSiteId));
        }
    }, [initialSiteId]);

    const fetchSites = async () => {
        try {
            const data = await api.getSites();
            setSites(data);
        } catch (err) {
            console.error(err);
        } finally {
            setLoadingList(false);
        }
    };

    const handleEdit = async (id) => {
        try {
            const site = await api.getSite(id);
            setSelectedSite(site);
            setEditData({
                name: site.name,
                url: site.url,
                refresh_frequency: site.refresh_frequency || 60,
                list_rules: JSON.stringify(site.list_rules, null, 2),
                content_rules: JSON.stringify(site.content_rules, null, 2)
            });
            // Smooth scroll to editor
            setTimeout(() => {
                document.getElementById('editor-view')?.scrollIntoView({ behavior: 'smooth' });
            }, 100);
        } catch (err) {
            alert("Error fetching site details: " + err.message);
        }
    };

    const handleDuplicate = async (id) => {
        if (!window.confirm("Duplicate this feed configuration?")) return;
        try {
            await api.duplicateSite(id);
            fetchSites();
        } catch (err) {
            alert("Duplicate failed: " + err.message);
        }
    };

    const handleDelete = async (id) => {
        if (!window.confirm("Are you sure you want to delete this feed?")) return;
        try {
            await api.deleteSite(id);
            if (selectedSite?.id === id) setSelectedSite(null);
            fetchSites();
        } catch (err) {
            alert("Delete failed: " + err.message);
        }
    };

    const handleManualCrawl = async (id) => {
        setCrawlingId(id);
        try {
            await api.triggerCrawl(id, debugMode);
            alert("Crawl task triggered successfully!");
        } catch (err) {
            alert("Crawl failed: " + err.message);
        } finally {
            setCrawlingId(null);
        }
    };

    const handleUpdate = async () => {
        if (!selectedSite) return;
        setSaving(true);
        try {
            const payload = {
                name: editData.name,
                url: editData.url,
                refresh_frequency: parseInt(editData.refresh_frequency),
                list_rules: JSON.parse(editData.list_rules),
                content_rules: JSON.parse(editData.content_rules)
            };
            await api.updateSite(selectedSite.id, payload);
            alert("Site updated successfully!");
            fetchSites();
        } catch (err) {
            alert("Update failed: " + err.message);
        } finally {
            setSaving(false);
        }
    };

    const handleAnalyze = async (mode) => {
        const targetUrl = mode === 'list' ? editData.url : (editData.sample_url || prompt("Enter sample article URL for analysis:"));
        if (!targetUrl) return;

        setAnalyzing(mode);
        try {
            const method = mode === 'list' ? api.analyzeList : api.analyzeContent;
            const data = await method(targetUrl, debugMode);
            const key = mode === 'list' ? 'list_rules' : 'content_rules';
            setEditData(prev => ({ ...prev, [key]: JSON.stringify(data.rules, null, 2) }));
            if (debugMode && data.debug_dir) setTimeout(() => alert("Debug artifacts: " + data.debug_dir), 500);
        } catch (err) {
            alert(`AI Analysis failed: ${err.message}`);
        } finally {
            setAnalyzing(null);
        }
    };

    return (
        <div className="edit-page-container">
            {/* Top Section: Feed Table */}
            <div className="management-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h2 style={{ fontSize: '20px', fontWeight: 600 }}>Feed Management</h2>
                    <button className="mini-btn" onClick={fetchSites} disabled={loadingList}>
                        <span className={loadingList ? 'animate-spin' : ''}>🔄</span> Refresh Table
                    </button>
                </div>

                <div className="table-wrapper">
                    {loadingList ? (
                        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                            <span className="animate-spin" style={{ fontSize: '24px', display: 'block', marginBottom: '12px' }}>⏳</span>
                            Loading feeds...
                        </div>
                    ) : (
                        <table>
                            <thead>
                                <tr>
                                    <th>Feed Name</th>
                                    <th>Target URL</th>
                                    <th>Refresh</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {sites.map(site => (
                                    <tr key={site.id} className={selectedSite?.id === site.id ? 'active-row' : ''}>
                                        <td style={{ fontWeight: 500 }}>{site.name}</td>
                                        <td className="url-cell">
                                            <a href={site.url} target="_blank" rel="noreferrer" style={{ color: 'inherit', textDecoration: 'none' }}>
                                                {site.url} <span style={{ marginLeft: 4 }}>🔗</span>
                                            </a>
                                        </td>
                                        <td>{site.refresh_frequency || 60}m</td>
                                        <td className="action-btns">
                                            <button className="mini-btn edit" title="Edit Details" onClick={() => handleEdit(site.id)}>
                                                ✏️ Edit
                                            </button>
                                            <button className="mini-btn duplicate" title="Duplicate" onClick={() => handleDuplicate(site.id)}>
                                                📋
                                            </button>
                                            <button className="mini-btn crawl" title="Trigger Crawl" onClick={() => handleManualCrawl(site.id)} disabled={crawlingId === site.id}>
                                                {crawlingId === site.id ? <span className="animate-spin">⏳</span> : <span>▶️</span>}
                                            </button>
                                            <button className="mini-btn delete" title="Delete" onClick={() => handleDelete(site.id)}>
                                                🗑️
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
            </div>

            {/* Bottom Section: Detail Editor */}
            {selectedSite && (
                <div id="editor-view" className="editor-section wizard-container" style={{ gridTemplateColumns: '1fr 1fr', padding: 0, gap: '24px' }}>
                    <div className="management-card" style={{ boxShadow: 'none', border: '1px solid var(--border-color)' }}>
                        <h3 style={{ fontSize: '18px', marginBottom: '24px', display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span>✏️</span> Editing: {selectedSite.name}
                        </h3>

                        <div className="input-group">
                            <label>Target Website URL</label>
                            <input
                                type="text"
                                value={editData.url}
                                onChange={e => setEditData({...editData, url: e.target.value})}
                            />
                        </div>

                        <div className="input-group" style={{ marginTop: 16 }}>
                            <label>Site Name</label>
                            <input
                                type="text"
                                value={editData.name}
                                onChange={e => setEditData({...editData, name: e.target.value})}
                            />
                        </div>

                        <div className="freq-input-group">
                            <label>Refresh Frequency (minutes):</label>
                            <input
                                type="number"
                                min="5"
                                max="1440"
                                value={editData.refresh_frequency}
                                onChange={e => setEditData({...editData, refresh_frequency: e.target.value})}
                            />
                            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Range: 5 - 1440 (1 day)</span>
                        </div>

                        <hr style={{ border: 'none', borderTop: '1px solid var(--border-color)', margin: '24px 0' }} />

                        <div className="input-group">
                            <div className="action-row">
                                <label>1. List Rules (AI Generation)</label>
                                <div style={{ display: 'flex', gap: 8 }}>
                                    <button className="btn btn-secondary" style={{ padding: '0 12px', height: '36px' }} onClick={() => previewRef.current?.triggerTest('list')} title="Test only list extraction">
                                        📝 Test List
                                    </button>
                                    <button className="btn btn-primary" style={{ padding: '0 16px', height: '36px' }} onClick={() => handleAnalyze('list')} disabled={analyzing === 'list'}>
                                        {analyzing === 'list' ? <span className="animate-spin">⏳</span> : '🧠 Analyze List'}
                                    </button>
                                </div>
                            </div>
                        </div>

                        <div className="input-group" style={{ marginTop: 24 }}>
                            <div className="action-row">
                                <label>2. Content Rules (AI Generation)</label>
                                <div style={{ display: 'flex', gap: 8 }}>
                                    <button className="btn btn-secondary" style={{ padding: '0 12px', height: '36px' }} onClick={() => previewRef.current?.triggerTest('content', editData.sample_url)} title="Test content extraction with sample URL">
                                        📄 Test Content
                                    </button>
                                    <button className="btn btn-primary" style={{ padding: '0 16px', height: '36px' }} onClick={() => handleAnalyze('content')} disabled={analyzing === 'content'}>
                                        {analyzing === 'content' ? <span className="animate-spin">⏳</span> : '🧠 Analyze Content'}
                                    </button>
                                </div>
                            </div>
                            <input
                                type="text"
                                placeholder="Sample Article URL for testing"
                                value={editData.sample_url || ''}
                                onChange={e => setEditData({...editData, sample_url: e.target.value})}
                                style={{ marginTop: 8, fontSize: '13px' }}
                            />
                        </div>

                        <div style={{ marginTop: 40, display: 'flex', gap: 12, alignItems: 'center' }}>
                            <button className="btn btn-success" style={{ flex: 1, padding: '0 24px' }} onClick={handleUpdate} disabled={saving}>
                                {saving ? <span className="animate-spin">⏳</span> : <span>💾</span>}
                                {saving ? "Updating..." : "Save Changes"}
                            </button>
                            <button className="btn btn-primary" style={{ background: '#374151', width: '42px', padding: 0 }} onClick={() => handleManualCrawl(selectedSite.id)}>
                                ▶️
                            </button>
                            <label className="debug-toggle" title="Enable debug mode to save intermediate artifacts">
                                <span style={{ color: debugMode ? 'var(--accent-orange)' : 'var(--text-secondary)' }}>🐛</span>
                                <span style={{ fontSize: '12px', color: debugMode ? 'var(--accent-orange)' : 'var(--text-secondary)' }}>Debug</span>
                                <input type="checkbox" checked={debugMode} onChange={e => setDebugMode(e.target.checked)} style={{ display: 'none' }} />
                                <div className={`toggle-switch ${debugMode ? 'on' : ''}`} />
                            </label>
                        </div>
                    </div>

                    <div className="wizard-preview">
                        <div className="section-title">List Rules JSON</div>
                        <textarea
                            className="preview-block"
                            spellCheck="false"
                            value={editData.list_rules}
                            onChange={e => setEditData({...editData, list_rules: e.target.value})}
                            style={{ height: '240px' }}
                        />

                        <div className="section-title" style={{ marginTop: 20 }}>Content Rules JSON</div>
                        <textarea
                            className="preview-block"
                            spellCheck="false"
                            value={editData.content_rules}
                            onChange={e => setEditData({...editData, content_rules: e.target.value})}
                            style={{ height: '240px' }}
                        />
                    </div>
                </div>
            )}

            {/* Preview Section */}
            {selectedSite && (
                <PreviewTable
                    ref={previewRef}
                    url={editData.url}
                    listRules={getParsedRules(editData.list_rules)}
                    contentRules={getParsedRules(editData.content_rules)}
                    debugMode={debugMode}
                    onDebugModeChange={setDebugMode}
                />
            )}

        </div>
    );
};

export default EditFeedPage;