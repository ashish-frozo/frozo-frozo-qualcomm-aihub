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
    pipeline_name: string;
    normalized_metrics: Record<string, number> | null;
    gates_eval: {
        passed: boolean;
        gates: Array<{
            metric: string;
            operator: string;
            threshold: number;
            actual_value: number;
            passed: boolean;
        }>;
    } | null;
}

export default function RunDetailPage() {
    const params = useParams();
    const workspaceId = params.id as string;
    const runId = params.runId as string;
    const [run, setRun] = useState<Run | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchRun();
    }, [workspaceId, runId]);

    const fetchRun = async () => {
        const token = localStorage.getItem("token");
        if (!token) {
            window.location.href = "/login";
            return;
        }

        try {
            const res = await fetch(
                `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/v1/workspaces/${workspaceId}/runs/${runId}`,
                { headers: { Authorization: `Bearer ${token}` } }
            );
            if (res.ok) {
                const data = await res.json();
                setRun(data);
            }
        } catch (err) {
            console.error("Failed to fetch run", err);
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

    if (!run) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center">
                <div className="text-red-400">Run not found</div>
            </div>
        );
    }

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
                        <span className="text-slate-600">/</span>
                        <Link href={`/workspace/${workspaceId}`} className="text-slate-400 hover:text-white">
                            Workspace
                        </Link>
                        <span className="text-slate-600">/</span>
                        <span className="text-white font-mono">{run.id.slice(0, 8)}</span>
                    </div>
                    <Link href={`/workspace/${workspaceId}`}>
                        <Button variant="ghost" className="text-slate-400 hover:text-white">
                            ← Back
                        </Button>
                    </Link>
                </div>
            </header>

            <main className="container mx-auto px-6 py-8">
                {/* Run Header */}
                <div className="flex items-center gap-4 mb-8">
                    <span className={`px-4 py-2 rounded-full text-lg border ${getStatusColor(run.status)}`}>
                        {run.status.toUpperCase()}
                    </span>
                    <div>
                        <h1 className="text-2xl font-bold text-white">{run.pipeline_name || "Run"}</h1>
                        <p className="text-slate-400">
                            Started {new Date(run.created_at).toLocaleString()}
                        </p>
                    </div>
                </div>

                {/* Metrics */}
                <h2 className="text-xl font-bold text-white mb-4">Performance Metrics</h2>
                <div className="grid md:grid-cols-3 gap-4 mb-8">
                    {run.normalized_metrics ? (
                        Object.entries(run.normalized_metrics).map(([key, value]) => (
                            <Card key={key} className="bg-slate-900/50 border-slate-800">
                                <CardContent className="pt-6">
                                    <div className="text-3xl font-bold text-white">
                                        {typeof value === "number" ? value.toFixed(2) : value}
                                    </div>
                                    <div className="text-slate-400 text-sm capitalize">
                                        {key.replace(/_/g, " ")}
                                    </div>
                                </CardContent>
                            </Card>
                        ))
                    ) : (
                        <Card className="bg-slate-900/50 border-slate-800 md:col-span-3">
                            <CardContent className="py-8 text-center text-slate-400">
                                No metrics available yet
                            </CardContent>
                        </Card>
                    )}
                </div>

                {/* Gate Evaluations */}
                <h2 className="text-xl font-bold text-white mb-4">Quality Gates</h2>
                {run.gates_eval ? (
                    <div className="space-y-4">
                        {run.gates_eval.gates.map((gate, i) => (
                            <Card
                                key={i}
                                className={`border ${gate.passed ? "bg-green-500/5 border-green-500/20" : "bg-red-500/5 border-red-500/20"}`}
                            >
                                <CardContent className="py-4 flex items-center justify-between">
                                    <div className="flex items-center gap-4">
                                        <span
                                            className={`h-8 w-8 rounded-full flex items-center justify-center ${gate.passed ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}
                                        >
                                            {gate.passed ? "✓" : "✗"}
                                        </span>
                                        <div>
                                            <span className="text-white font-medium capitalize">
                                                {gate.metric.replace(/_/g, " ")}
                                            </span>
                                            <span className="text-slate-400 ml-2">
                                                {gate.operator} {gate.threshold}
                                            </span>
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <div className={`text-lg font-bold ${gate.passed ? "text-green-400" : "text-red-400"}`}>
                                            {gate.actual_value.toFixed(2)}
                                        </div>
                                        <div className="text-slate-500 text-sm">Actual</div>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                ) : (
                    <Card className="bg-slate-900/50 border-slate-800">
                        <CardContent className="py-8 text-center text-slate-400">
                            No gate evaluations available
                        </CardContent>
                    </Card>
                )}

                {/* Evidence Bundle */}
                <div className="mt-8">
                    <Button
                        variant="outline"
                        className="border-slate-700 text-white hover:bg-slate-800"
                        disabled
                    >
                        Download Evidence Bundle (Coming Soon)
                    </Button>
                </div>
            </main>
        </div>
    );
}
