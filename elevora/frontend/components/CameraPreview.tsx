"use client";

import { useEffect, useRef, useState } from "react";

export type CameraStatus =
  | "idle"
  | "requesting"
  | "active"
  | "denied"
  | "unavailable"
  | "disconnected";

interface CameraPreviewProps {
  enabled: boolean;
  onStatusChange?: (status: CameraStatus) => void;
  /** Fired roughly once per second while the camera is active — Phase 7's
   * hook point for client-side analytics (see lib/webcamAnalytics.ts). Not
   * used at all if omitted; CameraPreview itself has no analytics logic. */
  onFrameSample?: (video: HTMLVideoElement) => void;
  sampleIntervalMs?: number;
}

/**
 * Self-view camera preview for the interview room.
 *
 * UNVERIFIED — same caveat as VoiceControls (Phase 3): no browser or camera
 * was available while building this, so nobody has confirmed a stream
 * actually renders. Test in Chrome on localhost first.
 *
 * Scope note: this is purely a local self-view. Nothing is recorded or
 * uploaded — no video ever leaves the browser. If `onFrameSample` is
 * provided (Phase 7), the caller can run analysis (e.g. MediaPipe) on
 * individual frames locally; this component still never transmits video
 * itself, only whatever aggregate the caller chooses to compute and send.
 */
export function CameraPreview({
  enabled,
  onStatusChange,
  onFrameSample,
  sampleIntervalMs = 1000,
}: CameraPreviewProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [status, setStatus] = useState<CameraStatus>("idle");

  function updateStatus(next: CameraStatus) {
    setStatus(next);
    onStatusChange?.(next);
  }

  function stopCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }

  async function startCamera() {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      updateStatus("unavailable");
      return;
    }
    updateStatus("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      stream.getVideoTracks().forEach((track) => {
        track.onended = () => updateStatus("disconnected");
      });
      updateStatus("active");
    } catch {
      updateStatus("denied");
    }
  }

  useEffect(() => {
    if (enabled) {
      startCamera();
    } else {
      stopCamera();
      updateStatus("idle");
    }
    return () => stopCamera();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled]);

  useEffect(() => {
    if (status !== "active" || !onFrameSample) return;
    const interval = setInterval(() => {
      if (videoRef.current) onFrameSample(videoRef.current);
    }, sampleIntervalMs);
    return () => clearInterval(interval);
  }, [status, onFrameSample, sampleIntervalMs]);

  const statusMessage: Record<Exclude<CameraStatus, "active">, string> = {
    idle: "Camera off",
    requesting: "Requesting camera access…",
    denied: "Camera access denied — check your browser's permission settings.",
    unavailable: "This browser doesn't support camera preview.",
    disconnected: "Camera disconnected.",
  };

  return (
    <div className="overflow-hidden rounded-lg border border-surface-border bg-navy-950">
      <div className="relative aspect-video">
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          className={`h-full w-full object-cover ${status === "active" ? "" : "hidden"}`}
        />
        {status !== "active" && (
          <div className="flex h-full w-full items-center justify-center p-4 text-center text-sm text-white/70">
            {statusMessage[status]}
          </div>
        )}
      </div>
      {(status === "denied" || status === "disconnected") && (
        <button
          type="button"
          onClick={startCamera}
          className="w-full border-t border-white/10 py-2 text-sm font-medium text-white hover:bg-white/5"
        >
          Reconnect camera
        </button>
      )}
    </div>
  );
}
