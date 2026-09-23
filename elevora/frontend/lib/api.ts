import type {
  AnswerResult,
  AudioAnswerResult,
  CandidateProfile,
  ExitInterviewResult,
  Interview,
  InterviewConfig,
  InterviewProfile,
  InterviewProfileInput,
  InterviewReport,
  InterviewTurn,
  JobProfile,
  StartInterviewResult,
  User,
  WebcamMetrics,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: "include", // send/receive the HTTP-only session cookie
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (res.status === 204) {
    return undefined as T;
  }

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const body = isJson ? await res.json() : undefined;

  if (!res.ok) {
    const message =
      (body && typeof body.detail === "string" && body.detail) ||
      `Request failed with status ${res.status}`;
    throw new ApiError(message, res.status);
  }

  return body as T;
}

export const authApi = {
  register: (data: { name: string; email: string; password: string }) =>
    request<User>("/auth/register", { method: "POST", body: JSON.stringify(data) }),

  login: (data: { email: string; password: string }) =>
    request<User>("/auth/login", { method: "POST", body: JSON.stringify(data) }),

  logout: () => request<void>("/auth/logout", { method: "POST" }),

  me: () => request<User>("/auth/me"),
};

export const profilesApi = {
  list: () => request<InterviewProfile[]>("/interview-profiles"),

  get: (id: string) => request<InterviewProfile>(`/interview-profiles/${id}`),

  create: (data: InterviewProfileInput) =>
    request<InterviewProfile>("/interview-profiles", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  update: (id: string, data: Partial<InterviewProfileInput>) =>
    request<InterviewProfile>(`/interview-profiles/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  remove: (id: string) => request<void>(`/interview-profiles/${id}`, { method: "DELETE" }),
};

export const interviewsApi = {
  create: (data: InterviewConfig) =>
    request<Interview>("/interviews", { method: "POST", body: JSON.stringify(data) }),

  list: () => request<Interview[]>("/interviews"),

  get: (id: string) => request<Interview>(`/interviews/${id}`),

  remove: (id: string) => request<void>(`/interviews/${id}`, { method: "DELETE" }),

  start: (id: string) =>
    request<StartInterviewResult>(`/interviews/${id}/start`, { method: "POST" }),

  answer: (id: string, answer: string) =>
    request<AnswerResult>(`/interviews/${id}/answer`, {
      method: "POST",
      body: JSON.stringify({ answer }),
    }),

  turns: (id: string) => request<InterviewTurn[]>(`/interviews/${id}/turns`),

  exit: (id: string) => request<ExitInterviewResult>(`/interviews/${id}/exit`, { method: "POST" }),

  /** Not a fetch helper — the <audio> element or a manual fetch(..., {credentials:
   * "include"}) hits this directly, since it returns raw audio bytes, not JSON. */
  questionAudioUrl: (id: string) => `${API_URL}/interviews/${id}/question-audio`,

  answerAudio: async (id: string, blob: Blob, filename: string): Promise<AudioAnswerResult> => {
    const form = new FormData();
    form.append("audio_file", blob, filename);

    const res = await fetch(`${API_URL}/interviews/${id}/answer/audio`, {
      method: "POST",
      credentials: "include",
      // No Content-Type header here on purpose — the browser sets
      // multipart/form-data with the correct boundary itself. Setting it
      // manually (like the JSON request() helper does) breaks the upload.
      body: form,
    });

    const isJson = res.headers.get("content-type")?.includes("application/json");
    const body = isJson ? await res.json() : undefined;

    if (!res.ok) {
      const message =
        (body && typeof body.detail === "string" && body.detail) ||
        `Request failed with status ${res.status}`;
      throw new ApiError(message, res.status);
    }

    return body as AudioAnswerResult;
  },

  uploadResume: async (id: string, file: File): Promise<CandidateProfile> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_URL}/interviews/${id}/resume`, {
      method: "POST",
      credentials: "include",
      body: form,
    });
    const isJson = res.headers.get("content-type")?.includes("application/json");
    const body = isJson ? await res.json() : undefined;
    if (!res.ok) {
      const message =
        (body && typeof body.detail === "string" && body.detail) ||
        `Request failed with status ${res.status}`;
      throw new ApiError(message, res.status);
    }
    return (body as { candidateProfile: CandidateProfile }).candidateProfile;
  },

  uploadJobDescription: async (
    id: string,
    source: { text: string } | { file: File }
  ): Promise<JobProfile> => {
    const form = new FormData();
    if ("file" in source) {
      form.append("file", source.file);
    } else {
      form.append("text", source.text);
    }
    const res = await fetch(`${API_URL}/interviews/${id}/job-description`, {
      method: "POST",
      credentials: "include",
      body: form,
    });
    const isJson = res.headers.get("content-type")?.includes("application/json");
    const body = isJson ? await res.json() : undefined;
    if (!res.ok) {
      const message =
        (body && typeof body.detail === "string" && body.detail) ||
        `Request failed with status ${res.status}`;
      throw new ApiError(message, res.status);
    }
    return (body as { jobProfile: JobProfile }).jobProfile;
  },

  generateReport: (id: string) =>
    request<InterviewReport>(`/interviews/${id}/report`, { method: "POST" }),

  getReport: (id: string) => request<InterviewReport>(`/interviews/${id}/report`),

  submitWebcamMetrics: (id: string, metrics: WebcamMetrics) =>
    request<WebcamMetrics>(`/interviews/${id}/webcam-metrics`, {
      method: "POST",
      body: JSON.stringify(metrics),
    }),
};
