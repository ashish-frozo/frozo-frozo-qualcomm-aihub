"use client";

import { cn } from "@/lib/utils";

interface StatCardProps {
    title: string;
    value: string | number;
    icon: string;
    trend?: {
        value: string;
        direction: "up" | "down" | "neutral";
        label?: string;
    };
    className?: string;
}

export function StatCard({ title, value, icon, trend, className }: StatCardProps) {
    const trendColor = trend?.direction === "up"
        ? "text-green-500"
        : trend?.direction === "down"
            ? "text-red-400"
            : "text-slate-500 dark:text-slate-400";

    const trendIcon = trend?.direction === "up"
        ? "trending_up"
        : trend?.direction === "down"
            ? "trending_down"
            : null;

    return (
        <div
            className={cn(
                "bg-card border border-border rounded-lg p-5 flex flex-col justify-between h-32 hover:border-white/20 transition-colors",
                className
            )}
        >
            <div className="flex justify-between items-start">
                <span className="text-muted-foreground text-xs font-medium uppercase tracking-wider">
                    {title}
                </span>
                <span className="material-symbols-outlined text-muted-foreground text-[20px]">
                    {icon}
                </span>
            </div>
            <div>
                <div className="text-2xl font-bold text-foreground tracking-tight">
                    {value}
                </div>
                {trend && (
                    <div className="flex items-center gap-1 mt-1">
                        {trendIcon && (
                            <span className={cn("material-symbols-outlined text-[16px]", trendColor)}>
                                {trendIcon}
                            </span>
                        )}
                        <span className={cn("text-xs font-medium", trendColor)}>
                            {trend.value}
                        </span>
                        {trend.label && (
                            <span className="text-muted-foreground text-xs ml-1">
                                {trend.label}
                            </span>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
