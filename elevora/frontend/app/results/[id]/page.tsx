"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { DimensionBar } from "@/components/DimensionBar";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { ApiError, interviewsApi } from "@/lib/api";
import {
  DIMENSION_LABELS,
  DIMENSION_ORDER,
  INTERVIEW_CATEGORIES,
  type Confidence,
  type Interview,
  type InterviewReport,
} from "@/lib/types";

function categoryLabel(value: string) {
  return INTERVIEW_CATEGORIES.find((c) => c.value === value)?.label ?? value;
}

const CONFIDENCE_COPY: Record<Confidence, string> = {
  low: "Low confidence — this was a short or narrow session, treat the scores as a rough signal rather than a final verdict.",
  medium: "Medium confidence — a reasonable sample of questions to draw conclusions from.",
  high: "High confidence — enough breadth and length here to trust the scores.",
};

function ScoreRing({ score }: { score: number }) {
  return (
    <div className="flex h-28 w-28 flex-col items-center justify-center rounded-full border-4 border-accent bg-white">
      <span className="text-3xl font-semibold text-white">{score}</span>
      <span className="text-xs text-white/30">/ 100</span>
    </div>
  );
}

function ReportView({ interview, report }: { interview: Interview; report: InterviewReport }) {
  return (
    <div className="mt-6 space-y-6">
      <Card className="flex flex-wrap items-center gap-6">
        <ScoreRing score={report.overallScore} />
        <div className="flex-1">
          <p className="text-sm font-medium text-white">
            {categoryLabel(interview.category)}
            {interview.role ? ` — ${interview.role}` : ""}
          </p>
          <p className="mt-1 text-sm text-white/50">{CONFIDENCE_COPY[report.confidence]}</p>
          <p className="mt-2 text-xs text-white/30">
            Generated {new Date(report.generatedAt).toLocaleString()}
          </p>
        </div>
      </Card>

      <Card>
        <p className="text-sm font-medium text-white">Dimension breakdown</p>
        <div className="mt-4 space-y-5">
          {DIMENSION_ORDER.map((key) => (
            <DimensionBar key={key} label={DIMENSION_LABELS[key]} dimension={report.dimensions[key]} />
          ))}
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <p className="text-sm font-medium text-white">Strengths</p>
          {report.strengths.length === 0 ? (
            <p className="mt-2 text-sm text-white/50">Nothing specific stood out this time.</p>
          ) : (
            <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-ink-900">
              {report.strengths.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <p className="text-sm font-medium text-white">Weaknesses</p>
          {report.weaknesses.length === 0 ? (
            <p className="mt-2 text-sm text-white/50">Nothing specific stood out this time.</p>
          ) : (
            <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-ink-900">
              {report.weaknesses.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {report.recommendedPractice.length > 0 && (
        <Card>
          <p className="text-sm font-medium text-white">What to practice next</p>
          <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-ink-900">
            {report.recommendedPractice.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
          <Link href="/interviews/new" className="mt-3 inline-block text-sm text-accent">
            Start a targeted practice interview →
          </Link>
        </Card>
      )}

      {report.improvedAnswer && (
        <Card className="bg-white/[.03]">
          <p className="text-sm font-medium text-white">A stronger version of one of your answers</p>
          <p className="mt-2 whitespace-pre-wrap text-sm text-white/50">{report.improvedAnswer}</p>
        </Card>
      )}

      <p className="text-xs text-white/30">
        Delivery and webcam dimensions show &quot;Not available&quot; on purpose — those need the
        speech/webcam analytics pipeline (Phase 7/8), which isn&apos;t built yet. Nothing here was
        estimated to fill the gap.
      </p>
    </div>
  );
}

function ResultsContent({ id }: { id: string }) {
  const [interview, setInterview] = useState<Interview | null>(null);
  const [report, setReport] = useState<InterviewReport | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    interviewsApi
      .get(id)
      .then(async (interviewData) => {
        setInterview(interviewData);
        try {
          setReport(await interviewsApi.getReport(id));
        } catch (err) {
          if (!(err instanceof ApiError && err.status === 404)) throw err;
          // no report yet — not an error, just an empty state
        }
      })
      .catch((err) =>
        setLoadError(
          err instanceof ApiError && err.status === 404
            ? "Interview not found."
            : "Couldn't load this interview."
        )
      )
      .finally(() => setIsLoading(false));
  }, [id]);

  async function handleGenerate() {
    setGenerateError(null);
    setIsGenerating(true);
    try {
      setReport(await interviewsApi.generateReport(id));
    } catch (err) {
      setGenerateError(
        err instanceof ApiError
          ? err.message
          : "Couldn't generate the report. Check that the backend has OPENAI_API_KEY set."
      );
    } finally {
      setIsGenerating(false);
    }
  }

  if (loadError) {
    return (
      <div className="mx-auto max-w-4xl px-5 py-10 lg:px-8">
        <p className="rounded-xl border border-red-400/15 bg-red-400/5 p-4 text-sm text-red-300">{loadError}</p>
        <Link href="/dashboard" className="mt-4 inline-block text-sm text-accent">
          Back to dashboard
        </Link>
      </div>
    );
  }

  if (isLoading || !interview) {
    return <div className="mx-auto max-w-2xl px-6 py-12 text-sm text-white/50">Loading…</div>;
  }

  return (
    <div className={`mx-auto px-6 py-12 ${report ? "max-w-4xl" : "max-w-2xl"}`}>
      <Link href="/dashboard" className="text-sm text-accent">
        ← Back to dashboard
      </Link>
      <h1 className="mt-4 text-2xl font-semibold text-white">Performance report</h1>

      {interview.status !== "completed" && (
        <Card className="mt-6 bg-white/[.03]">
          <p className="text-sm text-white/50">
            {interview.status === "abandoned"
              ? "This interview was left early and won't be scored — only completed interviews get a report."
              : interview.status === "in_progress"
                ? "This interview is still in progress. Finish it to get a report."
                : "This interview hasn't started yet."}
          </p>
          <Link href={`/interviews/${id}`} className="mt-3 inline-block text-sm text-accent">
            Go to the interview →
          </Link>
        </Card>
      )}

      {interview.status === "completed" && !report && (
        <Card className="mt-6">
          <p className="text-sm text-white/50">
            This interview is complete but hasn&apos;t been scored yet. Generating a report sends
            the full transcript to the AI evaluator — it isn&apos;t automatic, so you decide when
            that happens.
          </p>
          {generateError && <p className="mt-2 text-sm text-danger">{generateError}</p>}
          <div className="mt-4">
            <Button onClick={handleGenerate} isLoading={isGenerating}>
              Generate report
            </Button>
          </div>
        </Card>
      )}

      {report && <ReportView interview={interview} report={report} />}
    </div>
  );
}

export default function ResultsPage({ params }: { params: { id: string } }) {
  return (
    <ProtectedRoute>
      <ResultsContent id={params.id} />
    </ProtectedRoute>
  );
}
