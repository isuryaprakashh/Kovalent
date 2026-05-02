import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Box,
  Cpu,
  Database,
  Gauge,
  HardDrive,
  Info,
  Network,
  RefreshCw,
  RotateCcw,
  Server,
  Terminal
} from 'lucide-react';
import * as d3 from 'd3';
import './styles.css';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000';

const SERVICE_INFO = {
  'kube-dns': 'Cluster DNS server. Resolves service names to IP addresses inside Kubernetes.',
  'coredns': 'Cluster DNS server. Resolves service names to IP addresses inside Kubernetes.',
  'etcd': 'Key-value store. Holds all cluster state — pods, configs, secrets, and scheduling data.',
  'kube-apiserver': 'API gateway. Every kubectl command and controller talks to the cluster through this.',
  'kube-controller-manager': 'Runs control loops. Manages replicas, nodes, endpoints, and service accounts.',
  'kube-scheduler': 'Assigns pods to nodes. Picks the best node based on resources and constraints.',
  'kube-proxy': 'Network proxy. Routes traffic to the correct pod behind each Kubernetes service.',
  'storage-provisioner': 'Auto-creates persistent volumes when a pod requests storage.',
  'alertmanager': 'Handles Prometheus alerts. Deduplicates, groups, and routes notifications.',
  'grafana': 'Visualization dashboard. Renders charts and graphs from Prometheus and Loki data.',
  'kube-state-metrics': 'Exports Kubernetes object states (pods, deployments, nodes) as Prometheus metrics.',
  'kube-prometheus-stack-prometheus-operator': 'Manages Prometheus instances. Watches for monitoring config changes.',
  'prometheus-node-exporter': 'Exports hardware and OS metrics from each node (CPU, memory, disk, network).',
  'prometheus': 'Time-series database. Scrapes and stores all cluster metrics for querying.',
  'loki': 'Log aggregation system. Collects and indexes container logs for querying.',
  'promtail': 'Log shipper. Tails container log files and pushes them to Loki.',
  'nginx': 'Web server / reverse proxy. Serves HTTP traffic or load-balances to backends.',
};

function getServiceInfo(service) {
  if (SERVICE_INFO[service]) return SERVICE_INFO[service];
  // Try partial matches for long operator names
  for (const [key, desc] of Object.entries(SERVICE_INFO)) {
    if (service.includes(key)) return desc;
  }
  return `Kubernetes workload running in the cluster.`;
}

function TileInfo({ text }) {
  return (
    <span className="tile-info-wrap">
      <span className="tile-info-icon">
        <Info size={11} />
      </span>
      <span className="tile-info-tooltip">{text}</span>
    </span>
  );
}



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
      network_rx_drops_per_second: null,
      network_tx_drops_per_second: null,
      pvc_name: null,
      pvc_mounts: [],
      pvc_read_kbps: null,
      pvc_write_kbps: null,
      pvc_latency_ms: null,
      pvc_iops: null,
      error_rate_per_minute: 4,
      error_signatures: [],
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
      network_rx_drops_per_second: null,
      network_tx_drops_per_second: null,
      pvc_name: 'orders-data',
      pvc_mounts: ['orders-data'],
      pvc_read_kbps: 80,
      pvc_write_kbps: 420,
      pvc_latency_ms: 165,
      pvc_iops: 920,
      error_rate_per_minute: 1,
      error_signatures: [],
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
      network_rx_drops_per_second: null,
      network_tx_drops_per_second: null,
      pvc_name: null,
      pvc_mounts: [],
      pvc_read_kbps: null,
      pvc_write_kbps: null,
      pvc_latency_ms: null,
      pvc_iops: null,
      error_rate_per_minute: 18,
      error_signatures: [
        {
          signature: 'error checkout failed for order <num>',
          count: 12,
          first_seen: new Date(Date.now() - 300000).toISOString(),
          last_seen: new Date().toISOString(),
          sample: 'ERROR checkout failed for order 451'
        }
      ],
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
  const [collectorStatus, setCollectorStatus] = useState(null);
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
      fetch(`${API_BASE}/api/status`)
        .then(statusResponse => statusResponse.ok ? statusResponse.json() : null)
        .then(status => setCollectorStatus(status))
        .catch(() => setCollectorStatus(null));
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
        <MetricTile icon={<Server />} label="Services" hint="Total unique services discovered across all namespaces." value={summary.services} tone="neutral" />
        <MetricTile icon={<Box />} label="Pods" hint="Number of running pods being monitored in the cluster." value={snapshot.metrics.length} tone="neutral" />
        <MetricTile icon={<RotateCcw />} label="Restarts" hint="Total container restarts across all pods. High count may indicate crashes or OOM kills." value={summary.restarts} tone={summary.restarts ? 'warning' : 'neutral'} />
        <MetricTile icon={<AlertTriangle />} label="Log signatures" hint="Unique error patterns found in pod logs via Loki. Grouped by similar messages." value={summary.logSignatures} tone={summary.logSignatures ? 'danger' : 'neutral'} />
        <MetricTile icon={<Gauge />} label="CPU throttling" hint="Highest CPU pressure across all pods. Shows how much CPU time pods are waiting for." value={summary.hasThrottleData ? `${summary.maxCpuThrottle.toFixed(1)}%` : 'n/a'} tone={summary.maxCpuThrottle ? 'warning' : 'neutral'} />
        <MetricTile icon={<HardDrive />} label="Disk write" hint="Peak filesystem write throughput across all pods. Includes all disk I/O, not just PVC." value={summary.hasPvcData ? `${summary.maxPvcWrite.toFixed(1)} KiB/s` : 'n/a'} tone={summary.maxPvcWrite ? 'danger' : 'neutral'} />
      </section>

      <CollectorCoverage status={collectorStatus} metrics={snapshot.metrics} />

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

