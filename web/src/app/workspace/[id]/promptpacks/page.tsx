"use client";

import Link from "next/link";
import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Sidebar } from "@/components/Sidebar";

interface PromptPack {
    id: string;
    promptpack_id: string;
    version: string;
    name: string;
    description: string;
    case_count: number;
    created_at: string;
}

interface Workspace {
    id: string;
    name: string;
}

export default function PromptPacksPage() {
    const params = useParams();
    const workspaceId = params.id as string;
    const [workspace, setWorkspace] = useState<Workspace | null>(null);
    const [promptpacks, setPromptpacks] = useState<PromptPack[]>([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");
    const fileInputRef = useRef<HTMLInputElement>(null);

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
            const content = await file.text();
            const json = JSON.parse(content);

            const res = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/promptpacks`, {
                method: "POST",
                headers: { ...headers, "Content-Type": "application/json" },
                body: content,
            });

            if (res.ok) {
                setSuccess("PromptPack uploaded successfully!");
                fetchData();
            } else {
                const data = await res.json();
                setError(data.detail || "Failed to upload");
            }
        } catch (err: any) {
            if (err instanceof SyntaxError) {
                setError("Invalid JSON file");
            } else {
                setError(err.message || "Upload failed");
            }
        } finally {
            setUploading(false);
            if (fileInputRef.current) {
                fileInputRef.current.value = "";
            }
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex">
            <Sidebar workspaceId={workspaceId} workspaceName={workspace?.name || "Loading..."} />

            <main className="flex-1 p-8">
                <div className="max-w-6xl mx-auto">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-8">
                        <div>
                            <h1 className="text-2xl font-bold text-white">PromptPacks</h1>
                            <p className="text-slate-400">Test case collections for your AI models</p>
                        </div>
                        <div>
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept=".json"
                                onChange={handleFileUpload}
                                className="hidden"
                                id="promptpack-upload"
                            />
                            <Button
                                onClick={() => fileInputRef.current?.click()}
                                disabled={uploading}
                                className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
                            >
                                {uploading ? "Uploading..." : "+ Upload PromptPack"}
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
                    ) : promptpacks.length === 0 ? (
                        <Card className="bg-slate-900/50 border-slate-800 border-dashed">
                            <CardContent className="py-16 text-center">
                                <div className="h-16 w-16 mx-auto mb-4 rounded-full bg-slate-800 flex items-center justify-center">
                                    <svg className="h-8 w-8 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                    </svg>
                                </div>
                                <h3 className="text-lg font-medium text-white mb-2">No PromptPacks yet</h3>
                                <p className="text-slate-400 mb-6 max-w-md mx-auto">
                                    Upload a JSON file containing your test prompts and expected outputs.
                                </p>
                                <Button
                                    onClick={() => fileInputRef.current?.click()}
                                    className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
                                >
                                    Upload Your First PromptPack
                                </Button>

                                {/* Example Format */}
                                <div className="mt-8 text-left max-w-lg mx-auto">
                                    <p className="text-sm text-slate-400 mb-2">Example PromptPack format:</p>
                                    <pre className="p-4 bg-slate-800/50 rounded-lg text-xs text-slate-300 overflow-auto">
                                        {`{
  "promptpack_id": "basic-qa",
  "version": "1.0.0",
  "name": "Basic QA Tests",
  "description": "Simple Q&A test cases",
  "cases": [
    {
      "case_id": "greeting",
      "name": "Greeting Test",
      "prompt": "Hello, who are you?",
      "expected": {
        "type": "regex",
        "pattern": "assistant|AI|help"
      }
    }
  ]
}`}
                                    </pre>
                                </div>
                            </CardContent>
                        </Card>
                    ) : (
                        <div className="space-y-4">
                            {promptpacks.map((pp) => (
                                <Card key={`${pp.promptpack_id}-${pp.version}`} className="bg-slate-900/50 border-slate-800">
                                    <CardContent className="py-4 flex items-center justify-between">
                                        <div className="flex items-center gap-4">
                                            <div className="h-12 w-12 rounded-lg bg-purple-500/20 flex items-center justify-center">
                                                <svg className="h-6 w-6 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                                </svg>
                                            </div>
                                            <div>
                                                <div className="text-white font-medium">{pp.name}</div>
                                                <div className="text-sm text-slate-400">
                                                    {pp.promptpack_id} • v{pp.version}
                                                </div>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-6">
                                            <div className="text-right">
                                                <div className="text-white font-medium">{pp.case_count}</div>
                                                <div className="text-sm text-slate-400">Cases</div>
                                            </div>
                                            <div className="text-right">
                                                <div className="text-white">{new Date(pp.created_at).toLocaleDateString()}</div>
                                                <div className="text-sm text-slate-400">Created</div>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
