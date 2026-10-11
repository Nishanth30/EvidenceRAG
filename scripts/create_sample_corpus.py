"""Recreate the self-authored educational corpus and AI-authored evaluation examples."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Short anchors identify evidence independently of a chunking configuration.
SECTIONS = {
'message_delivery.md': [
('Acknowledgements', 'A consumer acknowledges a message only after its durable business transaction commits.',
 'If the process crashes before acknowledging, the broker may redeliver the message. This is at-least-once delivery: a message can arrive more than once. Acknowledging before the business transaction commits risks losing work if the process crashes between those two operations. Delivery acknowledgements and database commits are separate operations unless a stronger protocol connects them.'),
('Idempotent consumers', 'Store the message ID in a deduplication table in the same transaction as the business update.',
 'Put a unique constraint on that ID. On redelivery, an existing ID means the business change has already committed, so the consumer can acknowledge without applying it again. A separate check followed by an insert is unsafe under concurrent consumers. The uniqueness constraint and transaction must enforce the decision together. External side effects such as emails need their own idempotency mechanism.'),
('Transactional outbox', 'The transactional outbox stores the business change and an outgoing event in one database transaction.',
 'A relay later reads unsent outbox rows and publishes them to the broker. A crash after publication but before recording success can publish the event again. Consumers still need deduplication. The outbox removes the gap in which a database commit succeeds but the corresponding event is never scheduled for delivery. It does not make all network effects exactly once.'),
('Retries and poison messages', 'A dead-letter queue isolates messages that repeatedly fail so they can be inspected and replayed.',
 'Transient errors can be retried using exponential backoff and jitter. Set a retry budget so one invalid message does not consume the entire worker pool. Preserve the original message ID, error details and attempt count for investigation. Operators should repair the cause before replaying failed messages. A retry policy cannot make a non-idempotent operation safe by itself.'),
],
'database_transactions.md': [
('Atomicity', 'Atomicity makes all writes in a transaction commit together or roll back together.',
 'For a transfer between two accounts, debiting one balance and crediting the other belong in a single transaction. If a constraint fails, neither partial update should become visible as committed state. A transaction groups related state changes, but it does not automatically include external services such as a payment gateway or an email server.'),
('Isolation', 'Serializable isolation makes committed transactions equivalent to some serial execution.',
 'A database can enforce this with locking or optimistic conflict detection. Applications must be prepared to retry a transaction that is aborted due to a serialization conflict. Snapshot isolation provides a consistent snapshot but can permit write skew. For example, two doctors may each observe another doctor on call and independently remove themselves from the schedule.'),
('Write-ahead logging', 'Write-ahead logging persists the log record before the corresponding changed data page is flushed.',
 'Recovery can replay durable log records after a crash to restore committed changes. Durability depends on the database configuration and storage guarantees, including whether an acknowledgement waits for the required flush. A log supports crash recovery; a separate backup and restore strategy is needed for disk loss or accidental deletion.'),
('Indexes', 'A B-tree index accelerates equality and range lookups while adding storage and write maintenance costs.',
 'The query planner can locate matching keys without scanning every table row. Updating indexed columns also updates the index, so an index is not free for write-heavy workloads. Composite indexes depend on column order and the predicates used by the query. Measure execution plans and workload latency before adding indexes to every column.'),
],
'distributed_services.md': [
('Timeouts', 'A timeout means the caller did not receive a timely response; the remote operation may still have completed.',
 'A client that retries a payment after a timeout can therefore charge twice unless it reuses an idempotency key. Treat the outcome as unknown until it can be reconciled. Bound both the connection time and response time, and carry an overall deadline through downstream requests so nested calls do not exceed the user-facing time budget.'),
('Circuit breakers', 'A circuit breaker temporarily stops calls to a failing dependency after a failure threshold is reached.',
 'The open state fails quickly instead of repeatedly consuming connection and thread resources. After a delay, a half-open state permits a small number of trial calls. Success allows normal traffic again; failure reopens the breaker. The breaker complements timeouts and retry budgets but does not repair the dependency itself.'),
('Quorum replication', 'With N replicas, read quorum R and write quorum W overlap when R plus W is greater than N.',
 'For N equal to three, reading two replicas and writing two replicas creates overlap. Overlap alone is not a complete proof of linearizability: version ordering, concurrent writes and failure handling also matter. Availability depends on reaching enough replicas. Replication protects against some machine failures but does not replace backups against application-level corruption.'),
('Backpressure', 'Backpressure slows producers when consumers cannot keep up, preventing unbounded queue growth.',
 'Use bounded queues, admission control or flow-control signals to limit outstanding work. A system that always accepts requests can run out of memory when its downstream service stalls. Monitor queue depth and time spent waiting. A bounded queue makes overload visible, but the application must decide whether to reject, delay or shed lower-priority work.'),
],
'retrieval_systems.md': [
('Embeddings', 'Normalized embeddings have unit length, so their inner product equals cosine similarity.',
 'A text encoder maps queries and passages to numerical vectors in the same embedding space. Similar meaning can be retrieved even when the wording differs. Semantic similarity is not a calibrated probability that a proposed answer is correct. Model choice, domain vocabulary and input truncation all influence retrieval quality.'),
('Chunking', 'Chunk overlap preserves nearby context at boundaries but increases storage and duplicate retrieval.',
 'Small chunks can focus on one fact while omitting information needed to interpret it. Larger chunks offer more context but may dilute a specific topic and exceed the encoder input length. Paragraph-aware splitting attempts to preserve logical boundaries. Measure both retrieval quality and the resulting number of chunks rather than assuming one size is always superior.'),
('Recall', 'Recall at k is the fraction of labeled relevant evidence units found among the first k retrieved results.',
 'If a question requires two independent pieces of evidence and only one is retrieved, its evidence recall is one half. Average per-question recall over answerable questions and state the relevance definition. Hit rate asks only whether any relevant result appears; it is a different measure for questions with several evidence units. Unanswerable questions require a separate rejection measure.'),
('Reciprocal rank', 'Reciprocal rank is one divided by the rank of the first relevant result, or zero when none is retrieved.',
 'Mean reciprocal rank averages this quantity across questions. A relevant passage in position one contributes one; a first hit in position four contributes one quarter. A cutoff must be stated when retrieval is truncated. Retrieval evaluation diagnoses the evidence selection stage separately from answer generation, whose faithfulness needs additional assessment.'),
],
'production_observability.md': [
('Latency percentiles', 'The p95 latency is the duration at or below which approximately 95 percent of observed requests finish.',
 'A mean can hide slow tail requests, so report percentiles and sample counts. Warm timings exclude first-time model initialization, while cold timings include it. State whether a measurement includes network transport, queue waiting, query encoding and index lookup. Small local experiments do not establish performance under production concurrency.'),
('Tracing', 'A distributed trace links spans from multiple services using a shared trace identifier.',
 'Each span records an operation and its duration, making it possible to follow one request through dependencies. Logs provide detailed events, while metrics summarize aggregate behavior. Correlating these signals helps locate slow calls and failures. Avoid putting credentials or unnecessary personal data into trace attributes or logs.'),
('Liveness and readiness', 'Liveness checks whether a process is alive; readiness checks whether it can serve its intended traffic.',
 'A process can answer a liveness probe while its required database is unavailable. Readiness should reflect dependencies needed for serving, with care to avoid cascading restarts during an outage. A configured API endpoint is not proof that the remote model is reachable. Separate configuration status from an actual successful inference.'),
('Recovery testing', 'A backup is only demonstrated useful when a restore has been tested and the restored data has been checked.',
 'Document recovery point and recovery time objectives before choosing a schedule. A cache that can be reconstructed from authoritative records needs a different recovery procedure from the records themselves. Test interrupted writes and stale caches so the application cannot silently serve deleted or inconsistent data after restarting.'),
],
}
QUESTIONS = [
('When should a consumer acknowledge a message?', 'message_delivery.md', 0),
('How do we avoid applying a business change twice after redelivery?', 'message_delivery.md', 1),
('How can a committed database update reliably schedule an event for publication?', 'message_delivery.md', 2),
('Where should messages that keep failing be put?', 'message_delivery.md', 3),
('What prevents a bank transfer from committing only the debit?', 'database_transactions.md', 0),
('Which isolation guarantee corresponds to running transactions one after another?', 'database_transactions.md', 1),
('What must be persisted before a modified database page is flushed?', 'database_transactions.md', 2),
('Which index supports key ranges, and what does it cost for writes?', 'database_transactions.md', 3),
('Does a timeout prove that a remote payment did not happen?', 'distributed_services.md', 0),
('How can a service stop repeatedly calling a dependency that is failing?', 'distributed_services.md', 1),
('What condition makes read and write quorums overlap?', 'distributed_services.md', 2),
('How can producers avoid exhausting memory when consumers fall behind?', 'distributed_services.md', 3),
('Why can inner product be used for cosine search with unit vectors?', 'retrieval_systems.md', 0),
('What are the benefits and costs of overlapping chunks?', 'retrieval_systems.md', 1),
('What fraction does evidence Recall@k measure?', 'retrieval_systems.md', 2),
('How is reciprocal rank calculated if the first relevant passage is fourth?', 'retrieval_systems.md', 3),
('What does the 95th percentile request duration mean?', 'production_observability.md', 0),
('How are operations across different services connected in a trace?', 'production_observability.md', 1),
('How does readiness differ from liveness?', 'production_observability.md', 2),
('How do we verify that a backup can actually recover data?', 'production_observability.md', 3),
]

def evidence(doc, section):
    return {'document': doc, 'page': None, 'quote': SECTIONS[doc][section][1]}


def main():
    directory = ROOT / 'sample_documents'
    directory.mkdir(exist_ok=True)
    for name, sections in SECTIONS.items():
        text = '# ' + name.removesuffix('.md').replace('_', ' ').title() + '\n\n'
        for title, anchor, rest in sections:
            text += f'## {title}\n\n{anchor}\n\n{rest}\n\n'
        (directory / name).write_text(text, encoding='utf-8')
    rows = []
    for i, (q, doc, section) in enumerate(QUESTIONS):
        rows.append({'id': f'q{i+1:02}', 'question': q, 'kind': 'direct' if i % 2 == 0 else 'paraphrased',
                     'evidence': [evidence(doc, section)]})
    multi = [
        ('How do acknowledgement timing and transactional deduplication work together after a consumer crash?',
         [('message_delivery.md', 0), ('message_delivery.md', 1)]),
        ('What do timeouts tell a caller, and why are idempotent consumer updates needed on retries?',
         [('distributed_services.md', 0), ('message_delivery.md', 1)]),
        ('How do recall and reciprocal rank measure different aspects of retrieval?',
         [('retrieval_systems.md', 2), ('retrieval_systems.md', 3)]),
        ('How do circuit breakers and backpressure protect an overloaded service?',
         [('distributed_services.md', 1), ('distributed_services.md', 3)]),
    ]
    for q, refs in multi:
        rows.append({'id': f'q{len(rows)+1:02}', 'question': q, 'kind': 'multi_evidence',
                     'evidence': [evidence(*r) for r in refs]})
    for q in ['What is the capital of Peru?', 'What exact Kafka retention setting does our company use?',
              'How much does our cloud provider charge per million messages?',
              'Which medication should be used to treat a migraine?']:
        rows.append({'id': f'q{len(rows)+1:02}', 'question': q, 'kind': 'unanswerable', 'evidence': []})
    dataset = {'provenance': 'AI-authored educational documents and candidate questions, checked for exact evidence presence by code. Not independently human-validated; not a held-out benchmark.',
               'license': 'CC0-1.0 for this sample corpus and dataset', 'questions': rows}
    (ROOT / 'evaluation/dataset.json').write_text(json.dumps(dataset, indent=2) + '\n')

if __name__ == '__main__':
    main()
