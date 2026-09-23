"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Input } from "@/components/Input";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-md flex-col justify-center px-6 py-16">
      <h1 className="text-2xl font-semibold text-navy-900">Log in</h1>
      <p className="mt-2 text-sm text-ink-600">Pick up where you left off.</p>

      <Card className="mt-8">
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <Input
            label="Email"
            name="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Input
            label="Password"
            name="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />

          {error && <p className="text-sm text-danger">{error}</p>}

          <Button type="submit" isLoading={isSubmitting}>
            Log in
          </Button>
        </form>
      </Card>

      <p className="mt-6 text-center text-sm text-ink-600">
        New to Elevora?{" "}
        <Link href="/signup" className="font-medium text-accent">
          Create an account
        </Link>
      </p>
    </div>
  );
}
