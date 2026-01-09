"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { StatusBadge, getStatusFromRunStatus } from "@/components/ui/StatusBadge";
import { QualityGate } from "@/components/ui/QualityGate";
import { StatCard } from "@/components/ui/StatCard";

interface Run {
    id: string;
    status: string;
    created_at: string;
    completed_at: string | null;
    pipeline_name: string;
    bundle_artifact_id: string | null;
    model_artifact_id: string | null;
    normalized_metrics: Record<string, number> | null;
    device_metrics: Record<string, Record<string, number>> | null;
    gates_eval: {
        passed: boolean;
        gates: Array<{
            metric: string;
            operator: string;
            threshold: number;
            actual_value: number | null;
            passed: boolean;
            description?: string;
        }>;
    } | null;
}

export default function RunDetailPage() {
    const params = useParams();
    const workspaceId = params.id as string;
    const runId = params.runId as string;
    const [run, setRun] = useState<Run | null>(null);
    const [loading, setLoading] = useState(true);
    const [downloading, setDownloading] = useState(false);

    useEffect(() => {
        fetchRun();
        // eslint-disable-next-line react-hooks/exhaustive-deps
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

    const formatDuration = (start: string, end: string | null) => {
        if (!end) return "In progress...";
        const duration = new Date(end).getTime() - new Date(start).getTime();
        const minutes = Math.floor(duration / 60000);
        const seconds = Math.floor((duration % 60000) / 1000);
        return `${minutes}m ${seconds}s`;
    };

    const downloadReport = async () => {
        if (!run?.bundle_artifact_id) return;
        setDownloading(true);
        try {
            const token = localStorage.getItem("token");
            const res = await fetch(
                `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/v1/workspaces/${workspaceId}/runs/${runId}/bundle`,
                { headers: { Authorization: `Bearer ${token}` } }
            );
            if (res.ok) {
                const bundle = await res.json();
                const { jsPDF } = await import("jspdf");
                const doc = new jsPDF();

                // Header
                doc.setFillColor(13, 17, 23);
                doc.rect(0, 0, 210, 40, "F");
                doc.setTextColor(255, 255, 255);
                doc.setFontSize(24);
                doc.text("EdgeGate", 20, 25);
                doc.setFontSize(12);
                doc.text("Evidence Bundle Report", 20, 33);

                // Run Info
                doc.setTextColor(0, 0, 0);
                doc.setFontSize(14);
                doc.text(`Pipeline: ${bundle.pipeline_name || "N/A"}`, 20, 55);
                doc.setFontSize(10);
                doc.text(`Run ID: ${bundle.run_id}`, 20, 62);
                doc.text(`Status: ${bundle.status?.toUpperCase()}`, 20, 69);
                doc.text(`Generated: ${new Date().toLocaleString()}`, 20, 76);

                // Status Badge
                const statusColor = bundle.status === "passed" ? [35, 134, 54] : [218, 54, 51];
                doc.setFillColor(statusColor[0], statusColor[1], statusColor[2]);
                doc.roundedRect(150, 50, 40, 12, 2, 2, "F");
                doc.setTextColor(255, 255, 255);
                doc.setFontSize(10);
                doc.text(bundle.status?.toUpperCase() || "N/A", 160, 58);

                // Performance Metrics Section
                doc.setTextColor(0, 0, 0);
                doc.setFontSize(16);
                doc.text("Performance Metrics", 20, 95);
                doc.setDrawColor(200, 200, 200);
                doc.line(20, 98, 190, 98);

                let yPos = 108;
                if (bundle.normalized_metrics) {
                    doc.setFontSize(11);
                    Object.entries(bundle.normalized_metrics).forEach(([key, value]) => {
                        doc.setFillColor(241, 245, 249);
                        doc.rect(20, yPos - 5, 170, 12, "F");
                        doc.setTextColor(0, 0, 0);
                        doc.text(key.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()), 25, yPos + 3);
                        doc.text(String((value as number).toFixed(2)), 160, yPos + 3);
                        yPos += 15;
                    });
                }

                // Quality Gates Section
                yPos += 10;
                doc.setTextColor(0, 0, 0);
                doc.setFontSize(16);
                doc.text("Quality Gates", 20, yPos);
                doc.line(20, yPos + 3, 190, yPos + 3);
                yPos += 15;

                if (bundle.gates_eval?.gates) {
                    doc.setFontSize(10);
                    bundle.gates_eval.gates.forEach((gate: { metric: string; operator: string; threshold: number; actual_value: number; passed: boolean }) => {
                        const gateColor = gate.passed ? [220, 252, 231] : [254, 226, 226];
                        doc.setFillColor(gateColor[0], gateColor[1], gateColor[2]);
                        doc.rect(20, yPos - 5, 170, 14, "F");
                        const iconColor = gate.passed ? [35, 134, 54] : [218, 54, 51];
                        doc.setTextColor(iconColor[0], iconColor[1], iconColor[2]);
                        doc.text(gate.passed ? "✓" : "✗", 25, yPos + 4);
                        doc.setTextColor(0, 0, 0);
                        doc.text(gate.metric.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()), 35, yPos + 4);
                        doc.setTextColor(100, 100, 100);
                        doc.text(`${gate.operator} ${gate.threshold}`, 100, yPos + 4);
                        doc.setTextColor(iconColor[0], iconColor[1], iconColor[2]);
                        doc.text(gate.actual_value?.toFixed(2) || "N/A", 160, yPos + 4);
                        yPos += 18;
                    });
                }

                // Footer
                doc.setFillColor(13, 17, 23);
                doc.rect(0, 280, 210, 17, "F");
                doc.setTextColor(150, 150, 150);
                doc.setFontSize(8);
                doc.text("EdgeGate - Edge GenAI Regression Gates for Snapdragon", 20, 290);
                doc.text(`Bundle ID: ${bundle.bundle_artifact_id}`, 130, 290);

                doc.save(`evidence_report_${runId.slice(0, 8)}.pdf`);
            } else {
                alert("Failed to download evidence bundle");
            }
        } catch (err) {
            console.error("Failed to download bundle", err);
            alert("Failed to download evidence bundle");
        } finally {
            setDownloading(false);
        }
    };

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

    if (!run) {
        return (
            <div className="min-h-screen bg-background flex items-center justify-center">
                <div className="text-destructive">Run not found</div>
            </div>
        );
    }

    const gatesPassed = run.gates_eval?.gates.filter(g => g.passed).length || 0;
    const gatesFailed = run.gates_eval?.gates.filter(g => !g.passed).length || 0;

    return (
        <div className="min-h-screen bg-background text-foreground font-sans">
            {/* Top Navigation / Breadcrumbs */}
            <header className="sticky top-0 z-10 bg-background/95 backdrop-blur-sm border-b border-border px-8 py-4">
                <div className="flex flex-col gap-4 max-w-7xl mx-auto">
                    <div className="flex items-center justify-between">
                        {/* Breadcrumbs */}
                        <div className="flex items-center gap-2 text-sm">
                            <Link href="/dashboard" className="text-muted-foreground hover:text-foreground transition-colors">
                                EdgeGate
                            </Link>
                            <span className="material-symbols-outlined text-muted-foreground text-xs">chevron_right</span>
                            <Link href={`/workspace/${workspaceId}`} className="text-muted-foreground hover:text-foreground transition-colors">
                                Workspace
                            </Link>
                            <span className="material-symbols-outlined text-muted-foreground text-xs">chevron_right</span>
                            <Link href={`/workspace/${workspaceId}/runs`} className="text-muted-foreground hover:text-foreground transition-colors">
                                Runs
                            </Link>
                            <span className="material-symbols-outlined text-muted-foreground text-xs">chevron_right</span>
                            <span className="text-foreground font-medium font-mono">{run.id.slice(0, 8)}</span>
                        </div>
                        {/* Quick Actions */}
                        <div className="flex gap-3">
                            <Button
                                variant="outline"
                                className="border-border hover:bg-accent text-muted-foreground"
                                onClick={downloadReport}
                                disabled={!run.bundle_artifact_id || downloading}
                            >
                                <span className="material-symbols-outlined text-lg mr-2">download</span>
                                {downloading ? "Generating..." : "Download Report"}
                            </Button>
                            <Button className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold shadow-lg shadow-primary/20">
                                <span className="material-symbols-outlined text-lg mr-2">replay</span>
                                Re-run
                            </Button>
                        </div>
                    </div>
                    {/* Page Heading & Meta */}
                    <div className="flex items-end justify-between pb-2">
                        <div className="flex flex-col gap-2">
                            <div className="flex items-center gap-4">
                                <h1 className="text-foreground text-3xl font-black tracking-tight">
                                    Run #{run.id.slice(0, 8)}
                                </h1>
                                <StatusBadge status={getStatusFromRunStatus(run.status)} />
                            </div>
                            <p className="text-muted-foreground text-sm flex items-center gap-2">
                                <span className="material-symbols-outlined text-lg">schedule</span>
                                Duration: {formatDuration(run.created_at, run.completed_at)} • Started {new Date(run.created_at).toLocaleString()}
                            </p>
                        </div>
                    </div>
                </div>
            </header>

            {/* Content Body */}
            <div className="p-8 max-w-7xl mx-auto w-full flex flex-col gap-6">
                {/* Summary Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                    <StatCard
                        title="Pipeline"
                        value={run.pipeline_name || "Default Pipeline"}
                        icon="alt_route"
                    />
                    <StatCard
                        title="Device"
                        value={Object.keys(run.device_metrics || {})[0] || "sm8650"}
                        icon="smartphone"
                    />
                    <StatCard
                        title="Inference Time"
                        value={`${(run.normalized_metrics?.inference_time_ms || 0).toFixed(3)} ms`}
                        icon="speed"
                    />
                    <StatCard
                        title="Peak Memory"
                        value={`${(run.normalized_metrics?.peak_memory_mb || 0).toFixed(1)} MB`}
                        icon="memory"
                    />
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Quality Gates Section */}
                    <div className="lg:col-span-1 flex flex-col gap-4">
                        <div className="flex items-center justify-between">
                            <h3 className="text-foreground font-bold text-lg">Quality Gates</h3>
                            <span className="text-xs text-muted-foreground bg-accent px-2 py-1 rounded">
                                {gatesPassed} Pass, {gatesFailed} Fail
                            </span>
                        </div>
                        <div className="bg-card rounded-xl border border-border p-5 flex flex-col gap-6">
                            {run.gates_eval?.gates.map((gate, i) => (
                                <QualityGate
                                    key={i}
                                    metric={gate.metric}
                                    actualValue={gate.actual_value}
                                    threshold={gate.threshold}
                                    operator={gate.operator as "lt" | "lte" | "gt" | "gte" | "eq"}
                                    passed={gate.passed}
                                    unit={gate.metric.includes("time") ? "ms" : gate.metric.includes("memory") ? "MB" : ""}
                                />
                            )) || (
                                    <p className="text-muted-foreground text-sm">No gates configured</p>
                                )}
                        </div>
                    </div>

                    {/* Performance Analysis Section */}
                    <div className="lg:col-span-2 flex flex-col gap-4">
                        <div className="flex items-center justify-between">
                            <h3 className="text-foreground font-bold text-lg">Performance Summary</h3>
                        </div>
                        <div className="bg-card rounded-xl border border-border p-5">
                            {run.normalized_metrics && Object.keys(run.normalized_metrics).length > 0 ? (
                                <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
                                    {Object.entries(run.normalized_metrics).map(([key, value]) => (
                                        <div key={key} className="flex flex-col">
                                            <span className="text-muted-foreground text-xs uppercase tracking-wider mb-1">
                                                {key.replace(/_/g, " ")}
                                            </span>
                                            <span className="text-foreground text-2xl font-bold font-mono">
                                                {typeof value === "number" ? value.toFixed(3) : value}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <div className="text-center py-8 text-muted-foreground">
                                    <span className="material-symbols-outlined text-4xl mb-2 block">analytics</span>
                                    No metrics available yet
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Device-specific Metrics */}
                {run.device_metrics && Object.keys(run.device_metrics).length > 0 && (
                    <div className="flex flex-col gap-4">
                        <h3 className="text-foreground font-bold text-lg">Device Breakdown</h3>
                        <div className="bg-card rounded-xl border border-border overflow-hidden">
                            <table className="w-full text-left border-collapse">
                                <thead>
                                    <tr className="bg-accent border-b border-border">
                                        <th className="py-3 px-6 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Device</th>
                                        <th className="py-3 px-6 text-xs font-semibold uppercase tracking-wider text-muted-foreground text-right">Inference Time</th>
                                        <th className="py-3 px-6 text-xs font-semibold uppercase tracking-wider text-muted-foreground text-right">Peak Memory</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-border">
                                    {Object.entries(run.device_metrics).map(([device, metrics]) => (
                                        <tr key={device} className="hover:bg-accent/50 transition-colors">
                                            <td className="py-3 px-6 text-sm font-medium text-foreground flex items-center gap-2">
                                                <span className="material-symbols-outlined text-muted-foreground">smartphone</span>
                                                {device}
                                            </td>
                                            <td className="py-3 px-6 text-sm text-emerald-400 font-mono text-right">
                                                {(metrics.inference_time_ms || 0).toFixed(3)} ms
                                            </td>
                                            <td className="py-3 px-6 text-sm text-foreground font-mono text-right">
                                                {(metrics.peak_memory_mb || 0).toFixed(1)} MB
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
