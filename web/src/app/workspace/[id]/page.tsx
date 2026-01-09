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

interface Integration {
    status: string;
    token_last4: string;
}

interface Stats {
    pipelines: number;
    runs: number;
    passed: number;
    failed: number;
}

export default function WorkspacePage() {
    const params = useParams();
    const workspaceId = params.id as string;
    const [workspace, setWorkspace] = useState<Workspace | null>(null);
    const [runs, setRuns] = useState<Run[]>([]);
    const [integration, setIntegration] = useState<Integration | null>(null);
    const [stats, setStats] = useState<Stats>({ pipelines: 0, runs: 0, passed: 0, failed: 0 });
    const [loading, setLoading] = useState(true);

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    useEffect(() => {
        fetchData();
    }, [workspaceId]);

    const fetchData = async () => {
        const token = localStorage.getItem("token");
        if (!token) {
            window.location.href = "/login";
            return;
        }
        const headers = { Authorization: `Bearer ${token}` };

        try {
            const wsRes = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}`, { headers });
            if (wsRes.ok) setWorkspace(await wsRes.json());

            const runsRes = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/runs`, { headers });
            if (runsRes.ok) {
                const runsData = await runsRes.json();
                setRuns(runsData.slice(0, 5));
                setStats(prev => ({
                    ...prev,
                    runs: runsData.length,
                    passed: runsData.filter((r: Run) => r.status === "passed").length,
                    failed: runsData.filter((r: Run) => r.status === "failed").length,
                }));
            }

            const pipelinesRes = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/pipelines`, { headers });
            if (pipelinesRes.ok) {
                const pipelinesData = await pipelinesRes.json();
                setStats(prev => ({ ...prev, pipelines: pipelinesData.length }));
            }

            const intRes = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/integrations/qaihub`, { headers });
            if (intRes.ok) setIntegration(await intRes.json());
        } catch (err) {
            console.error("Failed to fetch data", err);
        } finally {
            setLoading(false);
        }
    };

    const formatDuration = (start: string, end: string | null) => {
        if (!end) return "In progress";
        const duration = new Date(end).getTime() - new Date(start).getTime();
        const minutes = Math.floor(duration / 60000);
        const seconds = Math.floor((duration % 60000) / 1000);
        return `${minutes}m ${seconds}s`;
    };

    const passRate = stats.runs > 0 ? ((stats.passed / stats.runs) * 100).toFixed(1) : "0";

    const getStatusIndicator = (status: string) => {
        switch (status) {
            case "passed":
                return { icon: "check_circle", color: "#238636" };
            case "failed":
                return { icon: "cancel", color: "#da3633" };
            case "running":
            case "pending":
                return { icon: "sync", color: "#2b8cee", animate: true };
            default:
                return { icon: "schedule", color: "#8b949e" };
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: "#0d1117" }}>
                <div className="flex items-center gap-2" style={{ color: "#8b949e" }}>
                    <span className="material-symbols-outlined animate-spin">sync</span>
                    <span>Loading...</span>
                </div>
            </div>
        );
    }

    return (
        <div className="flex h-screen w-full overflow-hidden" style={{ backgroundColor: "#0d1117", fontFamily: "Inter, sans-serif" }}>
            {/* Sidebar */}
            <aside className="w-64 flex-shrink-0 flex-col justify-between hidden md:flex" style={{ borderRight: "1px solid #30363d", backgroundColor: "#0d1117" }}>
                <div>
                    {/* Logo / Workspace Header */}
                    <div className="h-16 flex items-center px-4" style={{ borderBottom: "1px solid #30363d" }}>
                        <div className="flex items-center gap-3">
                            <div className="size-8 rounded flex items-center justify-center text-white font-bold text-lg" style={{ background: "linear-gradient(135deg, #2b8cee, #1e40af)" }}>E</div>
                            <div className="flex flex-col">
                                <span className="text-sm font-semibold text-white leading-tight">EdgeGate</span>
                                <span className="text-xs" style={{ color: "#8b949e" }}>{workspace?.name || "Workspace"}</span>
                            </div>
                        </div>
                    </div>
                    {/* Navigation */}
                    <nav className="flex flex-col gap-1 p-3">
                        <Link href={`/workspace/${workspaceId}`} className="flex items-center gap-3 px-3 py-2 rounded-md" style={{ backgroundColor: "rgba(43,140,238,0.1)", color: "#2b8cee", border: "1px solid rgba(43,140,238,0.2)" }}>
                            <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>dashboard</span>
                            <span className="text-sm font-medium">Dashboard</span>
                        </Link>
                        <Link href={`/workspace/${workspaceId}/pipelines`} className="flex items-center gap-3 px-3 py-2 rounded-md transition-colors" style={{ color: "#8b949e" }}>
                            <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>alt_route</span>
                            <span className="text-sm font-medium">Pipelines</span>
                        </Link>
                        <Link href={`/workspace/${workspaceId}/runs`} className="flex items-center gap-3 px-3 py-2 rounded-md transition-colors" style={{ color: "#8b949e" }}>
                            <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>play_circle</span>
                            <span className="text-sm font-medium">Runs</span>
                        </Link>
                        <Link href={`/workspace/${workspaceId}/artifacts`} className="flex items-center gap-3 px-3 py-2 rounded-md transition-colors" style={{ color: "#8b949e" }}>
                            <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>deployed_code</span>
                            <span className="text-sm font-medium">Artifacts</span>
                        </Link>
                        <Link href={`/workspace/${workspaceId}/settings`} className="flex items-center gap-3 px-3 py-2 rounded-md transition-colors" style={{ color: "#8b949e" }}>
                            <span className="material-symbols-outlined" style={{ fontSize: "20px" }}>settings</span>
                            <span className="text-sm font-medium">Settings</span>
                        </Link>
                    </nav>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1 flex flex-col h-full min-w-0 overflow-y-auto" style={{ backgroundColor: "#0d1117" }}>
                {/* Top Bar */}
                <header className="h-16 sticky top-0 z-10 px-6 flex items-center justify-between" style={{ borderBottom: "1px solid #30363d", backgroundColor: "rgba(13,17,23,0.8)", backdropFilter: "blur(8px)" }}>
                    <div className="flex items-center gap-2 text-sm">
                        <span style={{ color: "#8b949e" }}>EdgeGate</span>
                        <span style={{ color: "#8b949e" }}>/</span>
                        <span style={{ color: "#8b949e" }}>Workspace</span>
                        <span style={{ color: "#8b949e" }}>/</span>
                        <span className="font-semibold text-white">Overview</span>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded text-xs font-mono" style={{ border: "1px solid #30363d", backgroundColor: "#161b22", color: "#8b949e" }}>
                            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: integration ? "#238636" : "#d29922" }}></span>
                            {integration ? "System Healthy" : "AI Hub Not Connected"}
                        </div>
                        <Link href={`/workspace/${workspaceId}/pipelines`}>
                            <button className="flex items-center justify-center h-8 px-4 text-white text-sm font-medium rounded transition-colors" style={{ backgroundColor: "#2b8cee", boxShadow: "0 4px 14px rgba(43,140,238,0.2)" }}>
                                <span className="material-symbols-outlined mr-1.5" style={{ fontSize: "18px" }}>add</span>
                                New Run
                            </button>
                        </Link>
                    </div>
                </header>

                <div className="p-6 max-w-7xl w-full mx-auto space-y-6">
                    {/* Stats Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        {/* Total Runs */}
                        <div className="rounded-lg p-5 flex flex-col justify-between h-32 transition-colors" style={{ backgroundColor: "#161b22", border: "1px solid #30363d" }}>
                            <div className="flex justify-between items-start">
                                <span className="text-xs font-medium uppercase tracking-wider" style={{ color: "#8b949e" }}>Total Runs</span>
                                <span className="material-symbols-outlined" style={{ color: "#8b949e", fontSize: "20px" }}>bar_chart</span>
                            </div>
                            <div>
                                <div className="text-2xl font-bold text-white tracking-tight">{stats.runs.toLocaleString()}</div>
                                <div className="flex items-center gap-1 mt-1">
                                    <span className="material-symbols-outlined" style={{ color: "#238636", fontSize: "16px" }}>trending_up</span>
                                    <span className="text-xs font-medium" style={{ color: "#238636" }}>+{stats.passed}</span>
                                    <span className="text-xs ml-1" style={{ color: "#8b949e" }}>passed</span>
                                </div>
                            </div>
                        </div>
                        {/* Pass Rate */}
                        <div className="rounded-lg p-5 flex flex-col justify-between h-32 transition-colors" style={{ backgroundColor: "#161b22", border: "1px solid #30363d" }}>
                            <div className="flex justify-between items-start">
                                <span className="text-xs font-medium uppercase tracking-wider" style={{ color: "#8b949e" }}>Pass Rate</span>
                                <span className="material-symbols-outlined" style={{ color: "#8b949e", fontSize: "20px" }}>check_circle</span>
                            </div>
                            <div>
                                <div className="text-2xl font-bold text-white tracking-tight">{passRate}%</div>
                                <div className="flex items-center gap-1 mt-1">
                                    <span className="text-xs" style={{ color: "#8b949e" }}>of all runs</span>
                                </div>
                            </div>
                        </div>
                        {/* Active Pipelines */}
                        <div className="rounded-lg p-5 flex flex-col justify-between h-32 transition-colors" style={{ backgroundColor: "#161b22", border: "1px solid #30363d" }}>
                            <div className="flex justify-between items-start">
                                <span className="text-xs font-medium uppercase tracking-wider" style={{ color: "#8b949e" }}>Active Pipelines</span>
                                <span className="material-symbols-outlined" style={{ color: "#8b949e", fontSize: "20px" }}>account_tree</span>
                            </div>
                            <div>
                                <div className="text-2xl font-bold text-white tracking-tight">{stats.pipelines}</div>
                                <div className="flex items-center gap-1 mt-1">
                                    <span className="text-xs" style={{ color: "#8b949e" }}>configured</span>
                                </div>
                            </div>
                        </div>
                        {/* Failed */}
                        <div className="rounded-lg p-5 flex flex-col justify-between h-32 transition-colors" style={{ backgroundColor: "#161b22", border: "1px solid #30363d" }}>
                            <div className="flex justify-between items-start">
                                <span className="text-xs font-medium uppercase tracking-wider" style={{ color: "#8b949e" }}>Failed Runs</span>
                                <span className="material-symbols-outlined" style={{ color: "#8b949e", fontSize: "20px" }}>error</span>
                            </div>
                            <div>
                                <div className="text-2xl font-bold tracking-tight" style={{ color: "#da3633" }}>{stats.failed}</div>
                                <div className="flex items-center gap-1 mt-1">
                                    <span className="text-xs" style={{ color: "#8b949e" }}>need attention</span>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Recent Runs Section */}
                    <div className="flex flex-col gap-4">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                            <h2 className="text-lg font-semibold text-white">Recent Runs</h2>
                            <div className="flex items-center gap-2">
                                <div className="relative group">
                                    <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: "#8b949e", fontSize: "20px" }}>search</span>
                                    <input
                                        className="py-1.5 pl-9 pr-3 text-sm text-white block w-full sm:w-64 rounded-md"
                                        placeholder="Search pipelines, models..."
                                        style={{ backgroundColor: "#161b22", border: "1px solid #30363d", color: "white" }}
                                    />
                                </div>
                                <Link href={`/workspace/${workspaceId}/runs`}>
                                    <button className="flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-colors" style={{ backgroundColor: "#161b22", border: "1px solid #30363d", color: "#8b949e" }}>
                                        View All
                                    </button>
                                </Link>
                            </div>
                        </div>

                        {/* Table Container */}
                        <div className="rounded-lg overflow-hidden" style={{ border: "1px solid #30363d", backgroundColor: "#161b22" }}>
                            <div className="overflow-x-auto">
                                <table className="w-full text-left border-collapse">
                                    <thead>
                                        <tr className="text-xs uppercase tracking-wider font-medium" style={{ backgroundColor: "rgba(255,255,255,0.05)", borderBottom: "1px solid #30363d", color: "#8b949e" }}>
                                            <th className="px-6 py-3">Status</th>
                                            <th className="px-6 py-3">Run ID</th>
                                            <th className="px-6 py-3">Pipeline & Model</th>
                                            <th className="px-6 py-3">Duration</th>
                                            <th className="px-6 py-3 text-right">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y" style={{ borderColor: "#30363d" }}>
                                        {runs.length === 0 ? (
                                            <tr>
                                                <td colSpan={5} className="px-6 py-12 text-center" style={{ color: "#8b949e" }}>
                                                    <span className="material-symbols-outlined text-4xl mb-2 block">play_circle</span>
                                                    No runs yet. Create a pipeline and trigger from CI.
                                                </td>
                                            </tr>
                                        ) : (
                                            runs.map((run) => {
                                                const indicator = getStatusIndicator(run.status);
                                                return (
                                                    <tr key={run.id} className="group transition-colors" style={{ backgroundColor: "transparent" }}>
                                                        <td className="px-6 py-4 whitespace-nowrap">
                                                            <div className="flex items-center gap-2">
                                                                {run.status === "running" || run.status === "pending" ? (
                                                                    <span className="relative flex h-2.5 w-2.5">
                                                                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" style={{ backgroundColor: "#2b8cee" }}></span>
                                                                        <span className="relative inline-flex rounded-full h-2.5 w-2.5" style={{ backgroundColor: "#2b8cee" }}></span>
                                                                    </span>
                                                                ) : (
                                                                    <span className="material-symbols-outlined" style={{ color: indicator.color, fontSize: "18px" }}>{indicator.icon}</span>
                                                                )}
                                                                <span className="text-sm text-white font-medium capitalize">{run.status}</span>
                                                            </div>
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap">
                                                            <Link href={`/workspace/${workspaceId}/runs/${run.id}`} className="font-mono text-sm transition-colors cursor-pointer" style={{ color: "#8b949e" }}>
                                                                #{run.id.slice(0, 8)}
                                                            </Link>
                                                        </td>
                                                        <td className="px-6 py-4">
                                                            <div className="flex flex-col">
                                                                <span className="text-sm font-medium text-white">{run.pipeline_name || "Default"}</span>
                                                                <span className="text-xs" style={{ color: "#8b949e" }}>{run.model_artifact?.original_filename || "model.onnx"}</span>
                                                            </div>
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap">
                                                            <div className="flex flex-col">
                                                                <span className="text-sm text-white">{formatDuration(run.created_at, run.completed_at)}</span>
                                                                <span className="text-xs" style={{ color: "#8b949e" }}>{new Date(run.created_at).toLocaleString()}</span>
                                                            </div>
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap text-right">
                                                            <Link href={`/workspace/${workspaceId}/runs/${run.id}`}>
                                                                <button className="transition-colors" style={{ color: "#8b949e" }}>
                                                                    <span className="material-symbols-outlined">arrow_forward</span>
                                                                </button>
                                                            </Link>
                                                        </td>
                                                    </tr>
                                                );
                                            })
                                        )}
                                    </tbody>
                                </table>
                            </div>
                            {/* Pagination Footer */}
                            <div className="px-4 py-3 flex items-center justify-between sm:px-6" style={{ backgroundColor: "#161b22", borderTop: "1px solid #30363d" }}>
                                <p className="text-sm" style={{ color: "#8b949e" }}>
                                    Showing <span className="font-medium text-white">{runs.length}</span> of <span className="font-medium text-white">{stats.runs}</span> results
                                </p>
                                <Link href={`/workspace/${workspaceId}/runs`}>
                                    <button className="text-sm font-medium" style={{ color: "#2b8cee" }}>View all runs →</button>
                                </Link>
                            </div>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
