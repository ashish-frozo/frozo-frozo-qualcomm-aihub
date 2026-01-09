"use client";

import { cn } from "@/lib/utils";

type StatusVariant = "running" | "passed" | "failed" | "queued" | "warning" | "error";

interface StatusBadgeProps {
    status: StatusVariant;
    className?: string;
}

const statusConfig: Record<StatusVariant, { icon: string; label: string; classes: string }> = {
    running: {
        icon: "sync",
        label: "Running",
        classes: "bg-blue-100 dark:bg-primary/20 text-primary dark:text-blue-300 border-blue-200 dark:border-primary/20",
    },
    passed: {
        icon: "check_circle",
        label: "Passed",
        classes: "bg-green-100 dark:bg-green-500/10 text-green-700 dark:text-green-400 border-green-200 dark:border-green-500/20",
    },
    failed: {
        icon: "cancel",
        label: "Failed",
        classes: "bg-red-100 dark:bg-red-500/10 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/20",
    },
    error: {
        icon: "error",
        label: "Error",
        classes: "bg-red-100 dark:bg-red-500/10 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/20",
    },
    queued: {
        icon: "schedule",
        label: "Queued",
        classes: "bg-gray-100 dark:bg-gray-700/50 text-slate-600 dark:text-slate-300 border-gray-200 dark:border-gray-600",
    },
    warning: {
        icon: "warning",
        label: "Warning",
        classes: "bg-yellow-100 dark:bg-yellow-500/10 text-yellow-700 dark:text-yellow-400 border-yellow-200 dark:border-yellow-500/20",
    },
};

export function StatusBadge({ status, className }: StatusBadgeProps) {
    const config = statusConfig[status] || statusConfig.queued;
    const isAnimated = status === "running";

    return (
        <div
            className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 border text-xs font-bold",
                config.classes,
                className
            )}
        >
            <span
                className={cn(
                    "material-symbols-outlined text-[16px]",
                    isAnimated && "animate-spin"
                )}
                style={{ fontVariationSettings: "'FILL' 1, 'wght' 400" }}
            >
                {config.icon}
            </span>
            <span>{config.label}</span>
        </div>
    );
}

export function getStatusFromRunStatus(runStatus: string): StatusVariant {
    const statusMap: Record<string, StatusVariant> = {
        queued: "queued",
        preparing: "running",
        submitting: "running",
        running: "running",
        collecting: "running",
        evaluating: "running",
        reporting: "running",
        passed: "passed",
        failed: "failed",
        error: "error",
        completed: "passed",
    };
    return statusMap[runStatus.toLowerCase()] || "queued";
}
