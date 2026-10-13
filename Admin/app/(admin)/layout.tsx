"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { PageLoader } from "@/components/Spinner";
import { AdminShell } from "@/components/AdminShell";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") router.replace("/login");
  }, [status, router]);

  if (status !== "authenticated") {
    return (
      <PageLoader fullScreen label={status === "unauthenticated" ? "Redirecting to sign in..." : "Signing you in..."} />
    );
  }

  return <AdminShell>{children}</AdminShell>;
}
