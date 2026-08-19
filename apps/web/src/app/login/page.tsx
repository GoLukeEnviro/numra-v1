"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { NumericWheel } from "@/components/layout/numeric-wheel";
import { AlertTriangle } from "lucide-react";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        setError({ code: err.code, message: err.message });
      } else {
        setError({ code: "NETWORK_ERROR", message: "Could not reach the server." });
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="sacred-wheel-bg relative flex min-h-screen items-center justify-center overflow-hidden bg-background p-6">
      <NumericWheel className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 opacity-40" />
      <NumericWheel className="pointer-events-none absolute -bottom-32 -left-32 h-96 w-96 opacity-20" />
      <Card className="relative w-full max-w-sm">
        <CardHeader className="text-center">
          <div className="mb-3 flex justify-center">
            <NumericWheel className="h-12 w-12" />
          </div>
          <CardTitle className="text-2xl">Numra</CardTitle>
          <CardDescription>Sign in to your account</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} noValidate>
            <div className="mb-4">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="mb-5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {error && (
              <div
                role="alert"
                className="mb-4 flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-surface p-3 text-sm text-text"
              >
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden="true" />
                <span>
                  <span className="mr-1.5 rounded bg-black/20 px-1.5 py-0.5 font-mono text-xs">
                    {error.code}
                  </span>
                  {error.message}
                </span>
              </div>
            )}

            <Button type="submit" className="w-full" loading={submitting}>
              Sign in
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
