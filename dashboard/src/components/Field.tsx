// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: A reusable form field: label, the input itself, an optional hint and an error message.
// ────────────────────────────────────────────────────────────────────────────────────────────
// From react — React, the library that draws the user interface: ReactNode = type for anything
//   React can draw.
import type { ReactNode } from "react";

// What a Field needs: label, optional hint/error, and the input inside it.
interface FieldProps {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}

// Draws the label, input, hint and error in a consistent way.
export function Field({ label, hint, error, children }: FieldProps) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && !error && <span className="field-hint">{hint}</span>}
      {error && (
        <span className="field-error" role="alert">
          {error}
        </span>
      )}
    </label>
  );
}
