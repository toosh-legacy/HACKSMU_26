# Network Graph

Interactive network graph visualization extracted from GitNexus.  
Sigma.js (WebGL) + Graphology + ForceAtlas2 layout.

## Install dependencies

```bash
npm install sigma graphology graphology-layout-forceatlas2 graphology-layout-noverlap @sigma/edge-curve
```

## Quick start

```tsx
import { NetworkGraph } from './src';
import type { KnowledgeGraph } from './src';

const myGraph: KnowledgeGraph = {
  nodes: [
    { id: '1', label: 'Function', properties: { name: 'main', filePath: 'src/index.ts' } },
    { id: '2', label: 'Function', properties: { name: 'helper', filePath: 'src/utils.ts' } },
    { id: '3', label: 'Class',    properties: { name: 'UserService', filePath: 'src/user.ts' } },
  ],
  relationships: [
    { id: 'e1', sourceId: '1', targetId: '2', type: 'CALLS' },
    { id: 'e2', sourceId: '1', targetId: '3', type: 'CALLS' },
  ],
  nodeCount: 3,
  relationshipCount: 2,
};

function App() {
  return (
    <div style={{ width: '100vw', height: '100vh' }}>
      <NetworkGraph
        graph={myGraph}
        onNodeClick={(node) => console.log('clicked', node)}
      />
    </div>
  );
}
```

## Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `graph` | `KnowledgeGraph \| null` | — | Graph data |
| `onNodeClick` | `(node) => void` | — | Node click handler |
| `onDeselect` | `() => void` | — | Background click |
| `visibleLabels` | `NodeLabel[]` | structural+code | Filter node types |
| `visibleEdgeTypes` | `EdgeType[]` | all | Filter edge types |
| `depthFilter` | `number \| null` | null | Max hops from selected |
| `highlightedNodeIds` | `Set<string>` | empty | Cyan highlight |
| `blastRadiusNodeIds` | `Set<string>` | empty | Red highlight |
| `animatedNodes` | `Map<string, NodeAnimation>` | empty | Pulse/ripple/glow |
| `communityMemberships` | `Map<string, number>` | auto-detect | Cluster coloring |
| `className` | `string` | — | CSS class |

## Low-level usage

Use `useSigma` hook directly for full control:

```tsx
import { useSigma, knowledgeGraphToGraphology } from './src';

function MyGraph({ data }) {
  const { containerRef, setGraph, zoomIn, zoomOut, focusNode } = useSigma({
    onNodeClick: (id) => console.log(id),
  });

  useEffect(() => {
    const g = knowledgeGraphToGraphology(data);
    setGraph(g);
  }, [data]);

  return <div ref={containerRef} style={{ width: '100%', height: '100%' }} />;
}
```

## Files

```
src/
  index.ts          — barrel export
  types.ts          — all TypeScript types (self-contained, no external deps)
  constants.ts      — colors, sizes, palettes
  graph-adapter.ts  — KnowledgeGraph → Graphology conversion + positioning
  useSigma.ts       — React hook: Sigma lifecycle, layout, reducers
  NetworkGraph.tsx   — drop-in React component
```
