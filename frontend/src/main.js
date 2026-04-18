import { mountNetworkGraph } from './mountNetworkGraph.jsx';
import { mountAuroraWaves } from './mountAuroraWaves.jsx';
import { mountNavBar } from './mountNavBar.jsx';
import { mountHomepage } from './mountHomepage.jsx';

const SESSION_KEY = 'tribal_session';
const DEFAULT_BACKEND_ORIGIN = 'https://hacksmu-26.onrender.com';
const BACKEND_ORIGIN = (
  import.meta.env.VITE_BACKEND_ORIGIN ||
  (window.location.hostname === 'localhost' ? '' : DEFAULT_BACKEND_ORIGIN)
).replace(/\/$/, '');

function apiUrl(path) {
  return `${BACKEND_ORIGIN}/api${path.startsWith('/') ? path : `/${path}`}`;
}

function resultsUrl(path) {
  return `${BACKEND_ORIGIN}/results${path.startsWith('/') ? path : `/${path}`}`;
}

async function requestJson(url, options) {
  const res = await fetch(url, options);
  const text = await res.text();
  if (!res.ok) {
    throw new Error(text || `${res.status} ${res.statusText}`);
  }
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(text.slice(0, 160));
  }
}

function applySessionFromAuth() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return;
    const { email, name } = JSON.parse(raw);
    const landing = document.getElementById('landing');
    const app = document.getElementById('app-content');
    if (landing && app) {
      landing.style.display = 'none';
      app.classList.add('visible');
    }
    const avatar = document.querySelector('.avatar-btn');
    if (avatar) {
      const src = (name && String(name).trim()) || email || '';
      avatar.textContent = src ? src.charAt(0).toUpperCase() : 'U';
      avatar.title = email || 'Profile';
    }
  } catch {
    /* ignore */
  }
}

applySessionFromAuth();

// ── Data ─────────────────────────────────────────────────────────────
let allCalls = [];
let clusterSummaries = {};
let tribeEdges = [];
let aiHypotheses = '';
let knowledgeBase = null;

async function loadCSV(url) {
  const res = await fetch(url);
  const text = await res.text();
  const lines = text.trim().split('\n');
  const headers = lines[0].split(',');
  return lines.slice(1).map(line => {
    const vals = [];
    let current = '';
    let inQuote = false;
    for (const ch of line) {
      if (ch === '"') { inQuote = !inQuote; continue; }
      if (ch === ',' && !inQuote) { vals.push(current); current = ''; continue; }
      current += ch;
    }
    vals.push(current);
    const obj = {};
    headers.forEach((h, i) => { obj[h.trim()] = vals[i]?.trim() ?? ''; });
    return obj;
  });
}

async function loadData() {
  try {
    const [calls, clusters, edgesRaw, hypothesesText, kb] = await Promise.all([
      loadCSV(resultsUrl('/batch_results_clustered.csv')).catch(() => loadCSV(resultsUrl('/batch_results.csv'))),
      requestJson(resultsUrl('/cluster_summaries.json')).catch(() => ({})),
      loadCSV(resultsUrl('/tribe_edges.csv')).catch(() => []),
      fetch(resultsUrl('/ai_hypotheses.txt')).then(r => r.ok ? r.text() : '').catch(() => ''),
      requestJson(resultsUrl('/knowledge_base.json')).catch(() => null),
    ]);
    allCalls = calls;
    clusterSummaries = clusters;
    tribeEdges = edgesRaw;
    aiHypotheses = hypothesesText;
    knowledgeBase = kb;
    return true;
  } catch (e) {
    console.error('Data load error:', e);
    return false;
  }
}

// ── Landing → App ────────────────────────────────────────────────────
document.getElementById('process-btn')?.addEventListener('click', () => {
  document.getElementById('landing').style.display = 'none';
  document.getElementById('homepage-content').style.display = 'none';
  document.getElementById('app-content').classList.add('visible');
});

document.getElementById('app-home')?.addEventListener('click', (e) => {
  e.preventDefault();
  document.getElementById('app-content').classList.remove('visible');
  document.getElementById('landing').style.display = 'flex';
  document.getElementById('homepage-content').style.display = 'block';
  window.history.replaceState(null, '', ' '); // clear hash to reset router visually
});

