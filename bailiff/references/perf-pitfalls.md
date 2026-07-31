# Performance Pitfalls — Bailiff Reference

Recurring performance defects the bailiff must actively check for
when seeding the **Performance** category of the Phase 1
expectation checklist. Each pitfall passed compile and CI in at
least one real feature; each has a plan-phase guardrail that turns
into a bailiff expectation.

When Phase 1 sees any of the triggers below, add the corresponding
expectation to the checklist. When Phase 3 reads implementation
code, grep for the anti-pattern.

The numbering is stable — a bailiff report that says "perf-pitfall
#3 recurs here" is meaningful across features.

---

## Trigger map

Use this table to decide which pitfalls are in scope for a given
spec. If the trigger matches, the pitfall is in scope.

| # | Trigger phrase in PRD/plan | Pitfall |
|---|---|---|
| 1 | Any Mongo/HBase/Redis upsert, find, or list query | Missing index on lookup/upsert path |
| 2 | New Kafka consumer OR new downstream-bound RPC path OR "rate limit" OR "QPS" | RPM/QPS estimation from the wrong side |
| 3 | Kafka consumer with `batch`, `sub_batch_size`, or semaphore | Sub-batch / semaphore / yaml-batch misalignment |
| 4 | Per-message retry loop with `maxRetry` | `maxRetry=1` retry loop is a barrier stall |
| 5 | Hive/HDFS/ODS read job with a date partition | Full-scan on daily-snapshot tables |
| 6 | Spark ETL with `driverCollectMode` or `.collect()` | Driver-collect without `limit` OOM |
| 7 | Hive/HDFS read from a source known to be fragmented | Fragmented input → one-task-per-file |
| 8 | Any Spark job that logs row counts or "N rows read" | Eager `.count()` doubling the scan |
| 9 | Spark write to Kafka/HBase with a QPS/rate cap | Sink QPS throttle without per-partition math |
| 10 | Consumer/handler tuned by Rainbow numeric keys | Rainbow-config typo → wedged consumer |
| 11 | Async + goroutine / CAS / background worker introduced for perf | Async-then-sync flip-flop without measurement |
| 12 | Client-side retry on downstream that has Polaris ratelimit | Retry amplifying downstream backpressure |

---

## Pitfall catalogue

### #1. Missing index on upsert / lookup path

**Anti-pattern.** Mongo/HBase write path adds `Upsert` /
`FindOneAndUpdate` / `Find` with a filter, but the collection has
no index matching the filter shape. Passes tests on a small dataset
(fast anyway); prod does `COLLSCAN` per message.

**Bailiff expectations.**

- Every query shape named by the plan (upsert filter, find
  predicate, sort/skip/limit combination) has a matching index.
- Compound indexes follow the leftmost-prefix rule for the query
  shape.
- If ops owns index creation, the plan has an "Indexes to add
  before deploy" block. Bailiff verifies it exists and matches.
- Reject "add index later if slow" — flag as FAIL.

**Grep hooks.** `Upsert`, `FindOneAndUpdate`, `IndexModel`,
`EnsureIndex`, `CreateIndex`, `db.<coll>.getIndexes`.

### #2. RPM/QPS estimation from the wrong side

**Anti-pattern.** Batch size / concurrency picked without a
downstream capacity number. Two symmetric failure modes:
overestimated capacity (429 storm), overestimated latency (jitter
stall). Real example: `ExcelUploadWorkflowBatchSize` was 500,
downstream rate-limited, fix was 200.

**Bailiff expectations.**

- Plan cites p50 and p99 latency for every synchronous downstream
  RPC.
- Plan cites the downstream's rate-limit budget (RPS / QPS /
  Polaris token bucket).
- Plan sets target utilization ρ ≈ 0.6–0.7, not 0.9+.
- Jitter satisfies `avg_jitter_ms < per_message_rpc_ms`.

**Grep hooks.** `maxJitterMs`, `_JITTER_MS`, `RateLimit`, `429`,
`Retry-After`.

