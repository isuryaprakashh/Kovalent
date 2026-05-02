import React, { useEffect, useMemo, useState, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Activity,
  AlertCircle,
  ArrowUpRight,
  ChevronRight,
  Database,
  Eye,
  Fingerprint,
  LayoutGrid,
  Layers,
  MessageSquare,
  Network,
  RefreshCw,
  Search,
  ShieldCheck,
  Zap,
  Terminal,
  Cpu,
  Radio,
  ExternalLink
} from 'lucide-react';
import * as d3 from 'd3';
import './index.css';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8000';

function App() {
  const [pods, setPods] = useState([]);
  const [graph, setGraph] = useState({ nodes: [], links: [] });
  const [incidents, setIncidents] = useState([]);
  const [selectedPodId, setSelectedPodId] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [podsRes, graphRes, incidentsRes] = await Promise.all([
        fetch(`${API_BASE}/api/pods`),
        fetch(`${API_BASE}/api/graph`),
        fetch(`${API_BASE}/api/incidents`)
      ]);
      const podsData = await podsRes.json();
      const graphData = await graphRes.json();
      const incidentsData = await incidentsRes.json();
      
      setPods(podsData);
      setGraph(graphData);
      setIncidents(incidentsData.reports || []);

      if (!selectedPodId && podsData.length > 0) {
        const sorted = [...podsData].sort((a, b) => b.error_rate_per_minute - a.error_rate_per_minute);
        setSelectedPodId(sorted[0].pod);
      }
    } catch (err) {
      console.error("Failed to fetch dashboard data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 6000);
    return () => clearInterval(interval);
  }, []);

  const selectedPod = useMemo(() => 
    pods.find(p => p.pod === selectedPodId), 
    [pods, selectedPodId]
  );

  return (
    <div className="flex h-screen bg-white text-slate-900 font-mono overflow-hidden uppercase tracking-tight">
      {/* --- Top Clinical Rail --- */}
      <header className="fixed top-0 w-full h-10 flex items-center px-6 z-50 bg-white border-b border-slate-200 text-[10px] font-bold">
        <div className="flex items-center gap-8 w-full">
          <div className="text-[#FF003C] tracking-[0.2em] font-black text-sm">KOVALENT_OS</div>
          <div className="h-4 w-px bg-slate-200" />
          <div className="flex gap-8">
            <StatItem label="STATUS" value="OPERATIONAL" color="text-slate-900" />
            <StatItem label="THROUGHPUT" value="1.2M/s" color="text-[#FF003C]" />
            <StatItem label="LATENCY" value="14ms" color="text-slate-900" />
          </div>
          <div className="ml-auto flex items-center gap-4 text-slate-400">
            <RefreshCw size={12} className={loading ? 'animate-spin text-[#FF003C]' : ''} />
            <Terminal size={12} />
            <div className="flex items-center gap-2">
               <div className="w-1.5 h-1.5 bg-[#FF003C] rounded-full animate-pulse" />
               <span className="text-slate-900">LIVE_STREAM</span>
            </div>
          </div>
        </div>
      </header>

      {/* --- Left Rail: Service Array --- */}
      <aside className="mt-10 w-72 border-r border-slate-200 bg-white flex flex-col z-20 shadow-sm">
        <div className="p-4 border-b border-slate-100 bg-slate-50/50">
          <div className="text-[9px] text-slate-400 mb-1">SECTOR_01 // FLEET_ARRAY</div>
          <div className="text-[10px] text-[#FF003C] font-black tracking-widest">MISSION_CRITICAL</div>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {pods.map(pod => (
            <WarPodCardLight 
              key={pod.pod} 
              pod={pod} 
              isSelected={selectedPodId === pod.pod}
              onClick={() => setSelectedPodId(pod.pod)}
            />
          ))}
        </div>
      </aside>

      {/* --- Center: Command Canvas --- */}
      <main className="flex-1 mt-10 relative bg-[#fcfdfe]">
        <div className="absolute inset-0 opacity-10 pointer-events-none">
           <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] border border-slate-300 rotate-45" />
           <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] border border-slate-300 rotate-45" />
        </div>
        
        <div className="w-full h-full relative z-10">
          <TopologyGraphLight 
            data={graph} 
            selectedId={selectedPodId ? `pod:${selectedPodId}` : null}
            onSelect={(id) => id?.startsWith('pod:') ? setSelectedPodId(id.replace('pod:', '')) : setSelectedPodId(null)}
          />
        </div>

        {/* Floating Metrics Overlay */}
        <div className="absolute bottom-6 left-6 flex gap-4 pointer-events-none">
          <div className="bg-white border border-slate-200 p-4 flex gap-8 pointer-events-auto shadow-sm">
            <div className="flex flex-col">
              <span className="text-[9px] text-slate-400">CPU_AGGREGATE</span>
              <span className="text-xl font-bold text-slate-900 tracking-tighter">42.8%</span>
            </div>
            <div className="w-px bg-slate-200" />
            <div className="flex flex-col">
              <span className="text-[9px] text-slate-400">MEM_COMMIT</span>
              <span className="text-xl font-bold text-slate-900 tracking-tighter">8.4GB</span>
            </div>
          </div>
        </div>
      </main>

      {/* --- Right Rail: Intelligence Feed --- */}
      <aside className="mt-10 w-80 border-l border-slate-200 bg-white flex flex-col z-20 shadow-sm">
        <div className="p-4 border-b border-slate-100 bg-slate-50/50">
          <div className="text-[9px] text-[#FF003C] mb-1 tracking-widest font-black">INTELLIGENCE_FEED</div>
          <div className="text-[10px] text-slate-400">REAL-TIME_REPORTS</div>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {incidents.length > 0 ? (
            incidents.map(incident => (
              <WarIncidentCardLight key={incident.incident_id} incident={incident} />
            ))
          ) : (
            <div className="p-16 text-center">
               <ShieldCheck size={24} className="mx-auto text-slate-100 mb-2" />
               <p className="text-[9px] text-slate-400 font-bold">ZERO_ANOMALIES</p>
            </div>
          )}

          {selectedPod && (
            <div className="mt-8 pt-8 border-t border-slate-100 animate-in fade-in slide-in-from-bottom-2 duration-500">
               <div className="text-[9px] text-slate-400 mb-6 font-bold">SELECTED_SERVICE_METRICS</div>
               <div className="space-y-8">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 border border-slate-200 flex items-center justify-center text-[#FF003C] bg-white shadow-sm">
                      <Database size={24} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-black truncate text-slate-900">{selectedPod.service}</div>
                      <div className="text-[8px] text-slate-400 truncate font-mono tracking-tighter">{selectedPod.pod}</div>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-8">
                     <WarMetricLight label="CPU" value={`${(selectedPod.cpu_millicores / selectedPod.cpu_limit_millicores * 100).toFixed(1)}%`} />
                     <WarMetricLight label="RAM" value={`${(selectedPod.memory_mb / selectedPod.memory_limit_mb * 100).toFixed(1)}%`} />
                  </div>
                  <div className="p-4 border border-slate-200 bg-white shadow-sm">
                     <div className="text-[9px] text-slate-400 mb-3 font-bold">NETWORK_FLOW</div>
                     <div className="flex justify-between text-[11px] font-black">
                        <span className="text-slate-900">TX: {(selectedPod.network_tx_kbps / 1024).toFixed(2)} MB/S</span>
                        <span className="text-[#FF003C]">RX: {(selectedPod.network_rx_kbps / 1024).toFixed(2)} MB/S</span>
                     </div>
                  </div>
                  <button className="w-full py-2.5 border border-slate-900 bg-slate-900 text-white text-[10px] font-black uppercase tracking-widest hover:bg-slate-800 transition-all flex items-center justify-center gap-2">
                     Generate Runbook <ExternalLink size={12} />
                  </button>
               </div>
            </div>
          )}
        </div>
        <div className="p-4 border-t border-slate-100 bg-slate-50/50 text-[9px] text-slate-400 font-bold tracking-tighter">
           ENCRYPTION: AES_256_ACTIVE // SESSION: {Math.random().toString(16).slice(2, 10).toUpperCase()}
        </div>
      </aside>
    </div>
  );
}

