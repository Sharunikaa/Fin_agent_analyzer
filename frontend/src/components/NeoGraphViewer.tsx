import { useEffect, useRef, useState } from 'react';
import Cytoscape from 'cytoscape';
import COSELayout from 'cytoscape-cose-bilkent';
import '../styles/NeoGraphViewer.css';

// Register layout
Cytoscape.use(COSELayout);

const C = {
  bg: '#0A0C10',
  surface: '#111318',
  card: '#161A22',
  border: '#1E2330',
  teal: '#00C9A7',
  blue: '#4F8EF7',
  amber: '#F5A623',
  red: '#F26D6D',
  green: '#4ADE80',
  purple: '#A78BFA',
  text: '#E8EAF0',
  textMid: '#8891A8',
  textDim: '#454E66',
};

interface Node {
  data: {
    id: string;
    label: string;
    type?: 'document' | 'company' | 'signal';
    year?: string;
    company?: string;
  };
}

interface Edge {
  data: {
    source: string;
    target: string;
    label?: string;
    type?: 'contains' | 'references' | 'related_to';
  };
}

interface NeoGraphProps {
  query: string;
  nodes: Node[];
  edges: Edge[];
  loading?: boolean;
}

export default function NeoGraphViewer({ query, nodes, edges, loading = false }: NeoGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<any>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [layoutName, setLayoutName] = useState<'cose' | 'grid' | 'circle'>('cose');
  const [statsText, setStatsText] = useState('');

  useEffect(() => {
    if (!containerRef.current || nodes.length === 0) return;

    const style = [
      {
        selector: 'node',
        style: {
          'background-color': function (ele: any) {
            const type = ele.data('type');
            if (type === 'company') return C.blue;
            if (type === 'signal') return C.amber;
            return C.teal;
          },
          'label': 'data(label)',
          'font-size': 11,
          'color': C.text,
          'text-valign': 'center',
          'text-halign': 'center',
          'width': 50,
          'height': 50,
          'border-width': 2,
          'border-color': C.border,
          'overlay-padding': 5,
        },
      },
      {
        selector: 'node:selected',
        style: {
          'background-color': C.green,
          'border-color': C.green,
          'border-width': 3,
        },
      },
      {
        selector: 'node:hover',
        style: {
          'background-color': C.purple,
          'box-shadow': `0 0 10px ${C.purple}`,
        },
      },
      {
        selector: 'edge',
        style: {
          'line-color': C.textDim,
          'target-arrow-color': C.textDim,
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'width': 2,
          'label': 'data(label)',
          'font-size': 9,
          'color': C.textMid,
        },
      },
      {
        selector: 'edge:selected',
        style: {
          'line-color': C.green,
          'target-arrow-color': C.green,
          'width': 3,
        },
      },
    ];

    const cy = Cytoscape({
      container: containerRef.current,
      elements: [...nodes, ...edges],
      style,
      layout: {
        name: layoutName === 'cose' ? 'cose' : layoutName,
        directed: true,
        spacingFactor: 1.2,
        animate: true,
        animationDuration: 500,
      },
      wheelSensitivity: 0.1,
      autoungrabify: false,
    });

    // Add node click listeners
    cy.on('tap', 'node', function (evt: any) {
      const node = evt.target;
      setSelectedNode(node.id());
    });

    cy.on('tap', function (evt: any) {
      if (evt.target === cy) {
        setSelectedNode(null);
      }
    });

    cyRef.current = cy;

    // Auto-fit on load
    cy.fit();

    // Stats
    const numCompanies = nodes.filter(n => n.data.type === 'company').length;
    const numDocuments = nodes.filter(n => n.data.type === 'document').length;
    const numSignals = nodes.filter(n => n.data.type === 'signal').length;
    const numRelationships = edges.length;

    setStatsText(
      `Companies: ${numCompanies} | Documents: ${numDocuments} | Signals: ${numSignals} | Relationships: ${numRelationships}`
    );

    return () => {
      cy.destroy();
    };
  }, [nodes, edges, layoutName]);

  const handleLayoutChange = (newLayout: 'cose' | 'grid' | 'circle') => {
    setLayoutName(newLayout);
  };

  const handleZoomFit = () => {
    if (cyRef.current) {
      cyRef.current.fit();
    }
  };

  const handleExportSVG = () => {
    if (cyRef.current) {
      const svgString = cyRef.current.svg({ bg: C.bg });
      const blob = new Blob([svgString], { type: 'image/svg+xml' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `neo4j-graph-${Date.now()}.svg`;
      a.click();
    }
  };

  const selectedData = selectedNode
    ? nodes.find(n => n.data.id === selectedNode)?.data
    : null;

  return (
    <div className="neo-graph-container" style={{ backgroundColor: C.bg }}>
      {/* Header */}
      <div className="neo-graph-header" style={{ borderBottomColor: C.border }}>
        <div className="neo-graph-title">
          <span style={{ color: C.teal }}>◯ Neo4j Graph</span>
          <span style={{ color: C.textMid, fontSize: '12px', marginLeft: '12px' }}>
            {query && `Query: "${query}"`}
          </span>
        </div>
        <div className="neo-graph-controls">
          <button
            onClick={() => handleLayoutChange('cose')}
            className={layoutName === 'cose' ? 'active' : ''}
            style={{
              backgroundColor: layoutName === 'cose' ? C.blue : C.surface,
              color: C.text,
            }}
          >
            Force
          </button>
          <button
            onClick={() => handleLayoutChange('grid')}
            className={layoutName === 'grid' ? 'active' : ''}
            style={{
              backgroundColor: layoutName === 'grid' ? C.blue : C.surface,
              color: C.text,
            }}
          >
            Grid
          </button>
          <button
            onClick={() => handleLayoutChange('circle')}
            className={layoutName === 'circle' ? 'active' : ''}
            style={{
              backgroundColor: layoutName === 'circle' ? C.blue : C.surface,
              color: C.text,
            }}
          >
            Circle
          </button>
          <button
            onClick={handleZoomFit}
            style={{ backgroundColor: C.surface, color: C.text }}
          >
            Fit
          </button>
          <button
            onClick={handleExportSVG}
            style={{ backgroundColor: C.amber, color: 'black' }}
          >
            Export SVG
          </button>
        </div>
      </div>

      {/* Graph Canvas */}
      <div
        ref={containerRef}
        className="neo-graph-canvas"
        style={{
          backgroundColor: C.surface,
          minHeight: '400px',
          borderColor: C.border,
        }}
      />

      {/* Stats */}
      <div className="neo-graph-stats" style={{ borderTopColor: C.border, color: C.textMid }}>
        {statsText || 'No data'}
      </div>

      {/* Selected Node Details */}
      {selectedData && (
        <div className="neo-graph-details" style={{ backgroundColor: C.card, borderColor: C.border }}>
          <div style={{ fontSize: '12px', color: C.teal, fontWeight: 'bold' }}>Selected Node</div>
          <div style={{ marginTop: '8px', fontSize: '12px', color: C.text }}>
            <div>
              <strong>Label:</strong> {selectedData.label}
            </div>
            {selectedData.company && (
              <div>
                <strong>Company:</strong> {selectedData.company}
              </div>
            )}
            {selectedData.year && (
              <div>
                <strong>Year:</strong> {selectedData.year}
              </div>
            )}
            {selectedData.type && (
              <div>
                <strong>Type:</strong> {selectedData.type}
              </div>
            )}
          </div>
        </div>
      )}

      {loading && (
        <div
          className="neo-graph-loading"
          style={{ backgroundColor: C.bg, color: C.teal }}
        >
          Loading graph data...
        </div>
      )}
    </div>
  );
}
