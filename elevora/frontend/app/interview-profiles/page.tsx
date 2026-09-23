"use client";

import { FormEvent, useEffect, useState } from "react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Input } from "@/components/Input";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Select } from "@/components/Select";
import { ApiError, profilesApi } from "@/lib/api";
import type { InterviewProfile, InterviewProfileInput, ProfileDifficulty } from "@/lib/types";

const DIFFICULTY_OPTIONS: { value: ProfileDifficulty; label: string }[] = [
  { value: "easy", label: "Easy" },
  { value: "medium", label: "Medium" },
  { value: "hard", label: "Hard" },
  { value: "adaptive", label: "Adaptive" },
];

const EMPTY_FORM = {
  name: "",
  description: "",
  category: "",
  subjects: "",
  questionTypes: "",
  interviewerStyle: "professional",
  difficulty: "medium" as ProfileDifficulty,
  maxQuestions: 8,
  followUpEnabled: true,
  adaptiveDifficulty: true,
  resumeGrounding: true,
  jdGrounding: true,
};

type FormState = typeof EMPTY_FORM;

function toInput(form: FormState): InterviewProfileInput {
  return {
    name: form.name.trim(),
    description: form.description.trim(),
    category: form.category.trim(),
    subjects: form.subjects.split(",").map((s) => s.trim()).filter(Boolean),
    questionTypes: form.questionTypes.split(",").map((s) => s.trim()).filter(Boolean),
    interviewerStyle: form.interviewerStyle.trim() || "professional",
    difficulty: form.difficulty,
    maxQuestions: form.maxQuestions,
    followUpEnabled: form.followUpEnabled,
    adaptiveDifficulty: form.adaptiveDifficulty,
    resumeGrounding: form.resumeGrounding,
    jdGrounding: form.jdGrounding,
  };
}

function fromProfile(profile: InterviewProfile): FormState {
  return {
    name: profile.name,
    description: profile.description,
    category: profile.category,
    subjects: profile.subjects.join(", "),
    questionTypes: profile.questionTypes.join(", "),
    interviewerStyle: profile.interviewerStyle,
    difficulty: profile.difficulty,
    maxQuestions: profile.maxQuestions,
    followUpEnabled: profile.followUpEnabled,
    adaptiveDifficulty: profile.adaptiveDifficulty,
    resumeGrounding: profile.resumeGrounding,
    jdGrounding: profile.jdGrounding,
  };
}

function ProfileForm({
  initial,
  onCancel,
  onSubmit,
}: {
  initial: FormState;
  onCancel: () => void;
  onSubmit: (input: InterviewProfileInput) => Promise<void>;
}) {
  const [form, setForm] = useState<FormState>(initial);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const input = toInput(form);
    if (!input.name || !input.category || input.subjects.length === 0 || input.questionTypes.length === 0) {
      setError("Name, category, at least one subject, and at least one question type are required.");
      return;
    }
    setIsSubmitting(true);
    try {
      await onSubmit(input);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save this profile. Try again.");
      setIsSubmitting(false);
    }
  }

  return (
    <Card className="mt-4">
      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        <Input
          label="Name"
          name="name"
          placeholder="e.g. My Full Stack Interview"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
        <Input
          label="Description"
          name="description"
          placeholder="e.g. React, Node.js, and MongoDB, adaptive difficulty."
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
        />
        <Input
          label="Category"
          name="category"
          placeholder="e.g. full-stack"
          value={form.category}
          onChange={(e) => setForm({ ...form, category: e.target.value })}
        />
        <Input
          label="Subjects (comma-separated)"
          name="subjects"
          placeholder="e.g. React, Node.js, MongoDB"
          value={form.subjects}
          onChange={(e) => setForm({ ...form, subjects: e.target.value })}
        />
        <Input
          label="Question types (comma-separated)"
          name="questionTypes"
          placeholder="e.g. Technical, Scenario, Behavioral"
          value={form.questionTypes}
          onChange={(e) => setForm({ ...form, questionTypes: e.target.value })}
        />
        <Input
          label="Interviewer style"
          name="interviewerStyle"
          placeholder="e.g. professional"
          value={form.interviewerStyle}
          onChange={(e) => setForm({ ...form, interviewerStyle: e.target.value })}
        />
        <Select
          label="Difficulty"
          name="difficulty"
          value={form.difficulty}
          onChange={(e) => setForm({ ...form, difficulty: e.target.value as ProfileDifficulty })}
          options={DIFFICULTY_OPTIONS}
        />
        <div className="flex flex-col gap-1.5">
          <label htmlFor="maxQuestions" className="text-sm font-medium text-ink-900">
            Questions: {form.maxQuestions}
          </label>
          <input
            id="maxQuestions"
            type="range"
            min={3}
            max={30}
            step={1}
            value={form.maxQuestions}
            onChange={(e) => setForm({ ...form, maxQuestions: Number(e.target.value) })}
            className="accent-accent"
          />
        </div>

        <div className="grid gap-2 sm:grid-cols-2">
          {(
            [
              ["followUpEnabled", "Follow-up questions"],
              ["adaptiveDifficulty", "Adaptive difficulty"],
              ["resumeGrounding", "Ground in resume"],
              ["jdGrounding", "Ground in job description"],
            ] as [keyof FormState, string][]
          ).map(([key, label]) => (
            <label key={key} className="flex items-center gap-2 text-sm text-ink-900">
              <input
                type="checkbox"
                checked={Boolean(form[key])}
                onChange={(e) => setForm({ ...form, [key]: e.target.checked })}
                className="accent-accent"
              />
              {label}
            </label>
          ))}
        </div>

        {error && <p className="text-sm text-danger">{error}</p>}

        <div className="flex gap-3">
          <Button type="submit" isLoading={isSubmitting}>
            Save profile
          </Button>
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}

