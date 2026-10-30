import cytoscape, { type Core } from 'cytoscape';
import fcose from 'cytoscape-fcose';
import { useEffect, useMemo, useRef, useState } from 'react';
import type { GraphNodeData, GraphPayload, ToolSpec } from '../types';
import {
  CloseIcon,
  DownloadIcon,
  FocusIcon,
  PivotIcon,
  RefreshIcon,
  SearchIcon,
  ZoomInIcon,
  ZoomOutIcon,
} from './Icons';

const LIGHT_COLORS: Record<string, string> = {
  person: '#23201b',
  email: '#b8432b',
  phone: '#8a5c12',
  username: '#2f6b63',
  account: '#2f6b63',
  domain: '#3f5d78',
  url: '#3f5d78',
  ip: '#6a4a72',
  org: '#6b6357',
  breach: '#b8432b',
  document: '#6b6357',
  image: '#6b6357',
  location: '#8a5c12',
  nik: '#8f2f1d',
  npwp: '#8f2f1d',
  nim: '#3f5d78',
  btc: '#8a5c12',
  mac: '#3f5d78',
};

const DARK_COLORS: Record<string, string> = {
  person: '#e4dbc9',
  email: '#e07154',
  phone: '#d7aa60',
  username: '#86c1b5',
  account: '#86c1b5',
  domain: '#93b4d0',
  url: '#93b4d0',
  ip: '#c7a1cf',
  org: '#b0a693',
  breach: '#e07154',
  document: '#b0a693',
  image: '#b0a693',
  location: '#d7aa60',
  nik: '#f09a80',
  npwp: '#f09a80',
  nim: '#93b4d0',
  btc: '#d7aa60',
  mac: '#93b4d0',
};

const FALLBACK_LIGHT = '#7b7264';
const FALLBACK_DARK = '#b0a693';

try {
  cytoscape.use(fcose);
} catch {
  // the extension is already registered during hot reload
}

function colorFor(type: string, theme: 'light' | 'dark'): string {
  if (theme === 'dark') {
    return DARK_COLORS[type] ?? FALLBACK_DARK;
  }
  return LIGHT_COLORS[type] ?? FALLBACK_LIGHT;
}

function truncate(value: string, limit = 44): string {
  return value.length > limit ? `${value.slice(0, limit - 1)}…` : value;
}

function buildStyle(theme: 'light' | 'dark', showEdgeLabels: boolean): cytoscape.StylesheetStyle[] {
  const ink = theme === 'dark' ? '#f0e8d8' : '#23201b';
  const paper = theme === 'dark' ? '#1b1916' : '#f2ebdd';
  const line = theme === 'dark' ? '#61584a' : '#a99c85';
  const accent = theme === 'dark' ? '#e07154' : '#b8432b';
  return [
    {
      selector: 'node',
      style: {
        'background-color': 'data(color)',
        'border-width': 1.5,
        'border-color': paper,
        width: 26,
        height: 26,
        label: 'data(label)',
        color: ink,
        'font-family': 'Segoe UI, system-ui, sans-serif',
        'font-size': 10,
        'text-wrap': 'wrap',
        'text-max-width': '110px',
        'text-valign': 'bottom',
        'text-margin-y': 5,
        'text-outline-width': 2,
        'text-outline-color': paper,
        'min-zoomed-font-size': 9,
        'overlay-opacity': 0,
      },
    },
    {
      selector: 'node:selected',
      style: {
        'border-width': 4,
        'border-color': accent,
      },
    },
    {
      selector: 'node[status = "confirmed"]',
      style: {
        'border-width': 3,
        'border-style': 'double',
      },
    },
    {
      selector: 'edge',
      style: {
        width: 'mapData(confidence, 0, 1, 1, 2.6)',
        'line-color': line,
        'target-arrow-color': line,
        'target-arrow-shape': 'triangle',
        'arrow-scale': 0.8,
        'curve-style': 'bezier',
        opacity: 0.85,
        label: showEdgeLabels ? 'data(relation)' : '',
        'font-size': 8,
        color: theme === 'dark' ? '#c9bfad' : '#5a5348',
        'text-rotation': 'autorotate',
        'text-background-color': paper,
        'text-background-opacity': 0.82,
        'text-background-padding': '2px',
        'text-margin-y': -2,
        'min-zoomed-font-size': 7,
      },
    },
    {
      selector: 'edge:selected',
      style: {
        'line-color': accent,
        'target-arrow-color': accent,
        opacity: 1,
      },
    },
  ];
}

