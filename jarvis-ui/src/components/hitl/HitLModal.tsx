"use client";

import { useState } from "react";
import { useTaskStore } from "@/store/useTaskStore";
import { ShieldAlert, Check, X } from "lucide-react";

export default function HitLModal({ onClose }: { onClose?: () => void }) {
  const { taskId, status, riskScore, updateStatus } = useTaskStore();
  const [isLoading, setIsLoading] = useState(false);

  if (status !== 'PENDING_APPROVAL') return null;

  const handleApprove = async () => {
    if (!taskId) return;

    setIsLoading(true);
    try {
      const response = await fetch(`http://localhost:8000/tasks/${taskId}/approve`, {
        method: 'POST',
      });

      if (response.ok) {
        console.log("Task approved, Brain resuming...");
        onClose?.();
      } else {
        console.error("Failed to approve task");
      }
    } catch (error) {
      console.error("Failed to approve:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeny = async () => {
    if (!taskId) return;

    setIsLoading(true);
    try {
      const response = await fetch(`http://localhost:8000/tasks/${taskId}/deny`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Deny request failed');
      }

      updateStatus('FAILED');
    } catch (error) {
      console.error(error);
      updateStatus('FAILED');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-amber-500/50 rounded-2xl shadow-2xl shadow-amber-900/20 w-full max-w-lg overflow-hidden animate-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="bg-amber-500/10 border-b border-amber-500/20 p-4 flex items-center gap-3">
          <ShieldAlert className="text-amber-500 animate-pulse" size={24} />
          <h2 className="text-amber-500 font-semibold tracking-wide">EXECUTION PAUSED: AUTHORIZATION REQUIRED</h2>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4 text-slate-300">
          <p>JARVIS has generated an execution plan that exceeds the safety threshold.</p>
          
          <div className="bg-black/50 p-4 rounded-lg font-mono text-sm border border-slate-800">
            <div className="flex justify-between mb-2">
              <span className="text-slate-500">Threat Level:</span>
              <span className="text-amber-500 font-bold">{riskScore} / 10</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Trigger:</span>
              <span className="text-slate-300">OS File Modification / Code Execution</span>
            </div>
          </div>
          
          <p className="text-sm text-slate-400">Do you wish to authorize this operation on your local machine?</p>
        </div>

        {/* Footer */}
        <div className="p-4 bg-slate-950 border-t border-slate-800 flex gap-3 justify-end">
          <button 
            onClick={handleDeny}
            disabled={isLoading}
            className="px-4 py-2 rounded-lg font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-colors flex items-center gap-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <X size={16} /> {isLoading ? 'Processing...' : 'Abort Task'}
          </button>
          <button 
            onClick={handleApprove}
            disabled={isLoading}
            className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg font-medium transition-colors flex items-center gap-2 shadow-lg shadow-amber-600/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Check size={16} /> {isLoading ? 'Processing...' : 'Authorize Execution'}
          </button>
        </div>
      </div>
    </div>
  );
}