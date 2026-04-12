import React from 'react';
import { createRoot } from 'react-dom/client';
import { NetworkGraph } from './network-graph/NetworkGraph';

class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { hasError: false, error: null }; }
  static getDerivedStateFromError(error) { return { hasError: true, error }; }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '20px', color: 'red', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
          <h2>React Render Crash:</h2>
          {this.state.error?.stack || this.state.error?.message || "Unknown error"}
        </div>
      );
    }
    return this.props.children;
  }
}

function GeometryConstraint({ children }) {
  const [ready, setReady] = React.useState(false);
  const ref = React.useRef(null);
  React.useEffect(() => {
    const checkDimensions = () => {
      if (ref.current && ref.current.clientWidth > 0 && ref.current.clientHeight > 0) {
        setReady(true);
      } else {
        requestAnimationFrame(checkDimensions);
      }
    };
    checkDimensions();
  }, []);
  return <div ref={ref} style={{ width: '100%', height: '100%', position: 'relative' }}>{ready ? children : null}</div>;
}

let rootInstance = null;

export function mountNetworkGraph(containerId, tribeEdges, allCalls, clusterSummaries, threshold) {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (!rootInstance) {
    rootInstance = createRoot(container);
  }

  // Filter edges based on threshold
  const filteredEdges = tribeEdges.filter(e => parseFloat(e.weight) >= threshold);
  
  // Track unique node IDs from filtered edges
  const activeNodeIds = new Set();
  filteredEdges.forEach(e => {
    activeNodeIds.add(e.source);
    activeNodeIds.add(e.target);
  });

  // Construct KnowledgeGraph format
  const relationships = filteredEdges.map((e, idx) => ({
    id: `e_${idx}`,
    sourceId: e.source,
    targetId: e.target,
    type: 'SIMILAR_TO',
    confidence: parseFloat(e.weight)
  }));

  const nodes = [...activeNodeIds].map(nodeId => {
    const callData = allCalls.find(c => c.call_id === nodeId) || {};
    const cluster = callData.cluster || "0";
    return {
      id: nodeId,
      label: 'ElephantCall', // Matches updated Sigma constants
      properties: {
        name: `Call ${nodeId}`,
        filePath: '',
      }
    };
  });
  
  // Create community mapping for cluster coloring based on Tribal Palette
  const communityMemberships = new Map();
  nodes.forEach(n => {
    const callData = allCalls.find(c => c.call_id === n.id) || {};
    communityMemberships.set(n.id, parseInt(callData.cluster || "0"));
  });

  try {
    const graphData = {
      nodes,
      relationships,
      nodeCount: nodes.length,
      relationshipCount: relationships.length
    };

    if (nodes.length === 0) {
      rootInstance.render(
        <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--linen)', fontFamily: 'var(--font-mono)' }}>
          <p style={{ opacity: 0.5, marginBottom: 8 }}>Network Error</p>
          <p>No connections found above the {threshold} minimum threshold.</p>
          <p style={{ opacity: 0.5, fontSize: 12, marginTop: 8 }}>(Fetched {tribeEdges.length} total edges from CSV)</p>
        </div>
      );
      return;
    }

    rootInstance.render(
      <ErrorBoundary>
        <GeometryConstraint>
          <NetworkGraph 
            graph={graphData} 
            communityMemberships={communityMemberships}
            visibleEdgeTypes={['SIMILAR_TO']} // Ensure it renders our custom edge type
          />
        </GeometryConstraint>
      </ErrorBoundary>
    );
  } catch (err) {
    container.innerHTML = `<div style="padding: 20px; color: red; font-family: monospace; white-space: pre-wrap;"><h1>React Mount Crash:</h1>${err.stack || err.message}</div>`;
  }
}
