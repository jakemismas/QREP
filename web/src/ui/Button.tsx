/**
 * Button primitive (S2). Primary = terracotta CTA; secondary = bordered
 * card. Visual styling lives in tokens.css (.q-btn[data-variant]).
 */
import type { ReactNode } from "react";

interface ButtonProps {
  variant?: "primary" | "secondary";
  disabled?: boolean;
  onClick?: () => void;
  children: ReactNode;
  type?: "button" | "submit" | "reset";
  "data-testid"?: string;
}

export function Button({
  variant = "primary",
  disabled,
  onClick,
  children,
  type = "button",
  "data-testid": testId,
}: ButtonProps) {
  return (
    <button
      type={type}
      className="q-btn"
      data-variant={variant}
      disabled={disabled}
      onClick={onClick}
      data-testid={testId}
    >
      {children}
    </button>
  );
}
