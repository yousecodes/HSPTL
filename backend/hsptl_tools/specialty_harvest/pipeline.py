"""Clinical knowledge harvesting pipeline and local staging orchestration."""
from __future__ import annotations
from . import engine as _engine

ExamCuratedSource = getattr(_engine, 'ExamCuratedSource')
ExamTitleSource = getattr(_engine, 'ExamTitleSource')
FetchError = getattr(_engine, 'FetchError')
IMPORTANCE_PATTERNS = getattr(_engine, 'IMPORTANCE_PATTERNS')
JournalSource = getattr(_engine, 'JournalSource')
SOURCES = getattr(_engine, 'SOURCES')
SPECIALTIES = getattr(_engine, 'SPECIALTIES')
ThreadPoolExecutor = getattr(_engine, 'ThreadPoolExecutor')
_build_exam_jats = getattr(_engine, '_build_exam_jats')
as_completed = getattr(_engine, 'as_completed')
download_candidate = getattr(_engine, 'download_candidate')
download_pmc_batch = getattr(_engine, 'download_pmc_batch')
extract_jats_license = getattr(_engine, 'extract_jats_license')
hydrate_candidates = getattr(_engine, 'hydrate_candidates')
is_valid_specialty_case = getattr(_engine, 'is_valid_specialty_case')
json = getattr(_engine, 'json')
re = getattr(_engine, 're')

def existing_ids(out):
    return {p.parent.name: p.parent.parent.name for p in out.glob("*/article.xml")}

def _importance_score(case):
    """Return (score, list-of-matched-patterns) for a Candidate."""
    title = (case.title or "").lower()
    abstract = (case.abstract or "").lower()
    blob = title + " " + abstract
    score = 0
    hits = []
    for pattern, weight in IMPORTANCE_PATTERNS:
        if re.search(pattern, blob, re.I):
            score += weight
            hits.append(pattern)
    for m in re.finditer(r"\b([1-9][0-9]?)[- ]year[- ]old\b", title):
        age = int(m.group(1))
        if age < 18 or age > 80:
            score += 1
            hits.append("age:" + str(age))
            break
    return score, hits

def _has_exam_signal(title):
    """True if title contains an exam-style cue."""
    if not title:
        return False
    blob = title.lower()
    for cue in ExamTitleSource.TITLE_CUES:
        if cue in blob:
            return True
    return False