### #3. Sub-batch / semaphore / yaml-batch misalignment

**Anti-pattern.** yaml `batch` bumped without touching handler
`sub_batch_size`; extra sub-batches per handler call add a
`wg.Wait()` barrier per call, throughput doesn't move. Or:
semaphore sized far above sub_batch_size, wasting the budget.

**Bailiff expectations.**

- Plan states the four numbers together: `yaml_batch`,
  `sub_batch_size`, `semaphore_size`, target `per_pod_rate`.
- `yaml_batch = sub_batch_size` unless justified in-line.
- `semaphore ≥ sub_batch_size`; if higher, plan notes it's a doc
  artifact.
- Plan states input topic partition count and `active_pods =
  min(deployed, partitions)`.

**Grep hooks.** `batch:`, `sub_batch_size`, `sem := make(chan`,
`SEMAPHORE`, `PARALLEL`, `active_pods`, `partition`.

### #4. `maxRetry=1` retry loop is a barrier stall

**Anti-pattern.**

```go
for retry := 0; retry < maxRetry; retry++ {
    if err := call(); err == nil { break }
    time.Sleep(backoff)
}
```

with `maxRetry=1`. The loop runs once; the sleep never executes.
But if `maxRetry` is later dropped from 3 to 1, the sleep stays —
wedges the sub-batch `wg.Wait()` behind that one message.

**Bailiff expectations.**

- Retry depth is either 0 (no loop) or ≥ 2 (loop justified).
- No in-line `time.Sleep` between retry attempts when depth is 1.

**Grep hooks.** `for.*retry.*<.*maxRetry`, `time.Sleep` inside
retry, `MaxRetry`, `maxRetry`.

### #5. Full-scan on daily-snapshot tables

**Anti-pattern.** Spark ETL job over an ODS (daily full snapshot)
table doesn't require a `partition` arg — job with no partition
scans every day of history.

**Bailiff expectations.**

- `partition` is a required arg for any Hive/HDFS read on a
  partitioned table.
- Empty partition value is rejected at parse time before
  SparkSession is created.
- `TDWUtil.partitionExist()` (or equivalent) is called before the
  read.
- `partition` is normalized (`p_YYYYMMDD` ↔ `YYYYMMDD`).

**Grep hooks.** `argsMap.getOrElse("partition"`, `partitionExist`,
`p_${date}`, `spark.read.table`, `tdw.table(`.

### #6. Driver-collect without `limit` = OOM

**Anti-pattern.** `driverCollectMode=true` without an explicit
`limit=N` calls `.collect()` on the full result set. Symmetric:
`limit=N` without `driverCollectMode=true` looks like it's
smoke-testing but runs full distributed.

**Bailiff expectations.**

- Parse-time rejection of both combinations, with usage-line
  error log and `System.exit(1)`.

**Grep hooks.** `driverCollectMode`, `.collect()`, `.limit(`.

### #7. Fragmented input → one-task-per-file

**Anti-pattern.** Source has ~52k tiny ORC files. Naive
`spark.read` spawns 52k tasks. Naive `.repartition(100)` forces a
full shuffle of all 52k input partitions first.

**Bailiff expectations.**

- Plan states expected source partition/file count if fragmented
  (>1k files).
- `driverCollectMode=true limit=N` path skips `.repartition()`;
  uses `df.limit(n).collect()` to trigger `CollectLimitExec`.
- Distributed writes to a small number of output partitions use
  `.coalesce(N)`, not `.repartition(N)`.

**Grep hooks.** `.repartition(`, `.coalesce(`, `foreachPartition`.

### #8. Eager `.count()` doubling the scan

**Anti-pattern.** `.count()` called for a log line before the
actual action; forces a second full scan.

**Bailiff expectations.**

- No `.count()` / `.rdd.count()` / `.collect().length` in the hot
  path for logging purposes.
- Row counts logged from `sc.longAccumulator` inside the write's
  `foreachPartition`.
