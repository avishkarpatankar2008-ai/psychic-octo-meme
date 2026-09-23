"use client";

import { ChangeEvent, useRef, useState } from "react";
import { Button } from "./Button";
import { Card } from "./Card";
import { ApiError, interviewsApi } from "@/lib/api";
import type { CandidateProfile, Interview, JobProfile } from "@/lib/types";

function ProfileList({ label, items }: { label: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-ink-400">{label}</p>
      <ul className="mt-1 list-inside list-disc text-sm text-ink-900">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

/** Shows exactly what was extracted — nothing more — so the candidate can
 * catch a hallucinated skill or invented project before it grounds a
 * question. This is the trust mechanism the spec's anti-hallucination
 * guidance calls for: showing the extraction, not just using it silently. */
function CandidateProfilePreview({ profile }: { profile: CandidateProfile }) {
  const hasAnything =
    profile.skills.length ||
    profile.projects.length ||
    profile.experience.length ||
    profile.education.length ||
    profile.technologies.length ||
    profile.achievements.length;

  return (
    <Card className="mt-3 bg-surface-muted">
      <p className="text-sm font-medium text-navy-900">Extracted from your resume</p>
      {!hasAnything && (
        <p className="mt-2 text-sm text-ink-600">
          Didn&apos;t find any of the usual resume sections in that file — the interview will
          fall back to generic questions for this category.
        </p>
      )}
      <div className="mt-2 space-y-2">
        <ProfileList label="Skills" items={profile.skills} />
        <ProfileList label="Projects" items={profile.projects} />
        <ProfileList label="Experience" items={profile.experience} />
        <ProfileList label="Technologies" items={profile.technologies} />
        <ProfileList label="Achievements" items={profile.achievements} />
        <ProfileList label="Education" items={profile.education} />
      </div>
      <p className="mt-3 text-xs text-ink-400">
        If something here is wrong, the interviewer may reference it — this is exactly what was
        pulled from the file, not what should have been.
      </p>
    </Card>
  );
}

function JobProfilePreview({ profile }: { profile: JobProfile }) {
  return (
    <Card className="mt-3 bg-surface-muted">
      <p className="text-sm font-medium text-navy-900">Extracted from the job description</p>
      <div className="mt-2 space-y-2 text-sm text-ink-900">
        {(profile.role || profile.company) && (
          <p>
            {profile.role}
            {profile.role && profile.company ? " at " : ""}
            {profile.company}
          </p>
        )}
        <ProfileList label="Required skills" items={profile.requiredSkills} />
        <ProfileList label="Preferred skills" items={profile.preferredSkills} />
        <ProfileList label="Responsibilities" items={profile.responsibilities} />
      </div>
    </Card>
  );
}

function categoryHint(interview: Interview): string {
  return interview.category.replace(/-/g, " ");
}

export function ResumeJdUpload({
  interview,
  onUpdated,
}: {
  interview: Interview;
  onUpdated: (interview: Interview) => void;
}) {
  const [isUploadingResume, setIsUploadingResume] = useState(false);
  const [resumeError, setResumeError] = useState<string | null>(null);
  const resumeInputRef = useRef<HTMLInputElement | null>(null);

  const [jdText, setJdText] = useState("");
  const [isUploadingJd, setIsUploadingJd] = useState(false);
  const [jdError, setJdError] = useState<string | null>(null);

  async function handleResumeChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setResumeError(null);
    setIsUploadingResume(true);
    try {
      await interviewsApi.uploadResume(interview.id, file);
      onUpdated(await interviewsApi.get(interview.id));
    } catch (err) {
      setResumeError(
        err instanceof ApiError ? err.message : "Couldn't process that resume. Try again."
      );
    } finally {
      setIsUploadingResume(false);
      if (resumeInputRef.current) resumeInputRef.current.value = "";
    }
  }

  async function handleJdSubmit() {
    if (!jdText.trim()) return;
    setJdError(null);
    setIsUploadingJd(true);
    try {
      await interviewsApi.uploadJobDescription(interview.id, { text: jdText.trim() });
      onUpdated(await interviewsApi.get(interview.id));
    } catch (err) {
      setJdError(
        err instanceof ApiError ? err.message : "Couldn't process that job description. Try again."
      );
    } finally {
      setIsUploadingJd(false);
    }
  }

  return (
    <Card className="mt-6">
      <p className="text-sm font-medium text-navy-900">Resume &amp; job description (optional)</p>
      <p className="mt-1 text-sm text-ink-600">
        Upload either one and the interviewer grounds questions in your actual background instead
        of generic {categoryHint(interview)} questions.
      </p>

      <div className="mt-4 flex flex-col gap-2">
        <label className="text-sm font-medium text-ink-900">Resume (PDF or .docx)</label>
        <input
          ref={resumeInputRef}
          type="file"
          accept=".pdf,.docx"
          onChange={handleResumeChange}
          disabled={isUploadingResume}
          className="text-sm text-ink-600 file:mr-3 file:rounded-md file:border file:border-surface-border file:bg-white file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-navy-900 hover:file:bg-surface-muted"
        />
        {isUploadingResume && <p className="text-sm text-ink-600">Extracting your resume…</p>}
        {resumeError && <p className="text-sm text-danger">{resumeError}</p>}
        {interview.candidateProfile && (
          <CandidateProfilePreview profile={interview.candidateProfile} />
        )}
      </div>

      <div className="mt-6 flex flex-col gap-2">
        <label htmlFor="jd-text" className="text-sm font-medium text-ink-900">
          Job description (paste text)
        </label>
        <textarea
          id="jd-text"
          value={jdText}
          onChange={(e) => setJdText(e.target.value)}
          rows={4}
          placeholder="Paste the job posting here..."
          disabled={isUploadingJd}
          className="rounded-md border border-surface-border px-3.5 py-2.5 text-sm text-ink-900 placeholder:text-ink-400 focus:border-accent"
        />
        <div>
          <Button
            type="button"
            variant="secondary"
            onClick={handleJdSubmit}
            isLoading={isUploadingJd}
            disabled={!jdText.trim()}
          >
            Add job description
          </Button>
        </div>
        {jdError && <p className="text-sm text-danger">{jdError}</p>}
        {interview.jobProfile && <JobProfilePreview profile={interview.jobProfile} />}
      </div>
    </Card>
  );
}
