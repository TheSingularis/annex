import type { ButtonHTMLAttributes } from "react";

type ButtonVariant = "primary" | "secondary" | "success" | "danger";
type ButtonSize = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export function Button({ variant = "secondary", size = "md", className, ...rest }: ButtonProps) {
  const classes = ["btn", `btn--${variant}`, size === "sm" && "btn--sm", className].filter(Boolean).join(" ");
  return <button className={classes} {...rest} />;
}
