"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface Integration {
    id: string;
    provider: string;
    status: string;
    token_last4: string;
    created_at: string;
    updated_at: string;
}

interface Workspace {
    id: string;
    name: string;
    role: string;
}

export default function SettingsPage() {
    const params = useParams();
    const workspaceId = params.id as string;
    const [workspace, setWorkspace] = useState<Workspace | null>(null);
    const [integration, setIntegration] = useState<Integration | null>(null);
    const [loading, setLoading] = useState(true);
    const [token, setToken] = useState("");
    const [saving, setSaving] = useState(false);
    const [testing, setTesting] = useState(false);
    const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
    const [error, setError] = useState("");

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

            // Fetch integration (may not exist)
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

    const connectToken = async () => {
        const headers = getAuthHeader();
        if (!headers || !token) return;

        setSaving(true);
        setError("");
        setTestResult(null);

        try {
            const res = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/integrations/qaihub`, {
                method: "POST",
                headers: { ...headers, "Content-Type": "application/json" },
                body: JSON.stringify({ token }),
            });

            if (res.ok) {
                const data = await res.json();
                setIntegration(data);
                setToken("");
                setTestResult({ success: true, message: "AI Hub connected successfully!" });
            } else {
                const data = await res.json();
                setError(data.detail || "Failed to connect");
            }
        } catch (err: any) {
            setError(err.message || "Connection failed");
        } finally {
            setSaving(false);
        }
    };

    const rotateToken = async () => {
        const headers = getAuthHeader();
        if (!headers || !token) return;

        setSaving(true);
        setError("");
        setTestResult(null);

        try {
            const res = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/integrations/qaihub/rotate`, {
                method: "PUT",
                headers: { ...headers, "Content-Type": "application/json" },
                body: JSON.stringify({ token }),
            });

            if (res.ok) {
                const data = await res.json();
                setIntegration(data);
                setToken("");
                setTestResult({ success: true, message: "Token rotated successfully!" });
            } else {
                const data = await res.json();
                setError(data.detail || "Failed to rotate token");
            }
        } catch (err: any) {
            setError(err.message || "Rotation failed");
        } finally {
            setSaving(false);
        }
    };

    const toggleIntegration = async (enable: boolean) => {
        const headers = getAuthHeader();
        if (!headers) return;

        setSaving(true);
        setError("");

        try {
            const res = await fetch(
                `${apiUrl}/v1/workspaces/${workspaceId}/integrations/qaihub/${enable ? "enable" : "disable"}`,
                { method: "PUT", headers }
            );

            if (res.ok) {
                const data = await res.json();
                setIntegration(data);
            } else {
                const data = await res.json();
                setError(data.detail || "Failed to update");
            }
        } catch (err: any) {
            setError(err.message || "Update failed");
        } finally {
            setSaving(false);
        }
    };

    const deleteIntegration = async () => {
        const headers = getAuthHeader();
        if (!headers) return;

        if (!confirm("Are you sure you want to delete the AI Hub integration? This cannot be undone.")) {
            return;
        }

        setSaving(true);
        setError("");

        try {
            const res = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/integrations/qaihub`, {
                method: "DELETE",
                headers,
            });

            if (res.ok) {
                setIntegration(null);
            } else {
                const data = await res.json();
                setError(data.detail || "Failed to delete");
            }
        } catch (err: any) {
            setError(err.message || "Delete failed");
        } finally {
            setSaving(false);
        }
    };

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "active":
                return "bg-green-500/20 text-green-400 border-green-500/30";
            case "disabled":
                return "bg-yellow-500/20 text-yellow-400 border-yellow-500/30";
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
                            {workspace?.name || "Workspace"}
                        </Link>
                        <span className="text-slate-600">/</span>
                        <span className="text-white">Settings</span>
                    </div>
                    <Link href={`/workspace/${workspaceId}`}>
                        <Button variant="ghost" className="text-slate-400 hover:text-white">
                            ← Back
                        </Button>
                    </Link>
                </div>
            </header>

            <main className="container mx-auto px-6 py-8 max-w-4xl">
                <h1 className="text-2xl font-bold text-white mb-8">Workspace Settings</h1>

                {/* AI Hub Integration */}
                <Card className="bg-slate-900/50 border-slate-800 mb-8">
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <div>
                                <CardTitle className="text-white flex items-center gap-3">
                                    <div className="h-10 w-10 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
                                        <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                        </svg>
                                    </div>
                                    Qualcomm AI Hub
                                </CardTitle>
                                <CardDescription className="text-slate-400 mt-1">
                                    Connect your AI Hub API token to run tests on real Snapdragon devices
                                </CardDescription>
                            </div>
                            {integration && (
                                <span className={`px-3 py-1 rounded-full text-sm border ${getStatusBadge(integration.status)}`}>
                                    {integration.status}
                                </span>
                            )}
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-6">
                        {integration ? (
                            <>
                                {/* Connected State */}
                                <div className="bg-slate-800/50 rounded-lg p-4">
                                    <div className="flex items-center justify-between">
                                        <div>
                                            <div className="text-sm text-slate-400">API Token</div>
                                            <div className="text-white font-mono">
                                                ••••••••••••{integration.token_last4}
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <div className="text-sm text-slate-400">Last Updated</div>
                                            <div className="text-white">
                                                {new Date(integration.updated_at).toLocaleDateString()}
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Rotate Token */}
                                <div className="space-y-3">
                                    <Label htmlFor="newToken" className="text-slate-300">Rotate Token</Label>
                                    <div className="flex gap-3">
                                        <Input
                                            id="newToken"
                                            type="password"
                                            placeholder="Paste new AI Hub API token"
                                            value={token}
                                            onChange={(e) => setToken(e.target.value)}
                                            className="bg-slate-800/50 border-slate-700 text-white placeholder:text-slate-500"
                                        />
                                        <Button
                                            onClick={rotateToken}
                                            disabled={!token || saving}
                                            className="bg-cyan-500 hover:bg-cyan-600"
                                        >
                                            {saving ? "Saving..." : "Rotate"}
                                        </Button>
                                    </div>
                                </div>

                                {/* Actions */}
                                <div className="flex gap-3 pt-4 border-t border-slate-700">
                                    {integration.status === "active" ? (
                                        <Button
                                            variant="outline"
                                            onClick={() => toggleIntegration(false)}
                                            disabled={saving}
                                            className="border-yellow-500/50 text-yellow-400 hover:bg-yellow-500/10"
                                        >
                                            Disable
                                        </Button>
                                    ) : (
                                        <Button
                                            variant="outline"
                                            onClick={() => toggleIntegration(true)}
                                            disabled={saving}
                                            className="border-green-500/50 text-green-400 hover:bg-green-500/10"
                                        >
                                            Enable
                                        </Button>
                                    )}
                                    <Button
                                        variant="outline"
                                        onClick={deleteIntegration}
                                        disabled={saving}
                                        className="border-red-500/50 text-red-400 hover:bg-red-500/10"
                                    >
                                        Delete Integration
                                    </Button>
                                </div>
                            </>
                        ) : (
                            <>
                                {/* Not Connected State */}
                                <div className="space-y-3">
                                    <Label htmlFor="token" className="text-slate-300">API Token</Label>
                                    <Input
                                        id="token"
                                        type="password"
                                        placeholder="Paste your AI Hub API token"
                                        value={token}
                                        onChange={(e) => setToken(e.target.value)}
                                        className="bg-slate-800/50 border-slate-700 text-white placeholder:text-slate-500"
                                    />
                                    <p className="text-slate-500 text-sm">
                                        Get your token from{" "}
                                        <a
                                            href="https://aihub.qualcomm.com/settings"
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-cyan-400 hover:text-cyan-300"
                                        >
                                            AI Hub Settings
                                        </a>
                                    </p>
                                </div>
                                <Button
                                    onClick={connectToken}
                                    disabled={!token || saving}
                                    className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
                                >
                                    {saving ? "Connecting..." : "Connect AI Hub"}
                                </Button>
                            </>
                        )}

                        {/* Feedback Messages */}
                        {error && (
                            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
                                {error}
                            </div>
                        )}
                        {testResult && (
                            <div className={`p-3 rounded-lg text-sm ${testResult.success
                                    ? "bg-green-500/10 border border-green-500/30 text-green-400"
                                    : "bg-red-500/10 border border-red-500/30 text-red-400"
                                }`}>
                                {testResult.message}
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Workspace Info */}
                <Card className="bg-slate-900/50 border-slate-800">
                    <CardHeader>
                        <CardTitle className="text-white">Workspace Information</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <div className="text-sm text-slate-400">Workspace ID</div>
                                <div className="text-white font-mono text-sm">{workspaceId}</div>
                            </div>
                            <div>
                                <div className="text-sm text-slate-400">Your Role</div>
                                <div className="text-white capitalize">{workspace?.role || "—"}</div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </main>
        </div>
    );
}
