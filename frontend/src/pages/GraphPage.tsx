import React, { useState, useEffect, useMemo } from 'react';
import {
  forceSimulation,
  forceLink,
  forceManyBody,
  forceCenter,
  forceCollide,
  type SimulationNodeDatum,
  type SimulationLinkDatum,
} from 'd3-force';
import {
  Search,
  RefreshCw,
  X,
  Share2,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Navigation,
} from 'lucide-react';
import { useNeighborhood, useSync, formatErrorMessage } from '../api/client';
import type { GraphNode, NeighborhoodResponse } from '../api/schema';
import { DitheredOrb } from '../components/DitheredOrb';
import { useTheme } from '../context/ThemeContext';

interface SimNode extends SimulationNodeDatum {
  id: string;
  labels: string[];
  properties: Record<string, unknown>;
  color: string;
}

interface SimLink extends SimulationLinkDatum<SimNode> {
  source: SimNode | string;
  target: SimNode | string;
  type: string;
  properties?: Record<string, unknown>;
}

const ENTITY_COLORS: Record<string, string> = {
  Person: '#2563eb', // blue
  Team: '#7c3aed', // purple
  Module: '#0d9488', // teal
  File: '#64748b', // slate
  PullRequest: '#4f46e5', // indigo
  Issue: '#ea580c', // orange
  Comment: '#94a3b8', // gray
  Document: '#b45309', // amber
  Decision: '#db2777', // pink
};

function getNodeColor(labels: string[]): string {
  for (const label of labels) {
    if (ENTITY_COLORS[label]) return ENTITY_COLORS[label];
  }
  return '#4f46e5';
}

function normalizeLabels(labels?: string[] | string, label?: string): string[] {
  if (Array.isArray(labels)) return labels;
  if (typeof labels === 'string') return [labels];
  if (label) return [label];
  return ['Entity'];
}

