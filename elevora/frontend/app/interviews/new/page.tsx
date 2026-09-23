"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Input } from "@/components/Input";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Select } from "@/components/Select";
import { ApiError, interviewsApi, profilesApi } from "@/lib/api";
import {
  INTERVIEW_CATEGORIES,
  type InterviewCategory,
  type InterviewConfig,
  type InterviewDifficulty,
  type InterviewProfile,
} from "@/lib/types";

const DIFFICULTIES: { value: InterviewDifficulty; label: string }[] = [
  { value: "easy", label: "Easy — warm up" },
  { value: "medium", label: "Medium — typical" },
  { value: "hard", label: "Hard — push me" },
];

function profileDifficultyLabel(profile: InterviewProfile) {
  return profile.difficulty === "adaptive" ? "Adaptive" : profile.difficulty;
}

// ---- Profile-based flow (default) -----------------------------------------

function ProfilePicker({ onCreated }: { onCreated: (id: string) => void }) {
  const [profiles, setProfiles] = useState<InterviewProfile[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<InterviewProfile | null>(null);
  const [role, setRole] = useState("");
  const [company, setCompany] = useState("");
  const [industry, setIndustry] = useState("");
  const [difficulty, setDifficulty] = useState<InterviewDifficulty>("medium");
  const [durationMinutes, setDurationMinutes] = useState(20);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    profilesApi
      .list()
      .then(setProfiles)
      .catch(() => setLoadError("Couldn't load interview profiles. Try refreshing."));
  }, []);

  function selectProfile(profile: InterviewProfile) {
    setSelected(profile);
    setDifficulty(profile.difficulty === "adaptive" ? "medium" : profile.difficulty);
    setError(null);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!selected) return;
    setError(null);
    setIsSubmitting(true);

    const payload: InterviewConfig = {
      profileId: selected.id,
      role: role || undefined,
      company: company || undefined,
      industry: industry || undefined,
      experienceLevel: "entry-level",
      difficulty,
      language: "English",
      durationMinutes,
    };

    try {
      const interview = await interviewsApi.create(payload);
      onCreated(interview.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create the interview. Try again.");
      setIsSubmitting(false);
    }
  }

  if (loadError) return <p className="text-sm text-danger">{loadError}</p>;
  if (!profiles) return <p className="text-sm text-white/45">Loading interview profiles…</p>;

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 md:grid-cols-2">
        {profiles.map((profile) => (
          <Card
            key={profile.id}
            className={selected?.id === profile.id ? "border-violet-400/40 ring-1 ring-violet-400/40" : undefined}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-medium text-navy-900">{profile.name}</p>
                {!profile.isSystem && (
                  <span className="mt-1 inline-block rounded-full bg-surface-muted px-2 py-0.5 text-xs text-ink-600">
                    Custom
                  </span>
                )}
              </div>
            </div>
            <p className="mt-2 text-sm text-white/45">{profile.description}</p>
            <p className="mt-3 text-xs text-ink-600">
              <span className="font-medium text-ink-900">Subjects:</span>{" "}
              {profile.subjects.join(", ")}
            </p>
            <p className="mt-2 text-xs text-ink-600">
              {profileDifficultyLabel(profile)} · {profile.maxQuestions} questions
            </p>
            <Button
              type="button"
              variant={selected?.id === profile.id ? "primary" : "secondary"}
              className="mt-4 w-full"
              onClick={() => selectProfile(profile)}
            >
              {selected?.id === profile.id ? "Selected" : "Select"}
            </Button>
          </Card>
        ))}
      </div>

      {profiles.length === 0 && (
        <p className="text-sm text-white/45">No interview profiles available yet.</p>
      )}

      {selected && (
        <Card>
          <p className="font-medium text-navy-900">Configure “{selected.name}”</p>
          <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-5">
            <Input
              label="Role (optional)"
              name="role"
              placeholder="e.g. Backend Engineer"
              value={role}
              onChange={(e) => setRole(e.target.value)}
            />
            <Input
              label="Company (optional)"
              name="company"
              placeholder="e.g. Acme Corp"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
            />
            <Input
              label="Industry (optional)"
              name="industry"
              placeholder="e.g. Technology"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
            />
            <Select
              label="Difficulty"
              name="difficulty"
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value as InterviewDifficulty)}
              options={DIFFICULTIES}
            />
            <div className="flex flex-col gap-1.5">
              <label htmlFor="duration" className="text-sm font-medium text-ink-900">
                Duration: {durationMinutes} minutes
              </label>
              <input
                id="duration"
                type="range"
                min={5}
                max={60}
                step={5}
                value={durationMinutes}
                onChange={(e) => setDurationMinutes(Number(e.target.value))}
                className="accent-accent"
              />
            </div>

            {error && <p className="text-sm text-danger">{error}</p>}

            <Button type="submit" isLoading={isSubmitting}>
              Create interview
            </Button>
          </form>
        </Card>
      )}
    </div>
  );
}

