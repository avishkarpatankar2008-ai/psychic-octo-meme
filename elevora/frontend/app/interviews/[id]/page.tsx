"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/Button";
import { CameraPreview, type CameraStatus } from "@/components/CameraPreview";
import { Card } from "@/components/Card";
import { InterviewTimer } from "@/components/InterviewTimer";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { ResumeJdUpload } from "@/components/ResumeJdUpload";
import { VoiceControls, type RecordingState } from "@/components/VoiceControls";
import { ApiError, interviewsApi } from "@/lib/api";
import { INTERVIEW_CATEGORIES, type Interview, type InterviewTurn } from "@/lib/types";
import { WebcamAnalyticsTracker } from "@/lib/webcamAnalytics";

function categoryLabel(value: string) {
  return INTERVIEW_CATEGORIES.find((c) => c.value === value)?.label ?? value;
}

/** A completed Q&A exchange, rendered the same way whether it came from
 * history (GET /turns) or was just answered in this session. */
function TurnBubbles({ turn }: { turn: Pick<InterviewTurn, "question" | "answer" | "isFollowUp"> }) {
  return (
    <div className="space-y-3">
      <div className={`rounded-md p-4 ${turn.isFollowUp ? "bg-accent-100" : "bg-surface-muted"}`}>
        <p className="text-sm font-medium text-navy-900">
          {turn.isFollowUp ? "Interviewer follows up" : "Interviewer"}
        </p>
        <p className="mt-1 text-sm text-ink-600">{turn.question}</p>
      </div>
      <div className="rounded-md border border-surface-border p-4">
        <p className="text-sm font-medium text-navy-900">You</p>
        <p className="mt-1 whitespace-pre-wrap text-sm text-ink-600">{turn.answer}</p>
      </div>
    </div>
  );
}

/**
 * Fetches and plays the current question as audio (Phase 3 TTS).
 *
 * UNVERIFIED: no browser was available to confirm audio actually plays.
 * The fetch-then-blob-URL approach is standard, and triggering playback
 * from a click handler (rather than automatically) sidesteps browser
 * autoplay restrictions on unmuted audio — but neither of those has been
 * checked against a real browser here.
 */
