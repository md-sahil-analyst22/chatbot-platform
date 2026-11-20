// ────────────────────────────────────────────────────────────────────────────────────────────
// 📖 PLAIN-ENGLISH GUIDE TO THIS FILE
// What: A reusable form field: label, the input itself, an optional hint and an error message.
// ────────────────────────────────────────────────────────────────────────────────────────────
// From react — React, the library that draws the user interface: ReactNode = type for anything
//   React can draw.
import type { ReactNode } from "react";

// What a Field needs: label, optional hint/error, and the input inside it.
interface FieldProps {
  // The label text.
  label: string;
  // Optional help text ('?' = optional).
  hint?: string;
  // Optional error message.
  error?: string;
  // The input element(s) inside the field.
  children: ReactNode;
}

// Draws the label, input, hint and error in a consistent way.
export function Field({ label, hint, error, children }: FieldProps) {
  // Return:
  return (
    // A <label>, so clicking the text focuses the input.
    <label className="field">
      {/* The label text. */}
      <span className="field-label">{label}</span>
      {/* The input itself. */}
      {children}
      {/* The hint, only when there's a hint and no error. */}
      {hint && !error && <span className="field-hint">{hint}</span>}
      {/* The error, only when there is one: */}
      {error && (
        // shown in red; role='alert' makes screen readers announce it.
        <span className="field-error" role="alert">
          {/* The error text. */}
          {error}
        </span>
      )}
    </label>
  );
}