// --- Components ---

function StatItem({ label, value, color }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-slate-400">{label}:</span>
      <span className={`${color} font-black`}>{value}</span>
    </div>
  );
}

function WarPodCardLight({ pod, isSelected, onClick }) {
  const isCritical = pod.error_rate_per_minute > 5;
  
  return (
    <div 
      onClick={onClick}
      className={`p-3 border transition-all cursor-pointer group ${
        isSelected ? 'bg-slate-900 border-slate-900 text-white' : 'bg-white border-slate-200 hover:border-slate-400 shadow-sm'
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className={`w-1.5 h-1.5 ${isCritical ? 'bg-[#FF003C] animate-pulse shadow-[0_0_8px_rgba(255,0,60,0.5)]' : isSelected ? 'bg-white' : 'bg-slate-900'}`} />
          <span className="text-[11px] font-black truncate uppercase tracking-tight">{pod.service}</span>
        </div>
        <span className={`text-[9px] font-bold ${isSelected ? 'text-white' : isCritical ? 'text-[#FF003C]' : 'text-slate-400'}`}>
          {pod.error_rate_per_minute > 0 ? `${pod.error_rate_per_minute} ERR/M` : 'NOMINAL'}
        </span>
      </div>
      <div className="flex items-end gap-1 h-6">
        {[4, 7, 2, 8, 5, 9, 3, 6, 4, 8, 5, 7, 2, 9].map((h, i) => (
          <div key={i} className={`flex-1 ${isSelected ? 'bg-white/20' : 'bg-slate-100 group-hover:bg-slate-200'}`} style={{ height: `${h * 10}%` }} />
        ))}
      </div>
    </div>
  );
}

function WarIncidentCardLight({ incident }) {
  return (
    <div className="p-5 border-l-4 border-[#FF003C] bg-white border border-slate-200 shadow-sm hover:shadow-md transition-all group cursor-pointer">
      <div className="flex justify-between mb-3">
        <span className="text-[#FF003C] font-black text-[9px] tracking-widest">CRITICAL_ANOMALY</span>
        <span className="text-slate-400 text-[8px] font-bold">{new Date(incident.timestamp).toLocaleTimeString()}</span>
      </div>
      <h4 className="text-[12px] font-black text-slate-900 mb-3 leading-tight uppercase tracking-tighter">{incident.summary}</h4>
      <p className="text-[10px] text-slate-500 leading-relaxed font-medium">{incident.root_cause_explanation}</p>
    </div>
  );
}

function WarMetricLight({ label, value }) {
  return (
    <div>
      <div className="text-[9px] text-slate-400 mb-1.5 font-bold uppercase">{label}</div>
      <div className="text-lg font-black text-slate-900 tracking-tighter">{value}</div>
    </div>
  );
}

function TopologyGraphLight({ data, selectedId, onSelect }) {
  const svgRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!data.nodes?.length || !svgRef.current) return;

    const width = containerRef.current.clientWidth;
    const height = containerRef.current.clientHeight;

    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    svg.selectAll('*').remove();

    const g = svg.append('g');

    const zoom = d3.zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => g.attr('transform', event.transform));
    svg.call(zoom);

    const simulation = d3.forceSimulation(data.nodes)
      .force('link', d3.forceLink(data.edges || []).id(d => d.id).distance(200))
      .force('charge', d3.forceManyBody().strength(-1000))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(100));

    const link = g.append('g')
      .selectAll('line')
      .data(data.edges || [])
      .join('line')
      .attr('stroke', d => d.relationship === 'causal' ? '#FF003C' : '#e2e8f0')
      .attr('stroke-width', d => d.relationship === 'causal' ? 3 : 1)
      .attr('stroke-dasharray', d => d.relationship === 'causal' ? '0' : '6 4');

    const node = g.append('g')
      .selectAll('.node')
      .data(data.nodes)
      .join('g')
      .attr('class', 'cursor-pointer')
      .on('click', (e, d) => onSelect(d.id))
      .call(d3.drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended));

    node.append('rect')
      .attr('x', -70)
      .attr('y', -30)
      .attr('width', 140)
      .attr('height', 60)
      .attr('fill', '#ffffff')
      .attr('stroke', d => d.status === 'CRITICAL' ? '#FF003C' : d.id === selectedId ? '#0f172a' : '#e2e8f0')
      .attr('stroke-width', d => d.id === selectedId || d.status === 'CRITICAL' ? 3 : 1)
      .style('filter', 'drop-shadow(0 2px 4px rgba(0,0,0,0.05))');

    node.append('text')
      .attr('y', 0)
      .attr('text-anchor', 'middle')
      .attr('fill', d => d.status === 'CRITICAL' ? '#FF003C' : '#0f172a')
      .attr('font-size', '11px')
      .attr('font-weight', '900')
      .text(d => d.label);

    node.append('text')
      .attr('y', 18)
      .attr('text-anchor', 'middle')
      .attr('fill', '#94a3b8')
      .attr('font-size', '9px')
      .attr('font-weight', 'bold')
      .text(d => d.kind === 'pod' ? 'POD_NODE' : 'SVC_NODE');

    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      node.attr('transform', d => `translate(${d.x}, ${d.y})`);
    });

    function dragstarted(event) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      event.subject.fx = event.subject.x;
      event.subject.fy = event.subject.y;
    }
    function dragged(event) {
      event.subject.fx = event.x;
      event.subject.fy = event.y;
    }
    function dragended(event) {
      if (!event.active) simulation.alphaTarget(0);
      event.subject.fx = null;
      event.subject.fy = null;
    }

    return () => simulation.stop();
  }, [data, selectedId]);

  return (
    <div ref={containerRef} className="w-full h-full">
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
