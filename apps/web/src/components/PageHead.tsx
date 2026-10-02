import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { Glass } from "./Glass";

export function PageHead({ eyebrow, title, back, actions }: { eyebrow?: string; title: string; back?: string; actions?: ReactNode }) {
  return (
    <header className="page-head">
      <div style={{ minWidth: 0 }}>
        {back && (
          <Link to={back} className="back-link">
            <ChevronLeft size={18} aria-hidden="true" /> Back
          </Link>
        )}
        {eyebrow && <p className="page-head__eyebrow">{eyebrow}</p>}
        <h1 className="page-head__title">{title}</h1>
      </div>
      {actions && <div className="row">{actions}</div>}
    </header>
  );
}

export function IconButton({ label, onClick, children, disabled }: { label: string; onClick: () => void; children: ReactNode; disabled?: boolean }) {
  return (
    <Glass as="button" shape="pill" interactive className="button button--icon" onClick={onClick} aria-label={label} disabled={disabled}>
      {children}
    </Glass>
  );
}
