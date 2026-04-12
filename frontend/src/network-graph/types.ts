/**
 * Standalone types for the network graph visualization.
 * Extracted from GitNexus — no external dependencies.
 */

// --- Node types ---

export type NodeLabel =
  | 'Project'
  | 'Package'
  | 'Module'
  | 'Folder'
  | 'File'
  | 'Class'
  | 'Function'
  | 'Method'
  | 'Variable'
  | 'Interface'
  | 'Enum'
  | 'Decorator'
  | 'Import'
  | 'Type'
  | 'CodeElement'
  | 'Community'
  | 'Process'
  | 'Struct'
  | 'Macro'
  | 'Typedef'
  | 'Union'
  | 'Namespace'
  | 'Trait'
  | 'Impl'
  | 'TypeAlias'
  | 'Const'
  | 'Static'
  | 'Property'
  | 'Record'
  | 'Delegate'
  | 'Annotation'
  | 'Constructor'
  | 'Template'
  | 'Section'
  | 'Route'
  | 'Tool'
  | 'ElephantCall';

export type NodeProperties = {
  name: string;
  filePath: string;
  startLine?: number;
  endLine?: number;
  [key: string]: unknown;
};

export type RelationshipType =
  | 'CONTAINS'
  | 'CALLS'
  | 'IMPORTS'
  | 'DEFINES'
  | 'EXTENDS'
  | 'IMPLEMENTS'
  | 'MEMBER_OF'
  | string; // allow custom relationship types

export interface GraphNode {
  id: string;
  label: NodeLabel;
  properties: NodeProperties;
}

export interface GraphRelationship {
  id: string;
  sourceId: string;
  targetId: string;
  type: RelationshipType;
  confidence?: number;
  reason?: string;
}

export interface KnowledgeGraph {
  nodes: GraphNode[];
  relationships: GraphRelationship[];
  nodeCount: number;
  relationshipCount: number;
}

// --- Sigma attribute types ---

export interface SigmaNodeAttributes {
  x: number;
  y: number;
  size: number;
  color: string;
  label: string;
  nodeType: NodeLabel;
  filePath: string;
  startLine?: number;
  endLine?: number;
  hidden?: boolean;
  zIndex?: number;
  highlighted?: boolean;
  mass?: number;
  community?: number;
  communityColor?: string;
}

export interface SigmaEdgeAttributes {
  size: number;
  color: string;
  relationType: string;
  type?: string;
  curvature?: number;
  zIndex?: number;
}

// --- Animation types ---

export type AnimationType = 'pulse' | 'ripple' | 'glow';

export interface NodeAnimation {
  type: AnimationType;
  startTime: number;
  duration: number;
}

// --- Edge types ---

export type EdgeType = 'CONTAINS' | 'DEFINES' | 'IMPORTS' | 'CALLS' | 'EXTENDS' | 'IMPLEMENTS' | 'SIMILAR_TO';
