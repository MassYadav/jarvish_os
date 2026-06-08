"use client";

import { useTaskStore } from "@/store/useTaskStore";
import { Activity, CheckCircle2, CircleDashed, ShieldAlert, Terminal } from "lucide-react";

export default function ExecutionObserver() {
  const { status, intent } = useTaskStore();

  // If no task is active, hide the panel completely
  if (status === 'IDLE') return null;

  return (
    <aside className="w-80 bg-slate-950 border-l border-slate-800 flex flex-col h-screen text-slate-300 animate-in slide-in-from-right-8 duration-300">
      
      {/* Header */}
      <div className="h-16 flex items-center gap-3 px-4 border-b border-slate-800 bg-slate-900/50">
        <Activity size={18} className="text-blue-400 animate-pulse" />
        <span className="font-mono text-sm font-semibold tracking-wider text-slate-100">EXECUTION OBSERVER</span>
      </div>

      {/* Active Intent */}
      <div className="p-4 border-b border-slate-800 bg-slate-900/20">
        <p className="text-xs text-slate-500 font-mono mb-1">CURRENT INTENT</p>
        <p className="text-sm text-slate-300 line-clamp-3">{intent}</p>
      </div>

      {/* Timeline / DAG Steps */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6 font-mono text-sm">
        <TimelineStep 
          label="1. Retrieving Context" 
          state={status === 'RUNNING' ? 'loading' : 'done'} 
        />
        <TimelineStep 
          label="2. Generating DAG Plan" 
          state={status === 'RUNNING' ? 'loading' : 'done'} 
        />
        <TimelineStep 
          label="3. Security Review" 
          state={status === 'PENDING_APPROVAL' ? 'warning' : (status === 'RUNNING' ? 'waiting' : 'done')} 
        />
        <TimelineStep 
          label="4. Executing Graph" 
          state={status === 'COMPLETED' ? 'done' : 'waiting'} 
        />
      </div>

      {/* Terminal Output Mock */}
      <div className="h-48 bg-black border-t border-slate-800 p-3 font-mono text-xs text-green-400 overflow-y-auto">
        <div className="flex items-center gap-2 mb-2 text-slate-500">
          <Terminal size={14} />
          <span>system.stdout</span>
        </div>
        <p className="opacity-75">{'>'} Booting cognitive mesh...</p>
        <p className="opacity-75">{'>'} State: {status}</p>
      </div>
    </aside>
  );
}

// Sub-component for the visual timeline steps
function TimelineStep({ label, state }: { label: string, state: 'waiting' | 'loading' | 'done' | 'warning' }) {
  return (
    <div className="flex gap-4 items-start">
      <div className="mt-0.5">
        {state === 'waiting' && <CircleDashed size={16} className="text-slate-700" />}
        {state === 'loading' && <CircleDashed size={16} className="text-blue-500 animate-spin" />}
        {state === 'done' && <CheckCircle2 size={16} className="text-emerald-500" />}
        {state === 'warning' && <ShieldAlert size={16} className="text-amber-500 animate-pulse" />}
      </div>
      <span className={`${
        state === 'waiting' ? 'text-slate-600' : 
        state === 'warning' ? 'text-amber-500 font-bold' : 'text-slate-300'
      }`}>
        {label}
      </span>
    </div>
  );
}