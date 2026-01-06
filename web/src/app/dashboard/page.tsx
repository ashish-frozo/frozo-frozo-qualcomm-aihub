"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface Workspace {
    id: string;
    name: string;
    created_at: string;
}

export default function DashboardPage() {
    const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
    const [loading, setLoading] = useState(true);
    const [showCreate, setShowCreate] = useState(false);
    const [newName, setNewName] = useState("");

    useEffect(() => {
        fetchWorkspaces();
    }, []);

    const fetchWorkspaces = async () => {
        const token = localStorage.getItem("token");
        if (!token) {
            window.location.href = "/login";
            return;
        }

        try {
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/v1/workspaces`, {
                headers: { Authorization: `Bearer ${token}` },
            });

            if (res.ok) {
                const data = await res.json();
                setWorkspaces(data);
            }
        } catch (err) {
            console.error("Failed to fetch workspaces", err);
        } finally {
            setLoading(false);
        }
    };

    const createWorkspace = async () => {
        const token = localStorage.getItem("token");
        if (!token || !newName) return;

        try {
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/v1/workspaces`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify({ name: newName }),
            });

            if (res.ok) {
                setNewName("");
                setShowCreate(false);
                fetchWorkspaces();
            }
        } catch (err) {
            console.error("Failed to create workspace", err);
        }
    };

    const logout = () => {
        localStorage.removeItem("token");
        window.location.href = "/login";
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
            {/* Header */}
            <header className="border-b border-slate-800">
                <div className="container mx-auto px-6 py-4 flex items-center justify-between">
                    <Link href="/dashboard" className="flex items-center gap-2">
                        <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-500" />
                        <span className="text-xl font-bold text-white">EdgeGate</span>
                    </Link>
                    <Button variant="ghost" onClick={logout} className="text-slate-400 hover:text-white">
                        Logout
                    </Button>
                </div>
            </header>

            <main className="container mx-auto px-6 py-8">
                {/* Stats */}
                <div className="grid md:grid-cols-3 gap-6 mb-8">
                    <Card className="bg-slate-900/50 border-slate-800">
                        <CardHeader className="pb-2">
                            <CardDescription className="text-slate-400">Workspaces</CardDescription>
                            <CardTitle className="text-3xl text-white">{workspaces.length}</CardTitle>
                        </CardHeader>
                    </Card>
                    <Card className="bg-slate-900/50 border-slate-800">
                        <CardHeader className="pb-2">
                            <CardDescription className="text-slate-400">Total Runs</CardDescription>
                            <CardTitle className="text-3xl text-white">—</CardTitle>
                        </CardHeader>
                    </Card>
                    <Card className="bg-slate-900/50 border-slate-800">
                        <CardHeader className="pb-2">
                            <CardDescription className="text-slate-400">Pass Rate</CardDescription>
                            <CardTitle className="text-3xl text-green-400">—</CardTitle>
                        </CardHeader>
                    </Card>
                </div>

                {/* Workspaces */}
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-xl font-bold text-white">Your Workspaces</h2>
                    <Button
                        onClick={() => setShowCreate(true)}
                        className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
                    >
                        + New Workspace
                    </Button>
                </div>

                {showCreate && (
                    <Card className="bg-slate-900/50 border-slate-800 mb-6">
                        <CardContent className="pt-6">
                            <div className="flex gap-4">
                                <input
                                    type="text"
                                    placeholder="Workspace name"
                                    value={newName}
                                    onChange={(e) => setNewName(e.target.value)}
                                    className="flex-1 px-4 py-2 bg-slate-800/50 border border-slate-700 rounded-lg text-white placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                                />
                                <Button onClick={createWorkspace} className="bg-cyan-500 hover:bg-cyan-600">
                                    Create
                                </Button>
                                <Button variant="ghost" onClick={() => setShowCreate(false)} className="text-slate-400">
                                    Cancel
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                )}

                {loading ? (
                    <div className="text-slate-400 text-center py-12">Loading...</div>
                ) : workspaces.length === 0 ? (
                    <Card className="bg-slate-900/50 border-slate-800 border-dashed">
                        <CardContent className="py-12 text-center">
                            <p className="text-slate-400 mb-4">No workspaces yet. Create one to get started.</p>
                            <Button
                                onClick={() => setShowCreate(true)}
                                variant="outline"
                                className="border-slate-700 text-white hover:bg-slate-800"
                            >
                                Create Workspace
                            </Button>
                        </CardContent>
                    </Card>
                ) : (
                    <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {workspaces.map((ws) => (
                            <Link key={ws.id} href={`/workspace/${ws.id}`}>
                                <Card className="bg-slate-900/50 border-slate-800 hover:border-cyan-500/50 transition-colors cursor-pointer">
                                    <CardHeader>
                                        <CardTitle className="text-white">{ws.name}</CardTitle>
                                        <CardDescription className="text-slate-400">
                                            Created {new Date(ws.created_at).toLocaleDateString()}
                                        </CardDescription>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="flex gap-4 text-sm text-slate-400">
                                            <span>— Pipelines</span>
                                            <span>— Runs</span>
                                        </div>
                                    </CardContent>
                                </Card>
                            </Link>
                        ))}
                    </div>
                )}
            </main>
        </div>
    );
}
