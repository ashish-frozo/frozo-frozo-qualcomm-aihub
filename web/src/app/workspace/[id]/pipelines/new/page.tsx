"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sidebar } from "@/components/Sidebar";

interface PromptPack {
    id: string;
    promptpack_id: string;
    version: string;
    name: string;
}

interface Workspace {
    id: string;
    name: string;
}

// Common Snapdragon devices available on AI Hub
const AVAILABLE_DEVICES = [
    { name: "Snapdragon 8 Gen 3", id: "sm8650" },
    { name: "Snapdragon 8 Gen 2", id: "sm8550" },
    { name: "Snapdragon 8 Gen 1", id: "sm8450" },
    { name: "Snapdragon 888", id: "sm8350" },
    { name: "Snapdragon 7+ Gen 2", id: "sm7550" },
];

// Standard gate metrics (must match API's VALID_METRICS)
const AVAILABLE_METRICS = [
    { id: "peak_memory_mb", name: "Peak Memory (MB)", defaultOp: "lte", defaultValue: 3500 },
    { id: "inference_time_ms", name: "Inference Time (ms)", defaultOp: "lte", defaultValue: 1000 },
    { id: "ttft_ms", name: "Time to First Token (ms)", defaultOp: "lte", defaultValue: 1500 },
    { id: "tps", name: "Tokens/Second", defaultOp: "gte", defaultValue: 10 },
    { id: "npu_compute_percent", name: "NPU Compute %", defaultOp: "gte", defaultValue: 50 },
    { id: "gpu_compute_percent", name: "GPU Compute %", defaultOp: "lte", defaultValue: 30 },
    { id: "cpu_compute_percent", name: "CPU Compute %", defaultOp: "lte", defaultValue: 20 },
];

