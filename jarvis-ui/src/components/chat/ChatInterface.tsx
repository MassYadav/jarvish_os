"use client";

// jarvis-ui/src/components/chat/ChatInterface.tsx

import { useState, useEffect, useRef } from "react";
import { Send, Cpu, Mic, MicOff } from "lucide-react";
import { useTaskStore } from "@/store/useTaskStore";
import { useConfigStore } from "@/store/useConfigStore";
import { api } from "@/lib/api";
import ModelSelector from "./ModelSelector";
import { useGeminiLive } from "@/hooks/useGeminiLive";
import { useVoiceStore } from "@/store/useVoiceStore";

export default function ChatInterface() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([
    { role: "system", content: "JARVIS Cognitive Mesh initialized. Awaiting parameters." },
  ]);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const { startTask, setTaskId, updateStatus, setRiskScore, setFinalResult, status, taskId } =
    useTaskStore();

  const { getTaskConfig, activeProvider, activeModel } = useConfigStore();
  
  const { startVoiceSession, stopVoiceSession, isVoiceActive, voicePhase } = useGeminiLive();
  const { activeToolName } = useVoiceStore();

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, status, voicePhase]);

  const formatTaskResult = (resultPayload: unknown): string => {
    if (typeof resultPayload === "string") {
      return resultPayload.trim() || "Execution complete.";
    }
    if (resultPayload && typeof resultPayload === "object") {
      const payload = resultPayload as Record<string, unknown>;
      if (typeof payload.output === "string" && payload.output.trim()) return payload.output;
      if (typeof payload.message === "string" && payload.message.trim()) return payload.message;
    }
    return "Execution complete.";
  };

  // POLLING ENGINE: Checks task status every 2 seconds while running
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (status === "RUNNING" && taskId) {
      interval = setInterval(async () => {
        try {
          const data = await api.getTaskStatus(taskId);

          if (data.status === "PENDING_APPROVAL") {
            setRiskScore(data.risk_score || 7);
            updateStatus("PENDING_APPROVAL");
          } else if (data.status === "COMPLETED" || data.status === "FAILED") {
            updateStatus(data.status);
            const finalMessage = formatTaskResult(data.result_payload);
            setFinalResult(finalMessage);
            setMessages((prev) => [...prev, { role: "system", content: finalMessage }]);
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
    if (!input.trim() || status === "RUNNING") return;

    const userMessage = input;
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setInput("");
    startTask(userMessage);

    // Grab the full config snapshot at send time
    const config = getTaskConfig();

    try {
      const response = await api.submitTask(userMessage, config);
      setTaskId(response.task_id);
    } catch {
      updateStatus("FAILED");
      setMessages((prev) => [
        ...prev,
        {
          role: "system",
          content: "CRITICAL: Cannot connect to FastAPI backend on port 8000.",
        },
      ]);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-screen bg-slate-900 text-slate-100 min-w-0">
      
      {/* Active model badge in header */}
      <div className="h-16 flex items-center justify-between px-4 md:px-8 border-b border-slate-800 bg-slate-950/50 shrink-0">
        <div className="flex items-center gap-2">
          <Cpu size={16} className="text-blue-400" />
          <span className="text-sm font-mono text-slate-400">Active Thread</span>
          
          {isVoiceActive && (
            <div className="ml-4 px-2 py-1 bg-blue-900/40 border border-blue-500/30 rounded flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${voicePhase === 'listening' ? 'bg-green-500 animate-pulse' : voicePhase === 'speaking' ? 'bg-blue-400 animate-pulse' : 'bg-yellow-500'}`} />
              <span className="text-xs font-mono text-blue-200">VOICE: {voicePhase.toUpperCase()}</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-slate-600">ENGINE:</span>
          <span className="text-blue-400 uppercase">{activeProvider}</span>
          <span className="text-slate-700">/</span>
          <span className="text-slate-400 truncate max-w-[160px]">{activeModel}</span>
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              status === "RUNNING"
                ? "bg-blue-500 animate-pulse"
                : status === "COMPLETED"
                ? "bg-emerald-500"
                : status === "FAILED"
                ? "bg-red-500"
                : "bg-slate-600"
            }`}
          />
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex gap-4 max-w-4xl mx-auto ${
              msg.role === "user" ? "flex-row-reverse" : "flex-row"
            }`}
          >
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                msg.role === "user"
                  ? "bg-blue-600"
                  : "bg-slate-800 border border-slate-700"
              }`}
            >
              {msg.role === "system" ? (
                <Cpu size={16} className="text-blue-400" />
              ) : (
                <span className="text-xs font-bold">U</span>
              )}
            </div>
            <div
              className={`px-4 py-3 rounded-2xl max-w-[80%] ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-slate-800 text-slate-300"
              }`}
            >
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
            </div>
          </div>
        ))}

        {/* Thinking indicator */}
        {status === "RUNNING" && (
          <div className="flex gap-4 max-w-4xl mx-auto flex-row">
            <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-slate-800 border border-slate-700">
              <Cpu size={16} className="text-blue-400 animate-pulse" />
            </div>
            <div className="px-4 py-3 rounded-2xl bg-slate-800 text-slate-300 flex items-center gap-2">
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" />
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
          </div>
        )}

        {/* Voice Active Tool indicator */}
        {voicePhase === 'tool_active' && activeToolName && (
           <div className="flex gap-4 max-w-4xl mx-auto flex-row">
             <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-purple-900 border border-purple-700">
               <Cpu size={16} className="text-purple-400 animate-spin" />
             </div>
             <div className="px-4 py-3 rounded-2xl bg-slate-800 border border-purple-800 text-slate-300 flex items-center gap-3">
               <span className="text-sm font-mono text-purple-300">EXECUTING TOOL: {activeToolName}</span>
               <span className="w-2 h-2 bg-purple-500 rounded-full animate-pulse" />
             </div>
           </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="p-4 md:p-6 border-t border-slate-800 bg-slate-950/30">
        <div className="max-w-4xl mx-auto space-y-2">
          {/* Model selector row */}
          <div className="flex items-center gap-2 pl-1">
            <ModelSelector />
          </div>

          {/* Text input + send */}
          <form onSubmit={handleSend} className="relative flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={status === "RUNNING"}
              placeholder={
                status === "RUNNING" ? "JARVIS is executing..." : "Command JARVIS..."
              }
              className="flex-1 bg-slate-800 border border-slate-700 rounded-xl pl-4 pr-4 py-4 text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-blue-500 shadow-lg disabled:opacity-50 transition-all"
            />
            <button
              type="button"
              onClick={isVoiceActive ? stopVoiceSession : startVoiceSession}
              className={`shrink-0 p-3.5 rounded-xl transition-colors shadow-lg ${
                isVoiceActive 
                  ? 'bg-red-600 hover:bg-red-500 shadow-red-600/20 text-white' 
                  : 'bg-slate-700 hover:bg-slate-600 text-slate-300'
              }`}
              title={isVoiceActive ? "Stop Voice OS" : "Start Voice OS"}
            >
              {isVoiceActive ? <MicOff size={18} /> : <Mic size={18} />}
            </button>
            <button
              type="submit"
              disabled={status === "RUNNING" || !input.trim()}
              className="shrink-0 p-3.5 bg-blue-600 hover:bg-blue-500 active:bg-blue-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white rounded-xl transition-colors shadow-lg shadow-blue-600/20"
              title="Send command"
            >
              <Send size={18} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}