function InterviewProfilesContent() {
  const [profiles, setProfiles] = useState<InterviewProfile[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  function load() {
    profilesApi
      .list()
      .then(setProfiles)
      .catch(() => setError("Couldn't load interview profiles. Try refreshing."));
  }

  useEffect(load, []);

  async function handleCreate(input: InterviewProfileInput) {
    await profilesApi.create(input);
    setCreating(false);
    load();
  }

  async function handleUpdate(id: string, input: InterviewProfileInput) {
    await profilesApi.update(id, input);
    setEditingId(null);
    load();
  }

  async function handleDelete(id: string) {
    setDeletingId(id);
    try {
      await profilesApi.remove(id);
      load();
    } catch {
      setError("Couldn't delete this profile. Try again.");
    } finally {
      setDeletingId(null);
    }
  }

  const custom = profiles?.filter((p) => !p.isSystem) ?? [];
  const system = profiles?.filter((p) => p.isSystem) ?? [];

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-navy-900">Interview profiles</h1>
          <p className="mt-1 text-sm text-ink-600">
            Reusable interview configurations — subjects, question types, pacing, and grounding.
          </p>
        </div>
        {!creating && (
          <Button onClick={() => setCreating(true)}>Create custom profile</Button>
        )}
      </div>

      {error && <p className="mt-4 text-sm text-danger">{error}</p>}

      {creating && (
        <ProfileForm initial={EMPTY_FORM} onCancel={() => setCreating(false)} onSubmit={handleCreate} />
      )}

      {!profiles && !error && <p className="mt-8 text-sm text-ink-600">Loading…</p>}

      {profiles && (
        <>
          {custom.length > 0 && (
            <section className="mt-8">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-600">
                Your custom profiles
              </h2>
              <div className="mt-3 flex flex-col gap-4">
                {custom.map((profile) =>
                  editingId === profile.id ? (
                    <ProfileForm
                      key={profile.id}
                      initial={fromProfile(profile)}
                      onCancel={() => setEditingId(null)}
                      onSubmit={(input) => handleUpdate(profile.id, input)}
                    />
                  ) : (
                    <Card key={profile.id}>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-medium text-navy-900">{profile.name}</p>
                          <p className="mt-1 text-sm text-ink-600">{profile.description}</p>
                          <p className="mt-2 text-xs text-ink-600">
                            Subjects: {profile.subjects.join(", ")} · Types:{" "}
                            {profile.questionTypes.join(", ")}
                          </p>
                          <p className="mt-1 text-xs text-ink-600">
                            {profile.difficulty === "adaptive" ? "Adaptive" : profile.difficulty} ·{" "}
                            {profile.maxQuestions} questions
                          </p>
                        </div>
                        <div className="flex shrink-0 gap-2">
                          <Button variant="secondary" onClick={() => setEditingId(profile.id)}>
                            Edit
                          </Button>
                          <Button
                            variant="danger"
                            isLoading={deletingId === profile.id}
                            onClick={() => handleDelete(profile.id)}
                          >
                            Delete
                          </Button>
                        </div>
                      </div>
                    </Card>
                  )
                )}
              </div>
            </section>
          )}

          <section className="mt-8">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-ink-600">
              System profiles
            </h2>
            <div className="mt-3 grid gap-4 md:grid-cols-2">
              {system.map((profile) => (
                <Card key={profile.id}>
                  <p className="font-medium text-navy-900">{profile.name}</p>
                  <p className="mt-1 text-sm text-ink-600">{profile.description}</p>
                  <p className="mt-2 text-xs text-ink-600">Subjects: {profile.subjects.join(", ")}</p>
                  <p className="mt-1 text-xs text-ink-600">
                    {profile.difficulty === "adaptive" ? "Adaptive" : profile.difficulty} ·{" "}
                    {profile.maxQuestions} questions
                  </p>
                </Card>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

export default function InterviewProfilesPage() {
  return (
    <ProtectedRoute>
      <InterviewProfilesContent />
    </ProtectedRoute>
  );
}