function PlayQuestionButton({
  interviewId,
  onSpeakingChange,
}: {
  interviewId: string;
  onSpeakingChange?: (speaking: boolean) => void;
}) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  async function handlePlay() {
    setError(null);
    setIsLoading(true);
    try {
      const res = await fetch(interviewsApi.questionAudioUrl(interviewId), {
        credentials: "include",
      });
      if (!res.ok) throw new Error(`status ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      if (!audioRef.current) {
        audioRef.current = new Audio();
        audioRef.current.onplay = () => onSpeakingChange?.(true);
        audioRef.current.onended = () => onSpeakingChange?.(false);
        audioRef.current.onpause = () => onSpeakingChange?.(false);
      }
      audioRef.current.src = url;
      await audioRef.current.play();
    } catch {
      setError("Couldn't play the question audio. Read it above instead.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="mt-2 flex items-center gap-2">
      <button
        type="button"
        onClick={handlePlay}
        disabled={isLoading}
        className="text-sm font-medium text-accent hover:text-accent-700 disabled:opacity-50"
      >
        {isLoading ? "Loading audio…" : "🔊 Play question aloud"}
      </button>
      {error && <span className="text-sm text-danger">{error}</span>}
    </div>
  );
}

function DraftView({
  interview,
  onStarted,
  onUpdated,
}: {
  interview: Interview;
  onStarted: () => void;
  onUpdated: (interview: Interview) => void;
}) {
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStart() {
    setError(null);
    setIsStarting(true);
    try {
      await interviewsApi.start(interview.id);
      onStarted();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Couldn't start the interview. Check that the backend has OPENAI_API_KEY set."
      );
      setIsStarting(false);
    }
  }

  return (
    <>
      <Card className="mt-6">
        <dl className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-ink-400">Difficulty</dt>
            <dd className="mt-1 capitalize text-ink-900">{interview.difficulty}</dd>
          </div>
          <div>
            <dt className="text-ink-400">Duration</dt>
            <dd className="mt-1 text-ink-900">{interview.durationMinutes} minutes</dd>
          </div>
        </dl>
      </Card>

      <ResumeJdUpload interview={interview} onUpdated={onUpdated} />

      {error && <p className="mt-4 text-sm text-danger">{error}</p>}

      <div className="mt-6">
        <Button onClick={handleStart} isLoading={isStarting}>
          Start interview
        </Button>
      </div>
    </>
  );
}

const RECORDING_LABEL: Record<RecordingState, string> = {
  idle: "Mic idle",
  recording: "● Recording",
  processing: "Transcribing…",
};

const CAMERA_LABEL: Record<CameraStatus, string> = {
  idle: "Camera off",
  requesting: "Requesting camera…",
  active: "Camera on",
  denied: "Camera denied",
  unavailable: "Camera unavailable",
  disconnected: "Camera disconnected",
};

/** Status bar across the top of a live session: timer, mic/camera state,
 * exit control. Loosely mirrors the spec's interview-room mockup
 * ("🎤 Mute 📹 Camera Timer End"), adapted to what this phase actually has. */
function RoomStatusBar({
  interview,
  recordingState,
  cameraStatus,
  isSpeaking,
  cameraEnabled,
  onToggleCamera,
  onExit,
}: {
  interview: Interview;
  recordingState: RecordingState;
  cameraStatus: CameraStatus;
  isSpeaking: boolean;
  cameraEnabled: boolean;
  onToggleCamera: () => void;
  onExit: () => void;
}) {
  const [confirmingExit, setConfirmingExit] = useState(false);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-surface-border bg-white px-4 py-3">
      <div className="flex flex-wrap items-center gap-4 text-sm">
        {interview.startedAt && (
          <InterviewTimer startedAt={interview.startedAt} targetMinutes={interview.durationMinutes} />
        )}
        <span className="text-ink-600">{RECORDING_LABEL[recordingState]}</span>
        <button
          type="button"
          onClick={onToggleCamera}
          className="text-ink-600 hover:text-navy-900"
        >
          {CAMERA_LABEL[cameraStatus]} {cameraEnabled ? "(turn off)" : "(turn on)"}
        </button>
        {isSpeaking && <span className="text-accent">🔊 AI speaking…</span>}
      </div>

      {confirmingExit ? (
        <div className="flex items-center gap-2">
          <span className="text-sm text-ink-600">End now? Progress so far is saved, not scored.</span>
          <Button variant="danger" onClick={onExit}>
            Confirm exit
          </Button>
          <Button variant="ghost" onClick={() => setConfirmingExit(false)}>
            Cancel
          </Button>
        </div>
      ) : (
        <Button variant="secondary" onClick={() => setConfirmingExit(true)}>
          Exit interview
        </Button>
      )}
    </div>
  );
}

function LiveInterviewView({
  interview,
  turns,
  onUpdate,
  onExited,
}: {
  interview: Interview;
  turns: InterviewTurn[];
  onUpdate: (interview: Interview, newTurn?: InterviewTurn) => void;
  onExited: () => void;
}) {
  const [answer, setAnswer] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recordingState, setRecordingState] = useState<RecordingState>("idle");
  const [cameraEnabled, setCameraEnabled] = useState(true);
  const [cameraStatus, setCameraStatus] = useState<CameraStatus>("idle");
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isExiting, setIsExiting] = useState(false);
  const analyticsTracker = useRef(new WebcamAnalyticsTracker());
  const handleFrameSample = useCallback((video: HTMLVideoElement) => {
    analyticsTracker.current.sample(video);
  }, []);

  async function submitWebcamMetricsIfAvailable() {
    const aggregate = analyticsTracker.current.getAggregate();
    if (!aggregate) return; // camera was off, init failed, or too few samples
    try {
      await interviewsApi.submitWebcamMetrics(interview.id, aggregate);
    } catch {
      // Best-effort — a missing webcam score just means the report shows
      // "Not available" for that dimension, same as if the camera were
      // never used at all.
    }
  }

  async function handleTextSubmit(e: FormEvent) {
    e.preventDefault();
    if (!interview.pendingQuestion || !answer.trim()) return;

    const questionJustAnswered = interview.pendingQuestion;
    setError(null);
    setIsBusy(true);
    try {
      const result = await interviewsApi.answer(interview.id, answer.trim());
      applyResult(questionJustAnswered, answer.trim(), result);
      setAnswer("");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `The AI interviewer didn't respond: ${err.message}`
          : "Something went wrong submitting your answer. Your draft is still in the box below — try again."
      );
    } finally {
      setIsBusy(false);
    }
  }

  async function handleAudioRecorded(blob: Blob) {
    if (!interview.pendingQuestion) return;
    const questionJustAnswered = interview.pendingQuestion;
    setError(null);
    setIsBusy(true);
    try {
      const result = await interviewsApi.answerAudio(interview.id, blob, "answer.webm");
      applyResult(questionJustAnswered, result.transcript, result);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? `Voice answer failed: ${err.message}`
          : "Couldn't submit your voice answer. Try the text box instead."
      );
    } finally {
      setIsBusy(false);
    }
  }

  async function handleExit() {
    setIsExiting(true);
    try {
      await submitWebcamMetricsIfAvailable(); // must happen before /exit — status check requires in_progress
      await interviewsApi.exit(interview.id);
      onExited();
    } catch {
      setError("Couldn't exit the interview. Try again.");
      setIsExiting(false);
    }
  }

  function applyResult(
    questionJustAnswered: NonNullable<Interview["pendingQuestion"]>,
    answerText: string,
    result: {
      status: Interview["status"];
      questionNumber: number;
      maxQuestions: number;
      difficultyLevel: number;
      pendingQuestion?: Interview["pendingQuestion"];
    }
  ) {
    const newTurn: InterviewTurn = {
      sequence: result.questionNumber,
      question: questionJustAnswered.question,
      answer: answerText,
      topic: questionJustAnswered.topic,
      difficulty: questionJustAnswered.difficulty,
      isFollowUp: questionJustAnswered.isFollowUp,
      createdAt: new Date().toISOString(),
    };
    onUpdate(
      {
        ...interview,
        status: result.status,
        questionNumber: result.questionNumber,
        maxQuestions: result.maxQuestions,
        difficultyLevel: result.difficultyLevel,
        pendingQuestion: result.pendingQuestion,
      },
      newTurn
    );
    if (result.status === "completed") {
      submitWebcamMetricsIfAvailable();
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <RoomStatusBar
        interview={interview}
        recordingState={recordingState}
        cameraStatus={cameraStatus}
        isSpeaking={isSpeaking}
        cameraEnabled={cameraEnabled}
        onToggleCamera={() => setCameraEnabled((prev) => !prev)}
        onExit={handleExit}
      />
      {isExiting && <p className="text-sm text-ink-600">Ending the interview…</p>}

      {interview.maxQuestions && (
        <p className="text-sm text-ink-400">
          Question {interview.questionNumber + (interview.pendingQuestion ? 1 : 0)} of{" "}
          {interview.maxQuestions}
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-[1fr,280px]">
        <div className="space-y-6">
          {turns.map((turn) => (
            <TurnBubbles key={turn.sequence} turn={turn} />
          ))}

          {interview.pendingQuestion && (
            <div>
              <div
                className={`rounded-md p-4 ${
                  interview.pendingQuestion.isFollowUp ? "bg-accent-100" : "bg-surface-muted"
                }`}
              >
                <p className="text-sm font-medium text-navy-900">
                  {interview.pendingQuestion.isFollowUp ? "Interviewer follows up" : "Interviewer"}
                </p>
                <p className="mt-1 text-sm text-ink-600">{interview.pendingQuestion.question}</p>
              </div>
              <PlayQuestionButton interviewId={interview.id} onSpeakingChange={setIsSpeaking} />
            </div>
          )}

          {interview.pendingQuestion && (
            <div className="flex flex-col gap-4">
              <VoiceControls
                onRecorded={handleAudioRecorded}
                onStateChange={setRecordingState}
                disabled={isBusy}
              />

              <form onSubmit={handleTextSubmit} className="flex flex-col gap-3">
                <textarea
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                  rows={4}
                  placeholder="Or type your answer..."
                  disabled={isBusy}
                  className="rounded-md border border-surface-border px-3.5 py-2.5 text-sm text-ink-900 placeholder:text-ink-400 focus:border-accent"
                />
                {error && <p className="text-sm text-danger">{error}</p>}
                <div>
                  <Button type="submit" isLoading={isBusy} disabled={!answer.trim()}>
                    Submit answer
                  </Button>
                </div>
              </form>
            </div>
          )}
        </div>

        <div>
          <CameraPreview
            enabled={cameraEnabled}
            onStatusChange={setCameraStatus}
            onFrameSample={handleFrameSample}
          />
          <p className="mt-2 text-xs text-ink-400">
            Self-view only — nothing here is recorded, uploaded, or analyzed.
          </p>
        </div>
      </div>
    </div>
  );
}

function CompletedView({ interviewId }: { interviewId: string }) {
  return (
    <Card className="mt-6 bg-surface-muted">
      <p className="text-sm font-medium text-navy-900">Interview completed</p>
      <p className="mt-2 text-sm text-ink-600">
        The transcript above is what you actually said. Generate a scored, evidence-based report
        whenever you&apos;re ready to see how it went.
      </p>
      <Link href={`/results/${interviewId}`} className="mt-3 inline-block text-sm text-accent">
        View performance report →
      </Link>
    </Card>
  );
}

function AbandonedView() {
  return (
    <Card className="mt-6 bg-surface-muted">
      <p className="text-sm font-medium text-navy-900">You left this interview early</p>
      <p className="mt-2 text-sm text-ink-600">
        Whatever you answered before exiting is saved above. This session won&apos;t be scored —
        start a new interview when you&apos;re ready to try again.
      </p>
    </Card>
  );
}

function InterviewRoom({ id }: { id: string }) {
  const router = useRouter();
  const [interview, setInterview] = useState<Interview | null>(null);
  const [turns, setTurns] = useState<InterviewTurn[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    Promise.all([interviewsApi.get(id), interviewsApi.turns(id).catch(() => [])])
      .then(([interviewData, turnsData]) => {
        setInterview(interviewData);
        setTurns(turnsData);
      })
      .catch((err) =>
        setLoadError(
          err instanceof ApiError && err.status === 404
            ? "Interview not found."
            : "Couldn't load this interview."
        )
      );
  }, [id]);

  async function refetchTurns() {
    try {
      setTurns(await interviewsApi.turns(id));
    } catch {
      // non-fatal — the interview view still works from local state
    }
  }

  async function handleDelete() {
    setIsDeleting(true);
    try {
      await interviewsApi.remove(id);
      router.push("/dashboard");
    } catch {
      setLoadError("Couldn't delete this interview.");
      setIsDeleting(false);
    }
  }

  if (loadError) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-12">
        <p className="text-sm text-danger">{loadError}</p>
        <Link href="/dashboard" className="mt-4 inline-block text-sm text-accent">
          Back to dashboard
        </Link>
      </div>
    );
  }

  if (!interview) {
    return <div className="mx-auto max-w-2xl px-6 py-12 text-sm text-ink-600">Loading…</div>;
  }

  const isLive = interview.status === "in_progress";

  return (
    <div className={`mx-auto px-6 py-12 ${isLive ? "max-w-4xl" : "max-w-2xl"}`}>
      <Link href="/dashboard" className="text-sm text-accent">
        ← Back to dashboard
      </Link>

      <h1 className="mt-4 text-2xl font-semibold text-navy-900">
        {categoryLabel(interview.category)}
        {interview.role ? ` — ${interview.role}` : ""}
      </h1>

      {interview.status === "draft" && (
        <DraftView
          interview={interview}
          onStarted={async () => {
            setInterview(await interviewsApi.get(id));
          }}
          onUpdated={setInterview}
        />
      )}

      {isLive && (
        <div className="mt-6">
          <LiveInterviewView
            interview={interview}
            turns={turns}
            onUpdate={(updated, newTurn) => {
              setInterview(updated);
              if (newTurn) setTurns((prev) => [...prev, newTurn]);
              if (updated.status === "completed") refetchTurns();
            }}
            onExited={() => setInterview({ ...interview, status: "abandoned", pendingQuestion: undefined })}
          />
        </div>
      )}

      {interview.status === "completed" && (
        <>
          <div className="mt-6 space-y-6">
            {turns.map((turn) => (
              <TurnBubbles key={turn.sequence} turn={turn} />
            ))}
          </div>
          <CompletedView interviewId={interview.id} />
        </>
      )}

      {interview.status === "abandoned" && (
        <>
          <div className="mt-6 space-y-6">
            {turns.map((turn) => (
              <TurnBubbles key={turn.sequence} turn={turn} />
            ))}
          </div>
          <AbandonedView />
        </>
      )}

      <div className="mt-8 border-t border-surface-border pt-6">
        <Button variant="danger" onClick={handleDelete} isLoading={isDeleting}>
          Delete this interview
        </Button>
      </div>
    </div>
  );
}

export default function InterviewDetailPage({ params }: { params: { id: string } }) {
  return (
    <ProtectedRoute>
      <InterviewRoom id={params.id} />
    </ProtectedRoute>
  );
}
