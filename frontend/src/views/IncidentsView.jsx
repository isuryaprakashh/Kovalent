import React, { useEffect } from 'react';
import { AlertCircle, ShieldCheck } from 'lucide-react';
import { HyperIncidentCard } from '../components/Shared';

export function IncidentsView({ incidents, setDrawerIncident, drawerIncident }) {
  useEffect(() => {
    if (drawerIncident) {
      // Small timeout ensures the DOM has rendered the view switch before scrolling
      setTimeout(() => {
        document.getElementById('active-incident-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 100);
    }
  }, [drawerIncident]);
  return (
    <div className="flex-1 overflow-y-auto p-12 bg-[#101010]">
      <div className="max-w-5xl">
        <div className="mb-12">
          <h2 className="text-[28px] font-bold text-[#F3F3F3] tracking-tight">Incidents & Reports</h2>
          <p className="text-[14px] text-[#949494] mt-2">Comprehensive view of system anomalies and root cause analyses.</p>
        </div>
        
        <div className="space-y-6">
          {incidents.length > 0 ? (
            incidents.map((incident, i) => (
              <HyperIncidentCard 
                key={incident.incident_id || incident.id || i} 
                id={drawerIncident && (drawerIncident.incident_id === incident.incident_id || drawerIncident.summary === incident.summary) ? 'active-incident-card' : undefined}
                incident={incident} 
                isActive={drawerIncident && (drawerIncident.incident_id === incident.incident_id || drawerIncident.summary === incident.summary)}
                onClick={() => setDrawerIncident(incident)}
              />
            ))
          ) : (
            <div className="p-16 text-center border border-dashed border-[#333333] rounded-[8px] bg-[#080808]">
               <ShieldCheck size={32} className="mx-auto text-[#333333] mb-4" />
               <p className="text-[16px] font-bold text-[#F3F3F3] mb-1">System Secure</p>
               <p className="text-[14px] text-[#949494]">No active incidents or anomalies detected in the current window.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
