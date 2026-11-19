import json

from backend.main import PROJECT_ROOT, MemoryStore, create_app
from backend.rag import KnowledgeIndex, Passage, answer, build_index, references_for_warning


def index_of(*texts):
    return KnowledgeIndex([Passage(f"p{i}", "t.md", title, body) for i, (title, body) in enumerate(texts)])


def test_ranks_the_relevant_passage_first():
    index = index_of(("Lubrication", "Grease type and quantity affect bearing heat."),
                     ("Outer race", "Outer race damage sits in the housing and knocks repeat steadily."))
    assert index.search("outer race knocks")[0]["passage_id"] == "p1"


def test_unrelated_question_is_unanswered_not_guessed():
    result = answer(index_of(("Lubrication", "Grease quantity.")), "quarterly tax filing deadline")
    assert result["status"] == "no_relevant_source" and result["answer"] is None and result["citations"] == []


def test_equipment_model_filter_and_catalogue_requires_provenance(tmp_path, monkeypatch):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "repair_documents.json").write_text(json.dumps([
        {"id": "a", "source": "ACME manual p4", "title": "Pump seal", "text": "Replace seal kit", "equipment_models": ["P1"]},
        {"id": "b", "title": "No source", "text": "Replace seal kit"}]), encoding="utf-8")
    monkeypatch.setenv("AXON_RAG_DIRS", str(tmp_path / "none"))
    index = build_index(tmp_path)
    assert [h["passage_id"] for h in index.search("seal kit")] == ["a"]
    assert index.search("seal kit", equipment_model="P2") == []


def test_project_knowledge_grounds_a_fault_warning():
    refs = references_for_warning(build_index(PROJECT_ROOT), {"fault_class": "inner_race_damage"})
    assert refs and all(r["source"] for r in refs)
    assert any("inner race" in r["excerpt"].lower() for r in refs)


def test_endpoints():
    endpoints = {r.path: r.endpoint for r in create_app(store=MemoryStore()).routes if hasattr(r, "endpoint")}
    assert endpoints["/rag/ask"]("What should I check before replacing a bearing?", 3, None)["status"] == "answered"
    assert endpoints["/rag/search"]("lubrication grease", 4, None)["indexed_passages"] > 0
