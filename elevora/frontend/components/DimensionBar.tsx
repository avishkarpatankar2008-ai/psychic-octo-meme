import type { DimensionScore } from "@/lib/types";

export function DimensionBar({ label, dimension }: { label: string; dimension: DimensionScore }) {
  const isAvailable = dimension.score !== null;
  const percent = isAvailable ? (dimension.score! / 5) * 100 : 0;

  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-navy-900">{label}</span>
        <span className="text-ink-600">{isAvailable ? `${dimension.score}/5` : "Not available"}</span>
      </div>
      <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-surface-muted">
        {isAvailable ? (
          <div className="h-full rounded-full bg-accent" style={{ width: `${percent}%` }} />
        ) : (
          <div
            className="h-full rounded-full"
            style={{
              backgroundImage:
                "repeating-linear-gradient(45deg, transparent, transparent 4px, rgba(0,0,0,0.06) 4px, rgba(0,0,0,0.06) 8px)",
            }}
          />
        )}
      </div>
      <p className="mt-1.5 text-sm text-ink-600">{dimension.evidence}</p>
    </div>
  );
}