function runLayout(cy: Core) {
  const layout = cy.layout({
    name: 'fcose',
    quality: 'default',
    animate: true,
    animationDuration: 420,
    randomize: true,
    fit: true,
    padding: 48,
    nodeRepulsion: 7000,
    idealEdgeLength: 110,
    edgeElasticity: 0.35,
    gravity: 0.25,
    numIter: 2500,
  } as unknown as cytoscape.LayoutOptions);
  layout.run();
}

function attributeValue(value: unknown): string {
  if (value === null || value === undefined) {
    return '';
  }
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return '[object]';
    }
  }
  return String(value);
}

interface GraphViewProps {
  data: GraphPayload | null;
  tools: ToolSpec[];
  loading: boolean;
  running: boolean;
  theme: 'light' | 'dark';
  focusRequest: { id: string; token: number } | null;
  onPivot: (entityId: string, toolId: string) => void;
  onRefresh: () => void;
}

export function GraphView({ data, tools, loading, running, theme, focusRequest, onPivot, onRefresh }: GraphViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showEdgeLabels, setShowEdgeLabels] = useState(true);
  const [query, setQuery] = useState('');
  const [activeTypes, setActiveTypes] = useState<string[]>([]);

  const elements = useMemo(() => {
    if (!data) {
      return [];
    }
    const nodes = data.nodes.map((node) => ({
      group: 'nodes' as const,
      data: {
        ...node.data,
        label: truncate(node.data.label),
        color: colorFor(node.data.type, theme),
      },
    }));
    const edges = data.edges.map((edge) => ({
      group: 'edges' as const,
      data: edge.data,
    }));
    return [...nodes, ...edges];
  }, [data, theme]);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }
    const cy = cytoscape({
      container: containerRef.current,
      elements: [],
      style: buildStyle(theme, showEdgeLabels),
      minZoom: 0.25,
      maxZoom: 2.6,
      boxSelectionEnabled: false,
    });
    cy.on('tap', 'node', (event) => {
      setSelectedId(event.target.id());
    });
    cy.on('tap', (event) => {
      if (event.target === cy) {
        setSelectedId(null);
      }
    });
    cy.on('mouseover', 'node', () => {
      if (containerRef.current) {
        containerRef.current.style.cursor = 'pointer';
      }
    });
    cy.on('mouseout', 'node', () => {
      if (containerRef.current) {
        containerRef.current.style.cursor = 'default';
      }
    });
    cyRef.current = cy;
    let fitTimer = 0;
    const observer = new ResizeObserver(() => {
      cy.resize();
      window.clearTimeout(fitTimer);
      fitTimer = window.setTimeout(() => {
        if (!cy.destroyed()) {
          cy.fit(undefined, 40);
        }
      }, 140);
    });
    observer.observe(containerRef.current);
    return () => {
      window.clearTimeout(fitTimer);
      observer.disconnect();
      cy.destroy();
      cyRef.current = null;
    };
    // the graph instance is created once; style and data are updated by their own effects
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const cy = cyRef.current;
    if (cy) {
      cy.style(buildStyle(theme, showEdgeLabels));
    }
  }, [theme, showEdgeLabels]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) {
      return;
    }
    const previousNodes = cy.nodes().length;
    const ids = new Set(elements.map((element) => element.data.id));
    cy.batch(() => {
      cy.elements()
        .filter((element) => !ids.has(element.id()))
        .remove();
      elements.forEach((element) => {
        const existing = cy.getElementById(element.data.id);
        if (existing.empty()) {
          cy.add(element);
        } else {
          existing.data(element.data);
        }
      });
    });
    const nextNodes = cy.nodes().length;
    if (nextNodes > 0 && (nextNodes !== previousNodes || previousNodes === 0)) {
      runLayout(cy);
    }
  }, [elements]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) {
      return;
    }
    const term = query.trim().toLowerCase();
    const typeSet = new Set(activeTypes);
    cy.batch(() => {
      cy.nodes().forEach((node) => {
        const haystack = `${node.data('label')} ${node.data('normalized')}`.toLowerCase();
        const matchesText = !term || haystack.includes(term);
        const matchesType = typeSet.size === 0 || typeSet.has(String(node.data('type')));
        node.style('display', matchesText && matchesType ? 'element' : 'none');
      });
      cy.edges().forEach((edge) => {
        const sourceVisible = edge.source().style('display') !== 'none';
        const targetVisible = edge.target().style('display') !== 'none';
        edge.style('display', sourceVisible && targetVisible ? 'element' : 'none');
      });
    });
  }, [query, activeTypes, elements]);

  useEffect(() => {
    if (!focusRequest) {
      return;
    }
    const cy = cyRef.current;
    if (!cy) {
      return;
    }
    const node = cy.getElementById(focusRequest.id);
    if (!node.empty()) {
      setSelectedId(focusRequest.id);
      cy.animate({
        fit: { eles: node.closedNeighborhood(), padding: 70 },
        duration: 420,
      });
    }
  }, [focusRequest]);

  useEffect(() => {
    if (!data) {
      return;
    }
    const exists = data.nodes.some((node) => node.data.id === selectedId);
    if (!exists) {
      setSelectedId(null);
    }
  }, [data, selectedId]);

  const selectedNode: GraphNodeData | null =
    data?.nodes.find((node) => node.data.id === selectedId)?.data ?? null;
  const selectedTools = selectedNode ? tools.filter((tool) => tool.inputs.includes(selectedNode.type)) : [];
  const presentTypes = useMemo(() => {
    const types = new Set(data?.nodes.map((node) => node.data.type) ?? []);
    return Array.from(types).sort();
  }, [data]);

  const visibleCount = useMemo(() => {
    if (!data) {
      return 0;
    }
    const term = query.trim().toLowerCase();
    const typeSet = new Set(activeTypes);
    return data.nodes.filter((node) => {
      const haystack = `${node.data.label} ${node.data.normalized}`.toLowerCase();
      const matchesText = !term || haystack.includes(term);
      const matchesType = typeSet.size === 0 || typeSet.has(node.data.type);
      return matchesText && matchesType;
    }).length;
  }, [data, query, activeTypes]);

  function toggleType(type: string) {
    setActiveTypes((current) =>
      current.includes(type) ? current.filter((item) => item !== type) : [...current, type],
    );
  }

  function zoom(factor: number) {
    const cy = cyRef.current;
    if (!cy) {
      return;
    }
    cy.zoom({
      level: cy.zoom() * factor,
      renderedPosition: { x: cy.width() / 2, y: cy.height() / 2 },
    });
  }

  function exportPng() {
    const cy = cyRef.current;
    if (!cy) {
      return;
    }
    const uri = cy.png({
      full: true,
      scale: 2,
      bg: theme === 'dark' ? '#1b1916' : '#f2ebdd',
    });
    const link = document.createElement('a');
    link.href = uri;
    link.download = 'berkas-graph.png';
    link.click();
  }

  const hasNodes = (data?.nodes.length ?? 0) > 0;

  return (
    <section className="graph-pane" aria-labelledby="graph-title">
      <div className="pane-head">
        <div>
          <span className="file-tab">Peta bukti</span>
          <h2 id="graph-title">Koneksi entity</h2>
        </div>
        <div className="pane-actions">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setShowEdgeLabels((current) => !current)}
            aria-pressed={showEdgeLabels}
          >
            {showEdgeLabels ? 'Sembunyikan label' : 'Tampilkan label'}
          </button>
          <button type="button" className="btn btn-ghost btn-icon" aria-label="Muat ulang graph" onClick={onRefresh}>
            <RefreshIcon />
          </button>
        </div>
      </div>

      <div className="graph-filterbar">
        <label className="graph-search">
          <SearchIcon size={15} />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Cari entity, domain, atau username"
            aria-label="Cari entity di graph"
          />
          {query && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setQuery('')}>
              Hapus
            </button>
          )}
        </label>
        {presentTypes.length > 0 && (
          <div className="graph-type-filters" role="group" aria-label="Filter tipe entity">
            <button
              type="button"
              className={activeTypes.length === 0 ? 'active' : ''}
              aria-pressed={activeTypes.length === 0}
              onClick={() => setActiveTypes([])}
            >
              Semua
            </button>
            {presentTypes.map((type) => (
              <button
                type="button"
                key={type}
                className={activeTypes.includes(type) ? 'active' : ''}
                aria-pressed={activeTypes.includes(type)}
                onClick={() => toggleType(type)}
              >
                {type}
              </button>
            ))}
          </div>
        )}
        <span className="graph-filter-count mono" aria-live="polite">
          {visibleCount} / {data?.nodes.length ?? 0} entity
        </span>
      </div>

      <div className="graph-stage">
        <div className="graph-canvas" ref={containerRef} aria-label="Graph koneksi entity" />

        {loading && !data && (
          <div className="graph-state" aria-live="polite">
            <div>
              <strong>Memuat peta bukti...</strong>
              Graph dan temuan sedang dibaca dari kasus.
            </div>
          </div>
        )}

        {!loading && !hasNodes && (
          <div className="graph-state" aria-live="polite">
            <div>
              <strong>Belum ada entity di peta</strong>
              Tambahkan entity dari panel kiri atau unggah file bukti. Setiap hasil tool akan muncul di sini.
            </div>
          </div>
        )}

        <div className="graph-controls" role="group" aria-label="Kontrol graph">
          <button type="button" className="btn btn-ghost btn-icon" aria-label="Perbesar graph" onClick={() => zoom(1.2)}>
            <ZoomInIcon size={16} />
          </button>
          <button type="button" className="btn btn-ghost btn-icon" aria-label="Perkecil graph" onClick={() => zoom(0.84)}>
            <ZoomOutIcon size={16} />
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-icon"
            aria-label="Sesuaikan graph ke layar"
            onClick={() => cyRef.current?.fit(undefined, 50)}
          >
            <FocusIcon size={16} />
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-icon"
            aria-label="Susun ulang graph"
            onClick={() => {
              const cy = cyRef.current;
              if (cy) {
                runLayout(cy);
              }
            }}
          >
            <RefreshIcon size={16} />
          </button>
          <button type="button" className="btn btn-ghost btn-icon" aria-label="Unduh graph sebagai PNG" onClick={exportPng}>
            <DownloadIcon size={16} />
          </button>
        </div>

        {presentTypes.length > 0 && (
          <div className="graph-legend" aria-label="Legenda tipe entity">
            {presentTypes.map((type) => (
              <span className="legend-item" key={type}>
                <span className="legend-swatch" style={{ background: colorFor(type, theme) }} />
                {type}
              </span>
            ))}
          </div>
        )}

        {selectedNode && (
          <div className="node-detail" aria-live="polite">
            <div className="node-detail-head">
              <span className="node-detail-type">{selectedNode.type}</span>
              <button
                type="button"
                className="btn btn-ghost btn-icon btn-sm"
                aria-label="Tutup detail entity"
                onClick={() => setSelectedId(null)}
              >
                <CloseIcon size={15} />
              </button>
            </div>
            <h3>{selectedNode.label}</h3>
            <dl>
              <div>
                <dt>Keyakinan</dt>
                <dd className="mono">{Math.round(selectedNode.confidence * 100)}%</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>{selectedNode.status}</dd>
              </div>
            </dl>
            {Object.keys(selectedNode.attributes ?? {}).length > 0 && (
              <>
                <h4>Atribut</h4>
                <dl>
                  {Object.entries(selectedNode.attributes)
                    .slice(0, 6)
                    .map(([key, value]) => (
                      <div key={key}>
                        <dt>{key}</dt>
                        <dd title={attributeValue(value)}>{truncate(attributeValue(value), 48)}</dd>
                      </div>
                    ))}
                </dl>
              </>
            )}
            <h4>Pivot dari entity ini</h4>
            {selectedTools.length === 0 ? (
              <p className="muted">Belum ada tool yang cocok untuk tipe ini.</p>
            ) : (
              <div className="pivot-list">
                {selectedTools.map((tool) => (
                  <button
                    type="button"
                    key={tool.id}
                    disabled={running || (Boolean(tool.requires_key) && !tool.configured)}
                    title={
                      tool.requires_key && !tool.configured
                        ? `Butuh ${tool.requires_key}`
                        : tool.description
                    }
                    onClick={() => onPivot(selectedNode.id, tool.id)}
                  >
                    <PivotIcon size={14} />
                    <span>
                      <strong>{tool.label}</strong>
                      <small>{tool.id}</small>
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
}
