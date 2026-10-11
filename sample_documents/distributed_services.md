# Distributed Services

## Timeouts

A timeout means the caller did not receive a timely response; the remote operation may still have completed.

A client that retries a payment after a timeout can therefore charge twice unless it reuses an idempotency key. Treat the outcome as unknown until it can be reconciled. Bound both the connection time and response time, and carry an overall deadline through downstream requests so nested calls do not exceed the user-facing time budget.

## Circuit breakers

A circuit breaker temporarily stops calls to a failing dependency after a failure threshold is reached.

The open state fails quickly instead of repeatedly consuming connection and thread resources. After a delay, a half-open state permits a small number of trial calls. Success allows normal traffic again; failure reopens the breaker. The breaker complements timeouts and retry budgets but does not repair the dependency itself.

## Quorum replication

With N replicas, read quorum R and write quorum W overlap when R plus W is greater than N.

For N equal to three, reading two replicas and writing two replicas creates overlap. Overlap alone is not a complete proof of linearizability: version ordering, concurrent writes and failure handling also matter. Availability depends on reaching enough replicas. Replication protects against some machine failures but does not replace backups against application-level corruption.

## Backpressure

Backpressure slows producers when consumers cannot keep up, preventing unbounded queue growth.

Use bounded queues, admission control or flow-control signals to limit outstanding work. A system that always accepts requests can run out of memory when its downstream service stalls. Monitor queue depth and time spent waiting. A bounded queue makes overload visible, but the application must decide whether to reject, delay or shed lower-priority work.

