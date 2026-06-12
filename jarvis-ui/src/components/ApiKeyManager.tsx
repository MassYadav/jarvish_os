"use client";

// jarvis-ui/src/components/ApiKeyManager.tsx
// Manages API keys — saves to Zustand (localStorage) and the backend AES Vault.

import React, { useState } from "react";
import { api } from "@/lib/api";
import { useConfigStore, type Provider } from "@/store/useConfigStore";
import { KeyRound, Eye, EyeOff, CheckCircle2, AlertCircle, Loader2, Shield } from "lucide-react";

type ProviderKeyConfig = {
  label: string;
  placeholder: string;
  color: string;
  setter: (key: string) => void;
  currentValue: string;
};

export default function ApiKeyManager() {
  const {
    groqApiKey, setGroqApiKey,
    geminiApiKey, setGeminiApiKey,
    openaiApiKey, setOpenaiApiKey,
    anthropicApiKey, setAnthropicApiKey,
    openrouterApiKey, setOpenrouterApiKey,
  } = useConfigStore();

  const [vaultProvider, setVaultProvider] = useState<Provider>("groq");
  const [vaultKey, setVaultKey] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [vaultStatus, setVaultStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [vaultMessage, setVaultMessage] = useState("");

  // Maps providers → config store state
  const providerConfigs: Record<string, ProviderKeyConfig> = {
    groq:       { label: "Groq (LPU)",      placeholder: "gsk_...",   color: "text-orange-400", setter: setGroqApiKey,       currentValue: groqApiKey       },
    gemini:     { label: "Google Gemini",   placeholder: "AIza...",   color: "text-blue-400",   setter: setGeminiApiKey,     currentValue: geminiApiKey     },
    openai:     { label: "OpenAI",          placeholder: "sk-...",    color: "text-emerald-400",setter: setOpenaiApiKey,     currentValue: openaiApiKey     },
    anthropic:  { label: "Anthropic",       placeholder: "sk-ant-...",color: "text-purple-400", setter: setAnthropicApiKey,  currentValue: anthropicApiKey  },
    openrouter: { label: "OpenRouter",      placeholder: "sk-or-...", color: "text-pink-400",   setter: setOpenrouterApiKey, currentValue: openrouterApiKey },
  };

  const handleLocalSave = (provider: string, key: string) => {
    const cfg = providerConfigs[provider];
    if (cfg && key.trim()) {
      cfg.setter(key.trim());
    }
  };

  const handleVaultSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!vaultKey.trim()) return;

    setVaultStatus("loading");
    setVaultMessage("Encrypting and securing in AES-256 Vault...");

    try {
      await api.secureApiKey(vaultProvider, vaultKey.trim());
      // Also persist locally so the next task dispatch can use it immediately
      handleLocalSave(vaultProvider, vaultKey.trim());
      setVaultStatus("success");
      setVaultMessage(`${vaultProvider.toUpperCase()} key secured in Vault + localStorage.`);
      setVaultKey("");

      setTimeout(() => {
        setVaultStatus("idle");
        setVaultMessage("");
      }, 3500);
    } catch (error: unknown) {
      setVaultStatus("error");
      setVaultMessage(error instanceof Error ? error.message : "Vault operation failed.");
    }
  };

  const maskedValue = (val: string) =>
    val ? `${val.slice(0, 4)}${"•".repeat(Math.min(val.length - 4, 20))}` : "";

  return (
    <div className="w-full max-w-2xl space-y-6">

      {/* Section 1: Quick local key storage (no vault round-trip) */}
      <div className="bg-slate-800 border border-slate-700 p-6 rounded-xl shadow-xl">
        <h2 className="text-base font-semibold text-slate-200 mb-1 flex items-center gap-2">
          <KeyRound size={16} className="text-blue-400" />
          Local Session Keys
        </h2>
        <p className="text-xs text-slate-500 mb-5">
          Stored in localStorage — available immediately for task dispatch.
        </p>

        <div className="space-y-3">
          {Object.entries(providerConfigs).map(([providerKey, cfg]) => (
            <div key={providerKey} className="flex items-center gap-3">
              <label className={`w-32 text-xs font-mono shrink-0 ${cfg.color}`}>
                {cfg.label}
              </label>
              <div className="flex-1 relative">
                <input
                  type="password"
                  value={cfg.currentValue}
                  onChange={(e) => cfg.setter(e.target.value)}
                  placeholder={cfg.placeholder}
                  className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-2 font-mono outline-none focus:ring-1 focus:ring-blue-500 transition-all placeholder-slate-600"
                />
                {cfg.currentValue && (
                  <span className="absolute right-2 top-1/2 -translate-y-1/2">
                    <CheckCircle2 size={12} className="text-emerald-500" />
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Section 2: Vault encryption (backend AES-256) */}
      <div className="bg-slate-800 border border-slate-700 p-6 rounded-xl shadow-xl">
        <h2 className="text-base font-semibold text-slate-200 mb-1 flex items-center gap-2">
          <Shield size={16} className="text-amber-400" />
          Cryptographic Vault
        </h2>
        <p className="text-xs text-slate-500 mb-5">
          Encrypts the key server-side with AES-256-GCM. Also writes to localStorage.
        </p>

        <form onSubmit={handleVaultSave} className="space-y-4">
          {/* Provider selector */}
          <div>
            <label className="block text-xs font-mono text-slate-400 mb-1.5 uppercase tracking-widest">
              Provider Core
            </label>
            <select
              value={vaultProvider}
              onChange={(e) => setVaultProvider(e.target.value as Provider)}
              className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded-lg focus:ring-1 focus:ring-blue-500 block p-2.5 outline-none appearance-none"
            >
              {Object.entries(providerConfigs).map(([k, cfg]) => (
                <option key={k} value={k}>{cfg.label}</option>
              ))}
            </select>
          </div>

          {/* Key input */}
          <div>
            <label className="block text-xs font-mono text-slate-400 mb-1.5 uppercase tracking-widest">
              Authorization Key
            </label>
            <div className="relative">
              <input
                type={showKey ? "text" : "password"}
                value={vaultKey}
                onChange={(e) => setVaultKey(e.target.value)}
                placeholder={providerConfigs[vaultProvider]?.placeholder ?? "Enter key..."}
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-sm rounded-lg focus:ring-1 focus:ring-blue-500 block pl-3 pr-10 py-2.5 outline-none font-mono"
                required
              />
              <button
                type="button"
                onClick={() => setShowKey((v) => !v)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
              >
                {showKey ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>

            {/* Show current stored value hint */}
            {providerConfigs[vaultProvider]?.currentValue && (
              <p className="text-[11px] font-mono text-slate-600 mt-1">
                Current: {maskedValue(providerConfigs[vaultProvider].currentValue)}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={vaultStatus === "loading" || !vaultKey.trim()}
            className="w-full flex items-center justify-center gap-2 text-white bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:bg-slate-700 disabled:text-slate-500 font-medium rounded-lg text-sm px-5 py-2.5 text-center transition-all"
          >
            {vaultStatus === "loading" ? (
              <><Loader2 size={15} className="animate-spin" /> ENCRYPTING...</>
            ) : (
              <><Shield size={15} /> SECURE IN VAULT</>
            )}
          </button>

          {/* Status message */}
          {vaultMessage && (
            <div
              className={`text-xs mt-2 p-3 rounded-lg border flex items-center gap-2 ${
                vaultStatus === "error"
                  ? "bg-red-900/20 border-red-800/50 text-red-400"
                  : vaultStatus === "success"
                  ? "bg-emerald-900/20 border-emerald-800/50 text-emerald-400"
                  : "bg-blue-900/20 border-blue-800/50 text-blue-400"
              }`}
            >
              {vaultStatus === "error" ? (
                <AlertCircle size={13} className="shrink-0" />
              ) : vaultStatus === "success" ? (
                <CheckCircle2 size={13} className="shrink-0" />
              ) : (
                <Loader2 size={13} className="animate-spin shrink-0" />
              )}
              {vaultMessage}
            </div>
          )}
        </form>
      </div>
    </div>
  );
}