# Message Delivery

## Acknowledgements

A consumer acknowledges a message only after its durable business transaction commits.

If the process crashes before acknowledging, the broker may redeliver the message. This is at-least-once delivery: a message can arrive more than once. Acknowledging before the business transaction commits risks losing work if the process crashes between those two operations. Delivery acknowledgements and database commits are separate operations unless a stronger protocol connects them.

## Idempotent consumers

Store the message ID in a deduplication table in the same transaction as the business update.

Put a unique constraint on that ID. On redelivery, an existing ID means the business change has already committed, so the consumer can acknowledge without applying it again. A separate check followed by an insert is unsafe under concurrent consumers. The uniqueness constraint and transaction must enforce the decision together. External side effects such as emails need their own idempotency mechanism.

## Transactional outbox

The transactional outbox stores the business change and an outgoing event in one database transaction.

A relay later reads unsent outbox rows and publishes them to the broker. A crash after publication but before recording success can publish the event again. Consumers still need deduplication. The outbox removes the gap in which a database commit succeeds but the corresponding event is never scheduled for delivery. It does not make all network effects exactly once.

## Retries and poison messages

A dead-letter queue isolates messages that repeatedly fail so they can be inspected and replayed.

Transient errors can be retried using exponential backoff and jitter. Set a retry budget so one invalid message does not consume the entire worker pool. Preserve the original message ID, error details and attempt count for investigation. Operators should repair the cause before replaying failed messages. A retry policy cannot make a non-idempotent operation safe by itself.