// ── Navigation ───────────────────────────────────────────────────────
function navigateTo(hash) {
  const sectionId = hash.replace('#', '') || 'dashboard';

  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  const targetSection = document.getElementById(`section-${sectionId}`);
  if (targetSection) targetSection.classList.add('active');

  if (sectionId === 'network') setTimeout(renderNetwork, 50);
  if (sectionId === 'upload') initUploadSection();
}

window.addEventListener('hashchange', () => navigateTo(window.location.hash));

// ── Dashboard ────────────────────────────────────────────────────────
function renderHeroStats() {
  const valid = allCalls.filter(c => c.valid === 'True');
  const avgSNR = valid.length
    ? (valid.reduce((a, c) => a + parseFloat(c.snr_improvement_db || 0), 0) / valid.length).toFixed(1)
    : '—';
  document.getElementById('hero-stats').innerHTML = `
    <div><div class="hero-stat-value">${allCalls.length}</div><div class="hero-stat-label">Calls Processed</div></div>
    <div><div class="hero-stat-value">${Object.keys(clusterSummaries).length}</div><div class="hero-stat-label">Clusters Found</div></div>
    <div><div class="hero-stat-value">${avgSNR} dB</div><div class="hero-stat-label">Avg SNR Gain</div></div>
  `;
}

function renderDashboard() {
  const valid = allCalls.filter(c => c.valid === 'True');
  const avgSNR = valid.length
    ? (valid.reduce((a, c) => a + parseFloat(c.snr_improvement_db || 0), 0) / valid.length).toFixed(1)
    : '—';
  const multi = allCalls.filter(c => c.multi_elephant === 'True').length;

  document.getElementById('stats-grid').innerHTML = `
    <div class="stat-card">
      <div class="stat-label">Calls Processed</div>
      <div class="stat-value">${allCalls.length}</div>
      <div class="stat-sub">Total analyzed</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Valid Calls</div>
      <div class="stat-value">${valid.length}</div>
      <div class="stat-sub">${((valid.length / allCalls.length) * 100).toFixed(0)}% success</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Avg SNR Gain</div>
      <div class="stat-value stat-accent">${avgSNR} <span style="font-size:0.8rem;color:var(--text-muted)">dB</span></div>
      <div class="stat-sub">Noise removal</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Clusters</div>
      <div class="stat-value">${Object.keys(clusterSummaries).length}</div>
      <div class="stat-sub">Patterns found</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Multi-Elephant</div>
      <div class="stat-value">${multi}</div>
      <div class="stat-sub">Overlapping calls</div>
    </div>
  `;

  // Noise chart
  const noiseCounts = {};
  allCalls.forEach(c => { const t = c.noise_type || 'unknown'; noiseCounts[t] = (noiseCounts[t] || 0) + 1; });
  const maxCount = Math.max(...Object.values(noiseCounts));
  document.getElementById('noise-chart').innerHTML = Object.entries(noiseCounts)
    .sort((a, b) => b[1] - a[1])
    .map(([type, count]) => `
      <div class="chart-bar-row">
        <div class="chart-bar-label">${type}</div>
        <div class="chart-bar-track">
          <div class="chart-bar" style="width:${((count / maxCount) * 100).toFixed(0)}%">${count}</div>
        </div>
      </div>
    `).join('');

  // Cluster pills — click navigates to clusters section
  document.getElementById('cluster-pills').innerHTML = Object.entries(clusterSummaries)
    .map(([id, s]) => `
      <div class="cluster-pill" onclick="navigateToCluster(${id})">
        <span class="cluster-pill-name">Cluster ${id}</span>
        <span class="cluster-pill-meta">${s.count} calls · ${s.mean_f0_hz} Hz</span>
      </div>
    `).join('');
}

// ── Explorer ─────────────────────────────────────────────────────────
function renderExplorer() {
  const noises = [...new Set(allCalls.map(c => c.noise_type).filter(Boolean))];
  const clusters = [...new Set(allCalls.map(c => c.cluster).filter(c => c !== undefined && c !== ''))];

  document.getElementById('noise-filter').innerHTML = `<option value="">All Noise</option>` +
    noises.map(t => `<option value="${t}">${t}</option>`).join('');
  document.getElementById('cluster-filter').innerHTML = `<option value="">All Clusters</option>` +
    clusters.map(c => `<option value="${c}">Cluster ${c}</option>`).join('');

  renderCallList();
  document.getElementById('call-search').addEventListener('input', renderCallList);
  document.getElementById('noise-filter').addEventListener('change', renderCallList);
  document.getElementById('cluster-filter').addEventListener('change', renderCallList);
}

