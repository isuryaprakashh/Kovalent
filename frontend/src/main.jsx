import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, AlertTriangle, ArrowLeft, Box, Cpu, Database, Network, RefreshCw, Server } from 'lucide-react';
import * as d3 from 'd3';
import './styles.css';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000';

const fallbackSnapshot = {
  generated_at: new Date().toISOString(),
  source: 'demo',
  metrics: [
    {
      namespace: 'payments',
      pod: 'checkout-api-7d9f',
      service: 'checkout-api',
      cpu_millicores: 820,
      cpu_limit_millicores: 1000,
      memory_mb: 610,
      memory_limit_mb: 1024,
      network_rx_kbps: 920,
      network_tx_kbps: 1340,
      pvc_name: null,
      pvc_latency_ms: null,
      pvc_iops: null,
      error_rate_per_minute: 4,
      restart_count: 0,
      observed_at: new Date().toISOString()
    },
    {
      namespace: 'payments',
      pod: 'orders-db-0',
      service: 'orders-db',
      cpu_millicores: 710,
      cpu_limit_millicores: 1500,
      memory_mb: 1840,
      memory_limit_mb: 2048,
      network_rx_kbps: 560,
      network_tx_kbps: 460,
      pvc_name: 'orders-data',
      pvc_latency_ms: 165,
      pvc_iops: 920,
      error_rate_per_minute: 1,
      restart_count: 0,
      observed_at: new Date().toISOString()
    },
    {
      namespace: 'payments',
      pod: 'frontend-5c6b',
      service: 'frontend',
      cpu_millicores: 210,
      cpu_limit_millicores: 500,
      memory_mb: 212,
      memory_limit_mb: 512,
      network_rx_kbps: 1480,
      network_tx_kbps: 730,
      pvc_name: null,
      pvc_latency_ms: null,
      pvc_iops: null,
      error_rate_per_minute: 18,
      restart_count: 1,
      observed_at: new Date().toISOString()
    }
  ],
  findings: [],
  insights: [
    {
      status: 'WARNING',
      event: 'Cascading Latency Detected',
      root_cause: "PVC orders-data on orders-db is experiencing I/O wait saturation.",
      correlation: 'Frontend errors coincide with high storage latency in its downstream order database.',
      recommendation: 'Check storage provisioner IOPS limits or migrate the database pod to faster disk.',
      affected_services: ['frontend', 'checkout-api', 'orders-db'],
      evidence: []
    }
  ],
  topology: {
    nodes: [
      { id: 'svc:frontend', label: 'frontend', namespace: 'payments', kind: 'service', status: 'WARNING' },
      { id: 'svc:checkout-api', label: 'checkout-api', namespace: 'payments', kind: 'service', status: 'WARNING' },
      { id: 'svc:orders-db', label: 'orders-db', namespace: 'payments', kind: 'service', status: 'WARNING' },
      { id: 'pod:frontend-5c6b', label: 'frontend-5c6b', namespace: 'payments', kind: 'pod', status: 'WARNING' },
      { id: 'pod:checkout-api-7d9f', label: 'checkout-api-7d9f', namespace: 'payments', kind: 'pod', status: 'WARNING' },
      { id: 'pod:orders-db-0', label: 'orders-db-0', namespace: 'payments', kind: 'pod', status: 'WARNING' },
      { id: 'pvc:orders-data', label: 'orders-data', namespace: 'payments', kind: 'pvc', status: 'WARNING' }
    ],
    edges: [
      { source: 'svc:frontend', target: 'svc:checkout-api', relationship: 'calls' },
      { source: 'svc:checkout-api', target: 'svc:orders-db', relationship: 'calls' },
      { source: 'svc:frontend', target: 'pod:frontend-5c6b', relationship: 'owns' },
      { source: 'svc:checkout-api', target: 'pod:checkout-api-7d9f', relationship: 'owns' },
      { source: 'svc:orders-db', target: 'pod:orders-db-0', relationship: 'owns' },
      { source: 'pod:orders-db-0', target: 'pvc:orders-data', relationship: 'mounts' }
    ]
  }
};

