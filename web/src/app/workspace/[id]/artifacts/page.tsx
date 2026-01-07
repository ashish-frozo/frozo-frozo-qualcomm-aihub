"use client";

import Link from "next/link";
import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Sidebar } from "@/components/Sidebar";

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
    const fileInputRef = useRef<HTMLInputElement>(null);

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    // Helper to safely extract error message from API response
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

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex">
            <Sidebar workspaceId={workspaceId} workspaceName={workspace?.name || "Loading..."} />

            <main className="flex-1 p-8">
                <div className="max-w-6xl mx-auto">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-8">
                        <div>
                            <h1 className="text-2xl font-bold text-white">Model Artifacts</h1>
                            <p className="text-slate-400">Compiled models for testing on devices</p>
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
                                className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
                            >
                                {uploading ? "Uploading..." : "+ Upload Model"}
                            </Button>
                        </div>
                    </div>

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

                    {/* Content */}
                    {loading ? (
                        <div className="text-slate-400 text-center py-12">Loading...</div>
                    ) : artifacts.length === 0 ? (
                        <Card className="bg-slate-900/50 border-slate-800 border-dashed">
                            <CardContent className="py-16 text-center">
                                <div className="h-16 w-16 mx-auto mb-4 rounded-full bg-slate-800 flex items-center justify-center">
                                    <svg className="h-8 w-8 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                    </svg>
                                </div>
                                <h3 className="text-lg font-medium text-white mb-2">No model artifacts yet</h3>
                                <p className="text-slate-400 mb-6 max-w-md mx-auto">
                                    Upload compiled models (.so, .onnx, .bin) to test on Snapdragon devices.
                                </p>
                                <Button
                                    onClick={() => fileInputRef.current?.click()}
                                    className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
                                >
                                    Upload Your First Model
                                </Button>
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="space-y-4">
                            {artifacts.map((artifact) => (
                                <Card key={artifact.id} className="bg-slate-900/50 border-slate-800">
                                    <CardContent className="py-4 flex items-center justify-between">
                                        <div className="flex items-center gap-4">
                                            <div className="h-12 w-12 rounded-lg bg-orange-500/20 flex items-center justify-center">
                                                <svg className="h-6 w-6 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                                </svg>
                                            </div>
                                            <div>
                                                <div className="text-white font-medium">
                                                    {artifact.original_filename || `Model ${artifact.id.slice(0, 8)}`}
                                                </div>
                                                <div className="text-sm text-slate-400 font-mono">
                                                    {artifact.sha256.slice(0, 16)}...
                                                </div>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-6">
                                            <div className="text-right">
                                                <div className="text-white font-medium">{formatSize(artifact.size_bytes)}</div>
                                                <div className="text-sm text-slate-400">Size</div>
                                            </div>
                                            <div className="text-right">
                                                <div className="text-white">{new Date(artifact.created_at).toLocaleDateString()}</div>
                                                <div className="text-sm text-slate-400">Uploaded</div>
                                            </div>
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={() => copyToClipboard(artifact.id)}
                                                className="border-slate-700 text-slate-300 hover:bg-slate-800"
                                            >
                                                Copy ID
                                            </Button>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}

                    {/* Usage Info */}
                    <div className="mt-8 p-4 bg-slate-900/50 border border-slate-800 rounded-lg">
                        <h3 className="text-white font-medium mb-2">How to use model artifacts</h3>
                        <ol className="text-sm text-slate-400 space-y-1 list-decimal list-inside">
                            <li>Upload your compiled model (.so, .onnx, .bin)</li>
                            <li>Copy the artifact ID</li>
                            <li>Use it when triggering a run via CI or API</li>
                        </ol>
                    </div>
                </div>
            </main>
        </div>
    );
}
