"use client";

// jarvis-ui/src/components/chat/ModelSelector.tsx
// Inline provider + model selector that lives inside the chat input bar.

import { ChevronDown, Cpu, Zap, Bot } from "lucide-react";
import { useConfigStore, PROVIDER_MODELS, type Provider } from "@/store/useConfigStore";
import { useState, useRef, useEffect } from "react";

const PROVIDER_META: Record<Provider, { label: string; icon: React.ReactNode; color: string }> = {
  groq:       { label: "Groq",        icon: <Zap size={12} />,   color: "text-orange-400" },
  gemini:     { label: "Gemini",      icon: <Cpu size={12} />,   color: "text-blue-400"   },
  ollama:     { label: "Ollama",      icon: <Bot size={12} />,   color: "text-emerald-400"},
  openai:     { label: "OpenAI",      icon: <Cpu size={12} />,   color: "text-emerald-400"},
  anthropic:  { label: "Anthropic",   icon: <Cpu size={12} />,   color: "text-purple-400" },
  openrouter: { label: "OpenRouter",  icon: <Zap size={12} />,   color: "text-pink-400"   },
};

export default function ModelSelector() {
  const { activeProvider, activeModel, setActiveProvider, setActiveModel } = useConfigStore();
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const meta = PROVIDER_META[activeProvider];
  const models = PROVIDER_MODELS[activeProvider];
  const selectedModelLabel = models.find((m) => m.value === activeModel)?.label ?? activeModel;

  return (
    <div className="relative" ref={ref}>
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-700/60 hover:bg-slate-700 border border-slate-600/50 rounded-lg text-xs font-mono transition-colors group"
        title="Select AI provider and model"
      >
        <span className={meta.color}>{meta.icon}</span>
        <span className="text-slate-300 max-w-[120px] truncate hidden sm:block">
          {meta.label} / {selectedModelLabel}
        </span>
        <span className="text-slate-300 sm:hidden">{meta.label}</span>
        <ChevronDown
          size={12}
          className={`text-slate-500 transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </button>

      {/* Dropdown panel */}
      {isOpen && (
        <div className="absolute bottom-full mb-2 left-0 w-72 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl shadow-black/40 overflow-hidden z-50 animate-in fade-in slide-in-from-bottom-2 duration-150">
          
          {/* Provider row */}
          <div className="p-3 border-b border-slate-800">
            <p className="text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-2">Provider</p>
            <div className="grid grid-cols-3 gap-1.5">
              {(Object.keys(PROVIDER_META) as Provider[]).map((p) => {
                const pm = PROVIDER_META[p];
                return (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setActiveProvider(p)}
                    className={`flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg text-xs font-mono transition-all border ${
                      activeProvider === p
                        ? `bg-slate-700 border-slate-500 ${pm.color}`
                        : "bg-slate-800/50 border-slate-700/50 text-slate-500 hover:text-slate-300 hover:bg-slate-800"
                    }`}
                  >
                    <span className={activeProvider === p ? pm.color : ""}>{pm.icon}</span>
                    {pm.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Model row */}
          <div className="p-3">
            <p className="text-[10px] font-mono text-slate-500 uppercase tracking-widest mb-2">Model</p>
            <div className="space-y-1">
              {models.map((m) => (
                <button
                  key={m.value}
                  type="button"
                  onClick={() => { setActiveModel(m.value); setIsOpen(false); }}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs font-mono transition-colors ${
                    activeModel === m.value
                      ? "bg-blue-600/20 border border-blue-500/30 text-blue-300"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
                  }`}
                >
                  {m.label}
                  {activeModel === m.value && (
                    <span className="float-right text-blue-400">✓</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
