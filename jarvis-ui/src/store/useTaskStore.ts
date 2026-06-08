import { create } from 'zustand';

// 1. We strictly define every variable and function here so VS Code stops complaining
interface TaskState {
  taskId: string | null;
  status: 'IDLE' | 'RUNNING' | 'PENDING_APPROVAL' | 'COMPLETED' | 'FAILED';
  intent: string;
  stepResults: Record<string, string>;
  riskScore: number;
  finalResult: string;
  
  // Actions
  startTask: (intent: string) => void;
  updateStatus: (status: TaskState['status']) => void;
  clearTask: () => void;
  setTaskId: (id: string) => void;
  setRiskScore: (score: number) => void;
  setFinalResult: (result: string) => void;
}

// 2. We implement the actual logic here
export const useTaskStore = create<TaskState>((set) => ({
  taskId: null,
  status: 'IDLE',
  intent: '',
  stepResults: {},
  riskScore: 0,
  finalResult: '',

  startTask: (intent) => set({ 
    taskId: null, 
    status: 'RUNNING', 
    intent,
    stepResults: {},
    riskScore: 0,
    finalResult: ''
  }),
  
  updateStatus: (status) => set({ status }),
  clearTask: () => set({ taskId: null, status: 'IDLE', intent: '' }),
  
  // These are the missing functions that caused the crash!
  setTaskId: (id: string) => set({ taskId: id }),
  setRiskScore: (score: number) => set({ riskScore: score }),
  setFinalResult: (result: string) => set({ finalResult: result }),
}));