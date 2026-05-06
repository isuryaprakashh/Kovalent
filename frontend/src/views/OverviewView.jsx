import React, { useState } from 'react';
import { Search, Database, ShieldCheck, BarChart3, ChevronRight, ChevronLeft } from 'lucide-react';
import { TopologyGraph } from '../components/TopologyGraph';
import { StatBlock, HyperPodCard, HyperIncidentCard, HyperMetric } from '../components/Shared';

export function OverviewView({ data, selectedPodId, setSelectedPodId, setDrawerIncident, setActiveView, drawerIncident }) {
  const { pods, graph, incidents } = data;
  const selectedPod = pods.find(p => p.pod === selectedPodId);
  const [filterText, setFilterText] = useState('');
  const [sortMode, setSortMode] = useState('name'); // 'name' or 'cpu'
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(true);

  const processedPods = pods
    .filter(p => p.pod.toLowerCase().includes(filterText.toLowerCase()) || p.service.toLowerCase().includes(filterText.toLowerCase()))
    .sort((a, b) => {
      if (sortMode === 'cpu') {
        const cpuA = (a.cpu_millicores / Math.max(a.cpu_limit_millicores, 1)) * 100;
        const cpuB = (b.cpu_millicores / Math.max(b.cpu_limit_millicores, 1)) * 100;
        return cpuB - cpuA; // High to Low
      }
      return a.service.localeCompare(b.service); // A-Z
    });

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-80 border-r border-[#333333] bg-[#080808] flex flex-col z-20">
        <div className="p-6 border-b border-[#333333]">
          <p className="text-[13px] font-normal text-[#949494] uppercase tracking-[-0.007px] mb-4">Service Array</p>
          <div className="relative">
            <Search className="absolute left-3 top-2.5 text-[#949494]" size={14} />
            <input 
              type="text" 
              placeholder="Filter services..."
              value={filterText}
              onChange={e => setFilterText(e.target.value)}
              className="w-full pl-9 pr-4 py-2 bg-[#101010] border border-[#333333] rounded-[8px] text-[13px] text-[#F3F3F3] focus:outline-none focus:border-[#E7C59A]/50 transition-all"
            />
          </div>
          <div className="flex items-center gap-2 mt-4 px-1">
             <span className="text-[11px] text-[#949494] font-bold uppercase tracking-wider">Sort by:</span>
             <button onClick={() => setSortMode('name')} className={`text-[11px] px-2 py-1 rounded-[4px] font-bold transition-all ${sortMode === 'name' ? 'bg-[#333333] text-[#F3F3F3]' : 'text-[#949494] hover:text-[#F3F3F3]'}`}>NAME</button>
             <button onClick={() => setSortMode('cpu')} className={`text-[11px] px-2 py-1 rounded-[4px] font-bold transition-all ${sortMode === 'cpu' ? 'bg-[#333333] text-[#F3F3F3]' : 'text-[#949494] hover:text-[#F3F3F3]'}`}>CPU USAGE</button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          {processedPods.map(pod => (
            <HyperPodCard 
              key={pod.pod} 
              pod={pod} 
              isSelected={selectedPodId === pod.pod}
              onClick={() => setSelectedPodId(pod.pod)}
            />
          ))}
        </div>
      </aside>

      {/* Main Topology */}
      <main className="flex-1 relative bg-[#101010]">
        <div className="w-full h-full relative z-10">
          <TopologyGraph 
            data={graph} 
            selectedId={selectedPodId ? `pod:${selectedPodId}` : null}
            onSelect={(id) => id?.startsWith('pod:') ? setSelectedPodId(id.replace('pod:', '')) : setSelectedPodId(null)}
          />
        </div>

        <div className="absolute bottom-10 left-10 right-10 flex justify-between pointer-events-none z-20">
           <div className="flex gap-12 bg-[#080808]/80 backdrop-blur-xl border border-[#333333] p-6 rounded-[8px] pointer-events-auto shadow-2xl">
              <StatBlock 
                label="AGGREGATE CPU" 
                value={`${(pods.reduce((acc, p) => acc + (p.cpu_millicores / Math.max(p.cpu_limit_millicores, 1)), 0) / Math.max(pods.length, 1) * 100).toFixed(1)}%`} 
              />
              <StatBlock 
                label="THROUGHPUT" 
                value={`${(pods.reduce((acc, p) => acc + p.network_rx_kbps + p.network_tx_kbps, 0) / 1024).toFixed(1)}M/s`} 
              />
              <StatBlock 
                label="ANOMALY RATE" 
                value={`${((incidents.length / Math.max(pods.length, 1)) * 100).toFixed(2)}%`} 
              />
           </div>
           <div className="flex items-end">
              <div className="bg-[#E7C59A] text-[#101010] text-[13px] font-bold px-4 py-1.5 rounded-[99px] shadow-lg shadow-[#E7C59A]/20 pointer-events-auto">
                 {incidents.length} INCIDENTS PENDING
              </div>
           </div>
        </div>
      </main>

      {/* Intelligence Feed */}
      <aside className={`${isRightSidebarOpen ? 'w-[420px]' : 'w-0'} border-l border-[#333333] bg-[#080808] flex flex-col relative transition-all duration-300 ease-in-out z-20`}>
        {/* Toggle Button */}
        <button 
          onClick={() => setIsRightSidebarOpen(!isRightSidebarOpen)}
          className="absolute -left-4 top-1/2 -translate-y-1/2 w-8 h-8 bg-[#101010] border border-[#333333] rounded-full flex items-center justify-center text-[#949494] hover:text-[#F3F3F3] z-30 transition-colors"
        >
          {isRightSidebarOpen ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>

        <div className={`flex-1 flex flex-col p-8 overflow-y-auto transition-opacity duration-300 ${isRightSidebarOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}>
          <div className="flex items-center justify-between mb-12">
            <h2 className="text-[23px] font-bold text-[#F3F3F3]">INTELLIGENCE</h2>
            <BarChart3 className="text-[#949494]" size={20} />
          </div>
          
          <div className="space-y-12">
            {selectedPod ? (
              <>
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
                         <HyperMetric label="CPU SATURATION" value={`${(selectedPod.cpu_millicores / Math.max(selectedPod.cpu_limit_millicores, 1) * 100).toFixed(1)}%`} />
                         <HyperMetric label="MEM CAPACITY" value={`${(selectedPod.memory_mb / Math.max(selectedPod.memory_limit_mb, 1) * 100).toFixed(1)}%`} />
                      </div>
                      <div className="pt-6 border-t border-[#333333]">
                         <div className="flex justify-between items-center mb-4 text-[13px] font-normal text-[#949494]">
                            <span>INGRESS: <span className="text-[#F3F3F3]">{(selectedPod.network_rx_kbps / 1024).toFixed(1)} MB/s</span></span>
                            <span>EGRESS: <span className="text-[#F3F3F3]">{(selectedPod.network_tx_kbps / 1024).toFixed(1)} MB/s</span></span>
                         </div>
                      </div>
                   </div>
                </section>

                <section className="animate-in fade-in slide-in-from-bottom-4 duration-700 delay-100">
                  <p className="text-[13px] font-normal text-[#949494] uppercase tracking-[-0.007px] mb-6">Local Anomalies</p>
                  <div className="space-y-6">
                    {incidents.filter(inc => inc.root_cause_pod?.includes(selectedPod.service) || inc.summary?.includes(selectedPod.service)).length > 0 ? (
                      incidents
                        .filter(inc => inc.root_cause_pod?.includes(selectedPod.service) || inc.summary?.includes(selectedPod.service))
                        .map((incident, i) => (
                        <HyperIncidentCard 
                          key={incident.incident_id || incident.id || i} 
                          incident={incident} 
                          isActive={drawerIncident && (drawerIncident.incident_id === incident.incident_id || drawerIncident.summary === incident.summary)}
                          onClick={() => {
                            setActiveView('INCIDENTS');
                            setDrawerIncident(incident);
                          }}
                        />
                      ))
                    ) : (
                      <div className="p-16 text-center border border-dashed border-[#333333] rounded-[8px]">
                         <ShieldCheck size={24} className="mx-auto text-[#333333] mb-3" />
                         <p className="text-[13px] text-[#949494]">NODE SECURE</p>
                      </div>
                    )}
                  </div>
                </section>
              </>
            ) : (
              <div className="p-16 text-center border border-dashed border-[#333333] rounded-[8px] h-full flex flex-col items-center justify-center min-h-[400px]">
                 <BarChart3 size={32} className="text-[#333333] mb-4" />
                 <h3 className="text-[16px] font-bold text-[#F3F3F3] mb-2">Cluster Overview</h3>
                 <p className="text-[13px] text-[#949494] leading-relaxed">Select a node from the Service Array or the Topology Graph to view its contextual intelligence feed.</p>
              </div>
            )}
          </div>
        </div>
      </aside>
    </div>
  );
}
