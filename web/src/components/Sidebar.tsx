"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface SidebarProps {
    workspaceId: string;
    workspaceName: string;
}

export function Sidebar({ workspaceId, workspaceName }: SidebarProps) {
    const pathname = usePathname();

    const navItems = [
        {
            name: "Overview",
            href: `/workspace/${workspaceId}`,
            icon: (
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                </svg>
            ),
        },
        {
            name: "Pipelines",
            href: `/workspace/${workspaceId}/pipelines`,
            icon: (
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
                </svg>
            ),
        },
        {
            name: "PromptPacks",
            href: `/workspace/${workspaceId}/promptpacks`,
            icon: (
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
            ),
        },
        {
            name: "Runs",
            href: `/workspace/${workspaceId}/runs`,
            icon: (
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
            ),
        },
        {
            name: "Settings",
            href: `/workspace/${workspaceId}/settings`,
            icon: (
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
            ),
        },
    ];

    const isActive = (href: string) => {
        if (href === `/workspace/${workspaceId}`) {
            return pathname === href;
        }
        return pathname?.startsWith(href);
    };

    return (
        <aside className="w-64 min-h-screen bg-slate-900/50 border-r border-slate-800">
            {/* Workspace Header */}
            <div className="p-4 border-b border-slate-800">
                <Link href="/dashboard" className="flex items-center gap-2 mb-4">
                    <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-500" />
                    <span className="text-lg font-bold text-white">EdgeGate</span>
                </Link>
                <div className="px-2 py-1.5 bg-slate-800/50 rounded-lg">
                    <div className="text-sm text-slate-400">Workspace</div>
                    <div className="text-white font-medium truncate">{workspaceName}</div>
                </div>
            </div>

            {/* Navigation */}
            <nav className="p-3 space-y-1">
                {navItems.map((item) => (
                    <Link
                        key={item.name}
                        href={item.href}
                        className={`flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors ${isActive(item.href)
                                ? "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20"
                                : "text-slate-400 hover:text-white hover:bg-slate-800/50"
                            }`}
                    >
                        {item.icon}
                        <span className="font-medium">{item.name}</span>
                    </Link>
                ))}
            </nav>

            {/* Back to Dashboard */}
            <div className="absolute bottom-0 left-0 w-64 p-4 border-t border-slate-800">
                <Link
                    href="/dashboard"
                    className="flex items-center gap-2 text-slate-400 hover:text-white transition-colors"
                >
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                    </svg>
                    <span className="text-sm">Back to Dashboard</span>
                </Link>
            </div>
        </aside>
    );
}
