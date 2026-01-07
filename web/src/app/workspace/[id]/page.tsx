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
        name: string;
    };
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
}

export default function WorkspacePage() {
    const params = useParams();
    const workspaceId = params.id as string;
    const [workspace, setWorkspace] = useState<Workspace | null>(null);
    const [runs, setRuns] = useState<Run[]>([]);
    const [integration, setIntegration] = useState<Integration | null>(null);
    const [stats, setStats] = useState<Stats>({ pipelines: 0, promptpacks: 0, runs: 0, passed: 0, failed: 0 });
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
            // Fetch workspace
            const wsRes = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}`, { headers });
            if (wsRes.ok) {
                const wsData = await wsRes.json();
                setWorkspace(wsData);
            }

            // Fetch runs
            const runsRes = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/runs`, { headers });
            if (runsRes.ok) {
                const runsData = await runsRes.json();
                setRuns(runsData.slice(0, 5)); // Show only recent 5
                setStats(prev => ({
                    ...prev,
                    runs: runsData.length,
                    passed: runsData.filter((r: Run) => r.status === "passed").length,
                    failed: runsData.filter((r: Run) => r.status === "failed").length,
                }));
            }

            // Fetch pipelines count
            const pipelinesRes = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/pipelines`, { headers });
            if (pipelinesRes.ok) {
                const pipelinesData = await pipelinesRes.json();
                setStats(prev => ({ ...prev, pipelines: pipelinesData.length }));
            }

            // Fetch promptpacks count
            const ppRes = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/promptpacks`, { headers });
            if (ppRes.ok) {
                const ppData = await ppRes.json();
                setStats(prev => ({ ...prev, promptpacks: ppData.length }));
            }

            // Fetch integration
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

    if (loading) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center">
                <div className="text-slate-400">Loading...</div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex">
            <Sidebar workspaceId={workspaceId} workspaceName={workspace?.name || "Workspace"} />

            <main className="flex-1 p-8">
                <div className="max-w-6xl mx-auto">
                    {/* Header */}
                    <div className="mb-8">
                        <h1 className="text-2xl font-bold text-white">{workspace?.name || "Workspace"}</h1>
                        <p className="text-slate-400">Overview and quick actions</p>
                    </div>

                    {/* Integration Status */}
                    {!integration && (
                        <div className="mb-6 p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <svg className="h-5 w-5 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                </svg>
                                <span className="text-yellow-400">AI Hub not connected. Connect to run tests on real devices.</span>
                            </div>
                            <Link href={`/workspace/${workspaceId}/settings`}>
                                <Button size="sm" className="bg-yellow-500 hover:bg-yellow-600 text-black">
                                    Connect AI Hub
                                </Button>
                            </Link>
                        </div>
                    )}

                    {/* Stats Grid */}
                    <div className="grid md:grid-cols-4 gap-4 mb-8">
                        <Link href={`/workspace/${workspaceId}/pipelines`}>
                            <Card className="bg-slate-900/50 border-slate-800 hover:border-cyan-500/50 transition-colors cursor-pointer">
                                <CardContent className="pt-6">
                                    <div className="text-3xl font-bold text-white">{stats.pipelines}</div>
                                    <div className="text-slate-400 text-sm">Pipelines</div>
                                </CardContent>
                            </Card>
                        </Link>
                        <Link href={`/workspace/${workspaceId}/promptpacks`}>
                            <Card className="bg-slate-900/50 border-slate-800 hover:border-cyan-500/50 transition-colors cursor-pointer">
                                <CardContent className="pt-6">
                                    <div className="text-3xl font-bold text-white">{stats.promptpacks}</div>
                                    <div className="text-slate-400 text-sm">PromptPacks</div>
                                </CardContent>
                            </Card>
                        </Link>
                        <Card className="bg-slate-900/50 border-slate-800">
                            <CardContent className="pt-6">
                                <div className="text-3xl font-bold text-green-400">{stats.passed}</div>
                                <div className="text-slate-400 text-sm">Passed Runs</div>
                            </CardContent>
                        </Card>
                        <Card className="bg-slate-900/50 border-slate-800">
                            <CardContent className="pt-6">
                                <div className="text-3xl font-bold text-red-400">{stats.failed}</div>
                                <div className="text-slate-400 text-sm">Failed Runs</div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Quick Actions */}
                    <div className="grid md:grid-cols-3 gap-4 mb-8">
                        <Link href={`/workspace/${workspaceId}/pipelines/new`}>
                            <Card className="bg-slate-900/50 border-slate-800 hover:border-cyan-500/50 transition-colors cursor-pointer h-full">
                                <CardContent className="pt-6 flex items-center gap-4">
                                    <div className="h-12 w-12 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                                        <svg className="h-6 w-6 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                                        </svg>
                                    </div>
                                    <div>
                                        <div className="text-white font-medium">Create Pipeline</div>
                                        <div className="text-slate-400 text-sm">Set up a new test pipeline</div>
                                    </div>
                                </CardContent>
                            </Card>
                        </Link>
                        <Link href={`/workspace/${workspaceId}/promptpacks`}>
                            <Card className="bg-slate-900/50 border-slate-800 hover:border-cyan-500/50 transition-colors cursor-pointer h-full">
                                <CardContent className="pt-6 flex items-center gap-4">
                                    <div className="h-12 w-12 rounded-lg bg-purple-500/20 flex items-center justify-center">
                                        <svg className="h-6 w-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                                        </svg>
                                    </div>
                                    <div>
                                        <div className="text-white font-medium">Upload PromptPack</div>
                                        <div className="text-slate-400 text-sm">Add test cases</div>
                                    </div>
                                </CardContent>
                            </Card>
                        </Link>
                        <Link href={`/workspace/${workspaceId}/settings`}>
                            <Card className="bg-slate-900/50 border-slate-800 hover:border-cyan-500/50 transition-colors cursor-pointer h-full">
                                <CardContent className="pt-6 flex items-center gap-4">
                                    <div className="h-12 w-12 rounded-lg bg-slate-500/20 flex items-center justify-center">
                                        <svg className="h-6 w-6 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                        </svg>
                                    </div>
                                    <div>
                                        <div className="text-white font-medium">Settings</div>
                                        <div className="text-slate-400 text-sm">
                                            {integration ? `AI Hub: ••••${integration.token_last4}` : "Configure workspace"}
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        </Link>
                    </div>

                    {/* Recent Runs */}
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-xl font-bold text-white">Recent Runs</h2>
                        <Link href={`/workspace/${workspaceId}/runs`}>
                            <Button variant="ghost" className="text-slate-400 hover:text-white">
                                View All →
                            </Button>
                        </Link>
                    </div>

                    {runs.length === 0 ? (
                        <Card className="bg-slate-900/50 border-slate-800 border-dashed">
                            <CardContent className="py-12 text-center">
                                <p className="text-slate-400">No runs yet. Create a pipeline and trigger from CI.</p>
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
                </div>
            </main>
        </div>
    );
}
