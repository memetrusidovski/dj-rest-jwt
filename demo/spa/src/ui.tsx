import { useState, type FormEvent, type ReactNode } from "react";
import type { ApiError, ApiResponse } from "dj-rest-jwt-client";

/** Runs an API call, tracking busy state and allauth's `errors` list. */
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<ApiError[]>([]);
  async function run<T>(fn: () => Promise<ApiResponse<T>>): Promise<ApiResponse<T> | null> {
    setBusy(true);
    setErrors([]);
    try {
      const res = await fn();
      if (res.errors?.length) setErrors(res.errors);
      return res;
    } catch (err) {
      setErrors([{ code: "client", message: err instanceof Error ? err.message : String(err) }]);
      return null;
    } finally {
      setBusy(false);
    }
  }
  return { busy, errors, setErrors, run };
}

export function Errors({ errors }: { errors: ApiError[] }) {
  if (!errors.length) return null;
  return (
    <ul className="errors" role="alert">
      {errors.map((e, i) => (
        <li key={i}>{e.param ? <strong>{e.param}: </strong> : null}{e.message ?? e.code}</li>
      ))}
    </ul>
  );
}

export function Form({ onSubmit, children }: { onSubmit: () => void; children: ReactNode }) {
  return (
    <form onSubmit={(e: FormEvent) => { e.preventDefault(); onSubmit(); }}>
      {children}
    </form>
  );
}

export function Field(props: {
  label: string; value: string; onChange: (v: string) => void;
  type?: string; autoComplete?: string; autoFocus?: boolean; placeholder?: string;
}) {
  return (
    <label className="field">
      <span>{props.label}</span>
      <input
        type={props.type ?? "text"}
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        autoComplete={props.autoComplete}
        autoFocus={props.autoFocus}
        placeholder={props.placeholder}
        required
      />
    </label>
  );
}

export function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="card">
      <h2>{title}</h2>
      {children}
    </section>
  );
}