function renderCallList() {
  const search = document.getElementById('call-search').value.toLowerCase();
  const noise = document.getElementById('noise-filter').value;
  const cluster = document.getElementById('cluster-filter').value;

  let filtered = allCalls;
  if (search) filtered = filtered.filter(c => c.call_id.toLowerCase().includes(search));
  if (noise) filtered = filtered.filter(c => c.noise_type === noise);
  if (cluster) filtered = filtered.filter(c => String(c.cluster) === cluster);

  document.getElementById('call-list').innerHTML = filtered.slice(0, 100).map(c => `
    <div class="call-item" data-call-id="${c.call_id}" onclick="selectCall('${c.call_id}')">
      <div class="call-item-id">${c.call_id}</div>
      <div class="call-item-meta">
        <span class="badge badge-noise">${c.noise_type || '?'}</span>
        <span>${parseFloat(c.f0_hz || 0).toFixed(1)} Hz</span>
      </div>
    </div>
  `).join('');
}

window.selectCall = function(callId) {
  const explorerNav = document.querySelector('[data-section="explorer"]');
  if (!document.getElementById('section-explorer')?.classList.contains('active')) explorerNav?.click();

  document.querySelectorAll('.call-item').forEach(el => el.classList.remove('active'));
  const item = document.querySelector(`[data-call-id="${callId}"]`);
  if (item) item.classList.add('active');

  const c = allCalls.find(x => x.call_id === callId);
  if (!c) return;

  const gain = parseFloat(c.snr_improvement_db || 0);
  document.getElementById('call-detail').innerHTML = `
    <div class="detail-header">
      <h2>${c.call_id}</h2>
      <span class="badge badge-noise">${c.noise_type || '—'}</span>
    </div>
    <div class="detail-metrics">
      <div class="detail-metric">
        <div class="detail-metric-label">F0</div>
        <div class="detail-metric-value">${parseFloat(c.f0_hz || 0).toFixed(1)} Hz</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">SNR Before</div>
        <div class="detail-metric-value">${parseFloat(c.snr_before_db || 0).toFixed(1)} dB</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">SNR After</div>
        <div class="detail-metric-value">${parseFloat(c.snr_after_db || 0).toFixed(1)} dB</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">SNR Gain</div>
        <div class="detail-metric-value" style="color:${gain > 0 ? 'var(--sage)' : 'var(--sienna)'}">
          ${gain > 0 ? '+' : ''}${gain.toFixed(1)} dB
        </div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Harmonics</div>
        <div class="detail-metric-value">${c.harmonics_present || '?'} / ${c.harmonics_possible || '?'}</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Multi-Elephant</div>
        <div class="detail-metric-value">${c.multi_elephant === 'True' ? 'Yes' : 'No'}</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Cluster</div>
        <div class="detail-metric-value">${c.cluster ?? '—'}</div>
      </div>
      <div class="detail-metric">
        <div class="detail-metric-label">Status</div>
        <div class="detail-metric-value"><span class="badge ${c.valid === 'True' ? 'badge-valid' : 'badge-invalid'}">${c.valid === 'True' ? 'Valid' : 'Invalid'}</span></div>
      </div>
    </div>
    <div class="detail-spectrogram">
      <img src="${resultsUrl(`/${c.call_id}_comparison.png`)}" alt="Spectrogram" onerror="this.parentElement.innerHTML='<p style=color:var(--text-muted)>No spectrogram available</p>'" />
    </div>
    <div class="detail-audio">
      <div class="detail-audio-label">Cleaned Audio</div>
      <audio controls preload="none" src="${resultsUrl(`/${c.call_id.replace(/_c\d+$/, '')}_clean.wav`)}"></audio>
    </div>
    ${c.multi_elephant === 'True' ? `
    <div class="detail-audio">
      <div class="detail-audio-label">Elephant B (separated)</div>
      <audio controls preload="none" src="${resultsUrl(`/${c.call_id.replace(/_c\d+$/, '')}_clean_b.wav`)}"></audio>
    </div>` : ''}
  `;
};

