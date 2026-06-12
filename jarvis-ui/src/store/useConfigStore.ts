// jarvis-ui/src/store/useConfigStore.ts
// Persists provider, model, and API key config in localStorage.
// This is the single source of truth for runtime LLM config passed to the backend.

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type Provider = 'groq' | 'gemini' | 'ollama' | 'openai' | 'anthropic' | 'openrouter';

export interface ModelOption {
  label: string;
  value: string;
}

export const PROVIDER_MODELS: Record<Provider, ModelOption[]> = {
  groq: [
    { label: 'Llama 3.1 70B (Fast)', value: 'llama-3.1-70b-versatile' },
    { label: 'Llama 3.1 8B (Ultra-Fast)', value: 'llama-3.1-8b-instant' },
    { label: 'Mixtral 8x7B', value: 'mixtral-8x7b-32768' },
    { label: 'Gemma 2 9B', value: 'gemma2-9b-it' },
  ],
  gemini: [
    { label: 'Gemini 1.5 Flash (Fast)', value: 'gemini-1.5-flash' },
    { label: 'Gemini 1.5 Pro (Smart)', value: 'gemini-1.5-pro' },
    { label: 'Gemini 2.0 Flash', value: 'gemini-2.0-flash' },
  ],
  ollama: [
    { label: 'Llama 3 (Local)', value: 'llama3' },
    { label: 'Mistral (Local)', value: 'mistral' },
    { label: 'CodeLlama (Local)', value: 'codellama' },
  ],
  openai: [
    { label: 'GPT-4o', value: 'gpt-4o' },
    { label: 'GPT-4o Mini (Fast)', value: 'gpt-4o-mini' },
    { label: 'GPT-4 Turbo', value: 'gpt-4-turbo' },
  ],
  anthropic: [
    { label: 'Claude 3.5 Sonnet', value: 'claude-3-5-sonnet-20240620' },
    { label: 'Claude 3 Haiku (Fast)', value: 'claude-3-haiku-20240307' },
    { label: 'Claude 3 Opus', value: 'claude-3-opus-20240229' },
  ],
  openrouter: [
    { label: 'Auto (Best Available)', value: 'auto' },
    { label: 'Llama 3.1 70B', value: 'meta-llama/llama-3.1-70b-instruct' },
  ],
};

// The dev UUID — matches what ApiKeyManager and api.ts use.
export const DEV_USER_UUID = '550e8400-e29b-41d4-a716-446655440000';

interface ConfigState {
  activeProvider: Provider;
  activeModel: string;
  groqApiKey: string;
  geminiApiKey: string;
  openaiApiKey: string;
  anthropicApiKey: string;
  openrouterApiKey: string;

  // Actions
  setActiveProvider: (provider: Provider) => void;
  setActiveModel: (model: string) => void;
  setGroqApiKey: (key: string) => void;
  setGeminiApiKey: (key: string) => void;
  setOpenaiApiKey: (key: string) => void;
  setAnthropicApiKey: (key: string) => void;
  setOpenrouterApiKey: (key: string) => void;

  /** Builds the config block to send with every task payload. */
  getTaskConfig: () => {
    active_provider: Provider;
    active_model: string;
    groq_api_key: string;
    gemini_api_key: string;
    openai_api_key: string;
    anthropic_api_key: string;
    openrouter_api_key: string;
  };
}

export const useConfigStore = create<ConfigState>()(
  persist(
    (set, get) => ({
      activeProvider: 'groq',
      activeModel: 'llama-3.1-70b-versatile',
      groqApiKey: '',
      geminiApiKey: '',
      openaiApiKey: '',
      anthropicApiKey: '',
      openrouterApiKey: '',

      setActiveProvider: (provider) => {
        // Auto-select the first model of the new provider
        const models = PROVIDER_MODELS[provider];
        set({ activeProvider: provider, activeModel: models[0]?.value ?? '' });
      },
      setActiveModel: (model) => set({ activeModel: model }),
      setGroqApiKey: (key) => set({ groqApiKey: key }),
      setGeminiApiKey: (key) => set({ geminiApiKey: key }),
      setOpenaiApiKey: (key) => set({ openaiApiKey: key }),
      setAnthropicApiKey: (key) => set({ anthropicApiKey: key }),
      setOpenrouterApiKey: (key) => set({ openrouterApiKey: key }),

      getTaskConfig: () => {
        const s = get();
        return {
          active_provider: s.activeProvider,
          active_model: s.activeModel,
          groq_api_key: s.groqApiKey,
          gemini_api_key: s.geminiApiKey,
          openai_api_key: s.openaiApiKey,
          anthropic_api_key: s.anthropicApiKey,
          openrouter_api_key: s.openrouterApiKey,
        };
      },
    }),
    {
      name: 'jarvis-config', // localStorage key
      // Only persist keys — activeProvider/model are safe to persist too
    }
  )
);
