"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Sidebar } from "@/components/Sidebar";
import { StatusBadge, getStatusFromRunStatus } from "@/components/ui/StatusBadge";

interface Pipeline {
    id: string;
    name: string;
    description?: string;
    device_matrix?: string[];
    device_count: number;
    gate_count: number;
    last_run?: {
        id: string;
        status: string;
        created_at: string;
    };
    created_at: string;
    updated_at: string;
}

interface Workspace {
    id: string;
    name: string;
}

export default function PipelinesPage() {
    const params = useParams();
    const workspaceId = params.id as string;
    const [workspace, setWorkspace] = useState<Workspace | null>(null);
    const [pipelines, setPipelines] = useState<Pipeline[]>([]);
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

            const pipelinesRes = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/pipelines`, { headers });
            if (pipelinesRes.ok) {
                const pipelinesData = await pipelinesRes.json();
                setPipelines(pipelinesData);
            }
        } catch (err) {
            console.error("Failed to fetch data", err);
        } finally {
            setLoading(false);
        }
    };

    const filteredPipelines = pipelines.filter(p => {
        if (!searchQuery) return true;
        return p.name.toLowerCase().includes(searchQuery.toLowerCase());
    });

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
                        <span className="font-semibold text-foreground">Pipelines</span>
                    </div>
                    <Link href={`/workspace/${workspaceId}/pipelines/new`}>
                        <Button className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold shadow-lg shadow-primary/20">
                            <span className="material-symbols-outlined text-[18px] mr-1.5">add</span>
                            Create Pipeline
                        </Button>
                    </Link>
                </header>

                <div className="flex-1 overflow-y-auto p-6 max-w-7xl w-full mx-auto space-y-6">
                    {/* Page Header */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                        <div>
                            <h1 className="text-3xl font-black tracking-tight text-foreground">Automated Test Pipelines</h1>
                            <p className="text-muted-foreground mt-1 text-sm">Manage and monitor your automated regression tests on edge devices.</p>
                        </div>
                    </div>

                    {/* Search & Filters */}
                    <div className="flex flex-col sm:flex-row flex-wrap items-center gap-4">
                        <div className="relative w-full sm:flex-1 min-w-[240px]">
                            <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground text-[20px]">search</span>
                            <input
                                className="w-full rounded-lg border border-border bg-card text-foreground focus:outline-0 focus:ring-2 focus:ring-primary focus:border-primary h-11 pl-11 pr-4 text-sm placeholder:text-muted-foreground transition-all"
                                placeholder="Search pipelines..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                            />
                        </div>
                        <div className="relative w-full sm:w-auto min-w-[200px]">
                            <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground text-[20px]">filter_list</span>
                            <select className="w-full appearance-none rounded-lg border border-border bg-card text-foreground focus:outline-0 focus:ring-2 focus:ring-primary focus:border-primary h-11 pl-11 pr-10 text-sm transition-all cursor-pointer">
                                <option value="all">All Statuses</option>
                                <option value="passed">Passed</option>
                                <option value="failed">Failed</option>
                                <option value="running">Running</option>
                            </select>
                            <span className="material-symbols-outlined absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none text-[20px]">expand_more</span>
                        </div>
                    </div>

                    {/* Table Section */}
                    {loading ? (
                        <div className="flex items-center justify-center py-12 text-muted-foreground">
                            <span className="material-symbols-outlined animate-spin mr-2">sync</span>
                            Loading...
                        </div>
                    ) : filteredPipelines.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-16 rounded-xl border border-border border-dashed bg-card">
                            <span className="material-symbols-outlined text-4xl text-muted-foreground mb-4">account_tree</span>
                            <h3 className="text-lg font-medium text-foreground mb-2">No pipelines yet</h3>
                            <p className="text-muted-foreground mb-6 max-w-md text-center">
                                Create a pipeline to define testing criteria for your AI models on Snapdragon devices.
                            </p>
                            <Link href={`/workspace/${workspaceId}/pipelines/new`}>
                                <Button className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold">
                                    Create Your First Pipeline
                                </Button>
                            </Link>
                        </div>
                    ) : (
                        <div className="flex flex-col overflow-hidden rounded-xl border border-border bg-card shadow-sm">
                            <div className="overflow-x-auto">
                                <table className="w-full min-w-[900px]">
                                    <thead>
                                        <tr className="bg-accent border-b border-border">
                                            <th className="px-6 py-4 text-left text-muted-foreground text-xs font-semibold uppercase tracking-wider w-[25%]">Pipeline Name</th>
                                            <th className="px-6 py-4 text-left text-muted-foreground text-xs font-semibold uppercase tracking-wider w-[30%]">Description</th>
                                            <th className="px-6 py-4 text-left text-muted-foreground text-xs font-semibold uppercase tracking-wider w-[20%]">Target Devices</th>
                                            <th className="px-6 py-4 text-left text-muted-foreground text-xs font-semibold uppercase tracking-wider w-[15%]">Last Run</th>
                                            <th className="px-6 py-4 text-right text-muted-foreground text-xs font-semibold uppercase tracking-wider w-[10%]">Actions</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-border">
                                        {filteredPipelines.map((pipeline) => (
                                            <tr key={pipeline.id} className="group hover:bg-accent/50 transition-colors">
                                                <td className="px-6 py-4">
                                                    <div className="flex flex-col">
                                                        <Link
                                                            href={`/workspace/${workspaceId}/pipelines/${pipeline.id}`}
                                                            className="text-sm font-semibold text-foreground group-hover:text-primary transition-colors cursor-pointer"
                                                        >
                                                            {pipeline.name}
                                                        </Link>
                                                        <span className="text-xs text-muted-foreground font-mono mt-1">
                                                            ID: #{pipeline.id.slice(0, 8)}
                                                        </span>
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4">
                                                    <p className="text-sm text-muted-foreground line-clamp-2">
                                                        {pipeline.description || `${pipeline.gate_count} quality gates configured`}
                                                    </p>
                                                </td>
                                                <td className="px-6 py-4">
                                                    <div className="flex flex-wrap gap-2">
                                                        {(pipeline.device_matrix || []).slice(0, 2).map((device) => (
                                                            <span
                                                                key={device}
                                                                className="inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium bg-accent text-foreground border border-border"
                                                            >
                                                                {device}
                                                            </span>
                                                        ))}
                                                        {(pipeline.device_matrix?.length || 0) > 2 && (
                                                            <span className="inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium bg-accent text-muted-foreground border border-border">
                                                                +{(pipeline.device_matrix?.length || 0) - 2}
                                                            </span>
                                                        )}
                                                        {(!pipeline.device_matrix || pipeline.device_matrix.length === 0) && (
                                                            <span className="text-xs text-muted-foreground">{pipeline.device_count} devices</span>
                                                        )}
                                                    </div>
                                                </td>
                                                <td className="px-6 py-4">
                                                    {pipeline.last_run ? (
                                                        <div className="flex items-center gap-2">
                                                            <StatusBadge status={getStatusFromRunStatus(pipeline.last_run.status)} />
                                                        </div>
                                                    ) : (
                                                        <span className="text-xs text-muted-foreground">No runs yet</span>
                                                    )}
                                                </td>
                                                <td className="px-6 py-4 text-right">
                                                    <Link href={`/workspace/${workspaceId}/pipelines/${pipeline.id}`}>
                                                        <button className="text-primary hover:text-primary/80 font-semibold text-sm inline-flex items-center gap-1 transition-colors">
                                                            <span className="material-symbols-outlined text-[18px]">play_arrow</span>
                                                            Run
                                                        </button>
                                                    </Link>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                            {/* Pagination */}
                            <div className="flex items-center justify-between px-6 py-4 border-t border-border bg-accent">
                                <span className="text-sm text-muted-foreground">
                                    Showing {filteredPipelines.length} of {pipelines.length} pipelines
                                </span>
                                <div className="flex items-center gap-2">
                                    <Button variant="outline" size="sm" disabled className="border-border">
                                        <span className="material-symbols-outlined text-[18px]">chevron_left</span>
                                    </Button>
                                    <Button variant="outline" size="sm" className="border-border bg-primary text-primary-foreground">1</Button>
                                    <Button variant="outline" size="sm" className="border-border">
                                        <span className="material-symbols-outlined text-[18px]">chevron_right</span>
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
