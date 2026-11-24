"""Answer-level evaluation: runs the real /ask pipeline (retrieval + local LLM + response contract) on every
question in evaluation/dataset.json and grades the ANSWERS, not just retrieval. Code-graded, no LLM judge.

    python -m evaluation.answer_eval --models qwen2.5:3b qwen2.5:7b

Per answerable question (24):
  * answered_supported  - status "answered" and the passages it cites contain every gold evidence quote
  * answered_partial    - answered, cites at least one passage with gold evidence, but not all of it
  * answered_unsupported- answered, but none of its cited passages contains the gold evidence
  * wrongly_abstained   - said "insufficient evidence" although the evidence was retrieved
  * withheld            - the response contract blocked the model output (invalid JSON or citations)
  * citation precision  - share of cited passages that contain gold evidence
Per unanswerable question (4): correct abstention vs. answered (a hallucination) vs. withheld.
Retrieval upper bound: whether all gold evidence was in the passages sent to the model at all.

Caveat: questions and documents were AI-authored together (see dataset provenance); this is a development
set, not a benchmark. "Supported" means the cited passages contain the evidence; it does not prove every
word of the answer is faithful.
"""
import argparse
import json
import re
import statistics
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.embeddings.embedding_service import EmbeddingService
from app.generation.llm_client import LLMClient
from app.generation.rag_pipeline import RAGPipeline
from app.ingestion.pipeline import DocumentService
from app.retrieval.retriever import Retriever
from evaluation.metrics import normalize

ROOT = Path(__file__).resolve().parents[1]


class RecordingLLM:
    """Wraps the production client to keep the raw model text (to inspect what the contract withheld)."""
    def __init__(self, client):
        self.client, self.last_raw = client, None

    @property
    def configured(self):
        return self.client.configured

    def generate(self, messages):
        self.last_raw = None
        self.last_raw = self.client.generate(messages)
        return self.last_raw


def contains(text, quote):
    return normalize(quote).lower() in normalize(text).lower()


def grade(q, resp):
    gold = [e["quote"] for e in q["evidence"]]
    sent = [s.text for s in resp.sources]
    cited = [s.text for s in resp.sources if s.source_id in set(resp.cited_source_ids)]
    out = {"status": resp.status, "error_code": resp.error_code, "cited": resp.cited_source_ids,
           "n_sources": len(sent), "answer": resp.answer}
    if not gold:                                             # unanswerable
        out["outcome"] = {"insufficient_evidence": "correct_abstention", "answered": "hallucinated_answer"}.get(
            resp.status, "withheld")
        return out
    out["evidence_retrieved"] = all(any(contains(t, g) for t in sent) for g in gold)
    covered = [any(contains(t, g) for t in cited) for g in gold]
    out["citation_precision"] = (sum(any(contains(t, g) for g in gold) for t in cited) / len(cited)) if cited else None
    if resp.status == "answered":
        out["outcome"] = "answered_supported" if all(covered) else "answered_partial" if any(covered) else "answered_unsupported"
    elif resp.status == "insufficient_evidence":
        out["outcome"] = "wrongly_abstained" if out["evidence_retrieved"] else "abstained_no_evidence"
    else:
        out["outcome"] = "withheld"
    return out


def run_model(model, questions, embeddings, documents):
    with tempfile.TemporaryDirectory(dir=ROOT / "data") as d:
        settings = Settings(_env_file=None, data_dir=Path(d), embedding_device="cpu", llm_provider="ollama",
                            llm_model=model, llm_base_url="http://127.0.0.1:11434")
        service = DocumentService(settings, embeddings)
        try:
            for doc in documents:
                service.ingest(doc.name, doc.read_bytes(), "text/markdown")
            llm = RecordingLLM(LLMClient(settings))
            pipe = RAGPipeline(Retriever(service), llm, settings)
            pipe.ask("Warm-up: what does a consumer do after processing a message?")   # load model; not timed
            rows = []
            for q in questions:
                t0 = time.perf_counter()
                resp = pipe.ask(q["question"])
                ms = (time.perf_counter() - t0) * 1000
                row = {"id": q["id"], "kind": q["kind"], "question": q["question"], "latency_ms": round(ms, 1),
                       "llm_called": llm.last_raw is not None or resp.status == "error", **grade(q, resp)}
                if resp.status == "error":
                    row["raw_model_output"] = llm.last_raw
                rows.append(row)
                print(f"[{model}] {q['id']} {q['kind']:14s} {row['outcome']:22s} {ms:7.0f} ms", flush=True)
                llm.last_raw = None
        finally:
            service.close()
    return rows


def summarize(rows):
    ans = [r for r in rows if r["kind"] != "unanswerable"]
    una = [r for r in rows if r["kind"] == "unanswerable"]
    count = lambda rs, o: sum(r["outcome"] == o for r in rs)
    precisions = [r["citation_precision"] for r in ans if r.get("citation_precision") is not None]
    lat = sorted(r["latency_ms"] for r in rows if r["llm_called"])
    by_kind = {}
    for k in sorted({r["kind"] for r in ans}):
        rs = [r for r in ans if r["kind"] == k]
        by_kind[k] = f"{count(rs, 'answered_supported')}/{len(rs)}"
    return {
        "answerable": len(ans), "unanswerable": len(una),
        "answered_supported": count(ans, "answered_supported"), "answered_partial": count(ans, "answered_partial"),
        "answered_unsupported": count(ans, "answered_unsupported"), "wrongly_abstained": count(ans, "wrongly_abstained"),
        "abstained_no_evidence": count(ans, "abstained_no_evidence"), "withheld_answerable": count(ans, "withheld"),
        "evidence_retrieved": sum(r["evidence_retrieved"] for r in ans),
        "supported_by_kind": by_kind,
        "citation_precision_mean": round(statistics.mean(precisions), 3) if precisions else None,
        "correct_abstentions": count(una, "correct_abstention"), "hallucinated_on_unanswerable": count(una, "hallucinated_answer"),
        "withheld_unanswerable": count(una, "withheld"),
        "withheld_by_code": {c: sum(r.get("error_code") == c for r in rows) for c in ("invalid_model_response", "invalid_citations", "llm_unavailable")},
        "latency_ms_p50": round(statistics.median(lat)) if lat else None,
        "latency_ms_p95": round(lat[int(0.95 * (len(lat) - 1))]) if lat else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["qwen2.5:3b", "qwen2.5:7b"])
    ap.add_argument("--output", type=Path, default=ROOT / "evaluation/results/answer-eval")
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    (ROOT / "data").mkdir(exist_ok=True)
    dataset = json.loads((ROOT / "evaluation/dataset.json").read_text())
    documents = sorted((ROOT / "sample_documents").glob("*.md"))
    embeddings = EmbeddingService(Settings(_env_file=None, data_dir=ROOT / "data", embedding_device="cpu"))
    embeddings.encode(["warm up the encoder"])
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "dataset_provenance": dataset["provenance"],
              "defaults": "chunk 800/150 recursive, top_k 6, similarity threshold 0.30, temperature 0", "models": {}}
    for model in args.models:
        rows = run_model(model, dataset["questions"], embeddings, documents)
        (args.output / f"{model.replace(':', '_')}.json").write_text(json.dumps(rows, indent=1))
        report["models"][model] = summarize(rows)
        print(json.dumps(report["models"][model], indent=1))
    (args.output / "summary.json").write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
