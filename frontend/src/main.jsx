import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, AlertTriangle, Box, Cpu, Database, Network, RefreshCw, Server } from 'lucide-react';
import * as d3 from 'd3';
import './styles.css';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000';

const fallbackSnapshot = {
  generated_at: new Date().toISOString(),
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

  const loadSnapshot = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/snapshot`);
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      const nextSnapshot = await response.json();
      setSnapshot(nextSnapshot);
      setApiState(nextSnapshot.source ?? 'live');
    } catch {
      setSnapshot(fallbackSnapshot);
      setApiState('demo');
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
          <span className={`api-pill ${apiState}`}>{sourceLabel(apiState)}</span>
          <button type="button" onClick={loadSnapshot} disabled={loading} aria-label="Refresh snapshot">
            <RefreshCw size={18} className={loading ? 'spin' : ''} />
          </button>
        </div>
      </header>

      <section className="summary-grid" aria-label="Cluster summary">
        <MetricTile icon={<Server />} label="Services" value={summary.services} tone="neutral" />
        <MetricTile icon={<Box />} label="Pods" value={snapshot.metrics.length} tone="neutral" />
        <MetricTile icon={<AlertTriangle />} label="Insights" value={snapshot.insights.length} tone="warning" />
        <MetricTile icon={<Database />} label="PVC latency" value={`${summary.maxPvcLatency} ms`} tone="danger" />
      </section>

      <section className="main-grid">
        <div className="panel topology-panel">
          <PanelHeader icon={<Network />} title="Dependency topology" />
          <TopologyGraph topology={snapshot.topology} />
        </div>
        <div className="panel">
          <PanelHeader icon={<Activity />} title="Root-cause insights" />
          <InsightList insights={snapshot.insights} />
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

function PanelHeader({ icon, title }) {
  return (
    <div className="panel-header">
      {React.cloneElement(icon, { size: 18 })}
      <h2>{title}</h2>
    </div>
  );
}

function TopologyGraph({ topology }) {
  const width = 760;
  const height = 420;
  const graph = useMemo(() => {
    const nodes = topology.nodes.map((node) => ({ ...node }));
    const links = topology.edges.map((edge) => ({ ...edge }));
    d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id((node) => node.id).distance((link) => (link.relationship === 'calls' ? 130 : 82)))
      .force('charge', d3.forceManyBody().strength(-460))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(44))
      .tick(180);
    return { nodes, links };
  }, [topology]);

  return (
    <svg className="topology" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Service dependency topology">
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" fill="#73808c" />
        </marker>
      </defs>
      {graph.links.map((link, index) => (
        <line
          key={`${link.source.id}-${link.target.id}-${index}`}
          x1={link.source.x}
          y1={link.source.y}
          x2={link.target.x}
          y2={link.target.y}
          className={`edge ${link.relationship}`}
          markerEnd={link.relationship === 'calls' ? 'url(#arrow)' : undefined}
        />
      ))}
      {graph.nodes.map((node) => (
        <g key={node.id} transform={`translate(${node.x}, ${node.y})`} className={`node ${node.status.toLowerCase()}`}>
          <circle r={node.kind === 'service' ? 25 : 20} />
          <text y={node.kind === 'service' ? 43 : 37}>{node.label}</text>
        </g>
      ))}
    </svg>
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
              <td><Bar value={metric.cpu_millicores / metric.cpu_limit_millicores} label={`${metric.cpu_millicores}m`} /></td>
              <td><Bar value={metric.memory_mb / metric.memory_limit_mb} label={`${metric.memory_mb} MB`} /></td>
              <td>{metric.network_rx_kbps + metric.network_tx_kbps} kbps</td>
              <td>{metric.pvc_name ? `${metric.pvc_name} (${metric.pvc_latency_ms} ms)` : 'none'}</td>
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

createRoot(document.getElementById('root')).render(<App />);
