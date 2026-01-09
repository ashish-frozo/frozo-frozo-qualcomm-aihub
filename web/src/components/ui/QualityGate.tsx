"use client";

import { cn } from "@/lib/utils";

interface QualityGateProps {
    metric: string;
    actualValue: number | null;
    threshold: number;
    operator: "lt" | "lte" | "gt" | "gte" | "eq";
    passed: boolean;
    unit?: string;
    className?: string;
}

function formatOperator(operator: string): string {
    const operatorMap: Record<string, string> = {
        lt: "<",
        lte: "≤",
        gt: ">",
        gte: "≥",
        eq: "=",
    };
    return operatorMap[operator] || operator;
}

function formatMetricName(metric: string): string {
    return metric
        .replace(/_/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function QualityGate({
    metric,
    actualValue,
    threshold,
    operator,
    passed,
    unit = "",
    className,
}: QualityGateProps) {
    const isAvailable = actualValue !== null && !Number.isNaN(actualValue);
    const displayValue = isAvailable ? actualValue.toFixed(2) : "N/A";

    // Calculate percentage for progress bar
    // For "less than" operators, lower is better
    // For "greater than" operators, higher is better
    let percentage = 0;
    let exceedsThreshold = false;

    if (isAvailable) {
        if (operator === "lt" || operator === "lte") {
            // For less than: 100% = hitting threshold, >100% = exceeded
            percentage = Math.min((actualValue / threshold) * 100, 100);
            exceedsThreshold = actualValue > threshold;
        } else {
            // For greater than: 100% = hitting threshold
            percentage = Math.min((actualValue / threshold) * 100, 100);
            exceedsThreshold = actualValue < threshold;
        }
    }

    const barColor = passed ? "bg-emerald-500" : "bg-red-500";
    const valueColor = passed ? "text-emerald-400" : "text-red-500";
    const thresholdPosition = Math.min(90, Math.max(10, (threshold / (threshold * 1.3)) * 100));

    return (
        <div className={cn("flex flex-col gap-2", className)}>
            <div className="flex justify-between items-end">
                <span className="text-muted-foreground text-sm font-medium">
                    {formatMetricName(metric)}
                </span>
                <div className="text-right">
                    <span className={cn("font-bold font-mono", valueColor)}>
                        {displayValue}{unit}
                    </span>
                    <span className="text-muted-foreground text-xs ml-1">
                        / {formatOperator(operator)}{threshold}{unit}
                    </span>
                </div>
            </div>
            <div className="relative h-2 w-full bg-muted rounded-full overflow-hidden">
                {/* Threshold marker */}
                <div
                    className="absolute top-0 bottom-0 w-0.5 bg-white z-10 opacity-30"
                    style={{ left: `${thresholdPosition}%` }}
                />
                {/* Progress bar */}
                <div
                    className={cn("h-full rounded-full transition-all duration-500", barColor)}
                    style={{ width: `${Math.min(percentage, 100)}%` }}
                />
            </div>
            {!passed && exceedsThreshold && (
                <p className="text-red-400/80 text-xs mt-0.5 flex items-center gap-1">
                    <span className="material-symbols-outlined text-xs">warning</span>
                    Exceeded threshold by {Math.abs(((actualValue! - threshold) / threshold) * 100).toFixed(0)}%
                </p>
            )}
            {!isAvailable && (
                <p className="text-muted-foreground text-xs mt-0.5 flex items-center gap-1">
                    <span className="material-symbols-outlined text-xs">info</span>
                    Metric not available
                </p>
            )}
        </div>
    );
}
