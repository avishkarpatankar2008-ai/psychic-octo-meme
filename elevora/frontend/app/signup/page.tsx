"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { Input } from "@/components/Input";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function SignupPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await register(name, email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-md flex-col justify-center px-6 py-16">
      <h1 className="text-2xl font-semibold text-navy-900">Create your account</h1>
      <p className="mt-2 text-sm text-ink-600">
        Set up interview practice in under a minute.
      </p>

      <Card className="mt-8">
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <Input
            label="Full name"
            name="name"
            autoComplete="name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
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
            autoComplete="new-password"
            minLength={8}
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <p className="-mt-3 text-xs text-ink-400">At least 8 characters.</p>

          {error && <p className="text-sm text-danger">{error}</p>}

          <Button type="submit" isLoading={isSubmitting}>
            Create account
          </Button>
        </form>
      </Card>

      <p className="mt-6 text-center text-sm text-ink-600">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-accent">
          Log in
        </Link>
      </p>
    </div>
  );
}
