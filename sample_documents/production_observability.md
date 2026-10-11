# Production Observability

## Latency percentiles

The p95 latency is the duration at or below which approximately 95 percent of observed requests finish.

A mean can hide slow tail requests, so report percentiles and sample counts. Warm timings exclude first-time model initialization, while cold timings include it. State whether a measurement includes network transport, queue waiting, query encoding and index lookup. Small local experiments do not establish performance under production concurrency.

## Tracing

A distributed trace links spans from multiple services using a shared trace identifier.

Each span records an operation and its duration, making it possible to follow one request through dependencies. Logs provide detailed events, while metrics summarize aggregate behavior. Correlating these signals helps locate slow calls and failures. Avoid putting credentials or unnecessary personal data into trace attributes or logs.

## Liveness and readiness

Liveness checks whether a process is alive; readiness checks whether it can serve its intended traffic.

A process can answer a liveness probe while its required database is unavailable. Readiness should reflect dependencies needed for serving, with care to avoid cascading restarts during an outage. A configured API endpoint is not proof that the remote model is reachable. Separate configuration status from an actual successful inference.

## Recovery testing

A backup is only demonstrated useful when a restore has been tested and the restored data has been checked.

Document recovery point and recovery time objectives before choosing a schedule. A cache that can be reconstructed from authoritative records needs a different recovery procedure from the records themselves. Test interrupted writes and stale caches so the application cannot silently serve deleted or inconsistent data after restarting.