// ── Clusters ─────────────────────────────────────────────────────────
function renderClusters() {
  document.getElementById('clusters-grid').innerHTML = Object.entries(clusterSummaries).map(([id, s]) => `
    <div class="cluster-card">
      <div class="cluster-header">
        <span class="cluster-id">C${id}</span>
        <span class="cluster-count">${s.count} calls</span>
        <button class="cluster-network-btn" onclick="viewClusterInNetwork(${id})" title="Focus this cluster in the knowledge graph">
          Network →
        </button>
      </div>
      <div class="cluster-stats">
        <div class="cluster-stat"><div class="cluster-stat-label">Mean F0</div><div class="cluster-stat-value">${s.mean_f0_hz} Hz</div></div>
        <div class="cluster-stat"><div class="cluster-stat-label">Duration</div><div class="cluster-stat-value">${s.mean_dur_s} s</div></div>
        <div class="cluster-stat"><div class="cluster-stat-label">SNR</div><div class="cluster-stat-value">${s.mean_snr_db} dB</div></div>
        <div class="cluster-stat"><div class="cluster-stat-label">Harmonics</div><div class="cluster-stat-value">${s.mean_harmonics}</div></div>
      </div>
      <div class="cluster-calls">
        ${s.call_ids.slice(0, 10).map(cid => `<span class="cluster-call-tag" onclick="selectCall('${cid}')">${cid.split('_').pop()}</span>`).join('')}
        ${s.call_ids.length > 10 ? `<span class="cluster-call-tag">+${s.call_ids.length - 10}</span>` : ''}
      </div>
    </div>
  `).join('');

  // AI behavioral hypotheses
  const panel = document.getElementById('ai-hypotheses-panel');
  if (!panel) return;
  if (aiHypotheses) {
    panel.style.display = 'block';
    document.getElementById('ai-hypotheses-text').innerHTML = markdownToHtml(aiHypotheses);
  } else {
    panel.style.display = 'none';
  }
}

function markdownToHtml(md) {
  return md
    // Horizontal rules
    .replace(/^---$/gm, '<hr>')
    // H2
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    // H3
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    // Tables: header row
    .replace(/^\|(.+)\|$/gm, (_, row) => {
      const cells = row.split('|').map(c => c.trim());
      return '<table-row>' + cells.map(c => `<th>${c}</th>`).join('') + '</table-row>';
    })
    // Remove separator rows (|---|---|)
    .replace(/^<table-row>(<th>[-: ]+<\/th>)+<\/table-row>$/gm, '<table-sep>')
    // Wrap consecutive table rows in <table>
    .replace(/((?:<table-row>.+<\/table-row>\n?)+)/g, (block) => {
      const rows = block.trim().split('\n').filter(r => r && !r.includes('<table-sep>'));
      const [header, ...body] = rows;
      const thead = header.replace('<table-row>', '<thead><tr>').replace('</table-row>', '</tr></thead>').replace(/<th>/g, '<th>').replace(/<\/th>/g, '</th>');
      const tbody = body.map(r => r.replace('<table-row>', '<tr>').replace('</table-row>', '</tr>').replace(/<th>/g, '<td>').replace(/<\/th>/g, '</td>')).join('\n');
      return `<table>${thead}<tbody>${tbody}</tbody></table>`;
    })
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Italic
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Inline code
    .replace(/`(.+?)`/g, '<code>$1</code>')
    // Paragraphs: wrap non-tag lines
    .split('\n')
    .map(line => {
      if (!line.trim()) return '';
      if (/^<(h[23]|hr|table|thead|tbody|tr|th|td|table-sep)/.test(line)) return line;
      return `<p>${line}</p>`;
    })
    .join('\n')
    // Clean up empty table-sep markers
    .replace(/<table-sep>/g, '');
}

// ── Network ──────────────────────────────────────────────────────────
let networkMounted = false;
function renderNetwork() {
  if (networkMounted) return;
  networkMounted = true;
  // Threshold 0.90: all tribe_edges weights are ≥0.80 so 0.70 passes everything (1415 edges).
  // 0.90 drops to ~489 edges — still rich but ForceAtlas2 can handle it smoothly.
  mountNetworkGraph('react-network-root', tribeEdges, allCalls, clusterSummaries, 0.92, knowledgeBase);
}

