"use client";

import { useEffect, useState } from "react";

function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

/**
 * Shows elapsed time since the interview started. This is informational
 * only — it does not end the interview. The engine ends interviews by
 * question count (see backend/app/services/interview_engine.py), not wall
 * clock, so a candidate who thinks slowly isn't cut off mid-thought.
 * `targetMinutes` is shown purely as a reference point.
 */
export function InterviewTimer({
  startedAt,
  targetMinutes,
}: {
  startedAt: string;
  targetMinutes?: number;
}) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    const startMs = new Date(startedAt).getTime();
    const tick = () => setElapsedSeconds(Math.max(0, Math.floor((Date.now() - startMs) / 1000)));
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [startedAt]);

  return (
    <span className="font-mono text-sm text-ink-600">
      {formatDuration(elapsedSeconds)}
      {targetMinutes ? ` / ~${targetMinutes}:00` : ""}
    </span>
  );
}
