"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Sidebar } from "@/components/Sidebar";

interface Run {
    id: string;
    status: string;
    created_at: string;
    pipeline: {
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

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    useEffect(() => {
        fetchData();
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

    const getStatusColor = (status: string) => {
        switch (status) {
            case "passed":
                return "bg-green-500/20 text-green-400 border-green-500/30";
            case "failed":
                return "bg-red-500/20 text-red-400 border-red-500/30";
            case "running":
            case "submitting":
            case "collecting":
            case "evaluating":
                return "bg-blue-500/20 text-blue-400 border-blue-500/30";
            case "queued":
            case "preparing":
                return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
            case "error":
                return "bg-red-500/20 text-red-400 border-red-500/30";
            default:
                return "bg-slate-500/20 text-slate-400 border-slate-500/30";
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex">
            <Sidebar workspaceId={workspaceId} workspaceName={workspace?.name || "Loading..."} />

            <main className="flex-1 p-8">
                <div className="max-w-6xl mx-auto">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-8">
                        <div>
                            <h1 className="text-2xl font-bold text-white">Runs</h1>
                            <p className="text-slate-400">Test execution history</p>
                        </div>
                    </div>

                    {/* Stats */}
                    <div className="grid md:grid-cols-4 gap-4 mb-8">
                        <Card className="bg-slate-900/50 border-slate-800">
                            <CardContent className="pt-6">
                                <div className="text-3xl font-bold text-white">{runs.length}</div>
                                <div className="text-slate-400 text-sm">Total Runs</div>
                            </CardContent>
                        </Card>
                        <Card className="bg-slate-900/50 border-slate-800">
                            <CardContent className="pt-6">
                                <div className="text-3xl font-bold text-green-400">
                                    {runs.filter((r) => r.status === "passed").length}
                                </div>
                                <div className="text-slate-400 text-sm">Passed</div>
                            </CardContent>
                        </Card>
                        <Card className="bg-slate-900/50 border-slate-800">
                            <CardContent className="pt-6">
                                <div className="text-3xl font-bold text-red-400">
                                    {runs.filter((r) => r.status === "failed").length}
                                </div>
                                <div className="text-slate-400 text-sm">Failed</div>
                            </CardContent>
                        </Card>
                        <Card className="bg-slate-900/50 border-slate-800">
                            <CardContent className="pt-6">
                                <div className="text-3xl font-bold text-blue-400">
                                    {runs.filter((r) => ["running", "queued", "preparing", "submitting", "collecting", "evaluating"].includes(r.status)).length}
                                </div>
                                <div className="text-slate-400 text-sm">In Progress</div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Content */}
                    {loading ? (
                        <div className="text-slate-400 text-center py-12">Loading...</div>
                    ) : runs.length === 0 ? (
                        <Card className="bg-slate-900/50 border-slate-800 border-dashed">
                            <CardContent className="py-16 text-center">
                                <div className="h-16 w-16 mx-auto mb-4 rounded-full bg-slate-800 flex items-center justify-center">
                                    <svg className="h-8 w-8 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                                    </svg>
                                </div>
                                <h3 className="text-lg font-medium text-white mb-2">No runs yet</h3>
                                <p className="text-slate-400 mb-6 max-w-md mx-auto">
                                    Runs are created when you trigger a pipeline from CI or manually.
                                </p>
                                <Link href={`/workspace/${workspaceId}/pipelines`}>
                                    <Button variant="outline" className="border-slate-700 text-white hover:bg-slate-800">
                                        View Pipelines
                                    </Button>
                                </Link>
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="space-y-3">
                            {runs.map((run) => (
                                <Link key={run.id} href={`/workspace/${workspaceId}/runs/${run.id}`}>
                                    <Card className="bg-slate-900/50 border-slate-800 hover:border-cyan-500/50 transition-colors cursor-pointer">
                                        <CardContent className="py-4 flex items-center justify-between">
                                            <div className="flex items-center gap-4">
                                                <span className={`px-3 py-1 rounded-full text-sm border ${getStatusColor(run.status)}`}>
                                                    {run.status}
                                                </span>
                                                <span className="text-white font-medium">
                                                    {run.pipeline?.name || "Unknown Pipeline"}
                                                </span>
                                                <span className="text-slate-500 text-sm font-mono">
                                                    {run.id.slice(0, 8)}
                                                </span>
                                            </div>
                                            <span className="text-slate-400 text-sm">
                                                {new Date(run.created_at).toLocaleString()}
                                            </span>
                                        </CardContent>
                                    </Card>
                                </Link>
                            ))}
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
