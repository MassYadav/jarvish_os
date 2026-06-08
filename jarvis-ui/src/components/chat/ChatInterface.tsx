"use client";

import { useState, useEffect } from "react";
import { Send, Cpu } from "lucide-react";
import { useTaskStore } from "@/store/useTaskStore";
import { api } from "@/lib/api";

export default function ChatInterface() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([
    { role: "system", content: "JARVIS Cognitive Mesh initialized. Awaiting parameters." }
  ]);
  
  const { startTask, setTaskId, updateStatus, setRiskScore, setFinalResult, status, taskId } = useTaskStore();

  // POLLING ENGINE: Checks the database every 2 seconds while a task is running
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (status === 'RUNNING' && taskId) {
      interval = setInterval(async () => {
        try {
          const data = await api.getTaskStatus(taskId);
          
          if (data.status === 'PENDING_APPROVAL') {
            setRiskScore(data.risk_score || 7);
            updateStatus('PENDING_APPROVAL');
          } else if (data.status === 'COMPLETED' || data.status === 'FAILED') {
            updateStatus(data.status);
            setFinalResult(data.result_payload || "Execution complete.");
            setMessages(prev => [...prev, { role: "system", content: data.result_payload }]);
          }
        } catch (error) {
          console.error("Polling error:", error);
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [status, taskId, updateStatus, setRiskScore, setFinalResult]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || status === 'RUNNING') return;
    
    const userMessage = input;
    setMessages(prev => [...prev, { role: "user", content: userMessage }]);
    setInput("");
    startTask(userMessage);

    try {
      // 1. Send to FastAPI
      const response = await api.submitTask(userMessage);
      // 2. Save the real UUID so the polling engine starts watching it
      setTaskId(response.task_id);
    } catch (error) {
      updateStatus('FAILED');
      setMessages(prev => [...prev, { role: "system", content: "CRITICAL: Cannot connect to FastAPI backend on port 8000." }]);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-screen bg-slate-900 text-slate-100">
      <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex gap-4 max-w-4xl mx-auto ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
              msg.role === "user" ? "bg-blue-600" : "bg-slate-800 border border-slate-700"
            }`}>
              {msg.role === "system" ? <Cpu size={16} className="text-blue-400" /> : "U"}
            </div>
            <div className={`px-4 py-3 rounded-2xl max-w-[80%] ${
              msg.role === "user" ? "bg-blue-600 text-white" : "bg-slate-800 text-slate-300"
            }`}>
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
            </div>
          </div>
        ))}
        
        {status === 'RUNNING' && (
          <div className="flex gap-4 max-w-4xl mx-auto flex-row">
            <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-slate-800 border border-slate-700">
              <Cpu size={16} className="text-blue-400 animate-pulse" />
            </div>
            <div className="px-4 py-3 rounded-2xl bg-slate-800 text-slate-300 flex items-center gap-2">
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></span>
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></span>
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></span>
            </div>
          </div>
        )}
      </div>

      <div className="p-4 md:p-8 max-w-4xl mx-auto w-full">
        <form onSubmit={handleSend} className="relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={status === 'RUNNING'}
            placeholder={status === 'RUNNING' ? "JARVIS is executing..." : "Command JARVIS..."}
            className="w-full bg-slate-800 border border-slate-700 rounded-xl pl-4 pr-12 py-4 text-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 shadow-lg disabled:opacity-50"
          />
          <button type="submit" disabled={status === 'RUNNING'} className="absolute right-3 p-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 text-white rounded-lg transition-colors">
            <Send size={18} />
          </button>
        </form>
      </div>
    </div>
  );
}