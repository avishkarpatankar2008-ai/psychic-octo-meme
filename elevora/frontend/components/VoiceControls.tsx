"use client";

import { useRef, useState } from "react";

type RecordingState = "idle" | "recording" | "processing";
export type { RecordingState };

interface VoiceControlsProps {
  onRecorded: (blob: Blob) => Promise<void>;
  onStateChange?: (state: RecordingState) => void;
  disabled?: boolean;
}

/**
 * Microphone recording control for the interview room.
 *
 * UNVERIFIED. This was written and type-checked in a sandbox with no
 * browser and no microphone — nobody has actually clicked "record" and
 * confirmed a blob comes out the other end. Specific risks worth knowing:
 *   - MediaRecorder's supported mime types vary by browser (Chrome/Firefox:
 *     audio/webm;codecs=opus, Safari: audio/mp4). The candidate list below
 *     is my best understanding of current support, not something tested.
 *   - Safari's MediaRecorder support has historically been the least
 *     reliable of the major browsers — test there first if something's off.
 *   - getUserMedia requires a secure context (HTTPS, or localhost) — it
 *     will silently fail to prompt on a plain http:// deployment.
 * Test in Chrome on localhost first.
 */
const CANDIDATE_MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4",
  "audio/ogg;codecs=opus",
];

function pickSupportedMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return CANDIDATE_MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type));
}

export function VoiceControls({ onRecorded, onStateChange, disabled = false }: VoiceControlsProps) {
  const [state, setState] = useState<RecordingState>("idle");
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  function updateState(next: RecordingState) {
    setState(next);
    onStateChange?.(next);
  }

  async function startRecording() {
    setError(null);

    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      setError("This browser doesn't support microphone recording. Use the text box instead.");
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError(
        "Microphone access was denied or unavailable. Check your browser's permission " +
          "settings, or use the text box instead."
      );
      return;
    }

    const mimeType = pickSupportedMimeType();
    const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    chunksRef.current = [];

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };

    recorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      const blob = new Blob(chunksRef.current, { type: mimeType ?? "audio/webm" });
      updateState("processing");
      try {
        await onRecorded(blob);
      } catch {
        setError("Couldn't process that recording. Try again, or use the text box.");
      } finally {
        updateState("idle");
      }
    };

    mediaRecorderRef.current = recorder;
    recorder.start();
    updateState("recording");
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-3">
        {state === "idle" && (
          <button
            type="button"
            onClick={startRecording}
            disabled={disabled}
            className="inline-flex items-center gap-2 rounded-md border border-surface-border bg-white px-4 py-2.5 text-sm font-medium text-navy-900 hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-50"
          >
            🎤 Record answer
          </button>
        )}
        {state === "recording" && (
          <button
            type="button"
            onClick={stopRecording}
            className="inline-flex items-center gap-2 rounded-md bg-danger px-4 py-2.5 text-sm font-medium text-white"
          >
            ● Stop recording
          </button>
        )}
        {state === "processing" && (
          <span className="text-sm text-ink-600">Transcribing your answer…</span>
        )}
      </div>
      {error && <p className="text-sm text-danger">{error}</p>}
    </div>
  );
}
