// Standalone Network Graph — extracted from GitNexus
// Drop into any React project

export { NetworkGraph } from './NetworkGraph';
export type { NetworkGraphHandle, NetworkGraphProps } from './NetworkGraph';

export { useSigma } from './useSigma';
export type { UseSigmaOptions, UseSigmaReturn } from './useSigma';

export { knowledgeGraphToGraphology, filterGraphByLabels, filterGraphByDepth, getNodesWithinHops } from './graph-adapter';

export {
  NODE_COLORS, NODE_SIZES, COMMUNITY_COLORS, getCommunityColor,
  DEFAULT_VISIBLE_LABELS, ALL_EDGE_TYPES, DEFAULT_VISIBLE_EDGES, EDGE_INFO,
} from './constants';

export type {
  NodeLabel, NodeProperties, RelationshipType,
  GraphNode, GraphRelationship, KnowledgeGraph,
  SigmaNodeAttributes, SigmaEdgeAttributes,
  AnimationType, NodeAnimation, EdgeType,
} from './types';
