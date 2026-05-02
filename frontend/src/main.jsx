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
  ExternalLink,
  BarChart3
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
    const interval = setInterval(fetchData, 8000);
    return () => clearInterval(interval);
  }, []);

  const selectedPod = useMemo(() => 
    pods.find(p => p.pod === selectedPodId), 
    [pods, selectedPodId]
  );

  return (
    <div className="flex h-screen bg-[#101010] text-[#F3F3F3] font-aeonik overflow-hidden">
      {/* --- Header: Persistent Navigation --- */}
      <header className="fixed top-0 w-full h-14 flex items-center px-8 z-50 bg-[#101010]/80 backdrop-blur-md border-b border-[#333333]">
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-12">
            <div className="text-lg font-bold tracking-tight">Kovalent <span className="text-[#E7C59A] text-[10px] ml-2 font-normal border border-[#E7C59A]/30 px-1.5 py-0.5 rounded">NEW</span></div>
            <nav className="flex gap-8 text-[14px] font-normal">
              <NavLink label="SERVICES" active />
              <NavLink label="TOPOLOGY" />
              <NavLink label="REPORTS" />
            </nav>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2 text-[13px] font-input text-[#00AC5C]">
               <div className="w-1.5 h-1.5 bg-[#00AC5C] rounded-full shadow-[0_0_8px_#00AC5C]" />
               SYSTEM NOMINAL
            </div>
            <button className="bg-[#333333] text-white text-[14px] px-4 py-1.5 rounded-[8px] hover:bg-[#444] transition-all">
              LET'S CHAT
            </button>
          </div>
        </div>
      </header>

      {/* --- Sidebar: Service Discovery --- */}
      <aside className="mt-14 w-80 border-r border-[#333333] bg-[#080808] flex flex-col">
        <div className="p-6 border-b border-[#333333]">
          <p className="text-[13px] font-normal text-[#949494] uppercase tracking-[-0.007px] mb-4">Service Array</p>
          <div className="relative">
            <Search className="absolute left-3 top-2 text-[#949494]" size={14} />
            <input 
              type="text" 
              placeholder="Filter services..."
              className="w-full pl-9 pr-4 py-1.5 bg-[#101010] border border-[#333333] rounded-[8px] text-[13px] text-[#F3F3F3] focus:outline-none focus:border-[#E7C59A]/50 transition-all"
            />
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {pods.map(pod => (
            <HyperPodCard 
              key={pod.pod} 
              pod={pod} 
              isSelected={selectedPodId === pod.pod}
              onClick={() => setSelectedPodId(pod.pod)}
            />
          ))}
        </div>
      </aside>

      {/* --- Main: Topology Command --- */}
      <main className="flex-1 mt-14 relative bg-[#101010]">
        <div className="w-full h-full relative z-10">
          <TopologyGraph 
            data={graph} 
            selectedId={selectedPodId ? `pod:${selectedPodId}` : null}
            onSelect={(id) => id?.startsWith('pod:') ? setSelectedPodId(id.replace('pod:', '')) : setSelectedPodId(null)}
          />
        </div>

        {/* Global KPI Strip */}
        <div className="absolute bottom-10 left-10 right-10 flex justify-between pointer-events-none">
           <div className="flex gap-12 bg-[#080808]/80 backdrop-blur-xl border border-[#333333] p-6 rounded-[8px] pointer-events-auto shadow-2xl">
              <StatBlock label="AGGREGATE CPU" value="42.8%" />
              <StatBlock label="THROUGHPUT" value="1.2M/s" />
              <StatBlock label="ANOMALY RATE" value="0.02%" />
           </div>
           <div className="flex items-end">
              <div className="bg-[#E7C59A] text-[#101010] text-[13px] font-bold px-4 py-1.5 rounded-[99px] shadow-lg shadow-[#E7C59A]/20 pointer-events-auto">
                 {incidents.length} INCIDENTS PENDING
              </div>
           </div>
        </div>
      </main>

      {/* --- Right: Intelligence Feed --- */}
      <aside className="mt-14 w-[420px] border-l border-[#333333] bg-[#080808] flex flex-col p-8 overflow-y-auto">
        <div className="flex items-center justify-between mb-12">
          <h2 className="text-[23px] font-bold text-[#F3F3F3]">INTELLIGENCE</h2>
          <BarChart3 className="text-[#949494]" size={20} />
        </div>
        
        <div className="space-y-12">
          <section>
            <p className="text-[13px] font-normal text-[#949494] uppercase tracking-[-0.007px] mb-6">Critical Anomalies</p>
            <div className="space-y-6">
              {incidents.length > 0 ? (
                incidents.map(incident => (
                  <HyperIncidentCard key={incident.incident_id} incident={incident} />
                ))
              ) : (
                <div className="p-16 text-center border border-dashed border-[#333333] rounded-[8px]">
                   <ShieldCheck size={24} className="mx-auto text-[#333333] mb-3" />
                   <p className="text-[13px] text-[#949494]">SYSTEM SECURE</p>
                </div>
              )}
            </div>
          </section>

          {selectedPod && (
            <section className="animate-in fade-in slide-in-from-bottom-4 duration-700">
               <p className="text-[13px] font-normal text-[#949494] uppercase tracking-[-0.007px] mb-6">Service Insights</p>
               <div className="bg-[#101010] border border-[#333333] p-6 rounded-[8px] space-y-8">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-[#333333] rounded-[8px] flex items-center justify-center text-[#E7C59A]">
                      <Database size={24} />
                    </div>
                    <div>
                      <h3 className="text-[18px] font-bold text-[#F3F3F3] leading-none mb-1.5">{selectedPod.service}</h3>
                      <p className="text-[13px] font-input text-[#949494] tracking-[-0.037em]">{selectedPod.pod}</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-10">
                     <HyperMetric label="CPU SATURATION" value={`${(selectedPod.cpu_millicores / selectedPod.cpu_limit_millicores * 100).toFixed(1)}%`} />
                     <HyperMetric label="MEM CAPACITY" value={`${(selectedPod.memory_mb / selectedPod.memory_limit_mb * 100).toFixed(1)}%`} />
                  </div>
                  <div className="pt-6 border-t border-[#333333]">
                     <div className="flex justify-between items-center mb-4 text-[13px] font-normal text-[#949494]">
                        <span>INGRESS: <span className="text-[#F3F3F3]">{(selectedPod.network_rx_kbps / 1024).toFixed(1)} MB/s</span></span>
                        <span>EGRESS: <span className="text-[#F3F3F3]">{(selectedPod.network_tx_kbps / 1024).toFixed(1)} MB/s</span></span>
                     </div>
                  </div>
                  <button className="w-full py-2.5 bg-[#333333] text-white text-[16px] font-normal rounded-[8px] hover:bg-[#444] transition-all">
                    READ MANIFESTO
                  </button>
               </div>
            </section>
          )}
        </div>
      </aside>
    </div>
  );
}

// --- Components ---

function NavLink({ label, active }) {
  return (
    <a href="#" className={`tracking-wide transition-all ${
      active ? 'text-[#F3F3F3] border-b border-[#F3F3F3]' : 'text-[#949494] hover:text-[#F3F3F3]'
    }`}>
      {label}
    </a>
  );
}

function StatBlock({ label, value }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[13px] text-[#949494] tracking-tight">{label}</span>
      <span className="text-[21px] font-bold text-[#F3F3F3] leading-none">{value}</span>
    </div>
  );
}

function HyperPodCard({ pod, isSelected, onClick }) {
  const isAnomalous = pod.error_rate_per_minute > 2;
  const cpuPercent = (pod.cpu_millicores / pod.cpu_limit_millicores * 100).toFixed(0);

  return (
    <div 
      onClick={onClick}
      className={`p-4 border transition-all cursor-pointer rounded-[8px] group ${
        isSelected ? 'bg-[#101010] border-[#E7C59A]/40' : 'bg-[#101010] border-[#333333] hover:border-[#E7C59A]/20'
      }`}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`w-1.5 h-1.5 rounded-full ${isAnomalous ? 'bg-[#E7C59A]' : 'bg-[#00AC5C]'}`} />
          <span className="text-[14px] font-bold text-[#F3F3F3]">{pod.service}</span>
        </div>
        <div className="text-[13px] font-input text-[#949494] tracking-[-0.037em]">
          CPU: {cpuPercent}%
        </div>
      </div>
      <div className="flex items-end gap-1 h-6">
        {[3, 7, 4, 8, 5, 9, 6, 4, 7, 8, 5, 6, 4, 9].map((h, i) => (
          <div key={i} className={`flex-1 ${isSelected ? 'bg-[#E7C59A]/20' : 'bg-[#333333] group-hover:bg-[#444]'}`} style={{ height: `${h * 10}%` }} />
        ))}
      </div>
    </div>
  );
}