def harvest_specialty(key, args, out, claimed):
    name = SPECIALTIES[key][0]
    folder = out / key
    folder.mkdir(parents=True, exist_ok=True)

    print("  sources: " + ", ".join(args.sources))
    raw = []
    with ThreadPoolExecutor(max_workers=len(args.sources)) as ex:
        futs = {}
        for sn in args.sources:
            if sn == "exam":
                src = ExamCuratedSource(getattr(args, "exam_max", 40))
            elif sn == "journals":
                src = JournalSource(args.journals, args.journal_workers)
            else:
                src = SOURCES[sn]
            futs[ex.submit(_parallel_search, sn, src, key, args)] = sn
        for f in as_completed(futs):
            sn, cands = f.result()
            print("  [" + sn + "] " + str(len(cands)) + " raw")
            raw.extend(cands)

    ready = [c for c in raw if (c.title and (c.pmcid or c.doi or c.pmid)) or c.source.startswith("exam:")]
    need = [c for c in raw if not (c.title and (c.pmcid or c.doi or c.pmid)) and not c.source.startswith("exam:")]
    hydrated = ready + hydrate_candidates(need)
    print("  hydrated: " + str(len(hydrated)) + " total")
    seen = {}
    skipped = 0
    for c in hydrated:
        dk = c.dedup_key()
        if dk in seen:
            existing = seen[dk]
            if c.source.startswith("exam:") and not existing.source.startswith("exam:"):
                seen[dk] = c
            continue
        if c.source.startswith("journals:"):
            jmode = getattr(args, "journal_mode", "all")
            if jmode == "exam-only":
                if not _has_exam_signal(c.title):
                    skipped += 1
                    continue
            elif jmode == "important":
                jscore, _jhits = _importance_score(c)
                jmin = getattr(args, "journal_min_score", 2)
                if jscore < jmin:
                    skipped += 1
                    continue
        if not is_valid_specialty_case(c.title, key, c.abstract, c.source):
            skipped += 1
            continue
        if getattr(args, "knowledge_profile", "case_reports") != "case_reports":
            pub = (c.publication_type or "").lower()
            if "guideline" in pub: c.content_type = "guideline"
            elif "systematic review" in pub or "meta-analysis" in pub: c.content_type = "systematic_review"
            elif "clinical trial" in pub or "randomized controlled trial" in pub: c.content_type = "trial"
            elif any(x in pub for x in ("observational", "cohort", "case-control", "diagnostic test")): c.content_type = "observational_study"
            elif "case report" in pub: c.content_type = "case_report"
            else: c.content_type = "other"
        seen[dk] = c
        if args.per_specialty and len(seen) >= args.per_specialty:
            break
    chosen = list(seen.values())

    todo = [c for c in chosen if not (folder / (c.folder_name() or "x") / "article.xml").exists()]
    exam_todo = [c for c in todo if c.source.startswith("exam:")]
    pmc_todo = [c for c in todo if c.pmcid]
    doi_todo = [c for c in todo if not c.pmcid and c.doi]
    print("  " + name + ": " + str(len(chosen)) + " valid (" + str(skipped) +
          " filtered), " + str(len(todo)) + " to download (" +
          str(len(exam_todo)) + " exam, " + str(len(pmc_todo)) + " PMC, " +
          str(len(doi_todo)) + " DOI)")

    ok = failed = 0
    for c in exam_todo:
        try:
            d = folder / c.folder_name()
            d.mkdir(parents=True, exist_ok=True)
            (d / "article.xml").write_bytes(_build_exam_jats(c))
            rights = extract_jats_license((d / "article.xml").read_bytes())
            (d / "meta.json").write_text(json.dumps({
                "pmcid": "", "doi": "", "title": c.title,
                "abstractText": c.abstract, "year": c.year,
                "journal": c.journal, "discovered_via": c.source,
                "jats_source": "exam", **rights,
                "review_status": "harvested_unreviewed"}, ensure_ascii=False))
            ok += 1
        except Exception as e:
            failed += 1
            print("    ! exam " + (c.title or "")[:40] + ": " + str(e))

    if pmc_todo:
        b_ok, b_fail, _ = download_pmc_batch(pmc_todo, folder, args, args.batch_size)
        ok += b_ok
        failed += b_fail
        for c in pmc_todo:
            if c.pmid and not (folder / (c.folder_name() or "x") / "article.xml").exists() and not (folder / (c.folder_name() or "x") / "meta.json").exists():
                _write_metadata_record(c, folder)
    if doi_todo:
        doi_total = len(doi_todo)
        doi_ok = 0
        doi_errs = []
        print("    [doi] downloading " + str(doi_total) + " DOIs (" +
              (args.unpaywall_email or "NO UNPAYWALL EMAIL SET") + ")", flush=True)
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(download_candidate, c, folder, args.delay,
                          not args.no_pmc_fallback, not args.no_convert,
                          args.unpaywall_email): c for c in doi_todo}
            for i, f in enumerate(as_completed(futs), 1):
                c = futs[f]
                try:
                    f.result()
                    ok += 1
                    doi_ok += 1
                except Exception as e:
                    if c.pmid:
                        _write_metadata_record(c, folder)
                    else:
                        failed += 1
                        doi_errs.append(c.doi + ": " + str(e)[:60])
                if i % 100 == 0 or i == doi_total:
                    print("    [doi] " + str(i) + "/" + str(doi_total) +
                          " ok=" + str(doi_ok) + " failed=" +
                          str(len(doi_errs)), flush=True)
        for e in doi_errs[:3]:
            print("    ! doi " + e, flush=True)
    
    metadata_only = [c for c in todo if c.pmid and not c.pmcid and not c.doi]
    for c in metadata_only:
        _write_metadata_record(c, folder)

    return len(chosen), failed

def _write_metadata_record(candidate, folder):
    """Persist a clearly labelled metadata/abstract record when full text is unavailable."""
    import json
    target = folder / (candidate.folder_name() or "metadata_record")
    target.mkdir(parents=True, exist_ok=True)
    metadata = {"pmid": candidate.pmid, "pmcid": candidate.pmcid, "doi": candidate.doi,
        "title": candidate.title, "abstractText": candidate.abstract, "year": candidate.year,
        "journal": candidate.journal, "publication_type": candidate.publication_type,
        "content_type": candidate.content_type, "knowledge_profile": candidate.knowledge_profile,
        "discovered_via": candidate.source, "jats_source": "metadata_only",
        "license_status": "provider_metadata_requires_verification" if candidate.license_uri else "not_assessed_metadata_only",
        "license_uri": candidate.license_uri, "provider_license_uri": candidate.license_uri,
        "review_status": "harvested_unreviewed", "full_text_available": False}
    (target / "meta.json").write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")

def _parallel_search(name, src, key, args):
    out = []
    try:
        for c in src.search(key, args):
            out.append(c)
    except FetchError as e:
        print("  [" + name + "] FAILED: " + str(e), flush=True)
    except Exception as e:
        print("  [" + name + "] ERROR: " + type(e).__name__ + ": " + str(e), flush=True)
    return name, out

