"use client";

import { useUIStore } from "@/store/useUIStore";
import { MessageSquare, Settings, Terminal, Database, ChevronLeft, ChevronRight } from "lucide-react";

export default function Sidebar() {
  const { isSidebarOpen, toggleSidebar } = useUIStore();

  return (
    <aside 
      className={`${
        isSidebarOpen ? "w-64" : "w-16"
      } bg-slate-950 border-r border-slate-800 transition-all duration-300 flex flex-col h-screen text-slate-300`}
    >
      {/* Header */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-slate-800">
        {isSidebarOpen && <span className="font-bold tracking-widest text-white">JARVIS OS</span>}
        <button onClick={toggleSidebar} className="p-1 hover:bg-slate-800 rounded text-slate-400">
          {isSidebarOpen ? <ChevronLeft size={20} /> : <ChevronRight size={20} />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 flex flex-col gap-2 px-2">
        <NavItem icon={<MessageSquare size={20} />} label="Active Thread" isOpen={isSidebarOpen} active />
        <NavItem icon={<Terminal size={20} />} label="Execution Logs" isOpen={isSidebarOpen} />
        <NavItem icon={<Database size={20} />} label="Memory Bank" isOpen={isSidebarOpen} />
      </nav>

      {/* Footer */}
      <div className="p-2 border-t border-slate-800">
        <NavItem icon={<Settings size={20} />} label="Settings" isOpen={isSidebarOpen} />
      </div>
    </aside>
  );
}

function NavItem({ icon, label, isOpen, active = false }: { icon: React.ReactNode; label: string; isOpen: boolean; active?: boolean }) {
  return (
    <button className={`flex items-center gap-3 p-3 rounded-md transition-colors w-full ${
      active ? "bg-blue-900/30 text-blue-400" : "hover:bg-slate-800 text-slate-400 hover:text-slate-200"
    }`}>
      {icon}
      {isOpen && <span className="text-sm font-medium whitespace-nowrap">{label}</span>}
    </button>
  );
}