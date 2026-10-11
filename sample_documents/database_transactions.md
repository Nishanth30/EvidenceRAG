# Database Transactions

## Atomicity

Atomicity makes all writes in a transaction commit together or roll back together.

For a transfer between two accounts, debiting one balance and crediting the other belong in a single transaction. If a constraint fails, neither partial update should become visible as committed state. A transaction groups related state changes, but it does not automatically include external services such as a payment gateway or an email server.

## Isolation

Serializable isolation makes committed transactions equivalent to some serial execution.

A database can enforce this with locking or optimistic conflict detection. Applications must be prepared to retry a transaction that is aborted due to a serialization conflict. Snapshot isolation provides a consistent snapshot but can permit write skew. For example, two doctors may each observe another doctor on call and independently remove themselves from the schedule.

## Write-ahead logging

Write-ahead logging persists the log record before the corresponding changed data page is flushed.

Recovery can replay durable log records after a crash to restore committed changes. Durability depends on the database configuration and storage guarantees, including whether an acknowledgement waits for the required flush. A log supports crash recovery; a separate backup and restore strategy is needed for disk loss or accidental deletion.

## Indexes

A B-tree index accelerates equality and range lookups while adding storage and write maintenance costs.

The query planner can locate matching keys without scanning every table row. Updating indexed columns also updates the index, so an index is not free for write-heavy workloads. Composite indexes depend on column order and the predicates used by the query. Measure execution plans and workload latency before adding indexes to every column.

