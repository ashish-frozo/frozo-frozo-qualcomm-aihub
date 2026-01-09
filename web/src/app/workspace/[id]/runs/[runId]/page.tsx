"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

interface Run {
    id: string;
    status: string;
    created_at: string;
    completed_at: string | null;
    pipeline_name: string;
    bundle_artifact_id: string | null;
    model_artifact_id: string | null;
    model_artifact?: {
        original_filename: string;
    };
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

    const formatOperator = (op: string) => {
        const map: Record<string, string> = { lt: "<", lte: "≤", gt: ">", gte: "≥", eq: "=" };
        return map[op] || op;
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
                doc.setFillColor(16, 25, 34);
                doc.rect(0, 0, 210, 40, "F");
                doc.setTextColor(255, 255, 255);
                doc.setFontSize(24);
                doc.text("EdgeGate", 20, 25);
                doc.setFontSize(12);
                doc.text("Evidence Bundle Report", 20, 33);
                doc.setTextColor(0, 0, 0);
                doc.setFontSize(14);
                doc.text(`Pipeline: ${bundle.pipeline_name || "N/A"}`, 20, 55);
                doc.setFontSize(10);
                doc.text(`Run ID: ${bundle.run_id}`, 20, 62);
                doc.text(`Status: ${bundle.status?.toUpperCase()}`, 20, 69);
                doc.save(`evidence_report_${runId.slice(0, 8)}.pdf`);
            }
        } catch (err) {
            console.error("Failed to download bundle", err);
        } finally {
            setDownloading(false);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: "#101922" }}>
                <div className="flex items-center gap-2" style={{ color: "#92adc9" }}>
                    <span className="material-symbols-outlined animate-spin">sync</span>
                    <span>Loading...</span>
                </div>
            </div>
        );
    }

    if (!run) {
        return (
            <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: "#101922" }}>
                <div style={{ color: "#ef4444" }}>Run not found</div>
            </div>
        );
    }

    const gatesPassed = run.gates_eval?.gates.filter(g => g.passed).length || 0;
    const gatesFailed = run.gates_eval?.gates.filter(g => !g.passed).length || 0;
    const statusColor = run.status === "passed" ? "#10b981" : run.status === "failed" ? "#ef4444" : "#3b82f6";
    const statusBg = run.status === "passed" ? "rgba(16,185,129,0.1)" : run.status === "failed" ? "rgba(239,68,68,0.1)" : "rgba(59,130,246,0.1)";
    const statusBorder = run.status === "passed" ? "rgba(16,185,129,0.2)" : run.status === "failed" ? "rgba(239,68,68,0.2)" : "rgba(59,130,246,0.2)";

    return (
        <div className="min-h-screen flex overflow-hidden" style={{ backgroundColor: "#101922", color: "#f1f5f9", fontFamily: "Inter, sans-serif" }}>
            {/* Sidebar */}
            <div className="w-64 flex-shrink-0 hidden md:flex flex-col" style={{ borderRight: "1px solid #2a3b4d", backgroundColor: "#101922" }}>
                <div className="flex flex-col h-full p-4">
                    <div className="flex items-center gap-2 mb-8 px-2">
                        <div className="w-8 h-8 rounded flex items-center justify-center" style={{ backgroundColor: "#2b8cee" }}>
                            <span className="material-symbols-outlined text-white" style={{ fontSize: "20px" }}>hub</span>
                        </div>
                        <div className="flex flex-col">
                            <h1 className="text-white text-base font-bold leading-none">EdgeGate</h1>
                            <p style={{ color: "#92adc9", fontSize: "12px" }} className="mt-1">CI/CD Platform</p>
                        </div>
                    </div>
                    <nav className="flex flex-col gap-1">
                        <Link href={`/workspace/${workspaceId}`} className="flex items-center gap-3 px-3 py-2 rounded-lg transition-colors" style={{ color: "#92adc9" }}>
                            <span className="material-symbols-outlined">dashboard</span>
                            <span className="text-sm font-medium">Dashboard</span>
                        </Link>
                        <Link href={`/workspace/${workspaceId}/runs`} className="flex items-center gap-3 px-3 py-2 rounded-lg" style={{ backgroundColor: "rgba(43,140,238,0.1)", color: "#2b8cee" }}>
                            <span className="material-symbols-outlined">play_circle</span>
                            <span className="text-sm font-medium">Runs</span>
                        </Link>
                        <Link href={`/workspace/${workspaceId}/pipelines`} className="flex items-center gap-3 px-3 py-2 rounded-lg transition-colors" style={{ color: "#92adc9" }}>
                            <span className="material-symbols-outlined">account_tree</span>
                            <span className="text-sm font-medium">Pipelines</span>
                        </Link>
                        <Link href={`/workspace/${workspaceId}/artifacts`} className="flex items-center gap-3 px-3 py-2 rounded-lg transition-colors" style={{ color: "#92adc9" }}>
                            <span className="material-symbols-outlined">deployed_code</span>
                            <span className="text-sm font-medium">Artifacts</span>
                        </Link>
                        <Link href={`/workspace/${workspaceId}/settings`} className="flex items-center gap-3 px-3 py-2 rounded-lg transition-colors" style={{ color: "#92adc9" }}>
                            <span className="material-symbols-outlined">settings</span>
                            <span className="text-sm font-medium">Settings</span>
                        </Link>
                    </nav>
                </div>
            </div>

            {/* Main Content */}
            <main className="flex-1 flex flex-col h-screen overflow-y-auto relative">
                {/* Top Navigation / Breadcrumbs */}
                <header className="sticky top-0 z-10 px-8 py-4" style={{ backgroundColor: "rgba(16,25,34,0.95)", backdropFilter: "blur(4px)", borderBottom: "1px solid #2a3b4d" }}>
                    <div className="flex flex-col gap-4 max-w-7xl mx-auto">
                        <div className="flex items-center justify-between">
                            {/* Breadcrumbs */}
                            <div className="flex items-center gap-2 text-sm">
                                <Link href={`/workspace/${workspaceId}`} style={{ color: "#92adc9" }} className="hover:text-white transition-colors">Workspace</Link>
                                <span className="material-symbols-outlined text-xs" style={{ color: "#56697d" }}>chevron_right</span>
                                <Link href={`/workspace/${workspaceId}/runs`} style={{ color: "#92adc9" }} className="hover:text-white transition-colors">Runs</Link>
                                <span className="material-symbols-outlined text-xs" style={{ color: "#56697d" }}>chevron_right</span>
                                <span className="text-white font-medium">Run #{run.id.slice(0, 8)}</span>
                            </div>
                            {/* Quick Actions */}
                            <div className="flex gap-3">
                                <button
                                    onClick={downloadReport}
                                    disabled={!run.bundle_artifact_id || downloading}
                                    className="flex items-center gap-2 h-9 px-4 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                                    style={{ border: "1px solid #2a3b4d", color: "#92adc9" }}
                                >
                                    <span className="material-symbols-outlined text-lg">download</span>
                                    <span>{downloading ? "Generating..." : "Download Report"}</span>
                                </button>
                                <button className="flex items-center gap-2 h-9 px-4 rounded-lg text-white text-sm font-bold transition-colors" style={{ backgroundColor: "#2b8cee", boxShadow: "0 4px 14px rgba(43,140,238,0.2)" }}>
                                    <span className="material-symbols-outlined text-lg">replay</span>
                                    <span>Re-run</span>
                                </button>
                            </div>
                        </div>
                        {/* Page Heading & Meta */}
                        <div className="flex items-end justify-between pb-2">
                            <div className="flex flex-col gap-2">
                                <div className="flex items-center gap-4">
                                    <h1 className="text-white text-3xl font-black tracking-tight">Run #{run.id.slice(0, 8)}</h1>
                                    <div className="flex items-center gap-1.5 px-3 py-1 rounded-full" style={{ backgroundColor: statusBg, border: `1px solid ${statusBorder}`, color: statusColor }}>
                                        <span className="material-symbols-outlined text-base">{run.status === "passed" ? "check_circle" : run.status === "failed" ? "error" : "sync"}</span>
                                        <span className="text-sm font-bold capitalize">{run.status}</span>
                                    </div>
                                </div>
                                <p className="text-sm flex items-center gap-2" style={{ color: "#92adc9" }}>
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
                        {/* Card 1: Target Model */}
                        <div className="rounded-xl p-4 flex flex-col gap-1" style={{ backgroundColor: "#182430", border: "1px solid #2a3b4d" }}>
                            <div className="text-xs font-medium uppercase tracking-wider mb-1" style={{ color: "#92adc9" }}>Target Model</div>
                            <div className="flex items-center gap-3">
                                <div className="p-2 rounded" style={{ backgroundColor: "rgba(99,102,241,0.1)", color: "#818cf8" }}>
                                    <span className="material-symbols-outlined">deployed_code</span>
                                </div>
                                <div>
                                    <div className="text-white font-semibold">{run.model_artifact?.original_filename || "Model"}</div>
                                    <div className="text-xs" style={{ color: "#56697d" }}>ONNX</div>
                                </div>
                            </div>
                        </div>
                        {/* Card 2: Device */}
                        <div className="rounded-xl p-4 flex flex-col gap-1" style={{ backgroundColor: "#182430", border: "1px solid #2a3b4d" }}>
                            <div className="text-xs font-medium uppercase tracking-wider mb-1" style={{ color: "#92adc9" }}>Device</div>
                            <div className="flex items-center gap-3">
                                <div className="p-2 rounded" style={{ backgroundColor: "rgba(16,185,129,0.1)", color: "#34d399" }}>
                                    <span className="material-symbols-outlined">smartphone</span>
                                </div>
                                <div>
                                    <div className="text-white font-semibold">{Object.keys(run.device_metrics || {})[0] || "SM8650"}</div>
                                    <div className="text-xs" style={{ color: "#56697d" }}>Snapdragon</div>
                                </div>
                            </div>
                        </div>
                        {/* Card 3: Inference Time */}
                        <div className="rounded-xl p-4 flex flex-col gap-1" style={{ backgroundColor: "#182430", border: "1px solid #2a3b4d" }}>
                            <div className="text-xs font-medium uppercase tracking-wider mb-1" style={{ color: "#92adc9" }}>Inference Time</div>
                            <div className="flex items-center gap-3">
                                <div className="p-2 rounded" style={{ backgroundColor: "rgba(245,158,11,0.1)", color: "#fbbf24" }}>
                                    <span className="material-symbols-outlined">speed</span>
                                </div>
                                <div>
                                    <div className="text-white font-semibold font-mono">{(run.normalized_metrics?.inference_time_ms || 0).toFixed(3)} ms</div>
                                    <div className="text-xs" style={{ color: "#56697d" }}>Avg Latency</div>
                                </div>
                            </div>
                        </div>
                        {/* Card 4: Peak Memory */}
                        <div className="rounded-xl p-4 flex flex-col gap-1" style={{ backgroundColor: "#182430", border: "1px solid #2a3b4d" }}>
                            <div className="text-xs font-medium uppercase tracking-wider mb-1" style={{ color: "#92adc9" }}>Peak Memory</div>
                            <div className="flex items-center gap-3">
                                <div className="p-2 rounded" style={{ backgroundColor: "rgba(236,72,153,0.1)", color: "#f472b6" }}>
                                    <span className="material-symbols-outlined">memory</span>
                                </div>
                                <div>
                                    <div className="text-white font-semibold font-mono">{(run.normalized_metrics?.peak_memory_mb || 0).toFixed(2)} MB</div>
                                    <div className="text-xs" style={{ color: "#56697d" }}>Max Usage</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* Quality Gates Section */}
                        <div className="lg:col-span-1 flex flex-col gap-4">
                            <div className="flex items-center justify-between">
                                <h3 className="text-white font-bold text-lg">Quality Gates</h3>
                                <span className="text-xs px-2 py-1 rounded" style={{ color: "#92adc9", backgroundColor: "#1f2e3d" }}>
                                    {gatesPassed} Pass, {gatesFailed} Fail
                                </span>
                            </div>
                            <div className="rounded-xl p-5 flex flex-col gap-6" style={{ backgroundColor: "#182430", border: "1px solid #2a3b4d" }}>
                                {run.gates_eval?.gates.map((gate, i) => {
                                    const isPass = gate.passed;
                                    const barColor = isPass ? "#10b981" : "#ef4444";
                                    const textColor = isPass ? "#34d399" : "#ef4444";
                                    const actualValue = gate.actual_value ?? 0;
                                    const threshold = gate.threshold;
                                    const percentage = Math.min((actualValue / (threshold * 1.3)) * 100, 100);

                                    return (
                                        <div key={i} className="flex flex-col gap-2">
                                            <div className="flex justify-between items-end">
                                                <span className="text-sm font-medium" style={{ color: "#92adc9" }}>
                                                    {gate.metric.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
                                                </span>
                                                <div className="text-right">
                                                    <span className="font-bold font-mono" style={{ color: textColor }}>
                                                        {actualValue?.toFixed(2) ?? "N/A"}
                                                    </span>
                                                    <span className="text-xs ml-1" style={{ color: "#56697d" }}>
                                                        / {formatOperator(gate.operator)}{threshold}
                                                    </span>
                                                </div>
                                            </div>
                                            <div className="relative h-2 w-full rounded-full overflow-hidden" style={{ backgroundColor: "#1f2e3d" }}>
                                                {/* Threshold marker */}
                                                <div className="absolute top-0 bottom-0 w-0.5 z-10 opacity-30" style={{ left: "76%", backgroundColor: "white" }}></div>
                                                {/* Progress bar */}
                                                <div className="h-full rounded-full" style={{ width: `${percentage}%`, backgroundColor: barColor }}></div>
                                            </div>
                                            {!isPass && (
                                                <p className="text-xs mt-0.5 flex items-center gap-1" style={{ color: "rgba(239,68,68,0.8)" }}>
                                                    <span className="material-symbols-outlined text-xs">warning</span>
                                                    Exceeded threshold by {Math.abs(((actualValue - threshold) / threshold) * 100).toFixed(0)}%
                                                </p>
                                            )}
                                        </div>
                                    );
                                }) || (
                                        <p style={{ color: "#92adc9" }} className="text-sm">No gates configured</p>
                                    )}
                            </div>
                        </div>

                        {/* Performance Summary Section */}
                        <div className="lg:col-span-2 flex flex-col gap-4">
                            <div className="flex items-center justify-between">
                                <h3 className="text-white font-bold text-lg">Performance Summary</h3>
                            </div>
                            <div className="rounded-xl p-5" style={{ backgroundColor: "#182430", border: "1px solid #2a3b4d" }}>
                                {run.normalized_metrics && Object.keys(run.normalized_metrics).length > 0 ? (
                                    <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
                                        {Object.entries(run.normalized_metrics).map(([key, value]) => (
                                            <div key={key} className="flex flex-col">
                                                <span className="text-xs uppercase tracking-wider mb-1" style={{ color: "#92adc9" }}>
                                                    {key.replace(/_/g, " ")}
                                                </span>
                                                <span className="text-2xl font-bold font-mono text-white">
                                                    {typeof value === "number" ? value.toFixed(3) : value}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="text-center py-8" style={{ color: "#92adc9" }}>
                                        <span className="material-symbols-outlined text-4xl mb-2 block">analytics</span>
                                        No metrics available yet
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