function MetricTile({ icon, label, value, tone, hint }) {
  return (
    <div className={`metric-tile ${tone}`}>
      <div className="tile-icon">{icon}</div>
      <div>
        <p>{label}{hint ? <TileInfo text={hint} /> : null}</p>
        <strong>{value}</strong>
      </div>
    </div>
  );
}
function NodeDetails({ metric, onClear }) {
  const owner = metric.owner_kind && metric.owner_name ? `${metric.owner_kind}/${metric.owner_name}` : 'unknown';
  const pvcMounts = metric.pvc_mounts?.length ? metric.pvc_mounts.join(', ') : metric.pvc_name ?? 'none';

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
        <div className="detail-row">
          <span>Owner</span>
          <strong>{owner}</strong>
        </div>
        <div className="detail-row">
          <span>Node</span>
          <strong>{metric.node_name ?? 'unknown'}</strong>
        </div>
        <div className="detail-row">
          <span>PVC mounts</span>
          <strong>{pvcMounts}</strong>
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
        <div className="detail-stat">
          <p>Restart State</p>
          <div className="restart-stack">
            <span>{metric.restart_count ?? 0} restarts</span>
            {metric.waiting_reason ? <span>{metric.waiting_reason}</span> : null}
            {metric.last_termination_reason ? <span>{metric.last_termination_reason}</span> : null}
            {metric.oom_killed ? <span>OOMKilled</span> : null}
          </div>
        </div>
        <LogSignatures signatures={metric.error_signatures ?? []} />
      </div>
    </div>
  );
}

function CollectorCoverage({ status, metrics }) {
  const kubernetesPods = metrics.filter(metric => metric.owner_kind || metric.node_name || metric.pvc_mounts?.length).length;
  const throttlingPods = metrics.filter(metric => metric.cpu_throttled_percent != null).length;
  const pvcPods = metrics.filter(metric => metric.pvc_read_kbps != null || metric.pvc_write_kbps != null).length;
  const logPods = metrics.filter(metric => metric.error_signatures?.length).length;
  const kubeStatus = status?.live_collector_status?.kubernetes;
  const optionalErrors = status?.live_collector_status?.optional_errors ?? [];

  return (
    <section className="coverage-strip" aria-label="Collector coverage">
      <CoverageItem icon={<Network />} label="Kubernetes API" hint="Enriches pods with owner, node, restart, and PVC metadata from the Kubernetes API." value={kubeStatus?.available ? `${kubernetesPods} pods enriched` : 'unavailable'} tone={kubeStatus?.available ? 'ok' : 'warn'} />
      <CoverageItem icon={<Gauge />} label="Prometheus extras" hint="Additional metrics like CPU throttling and filesystem I/O from Prometheus queries." value={`${throttlingPods} throttle / ${pvcPods} PVC pods`} tone="ok" />
      <CoverageItem icon={<Terminal />} label="Loki patterns" hint="Error log patterns extracted from Loki. Pods with signatures have recent error logs." value={`${logPods} pods with signatures`} tone={logPods ? 'warn' : 'ok'} />
      <CoverageItem icon={<AlertTriangle />} label="Optional query errors" hint="Count of non-critical Prometheus queries that returned errors or empty results." value={optionalErrors.length} tone={optionalErrors.length ? 'warn' : 'ok'} />
    </section>
  );
}