// ── Cross-section navigation helpers ─────────────────────────────────
// Navigate to clusters section and scroll to a specific cluster card
window.navigateToCluster = function(clusterId) {
  document.querySelector('[data-section="clusters"]')?.click();
  navigateTo('#clusters');
  setTimeout(() => {
    const cards = document.querySelectorAll('.cluster-card');
    // cluster cards render in order 0,1,2... so index = clusterId
    if (cards[clusterId]) cards[clusterId].scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, 100);
};

// Navigate to network section and focus on a cluster hub node
window.viewClusterInNetwork = function(clusterId) {
  // Ensure network is mounted
  if (!networkMounted) renderNetwork();
  document.querySelector('[data-section="network"]')?.click();
  navigateTo('#network');
  setTimeout(() => {
    if (typeof window.focusNetworkCluster === 'function') {
      window.focusNetworkCluster(clusterId);
    }
  }, 400);
};

// ── Upload ───────────────────────────────────────────────────────────
let _uploadPollTimer = null;
let _uploadSectionReady = false;

function initUploadSection() {
  if (_uploadSectionReady) return;
  _uploadSectionReady = true;

  const dropzone = document.getElementById('upload-dropzone');
  const fileInput = document.getElementById('upload-file-input');

  if (!dropzone || !fileInput) return;

  // Click anywhere on zone to open picker
  dropzone.addEventListener('click', () => fileInput.click());

  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) submitFile(fileInput.files[0]);
  });

  // Drag-and-drop
  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('drag-over');
  });
  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) submitFile(file);
  });

  // Resume polling if pipeline is already running from a previous upload
  requestJson(apiUrl('/status'))
    .then(s => { if (s.status === 'running') startPolling(); })
    .catch(() => {});
}

function submitFile(file) {
  if (!file.name.toLowerCase().endsWith('.wav')) {
    showUploadStatus('error', 'Only .wav files are accepted.');
    return;
  }

  showUploadStatus('running', file.name);

  const reader = new FileReader();
  reader.onload = () => {
    const base64 = reader.result.split(',')[1];
    requestJson(apiUrl('/upload'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: file.name, data: base64 }),
    })
      .then(data => {
        if (data.error) showUploadStatus('error', data.error);
        else startPolling();
      })
      .catch(err => showUploadStatus('error', String(err)));
  };
  reader.readAsDataURL(file);
}

function showUploadStatus(status, filename) {
  const card = document.getElementById('upload-status-card');
  const badge = document.getElementById('upload-status-badge');
  const label = document.getElementById('upload-filename-label');

  if (!card) return;
  card.style.display = 'block';
  badge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
  badge.className = `upload-status-badge ${status}`;
  if (filename) label.textContent = filename;
}

function startPolling() {
  if (_uploadPollTimer) return;
  _uploadPollTimer = setInterval(pollStatus, 1500);
}

let _lastLogCount = 0;

function pollStatus() {
  requestJson(apiUrl('/status'))
    .then(data => {
      const badge = document.getElementById('upload-status-badge');
      const bar = document.getElementById('upload-progress-bar');
      const log = document.getElementById('upload-log');

      if (badge) {
        badge.textContent = data.status.charAt(0).toUpperCase() + data.status.slice(1);
        badge.className = `upload-status-badge ${data.status}`;
      }
      if (bar) {
        bar.style.width = `${data.progress || 0}%`;
        if (data.status === 'done') bar.classList.add('done');
        else bar.classList.remove('done');
      }
      if (log && data.logs) {
        const newLines = data.logs.slice(_lastLogCount);
        _lastLogCount = data.logs.length;
        newLines.forEach(line => {
          const span = document.createElement('span');
          span.className = line.startsWith('OK') || line.includes('done')
            ? 'log-ok'
            : line.startsWith('FAIL') || line.toLowerCase().includes('error')
              ? 'log-err'
              : 'log-info';
          span.textContent = line + '\n';
          log.appendChild(span);
        });
        if (newLines.length) log.scrollTop = log.scrollHeight;
      }

      if (data.status === 'done' || data.status === 'error') {
        clearInterval(_uploadPollTimer);
        _uploadPollTimer = null;
        _lastLogCount = 0;
        if (data.status === 'done') reloadAndRefresh();
      }
    })
    .catch(() => {});
}

async function reloadAndRefresh() {
  const ok = await loadData();
  if (!ok) return;
  networkMounted = false;   // force network re-mount on next visit
  renderDashboard();
  renderExplorer();
  renderClusters();
}

// ── Init ─────────────────────────────────────────────────────────────
async function init() {
  const ok = await loadData();
  if (!ok) return;
  renderDashboard();
  renderExplorer();
  renderClusters();
  
  // Boot router
  navigateTo(window.location.hash || '#dashboard');
}
init();
mountAuroraWaves('aurora-banner');
mountNavBar('app-nav-root');
mountHomepage('homepage-react-root');
