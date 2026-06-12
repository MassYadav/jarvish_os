// jarvis-ui/src/store/useVoiceStore.ts
// Voice OS state management — drives UI animations, SFX triggers, and mic/speaker states.

import { create } from 'zustand';

export type VoicePhase =
  | 'idle'
  | 'connecting'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'tool_active';

interface VoiceState {
  /** Current phase of the voice pipeline state machine. */
  voicePhase: VoicePhase;

  /** Master toggle — true when a voice session is active. */
  isVoiceActive: boolean;

  /** Number of connection retry attempts consumed. */
  connectionRetries: number;

  /** Latest transcript fragment received from Gemini. */
  lastTranscript: string;

  /** Name of the tool currently being executed by the Vision daemon. */
  activeToolName: string;

  /** Task ID of the dispatched tool call for telemetry tracking. */
  activeToolTaskId: string;

  // --- Actions ---
  setVoicePhase: (phase: VoicePhase) => void;
  setIsVoiceActive: (active: boolean) => void;
  incrementRetries: () => void;
  resetRetries: () => void;
  setLastTranscript: (text: string) => void;
  setActiveTool: (toolName: string, taskId: string) => void;
  clearActiveTool: () => void;

  /** Full reset to idle state — call on session teardown. */
  resetVoiceState: () => void;
}

export const useVoiceStore = create<VoiceState>()((set) => ({
  voicePhase: 'idle',
  isVoiceActive: false,
  connectionRetries: 0,
  lastTranscript: '',
  activeToolName: '',
  activeToolTaskId: '',

  setVoicePhase: (phase) => set({ voicePhase: phase }),
  setIsVoiceActive: (active) => set({ isVoiceActive: active }),
  incrementRetries: () => set((s) => ({ connectionRetries: s.connectionRetries + 1 })),
  resetRetries: () => set({ connectionRetries: 0 }),
  setLastTranscript: (text) => set({ lastTranscript: text }),
  setActiveTool: (toolName, taskId) =>
    set({ activeToolName: toolName, activeToolTaskId: taskId, voicePhase: 'tool_active' }),
  clearActiveTool: () =>
    set({ activeToolName: '', activeToolTaskId: '', voicePhase: 'listening' }),

  resetVoiceState: () =>
    set({
      voicePhase: 'idle',
      isVoiceActive: false,
      connectionRetries: 0,
      lastTranscript: '',
      activeToolName: '',
      activeToolTaskId: '',
    }),
}));
