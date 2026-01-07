"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Sidebar } from "@/components/Sidebar";

interface Pipeline {
    id: string;
    name: string;
    device_count: number;
    gate_count: number;
    promptpack_id: string;
    promptpack_version: string;
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

            // Fetch pipelines
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

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex">
            {/* Sidebar */}
            <Sidebar workspaceId={workspaceId} workspaceName={workspace?.name || "Loading..."} />

            {/* Main Content */}
            <main className="flex-1 p-8">
                <div className="max-w-6xl mx-auto">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-8">
                        <div>
                            <h1 className="text-2xl font-bold text-white">Pipelines</h1>
                            <p className="text-slate-400">Configure testing pipelines for your models</p>
                        </div>
                        <Link href={`/workspace/${workspaceId}/pipelines/new`}>
                            <Button className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600">
                                + New Pipeline
                            </Button>
                        </Link>
                    </div>

                    {/* Content */}
                    {loading ? (
                        <div className="text-slate-400 text-center py-12">Loading...</div>
                    ) : pipelines.length === 0 ? (
                        <Card className="bg-slate-900/50 border-slate-800 border-dashed">
                            <CardContent className="py-16 text-center">
                                <div className="h-16 w-16 mx-auto mb-4 rounded-full bg-slate-800 flex items-center justify-center">
                                    <svg className="h-8 w-8 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
                                    </svg>
                                </div>
                                <h3 className="text-lg font-medium text-white mb-2">No pipelines yet</h3>
                                <p className="text-slate-400 mb-6 max-w-md mx-auto">
                                    Create a pipeline to define testing criteria for your AI models on Snapdragon devices.
                                </p>
                                <Link href={`/workspace/${workspaceId}/pipelines/new`}>
                                    <Button className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600">
                                        Create Your First Pipeline
                                    </Button>
                                </Link>
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="grid md:grid-cols-2 gap-6">
                            {pipelines.map((pipeline) => (
                                <Link key={pipeline.id} href={`/workspace/${workspaceId}/pipelines/${pipeline.id}`}>
                                    <Card className="bg-slate-900/50 border-slate-800 hover:border-cyan-500/50 transition-colors cursor-pointer h-full">
                                        <CardHeader>
                                            <CardTitle className="text-white flex items-center justify-between">
                                                <span>{pipeline.name}</span>
                                                <svg className="h-5 w-5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                                </svg>
                                            </CardTitle>
                                            <CardDescription className="text-slate-400">
                                                Created {new Date(pipeline.created_at).toLocaleDateString()}
                                            </CardDescription>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="grid grid-cols-3 gap-4 text-sm">
                                                <div>
                                                    <div className="text-slate-400">Devices</div>
                                                    <div className="text-white font-medium">{pipeline.device_count}</div>
                                                </div>
                                                <div>
                                                    <div className="text-slate-400">Gates</div>
                                                    <div className="text-white font-medium">{pipeline.gate_count}</div>
                                                </div>
                                                <div>
                                                    <div className="text-slate-400">PromptPack</div>
                                                    <div className="text-white font-medium truncate" title={pipeline.promptpack_id}>
                                                        v{pipeline.promptpack_version}
                                                    </div>
                                                </div>
                                            </div>
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
