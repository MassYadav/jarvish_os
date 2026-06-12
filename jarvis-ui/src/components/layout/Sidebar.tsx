// jarvis-ui/src/components/layout/Sidebar.tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUIStore } from "@/store/useUIStore";
import { MessageSquare, Settings, Terminal, Database, ChevronLeft, ChevronRight } from "lucide-react";

export default function Sidebar() {
  const { isSidebarOpen, toggleSidebar } = useUIStore();
  const pathname = usePathname(); // Detects which page we are on

  return (
    <aside 
      className={`${
        isSidebarOpen ? "w-64" : "w-16"
      } bg-slate-950 border-r border-slate-800 transition-all duration-300 flex flex-col h-screen text-slate-300 z-50`}
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
        {/* Changed href from "/" to standard dashboard routing */}
        <NavItem href="/" icon={<MessageSquare size={20} />} label="Active Thread" isOpen={isSidebarOpen} active={pathname === "/"} />
        <NavItem href="#" icon={<Terminal size={20} />} label="Execution Logs" isOpen={isSidebarOpen} active={pathname === "/logs"} />
        <NavItem href="#" icon={<Database size={20} />} label="Memory Bank" isOpen={isSidebarOpen} active={pathname === "/memory"} />
      </nav>

      {/* Footer */}
      <div className="p-2 border-t border-slate-800">
        <NavItem href="/settings" icon={<Settings size={20} />} label="Settings" isOpen={isSidebarOpen} active={pathname === "/settings"} />
      </div>
    </aside>
  );
}

// Updated NavItem to use Next.js Link for actual page routing
function NavItem({ href, icon, label, isOpen, active = false }: { href: string; icon: React.ReactNode; label: string; isOpen: boolean; active?: boolean }) {
  return (
    <Link href={href} className={`flex items-center gap-3 p-3 rounded-md transition-colors w-full ${
      active ? "bg-blue-900/30 text-blue-400" : "hover:bg-slate-800 text-slate-400 hover:text-slate-200"
    }`}>
      {icon}
      {isOpen && <span className="text-sm font-medium whitespace-nowrap">{label}</span>}
    </Link>
  );
}