function CoverageItem({ icon, label, value, tone, hint }) {
  return (
    <div className={`coverage-item ${tone}`}>
      {React.cloneElement(icon, { size: 17 })}
      <div>
        <span>{label}{hint ? <TileInfo text={hint} /> : null}</span>
        <strong>{value}</strong>
      </div>
    </div>
  );
}

function LogSignatures({ signatures }) {
  if (!signatures.length) {
    return null;
  }

  return (
    <div className="log-signatures">
      <p>Top log signatures</p>
      {signatures.slice(0, 3).map(signature => (
        <article key={signature.signature}>
          <strong>{signature.count}x</strong>
          <span>{signature.signature}</span>
          <small>{formatTime(signature.first_seen)} - {formatTime(signature.last_seen)}</small>
        </article>
      ))}
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
            <th>Owner</th>
            <th>Node</th>
            <th>CPU</th>
            <th>Throttle</th>
            <th>Memory</th>
            <th>Network</th>
            <th>Drops/s</th>
            <th>PVC</th>
            <th>PVC I/O</th>
            <th>Restarts</th>
            <th>Errors/min</th>
            <th>Top log signature</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((metric) => (
            <tr key={metric.pod}>
              <td>{metric.namespace}</td>
              <td>{metric.pod}</td>
              <td>{metric.service}</td>
              <td>{metric.owner_kind && metric.owner_name ? `${metric.owner_kind}/${metric.owner_name}` : 'unknown'}</td>
              <td>{metric.node_name ?? 'unknown'}</td>
              <td><Bar value={metric.cpu_millicores / metric.cpu_limit_millicores} label={`${metric.cpu_millicores.toFixed(1)}m`} /></td>
              <td>{formatOptional(metric.cpu_throttled_percent, '%')}</td>
              <td><Bar value={metric.memory_mb / metric.memory_limit_mb} label={`${metric.memory_mb.toFixed(1)} MB`} /></td>
              <td>{(metric.network_rx_kbps + metric.network_tx_kbps).toFixed(1)} kbps</td>
              <td>{formatDrops(metric)}</td>
              <td>{metric.pvc_name ? `${metric.pvc_name} (${formatOptional(metric.pvc_latency_ms, ' ms')})` : 'none'}</td>
              <td>{formatPvcIo(metric)}</td>
              <td>{formatRestart(metric)}</td>
              <td>{metric.error_rate_per_minute}</td>
              <td className="signature-cell">{metric.error_signatures?.[0]?.signature ?? 'none'}</td>
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
  const restarts = snapshot.metrics.reduce((sum, metric) => sum + (metric.restart_count ?? 0), 0);
  const logSignatures = snapshot.metrics.reduce((sum, metric) => sum + (metric.error_signatures?.length ?? 0), 0);
  const hasThrottleData = snapshot.metrics.some((metric) => metric.cpu_throttled_percent != null);
  const maxCpuThrottle = Math.max(0, ...snapshot.metrics.map((metric) => metric.cpu_throttled_percent ?? 0));
  const hasPvcData = snapshot.metrics.some((metric) => metric.pvc_write_kbps != null);
  const maxPvcWrite = Math.max(0, ...snapshot.metrics.map((metric) => metric.pvc_write_kbps ?? 0));
  return { services, maxPvcLatency, restarts, logSignatures, hasThrottleData, maxCpuThrottle, hasPvcData, maxPvcWrite };
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

function formatOptional(value, suffix = '') {
  if (value == null) return 'n/a';
  return `${Number(value).toFixed(1)}${suffix}`;
}

function formatDrops(metric) {
  const rx = metric.network_rx_drops_per_second;
  const tx = metric.network_tx_drops_per_second;
  if (rx == null && tx == null) return 'n/a';
  return `${((rx ?? 0) + (tx ?? 0)).toFixed(2)}`;
}

function formatPvcIo(metric) {
  if (metric.pvc_read_kbps == null && metric.pvc_write_kbps == null) return 'n/a';
  return `R ${formatOptional(metric.pvc_read_kbps)} / W ${formatOptional(metric.pvc_write_kbps)} KiB/s`;
}

function formatRestart(metric) {
  const reasons = [metric.waiting_reason, metric.last_termination_reason, metric.oom_killed ? 'OOMKilled' : null].filter(Boolean);
  return reasons.length ? `${metric.restart_count ?? 0} (${reasons.join(', ')})` : `${metric.restart_count ?? 0}`;
}

createRoot(document.getElementById('root')).render(<App />);
