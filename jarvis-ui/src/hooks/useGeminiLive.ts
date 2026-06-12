'use client';

import { useCallback, useRef, useEffect } from 'react';
import { useConfigStore } from '@/store/useConfigStore';
import { useVoiceStore } from '@/store/useVoiceStore';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const GATEWAY_WS_URL = 'ws://localhost:8000/v1/stream/voice/';
const TARGET_SAMPLE_RATE = 16000;
const OUTPUT_SAMPLE_RATE = 24000;
const CAPTURE_BUFFER_SIZE = 4096;
const MAX_RECONNECT_ATTEMPTS = 3;
const BARGE_IN_AMPLITUDE_THRESHOLD = 0.08;

// ---------------------------------------------------------------------------
// Audio Utility Functions
// ---------------------------------------------------------------------------

function float32ToInt16(buffer: Float32Array): Int16Array {
  const output = new Int16Array(buffer.length);
  for (let i = 0; i < buffer.length; i++) {
    const s = Math.max(-1, Math.min(1, buffer[i]));
    output[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  return output;
}

function int16ToFloat32(buffer: Int16Array): Float32Array {
  const output = new Float32Array(buffer.length);
  for (let i = 0; i < buffer.length; i++) {
    output[i] = buffer[i] / (buffer[i] < 0 ? 0x8000 : 0x7FFF);
  }
  return output;
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

function calculateRMS(buffer: Float32Array): number {
  let sum = 0;
  for (let i = 0; i < buffer.length; i++) {
    sum += buffer[i] * buffer[i];
  }
  return Math.sqrt(sum / buffer.length);
}

function downsample(buffer: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (fromRate === toRate) return buffer;
  const ratio = fromRate / toRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  for (let i = 0; i < newLength; i++) {
    const srcIndex = Math.round(i * ratio);
    result[i] = buffer[Math.min(srcIndex, buffer.length - 1)];
  }
  return result;
}

// ---------------------------------------------------------------------------
// Main Hook
// ---------------------------------------------------------------------------

export function useGeminiLive() {
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const captureCtxRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  
  const playbackCtxRef = useRef<AudioContext | null>(null);
  const playbackQueueRef = useRef<AudioBuffer[]>([]);
  const isPlayingRef = useRef(false);
  
  const retriesRef = useRef(0);

  // SFX Refs
  const sfxCtxRef = useRef<AudioContext | null>(null);
  const humOscRef = useRef<OscillatorNode | null>(null);
  const humGainRef = useRef<GainNode | null>(null);

  const {
    setVoicePhase,
    setIsVoiceActive,
    setLastTranscript,
    setActiveTool,
    clearActiveTool,
    resetVoiceState,
  } = useVoiceStore();

  const { geminiApiKey } = useConfigStore();

  // -----------------------------------------------------------------
  // SFX Engine
  // -----------------------------------------------------------------

  const getSfxContext = useCallback(() => {
    if (!sfxCtxRef.current || sfxCtxRef.current.state === 'closed') {
      sfxCtxRef.current = new AudioContext();
    }
    if (sfxCtxRef.current.state === 'suspended') {
      sfxCtxRef.current.resume();
    }
    return sfxCtxRef.current;
  }, []);

  const playWakeChime = useCallback(() => {
    const ctx = getSfxContext();
    const now = ctx.currentTime;
    
    // High-frequency sine-wave wake chime
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, now); // A5
    osc.frequency.exponentialRampToValueAtTime(1760, now + 0.1); // Slide up to A6

    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(0.3, now + 0.05);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);

    osc.connect(gain).connect(ctx.destination);
    osc.start(now);
    osc.stop(now + 0.35);
  }, [getSfxContext]);

  const startProcessingHum = useCallback(() => {
    if (humOscRef.current) return;

    const ctx = getSfxContext();
    const now = ctx.currentTime;

    // Ambient triangle-wave low computational data hum
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'triangle';
    osc.frequency.setValueAtTime(55, now); // Low hum (A1)

    // LFO for modulation
    const lfo = ctx.createOscillator();
    const lfoGain = ctx.createGain();
    lfo.type = 'sine';
    lfo.frequency.value = 2; // 2Hz throb
    lfoGain.gain.value = 5; // modulate freq by +/- 5Hz
    lfo.connect(lfoGain).connect(osc.frequency);
    lfo.start(now);

    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(0.08, now + 0.5); // Fade in

    osc.connect(gain).connect(ctx.destination);
    osc.start(now);

    humOscRef.current = osc;
    humGainRef.current = gain;
    (osc as any).__lfo = lfo; // keep ref for cleanup
  }, [getSfxContext]);

  const stopProcessingHum = useCallback(() => {
    if (!humOscRef.current || !humGainRef.current) return;

    const ctx = getSfxContext();
    const now = ctx.currentTime;
    const gain = humGainRef.current;
    const osc = humOscRef.current;
    const lfo = (osc as any).__lfo;

    // Fade out
    gain.gain.linearRampToValueAtTime(0.001, now + 0.3);

    setTimeout(() => {
      try { osc.stop(); } catch { /* ignore */ }
      try { lfo?.stop(); } catch { /* ignore */ }
      osc.disconnect();
      lfo?.disconnect();
      gain.disconnect();
    }, 350);

    humOscRef.current = null;
    humGainRef.current = null;
  }, [getSfxContext]);

  // -----------------------------------------------------------------
  // Audio Playback Engine (24kHz PCM → speakers)
  // -----------------------------------------------------------------

  const enqueuePlayback = useCallback((base64Audio: string) => {
    if (!playbackCtxRef.current) {
      playbackCtxRef.current = new AudioContext({ sampleRate: OUTPUT_SAMPLE_RATE });
    }
    const ctx = playbackCtxRef.current;

    const raw = base64ToArrayBuffer(base64Audio);
    const int16 = new Int16Array(raw);
    const float32 = int16ToFloat32(int16);

    const audioBuffer = ctx.createBuffer(1, float32.length, OUTPUT_SAMPLE_RATE);
    audioBuffer.getChannelData(0).set(float32);
    playbackQueueRef.current.push(audioBuffer);

    if (!isPlayingRef.current) {
      drainPlaybackQueue();
    }
  }, []);

  const drainPlaybackQueue = useCallback(() => {
    const ctx = playbackCtxRef.current;
    if (!ctx || playbackQueueRef.current.length === 0) {
      isPlayingRef.current = false;
      return;
    }

    isPlayingRef.current = true;
    const buffer = playbackQueueRef.current.shift()!;
    const source = ctx.createBufferSource();
    source.buffer = buffer;
    
    // Create a gain node to allow instant attenuation for Barge-In
    const gainNode = ctx.createGain();
    gainNode.gain.value = 1;
    
    source.connect(gainNode).connect(ctx.destination);
    
    source.onended = () => drainPlaybackQueue();
    source.start();
    
    // Store reference to the active gain node for barge-in flushing
    (ctx as any).__activeGainNode = gainNode;
    (ctx as any).__activeSourceNode = source;

    setVoicePhase('speaking');
  }, [setVoicePhase]);

  const flushPlaybackQueue = useCallback(() => {
    playbackQueueRef.current = [];
    isPlayingRef.current = false;
    
    const ctx = playbackCtxRef.current;
    if (ctx && ctx.state !== 'closed') {
      // Gain-attenuation clear method to flush audio instantly
      const gainNode = (ctx as any).__activeGainNode as GainNode | undefined;
      const sourceNode = (ctx as any).__activeSourceNode as AudioBufferSourceNode | undefined;
      
      if (gainNode) {
        // Fast exponential ramp down to avoid clicks
        gainNode.gain.cancelScheduledValues(ctx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.05);
      }
      
      setTimeout(() => {
        try { sourceNode?.stop(); } catch { /* ignore */ }
      }, 50);
    }
  }, []);

  // -----------------------------------------------------------------
  // WebSocket Message Handler
  // -----------------------------------------------------------------

  const handleServerMessage = useCallback((event: MessageEvent) => {
    try {
      const msg = JSON.parse(event.data);

      switch (msg.type) {
        case 'setup_complete':
          setVoicePhase('listening');
          playWakeChime();
          break;

        case 'audio':
          enqueuePlayback(msg.data);
          break;

        case 'transcript':
          setLastTranscript(msg.text || '');
          break;

        case 'turn_complete':
          if (useVoiceStore.getState().voicePhase === 'speaking') {
            setVoicePhase('listening');
          }
          break;

        case 'tool_active':
          setActiveTool(msg.tool || 'unknown', msg.task_id || '');
          startProcessingHum();
          break;

        case 'error':
          console.error('[JARVIS Voice] Server error:', msg.message);
          break;

        default:
          break;
      }
    } catch {
      // Non-JSON message — ignore
    }
  }, [setVoicePhase, setLastTranscript, setActiveTool, enqueuePlayback, playWakeChime, startProcessingHum]);

  // -----------------------------------------------------------------
  // Microphone Capture Engine (16kHz PCM → WebSocket)
  // -----------------------------------------------------------------

  const startMicCapture = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        sampleRate: TARGET_SAMPLE_RATE,
      },
    });
    streamRef.current = stream;

    const ctx = new AudioContext({ sampleRate: TARGET_SAMPLE_RATE });
    captureCtxRef.current = ctx;

    const source = ctx.createMediaStreamSource(stream);
    const processor = ctx.createScriptProcessor(CAPTURE_BUFFER_SIZE, 1, 1);
    processorRef.current = processor;

    processor.onaudioprocess = (e: AudioProcessingEvent) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;

      const inputData = e.inputBuffer.getChannelData(0);

      // --- Barge-In Detection ---
      const rms = calculateRMS(inputData);
      if (rms > BARGE_IN_AMPLITUDE_THRESHOLD && isPlayingRef.current) {
        flushPlaybackQueue();
        setVoicePhase('listening');
      }

      // Downsample if needed
      const pcm = ctx.sampleRate !== TARGET_SAMPLE_RATE
        ? downsample(inputData, ctx.sampleRate, TARGET_SAMPLE_RATE)
        : new Float32Array(inputData);

      const int16 = float32ToInt16(pcm);
      const base64 = arrayBufferToBase64(int16.buffer);

      ws.send(JSON.stringify({ type: 'audio', data: base64 }));
    };

    source.connect(processor);
    processor.connect(ctx.destination);
  }, [flushPlaybackQueue, setVoicePhase]);

  const stopMicCapture = useCallback(() => {
    processorRef.current?.disconnect();
    processorRef.current = null;

    if (captureCtxRef.current && captureCtxRef.current.state !== 'closed') {
      captureCtxRef.current.close();
      captureCtxRef.current = null;
    }

    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  // -----------------------------------------------------------------
  // Session Lifecycle
  // -----------------------------------------------------------------

  const startVoiceSession = useCallback(async () => {
    const apiKey = geminiApiKey;
    if (!apiKey) {
      console.error('[JARVIS Voice] No Gemini API key configured.');
      return;
    }

    setIsVoiceActive(true);
    setVoicePhase('connecting');
    retriesRef.current = 0;

    const connect = () => {
      const wsUrl = `${GATEWAY_WS_URL}?gemini_api_key=${encodeURIComponent(apiKey)}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = async () => {
        retriesRef.current = 0;
        try {
          await startMicCapture();
        } catch (err) {
          console.error('[JARVIS Voice] Microphone access denied:', err);
          stopVoiceSession();
        }
      };

      ws.onmessage = handleServerMessage;

      ws.onclose = () => {
        stopMicCapture();
        flushPlaybackQueue();
        stopProcessingHum();

        if (useVoiceStore.getState().isVoiceActive && retriesRef.current < MAX_RECONNECT_ATTEMPTS) {
          retriesRef.current++;
          const delay = 1000 * retriesRef.current;
          console.warn(`[JARVIS Voice] Connection lost. Retry ${retriesRef.current}/${MAX_RECONNECT_ATTEMPTS} in ${delay}ms`);
          setVoicePhase('connecting');
          setTimeout(connect, delay);
        } else if (retriesRef.current >= MAX_RECONNECT_ATTEMPTS) {
          console.error('[JARVIS Voice] Max reconnection attempts reached.');
          resetVoiceState();
        }
      };

      ws.onerror = (err) => {
        console.error('[JARVIS Voice] WebSocket error:', err);
      };
    };

    connect();
  }, [
    geminiApiKey,
    setIsVoiceActive,
    setVoicePhase,
    startMicCapture,
    stopMicCapture,
    handleServerMessage,
    flushPlaybackQueue,
    stopProcessingHum,
    resetVoiceState,
  ]);

  const stopVoiceSession = useCallback(() => {
    setIsVoiceActive(false);

    if (wsRef.current) {
      wsRef.current.close(1000, 'User ended session');
      wsRef.current = null;
    }

    stopMicCapture();
    flushPlaybackQueue();
    stopProcessingHum();
    resetVoiceState();
  }, [setIsVoiceActive, stopMicCapture, flushPlaybackQueue, stopProcessingHum, resetVoiceState]);

  useEffect(() => {
    return () => {
      stopVoiceSession();
    };
  }, [stopVoiceSession]);

  return {
    startVoiceSession,
    stopVoiceSession,
    voicePhase: useVoiceStore.getState().voicePhase,
    isVoiceActive: useVoiceStore.getState().isVoiceActive,
  };
}