function HyperIncidentCard({ incident }) {
  return (
    <div className="bg-[#101010] border-l border-[#E7C59A] p-6 space-y-4 hover:bg-[#080808] transition-all">
      <div className="flex justify-between items-center">
        <span className="text-[13px] font-bold text-[#E7C59A] uppercase tracking-wider">Anomaly</span>
        <span className="text-[13px] font-input text-[#949494] tracking-[-0.037em]">{new Date(incident.timestamp).toLocaleTimeString()}</span>
      </div>
      <h4 className="text-[18px] font-bold text-[#F3F3F3] leading-tight tracking-tight">{incident.summary}</h4>
      <p className="text-[16px] text-[#949494] leading-relaxed font-normal">
        {incident.root_cause_explanation}
      </p>
      <div className="pt-4 flex items-center gap-2 text-[13px] text-[#E7C59A] font-bold cursor-pointer hover:underline">
        READ INCIDENT LOG <ChevronRight size={14} />
      </div>
    </div>
  );
}

function HyperMetric({ label, value }) {
  return (
    <div>
      <p className="text-[13px] text-[#949494] mb-2 uppercase tracking-tight">{label}</p>
      <p className="text-[23px] font-bold text-[#F3F3F3] tracking-tight leading-none">{value}</p>
    </div>
  );
}

function TopologyGraph({ data, selectedId, onSelect }) {
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
      .force('link', d3.forceLink(data.edges || []).id(d => d.id).distance(180))
      .force('charge', d3.forceManyBody().strength(-800))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(80));

    const link = g.append('g')
      .selectAll('line')
      .data(data.edges || [])
      .join('line')
      .attr('stroke', '#333333')
      .attr('stroke-width', d => d.relationship === 'causal' ? 2 : 1)
      .attr('stroke-dasharray', d => d.relationship === 'causal' ? '0' : '4 4');

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

    node.append('circle')
      .attr('r', 28)
      .attr('fill', d => d.id === selectedId ? '#1a1a1a' : '#080808')
      .attr('stroke', d => d.status === 'CRITICAL' ? '#E7C59A' : d.id === selectedId ? '#F3F3F3' : '#333333')
      .attr('stroke-width', d => d.id === selectedId || d.status === 'CRITICAL' ? 2 : 1);

    node.append('text')
      .attr('y', 45)
      .attr('text-anchor', 'middle')
      .attr('fill', d => d.id === selectedId ? '#F3F3F3' : '#949494')
      .attr('font-size', '13px')
      .attr('font-weight', '700')
      .text(d => d.label);

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
