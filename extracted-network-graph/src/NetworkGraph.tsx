/**
 * Standalone NetworkGraph component.
 *
 * Drop-in React component that renders an interactive network graph
 * using Sigma.js + Graphology with ForceAtlas2 layout.
 *
 * Usage:
 *   <NetworkGraph
 *     graph={myKnowledgeGraph}
 *     onNodeClick={(node) => console.log('clicked', node)}
 *   />
 */
import { useEffect, useCallback, useMemo, useState, forwardRef, useImperativeHandle } from 'react';
import { useSigma } from './useSigma';
import { knowledgeGraphToGraphology, filterGraphByDepth } from './graph-adapter';
import { DEFAULT_VISIBLE_LABELS, DEFAULT_VISIBLE_EDGES } from './constants';
import type {
  KnowledgeGraph,
  GraphNode,
  NodeLabel,
  EdgeType,
  SigmaNodeAttributes,
  SigmaEdgeAttributes,
  NodeAnimation,
} from './types';
import Graph from 'graphology';

export interface NetworkGraphHandle {
  focusNode: (nodeId: string) => void;
}

export interface NetworkGraphProps {
  /** The graph data to render */
  graph: KnowledgeGraph | null;
  /** Callback when a node is clicked */
  onNodeClick?: (node: GraphNode) => void;
  /** Callback when the background is clicked (deselect) */
  onDeselect?: () => void;
  /** Which node labels to show (default: all structural + code types) */
  visibleLabels?: NodeLabel[];
  /** Which edge types to show (default: all) */
  visibleEdgeTypes?: EdgeType[];
  /** Max depth filter from selected node (null = no filter) */
  depthFilter?: number | null;
  /** Node IDs to highlight (e.g. search results) */
  highlightedNodeIds?: Set<string>;
  /** Node IDs for blast-radius highlighting (red) */
  blastRadiusNodeIds?: Set<string>;
  /** Animated nodes map */
  animatedNodes?: Map<string, NodeAnimation>;
  /** Community memberships: nodeId -> communityIndex */
  communityMemberships?: Map<string, number>;
  /** CSS class for the container */
  className?: string;
}

