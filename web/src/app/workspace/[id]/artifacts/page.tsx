"use client";

import Link from "next/link";
import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Sidebar } from "@/components/Sidebar";
import { StatCard } from "@/components/ui/StatCard";

interface Artifact {
    id: string;
    kind: string;
    sha256: string;
    size_bytes: number;
    original_filename: string | null;
    storage_url: string;
    created_at: string;
    expires_at: string | null;
}

interface Workspace {
    id: string;
    name: string;
}

export default function ArtifactsPage() {
    const params = useParams();
    const workspaceId = params.id as string;
    const [workspace, setWorkspace] = useState<Workspace | null>(null);
    const [artifacts, setArtifacts] = useState<Artifact[]>([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");
    const [searchQuery, setSearchQuery] = useState("");
    const fileInputRef = useRef<HTMLInputElement>(null);

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    const getErrorMessage = (data: any): string => {
        if (typeof data.detail === 'string') return data.detail;
        if (Array.isArray(data.detail) && data.detail.length > 0) {
            const firstError = data.detail[0];
            return firstError.msg || JSON.stringify(firstError);
        }
        if (data.detail?.message) return data.detail.message;
        if (typeof data.detail === 'object') return JSON.stringify(data.detail);
        return "An error occurred";
    };

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
            const [wsRes, artifactsRes] = await Promise.all([
                fetch(`${apiUrl}/v1/workspaces/${workspaceId}`, { headers }),
                fetch(`${apiUrl}/v1/workspaces/${workspaceId}/artifacts?kind=model`, { headers }),
            ]);

            if (wsRes.ok) {
                setWorkspace(await wsRes.json());
            }
            if (artifactsRes.ok) {
                setArtifacts(await artifactsRes.json());
            }
        } catch (err) {
            console.error("Failed to fetch data", err);
        } finally {
            setLoading(false);
        }
    };

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        const headers = getAuthHeader();
        if (!headers) return;

        setUploading(true);
        setError("");
        setSuccess("");

        try {
            const formData = new FormData();
            formData.append("file", file);
            formData.append("kind", "model");

            const res = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/artifacts`, {
                method: "POST",
                headers: { Authorization: headers.Authorization },
                body: formData,
            });

            if (res.ok) {
                setSuccess(`Model artifact "${file.name}" uploaded successfully!`);
                fetchData();
            } else {
                const data = await res.json();
                setError(getErrorMessage(data));
            }
        } catch (err: any) {
            setError(err.message || "Upload failed");
        } finally {
            setUploading(false);
            if (fileInputRef.current) {
                fileInputRef.current.value = "";
            }
        }
    };

    const formatSize = (bytes: number): string => {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
        return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
    };

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text);
        setSuccess("Copied to clipboard!");
        setTimeout(() => setSuccess(""), 2000);
    };

    const getFileExtension = (filename: string | null): string => {
        if (!filename) return "model";
        const ext = filename.split('.').pop()?.toLowerCase();
        return ext || "model";
    };

    const getFileIcon = (ext: string): string => {
        const iconMap: Record<string, string> = {
            onnx: "deployed_code",
            so: "memory",
            bin: "data_object",
            pt: "data_object",
            aimet: "deployed_code",
        };
        return iconMap[ext] || "deployed_code";
    };

    const filteredArtifacts = artifacts.filter(a => {
        if (!searchQuery) return true;
        const query = searchQuery.toLowerCase();
        return (
            a.original_filename?.toLowerCase().includes(query) ||
            a.id.toLowerCase().includes(query)
        );
    });

    const totalSize = artifacts.reduce((sum, a) => sum + a.size_bytes, 0);

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
                        <span className="font-semibold text-foreground">Model Artifacts</span>
                    </div>
                    <div>
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".so,.onnx,.bin,.pt,.aimet"
                            onChange={handleFileUpload}
                            className="hidden"
                            id="artifact-upload"
                        />
                        <Button
                            onClick={() => fileInputRef.current?.click()}
                            disabled={uploading}
                            className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold shadow-lg shadow-primary/20"
                        >
                            <span className="material-symbols-outlined text-[18px] mr-1.5">upload</span>
                            {uploading ? "Uploading..." : "Upload Model"}
                        </Button>
                    </div>
                </header>

                <div className="flex-1 overflow-y-auto p-6 max-w-7xl w-full mx-auto space-y-6">
                    {/* Feedback */}
                    {error && (
                        <div className="p-4 bg-destructive/10 border border-destructive/30 rounded-lg text-destructive flex items-center gap-2">
                            <span className="material-symbols-outlined">error</span>
                            {error}
                        </div>
                    )}
                    {success && (
                        <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 flex items-center gap-2">
                            <span className="material-symbols-outlined">check_circle</span>
                            {success}
                        </div>
                    )}

                    {/* Page Header */}
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                        <div>
                            <h1 className="text-3xl font-black tracking-tight text-foreground">Model Artifacts Repository</h1>
                            <p className="text-muted-foreground mt-1 text-sm">Compiled models for testing on Snapdragon devices.</p>
                        </div>
                    </div>

                    {/* Stats Grid */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        <StatCard title="Total Models" value={artifacts.length.toString()} icon="deployed_code" />
                        <StatCard title="Total Storage" value={formatSize(totalSize)} icon="storage" />
                        <StatCard title="ONNX Models" value={artifacts.filter(a => a.original_filename?.endsWith('.onnx')).length.toString()} icon="data_object" />
                        <StatCard title="Compiled (.so)" value={artifacts.filter(a => a.original_filename?.endsWith('.so')).length.toString()} icon="memory" />
                    </div>

                    {/* Search */}
                    <div className="relative w-full max-w-md">
                        <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground text-[20px]">search</span>
                        <input
                            className="w-full rounded-lg border border-border bg-card text-foreground focus:outline-0 focus:ring-2 focus:ring-primary focus:border-primary h-11 pl-11 pr-4 text-sm placeholder:text-muted-foreground transition-all"
                            placeholder="Search models..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                        />
                    </div>

                    {/* Content */}
                    {loading ? (
                        <div className="flex items-center justify-center py-12 text-muted-foreground">
                            <span className="material-symbols-outlined animate-spin mr-2">sync</span>
                            Loading...
                        </div>
                    ) : filteredArtifacts.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-16 rounded-xl border border-border border-dashed bg-card">
                            <span className="material-symbols-outlined text-4xl text-muted-foreground mb-4">deployed_code</span>
                            <h3 className="text-lg font-medium text-foreground mb-2">No model artifacts yet</h3>
                            <p className="text-muted-foreground mb-6 max-w-md text-center">
                                Upload compiled models (.so, .onnx, .bin) to test on Snapdragon devices.
                            </p>
                            <Button
                                onClick={() => fileInputRef.current?.click()}
                                className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold"
                            >
                                Upload Your First Model
                            </Button>
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {filteredArtifacts.map((artifact) => {
                                const ext = getFileExtension(artifact.original_filename);
                                const icon = getFileIcon(ext);
                                return (
                                    <div
                                        key={artifact.id}
                                        className="group bg-card border border-border rounded-xl p-5 hover:border-primary/50 transition-all cursor-pointer"
                                        onClick={() => copyToClipboard(artifact.id)}
                                    >
                                        <div className="flex items-start justify-between mb-4">
                                            <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center">
                                                <span className="material-symbols-outlined text-primary text-2xl">{icon}</span>
                                            </div>
                                            <span className="inline-flex items-center px-2.5 py-0.5 rounded text-xs font-bold bg-accent text-muted-foreground border border-border uppercase">
                                                {ext}
                                            </span>
                                        </div>
                                        <h3 className="text-foreground font-semibold truncate mb-1 group-hover:text-primary transition-colors">
                                            {artifact.original_filename || `Model ${artifact.id.slice(0, 8)}`}
                                        </h3>
                                        <p className="text-xs text-muted-foreground font-mono mb-3 truncate">
                                            {artifact.sha256.slice(0, 24)}...
                                        </p>
                                        <div className="flex items-center justify-between text-xs text-muted-foreground">
                                            <span className="flex items-center gap-1">
                                                <span className="material-symbols-outlined text-[16px]">folder</span>
                                                {formatSize(artifact.size_bytes)}
                                            </span>
                                            <span className="flex items-center gap-1">
                                                <span className="material-symbols-outlined text-[16px]">schedule</span>
                                                {new Date(artifact.created_at).toLocaleDateString()}
                                            </span>
                                        </div>
                                        <div className="mt-4 pt-4 border-t border-border flex items-center justify-between">
                                            <button
                                                className="text-primary hover:text-primary/80 text-xs font-semibold inline-flex items-center gap-1 transition-colors"
                                                onClick={(e) => { e.stopPropagation(); copyToClipboard(artifact.id); }}
                                            >
                                                <span className="material-symbols-outlined text-[16px]">content_copy</span>
                                                Copy ID
                                            </button>
                                            <span className="text-xs text-muted-foreground font-mono">
                                                #{artifact.id.slice(0, 8)}
                                            </span>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {/* Usage Info */}
                    <div className="p-5 bg-card border border-border rounded-xl">
                        <div className="flex items-center gap-2 mb-3">
                            <span className="material-symbols-outlined text-primary">info</span>
                            <h3 className="text-foreground font-semibold">How to use model artifacts</h3>
                        </div>
                        <ol className="text-sm text-muted-foreground space-y-2 list-decimal list-inside">
                            <li>Upload your compiled model (.so, .onnx, .bin)</li>
                            <li>Copy the artifact ID by clicking on the card</li>
                            <li>Use it when triggering a run via CI or API</li>
                        </ol>
                    </div>
                </div>
            </main>
        </div>
    );
}
