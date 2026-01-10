"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sidebar } from "@/components/Sidebar";

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
    const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
    const [error, setError] = useState("");
    // CI Secret state
    const [ciSecretStatus, setCiSecretStatus] = useState<{ has_secret: boolean; created_at?: string } | null>(null);
    const [generatedSecret, setGeneratedSecret] = useState<string | null>(null);
    const [generatingSecret, setGeneratingSecret] = useState(false);

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
            const wsRes = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}`, { headers });
            if (wsRes.ok) {
                const wsData = await wsRes.json();
                setWorkspace(wsData);
            }

            // Fetch AI Hub integration
            try {
                const intRes = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/integrations/qaihub`, { headers });
                if (intRes.ok) {
                    const intData = await intRes.json();
                    setIntegration(intData);
                }
            } catch (e) {
                // Integration may not exist
            }

            // Fetch CI secret status
            try {
                const ciRes = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/integrations/ci-secret`, { headers });
                if (ciRes.ok) {
                    const ciData = await ciRes.json();
                    setCiSecretStatus(ciData);
                }
            } catch (e) {
                // CI secret may not exist
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

    // CI Secret management
    const generateCiSecret = async () => {
        const headers = getAuthHeader();
        if (!headers) return;

        setGeneratingSecret(true);
        setGeneratedSecret(null);
        setError("");

        try {
            const res = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/integrations/ci-secret`, {
                method: "POST",
                headers,
            });

            if (res.ok) {
                const data = await res.json();
                setGeneratedSecret(data.secret);
                setCiSecretStatus({ has_secret: true, created_at: new Date().toISOString() });
            } else {
                const data = await res.json();
                setError(data.detail || "Failed to generate CI secret");
            }
        } catch (err: any) {
            setError(err.message || "Failed to generate CI secret");
        } finally {
            setGeneratingSecret(false);
        }
    };

    const revokeCiSecret = async () => {
        const headers = getAuthHeader();
        if (!headers) return;

        if (!confirm("Are you sure? Any CI integrations using this secret will stop working.")) return;

        try {
            const res = await fetch(`${apiUrl}/v1/workspaces/${workspaceId}/integrations/ci-secret`, {
                method: "DELETE",
                headers,
            });

            if (res.ok || res.status === 204) {
                setCiSecretStatus({ has_secret: false });
                setGeneratedSecret(null);
            } else {
                const data = await res.json();
                setError(data.detail || "Failed to revoke CI secret");
            }
        } catch (err: any) {
            setError(err.message || "Failed to revoke CI secret");
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
                        <span className="font-semibold text-foreground">Settings</span>
                    </div>
                </header>

                <div className="flex-1 overflow-y-auto p-6 max-w-4xl w-full mx-auto space-y-6">
                    {/* Page Header */}
                    <div>
                        <h1 className="text-3xl font-black tracking-tight text-foreground">Workspace Settings</h1>
                        <p className="text-muted-foreground mt-1 text-sm">Configure integrations and workspace preferences.</p>
                    </div>

                    {/* AI Hub Integration */}
                    <div className="bg-card border border-border rounded-xl overflow-hidden">
                        <div className="p-6 border-b border-border flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-purple-500/20">
                                    <span className="material-symbols-outlined text-white text-2xl">developer_board</span>
                                </div>
                                <div>
                                    <h2 className="text-lg font-bold text-foreground">Qualcomm AI Hub</h2>
                                    <p className="text-muted-foreground text-sm">Connect to run tests on real Snapdragon devices</p>
                                </div>
                            </div>
                            {integration && (
                                <span className={`px-3 py-1.5 rounded-lg text-sm font-bold ${integration.status === "active"
                                    ? "bg-green-500/10 text-green-400 border border-green-500/20"
                                    : "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20"
                                    }`}>
                                    <span className="material-symbols-outlined text-[14px] mr-1 align-text-bottom">
                                        {integration.status === "active" ? "check_circle" : "pause_circle"}
                                    </span>
                                    {integration.status === "active" ? "Active" : "Disabled"}
                                </span>
                            )}
                        </div>

                        <div className="p-6 space-y-6">
                            {integration ? (
                                <>
                                    {/* Connected State */}
                                    <div className="bg-accent rounded-lg p-4 flex items-center justify-between">
                                        <div>
                                            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">API Token</div>
                                            <div className="text-foreground font-mono text-sm">
                                                ••••••••••••{integration.token_last4}
                                            </div>
                                        </div>
                                        <div className="text-right">
                                            <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Last Updated</div>
                                            <div className="text-foreground text-sm">
                                                {new Date(integration.updated_at).toLocaleDateString()}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Rotate Token */}
                                    <div className="space-y-3">
                                        <Label htmlFor="newToken" className="text-muted-foreground text-sm font-medium">Rotate Token</Label>
                                        <div className="flex gap-3">
                                            <Input
                                                id="newToken"
                                                type="password"
                                                placeholder="Paste new AI Hub API token"
                                                value={token}
                                                onChange={(e) => setToken(e.target.value)}
                                                className="bg-background border-border text-foreground placeholder:text-muted-foreground"
                                            />
                                            <Button
                                                onClick={rotateToken}
                                                disabled={!token || saving}
                                                className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold shrink-0"
                                            >
                                                <span className="material-symbols-outlined text-[18px] mr-1.5">refresh</span>
                                                {saving ? "Saving..." : "Rotate"}
                                            </Button>
                                        </div>
                                    </div>

                                    {/* Actions */}
                                    <div className="flex gap-3 pt-4 border-t border-border">
                                        {integration.status === "active" ? (
                                            <Button
                                                variant="outline"
                                                onClick={() => toggleIntegration(false)}
                                                disabled={saving}
                                                className="border-yellow-500/50 text-yellow-400 hover:bg-yellow-500/10"
                                            >
                                                <span className="material-symbols-outlined text-[18px] mr-1.5">pause</span>
                                                Disable
                                            </Button>
                                        ) : (
                                            <Button
                                                variant="outline"
                                                onClick={() => toggleIntegration(true)}
                                                disabled={saving}
                                                className="border-green-500/50 text-green-400 hover:bg-green-500/10"
                                            >
                                                <span className="material-symbols-outlined text-[18px] mr-1.5">play_arrow</span>
                                                Enable
                                            </Button>
                                        )}
                                        <Button
                                            variant="outline"
                                            onClick={deleteIntegration}
                                            disabled={saving}
                                            className="border-destructive/50 text-destructive hover:bg-destructive/10"
                                        >
                                            <span className="material-symbols-outlined text-[18px] mr-1.5">delete</span>
                                            Delete Integration
                                        </Button>
                                    </div>
                                </>
                            ) : (
                                <>
                                    {/* Not Connected State */}
                                    <div className="space-y-3">
                                        <Label htmlFor="token" className="text-muted-foreground text-sm font-medium">API Token</Label>
                                        <Input
                                            id="token"
                                            type="password"
                                            placeholder="Paste your AI Hub API token"
                                            value={token}
                                            onChange={(e) => setToken(e.target.value)}
                                            className="bg-background border-border text-foreground placeholder:text-muted-foreground"
                                        />
                                        <p className="text-muted-foreground text-xs flex items-center gap-1">
                                            <span className="material-symbols-outlined text-[14px]">info</span>
                                            Get your token from{" "}
                                            <a
                                                href="https://aihub.qualcomm.com/settings"
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-primary hover:underline"
                                            >
                                                AI Hub Settings
                                            </a>
                                        </p>
                                    </div>
                                    <Button
                                        onClick={connectToken}
                                        disabled={!token || saving}
                                        className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold shadow-lg shadow-primary/20"
                                    >
                                        <span className="material-symbols-outlined text-[18px] mr-1.5">link</span>
                                        {saving ? "Connecting..." : "Connect AI Hub"}
                                    </Button>
                                </>
                            )}

                            {/* Feedback Messages */}
                            {error && (
                                <div className="p-3 bg-destructive/10 border border-destructive/30 rounded-lg text-destructive text-sm flex items-center gap-2">
                                    <span className="material-symbols-outlined text-lg">error</span>
                                    {error}
                                </div>
                            )}
                            {testResult && (
                                <div className={`p-3 rounded-lg text-sm flex items-center gap-2 ${testResult.success
                                    ? "bg-green-500/10 border border-green-500/30 text-green-400"
                                    : "bg-destructive/10 border border-destructive/30 text-destructive"
                                    }`}>
                                    <span className="material-symbols-outlined text-lg">
                                        {testResult.success ? "check_circle" : "error"}
                                    </span>
                                    {testResult.message}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Workspace Info */}
                    <div className="bg-card border border-border rounded-xl overflow-hidden">
                        <div className="p-6 border-b border-border">
                            <h2 className="text-lg font-bold text-foreground">Workspace Information</h2>
                        </div>
                        <div className="p-6">
                            <div className="grid grid-cols-2 gap-6">
                                <div>
                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Workspace ID</div>
                                    <div className="text-foreground font-mono text-sm">{workspaceId}</div>
                                </div>
                                <div>
                                    <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Your Role</div>
                                    <div className="text-foreground capitalize">{workspace?.role || "—"}</div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* CI Secret */}
                    <div className="bg-card border border-border rounded-xl overflow-hidden">
                        <div className="p-6 border-b border-border">
                            <h2 className="text-lg font-bold text-foreground">CI/CD Integration</h2>
                            <p className="text-sm text-muted-foreground mt-1">
                                Generate a secret to authenticate GitHub Actions with EdgeGate
                            </p>
                        </div>
                        <div className="p-6 space-y-4">
                            {generatedSecret && (
                                <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
                                    <div className="flex items-center gap-2 text-green-400 mb-2">
                                        <span className="material-symbols-outlined">key</span>
                                        <span className="font-medium">Your CI Secret (copy now - shown only once!)</span>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <code className="flex-1 p-3 bg-black/50 rounded font-mono text-sm text-green-300 break-all">
                                            {generatedSecret}
                                        </code>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => {
                                                navigator.clipboard.writeText(generatedSecret);
                                                alert("Copied to clipboard!");
                                            }}
                                            className="border-green-500/50 text-green-400"
                                        >
                                            Copy
                                        </Button>
                                    </div>
                                </div>
                            )}

                            {ciSecretStatus?.has_secret && !generatedSecret && (
                                <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
                                    <div>
                                        <div className="flex items-center gap-2 text-foreground">
                                            <span className="material-symbols-outlined text-primary">verified</span>
                                            <span>CI Secret configured</span>
                                        </div>
                                        {ciSecretStatus.created_at && (
                                            <div className="text-xs text-muted-foreground mt-1">
                                                Created: {new Date(ciSecretStatus.created_at).toLocaleDateString()}
                                            </div>
                                        )}
                                    </div>
                                    <div className="flex gap-2">
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={generateCiSecret}
                                            disabled={generatingSecret}
                                        >
                                            Regenerate
                                        </Button>
                                        <Button
                                            size="sm"
                                            variant="destructive"
                                            onClick={revokeCiSecret}
                                        >
                                            Revoke
                                        </Button>
                                    </div>
                                </div>
                            )}

                            {!ciSecretStatus?.has_secret && !generatedSecret && (
                                <div className="text-center py-8">
                                    <p className="text-muted-foreground mb-4">
                                        No CI secret configured. Generate one to use EdgeGate from GitHub Actions.
                                    </p>
                                    <Button
                                        onClick={generateCiSecret}
                                        disabled={generatingSecret}
                                        className="bg-gradient-to-r from-cyan-500 to-blue-500"
                                    >
                                        {generatingSecret ? "Generating..." : "Generate CI Secret"}
                                    </Button>
                                </div>
                            )}

                            <div className="text-xs text-muted-foreground border-t border-border pt-4 mt-4">
                                <p className="font-medium mb-2">Usage in GitHub Actions:</p>
                                <pre className="p-3 bg-muted/50 rounded text-xs overflow-x-auto">
                                    {`# Add to repository secrets:
# EDGEGATE_WORKSPACE_ID: ${workspaceId}
# EDGEGATE_API_SECRET: <your-secret>

- name: Trigger EdgeGate
  env:
    WORKSPACE_ID: \${{ secrets.EDGEGATE_WORKSPACE_ID }}
    API_SECRET: \${{ secrets.EDGEGATE_API_SECRET }}`}
                                </pre>
                            </div>
                        </div>
                    </div>
                </div>
            </main>
        </div>
    );
}
