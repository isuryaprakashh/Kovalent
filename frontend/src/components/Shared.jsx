import React from 'react';
import { ChevronRight } from 'lucide-react';

export function NavLink({ label, active, onClick }) {
  return (
    <a 
      href="#" 
      onClick={(e) => { e.preventDefault(); onClick(); }} 
      className={`tracking-wide transition-all ${
        active ? 'text-[#F3F3F3] border-b border-[#F3F3F3]' : 'text-[#949494] hover:text-[#F3F3F3]'
      }`}
    >
      {label}
    </a>
  );
}

export function StatBlock({ label, value }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[13px] text-[#949494] tracking-tight">{label}</span>
      <span className="text-[21px] font-bold text-[#F3F3F3] leading-none">{value}</span>
    </div>
  );
}

export function HyperPodCard({ pod, isSelected, onClick }) {
  const isAnomalous = pod.error_rate_per_minute > 2;
  const cpuPercent = (pod.cpu_millicores / Math.max(pod.cpu_limit_millicores, 1) * 100).toFixed(0);

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

export function HyperIncidentCard({ incident, onClick, isActive, id }) {
  return (
    <div id={id} className={`border-l-[4px] p-6 space-y-4 transition-all cursor-pointer ${isActive ? 'border-[#E7C59A] bg-[#221c14] shadow-[inset_0_0_30px_rgba(231,197,154,0.1)]' : 'bg-[#101010] border-[#333333] hover:border-[#E7C59A]/50 hover:bg-[#080808]'}`} onClick={onClick}>
      <div className="flex justify-between items-center">
        <span className="text-[13px] font-bold text-[#E7C59A] uppercase tracking-wider">Anomaly</span>
        <span className="text-[13px] font-input text-[#949494] tracking-[-0.037em]">{incident.generated_at ? new Date(incident.generated_at).toLocaleTimeString() : incident.timestamp ? new Date(incident.timestamp).toLocaleTimeString() : ''}</span>
      </div>
      <h4 className="text-[18px] font-bold text-[#F3F3F3] leading-tight tracking-tight">{incident.summary || incident.title}</h4>
      <p className="text-[16px] text-[#949494] leading-relaxed font-normal">
        {incident.explanation || "No explanation provided."}
      </p>
      <div className="pt-4 flex items-center gap-2 text-[13px] text-[#E7C59A] font-bold hover:underline">
        READ INCIDENT LOG <ChevronRight size={14} />
      </div>
    </div>
  );
}

export function HyperMetric({ label, value }) {
  return (
    <div>
      <p className="text-[13px] text-[#949494] mb-2 uppercase tracking-tight">{label}</p>
      <p className="text-[23px] font-bold text-[#F3F3F3] tracking-tight leading-none">{value}</p>
    </div>
  );
}