export const NetworkGraph = forwardRef<NetworkGraphHandle, NetworkGraphProps>((props, ref) => {
  const {
    graph: inputGraph,
    onNodeClick,
    onDeselect,
    visibleLabels = DEFAULT_VISIBLE_LABELS,
    visibleEdgeTypes = DEFAULT_VISIBLE_EDGES,
    depthFilter = null,
    highlightedNodeIds = new Set<string>(),
    blastRadiusNodeIds = new Set<string>(),
    animatedNodes = new Map<string, NodeAnimation>(),
    communityMemberships,
    className = '',
  } = props;

  const [hoveredNodeName, setHoveredNodeName] = useState<string | null>(null);
  const [selectedAppNode, setSelectedAppNode] = useState<GraphNode | null>(null);

  const nodeById = useMemo(() => {
    if (!inputGraph) return new Map<string, GraphNode>();
    return new Map(inputGraph.nodes.map((n) => [n.id, n]));
  }, [inputGraph]);

  const handleNodeClick = useCallback(
    (nodeId: string) => {
      const node = nodeById.get(nodeId);
      if (node) {
        setSelectedAppNode(node);
        onNodeClick?.(node);
      }
    },
    [nodeById, onNodeClick],
  );

  const handleNodeHover = useCallback(
    (nodeId: string | null) => {
      if (!nodeId) { setHoveredNodeName(null); return; }
      const node = nodeById.get(nodeId);
      setHoveredNodeName(node ? node.properties.name : null);
    },
    [nodeById],
  );

  const handleStageClick = useCallback(() => {
    setSelectedAppNode(null);
    onDeselect?.();
  }, [onDeselect]);

  const {
    containerRef,
    sigmaRef,
    setGraph: setSigmaGraph,
    zoomIn,
    zoomOut,
    resetZoom,
    focusNode,
    isLayoutRunning,
    startLayout,
    stopLayout,
    selectedNode: sigmaSelectedNode,
    setSelectedNode: setSigmaSelectedNode,
  } = useSigma({
    onNodeClick: handleNodeClick,
    onNodeHover: handleNodeHover,
    onStageClick: handleStageClick,
    highlightedNodeIds,
    blastRadiusNodeIds,
    animatedNodes,
    visibleEdgeTypes,
  });

  useImperativeHandle(ref, () => ({
    focusNode: (nodeId: string) => {
      const node = nodeById.get(nodeId);
      if (node) { setSelectedAppNode(node); onNodeClick?.(node); }
      focusNode(nodeId);
    },
  }), [focusNode, nodeById, onNodeClick]);

  // Build graphology graph when data changes
  useEffect(() => {
    if (!inputGraph) return;

    // Auto-detect community memberships from MEMBER_OF relationships if not provided
    let memberships = communityMemberships;
    if (!memberships) {
      memberships = new Map<string, number>();
      inputGraph.relationships.forEach((rel) => {
        if (rel.type === 'MEMBER_OF') {
          const numericPart = rel.targetId.replace('comm_', '');
          const idx = /^\d+$/.test(numericPart) ? parseInt(numericPart, 10) : 0;
          memberships!.set(rel.sourceId, idx);
        }
      });
    }

    const sigmaGraph = knowledgeGraphToGraphology(inputGraph, memberships);
    setSigmaGraph(sigmaGraph);
  }, [inputGraph, communityMemberships, setSigmaGraph]);

  // Update node visibility on filter changes
  useEffect(() => {
    const sigma = sigmaRef.current;
    if (!sigma) return;
    const sigmaGraph = sigma.getGraph() as Graph<SigmaNodeAttributes, SigmaEdgeAttributes>;
    if (sigmaGraph.order === 0) return;
    filterGraphByDepth(sigmaGraph, selectedAppNode?.id || null, depthFilter, visibleLabels);
    sigma.refresh();
  }, [visibleLabels, depthFilter, selectedAppNode]);

  // Sync selection
  useEffect(() => {
    setSigmaSelectedNode(selectedAppNode ? selectedAppNode.id : null);
  }, [selectedAppNode, setSigmaSelectedNode]);

  const handleClearSelection = useCallback(() => {
    setSelectedAppNode(null);
    setSigmaSelectedNode(null);
    resetZoom();
  }, [setSigmaSelectedNode, resetZoom]);

  return (
    <div className={`network-graph-root ${className}`} style={{ position: 'relative', width: '100%', height: '100%', background: '#06060a' }}>
      {/* Background gradient */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', background: 'radial-gradient(circle at 50% 50%, rgba(124, 58, 237, 0.03) 0%, transparent 70%), linear-gradient(to bottom, #06060a, #0a0a10)' }} />

      {/* Sigma container */}
      <div ref={containerRef} style={{ width: '100%', height: '100%', cursor: 'grab' }} />

      {/* Hovered node tooltip */}
      {hoveredNodeName && !sigmaSelectedNode && (
        <div style={{ position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 20, background: 'rgba(20,20,30,0.95)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, padding: '6px 12px', fontFamily: 'JetBrains Mono, monospace', fontSize: 13, color: '#e4e4ed', pointerEvents: 'none' }}>
          {hoveredNodeName}
        </div>
      )}

      {/* Selection info */}
      {sigmaSelectedNode && selectedAppNode && (
        <div style={{ position: 'absolute', top: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 20, display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(99,102,241,0.2)', border: '1px solid rgba(99,102,241,0.3)', borderRadius: 12, padding: '8px 16px', backdropFilter: 'blur(4px)' }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#6366f1', animation: 'pulse 2s infinite' }} />
          <span style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: 13, color: '#e4e4ed' }}>
            {selectedAppNode.properties.name}
          </span>
          <span style={{ fontSize: 11, color: '#9ca3af' }}>({selectedAppNode.label})</span>
          <button onClick={handleClearSelection} style={{ marginLeft: 8, padding: '2px 8px', fontSize: 11, color: '#9ca3af', background: 'transparent', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
            Clear
          </button>
        </div>
      )}

      {/* Controls */}
      <div style={{ position: 'absolute', right: 16, bottom: 16, zIndex: 10, display: 'flex', flexDirection: 'column', gap: 4 }}>
        {[
          { label: '+', onClick: zoomIn, title: 'Zoom In' },
          { label: '\u2212', onClick: zoomOut, title: 'Zoom Out' },
          { label: '\u2922', onClick: resetZoom, title: 'Fit' },
        ].map((btn) => (
          <button key={btn.title} onClick={btn.onClick} title={btn.title} style={{ width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 6, border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(20,20,30,0.9)', color: '#9ca3af', fontSize: 18, cursor: 'pointer' }}>
            {btn.label}
          </button>
        ))}

        <div style={{ height: 1, margin: '4px 0', background: 'rgba(255,255,255,0.1)' }} />

        <button onClick={isLayoutRunning ? stopLayout : startLayout} title={isLayoutRunning ? 'Stop Layout' : 'Run Layout'} style={{ width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 6, border: `1px solid ${isLayoutRunning ? '#6366f1' : 'rgba(255,255,255,0.1)'}`, background: isLayoutRunning ? '#6366f1' : 'rgba(20,20,30,0.9)', color: isLayoutRunning ? '#fff' : '#9ca3af', fontSize: 14, cursor: 'pointer' }}>
          {isLayoutRunning ? '\u23F8' : '\u25B6'}
        </button>
      </div>

      {/* Layout running indicator */}
      {isLayoutRunning && (
        <div style={{ position: 'absolute', bottom: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 10, display: 'flex', alignItems: 'center', gap: 8, background: 'rgba(16,185,129,0.2)', border: '1px solid rgba(16,185,129,0.3)', borderRadius: 999, padding: '6px 12px', backdropFilter: 'blur(4px)' }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#34d399', animation: 'ping 1s infinite' }} />
          <span style={{ fontSize: 12, fontWeight: 500, color: '#34d399' }}>Layout optimizing...</span>
        </div>
      )}
    </div>
  );
});

NetworkGraph.displayName = 'NetworkGraph';
