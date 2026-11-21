import { api } from './api';
import type { SharedClinicalTag, TaggedContentItem } from './api';
import type { TagFacet } from '../components/ClinicalTags';

let catalogueCache: SharedClinicalTag[] | null = null;
let cataloguePromise: Promise<SharedClinicalTag[]> | null = null;
const indexedContent = new Map<string, string>();

async function getCatalogue(): Promise<SharedClinicalTag[]> {
  if (catalogueCache) return catalogueCache;
  if (!cataloguePromise) cataloguePromise = api.tagCatalogue().then((result) => result.tags);
  const catalogue = await cataloguePromise;
  catalogueCache = catalogue;
  return catalogue;
}

export async function resolveTagIds(pairs: Array<[TagFacet, string]>): Promise<string[]> {
  const catalogue = await getCatalogue();
  const ids: string[] = [];
  for (const [facet, label] of pairs) {
    const normal = label.trim().toLowerCase();
    if (!normal) continue;
    const match = catalogue.find((tag) => tag.facet === facet &&
      (tag.label.toLowerCase() === normal || (tag.aliases || []).some((alias) => alias.toLowerCase() === normal)));
    if (match && !ids.includes(match.tag_id)) ids.push(match.tag_id);
  }
  return ids;
}

export async function indexClinicalContent(payload: {
  content_type: string; content_id: string; title: string; workspace: string;
  summary?: string; source_status?: string; content_url?: string;
  tag_pairs: Array<[TagFacet, string]>;
}): Promise<TaggedContentItem | null> {
  try {
    const tags = await resolveTagIds(payload.tag_pairs);
    if (!tags.length) return null;
    const indexed = await api.registerTaggedContent({
      content_type: payload.content_type,
      content_id: payload.content_id,
      title: payload.title,
      workspace: payload.workspace,
      summary: payload.summary || '',
      source_status: payload.source_status || 'unreviewed',
      content_url: payload.content_url || '',
      tags,
      assigned_by: 'hsptl-indexer',
    });
    indexedContent.set(`${payload.content_type}:${payload.content_id}`, indexed.item_id);
    return indexed;
  } catch {
    // Tag indexing is additive; it must never break the core case, exam or OSCE workflow.
    return null;
  }
}


export async function recordIndexedLearningEvent(
  contentType: string,
  contentId: string,
  payload: { action: 'opened' | 'attempted' | 'completed' | 'reviewed' | 'revisited'; score?: number; max_score?: number; confidence?: 'low' | 'medium' | 'high' | '' },
): Promise<void> {
  const itemId = indexedContent.get(`${contentType}:${contentId}`);
  if (!itemId) return;
  try { await api.recordTagEvent(itemId, payload); } catch { /* performance telemetry is additive */ }
}