// ---- Legacy category flow (kept for full backward compatibility) ---------

function CategoryForm({ onCreated }: { onCreated: (id: string) => void }) {
  const [category, setCategory] = useState<InterviewCategory>("software-engineer");
  const [role, setRole] = useState("");
  const [company, setCompany] = useState("");
  const [exam, setExam] = useState("");
  const [industry, setIndustry] = useState("");
  const [difficulty, setDifficulty] = useState<InterviewDifficulty>("medium");
  const [durationMinutes, setDurationMinutes] = useState(20);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const showRole = ["campus-placement", "software-engineer", "mechanical-engineer"].includes(
    category
  );
  const showCompany = category === "company-specific";
  const showExam = ["upsc", "mpsc", "ssc", "banking"].includes(category);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    const payload: InterviewConfig = {
      category,
      role: showRole && role ? role : undefined,
      company: showCompany && company ? company : undefined,
      exam: showExam && exam ? exam : undefined,
      industry: industry || undefined,
      experienceLevel: "entry-level",
      difficulty,
      language: "English",
      durationMinutes,
    };

    try {
      const interview = await interviewsApi.create(payload);
      onCreated(interview.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't create the interview. Try again.");
      setIsSubmitting(false);
    }
  }

  return (
    <Card>
      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        <Select
          label="What are you preparing for?"
          name="category"
          value={category}
          onChange={(e) => setCategory(e.target.value as InterviewCategory)}
          options={INTERVIEW_CATEGORIES}
        />

        {showRole && (
          <Input
            label="Role"
            name="role"
            placeholder="e.g. Backend Engineer"
            value={role}
            onChange={(e) => setRole(e.target.value)}
          />
        )}

        {showCompany && (
          <Input
            label="Company"
            name="company"
            placeholder="e.g. Acme Corp"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
          />
        )}

        {showExam && (
          <Input
            label="Exam"
            name="exam"
            placeholder="e.g. UPSC Civil Services"
            value={exam}
            onChange={(e) => setExam(e.target.value)}
          />
        )}

        <Input
          label="Industry (optional)"
          name="industry"
          placeholder="e.g. Technology"
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
        />

        <Select
          label="Difficulty"
          name="difficulty"
          value={difficulty}
          onChange={(e) => setDifficulty(e.target.value as InterviewDifficulty)}
          options={DIFFICULTIES}
        />

        <div className="flex flex-col gap-1.5">
          <label htmlFor="duration" className="text-sm font-medium text-ink-900">
            Duration: {durationMinutes} minutes
          </label>
          <input
            id="duration"
            type="range"
            min={5}
            max={60}
            step={5}
            value={durationMinutes}
            onChange={(e) => setDurationMinutes(Number(e.target.value))}
            className="accent-accent"
          />
        </div>

        {error && <p className="text-sm text-danger">{error}</p>}

        <Button type="submit" isLoading={isSubmitting}>
          Create interview
        </Button>
      </form>
    </Card>
  );
}

// ---- Page ------------------------------------------------------------------

function NewInterviewForm() {
  const router = useRouter();
  const [mode, setMode] = useState<"profile" | "category">("profile");

  function handleCreated(id: string) {
    router.push(`/interviews/${id}`);
  }

  return (
    <div className="mx-auto max-w-5xl px-5 py-10 lg:px-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-white">Configure your interview</h1>
          <p className="mt-2 text-sm text-white/45">
            Pick an interview profile to set the subjects, question types, and pacing — or{" "}
            <Link href="/interview-profiles" className="text-accent hover:underline">
              build your own
            </Link>
            .
          </p>
        </div>
      </div>

      <div className="mt-6 flex gap-2 border-b border-white/[.08]">
        <button
          type="button"
          onClick={() => setMode("profile")}
          className={`px-3 py-2 text-sm font-medium ${
            mode === "profile"
              ? "border-b-2 border-accent text-navy-900"
              : "text-ink-600 hover:text-navy-900"
          }`}
        >
          Interview profiles
        </button>
        <button
          type="button"
          onClick={() => setMode("category")}
          className={`px-3 py-2 text-sm font-medium ${
            mode === "category"
              ? "border-b-2 border-accent text-navy-900"
              : "text-ink-600 hover:text-navy-900"
          }`}
        >
          Choose by category instead
        </button>
      </div>

      <div className="mt-8">
        {mode === "profile" ? (
          <ProfilePicker onCreated={handleCreated} />
        ) : (
          <CategoryForm onCreated={handleCreated} />
        )}
      </div>
    </div>
  );
}

export default function NewInterviewPage() {
  return (
    <ProtectedRoute>
      <NewInterviewForm />
    </ProtectedRoute>
  );
}