export function GraphPage({ initialSample }: { initialSample?: NeighborhoodResponse }) {
  const [searchEntity, setSearchEntity] = useState('caleb-rivers');
  const [activeEntity, setActiveEntity] = useState('caleb-rivers');
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [showPath, setShowPath] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const { reducedMotion } = useTheme();

  const { data: neighborhoodData, isLoading, isError, error } = useNeighborhood(activeEntity);
  const syncMutation = useSync();

  const data = neighborhoodData || initialSample;

  // Limit to 80 nodes as required by prompt
  const nodesRaw = useMemo(() => {
    if (!data?.nodes) return [];
    return data.nodes.slice(0, 80);
  }, [data]);

  const nodeIdsSet = useMemo(() => new Set(nodesRaw.map((n) => n.id)), [nodesRaw]);

  const edgesRaw = useMemo(() => {
    if (!data?.edges) return [];
    return data.edges.filter((e) => nodeIdsSet.has(e.source) && nodeIdsSet.has(e.target));
  }, [data, nodeIdsSet]);

  // Calculate node degree (connection count) for node sizing
  const degreeMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const e of edgesRaw) {
      map.set(e.source, (map.get(e.source) || 0) + 1);
      map.set(e.target, (map.get(e.target) || 0) + 1);
    }
    return map;
  }, [edgesRaw]);

  const [simNodes, setSimNodes] = useState<SimNode[]>([]);
  const [simLinks, setSimLinks] = useState<SimLink[]>([]);

  // Auto zoom-to-fit helper
  const fitViewToNodes = (nodes: SimNode[]) => {
    if (nodes.length === 0) return;
    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    for (const n of nodes) {
      if (n.x !== undefined && n.y !== undefined) {
        if (n.x < minX) minX = n.x;
        if (n.x > maxX) maxX = n.x;
        if (n.y < minY) minY = n.y;
        if (n.y > maxY) maxY = n.y;
      }
    }
    const graphWidth = maxX - minX || 1;
    const graphHeight = maxY - minY || 1;
    const containerWidth = 900;
    const containerHeight = 600;
    const padding = 80;

    const scaleX = (containerWidth - padding * 2) / graphWidth;
    const scaleY = (containerHeight - padding * 2) / graphHeight;
    const newZoom = Math.min(Math.max(Math.min(scaleX, scaleY), 0.5), 1.2);

    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    const newPanX = (containerWidth / 2 - centerX) * newZoom;
    const newPanY = (containerHeight / 2 - centerY) * newZoom;

    setZoom(newZoom);
    setPan({ x: newPanX, y: newPanY });
  };

  // Simulation setup
  useEffect(() => {
    if (nodesRaw.length === 0) {
      setSimNodes([]);
      setSimLinks([]);
      return;
    }

    const width = 900;
    const height = 550;

    const nodes: SimNode[] = nodesRaw.map((n) => {
      const labels = normalizeLabels(n.labels, n.label);
      return {
        id: n.id,
        labels,
        properties: n.properties || {},
        color: getNodeColor(labels),
        x: width / 2 + (Math.random() - 0.5) * 400,
        y: height / 2 + (Math.random() - 0.5) * 300,
      };
    });

    const links: SimLink[] = edgesRaw.map((e) => ({
      source: e.source,
      target: e.target,
      type: e.type,
      properties: e.properties,
    }));

    const sim = forceSimulation<SimNode>(nodes)
      .force(
        'link',
        forceLink<SimNode, SimLink>(links)
          .id((d) => d.id)
          .distance(120),
      )
      .force('charge', forceManyBody().strength(-350))
      .force('center', forceCenter(width / 2, height / 2))
      .force('collide', forceCollide().radius(36));

    if (reducedMotion) {
      for (let i = 0; i < 150; ++i) sim.tick();
      setSimNodes([...nodes]);
      setSimLinks([...links]);
      fitViewToNodes(nodes);
      sim.stop();
    } else {
      let tickCount = 0;
      sim.on('tick', () => {
        setSimNodes([...nodes]);
        setSimLinks([...links]);
        tickCount++;
        if (tickCount === 60) {
          fitViewToNodes(nodes);
        }
      });
      sim.on('end', () => {
        fitViewToNodes(nodes);
      });

      return () => {
        sim.stop();
      };
    }
  }, [nodesRaw, edgesRaw, reducedMotion]);

  // Neighbors of selected node
  const neighborIds = useMemo(() => {
    if (!selectedNode) return new Set<string>();
    const set = new Set<string>();
    set.add(selectedNode.id);
    for (const edge of edgesRaw) {
      if (edge.source === selectedNode.id) set.add(edge.target);
      if (edge.target === selectedNode.id) set.add(edge.source);
    }
    return set;
  }, [selectedNode, edgesRaw]);

  // Pan and drag handling
  const handleMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('.interactive-node')) return;
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  // Connected path line points (from selected node to its first neighbor)
  const pathPoints = useMemo(() => {
    if (!selectedNode || !showPath) return null;
    const sourceNode = simNodes.find((n) => n.id === selectedNode.id);
    if (!sourceNode || sourceNode.x === undefined || sourceNode.y === undefined) return null;

    // Find first neighbor
    const neighborId = Array.from(neighborIds).find((id) => id !== selectedNode.id);
    if (!neighborId) return null;

    const targetNode = simNodes.find((n) => n.id === neighborId);
    if (!targetNode || targetNode.x === undefined || targetNode.y === undefined) return null;

    return {
      x1: sourceNode.x,
      y1: sourceNode.y,
      x2: targetNode.x,
      y2: targetNode.y,
    };
  }, [selectedNode, showPath, simNodes, neighborIds]);

  const isEmpty = !isLoading && (!data || data.node_count === 0 || simNodes.length === 0);

  return (
    <div className="w-full max-w-[1440px] mx-auto px-4 md:px-8 py-4 flex flex-col gap-4">
      {/* Top Search & Filter Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-surface-container rounded-xl p-3 border border-outline-variant/30 shadow-xs">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (searchEntity.trim()) {
              setActiveEntity(searchEntity.trim());
              setSelectedNode(null);
              setShowPath(false);
            }
          }}
          className="flex-1 flex items-center gap-2"
        >
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 text-outline pointer-events-none top-2.5" />
            <input
              type="text"
              id="graph-search-input"
              value={searchEntity}
              onChange={(e) => setSearchEntity(e.target.value)}
              placeholder="Query entity neighborhood (e.g. payments/refund.py, caleb-rivers, ADR-0004)..."
              className="w-full pl-9 pr-3 py-1.5 bg-surface-container-lowest text-on-surface text-xs font-mono rounded-lg border border-outline-variant/30 focus:outline-none focus:ring-1 focus:ring-primary-container"
            />
          </div>
          <button
            type="submit"
            id="graph-search-btn"
            className="px-4 py-1.5 rounded-lg bg-primary hover:bg-primary-hover text-white text-xs font-semibold shrink-0 cursor-pointer"
          >
            Explore
          </button>
        </form>

        {/* Zoom Controls */}
        <div className="flex items-center gap-1 shrink-0 self-end sm:self-auto">
          <button
            type="button"
            onClick={() => setZoom((z) => Math.min(z + 0.15, 2.5))}
            className="p-1.5 rounded-lg bg-surface-container-lowest hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface border border-outline-variant/30"
            title="Zoom In"
          >
            <ZoomIn size={14} />
          </button>
          <button
            type="button"
            onClick={() => setZoom((z) => Math.max(z - 0.15, 0.4))}
            className="p-1.5 rounded-lg bg-surface-container-lowest hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface border border-outline-variant/30"
            title="Zoom Out"
          >
            <ZoomOut size={14} />
          </button>
          <button
            type="button"
            onClick={() => {
              setZoom(1);
              setPan({ x: 0, y: 0 });
            }}
            className="p-1.5 rounded-lg bg-surface-container-lowest hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface border border-outline-variant/30"
            title="Reset View"
          >
            <Maximize2 size={14} />
          </button>
        </div>
      </div>

      {/* Error state */}
      {isError && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
          <p className="font-semibold">{error?.code || 'ERROR'}</p>
          <p className="text-xs mt-1 text-red-300">
            {formatErrorMessage(error?.code || 'INVALID_REQUEST', error?.message)}
          </p>
        </div>
      )}

      {/* Main Canvas Container */}
      <div
        className="relative w-full h-[620px] rounded-2xl bg-surface-container-lowest border border-outline-variant/30 overflow-hidden shadow-inner select-none cursor-grab active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
      >
        {/* Background Dot Grid */}
        <div
          className="absolute inset-0 opacity-[0.06] pointer-events-none"
          style={{
            backgroundImage: 'radial-gradient(var(--color-on-surface) 1px, transparent 1px)',
            backgroundSize: '20px 20px',
          }}
        />

        {/* Empty State */}
        {isEmpty && (
          <div className="absolute inset-0 z-30 flex flex-col items-center justify-center p-6 text-center bg-surface/85 backdrop-blur-md">
            <div className="mb-4">
              <DitheredOrb size={64} className="shadow-2xl" />
            </div>
            <h2 className="text-base md:text-lg font-semibold text-on-surface mb-1">
              No graph neighborhood loaded
            </h2>
            <p className="text-xs text-on-surface-variant max-w-sm mb-6 leading-relaxed">
              No entities found for &quot;{activeEntity}&quot; or repository has not been indexed yet.
            </p>
            <button
              type="button"
              id="graph-empty-sync-btn"
              disabled={syncMutation.isPending}
              onClick={() => syncMutation.mutate()}
              className="px-5 py-2.5 rounded-xl bg-primary hover:bg-primary-hover text-white text-xs font-semibold shadow-lg transition-all flex items-center gap-2 cursor-pointer disabled:opacity-50"
            >
              <RefreshCw size={14} className={syncMutation.isPending ? 'animate-spin' : ''} />
              <span>{syncMutation.isPending ? 'Syncing...' : 'Run sync'}</span>
            </button>
            {syncMutation.isSuccess && (
              <span className="mt-3 text-xs text-secondary font-mono">
                Sync completed! {syncMutation.data.mutations_applied ?? 0} mutations applied.
              </span>
            )}
          </div>
        )}

        {/* Graph Canvas SVG */}
        {!isEmpty && (
          <svg
            id="neighborhood-canvas-svg"
            className="w-full h-full"
            style={{
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
              transformOrigin: 'center center',
              transition: isDragging ? 'none' : 'transform 0.1s ease-out',
            }}
          >
            {/* Edges */}
            <g className="edges">
              {simLinks.map((link, i) => {
                const s = link.source as SimNode;
                const t = link.target as SimNode;
                if (!s || !t || s.x === undefined || s.y === undefined || t.x === undefined || t.y === undefined) {
                  return null;
                }
                const isHighlighted =
                  selectedNode &&
                  (s.id === selectedNode.id || t.id === selectedNode.id);
                const isDimmed = selectedNode && !isHighlighted;
                const midX = (s.x + t.x) / 2;
                const midY = (s.y + t.y) / 2;

                return (
                  <g key={i}>
                    <line
                      x1={s.x}
                      y1={s.y}
                      x2={t.x}
                      y2={t.y}
                      stroke={isHighlighted ? '#6366f1' : 'var(--color-outline-variant)'}
                      strokeWidth={isHighlighted ? 2.5 : 1}
                      strokeOpacity={isDimmed ? 0.15 : isHighlighted ? 0.95 : 0.45}
                      strokeDasharray={link.type === 'MEMBER_OF' ? '4 2' : undefined}
                    />
                    <text
                      x={midX}
                      y={midY - 3}
                      textAnchor="middle"
                      fill={isHighlighted ? '#818cf8' : 'var(--color-on-surface-variant)'}
                      fontSize="8"
                      fontFamily="JetBrains Mono, monospace"
                      className="pointer-events-none font-semibold select-none"
                      opacity={isDimmed ? 0.15 : 0.85}
                    >
                      {link.type}
                    </text>
                  </g>
                );
              })}
            </g>

            {/* Animated SVG Path Line (over 600ms) */}
            {pathPoints && (
              <g className="animated-path">
                <line
                  x1={pathPoints.x1}
                  y1={pathPoints.y1}
                  x2={pathPoints.x2}
                  y2={pathPoints.y2}
                  stroke="#38bdf8"
                  strokeWidth="3.5"
                  strokeLinecap="round"
                  style={{
                    strokeDasharray: '300',
                    strokeDashoffset: '300',
                    animation: reducedMotion ? 'none' : 'drawPathLine 600ms ease-out forwards',
                  }}
                />
              </g>
            )}

            {/* Nodes */}
            {/* Nodes */}
            <g className="nodes">
              {simNodes.map((node) => {
                if (node.x === undefined || node.y === undefined) return null;
                const isSelected = selectedNode?.id === node.id;
                const isNeighbor = neighborIds.has(node.id);
                const isDimmed = selectedNode && !isNeighbor;
                const deg = degreeMap.get(node.id) || 1;
                const baseR = Math.max(9, Math.min(8 + deg * 2, 20));
                const r = isSelected ? baseR + 5 : isNeighbor ? baseR + 2 : baseR;
                const displayLabel =
                  (node.properties?.login && typeof node.properties.login === 'string')
                    ? `@${node.properties.login}`
                    : (node.properties?.path && typeof node.properties.path === 'string')
                    ? node.properties.path
                    : node.properties?.number !== undefined
                    ? `PR #${node.properties.number}`
                    : node.id;

                return (
                  <g
                    key={node.id}
                    className="interactive-node cursor-pointer"
                    transform={`translate(${node.x}, ${node.y})`}
                    onClick={() => {
                      const original = nodesRaw.find((n) => n.id === node.id);
                      if (original) {
                        setSelectedNode(original);
                        setShowPath(false);
                      }
                    }}
                    opacity={isDimmed ? 0.25 : 1}
                  >
                    {/* Outer ring on selected */}
                    {isSelected && (
                      <circle
                        r={r + 6}
                        fill="none"
                        stroke={node.color}
                        strokeWidth="2"
                        strokeDasharray="4 2"
                      />
                    )}
                    {/* Node circle sized by degree */}
                    <circle
                      r={r}
                      fill={node.color}
                      stroke="var(--color-surface-container-lowest)"
                      strokeWidth="2"
                      style={{
                        filter: isSelected ? `drop-shadow(0 0 10px ${node.color})` : undefined,
                        transition: 'r 0.2s, filter 0.2s',
                      }}
                    />
                    {/* Label text */}
                    <text
                      y={r + 11}
                      textAnchor="middle"
                      fill="var(--color-on-surface)"
                      fontSize="9"
                      fontFamily="JetBrains Mono, monospace"
                      className="pointer-events-none font-medium"
                      style={{ textShadow: '0 1px 3px rgba(0,0,0,0.8)' }}
                    >
                      {displayLabel.length > 20 ? `${displayLabel.slice(0, 18)}…` : displayLabel}
                    </text>
                  </g>
                );
              })}
            </g>
          </svg>
        )}

        {/* Floating Entity Types Legend */}
        {!isEmpty && (
          <div className="absolute top-3 right-3 z-20 p-2.5 rounded-xl bg-surface-container/90 backdrop-blur-md border border-outline-variant/30 shadow-lg text-[10px] font-mono flex flex-col gap-1.5 pointer-events-auto">
            <span className="text-on-surface-variant uppercase tracking-wider font-semibold text-[9px]">
              Entity Types
            </span>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1">
              {Object.entries(ENTITY_COLORS).map(([type, color]) => (
                <div key={type} className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
                  <span className="text-on-surface">{type}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Selected Node Inspector Card (using fields from response ONLY) */}
        {selectedNode && (
          <div
            id="node-inspector-card"
            className="absolute bottom-4 left-4 z-20 w-80 max-w-[calc(100%-2rem)] rounded-2xl bg-surface-container/95 backdrop-blur-xl border border-outline-variant/40 p-4 shadow-2xl text-on-surface flex flex-col gap-3"
          >
            <div className="flex items-start justify-between pb-2 border-b border-outline-variant/20">
              <div className="flex items-center gap-2">
                <span
                  className="w-3 h-3 rounded-full shrink-0"
                  style={{
                    backgroundColor: getNodeColor(normalizeLabels(selectedNode.labels, selectedNode.label)),
                  }}
                />
                <h3 className="font-mono text-xs font-bold text-on-surface truncate">
                  {selectedNode.id}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => {
                  setSelectedNode(null);
                  setShowPath(false);
                }}
                className="p-1 rounded-lg text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high cursor-pointer"
                title="Dismiss"
              >
                <X size={14} />
              </button>
            </div>

            {/* Labels from response */}
            <div className="flex flex-wrap gap-1">
              {normalizeLabels(selectedNode.labels, selectedNode.label).map((l, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 rounded-full bg-surface-container-high border border-outline-variant/30 font-mono text-[10px] uppercase font-semibold text-primary"
                >
                  {l}
                </span>
              ))}
            </div>

            {/* Properties (only from response) */}
            <div className="max-h-40 overflow-y-auto space-y-1 font-mono text-[11px] py-1">
              {selectedNode.properties && Object.keys(selectedNode.properties).length > 0 ? (
                Object.entries(selectedNode.properties).map(([k, v]) => (
                  <div
                    key={k}
                    className="flex items-center justify-between py-1 px-2 rounded bg-surface-container-lowest border border-outline-variant/10"
                  >
                    <span className="text-on-surface-variant">{k}</span>
                    <span className="text-on-surface font-semibold truncate max-w-[140px]">
                      {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                    </span>
                  </div>
                ))
              ) : (
                <span className="text-on-surface-variant italic">No extra properties</span>
              )}
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2 pt-2 border-t border-outline-variant/20">
              <button
                type="button"
                id="show-path-btn"
                onClick={() => setShowPath(!showPath)}
                className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
                  showPath
                    ? 'bg-primary-container text-on-primary-container shadow-sm'
                    : 'bg-surface-container-high hover:bg-surface-bright text-on-surface'
                }`}
              >
                <Navigation size={13} />
                <span>{showPath ? 'Hide path' : 'Show path'}</span>
              </button>
              <button
                type="button"
                id="expand-node-btn"
                onClick={() => {
                  setActiveEntity(selectedNode.id);
                  setSearchEntity(selectedNode.id);
                }}
                className="py-1.5 px-3 rounded-lg bg-surface-container-high hover:bg-surface-bright text-on-surface text-xs font-semibold flex items-center justify-center gap-1.5 transition-all cursor-pointer"
                title="Expand 2-hop neighborhood"
              >
                <Share2 size={13} />
                <span>Expand</span>
              </button>
            </div>
          </div>
        )}

        {/* Global Keyframe for 600ms SVG line animation */}
        <style>{`
          @keyframes drawPathLine {
            from {
              stroke-dashoffset: 300;
            }
            to {
              stroke-dashoffset: 0;
            }
          }
        `}</style>
      </div>
    </div>
  );
}
