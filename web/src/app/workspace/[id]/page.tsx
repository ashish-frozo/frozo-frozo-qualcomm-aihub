"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface Run {
    id: string;
    status: string;
    created_at: string;
    pipeline: {
        name: string;
    };
}

interface Workspace {
    id: string;
    name: string;
}

export default function WorkspacePage() {
    const params = useParams();
    const workspaceId = params.id as string;
    const [workspace, setWorkspace] = useState<Workspace | null>(null);
    const [runs, setRuns] = useState<Run[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchData();
    }, [workspaceId]);

    const fetchData = async () => {
        const token = localStorage.getItem("token");
        if (!token) {
            window.location.href = "/login";
            return;
        }

        try {
            // Fetch workspace
            const wsRes = await fetch(
                `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/v1/workspaces/${workspaceId}`,
                { headers: { Authorization: `Bearer ${token}` } }
            );
            if (wsRes.ok) {
                const wsData = await wsRes.json();
                setWorkspace(wsData);
            }

            // Fetch runs
            const runsRes = await fetch(
                `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/v1/workspaces/${workspaceId}/runs`,
                { headers: { Authorization: `Bearer ${token}` } }
            );
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
                return "bg-blue-500/20 text-blue-400 border-blue-500/30";
            default:
                return "bg-slate-500/20 text-slate-400 border-slate-500/30";
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
            {/* Header */}
            <header className="border-b border-slate-800">
                <div className="container mx-auto px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <Link href="/dashboard" className="flex items-center gap-2">
                            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-500" />
                            <span className="text-xl font-bold text-white">EdgeGate</span>
                        </Link>
                        {workspace && (
                            <>
                                <span className="text-slate-600">/</span>
                                <span className="text-white font-medium">{workspace.name}</span>
                            </>
                        )}
                    </div>
                    <Link href="/dashboard">
                        <Button variant="ghost" className="text-slate-400 hover:text-white">
                            ← Back
                        </Button>
                    </Link>
                </div>
            </header>

            <main className="container mx-auto px-6 py-8">
                {/* Quick Actions */}
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
                            <div className="text-3xl font-bold text-cyan-400">—</div>
                            <div className="text-slate-400 text-sm">Devices</div>
                        </CardContent>
                    </Card>
                </div>

                {/* Recent Runs */}
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-xl font-bold text-white">Recent Runs</h2>
                </div>

                {loading ? (
                    <div className="text-slate-400 text-center py-12">Loading...</div>
                ) : runs.length === 0 ? (
                    <Card className="bg-slate-900/50 border-slate-800 border-dashed">
                        <CardContent className="py-12 text-center">
                            <p className="text-slate-400">No runs yet. Trigger a run from your CI pipeline.</p>
                        </CardContent>
                    </Card>
                ) : (
                    <div className="space-y-4">
                        {runs.map((run) => (
                            <Link key={run.id} href={`/workspace/${workspaceId}/runs/${run.id}`}>
                                <Card className="bg-slate-900/50 border-slate-800 hover:border-cyan-500/50 transition-colors cursor-pointer">
                                    <CardContent className="py-4 flex items-center justify-between">
                                        <div className="flex items-center gap-4">
                                            <span
                                                className={`px-3 py-1 rounded-full text-sm border ${getStatusColor(run.status)}`}
                                            >
                                                {run.status}
                                            </span>
                                            <span className="text-white font-medium">
                                                {run.pipeline?.name || "Pipeline"}
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
            </main>
        </div>
    );
}
