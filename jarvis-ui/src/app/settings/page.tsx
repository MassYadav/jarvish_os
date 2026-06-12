import Sidebar from "@/components/layout/Sidebar";
import ApiKeyManager from "@/components/ApiKeyManager";

export default function Settings() {
  return (
    <main className="flex h-screen overflow-hidden bg-slate-900 font-sans antialiased relative">
      <Sidebar />
      <div className="flex-1 flex flex-col items-center justify-center bg-slate-950 p-8 z-10 border-l border-slate-800">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-slate-200 tracking-tight">System Configuration</h1>
          <p className="text-slate-500 mt-2">Manage your encrypted API credentials.</p>
        </div>
        <ApiKeyManager />
      </div>
    </main>
  );
}