export default function NewPipelinePage() {
    const params = useParams();
    const router = useRouter();
    const workspaceId = params.id as string;
    const [workspace, setWorkspace] = useState<Workspace | null>(null);
    const [promptpacks, setPromptpacks] = useState<PromptPack[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");

    // Form state
    const [name, setName] = useState("");
    const [selectedDevices, setSelectedDevices] = useState<string[]>(["sm8650"]);
    const [selectedPromptpack, setSelectedPromptpack] = useState<{ id: string; version: string } | null>(null);
    const [gates, setGates] = useState([
        { metric: "peak_memory_mb", operator: "lte", threshold: 3500 },
        { metric: "tps", operator: "gte", threshold: 10 },
    ]);

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

            const ppRes = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/promptpacks`, { headers });
            if (ppRes.ok) {
                const ppData = await ppRes.json();
                setPromptpacks(ppData);
                if (ppData.length > 0) {
                    setSelectedPromptpack({ id: ppData[0].promptpack_id, version: ppData[0].version });
                }
            }
        } catch (err) {
            console.error("Failed to fetch data", err);
        } finally {
            setLoading(false);
        }
    };

    const toggleDevice = (deviceId: string) => {
        setSelectedDevices((prev) =>
            prev.includes(deviceId) ? prev.filter((d) => d !== deviceId) : [...prev, deviceId]
        );
    };

    const addGate = () => {
        setGates([...gates, { metric: "tokens_per_sec", operator: "gte", threshold: 10 }]);
    };

    const removeGate = (index: number) => {
        setGates(gates.filter((_, i) => i !== index));
    };

    const updateGate = (index: number, field: string, value: any) => {
        const updated = [...gates];
        updated[index] = { ...updated[index], [field]: value };
        setGates(updated);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedPromptpack) {
            setError("Please select a PromptPack");
            return;
        }
        if (selectedDevices.length === 0) {
            setError("Please select at least one device");
            return;
        }

        const headers = getAuthHeader();
        if (!headers) return;

        setSaving(true);
        setError("");

        try {
            const res = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/pipelines`, {
                method: "POST",
                headers: { ...headers, "Content-Type": "application/json" },
                body: JSON.stringify({
                    name,
                    device_matrix: selectedDevices.map((d) => ({ name: d, enabled: true })),
                    promptpack_ref: {
                        promptpack_id: selectedPromptpack.id,
                        version: selectedPromptpack.version,
                    },
                    gates: gates.map((g) => ({
                        metric: g.metric,
                        operator: g.operator,
                        threshold: g.threshold,
                    })),
                    run_policy: {
                        warmup_runs: 1,
                        measurement_repeats: 3,
                        max_new_tokens: 128,
                        timeout_minutes: 20,
                    },
                }),
            });

            if (res.ok) {
                router.push(`/workspace/${workspaceId}/pipelines`);
            } else {
                const data = await res.json();
                setError(data.detail?.message || data.detail || "Failed to create pipeline");
            }
        } catch (err: any) {
            setError(err.message || "Failed to create pipeline");
        } finally {
            setSaving(false);
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
            <Sidebar workspaceId={workspaceId} workspaceName={workspace?.name || "Loading..."} />

            <main className="flex-1 p-8">
                <div className="max-w-3xl mx-auto">
                    <div className="flex items-center gap-4 mb-8">
                        <Link href={`/workspace/${workspaceId}/pipelines`}>
                            <Button variant="ghost" className="text-slate-400 hover:text-white">
                                ← Back
                            </Button>
                        </Link>
                        <h1 className="text-2xl font-bold text-white">Create Pipeline</h1>
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-8">
                        {/* Basic Info */}
                        <Card className="bg-slate-900/50 border-slate-800">
                            <CardHeader>
                                <CardTitle className="text-white">Basic Information</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="space-y-2">
                                    <Label htmlFor="name" className="text-slate-300">Pipeline Name</Label>
                                    <Input
                                        id="name"
                                        value={name}
                                        onChange={(e) => setName(e.target.value)}
                                        placeholder="e.g., Production Latency Tests"
                                        className="bg-slate-800/50 border-slate-700 text-white"
                                        required
                                    />
                                </div>
                            </CardContent>
                        </Card>

                        {/* Device Selection */}
                        <Card className="bg-slate-900/50 border-slate-800">
                            <CardHeader>
                                <CardTitle className="text-white">Target Devices</CardTitle>
                                <CardDescription className="text-slate-400">
                                    Select Snapdragon devices to run tests on
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                <div className="grid grid-cols-2 gap-3">
                                    {AVAILABLE_DEVICES.map((device) => (
                                        <button
                                            key={device.id}
                                            type="button"
                                            onClick={() => toggleDevice(device.id)}
                                            className={`p-4 rounded-lg border text-left transition-colors ${selectedDevices.includes(device.id)
                                                ? "bg-cyan-500/10 border-cyan-500/50 text-cyan-400"
                                                : "bg-slate-800/50 border-slate-700 text-slate-300 hover:border-slate-600"
                                                }`}
                                        >
                                            <div className="font-medium">{device.name}</div>
                                            <div className="text-sm opacity-70">{device.id}</div>
                                        </button>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>

                        {/* PromptPack Selection */}
                        <Card className="bg-slate-900/50 border-slate-800">
                            <CardHeader>
                                <CardTitle className="text-white">PromptPack</CardTitle>
                                <CardDescription className="text-slate-400">
                                    Select which test cases to run
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                {promptpacks.length === 0 ? (
                                    <div className="text-center py-8">
                                        <p className="text-slate-400 mb-4">No PromptPacks available</p>
                                        <Link href={`/workspace/${workspaceId}/promptpacks`}>
                                            <Button variant="outline" className="border-slate-700 text-white">
                                                Upload PromptPack First
                                            </Button>
                                        </Link>
                                    </div>
                                ) : (
                                    <div className="space-y-2">
                                        {promptpacks.map((pp) => (
                                            <button
                                                key={`${pp.promptpack_id}-${pp.version}`}
                                                type="button"
                                                onClick={() => setSelectedPromptpack({ id: pp.promptpack_id, version: pp.version })}
                                                className={`w-full p-4 rounded-lg border text-left transition-colors ${selectedPromptpack?.id === pp.promptpack_id && selectedPromptpack?.version === pp.version
                                                    ? "bg-cyan-500/10 border-cyan-500/50"
                                                    : "bg-slate-800/50 border-slate-700 hover:border-slate-600"
                                                    }`}
                                            >
                                                <div className="font-medium text-white">{pp.name}</div>
                                                <div className="text-sm text-slate-400">
                                                    {pp.promptpack_id} v{pp.version}
                                                </div>
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </CardContent>
                        </Card>

                        {/* Quality Gates */}
                        <Card className="bg-slate-900/50 border-slate-800">
                            <CardHeader>
                                <CardTitle className="text-white">Quality Gates</CardTitle>
                                <CardDescription className="text-slate-400">
                                    Define pass/fail criteria for your tests
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                {gates.map((gate, index) => (
                                    <div key={index} className="flex items-center gap-3 p-4 bg-slate-800/50 rounded-lg">
                                        <select
                                            value={gate.metric}
                                            onChange={(e) => updateGate(index, "metric", e.target.value)}
                                            className="flex-1 px-3 py-2 bg-slate-700 border border-slate-600 rounded text-white"
                                        >
                                            {AVAILABLE_METRICS.map((m) => (
                                                <option key={m.id} value={m.id}>{m.name}</option>
                                            ))}
                                        </select>
                                        <select
                                            value={gate.operator}
                                            onChange={(e) => updateGate(index, "operator", e.target.value)}
                                            className="w-24 px-3 py-2 bg-slate-700 border border-slate-600 rounded text-white"
                                        >
                                            <option value="lte">≤</option>
                                            <option value="lt">&lt;</option>
                                            <option value="gte">≥</option>
                                            <option value="gt">&gt;</option>
                                            <option value="eq">=</option>
                                        </select>
                                        <Input
                                            type="number"
                                            value={gate.threshold}
                                            onChange={(e) => updateGate(index, "threshold", parseFloat(e.target.value))}
                                            className="w-32 bg-slate-700 border-slate-600 text-white"
                                            step="any"
                                        />
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            onClick={() => removeGate(index)}
                                            className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                                        >
                                            ✕
                                        </Button>
                                    </div>
                                ))}
                                <Button
                                    type="button"
                                    variant="outline"
                                    onClick={addGate}
                                    className="w-full border-dashed border-slate-700 text-slate-400 hover:text-white hover:bg-slate-800"
                                >
                                    + Add Gate
                                </Button>
                            </CardContent>
                        </Card>

                        {/* Error */}
                        {error && (
                            <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400">
                                {error}
                            </div>
                        )}

                        {/* Submit */}
                        <div className="flex gap-4">
                            <Button
                                type="submit"
                                disabled={saving || !name || selectedDevices.length === 0}
                                className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
                            >
                                {saving ? "Creating..." : "Create Pipeline"}
                            </Button>
                            <Link href={`/workspace/${workspaceId}/pipelines`}>
                                <Button type="button" variant="outline" className="border-slate-700 text-white">
                                    Cancel
                                </Button>
                            </Link>
                        </div>
                    </form>
                </div>
            </main>
        </div>
    );
}
