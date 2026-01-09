"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Sidebar } from "@/components/Sidebar";
import { StatusBadge, getStatusFromRunStatus } from "@/components/ui/StatusBadge";
import { StatCard } from "@/components/ui/StatCard";

interface Run {
    id: string;
    status: string;
    created_at: string;
    pipeline: {
        id: string;
        name: string;
    } | null;
    model_artifact: {
        id: string;
        name: string;
    } | null;
}

interface Workspace {
    id: string;
    name: string;
}

export default function RunsPage() {
    const params = useParams();
    const workspaceId = params.id as string;
    const [workspace, setWorkspace] = useState<Workspace | null>(null);
    const [runs, setRuns] = useState<Run[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState("");

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
                setRuns(runsData);
            }
        } catch (err) {
            console.error("Failed to fetch data", err);
        } finally {
            setLoading(false);
        }
    };

    const filteredRuns = runs.filter(run => {
        if (!searchQuery) return true;
        const query = searchQuery.toLowerCase();
        return (
            run.id.toLowerCase().includes(query) ||
            run.pipeline?.name.toLowerCase().includes(query) ||
            run.model_artifact?.name.toLowerCase().includes(query)
        );
    });

    const totalRuns = runs.length;
    const passedRuns = runs.filter(r => r.status === "passed").length;
    const failedRuns = runs.filter(r => r.status === "failed").length;
    const inProgressRuns = runs.filter(r => ["running", "queued", "preparing", "submitting", "collecting", "evaluating", "reporting"].includes(r.status)).length;
    const passRate = totalRuns > 0 ? ((passedRuns / (passedRuns + failedRuns)) * 100).toFixed(1) : "0";

    return (
        <div className="min-h-screen bg-background flex">
            <Sidebar workspaceId={workspaceId} workspaceName={workspace?.name || "Loading..."} />

            <main className="flex-1 flex flex-col h-screen overflow-hidden">
                {/* Top Bar */}
                <header className="h-16 border-b border-border bg-background/80 backdrop-blur sticky top-0 z-10 px-6 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm">
                        <span className="text-muted-foreground">EdgeGate</span>
                        <span className="text-muted-foreground">/</span>
                        <span className="text-muted-foreground">{workspace?.name || "Workspace"}</span>
                        <span className="text-muted-foreground">/</span>
                        <span className="font-semibold text-foreground">Test Runs</span>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded border border-border bg-card text-xs font-mono text-muted-foreground">
                            <span className="w-2 h-2 rounded-full bg-green-500"></span>
                            System Healthy
                        </div>
                        <Link href={`/workspace/${workspaceId}/pipelines`}>
                            <Button className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold shadow-lg shadow-primary/20">
                                <span className="material-symbols-outlined text-[18px] mr-1.5">play_arrow</span>
                                New Run
                            </Button>
                        </Link>
                    </div>
                </header>

                <div className="flex-1 overflow-y-auto p-6 max-w-7xl w-full mx-auto space-y-6">
                    {/* Page Header */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                        <div>
                            <h1 className="text-3xl font-black tracking-tight text-foreground">Test Runs</h1>
                            <p className="text-muted-foreground mt-1 text-sm">Monitor historical regression tests and device performance.</p>
                        </div>
                    </div>

                    {/* Stats Grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        <StatCard
                            title="Total Runs"
                            value={totalRuns.toString()}
                            icon="bar_chart"
                            trend={inProgressRuns > 0 ? { value: `${inProgressRuns} active`, direction: "neutral" } : undefined}
                        />
                        <StatCard
                            title="Pass Rate"
                            value={`${passRate}%`}
                            icon="check_circle"
                            trend={{ value: `${passedRuns} passed`, direction: "up" }}
                        />
                        <StatCard
                            title="Failed"
                            value={failedRuns.toString()}
                            icon="cancel"
                            trend={failedRuns > 0 ? { value: "Needs attention", direction: "down" } : undefined}
                        />
                        <StatCard
                            title="In Progress"
                            value={inProgressRuns.toString()}
                            icon="sync"
                        />
                    </div>

                    {/* Search & Filters */}
                    <div className="flex flex-col gap-4 rounded-xl border border-border bg-card p-4 shadow-sm">
                        <div className="flex flex-col md:flex-row gap-4 items-stretch md:items-center">
                            <div className="relative flex-1 group">
                                <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-muted-foreground group-focus-within:text-primary transition-colors">
                                    <span className="material-symbols-outlined">search</span>
                                </div>
                                <input
                                    className="block w-full rounded-lg border border-border bg-background p-2.5 pl-10 text-sm text-foreground placeholder-muted-foreground focus:border-primary focus:ring-primary"
                                    placeholder="Search by Run ID, Pipeline, or Model..."
                                    type="text"
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                />
                            </div>
                            <button className="flex items-center gap-2 px-3 py-1.5 bg-card border border-border rounded-md text-sm text-muted-foreground hover:text-foreground hover:border-white/30 transition-colors">
                                <span className="material-symbols-outlined text-[18px]">filter_list</span>
                                Filter
                            </button>
                        </div>
                    </div>

                    {/* Data Table */}
                    {loading ? (
                        <div className="flex items-center justify-center py-12 text-muted-foreground">
                            <span className="material-symbols-outlined animate-spin mr-2">sync</span>
                            Loading...
                        </div>
                    ) : filteredRuns.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-16 rounded-xl border border-border border-dashed bg-card">
                            <span className="material-symbols-outlined text-4xl text-muted-foreground mb-4">play_circle</span>
                            <h3 className="text-lg font-medium text-foreground mb-2">No runs yet</h3>
                            <p className="text-muted-foreground mb-6 max-w-md text-center">
                                Runs are created when you trigger a pipeline from CI or manually.
                            </p>
                            <Link href={`/workspace/${workspaceId}/pipelines`}>
                                <Button variant="outline" className="border-border text-foreground hover:bg-accent">
                                    View Pipelines
                                </Button>
                            </Link>
                        </div>
                    ) : (
                        <div className="flex flex-col overflow-hidden rounded-xl border border-border bg-card shadow-sm">
                            <div className="overflow-x-auto">
                                <table className="w-full text-left text-sm whitespace-nowrap">
                                    <thead className="bg-accent border-b border-border">
                                        <tr>
                                            <th className="px-6 py-4 font-semibold text-muted-foreground uppercase tracking-wider text-xs">Status</th>
                                            <th className="px-6 py-4 font-semibold text-muted-foreground uppercase tracking-wider text-xs">Run ID</th>
                                            <th className="px-6 py-4 font-semibold text-muted-foreground uppercase tracking-wider text-xs">Pipeline</th>
                                            <th className="px-6 py-4 font-semibold text-muted-foreground uppercase tracking-wider text-xs">Model</th>
                                            <th className="px-6 py-4 font-semibold text-muted-foreground uppercase tracking-wider text-xs">Created</th>
                                            <th className="px-6 py-4 text-right"></th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-border">
                                        {filteredRuns.map((run) => (
                                            <tr key={run.id} className="group hover:bg-accent/50 transition-colors">
                                                <td className="px-6 py-4">
                                                    <StatusBadge status={getStatusFromRunStatus(run.status)} />
                                                </td>
                                                <td className="px-6 py-4">
                                                    <Link
                                                        href={`/workspace/${workspaceId}/runs/${run.id}`}
                                                        className="font-mono text-primary hover:text-primary/80 hover:underline font-medium"
                                                    >
                                                        #{run.id.slice(0, 8)}
                                                    </Link>
                                                </td>
                                                <td className="px-6 py-4">
                                                    <span className="text-foreground font-medium">
                                                        {run.pipeline?.name || "Default Pipeline"}
                                                    </span>
                                                </td>
                                                <td className="px-6 py-4">
                                                    <div className="flex items-center gap-2 text-muted-foreground group-hover:text-foreground">
                                                        <span className="material-symbols-outlined text-[18px]">folder_zip</span>
                                                        <span className="truncate max-w-[150px]">
                                                            {run.model_artifact?.name || "N/A"}
                                                        </span>
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4 text-muted-foreground">
                                                    {new Date(run.created_at).toLocaleString()}
                                                </td>
                                                <td className="px-6 py-4 text-right">
                                                    <Link href={`/workspace/${workspaceId}/runs/${run.id}`}>
                                                        <button className="text-muted-foreground hover:text-foreground transition-colors">
                                                            <span className="material-symbols-outlined text-[20px]">arrow_forward</span>
                                                        </button>
                                                    </Link>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                            {/* Pagination Footer */}
                            <div className="flex items-center justify-between border-t border-border bg-card px-6 py-3">
                                <p className="text-sm text-muted-foreground">
                                    Showing <span className="font-semibold text-foreground">{filteredRuns.length}</span> of <span className="font-semibold text-foreground">{runs.length}</span> results
                                </p>
                                <div className="flex gap-2">
                                    <Button variant="outline" size="sm" disabled className="border-border">
                                        Previous
                                    </Button>
                                    <Button variant="outline" size="sm" className="border-border">
                                        Next
                                    </Button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
