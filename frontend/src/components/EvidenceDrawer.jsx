import React, { useEffect, useState } from 'react';
import { Fingerprint, AlertCircle, X, ShieldAlert, Check, Copy, Play, History, GitBranch, Database } from 'lucide-react';

export function EvidenceDrawer({ incident, onClose }) {
  const [completedSteps, setCompletedSteps] = useState(new Set());
  const [executing, setExecuting] = useState(null);
  const [copied, setCopied] = useState(null);

  const toggleStep = (idx) => {
    const next = new Set(completedSteps);
    if (next.has(idx)) next.delete(idx);
    else next.add(idx);
    setCompletedSteps(next);
  };

  const handleExecute = async (idx) => {
    setExecuting(idx);
    try {
      await fetch(`http://localhost:8000/api/orchestrator/remediate/${incident.incident_id}?step_index=${idx}`, { method: 'POST' });
      toggleStep(idx);
    } catch (e) {
      console.error(e);
    }
    setExecuting(null);
  };

  const handleCopy = (text, idx) => {
    navigator.clipboard.writeText(text);
    setCopied(idx);
    setTimeout(() => setCopied(null), 2000);
  };

  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [onClose]);

  if (!incident) return null;

  return (
    <div className="fixed top-0 right-0 h-full w-[450px] bg-[#080808] border-l border-[#333333] p-8 z-[100] overflow-y-auto animate-in slide-in-from-right duration-300 shadow-2xl">
      <div className="flex justify-between items-center mb-8">
        <h2 className="text-[20px] font-bold text-[#F3F3F3] flex items-center gap-2">
          <Fingerprint size={20} className="text-[#E7C59A]" />
          Incident Evidence
        </h2>
        <button onClick={onClose} className="text-[#949494] hover:text-[#F3F3F3] transition-colors">
          <X size={24} />
        </button>
      </div>

      <div className="space-y-6">
        <div className="bg-[#101010] border border-[#333333] p-5 rounded-[8px]">
          <div className="flex items-center gap-2 mb-2">
            <ShieldAlert size={16} className="text-[#E7C59A]" />
            <h3 className="text-[14px] font-bold text-[#F3F3F3] leading-tight">{incident.summary || incident.title}</h3>
          </div>
          <p className="text-[13px] text-[#949494] leading-relaxed">
            {incident.explanation || "No explanation provided."}
          </p>
          
          {incident.causal_chain && incident.causal_chain.length > 0 && (
            <div className="mt-4 pt-4 border-t border-[#333333]">
              <p className="text-[12px] font-bold text-[#949494] uppercase tracking-wider mb-3 flex items-center gap-2">
                <GitBranch size={12} className="text-[#E7C59A]" /> Causal Propagation Chain
              </p>
              <div className="space-y-2">
                {incident.causal_chain.map((entry, i) => (
                  <div key={i} className="flex items-center justify-between text-[12px]">
                    <span className="text-[#F3F3F3] font-mono">{entry.pod}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-[#949494]">{entry.lag_seconds}s lag</span>
                      <span className={`font-bold ${entry.score > 0.7 ? 'text-[#ff4d4d]' : 'text-[#E7C59A]'}`}>{(entry.score * 100).toFixed(0)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="mt-4 pt-4 border-t border-[#333333]">
             <p className="text-[12px] font-bold text-[#949494] uppercase tracking-wider mb-2">Blast Radius</p>
             <div className="flex gap-2 flex-wrap">
                {(incident.affected_services || incident.propagation_path || []).map((srv, i) => (
                  <span key={i} className="text-[11px] bg-[#333333] text-[#F3F3F3] px-2 py-0.5 rounded-[4px]">{srv}</span>
                ))}
             </div>
          </div>
        </div>

        {incident.historical_context && incident.historical_context.length > 0 && (
          <div className="bg-[#00AC5C]/5 border border-[#00AC5C]/20 p-5 rounded-[8px]">
            <p className="text-[12px] font-bold text-[#00AC5C] uppercase tracking-wider mb-3 flex items-center gap-2">
              <Database size={12} /> Similar Historical Incidents
            </p>
            <div className="space-y-3">
              {incident.historical_context.slice(0, 2).map((ctx, i) => (
                <div key={i} className="text-[12px] text-[#949494] leading-relaxed border-l-2 border-[#00AC5C]/30 pl-3">
                  {ctx}
                </div>
              ))}
            </div>
          </div>
        )}

        <div>
           <div className="flex items-center justify-between mb-4">
             <p className="text-[13px] font-normal text-[#949494] uppercase tracking-[-0.007px]">Runbook & Evidence</p>
             {incident.is_historically_validated && (
               <div className="flex items-center gap-1.5 bg-[#00AC5C]/10 text-[#00AC5C] px-2 py-0.5 rounded-[4px] text-[11px] font-bold">
                 <History size={12} />
                 HISTORICAL SUCCESS: 100%
               </div>
             )}
           </div>
           {incident.runbook && incident.runbook.length > 0 ? (
             <div className="space-y-4">
                {incident.runbook.map((step, idx) => {
                  const isCompleted = completedSteps.has(idx);
                  const isPreviousCompleted = idx === 0 || completedSteps.has(idx - 1);
                  const canExecute = isPreviousCompleted && !isCompleted;

                  return (
                  <div key={idx} className={`bg-[#101010] border ${isCompleted ? 'border-[#00AC5C]/30 opacity-60' : 'border-[#333333]'} p-4 rounded-[8px] flex gap-4 transition-all`}>
                    <button 
                      onClick={() => { if (canExecute || isCompleted) toggleStep(idx); }}
                      disabled={!canExecute && !isCompleted}
                      className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 font-bold transition-all ${isCompleted ? 'bg-[#00AC5C] text-[#101010]' : canExecute ? 'bg-[#333333] hover:bg-[#E7C59A]/20 text-[#E7C59A]' : 'bg-[#1a1a1a] text-[#333333] border border-[#333333] cursor-not-allowed'}`}
                      title={!canExecute && !isCompleted ? "Complete previous step first" : "Toggle Step"}
                    >
                      {isCompleted ? <Check size={16} /> : step.step}
                    </button>
                    <div className="flex-1 min-w-0">
                      <p className={`text-[14px] font-bold mb-1 ${isCompleted ? 'text-[#00AC5C] line-through' : !isPreviousCompleted ? 'text-[#949494]' : 'text-[#F3F3F3]'}`}>{step.action}</p>
                      <p className={`text-[13px] mb-3 ${!isPreviousCompleted ? 'text-[#333333]' : 'text-[#949494]'}`}>{step.rationale}</p>
                      
                      {step.cli_command && !isCompleted && (
                        <div className={`bg-[#080808] border border-[#333333] rounded-[6px] p-2.5 font-mono text-[12px] text-[#E7C59A] flex items-center justify-between group ${!isPreviousCompleted ? 'opacity-30 grayscale pointer-events-none' : ''}`}>
                          <code className="truncate pr-4">{step.cli_command}</code>
                          <div className="flex items-center gap-2 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button onClick={() => handleCopy(step.cli_command, idx)} className="p-1.5 hover:bg-[#333333] rounded-[4px] text-[#949494] hover:text-[#F3F3F3]" title="Copy Command">
                              {copied === idx ? <Check size={14} className="text-[#00AC5C]" /> : <Copy size={14} />}
                            </button>
                            <button onClick={() => handleExecute(idx)} disabled={executing === idx || !canExecute} className="flex items-center gap-1 bg-[#E7C59A] text-[#101010] px-2 py-1 rounded-[4px] font-bold text-[11px] hover:bg-[#d6b48a]" title="Execute Automatically">
                              {executing === idx ? <span className="animate-pulse">RUNNING...</span> : <><Play size={10} fill="currentColor" /> EXECUTE</>}
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )})}
             </div>
           ) : (
             <div className="p-8 text-center border border-dashed border-[#333333] rounded-[8px]">
                <AlertCircle size={24} className="mx-auto text-[#333333] mb-3" />
                <p className="text-[13px] text-[#949494]">No structured runbook attached.</p>
             </div>
           )}
        </div>
      </div>
    </div>
  );
}
