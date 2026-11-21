import type { ReactNode } from 'react';

export type TagFacet = 'specialty' | 'system' | 'presentation' | 'task' | 'modality' | 'setting' | 'competency' | 'difficulty' | 'level' | 'source';
export type ClinicalTag = { id: string; label: string; facet: TagFacet };

export function makeClinicalTag(facet: TagFacet, label: string): ClinicalTag {
  const slug = label.trim().toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  return { id: `${facet}.${slug}`, label: label.trim(), facet };
}

export function ClinicalTags({ tags, limit = 6, className = '' }: { tags: ClinicalTag[]; limit?: number; className?: string }) {
  const unique = tags.filter((tag, index, all) => tag.label && all.findIndex((item) => item.id === tag.id) === index).slice(0, limit);
  if (!unique.length) return null;
  return <div className={`clinical-tag-list ${className}`} aria-label="Shared clinical tags">{unique.map((tag) => <span key={tag.id} className={`clinical-tag clinical-tag-${tag.facet}`} title={`Shared index · ${tag.facet}`}>{tag.label}</span>)}</div>;
}

export function ClinicalTagGroup({ title, children }: { title: string; children: ReactNode }) {
  return <section className="clinical-tag-group"><div className="clinical-tag-group-title">{title}</div>{children}</section>;
}
