# Retrieval-augmented grounding (RAG)

AXON retrieves cited passages from local documents to ground the repair agent and to answer maintenance questions. It is offline and deterministic: passages are ranked with BM25 in pure Python (`backend/rag.py`), with no model download and no network.

## Sources

- `knowledge/*.md`: maintenance guidance written for this project (not manufacturer documentation).
- `docs/*.md`: how AXON works.
- `config/repair_documents.json`: authorised repair documents. A record needs `source` and `text` (or `summary`); records without a source are not indexed. Optional `title`, `tags`, `equipment_models`.

Set `AXON_RAG_DIRS` (path-separated) to replace the markdown directories. The index is built at API start-up, so restart after editing documents.

## Use

- `GET /rag/search?query=...&k=4&equipment_model=` returns ranked passages with source and score.
- `GET /rag/ask?question=...` returns the best passage as an extractive answer with citations, or `no_relevant_source` when nothing matches. Nothing is generated that is not in a source.
- New repair proposals carry `references` (source, title, excerpt) chosen from the diagnosed fault class, shown beside the drafts. Retrieval failure never blocks a proposal.

## Limits

- Lexical matching: a question must share words with a passage. Synonyms are not understood.
- The answer is the top passage, not a synthesis. An LLM generation step can be added on top of `search`, as long as it cites passages and keeps the "no source, no answer" rule.
