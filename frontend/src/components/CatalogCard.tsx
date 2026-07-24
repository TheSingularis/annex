import type { ReactNode } from "react";
import type { StampTone } from "./StatusStamp";

interface CatalogCardProps {
  tone?: StampTone;
  compact?: boolean;
  selected?: boolean;
  onClick?: () => void;
  children: ReactNode;
  className?: string;
}

export function CatalogCard({ tone = "slate", compact, selected, onClick, children, className }: CatalogCardProps) {
  const classes = [
    "catalog-card",
    `catalog-card--${tone}`,
    compact && "catalog-card--compact",
    selected && "catalog-card--selected",
    onClick && "catalog-card--clickable",
    className,
  ].filter(Boolean).join(" ");

  return (
    <div className={classes} onClick={onClick}>
      {children}
    </div>
  );
}
