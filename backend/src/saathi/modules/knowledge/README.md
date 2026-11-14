# modules/knowledge

Owns: `source`, `chunk`, `faq`. Phase 2 (P2.1 - P2.16).

| Layer | Contents |
|---|---|
| domain | `Source` + status state machine (queued -> processing -> ready / failed) |
| application | ingestion use case (hash, re-sync), retrieval (hybrid search + RRF + rerank) |
| ports | `DocumentParser`, `Embedder`, `Reranker`, `ObjectStore`, `Crawler` interfaces |
| adapters | `parsers/` (PyMuPDF, Docling, XLSX), `embeddings/` (OpenAI, Cohere), `rerankers/` (Cohere), pgvector repo |
| api | `/api/v1/sources/upload`, `/sources/crawl`, `/faqs` |
| workers | ARQ jobs (`ingest_source`) - run in the worker process, never in the request |
