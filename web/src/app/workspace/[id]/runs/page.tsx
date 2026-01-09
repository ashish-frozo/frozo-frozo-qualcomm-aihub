"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

interface Run {
    id: string;
    status: string;
    created_at: string;
    completed_at: string | null;
    pipeline_name: string;
    model_artifact?: {
        original_filename: string;
    } | null;
}

interface Workspace {
    id: string;
    name: string;
}

export default function RunsListPage() {
    const params = useParams();
    const workspaceId = params.id as string;
    const [workspace, setWorkspace] = useState<Workspace | null>(null);
    const [runs, setRuns] = useState<Run[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState("");

    useEffect(() => {
        fetchData();
    }, [workspaceId]);

    const fetchData = async () => {
        const token = localStorage.getItem("token");
        if (!token) {
            window.location.href = "/login";
            return;
        }

        const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const headers = { Authorization: `Bearer ${token}` };

        try {
            const [wsRes, runsRes] = await Promise.all([
                fetch(`${apiUrl}/v1/workspaces/${workspaceId}`, { headers }),
                fetch(`${apiUrl}/v1/workspaces/${workspaceId}/runs`, { headers }),
            ]);

            if (wsRes.ok) setWorkspace(await wsRes.json());
            if (runsRes.ok) setRuns(await runsRes.json());
        } catch (err) {
            console.error("Failed to fetch data", err);
        } finally {
            setLoading(false);
        }
    };

    const formatDuration = (start: string, end: string | null) => {
        if (!end) return "--";
        const duration = new Date(end).getTime() - new Date(start).getTime();
        const minutes = Math.floor(duration / 60000);
        const seconds = Math.floor((duration % 60000) / 1000);
        return `${minutes}m ${seconds}s`;
    };

    const filteredRuns = runs.filter(run => {
        if (!searchQuery) return true;
        const q = searchQuery.toLowerCase();
        return run.id.toLowerCase().includes(q) || run.pipeline_name?.toLowerCase().includes(q);
    });

    const passedCount = runs.filter(r => r.status === "passed").length;
    const failedCount = runs.filter(r => r.status === "failed").length;
    const runningCount = runs.filter(r => r.status === "running" || r.status === "pending").length;
    const passRate = runs.length > 0 ? ((passedCount / runs.length) * 100).toFixed(1) : "0";

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "passed":
                return (
                    <div className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-bold" style={{ backgroundColor: "rgba(16,185,129,0.1)", color: "#34d399", border: "1px solid rgba(16,185,129,0.2)" }}>
                        <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>check_circle</span>
                        <span>Passed</span>
                    </div>
                );
            case "failed":
                return (
                    <div className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-bold" style={{ backgroundColor: "rgba(239,68,68,0.1)", color: "#f87171", border: "1px solid rgba(239,68,68,0.2)" }}>
                        <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>cancel</span>
                        <span>Failed</span>
                    </div>
                );
            case "running":
            case "pending":
                return (
                    <div className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-bold" style={{ backgroundColor: "rgba(43,140,238,0.2)", color: "#93c5fd", border: "1px solid rgba(43,140,238,0.2)" }}>
                        <span className="material-symbols-outlined animate-spin" style={{ fontSize: "16px" }}>sync</span>
                        <span>Running</span>
                    </div>
                );
            default:
                return (
                    <div className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-bold" style={{ backgroundColor: "rgba(100,116,139,0.5)", color: "#94a3b8", border: "1px solid rgba(100,116,139,0.6)" }}>
                        <span className="material-symbols-outlined" style={{ fontSize: "16px" }}>schedule</span>
                        <span>Queued</span>
                    </div>
                );
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: "#101922" }}>
                <div className="flex items-center gap-2" style={{ color: "#92adc9" }}>
                    <span className="material-symbols-outlined animate-spin">sync</span>
                    <span>Loading...</span>
                </div>
            </div>
        );
    }

    return (
        <div className="relative flex min-h-screen w-full flex-col overflow-x-hidden" style={{ backgroundColor: "#101922", color: "white", fontFamily: "Inter, sans-serif" }}>
            {/* Top Navigation */}
            <header className="sticky top-0 z-50 flex items-center justify-between px-6 py-3 shadow-sm" style={{ borderBottom: "1px solid #334155", backgroundColor: "#111a22" }}>
                <div className="flex items-center gap-4">
                    <Link href="/dashboard" className="flex items-center gap-2" style={{ color: "#2b8cee" }}>
                        <div className="size-8 rounded flex items-center justify-center" style={{ backgroundColor: "rgba(43,140,238,0.2)", color: "#2b8cee" }}>
                            <span className="material-symbols-outlined">hub</span>
                        </div>
                        <h2 className="text-xl font-bold leading-tight tracking-tight text-white">EdgeGate</h2>
                    </Link>
                </div>
                <div className="flex flex-1 justify-end gap-8 items-center">
                    <nav className="hidden md:flex items-center gap-8">
                        <Link href={`/workspace/${workspaceId}`} className="text-sm font-medium transition-colors" style={{ color: "#94a3b8" }}>Dashboard</Link>
                        <span className="text-sm font-medium text-white">Test Runs</span>
                        <Link href={`/workspace/${workspaceId}/artifacts`} className="text-sm font-medium transition-colors" style={{ color: "#94a3b8" }}>Artifacts</Link>
                        <Link href={`/workspace/${workspaceId}/settings`} className="text-sm font-medium transition-colors" style={{ color: "#94a3b8" }}>Settings</Link>
                    </nav>
                    <div className="h-6 w-px hidden md:block" style={{ backgroundColor: "#334155" }}></div>
                    <div className="flex gap-3 items-center">
                        <button className="flex size-9 cursor-pointer items-center justify-center rounded-lg transition-colors" style={{ color: "#cbd5e1" }}>
                            <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>notifications</span>
                        </button>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="flex-1 px-4 sm:px-8 py-6 w-full max-w-[1440px] mx-auto flex flex-col gap-6">
                {/* Page Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div>
                        <h1 className="text-3xl font-black tracking-tight text-white">Test Runs</h1>
                        <p className="mt-1 text-sm" style={{ color: "#94a3b8" }}>Monitor historical regression tests and device performance.</p>
                    </div>
                    <Link href={`/workspace/${workspaceId}/pipelines`}>
                        <button className="flex items-center justify-center gap-2 rounded-lg text-white h-10 px-5 text-sm font-bold transition-all" style={{ backgroundColor: "#2b8cee", boxShadow: "0 4px 14px rgba(43,140,238,0.2)" }}>
                            <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>play_arrow</span>
                            <span>New Run</span>
                        </button>
                    </Link>
                </div>

                {/* Stats Overview */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div className="rounded-xl p-4" style={{ border: "1px solid #334155", backgroundColor: "#1c2936" }}>
                        <p className="text-xs font-medium uppercase tracking-wider" style={{ color: "#94a3b8" }}>Total Runs</p>
                        <div className="mt-2 flex items-baseline gap-2">
                            <span className="text-2xl font-bold text-white">{runs.length}</span>
                        </div>
                    </div>
                    <div className="rounded-xl p-4" style={{ border: "1px solid #334155", backgroundColor: "#1c2936" }}>
                        <p className="text-xs font-medium uppercase tracking-wider" style={{ color: "#94a3b8" }}>Pass Rate</p>
                        <div className="mt-2 flex items-baseline gap-2">
                            <span className="text-2xl font-bold text-white">{passRate}%</span>
                            <span className="text-xs font-medium" style={{ color: "#94a3b8" }}>Stable</span>
                        </div>
                    </div>
                    <div className="rounded-xl p-4" style={{ border: "1px solid #334155", backgroundColor: "#1c2936" }}>
                        <p className="text-xs font-medium uppercase tracking-wider" style={{ color: "#94a3b8" }}>Failed</p>
                        <div className="mt-2 flex items-baseline gap-2">
                            <span className="text-2xl font-bold" style={{ color: "#f87171" }}>{failedCount}</span>
                        </div>
                    </div>
                    <div className="rounded-xl p-4" style={{ border: "1px solid #334155", backgroundColor: "#1c2936" }}>
                        <p className="text-xs font-medium uppercase tracking-wider" style={{ color: "#94a3b8" }}>In Progress</p>
                        <div className="mt-2 flex items-baseline gap-2">
                            <span className="text-2xl font-bold" style={{ color: "#2b8cee" }}>{runningCount}</span>
                        </div>
                    </div>
                </div>

                {/* Filters & Search Toolbar */}
                <div className="flex flex-col gap-4 rounded-xl p-4 shadow-sm" style={{ border: "1px solid #334155", backgroundColor: "#1c2936" }}>
                    <div className="flex flex-col md:flex-row gap-4 items-stretch md:items-center">
                        <div className="relative flex-1 group">
                            <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none" style={{ color: "#94a3b8" }}>
                                <span className="material-symbols-outlined">search</span>
                            </div>
                            <input
                                className="block w-full rounded-lg p-2.5 pl-10 text-sm text-white focus:outline-none focus:ring-1"
                                placeholder="Search by Run ID, Model, or Pipeline..."
                                style={{ border: "1px solid #334155", backgroundColor: "#111a22", color: "white" }}
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                            />
                        </div>
                        <div className="flex items-center gap-2 ml-auto">
                            <button className="p-1.5 rounded-md transition-colors" style={{ color: "#94a3b8" }} title="Refresh" onClick={fetchData}>
                                <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>refresh</span>
                            </button>
                        </div>
                    </div>
                </div>

                {/* Data Table */}
                <div className="flex flex-col flex-1 overflow-hidden rounded-xl shadow-sm" style={{ border: "1px solid #334155", backgroundColor: "#1c2936" }}>
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm whitespace-nowrap">
                            <thead style={{ backgroundColor: "#151f2b", borderBottom: "1px solid #334155" }}>
                                <tr>
                                    <th className="px-6 py-4 font-semibold uppercase tracking-wider text-xs" style={{ color: "#94a3b8" }}>Status</th>
                                    <th className="px-6 py-4 font-semibold uppercase tracking-wider text-xs" style={{ color: "#94a3b8" }}>Run ID</th>
                                    <th className="px-6 py-4 font-semibold uppercase tracking-wider text-xs" style={{ color: "#94a3b8" }}>Pipeline</th>
                                    <th className="px-6 py-4 font-semibold uppercase tracking-wider text-xs" style={{ color: "#94a3b8" }}>Model Artifact</th>
                                    <th className="px-6 py-4 font-semibold uppercase tracking-wider text-xs" style={{ color: "#94a3b8" }}>Duration</th>
                                    <th className="px-6 py-4 font-semibold uppercase tracking-wider text-xs" style={{ color: "#94a3b8" }}>Created At</th>
                                    <th className="px-6 py-4 text-right"></th>
                                </tr>
                            </thead>
                            <tbody className="divide-y" style={{ borderColor: "#334155" }}>
                                {filteredRuns.length === 0 ? (
                                    <tr>
                                        <td colSpan={7} className="px-6 py-12 text-center" style={{ color: "#94a3b8" }}>
                                            <span className="material-symbols-outlined text-4xl mb-2 block">play_circle</span>
                                            No runs found
                                        </td>
                                    </tr>
                                ) : (
                                    filteredRuns.map((run) => (
                                        <tr key={run.id} className="group transition-colors" style={{ backgroundColor: run.status === "running" ? "rgba(43,140,238,0.05)" : "transparent" }}>
                                            <td className="px-6 py-4">{getStatusBadge(run.status)}</td>
                                            <td className="px-6 py-4">
                                                <Link href={`/workspace/${workspaceId}/runs/${run.id}`} className="font-mono font-medium hover:underline" style={{ color: "#2b8cee" }}>
                                                    #{run.id.slice(0, 8)}
                                                </Link>
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className="font-medium" style={{ color: "#e2e8f0" }}>{run.pipeline_name || "Default"}</span>
                                            </td>
                                            <td className="px-6 py-4">
                                                <div className="flex items-center gap-2" style={{ color: "#94a3b8" }}>
                                                    <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>folder_zip</span>
                                                    <span className="truncate max-w-[150px]">{run.model_artifact?.original_filename || "model.onnx"}</span>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4" style={{ color: "#94a3b8" }}>{formatDuration(run.created_at, run.completed_at)}</td>
                                            <td className="px-6 py-4" style={{ color: "#94a3b8" }}>{new Date(run.created_at).toLocaleString()}</td>
                                            <td className="px-6 py-4 text-right">
                                                <Link href={`/workspace/${workspaceId}/runs/${run.id}`}>
                                                    <button className="transition-colors" style={{ color: "#94a3b8" }}>
                                                        <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>arrow_forward</span>
                                                    </button>
                                                </Link>
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                    {/* Pagination Footer */}
                    <div className="flex items-center justify-between px-6 py-3" style={{ borderTop: "1px solid #334155", backgroundColor: "#1c2936" }}>
                        <p className="text-sm" style={{ color: "#94a3b8" }}>
                            Showing <span className="font-semibold text-white">{filteredRuns.length}</span> of <span className="font-semibold text-white">{runs.length}</span> results
                        </p>
                        <div className="flex gap-2">
                            <button className="flex items-center justify-center rounded-lg px-3 py-1.5 text-sm font-medium disabled:opacity-50" style={{ border: "1px solid #334155", backgroundColor: "#111a22", color: "#cbd5e1" }} disabled>
                                Previous
                            </button>
                            <button className="flex items-center justify-center rounded-lg px-3 py-1.5 text-sm font-medium" style={{ border: "1px solid #334155", backgroundColor: "#111a22", color: "#cbd5e1" }}>
                                Next
                            </button>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
