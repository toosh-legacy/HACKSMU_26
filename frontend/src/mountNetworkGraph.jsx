import React, { useRef, useEffect } from 'react';
import { createRoot } from 'react-dom/client';
import { NetworkGraph } from './network-graph/NetworkGraph';

class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { hasError: false, error: null }; }
  static getDerivedStateFromError(error) { return { hasError: true, error }; }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '20px', color: '#ef4444', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
          <h2>Graph Render Error:</h2>
          <pre style={{ fontSize: '0.75rem' }}>{this.state.error?.stack || this.state.error?.message || 'Unknown error'}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

let _graphRef = null;
let _sigmaResizeFn = null;

window.focusNetworkCluster = (clusterId) => {
  if (_graphRef?.current) _graphRef.current.focusNode(`cluster_${clusterId}`);
};

// Called from main.js after the network section becomes visible.
window.resizeNetworkGraph = () => {
  if (_sigmaResizeFn) _sigmaResizeFn();
};

function NetworkGraphWrapper({ graphData, communityMemberships }) {
  const ref = useRef(null);

  useEffect(() => {
    _graphRef = ref;
    return () => { _graphRef = null; };
  }, []);

  // Expose sigma resize so the section-visibility handler can trigger it.
  useEffect(() => {
    _sigmaResizeFn = () => {
      if (ref.current?.resizeSigma) ref.current.resizeSigma();
    };
    return () => { _sigmaResizeFn = null; };
  }, []);

  return (
    <NetworkGraph
      ref={ref}
      graph={graphData}
      communityMemberships={communityMemberships}
      visibleEdgeTypes={['SIMILAR_TO', 'BELONGS_TO_CLUSTER', 'ASSOCIATED_WITH']}
    />
  );
}

let rootInstance = null;

export function mountNetworkGraph(containerId, tribeEdges, allCalls, clusterSummaries, threshold, knowledgeBase) {
  const container = document.getElementById(containerId);
  if (!container) return;
  if (!rootInstance) rootInstance = createRoot(container);

  // cluster lookup: call_id → cluster string (normalize '4.0' → '4' to match JSON keys)
  const callCluster = new Map();
  allCalls.forEach(c => {
    if (c.cluster !== undefined && c.cluster !== '') {
      callCluster.set(c.call_id, String(parseInt(c.cluster, 10)));
    }
  });

  // ── Tribe edges filtered by threshold ───────────────────────────
  const filteredEdges = tribeEdges.filter(e => parseFloat(e.weight) >= threshold);

  // ── All node IDs: tribe-connected + every valid clustered call ───
  const activeNodeIds = new Set();
  filteredEdges.forEach(e => { activeNodeIds.add(e.source); activeNodeIds.add(e.target); });
  allCalls.forEach(c => {
    if (c.cluster !== undefined && c.cluster !== '' && c.valid !== 'False') {
      activeNodeIds.add(c.call_id);
    }
  });

  if (activeNodeIds.size === 0) {
    rootInstance.render(
      <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--linen)', fontFamily: 'var(--font-mono)' }}>
        <p style={{ opacity: 0.5 }}>No data — run the pipeline first.</p>
      </div>
    );
    return;
  }

  // ── Degree for node sizing ───────────────────────────────────────
  const nodeDegree = new Map();
  filteredEdges.forEach(e => {
    nodeDegree.set(e.source, (nodeDegree.get(e.source) || 0) + 1);
    nodeDegree.set(e.target, (nodeDegree.get(e.target) || 0) + 1);
  });
  const degrees = [...activeNodeIds].map(id => nodeDegree.get(id) || 1);
  const minDeg = Math.min(...degrees);
  const maxDeg = Math.max(...degrees);
  const degRange = maxDeg - minDeg || 1;

  // ── Call nodes ───────────────────────────────────────────────────
  const callNodes = [...activeNodeIds].map(id => ({
    id,
    label: 'ElephantCall',
    properties: {
      name: id,
      filePath: '',
      nodeSize: 5 + ((nodeDegree.get(id) || 1) - minDeg) / degRange * 12,
    },
  }));

  // ── Cluster hub nodes ────────────────────────────────────────────
  const clusterHubNodes = Object.entries(clusterSummaries).map(([id, s]) => ({
    id: `cluster_${id}`,
    label: 'ClusterHub',
    properties: {
      name: `C${id} · ${s.count} calls · ${s.mean_f0_hz}Hz`,
      filePath: '',
      nodeSize: Math.max(18, 12 + Math.sqrt(s.count || 1) * 2),
      clusterId: parseInt(id),
    },
  }));

  const nodes = [...callNodes, ...clusterHubNodes];

  // ── Community memberships for coloring ──────────────────────────
  const communityMemberships = new Map();
  callNodes.forEach(n => {
    communityMemberships.set(n.id, parseInt(callCluster.get(n.id) || '0'));
  });
  clusterHubNodes.forEach(n => {
    communityMemberships.set(n.id, n.properties.clusterId);
  });

  // ── SIMILAR_TO edges (tribe similarity) ─────────────────────────
  const similarEdges = filteredEdges.map((e, idx) => ({
    id: `e_${idx}`,
    sourceId: e.source,
    targetId: e.target,
    type: 'SIMILAR_TO',
    confidence: parseFloat(e.weight),
  }));

  // ── BELONGS_TO_CLUSTER — every call → its hub ────────────────────
  const belongsEdges = [];
  callNodes.forEach((n, idx) => {
    const cid = callCluster.get(n.id);
    if (cid !== undefined && clusterSummaries[cid] !== undefined) {
      belongsEdges.push({
        id: `be_${idx}`,
        sourceId: n.id,
        targetId: `cluster_${cid}`,
        type: 'BELONGS_TO_CLUSTER',
        confidence: 1.0,
      });
    }
  });

  // ── ASSOCIATED_WITH from knowledge base ──────────────────────────
  const associatedEdges = [];
  if (knowledgeBase?.association_links) {
    knowledgeBase.association_links.forEach((link, idx) => {
      if (activeNodeIds.has(link.source) && activeNodeIds.has(link.target)) {
        associatedEdges.push({
          id: `ae_${idx}`,
          sourceId: link.source,
          targetId: link.target,
          type: 'ASSOCIATED_WITH',
          confidence: link.combined_score,
        });
      }
    });
  }

  const relationships = [...similarEdges, ...belongsEdges, ...associatedEdges];

  rootInstance.render(
    <ErrorBoundary>
      <NetworkGraphWrapper
        graphData={{ nodes, relationships, nodeCount: nodes.length, relationshipCount: relationships.length }}
        communityMemberships={communityMemberships}
      />
    </ErrorBoundary>
  );
}
