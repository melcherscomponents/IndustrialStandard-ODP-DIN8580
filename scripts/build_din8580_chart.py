#!/usr/bin/env python3
"""Build a DIN8580 taxonomy JSON model from an OWL source."""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

DEFAULT_SOURCE = (
    "https://raw.githubusercontent.com/hsu-aut/"
    "IndustrialStandard-ODP-DIN8580/master/DIN8580.owl"
)
DEFAULT_OUT_JSON = "artifacts/din8580_full_taxonomy.json"

OWL_NS = "http://www.w3.org/2002/07/owl#"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"


@dataclass(frozen=True)
class NodeBase:
    id: str
    label: str
    raw_fragment: str
    level_number: str | None
    level_type: str | None


def is_url(value: str) -> bool:
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"}


def load_source(source: str) -> bytes:
    if is_url(source):
        try:
            with urllib.request.urlopen(source, timeout=30) as response:
                return response.read()
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, ssl.SSLCertVerificationError):
                insecure_ctx = ssl._create_unverified_context()
                try:
                    with urllib.request.urlopen(source, timeout=30, context=insecure_ctx) as response:
                        print(
                            "WARNING: SSL certificate verification failed; "
                            "retried download with an unverified SSL context.",
                            file=sys.stderr,
                        )
                        return response.read()
                except urllib.error.URLError as insecure_exc:
                    raise RuntimeError(
                        f"Failed to download source URL '{source}' after SSL fallback: {insecure_exc}"
                    ) from insecure_exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Failed to download source URL '{source}': {exc}") from exc

    source_path = Path(source)
    if not source_path.exists():
        raise RuntimeError(f"Source file does not exist: {source_path}")
    try:
        return source_path.read_bytes()
    except OSError as exc:
        raise RuntimeError(f"Failed to read source file '{source_path}': {exc}") from exc


def extract_fragment(iri: str) -> str:
    if "#" in iri:
        return iri.rsplit("#", 1)[1]
    return iri.rstrip("/").rsplit("/", 1)[-1]


def humanize_fragment(fragment: str) -> str:
    return fragment.replace("_", " ").strip()


def extract_level_metadata(comment: str) -> Tuple[str | None, str | None]:
    """Extract DIN level type + number from a comment like 'Untergruppe 5.1.2'."""
    normalized = " ".join((comment or "").split())
    if not normalized:
        return None, None

    pattern = re.compile(
        r"\b(Hauptgruppe|Gruppe|Untergruppe)\s*([0-9]+(?:\.[0-9]+)*)\b",
        flags=re.IGNORECASE,
    )
    match = pattern.search(normalized)
    if not match:
        return None, None

    raw_type = match.group(1).lower()
    if raw_type == "hauptgruppe":
        level_type = "Hauptgruppe"
    elif raw_type == "untergruppe":
        level_type = "Untergruppe"
    else:
        level_type = "Gruppe"
    return match.group(2), level_type


def parse_preferred_label(class_el: ET.Element, fallback_fragment: str) -> str:
    label_xpath = f"{{{RDFS_NS}}}label"
    for lbl in class_el.findall(label_xpath):
        lang = (lbl.attrib.get("{http://www.w3.org/XML/1998/namespace}lang") or "").lower()
        if lang == "de" and (lbl.text or "").strip():
            return (lbl.text or "").strip()

    for lbl in class_el.findall(label_xpath):
        if (lbl.text or "").strip():
            return (lbl.text or "").strip()

    return humanize_fragment(fallback_fragment)


def parse_owl(content: bytes) -> Tuple[Dict[str, NodeBase], List[Tuple[str, str]]]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise RuntimeError(f"Failed to parse OWL/XML content: {exc}") from exc

    class_xpath = f".//{{{OWL_NS}}}Class"
    subclass_xpath = f"{{{RDFS_NS}}}subClassOf"
    comment_xpath = f"{{{RDFS_NS}}}comment"
    resource_attr = f"{{{RDF_NS}}}resource"
    about_attr = f"{{{RDF_NS}}}about"

    nodes: Dict[str, NodeBase] = {}
    edges: List[Tuple[str, str]] = []

    for class_el in root.findall(class_xpath):
        class_iri = class_el.get(about_attr)
        if not class_iri:
            continue

        fragment = extract_fragment(class_iri)
        label = parse_preferred_label(class_el, fragment)
        comment_text = ""
        comment_el = class_el.find(comment_xpath)
        if comment_el is not None and comment_el.text:
            comment_text = comment_el.text
        level_number, level_type = extract_level_metadata(comment_text)
        nodes[class_iri] = NodeBase(
            id=class_iri,
            label=label,
            raw_fragment=fragment,
            level_number=level_number,
            level_type=level_type,
        )

        for sub_el in class_el.findall(subclass_xpath):
            parent_iri = sub_el.get(resource_attr)
            if parent_iri:
                edges.append((class_iri, parent_iri))

    valid_edges = [(child, parent) for child, parent in edges if child in nodes and parent in nodes]
    return nodes, valid_edges


