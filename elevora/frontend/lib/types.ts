export interface UserPreferences {
  language: string;
  defaultDifficulty: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  createdAt: string;
  preferences: UserPreferences;
}

export type InterviewCategory =
  | "campus-placement"
  | "software-engineer"
  | "mechanical-engineer"
  | "hr"
  | "mba"
  | "upsc"
  | "mpsc"
  | "ssc"
  | "banking"
  | "company-specific"
  | "other";

export type InterviewDifficulty = "easy" | "medium" | "hard";
export type InterviewStatus = "draft" | "in_progress" | "completed" | "abandoned";

export interface InterviewConfig {
  // Phase 8: either category or profileId is required (profileId is the
  // preferred path — see InterviewProfile below). category stays a plain
  // string so it can also carry a custom profile's own category.
  category?: string;
  profileId?: string;
  role?: string;
  company?: string;
  exam?: string;
  industry?: string;
  experienceLevel?: string;
  difficulty: InterviewDifficulty;
  language: string;
  durationMinutes: number;
}

// ---- Phase 8: Interview Profiles -----------------------------------------

export type ProfileDifficulty = "easy" | "medium" | "hard" | "adaptive";

export interface InterviewProfile {
  id: string;
  name: string;
  description: string;
  category: string;
  subjects: string[];
  questionTypes: string[];
  interviewerStyle: string;
  difficulty: ProfileDifficulty;
  maxQuestions: number;
  followUpEnabled: boolean;
  adaptiveDifficulty: boolean;
  resumeGrounding: boolean;
  jdGrounding: boolean;
  isActive: boolean;
  isSystem: boolean;
  createdBy?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface InterviewProfileInput {
  name: string;
  description?: string;
  category: string;
  subjects: string[];
  questionTypes: string[];
  interviewerStyle?: string;
  difficulty?: ProfileDifficulty;
  maxQuestions?: number;
  followUpEnabled?: boolean;
  adaptiveDifficulty?: boolean;
  resumeGrounding?: boolean;
  jdGrounding?: boolean;
}

export interface PendingQuestion {
  question: string;
  topic: string;
  difficulty: number;
  isFollowUp: boolean;
}

export interface CandidateProfile {
  skills: string[];
  education: string[];
  experience: string[];
  projects: string[];
  technologies: string[];
  achievements: string[];
  claims: string[];
}

export interface JobProfile {
  role?: string;
  company?: string;
  industry?: string;
  requiredSkills: string[];
  preferredSkills: string[];
  responsibilities: string[];
  seniority?: string;
}

export interface Interview extends InterviewConfig {
  id: string;
  userId: string;
  category: string;
  status: InterviewStatus;
  createdAt: string;
  updatedAt: string;
  // Phase 2 — present once an interview has been started.
  questionNumber: number;
  maxQuestions?: number;
  difficultyLevel?: number;
  currentTopic?: string;
  pendingQuestion?: PendingQuestion;
  // Phase 4 — used by the interview-room timer.
  startedAt?: string;
  // Phase 5 — present once a resume/JD has been uploaded.
  candidateProfile?: CandidateProfile;
  jobProfile?: JobProfile;
}

export interface ExitInterviewResult {
  status: InterviewStatus;
  questionNumber: number;
}

export interface WebcamMetrics {
  faceVisibleRate: number;
  lookingAwayRate: number;
  movementRate: number;
  sampledFrames: number;
}

export type Confidence = "low" | "medium" | "high";

export interface DimensionScore {
  score: number | null;
  evidence: string;
}

export interface InterviewReport {
  interviewId: string;
  overallScore: number;
  categoryScores: Record<string, number>;
  dimensions: Record<string, DimensionScore>;
  strengths: string[];
  weaknesses: string[];
  recommendedPractice: string[];
  improvedAnswer?: string;
  confidence: Confidence;
  generatedAt: string;
}

export const DIMENSION_LABELS: Record<string, string> = {
  knowledge: "Knowledge",
  communication: "Communication",
  relevance: "Relevance",
  problemSolving: "Problem solving",
  interviewHandling: "Interview handling",
  delivery: "Delivery",
  webcam: "Webcam",
};

export const DIMENSION_ORDER = [
  "knowledge",
  "communication",
  "relevance",
  "problemSolving",
  "interviewHandling",
  "delivery",
  "webcam",
];

export interface AnswerAnalysis {
  quality: number;
  strengths: string[];
  weaknesses: string[];
  isRelevant: boolean;
  hasContradiction: boolean;
  followUpNeeded: boolean;
  followUpReason?: string;
  missingEvidence?: string;
}

export interface StartInterviewResult {
  status: InterviewStatus;
  questionNumber: number;
  maxQuestions: number;
  difficultyLevel: number;
  pendingQuestion: PendingQuestion;
}

export interface AnswerResult {
  status: InterviewStatus;
  questionNumber: number;
  maxQuestions: number;
  difficultyLevel: number;
  pendingQuestion?: PendingQuestion;
  lastEvaluation: AnswerAnalysis;
}

export interface AudioAnswerResult extends AnswerResult {
  transcript: string;
}

export interface InterviewTurn {
  sequence: number;
  question: string;
  answer: string;
  topic: string;
  difficulty: number;
  isFollowUp: boolean;
  createdAt: string;
}

export const INTERVIEW_CATEGORIES: { value: InterviewCategory; label: string }[] = [
  { value: "campus-placement", label: "Campus placement" },
  { value: "software-engineer", label: "Software engineer" },
  { value: "mechanical-engineer", label: "Mechanical engineer" },
  { value: "hr", label: "HR / behavioral" },
  { value: "mba", label: "MBA admissions" },
  { value: "upsc", label: "UPSC" },
  { value: "mpsc", label: "MPSC" },
  { value: "ssc", label: "SSC" },
  { value: "banking", label: "Banking" },
  { value: "company-specific", label: "Company-specific" },
  { value: "other", label: "Other" },
];
