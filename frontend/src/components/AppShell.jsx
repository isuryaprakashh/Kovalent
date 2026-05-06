import React, { useState, useEffect } from 'react';
import { NavLink } from './Shared';
import { OverviewView } from '../views/OverviewView';
import { IncidentsView } from '../views/IncidentsView';
import { EvidenceDrawer } from './EvidenceDrawer';
import { ChatDrawer } from './ChatDrawer';
import { fetchDashboardData } from '../api/client';

export function AppShell() {
  const [activeView, setActiveView] = useState('TOPOLOGY');
  const [data, setData] = useState({ pods: [], graph: { nodes: [], edges: [] }, incidents: [] });
  const [selectedPodId, setSelectedPodId] = useState(null);
  const [drawerIncident, setDrawerIncident] = useState(null);
  const [isChatOpen, setIsChatOpen] = useState(false);

  const loadData = async () => {
    try {
      const result = await fetchDashboardData();
      setData(result);
      if (!selectedPodId && result.pods.length > 0) {
        const sorted = [...result.pods].sort((a, b) => b.error_rate_per_minute - a.error_rate_per_minute);
        setSelectedPodId(sorted[0].pod);
      }
    } catch (err) {
      // API client already logs the error
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 8000);
    return () => clearInterval(interval);
  }, [selectedPodId]);

  return (
    <div className="flex h-screen bg-[#101010] text-[#F3F3F3] font-aeonik overflow-hidden">
      {/* Header */}
      <header className="fixed top-0 w-full h-14 flex items-center px-8 z-50 bg-[#101010]/80 backdrop-blur-md border-b border-[#333333]">
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-12">
            <div className="text-lg font-bold tracking-tight">Kovalent <span className="text-[#E7C59A] text-[10px] ml-2 font-normal border border-[#E7C59A]/30 px-1.5 py-0.5 rounded">NEW</span></div>
            <nav className="flex gap-8 text-[14px] font-normal">
              <NavLink label="TOPOLOGY" active={activeView === 'TOPOLOGY'} onClick={() => setActiveView('TOPOLOGY')} />
              <NavLink label="INCIDENTS" active={activeView === 'INCIDENTS'} onClick={() => setActiveView('INCIDENTS')} />
            </nav>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2 text-[13px] font-input text-[#00AC5C]">
               <div className="w-1.5 h-1.5 bg-[#00AC5C] rounded-full shadow-[0_0_8px_#00AC5C]" />
               SYSTEM NOMINAL
            </div>
            <button 
              onClick={() => setIsChatOpen(true)}
              className="bg-[#E7C59A] text-[#101010] font-bold text-[13px] px-5 py-1.5 rounded-[8px] hover:bg-[#d6b48a] transition-all shadow-lg shadow-[#E7C59A]/10 active:scale-95"
            >
              LET'S CHAT
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="flex-1 mt-14 flex overflow-hidden">
        {activeView === 'TOPOLOGY' && (
          <OverviewView 
            data={data} 
            selectedPodId={selectedPodId} 
            setSelectedPodId={setSelectedPodId} 
            setDrawerIncident={setDrawerIncident} 
            setActiveView={setActiveView}
            drawerIncident={drawerIncident}
          />
        )}
        {activeView === 'INCIDENTS' && (
          <IncidentsView 
            incidents={data.incidents} 
            setDrawerIncident={setDrawerIncident} 
            drawerIncident={drawerIncident}
          />
        )}
      </div>

      {/* Modals/Drawers */}
      <EvidenceDrawer incident={drawerIncident} onClose={() => setDrawerIncident(null)} />
      <ChatDrawer isOpen={isChatOpen} onClose={() => setIsChatOpen(false)} data={data} />
    </div>
  );
}