def build_forest(nodes: Dict[str, NodeBase], edges: List[Tuple[str, str]]) -> Tuple[List[dict], Set[str], int]:
    children_by_parent: Dict[str, Set[str]] = defaultdict(set)
    parent_count: Dict[str, int] = defaultdict(int)

    for child, parent in edges:
        children_by_parent[parent].add(child)
        parent_count[child] += 1

    def level_to_tuple(level: str | None) -> Tuple[int, ...]:
        if not level:
            return (10**9,)
        try:
            return tuple(int(part) for part in level.split("."))
        except ValueError:
            return (10**9,)

    def node_sort_key(node_id: str) -> Tuple[Tuple[int, ...], str, str]:
        node = nodes[node_id]
        return (
            level_to_tuple(node.level_number),
            node.label.lower(),
            node.raw_fragment.lower(),
        )

    roots = sorted(
        [node_id for node_id in nodes if parent_count[node_id] == 0],
        key=node_sort_key,
    )

    if not roots:
        roots = sorted(nodes.keys(), key=node_sort_key)

    seen: Set[str] = set()

    def render(node_id: str, path: Set[str]) -> dict:
        if node_id in path:
            return {
                "id": nodes[node_id].id,
                "label": nodes[node_id].label,
                "raw_fragment": nodes[node_id].raw_fragment,
                "level_number": nodes[node_id].level_number,
                "level_type": nodes[node_id].level_type,
                "children": [],
                "cycle": True,
            }

        next_path = set(path)
        next_path.add(node_id)
        seen.add(node_id)

        children = sorted(
            children_by_parent.get(node_id, set()),
            key=node_sort_key,
        )

        return {
            "id": nodes[node_id].id,
            "label": nodes[node_id].label,
            "raw_fragment": nodes[node_id].raw_fragment,
            "level_number": nodes[node_id].level_number,
            "level_type": nodes[node_id].level_type,
            "children": [render(child_id, next_path) for child_id in children],
        }

    forest = [render(root_id, set()) for root_id in roots]
    return forest, seen, len(set(edges))


def run(source: str, out_json: str) -> None:
    content = load_source(source)
    nodes, edges = parse_owl(content)
    forest, seen, edge_count = build_forest(nodes, edges)

    all_nodes = set(nodes.keys())
    missing = sorted(all_nodes - seen)

    if missing:
        for node_id in missing:
            forest.append(
                {
                    "id": nodes[node_id].id,
                    "label": nodes[node_id].label,
                    "raw_fragment": nodes[node_id].raw_fragment,
                    "level_number": nodes[node_id].level_number,
                    "level_type": nodes[node_id].level_type,
                    "children": [],
                }
            )
            seen.add(node_id)

        def detached_sort_key(node: dict) -> Tuple[Tuple[int, ...], str, str]:
            num = node.get("level_number")
            return (level_to_tuple(num), node["label"].lower(), node["raw_fragment"].lower())

        forest.sort(key=detached_sort_key)

    payload = {
        "source": source,
        "node_count": len(nodes),
        "edge_count": edge_count,
        "roots": forest,
    }

    out_path = Path(out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    empty_labels = [node.raw_fragment for node in nodes.values() if not node.label]
    if empty_labels:
        raise RuntimeError("Found empty labels after normalization. Check input OWL fragments.")

    print(f"Wrote JSON: {out_path}")
    print(f"source={source}")
    print(f"node_count={len(nodes)}")
    print(f"edge_count={edge_count}")
    print(f"roots={len(payload['roots'])}")
    print(f"covered_nodes={len(seen)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build DIN8580 taxonomy JSON from OWL")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="OWL source URL or local path")
    parser.add_argument("--out-json", default=DEFAULT_OUT_JSON, help="Output JSON path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run(source=args.source, out_json=args.out_json)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
