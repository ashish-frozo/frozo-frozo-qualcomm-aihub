"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Sidebar } from "@/components/Sidebar";

interface PipelineDetail {
    id: string;
    name: string;
    device_matrix: Array<{ name: string; enabled: boolean }>;
    promptpack_ref: { promptpack_id: string; version: string };
    gates: Array<{ metric: string; operator: string; threshold: number }>;
    run_policy: {
        warmup_runs: number;
        measurement_repeats: number;
        max_new_tokens: number;
        timeout_minutes: number;
    };
    created_at: string;
    updated_at: string;
}

interface Artifact {
    id: string;
    original_filename: string | null;
    kind: string;
}

interface Workspace {
    id: string;
    name: string;
}

export default function PipelineDetailPage() {
    const params = useParams();
    const router = useRouter();
    const workspaceId = params.id as string;
    const pipelineId = params.pipelineId as string;
    const [workspace, setWorkspace] = useState<Workspace | null>(null);
    const [pipeline, setPipeline] = useState<PipelineDetail | null>(null);
    const [artifacts, setArtifacts] = useState<Artifact[]>([]);
    const [selectedModelId, setSelectedModelId] = useState<string>("");
    const [loading, setLoading] = useState(true);
    const [triggering, setTriggering] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    // Helper to safely extract error message from API response
    const getErrorMessage = (data: any): string => {
        if (typeof data.detail === 'string') {
            return data.detail;
        }
        if (Array.isArray(data.detail) && data.detail.length > 0) {
            // Pydantic validation error format
            const firstError = data.detail[0];
            if (firstError.msg) {
                return firstError.msg;
            }
            return JSON.stringify(firstError);
        }
        if (data.detail?.message) {
            return data.detail.message;
        }
        if (typeof data.detail === 'object') {
            return JSON.stringify(data.detail);
        }
        return "An error occurred";
    };

    useEffect(() => {
        fetchData();
    }, [workspaceId, pipelineId]);

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
            const [wsRes, pipelineRes, artifactsRes] = await Promise.all([
                fetch(`${apiUrl}/v1/workspaces/${workspaceId}`, { headers }),
                fetch(`${apiUrl}/v1/workspaces/${workspaceId}/pipelines/${pipelineId}`, { headers }),
                fetch(`${apiUrl}/v1/workspaces/${workspaceId}/artifacts?kind=model`, { headers }),
            ]);

            if (wsRes.ok) {
                setWorkspace(await wsRes.json());
            }
            if (pipelineRes.ok) {
                setPipeline(await pipelineRes.json());
            }
            if (artifactsRes.ok) {
                const artifactsData = await artifactsRes.json();
                setArtifacts(artifactsData);
                if (artifactsData.length > 0) {
                    setSelectedModelId(artifactsData[0].id);
                }
            }
        } catch (err) {
            console.error("Failed to fetch data", err);
        } finally {
            setLoading(false);
        }
    };

    const triggerRun = async () => {
        const headers = getAuthHeader();
        if (!headers) return;

        setTriggering(true);
        setError("");
        setSuccess("");

        try {
            if (!selectedModelId) {
                setError("Please select a model artifact first");
                setTriggering(false);
                return;
            }

            const res = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/runs`, {
                method: "POST",
                headers: { ...headers, "Content-Type": "application/json" },
                body: JSON.stringify({
                    pipeline_id: pipelineId,
                    model_artifact_id: selectedModelId,
                    trigger: "manual"
                }),
            });

            if (res.ok) {
                const data = await res.json();
                setSuccess("Run triggered! Redirecting...");
                setTimeout(() => {
                    router.push(`/workspace/${workspaceId}/runs/${data.id}`);
                }, 1500);
            } else {
                const data = await res.json();
                setError(getErrorMessage(data));
            }
        } catch (err: any) {
            setError(err.message || "Failed to trigger run");
        } finally {
            setTriggering(false);
        }
    };

    const deletePipeline = async () => {
        if (!confirm("Are you sure you want to delete this pipeline?")) return;

        const headers = getAuthHeader();
        if (!headers) return;

        setDeleting(true);
        setError("");

        try {
            const res = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/pipelines/${pipelineId}`, {
                method: "DELETE",
                headers,
            });

            if (res.ok) {
                router.push(`/workspace/${workspaceId}/pipelines`);
            } else {
                const data = await res.json();
                setError(getErrorMessage(data));
            }
        } catch (err: any) {
            setError(err.message || "Delete failed");
        } finally {
            setDeleting(false);
        }
    };

    const getOperatorSymbol = (op: string) => {
        switch (op) {
            case "lt": return "<";
            case "lte": return "≤";
            case "gt": return ">";
            case "gte": return "≥";
            case "eq": return "=";
            default: return op;
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center">
                <div className="text-slate-400">Loading...</div>
            </div>
        );
    }

    if (!pipeline) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center">
                <div className="text-red-400">Pipeline not found</div>
            </div>
        );
    }

    const enabledDevices = pipeline.device_matrix.filter(d => d.enabled);

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex">
            <Sidebar workspaceId={workspaceId} workspaceName={workspace?.name || "Workspace"} />

            <main className="flex-1 p-8">
                <div className="max-w-4xl mx-auto">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-8">
                        <div>
                            <div className="flex items-center gap-2 text-sm text-slate-400 mb-2">
                                <Link href={`/workspace/${workspaceId}/pipelines`} className="hover:text-white">
                                    Pipelines
                                </Link>
                                <span>/</span>
                                <span className="text-white">{pipeline.name}</span>
                            </div>
                            <h1 className="text-2xl font-bold text-white">{pipeline.name}</h1>
                        </div>
                        <div className="flex gap-3 items-center">
                            {artifacts.length > 0 && (
                                <div className="flex flex-col mr-2">
                                    <label className="text-xs text-slate-500 mb-1 ml-1">Select Model</label>
                                    <select
                                        value={selectedModelId}
                                        onChange={(e) => setSelectedModelId(e.target.value)}
                                        className="bg-slate-900 border border-slate-700 text-white text-sm rounded-lg focus:ring-cyan-500 focus:border-cyan-500 block w-full p-2"
                                    >
                                        {artifacts.map((art) => (
                                            <option key={art.id} value={art.id}>
                                                {art.original_filename || `Model ${art.id.slice(0, 8)}`}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            )}
                            <Button
                                onClick={triggerRun}
                                disabled={triggering || artifacts.length === 0}
                                className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
                            >
                                {triggering ? "Triggering..." : "⚡ Trigger Run"}
                            </Button>
                            <Button
                                variant="outline"
                                onClick={deletePipeline}
                                disabled={deleting}
                                className="border-red-500/50 text-red-400 hover:bg-red-500/10"
                            >
                                {deleting ? "Deleting..." : "Delete"}
                            </Button>
                        </div>
                    </div>

                    {artifacts.length === 0 && (
                        <div className="mb-6 p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-400 flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                </svg>
                                <span>You need to upload a model artifact before you can trigger a run.</span>
                            </div>
                            <Link href={`/workspace/${workspaceId}/artifacts`}>
                                <Button size="sm" variant="outline" className="border-amber-500/50 text-amber-400 hover:bg-amber-500/10">
                                    Upload Model
                                </Button>
                            </Link>
                        </div>
                    )}

                    {/* Feedback */}
                    {error && (
                        <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400">
                            {error}
                        </div>
                    )}
                    {success && (
                        <div className="mb-6 p-4 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400">
                            {success}
                        </div>
                    )}

                    {/* Stats */}
                    <div className="grid md:grid-cols-3 gap-4 mb-8">
                        <Card className="bg-slate-900/50 border-slate-800">
                            <CardContent className="pt-6">
                                <div className="text-3xl font-bold text-white">{enabledDevices.length}</div>
                                <div className="text-slate-400 text-sm">Target Devices</div>
                            </CardContent>
                        </Card>
                        <Card className="bg-slate-900/50 border-slate-800">
                            <CardContent className="pt-6">
                                <div className="text-3xl font-bold text-white">{pipeline.gates.length}</div>
                                <div className="text-slate-400 text-sm">Quality Gates</div>
                            </CardContent>
                        </Card>
                        <Card className="bg-slate-900/50 border-slate-800">
                            <CardContent className="pt-6">
                                <div className="text-3xl font-bold text-cyan-400">
                                    v{pipeline.promptpack_ref.version}
                                </div>
                                <div className="text-slate-400 text-sm">PromptPack</div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Devices */}
                    <Card className="bg-slate-900/50 border-slate-800 mb-6">
                        <CardHeader>
                            <CardTitle className="text-white">Target Devices</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="flex flex-wrap gap-2">
                                {enabledDevices.map((device, i) => (
                                    <span
                                        key={i}
                                        className="px-3 py-1.5 bg-cyan-500/10 border border-cyan-500/30 rounded-lg text-cyan-400"
                                    >
                                        {device.name}
                                    </span>
                                ))}
                            </div>
                        </CardContent>
                    </Card>

                    {/* PromptPack */}
                    <Card className="bg-slate-900/50 border-slate-800 mb-6">
                        <CardHeader>
                            <CardTitle className="text-white">PromptPack</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="flex items-center gap-4">
                                <div className="h-12 w-12 rounded-lg bg-purple-500/20 flex items-center justify-center">
                                    <svg className="h-6 w-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                    </svg>
                                </div>
                                <div>
                                    <div className="text-white font-medium">{pipeline.promptpack_ref.promptpack_id}</div>
                                    <div className="text-sm text-slate-400">Version {pipeline.promptpack_ref.version}</div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Gates */}
                    <Card className="bg-slate-900/50 border-slate-800 mb-6">
                        <CardHeader>
                            <CardTitle className="text-white">Quality Gates</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            {pipeline.gates.map((gate, i) => (
                                <div
                                    key={i}
                                    className="flex items-center justify-between p-3 bg-slate-800/50 rounded-lg"
                                >
                                    <span className="text-white capitalize">
                                        {gate.metric.replace(/_/g, " ")}
                                    </span>
                                    <span className="text-cyan-400 font-mono">
                                        {getOperatorSymbol(gate.operator)} {gate.threshold}
                                    </span>
                                </div>
                            ))}
                        </CardContent>
                    </Card>

                    {/* Run Policy */}
                    <Card className="bg-slate-900/50 border-slate-800">
                        <CardHeader>
                            <CardTitle className="text-white">Run Policy</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                <div>
                                    <div className="text-slate-400 text-sm">Warmup Runs</div>
                                    <div className="text-white font-medium">{pipeline.run_policy.warmup_runs}</div>
                                </div>
                                <div>
                                    <div className="text-slate-400 text-sm">Repeats</div>
                                    <div className="text-white font-medium">{pipeline.run_policy.measurement_repeats}</div>
                                </div>
                                <div>
                                    <div className="text-slate-400 text-sm">Max Tokens</div>
                                    <div className="text-white font-medium">{pipeline.run_policy.max_new_tokens}</div>
                                </div>
                                <div>
                                    <div className="text-slate-400 text-sm">Timeout</div>
                                    <div className="text-white font-medium">{pipeline.run_policy.timeout_minutes} min</div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Metadata */}
                    <div className="mt-6 text-sm text-slate-500">
                        Created {new Date(pipeline.created_at).toLocaleString()} •
                        Updated {new Date(pipeline.updated_at).toLocaleString()}
                    </div>
                </div>
            </main>
        </div>
    );
}
