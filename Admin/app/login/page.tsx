"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

export default function LoginPage() {
  const { login, forgotPassword, status, error } = useAuth();
  const router = useRouter();
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [resetMode, setResetMode] = useState(false);
  const [resetNotice, setResetNotice] = useState<string | null>(null);
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetCooldown, setResetCooldown] = useState(0);

  useEffect(() => {
    if (resetCooldown <= 0) return;
    const t = setTimeout(() => setResetCooldown((n) => n - 1), 1000);
    return () => clearTimeout(t);
  }, [resetCooldown]);

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setResetError(null);
    setResetNotice(null);
    setSubmitting(true);
    try {
      await forgotPassword(identifier);
      // Same message whether or not the address exists (no enumeration).
      setResetNotice("If an account exists for this email, a reset link is on its way.");
      setResetCooldown(60);
    } catch (err) {
      setResetError(err instanceof Error ? err.message : "Could not send the reset email.");
    }
    setSubmitting(false);
  };

  useEffect(() => {
    if (status === "authenticated") router.replace("/dashboard");
  }, [status, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    await login(identifier, password);
    setSubmitting(false);
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-primary-800 px-4">
      <div className="w-full max-w-sm rounded bg-white p-8 shadow-xl">
        <div className="mb-8 text-center">
          <p className="eyebrow text-secondary-600">Gawacha Bazaar</p>
          <h1 className="mt-1 font-display text-2xl font-semibold text-primary-900">
            Operations Control Center
          </h1>
        </div>

        {resetMode ? (
          <form onSubmit={handleReset} className="flex flex-col gap-4">
            <p className="text-sm text-neutral-600">Enter your staff email and we&apos;ll send a password reset link.</p>
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">Email</label>
              <input
                type="email"
                required
                autoComplete="username"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                className="w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
              />
            </div>
            {resetNotice && (
              <p className="rounded border border-primary-200 bg-primary-50 px-3 py-2 text-sm text-primary-800">{resetNotice}</p>
            )}
            {resetError && (
              <p className="rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">
                {resetError}
              </p>
            )}
            <button
              type="submit"
              disabled={submitting || resetCooldown > 0}
              className="mt-2 rounded bg-primary-800 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-700 disabled:opacity-60"
            >
              {submitting ? "Sending..." : resetCooldown > 0 ? `Resend in ${resetCooldown}s` : "Send reset link"}
            </button>
            <button
              type="button"
              onClick={() => setResetMode(false)}
              className="text-sm font-medium text-primary-700 hover:underline"
            >
              Back to sign in
            </button>
          </form>
        ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Email or phone
            </label>
            <input
              type="text"
              required
              autoComplete="username"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              className="w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Password
            </label>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-1 focus:ring-primary-500"
            />
          </div>

          {error && (
            <p className="rounded border border-status-danger/30 bg-status-dangerLight px-3 py-2 text-sm text-status-danger">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="mt-2 rounded bg-primary-800 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-700 disabled:opacity-60"
          >
            {submitting ? "Signing in..." : "Sign in"}
          </button>
          <button
            type="button"
            onClick={() => {
              setResetMode(true);
              setResetNotice(null);
              setResetError(null);
            }}
            className="text-sm font-medium text-primary-700 hover:underline"
          >
            Forgot password?
          </button>
        </form>
        )}

        <p className="mt-6 text-center text-xs text-neutral-400">
          Staff access only. Customer accounts cannot open this panel.
        </p>
      </div>
    </div>
  );
}
