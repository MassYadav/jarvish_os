import Sidebar from "@/components/layout/Sidebar";
import ChatInterface from "@/components/chat/ChatInterface";
import ExecutionObserver from "@/components/execution/ExecutionObserver";
import HitLModal from "@/components/hitl/HitLModal";

export default function Home() {
  return (
    <main className="flex h-screen overflow-hidden bg-slate-900 font-sans antialiased relative">
      <Sidebar />
      <ChatInterface />
      <ExecutionObserver />
      <HitLModal />
    </main>
  );
}