- `.cache()` calls have a matched `.unpersist()` or a documented
  reason.

**Grep hooks.** `.count()`, `.rdd.count`, `sc.longAccumulator`,
`.cache()`, `.unpersist(`.

### #9. Sink QPS throttle without per-partition math

**Anti-pattern.** `foreachPartition` with a `kafkaQPS` cap that
uses `kafkaQPS` verbatim per partition — aggregate becomes
`N × qps`.

**Bailiff expectations.**

- Rate limit = `Math.max(1, target_qps / write_partitions)`.
- `.coalesce(kafkaWritePartitions)` before `foreachPartition` so
  the physical partition count matches the divisor.
- Plan shows the arithmetic and states aggregate throughput.

**Grep hooks.** `kafkaQPS`, `kafkaWritePartitions`, `rateLimit`,
`per_partition`, `sliding window`.

### #10. Rainbow-config typo → wedged consumer

**Anti-pattern.** `batchList(msgs, 0)` is an infinite loop. Rainbow
returns 0 (missing key or typo), consumer wedges with no recovery.

**Bailiff expectations.**

- Every Rainbow-loaded numeric knob validates `<= 0` and falls
  back to a named default.
- Consumer logs the effective value at boot (`init...Consumer
  cache_size=N batch_size=N`).
- Yaml `${VAR}` env-var substitutions either hard-code, use
  `${VAR:-default}`, or are guaranteed by the deploy template.

**Grep hooks.** `GetIntWithDefault`, `GetStringWithDefault`,
`Rainbow`, `os.Getenv`, `${.*}` in yaml.

### #11. Async-then-sync flip-flop without measurement

**Anti-pattern.** "Make it async for perf" without a baseline
number. Later reverted because the CAS/goroutine complexity
outweighed the actual latency saved (real example:
`pipeline_failure_readable_prd.md` v1.3 removed the async export).

**Bailiff expectations.**

- Any async / goroutine / CAS / background-worker plan cites the
  measured sync latency and the target the async version must
  hit.
- If either number is a hand-wave, prefer synchronous.

**Grep hooks.** `go func()`, `CompareAndSwap`, `channel.*background`,
`async`, `WorkerPool`.

### #12. Retry amplifying downstream backpressure

**Anti-pattern.** Polaris ratelimit doesn't 5xx — it queues.
Client-side "retry on slow response" makes the queue deeper, which
makes response slower, which fires more retries.

**Bailiff expectations.**

- Client retry distinguishes network error from latency
  saturation. Timeout does not automatically imply retry.
- Consumer-side rate control (semaphore + jitter) is the
  documented mechanism, not consumer-side retry.
- If the downstream lacks a circuit breaker, plan says so and does
  not substitute client-side timeout-based retry.

**Grep hooks.** `context.DeadlineExceeded` triggering retry,
`Retry.*Timeout`, `ratelimit`, `circuit.?breaker`.

---

## How to use this reference during a bailiff run

1. **Phase 1, before writing expectations:** read this file. For
   each trigger in the map above that matches the spec, add one
   Performance-category expectation to the checklist. Cite the
   pitfall number in the Source column so future bailiffs can
   track recurrence.

2. **Phase 3, after tests run:** run the grep hooks against the
   changed files. A hit doesn't automatically fail — but combined
   with an unmet expectation, it points to a concrete code line.

3. **Reporting:** when a Performance expectation fails, note the
   pitfall number in the failure title:
   `F<N>: perf-pitfall #<M> — <one-line summary>`. Cross-feature
   diffs become mechanical.

## Where this catalogue comes from

Distilled from `perf-preflight-2026-07-07.md` under the harness
folder of the reference project (`/root/.ai/harness/`), which in
turn was distilled from real PRDs, plans, and build reports across
`edu_service`, `data_streaming_hive_spark3`, `mas-edu-strategy`,
`mas-tool`. When a new pitfall category emerges from a bailiff or
scout finding, add it here — the numbering is append-only so
cross-feature references stay stable.
