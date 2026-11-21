"""Fixture adapters: PheKB-shaped phenotype cases and competency reference graphs.

These functions normalize supplied artifacts to inert test fixtures. They never
create runtime clinical facts, competencies or learner assertions.
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from typing import Any

from .proforma import validate_plan


class FixtureImportError(ValueError):
    pass


def phekb_phenotype_to_proforma(phenotype: dict[str, Any]) -> dict[str, Any]:
    """Convert a curator-normalized PheKB phenotype definition to a PROforma plan.

    PheKB artifacts can be human-readable and implementation-specific; this
    adapter intentionally requires an explicit, reviewed mapping of each
    phenotype criterion to the HSPTL PROforma predicate subset.
    """
    if not isinstance(phenotype, dict):
        raise FixtureImportError("Phenotype fixture must be a JSON object.")
    phenotype_id = phenotype.get("phenotype_id") or phenotype.get("id")
    if not isinstance(phenotype_id, str) or not phenotype_id.strip():
        raise FixtureImportError("A stable phenotype_id is required.")
    criteria = phenotype.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        raise FixtureImportError("At least one normalized phenotype criterion is required.")
    combination = phenotype.get("combination", "all")
    if combination not in {"all", "any"}:
        raise FixtureImportError("Combination must be 'all' or 'any'.")

    tasks: list[dict[str, Any]] = []
    criterion_ids: list[str] = []
    for index, criterion in enumerate(criteria, start=1):
        if not isinstance(criterion, dict):
            raise FixtureImportError(f"Criterion {index} must be an object.")
        criterion_id = criterion.get("id")
        expression = criterion.get("expression") or criterion.get("predicate")
        if not isinstance(criterion_id, str) or not criterion_id.strip():
            raise FixtureImportError(f"Criterion {index} requires a stable id.")
        if not isinstance(expression, (dict, bool)):
            raise FixtureImportError(f"Criterion {criterion_id} requires a PROforma expression, not executable source code.")
        task_id = f"criterion-{criterion_id}"
        tasks.append({
            "id": task_id, "type": "decision", "prompt": criterion.get("label", criterion_id),
            "options": [
                {"id": "satisfied", "label": "Criterion satisfied", "when": expression},
                {"id": "not_satisfied", "label": "Criterion not satisfied", "when": {"op": "not", "args": [expression]}},
            ],
        })
        criterion_ids.append(task_id)

    refs = [{"op": "eq", "left": {"ref": f"answers.decision:{task_id}"}, "right": "satisfied"}
            for task_id in criterion_ids]
    aggregate = {"op": "and" if combination == "all" else "or", "args": refs}
    tasks.append({
        "id": "phenotype-eligibility", "type": "decision", "prompt": "Phenotype criteria result",
        "options": [
            {"id": "eligible", "label": "All configured criteria satisfy the reviewed phenotype definition" if combination == "all" else "At least one configured criterion satisfies the reviewed phenotype definition", "when": aggregate},
            {"id": "not_eligible", "label": "Phenotype criteria not satisfied", "when": {"op": "not", "args": [aggregate]}},
        ],
    })
    plan = {
        "id": f"phekb-fixture-{phenotype_id}", "type": "plan",
        "title": phenotype.get("title", f"PheKB-derived fixture: {phenotype_id}"),
        "metadata": {"fixture_only": True, "source_family": "PheKB", "source_ref": phenotype.get("source_ref"),
                     "mapping_review_required": True},
        "tasks": tasks,
    }
    validation = validate_plan(plan)
    if not validation["valid"]:
        raise FixtureImportError("Converted PROforma plan is invalid: " + "; ".join(validation["errors"]))
    return plan


def _jsonld_refs(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    refs: list[str] = []
    for item in values:
        if isinstance(item, str): refs.append(item)
        elif isinstance(item, dict):
            ref = item.get("@id") or item.get("id") or item.get("@value")
            if isinstance(ref, str): refs.append(ref)
    return refs


def cass_jsonld_to_reference_graph(document: dict[str, Any]) -> dict[str, Any]:
    """Normalize CaSS JSON-LD objects to a read-only competency reference graph."""
    if not isinstance(document, dict):
        raise FixtureImportError("CaSS input must be a JSON-LD object.")
    raw_nodes = document.get("@graph")
    if not isinstance(raw_nodes, list):
        raw_nodes = [document]
    nodes: dict[str, dict[str, Any]] = {}
    type_by_id: dict[str, str] = {}
    for item in raw_nodes:
        if not isinstance(item, dict): continue
        node_id = item.get("@id") or item.get("id")
        if not isinstance(node_id, str) or not node_id: continue
        types = item.get("@type", item.get("type", []))
        if isinstance(types, str): types = [types]
        types = [str(value) for value in types] if isinstance(types, list) else []
        normalized_type = "framework" if any("framework" in value.casefold() for value in types) else (
            "competency" if any("competency" in value.casefold() for value in types) else "reference")
        if normalized_type not in {"framework", "competency"}: continue
        name = item.get("name") or item.get("title") or item.get("prefLabel") or node_id
        if isinstance(name, dict): name = name.get("@value", name.get("value", node_id))
        nodes[node_id] = {"id": node_id, "kind": normalized_type, "label": str(name),
                          "description": str(item.get("description", "")),
                          "source": "CaSS JSON-LD"}
        type_by_id[node_id] = normalized_type

    edges: set[tuple[str, str, str]] = set()
    collection_keys = ("competencies", "hasCompetency", "hasTopChild", "hasChild", "children", "members", "hasMember")
    parent_keys = ("isChildOf", "broader", "parent", "parentCompetency")
    relation_keys = ("relations", "relation", "hasRelation")
    for item in raw_nodes:
        if not isinstance(item, dict): continue
        source = item.get("@id") or item.get("id")
        if source not in nodes: continue
        for key in collection_keys:
            for target in _jsonld_refs(item.get(key)):
                if target in nodes: edges.add((source, "contains" if type_by_id[source] == "framework" else "has_child", target))
        for key in parent_keys:
            for parent in _jsonld_refs(item.get(key)):
                if parent in nodes: edges.add((parent, "has_child", source))
        for key in relation_keys:
            rel_values = item.get(key, [])
            if not isinstance(rel_values, list): rel_values = [rel_values]
            for relation in rel_values:
                if not isinstance(relation, dict): continue
                target = relation.get("target") or relation.get("object") or relation.get("to")
                target_refs = _jsonld_refs(target)
                predicate = str(relation.get("predicate") or relation.get("relationType") or "related_to")
                for target_id in target_refs:
                    if target_id in nodes: edges.add((source, predicate, target_id))

    if not nodes:
        raise FixtureImportError("No CaSS Framework or Competency nodes were found in @graph.")
    return _reference_graph("CaSS JSON-LD", nodes, edges, document.get("@context"))


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def medbiquitous_xml_to_reference_graph(xml_text: str) -> dict[str, Any]:
    """Normalize the published MedBiquitous competency-framework XML subset.

    The MedBiquitous competency-framework XSD is identified as a draft by its
    publisher; this conservative importer handles explicit competency objects
    and references and emits warnings when source relations are absent.
    """
    if not isinstance(xml_text, str) or len(xml_text.encode("utf-8")) > 5_000_000:
        raise FixtureImportError("MedBiquitous XML must be text no larger than 5 MB.")
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", xml_text, re.IGNORECASE):
        raise FixtureImportError("DTD and entity declarations are not accepted in fixture XML.")
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise FixtureImportError(f"Invalid MedBiquitous XML: {exc}") from exc

    framework_name = root.attrib.get("name") or root.attrib.get("id") or _local_name(root.tag)
    nodes: dict[str, dict[str, Any]] = {"framework:root": {"id": "framework:root", "kind": "framework",
        "label": framework_name, "description": "", "source": "MedBiquitous Competency Framework XML"}}
    element_to_id: dict[int, str] = {}
    relation_edges: set[tuple[str, str, str]] = set()

    for element in root.iter():
        tag = _local_name(element.tag)
        if "competency" not in tag or "framework" in tag or "relationship" in tag or "relation" in tag:
            continue
        child_values = {_local_name(child.tag): (child.text or "").strip() for child in list(element)}
        identifier = (element.attrib.get("id") or child_values.get("id") or child_values.get("identifier")
                      or child_values.get("competencyid"))
        if not identifier:
            continue
        label = (child_values.get("title") or child_values.get("name") or child_values.get("description") or identifier)
        node_id = str(identifier)
        nodes[node_id] = {"id": node_id, "kind": "competency", "label": label,
                          "description": child_values.get("description", ""),
                          "source": "MedBiquitous Competency Framework XML"}
        element_to_id[id(element)] = node_id

    # Preserve explicit nested hierarchy where a competency element contains
    # another competency element; do not infer edges from document ordering.
    for parent in root.iter():
        parent_id = element_to_id.get(id(parent))
        if not parent_id: continue
        for child in parent.iter():
            if child is parent: continue
            child_id = element_to_id.get(id(child))
            if child_id and child_id != parent_id:
                relation_edges.add((parent_id, "has_child", child_id))

    # Explicit reference attributes and relation elements are also preserved.
    for element in root.iter():
        source = element_to_id.get(id(element))
        if not source: continue
        for child in list(element):
            tag = _local_name(child.tag)
            target = child.attrib.get("ref") or child.attrib.get("target") or (child.text or "").strip()
            if target in nodes and ("parent" in tag or "child" in tag or "relation" in tag):
                relation_edges.add((source, "related_to", target))

    if len(nodes) == 1:
        raise FixtureImportError("No MedBiquitous competency objects were identified.")
    for node_id in nodes:
        if node_id != "framework:root" and not any(edge[2] == node_id for edge in relation_edges):
            relation_edges.add(("framework:root", "contains", node_id))
    graph = _reference_graph("MedBiquitous XML", nodes, relation_edges, None)
    graph["warnings"] = ["Source XSD is documented as draft; verify the source schema revision and mapped relations before adoption."]
    return graph


def _reference_graph(source: str, nodes: dict[str, dict[str, Any]],
                     edges: set[tuple[str, str, str]], context: Any) -> dict[str, Any]:
    sorted_nodes = [nodes[key] for key in sorted(nodes)]
    sorted_edges = [{"source": src, "predicate": predicate, "target": target}
                    for src, predicate, target in sorted(edges)]
    body = {"schema": "hsptl.reference-graph/1.0", "fixture_only": True,
            "source_format": source, "context": context,
            "nodes": sorted_nodes, "edges": sorted_edges}
    body["content_hash"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    return body
