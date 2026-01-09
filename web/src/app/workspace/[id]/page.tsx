"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Sidebar } from "@/components/Sidebar";
import { StatCard } from "@/components/ui/StatCard";
import { StatusBadge, getStatusFromRunStatus } from "@/components/ui/StatusBadge";

interface Run {
    id: string;
    status: string;
    created_at: string;
    pipeline: {
        name: string;
    } | null;
    model_artifact: {
        name: string;
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
    promptpacks: number;
    runs: number;
    passed: number;
    failed: number;
    artifacts: number;
}

export default function WorkspacePage() {
    const params = useParams();
    const workspaceId = params.id as string;
    const [workspace, setWorkspace] = useState<Workspace | null>(null);
    const [runs, setRuns] = useState<Run[]>([]);
    const [integration, setIntegration] = useState<Integration | null>(null);
    const [stats, setStats] = useState<Stats>({ pipelines: 0, promptpacks: 0, runs: 0, passed: 0, failed: 0, artifacts: 0 });
    const [loading, setLoading] = useState(true);

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    useEffect(() => {
        fetchData();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [workspaceId]);

    const getAuthHeader = () => {
        const token = localStorage.getItem("token");
        if (!token) {
            window.location.href = "/login";
            return null;
        }
        return { Authorization: `Bearer ${token}` };
    };

    const fetchData = async () => {
        const headers = getAuthHeader();
        if (!headers) return;

        try {
            const wsRes = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}`, { headers });
            if (wsRes.ok) {
                const wsData = await wsRes.json();
                setWorkspace(wsData);
            }

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

            const artifactsRes = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/artifacts`, { headers });
            if (artifactsRes.ok) {
                const artifactsData = await artifactsRes.json();
                setStats(prev => ({ ...prev, artifacts: artifactsData.length }));
            }

            const intRes = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/integrations/qaihub`, { headers });
            if (intRes.ok) {
                const intData = await intRes.json();
                setIntegration(intData);
            }
        } catch (err) {
            console.error("Failed to fetch data", err);
        } finally {
            setLoading(false);
        }
    };

    const passRate = stats.runs > 0
        ? ((stats.passed / (stats.passed + stats.failed)) * 100).toFixed(1)
        : "0";

    if (loading) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="flex items-center gap-2 text-muted-foreground">
                    <span className="material-symbols-outlined animate-spin">sync</span>
                    <span>Loading...</span>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background flex">
            <Sidebar workspaceId={workspaceId} workspaceName={workspace?.name || "Workspace"} />

            <main className="flex-1 flex flex-col h-screen overflow-hidden">
                {/* Top Bar */}
                <header className="h-16 border-b border-border bg-background/80 backdrop-blur sticky top-0 z-10 px-6 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm">
                        <span className="text-muted-foreground">EdgeGate</span>
                        <span className="text-muted-foreground">/</span>
                        <span className="text-muted-foreground">Workspace</span>
                        <span className="text-muted-foreground">/</span>
                        <span className="font-semibold text-foreground">Overview</span>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded border border-border bg-card text-xs font-mono text-muted-foreground">
                            <span className={`w-2 h-2 rounded-full ${integration ? "bg-green-500" : "bg-yellow-500"}`}></span>
                            {integration ? "AI Hub Connected" : "AI Hub Not Connected"}
                        </div>
                        <Link href={`/workspace/${workspaceId}/pipelines`}>
                            <Button className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold shadow-lg shadow-primary/20">
                                <span className="material-symbols-outlined text-[18px] mr-1.5">add</span>
                                New Run
                            </Button>
                        </Link>
                    </div>
                </header>

                <div className="flex-1 overflow-y-auto p-6 max-w-7xl w-full mx-auto space-y-6">
                    {/* Integration Warning */}
                    {!integration && (
                        <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <span className="material-symbols-outlined text-yellow-400">warning</span>
                                <span className="text-yellow-400">AI Hub not connected. Connect to run tests on real devices.</span>
                            </div>
                            <Link href={`/workspace/${workspaceId}/settings`}>
                                <Button size="sm" className="bg-yellow-500 hover:bg-yellow-600 text-black font-bold">
                                    Connect AI Hub
                                </Button>
                            </Link>
                        </div>
                    )}

                    {/* Stats Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        <StatCard
                            title="Total Runs"
                            value={stats.runs.toString()}
                            icon="bar_chart"
                            trend={stats.runs > 0 ? { value: `${passRate}% pass rate`, direction: "up" } : undefined}
                        />
                        <StatCard
                            title="Pass Rate"
                            value={`${passRate}%`}
                            icon="check_circle"
                            trend={stats.passed > 0 ? { value: `${stats.passed} passed`, direction: "up" } : undefined}
                        />
                        <StatCard
                            title="Active Pipelines"
                            value={stats.pipelines.toString()}
                            icon="account_tree"
                        />
                        <StatCard
                            title="Model Artifacts"
                            value={stats.artifacts.toString()}
                            icon="deployed_code"
                        />
                    </div>

                    {/* Recent Runs Section */}
                    <div className="flex flex-col gap-4">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                            <h2 className="text-lg font-semibold text-foreground">Recent Runs</h2>
                            <div className="flex items-center gap-2">
                                <div className="relative group">
                                    <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground group-focus-within:text-foreground transition-colors text-[20px]">search</span>
                                    <input
                                        className="bg-card border border-border rounded-md py-1.5 pl-9 pr-3 text-sm text-foreground placeholder-muted-foreground focus:ring-1 focus:ring-primary focus:border-primary block w-full sm:w-64"
                                        placeholder="Search pipelines, models..."
                                        type="text"
                                    />
                                </div>
                                <Link href={`/workspace/${workspaceId}/runs`}>
                                    <Button variant="outline" size="sm" className="border-border text-muted-foreground hover:text-foreground">
                                        View All
                                    </Button>
                                </Link>
                            </div>
                        </div>

                        {/* Table Container */}
                        <div className="border border-border rounded-lg overflow-hidden bg-card">
                            {runs.length === 0 ? (
                                <div className="py-12 text-center text-muted-foreground">
                                    <span className="material-symbols-outlined text-4xl mb-2 block">play_circle</span>
                                    <p>No runs yet. Create a pipeline and trigger from CI.</p>
                                </div>
                            ) : (
                                <div className="overflow-x-auto">
                                    <table className="w-full text-left border-collapse">
                                        <thead>
                                            <tr className="bg-accent border-b border-border text-xs uppercase tracking-wider text-muted-foreground font-medium">
                                                <th className="px-6 py-3">Status</th>
                                                <th className="px-6 py-3">Run ID</th>
                                                <th className="px-6 py-3">Pipeline & Model</th>
                                                <th className="px-6 py-3">Duration</th>
                                                <th className="px-6 py-3 text-right">Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-border">
                                            {runs.map((run) => (
                                                <tr key={run.id} className="group hover:bg-accent/50 transition-colors">
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <StatusBadge status={getStatusFromRunStatus(run.status)} />
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <Link
                                                            href={`/workspace/${workspaceId}/runs/${run.id}`}
                                                            className="font-mono text-sm text-muted-foreground group-hover:text-primary transition-colors cursor-pointer"
                                                        >
                                                            #{run.id.slice(0, 8)}
                                                        </Link>
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        <div className="flex flex-col">
                                                            <span className="text-sm font-medium text-foreground">
                                                                {run.pipeline?.name || "Default Pipeline"}
                                                            </span>
                                                            <span className="text-xs text-muted-foreground">
                                                                {run.model_artifact?.name || "N/A"}
                                                            </span>
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap">
                                                        <div className="flex flex-col">
                                                            <span className="text-sm text-foreground">--</span>
                                                            <span className="text-xs text-muted-foreground">
                                                                {new Date(run.created_at).toLocaleString()}
                                                            </span>
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-right">
                                                        <Link href={`/workspace/${workspaceId}/runs/${run.id}`}>
                                                            <button className="text-muted-foreground hover:text-foreground transition-colors">
                                                                <span className="material-symbols-outlined">arrow_forward</span>
                                                            </button>
                                                        </Link>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