function App() {
  const [snapshot, setSnapshot] = useState(fallbackSnapshot);
  const [loading, setLoading] = useState(false);
  const [apiState, setApiState] = useState('demo');
  const [apiError, setApiError] = useState(null);
  const [selectedNodeId, setSelectedNodeId] = useState(null);

  const selectedMetric = useMemo(() => {
    if (!selectedNodeId) return null;
    const [kind, id] = selectedNodeId.split(':');
    if (kind === 'pod') return snapshot.metrics.find(m => m.pod === id);
    if (kind === 'service') return snapshot.metrics.find(m => m.service === id);
    return null;
  }, [selectedNodeId, snapshot.metrics]);

  const loadSnapshot = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/snapshot`);
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      const nextSnapshot = await response.json();
      setSnapshot(nextSnapshot);
      setApiState(nextSnapshot.source ?? 'live');
      setApiError(null);
    } catch {
      setSnapshot(fallbackSnapshot);
      setApiState('demo');
      setApiError('API unavailable. Showing browser demo data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSnapshot();
    const timer = window.setInterval(loadSnapshot, 30000);
    return () => window.clearInterval(timer);
  }, []);

  const summary = useMemo(() => buildSummary(snapshot), [snapshot]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Kubernetes intelligence</p>
          <h1>Kovalent</h1>
        </div>
        <div className="topbar-actions">
          <span className="timestamp">Updated {formatTime(snapshot.generated_at)}</span>
          <span className={`api-pill ${apiState}`}>{sourceLabel(apiState)}</span>
          <button type="button" onClick={loadSnapshot} disabled={loading} aria-label="Refresh snapshot">
            <RefreshCw size={18} className={loading ? 'spin' : ''} />
          </button>
        </div>
      </header>

      {apiError ? <div className="status-banner" role="status">{apiError}</div> : null}

      <section className="summary-grid" aria-label="Cluster summary">
        <MetricTile icon={<Server />} label="Services" value={summary.services} tone="neutral" />
        <MetricTile icon={<Box />} label="Pods" value={snapshot.metrics.length} tone="neutral" />
        <MetricTile icon={<AlertTriangle />} label="Insights" value={snapshot.insights.length} tone="warning" />
        <MetricTile icon={<Database />} label="PVC latency" value={`${summary.maxPvcLatency.toFixed(1)} ms`} tone="danger" />
      </section>

      <section className="main-grid">
        <div className="panel topology-panel">
          <PanelHeader icon={<Network />} title="Dependency topology" />
          <TopologyGraph
            topology={snapshot.topology}
            selectedId={selectedNodeId}
            onSelect={setSelectedNodeId}
          />
        </div>
        <div className="panel side-panel">
          {selectedMetric ? (
            <NodeDetails metric={selectedMetric} onClear={() => setSelectedNodeId(null)} />
          ) : (
            <>
              <PanelHeader icon={<Activity />} title="Root-cause insights" />
              <InsightList insights={snapshot.insights} />
            </>
          )}
        </div>
      </section>

      <section className="panel">
        <PanelHeader icon={<Cpu />} title="Resource signals" />
        <ResourceTable metrics={snapshot.metrics} />
      </section>
    </main>
  );
}

function MetricTile({ icon, label, value, tone }) {
  return (
    <article className={`metric-tile ${tone}`}>
      <div className="tile-icon">{React.cloneElement(icon, { size: 20 })}</div>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
      </div>
    </article>
  );
}

function NodeDetails({ metric, onClear }) {
  return (
    <div className="node-details">
      <div className="details-header">
        <button className="back-btn" onClick={onClear} aria-label="Back to insights">
          <ArrowLeft size={18} />
        </button>
        <h3>{metric.pod}</h3>
      </div>
      <div className="details-body">
        <div className="detail-row">
          <span>Service</span>
          <strong>{metric.service}</strong>
        </div>
        <div className="detail-row">
          <span>Namespace</span>
          <strong>{metric.namespace}</strong>
        </div>
        <hr />
        <div className="detail-stat">
          <p>CPU Utilization</p>
          <Bar value={metric.cpu_millicores / metric.cpu_limit_millicores} label={`${metric.cpu_millicores.toFixed(1)}m`} />
        </div>
        <div className="detail-stat">
          <p>Memory Usage</p>
          <Bar value={metric.memory_mb / metric.memory_limit_mb} label={`${metric.memory_mb.toFixed(1)} MB`} />
        </div>
        <div className="detail-stat">
          <p>Error Rate</p>
          <div className="error-pill">{metric.error_rate_per_minute} errors/min</div>
        </div>
      </div>
    </div>
  );
}

function PanelHeader({ icon, title }) {
  return (
    <div className="panel-header">
      {React.cloneElement(icon, { size: 18 })}
      <h2>{title}</h2>
    </div>
  );
}

function TopologyGraph({ topology, selectedId, onSelect }) {
  const svgRef = React.useRef(null);
  const containerRef = React.useRef(null);
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });

  useEffect(() => {
    const nodes = topology.nodes.map(n => ({ ...n }));
    const links = topology.edges.map(e => ({ ...e }));
    setGraphData({ nodes, links });
  }, [topology]);

  useEffect(() => {
    if (!graphData.nodes.length || !svgRef.current) return;

    const width = containerRef.current.clientWidth;
    const height = 480;
    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    svg.selectAll('*').remove();

    const defs = svg.append('defs');
    defs.append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 0 10 10')
      .attr('refX', 32)
      .attr('refY', 5)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto-start-reverse')
      .append('path')
      .attr('d', 'M 0 0 L 10 5 L 0 10 z')
      .attr('fill', '#96a4ab');

    const g = svg.append('g');

    const zoom = d3.zoom()
      .scaleExtent([0.5, 3])
      .on('zoom', (event) => g.attr('transform', event.transform));
    svg.call(zoom);

    const simulation = d3.forceSimulation(graphData.nodes)
      .force('link', d3.forceLink(graphData.links).id(d => d.id).distance(d => d.relationship === 'calls' ? 140 : 90))
      .force('charge', d3.forceManyBody().strength(-400))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('x', d3.forceX(width / 2).strength(0.05))
      .force('y', d3.forceY(height / 2).strength(0.05))
      .force('collision', d3.forceCollide().radius(50));

    const link = g.append('g')
      .selectAll('line')
      .data(graphData.links)
      .join('line')
      .attr('class', d => `edge ${d.relationship}`)
      .attr('marker-end', d => d.relationship === 'calls' ? 'url(#arrow)' : '');

    const node = g.append('g')
      .selectAll('.node-group')
      .data(graphData.nodes)
      .join('g')
      .attr('class', d => `node-group node ${d.status.toLowerCase()} ${d.id === selectedId ? 'selected' : ''}`)
      .on('click', (event, d) => onSelect(d.id))
      .call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulation.alphaTarget(0.3).restart();
          d.fx = d.x;
          d.fy = d.y;
        })
        .on('drag', (event, d) => {
          d.fx = event.x;
          d.fy = event.y;
        })
        .on('end', (event, d) => {
          if (!event.active) simulation.alphaTarget(0);
          d.fx = null;
          d.fy = null;
        }));

    node.append('circle')
      .attr('r', d => d.kind === 'service' ? 28 : 22);

    node.append('text')
      .attr('class', 'node-label')
      .attr('y', d => d.kind === 'service' ? 48 : 42)
      .text(d => d.label);

    simulation.on('tick', () => {
      graphData.nodes.forEach(d => {
        d.x = Math.max(40, Math.min(width - 40, d.x));
        d.y = Math.max(40, Math.min(height - 40, d.y));
      });

      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      node.attr('transform', d => `translate(${d.x}, ${d.y})`);
    });

    return () => simulation.stop();
  }, [graphData, onSelect, selectedId]);

  return (
    <div ref={containerRef} className="topology-container">
      <svg ref={svgRef} className="topology" role="img" aria-label="Service dependency topology" />
    </div>
  );
}

function InsightList({ insights }) {
  if (!insights.length) {
    return <p className="empty">No active root-cause insights.</p>;
  }

  return (
    <div className="insight-list">
      {insights.map((insight) => (
        <article className="insight" key={`${insight.event}-${insight.affected_services.join('-')}`}>
          <div className="insight-title">
            <span className={`status-dot ${insight.status.toLowerCase()}`} />
            <h3>{insight.event}</h3>
          </div>
          <p>{insight.root_cause}</p>
          <p className="muted">{insight.correlation}</p>
          <div className="recommendation">{insight.recommendation}</div>
          <div className="service-tags">
            {insight.affected_services.map((service) => (
              <span key={service}>{service}</span>
            ))}
          </div>
        </article>
      ))}
    </div>
  );
}

function ResourceTable({ metrics }) {
  if (!metrics.length) {
    return <p className="empty">No pod metrics are available for the current selector.</p>;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Namespace</th>
            <th>Pod</th>
            <th>Service</th>
            <th>CPU</th>
            <th>Memory</th>
            <th>Network</th>
            <th>PVC</th>
            <th>Errors/min</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((metric) => (
            <tr key={metric.pod}>
              <td>{metric.namespace}</td>
              <td>{metric.pod}</td>
              <td>{metric.service}</td>
              <td><Bar value={metric.cpu_millicores / metric.cpu_limit_millicores} label={`${metric.cpu_millicores.toFixed(1)}m`} /></td>
              <td><Bar value={metric.memory_mb / metric.memory_limit_mb} label={`${metric.memory_mb.toFixed(1)} MB`} /></td>
              <td>{(metric.network_rx_kbps + metric.network_tx_kbps).toFixed(1)} kbps</td>
              <td>{metric.pvc_name ? `${metric.pvc_name} (${metric.pvc_latency_ms.toFixed(1)} ms)` : 'none'}</td>
              <td>{metric.error_rate_per_minute}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Bar({ value, label }) {
  const clamped = Math.min(value, 1);
  return (
    <div className="bar-cell">
      <div className="bar-track"><span style={{ width: `${clamped * 100}%` }} /></div>
      <span>{label}</span>
    </div>
  );
}

function buildSummary(snapshot) {
  const services = new Set(snapshot.metrics.map((metric) => metric.service)).size;
  const maxPvcLatency = Math.max(0, ...snapshot.metrics.map((metric) => metric.pvc_latency_ms ?? 0));
  return { services, maxPvcLatency };
}

function sourceLabel(source) {
  if (source === 'live') return 'Live telemetry';
  if (source === 'live-fallback') return 'Live fallback';
  return 'Demo data';
}

function formatTime(value) {
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).format(new Date(value));
}

createRoot(document.getElementById('root')).render(<App />);
