"""Offline retrieval-augmented grounding for AXON.

AXON runs on small-factory hardware with no guaranteed internet, so retrieval is
local and deterministic: documents are split into heading-scoped passages and
ranked with BM25 (pure Python, no model download). Every passage carries its
source so the owner or technician can see where a statement came from. When
nothing relevant is found the answer says so instead of guessing.

Sources (all optional):
  * ``knowledge/*.md``            maintenance guidance written for this project
  * ``docs/*.md``                 how AXON itself works
  * ``config/repair_documents.json``  authorised repair documents (provenance required)
Set ``AXON_RAG_DIRS`` (``os.pathsep``-separated) to replace the markdown directories.
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset("a an and are as at be by for from has have in is it its of on or that the this to was with will not no do does".split())
MAX_PASSAGE_WORDS = 160
MIN_SCORE = 0.1   # absolute floor; BM25 scores shrink on small corpora
MIN_COVERAGE = 0.5  # share of distinct query terms a passage must contain


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


@dataclass(frozen=True)
class Passage:
    passage_id: str
    source: str
    title: str
    text: str
    tags: tuple[str, ...] = ()
    equipment_models: tuple[str, ...] = ()
    terms: Counter = field(default_factory=Counter, compare=False, repr=False)

    def public(self, score: float | None = None) -> dict:
        data = {"passage_id": self.passage_id, "source": self.source, "title": self.title, "text": self.text}
        if self.tags: data["tags"] = list(self.tags)
        if score is not None: data["score"] = round(score, 3)
        return data


def _split_markdown(path: Path, root: Path) -> list[Passage]:
    """Split on headings, then cap each passage at MAX_PASSAGE_WORDS."""
    source = path.relative_to(root).as_posix() if path.is_relative_to(root) else path.name
    title, buffer, sections = path.stem, [], []
    heading = title
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#{1,4}\s+(.*)", line)
        if match:
            if buffer: sections.append((heading, buffer))
            heading, buffer = match.group(1).strip(), []
        else:
            buffer.append(line)
    if buffer: sections.append((heading, buffer))
    passages = []
    for heading, lines in sections:
        paragraphs = [p.strip() for p in "\n".join(lines).split("\n\n") if p.strip()]
        chunk: list[str] = []
        for paragraph in paragraphs + [None]:
            words = sum(len(p.split()) for p in chunk)
            if chunk and (paragraph is None or words + len(paragraph.split()) > MAX_PASSAGE_WORDS):
                body = "\n\n".join(chunk)
                passages.append(Passage(f"{source}#{len(passages)}", source, heading, body))
                chunk = []
            if paragraph is not None: chunk.append(paragraph)
    return passages


def _catalogue_passages(path: Path) -> list[Passage]:
    """Authorised repair documents. Records without provenance are not indexed."""
    if not path.is_file(): return []
    out = []
    for position, record in enumerate(json.loads(path.read_text(encoding="utf-8"))):
        if not isinstance(record, dict) or not record.get("source"): continue
        text = record.get("text") or record.get("summary") or ""
        if not text: continue
        out.append(Passage(record.get("id") or f"catalogue#{position}", record["source"], record.get("title", "Repair document"), text,
                           tuple(record.get("tags", [])), tuple(record.get("equipment_models", []))))
    return out


class KnowledgeIndex:
    """In-memory BM25 index over passages."""

    def __init__(self, passages: list[Passage], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.passages = [Passage(p.passage_id, p.source, p.title, p.text, p.tags, p.equipment_models,
                                 Counter(tokenize(f"{p.title} {p.title} {' '.join(p.tags)} {p.text}"))) for p in passages]
        self.lengths = [sum(p.terms.values()) for p in self.passages]
        self.average = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        frequency: Counter = Counter()
        for p in self.passages: frequency.update(p.terms.keys())
        n = len(self.passages)
        self.idf = {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in frequency.items()}

    def __len__(self) -> int: return len(self.passages)

    def search(self, query: str, k: int = 4, equipment_model: str | None = None, min_score: float = MIN_SCORE) -> list[dict]:
        terms = list(dict.fromkeys(tokenize(query)))
        if not terms or not self.passages: return []
        scored = []
        for passage, length in zip(self.passages, self.lengths):
            if equipment_model and passage.equipment_models and equipment_model not in passage.equipment_models: continue
            if sum(1 for t in terms if t in passage.terms) / len(terms) < MIN_COVERAGE: continue
            score = 0.0
            for term in terms:
                tf = passage.terms.get(term)
                if not tf: continue
                score += self.idf[term] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * length / (self.average or 1)))
            if score >= min_score: scored.append((score, passage))
        scored.sort(key=lambda item: (-item[0], item[1].passage_id))
        return [p.public(s) for s, p in scored[:k]]


def build_index(root: Path) -> KnowledgeIndex:
    configured = os.getenv("AXON_RAG_DIRS")
    directories = [Path(d) for d in configured.split(os.pathsep) if d] if configured else [root / "knowledge", root / "docs"]
    passages: list[Passage] = []
    for directory in directories:
        if directory.is_dir():
            for path in sorted(directory.rglob("*.md")): passages.extend(_split_markdown(path, root))
    passages.extend(_catalogue_passages(root / "config" / "repair_documents.json"))
    return KnowledgeIndex(passages)


def answer(index: KnowledgeIndex, question: str, k: int = 3, equipment_model: str | None = None) -> dict:
    """Extractive, cited answer. No text is generated that is not in a source."""
    hits = index.search(question, k, equipment_model)
    if not hits:
        return {"status": "no_relevant_source", "answer": None, "citations": [],
                "reason": "No indexed document answers this. Ask the technician or add an authorised document."}
    return {"status": "answered", "answer": hits[0]["text"], "citations": hits}


# Maps the diagnosis taxonomy to a retrieval query for the repair agent.
_FAULT_QUERIES = {
    "inner_race_damage": "bearing inner race damage inspection replacement",
    "outer_race_damage": "bearing outer race damage inspection replacement",
    "rolling_element_damage": "bearing rolling element ball damage inspection replacement",
}


def references_for_warning(index: KnowledgeIndex, assessment: dict, k: int = 3) -> list[dict]:
    query = _FAULT_QUERIES.get(assessment.get("fault_class"), "bearing vibration warning inspection checks before replacement")
    return [{"passage_id": h["passage_id"], "source": h["source"], "title": h["title"], "excerpt": h["text"][:400]}
            for h in index.search(query, k)]
