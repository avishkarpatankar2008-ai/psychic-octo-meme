"use client";

import { Card } from "@/components/Card";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { useAuth } from "@/lib/auth-context";

function SettingsContent() {
  const { user } = useAuth();
  if (!user) return null;

  return (
    <div className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-2xl font-semibold text-navy-900">Settings</h1>

      <Card className="mt-6">
        <h2 className="text-sm font-medium text-ink-400">Account</h2>
        <dl className="mt-3 grid grid-cols-2 gap-4 text-sm">
          <div>
            <dt className="text-ink-400">Name</dt>
            <dd className="mt-1 text-ink-900">{user.name}</dd>
          </div>
          <div>
            <dt className="text-ink-400">Email</dt>
            <dd className="mt-1 text-ink-900">{user.email}</dd>
          </div>
          <div>
            <dt className="text-ink-400">Language</dt>
            <dd className="mt-1 text-ink-900">{user.preferences.language}</dd>
          </div>
          <div>
            <dt className="text-ink-400">Default difficulty</dt>
            <dd className="mt-1 capitalize text-ink-900">{user.preferences.defaultDifficulty}</dd>
          </div>
        </dl>
      </Card>

      <Card className="mt-6 bg-surface-muted">
        <p className="text-sm text-ink-600">
          Editing these preferences isn&apos;t wired up yet — Phase 1 only exposes registration data.
          A <code className="rounded bg-white px-1 py-0.5 text-xs">PATCH /users/me</code> endpoint
          and this form&apos;s submit handler are the two pieces to add when that becomes a priority.
        </p>
      </Card>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <ProtectedRoute>
      <SettingsContent />
    </ProtectedRoute>
  );
}
