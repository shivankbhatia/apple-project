# Ad-Click Fraud / Invalid-Traffic Detection — Lambda Architecture

> **Phase 0 status:** this repository is being retargeted in place from the
> completed PaySim transaction demo to TalkingData ad-click / invalid-traffic
> detection. The prior implementation remains available in this repository's
> Git history. Its narrative is retained below as an archive only; its metrics,
> schema, and operational claims do **not** describe the ad-click pipeline.

## Target architecture

Kafka carries JSON click events on `clicks`, keyed by `ip` (three partitions).
PyFlink computes processing-time, incremental click features and writes scored
clicks to staging; Spark retrains on delayed labels, writes Delta and Hive
outputs, and exports campaign statistics for the speed layer. Flagged clicks
are additionally published to `click_alerts` for monitoring.

| Component | Target identifier |
| --- | --- |
| Kafka input / alert topics | `clicks` / `click_alerts` |
| Flink job | `click_scorer.py` |
| Delta path | `data/delta/scored_clicks` |
| Hive table | `ad_fraud.batch_scored_clicks` |
| Model artifacts | `models/click_fraud_model*.pkl` |

The shared `features/` package is the feature contract for both Flink and
Spark. Phase 2 will add its deterministic implementations and parity tests.

### Phase 3 baseline (reproducible)

The bootstrap-label model uses a chronological 80/20 split of the contiguous
1M-click Phase 1 extract (no shuffled split). Its `is_fraud` label is a
velocity-plus-near-zero-attribution heuristic and not real IVT ground truth;
these metrics measure separation of that bootstrap signal only.

| Model / experiment | ROC-AUC | PR-AUC | Fit time |
| --- | ---: | ---: | ---: |
| Logistic regression baseline | 0.987841 | 0.826458 | 2.191 s |
| XGBoost speed-layer model | 0.995370 | 0.905552 | 1.299 s |
| XGBoost warm start, W1 → W2 | 0.995041 | 0.892866 | 0.918 s |
| XGBoost cold, W1 + W2 | 0.995370 | 0.905552 | 1.331 s |

The selected validation F1 threshold is **0.859968** (F1 0.853524), rather
than an assumed 0.5. `models/click_fraud_model.pkl`, `models/feature_list.pkl`,
and `models/campaign_stats.json` are intentionally local artifacts; regenerate
them with `./.venv/bin/python scripts/train_click_model.py`.

### Local setup

```bash
cd fraud_lambda
docker compose up -d
docker compose ps
```

`kafka-topic-init` provisions the two topics idempotently. The Hive warehouse
is mounted at `./data/hive-warehouse`, not at a machine-specific absolute
path. Host-side dependencies are listed in `requirements.txt`; PyFlink is
normally run inside the supplied Flink Docker image rather than installed
natively.

### Click replay and contract check

Kafka messages are JSON (a deliberate local-demo tradeoff; production would
use Avro/Protobuf plus Schema Registry). The producer keys every message by
`ip`, preserving partition affinity for IP-keyed stream state. It replays in
`click_time` order; `event_timestamp` is stamped immediately before publish so
the speed layer can calculate end-to-end processing latency.

```bash
# Terminal 1: observe only new records, validate the schema, and show rate.
./.venv/bin/python producer/schema_check_consumer.py --max-messages 100

# Terminal 2: replay a small, fast demo and add a labeled click-farm burst.
./.venv/bin/python producer/kafka_producer.py \
  --limit 1000 --start-ts '2017-11-06 16:00:00' \
  --speed-multiplier 3600 --inject-farms
```

`--inject-farms` emits a small set of repeat IP/device fingerprints at uniform
gaps with `is_synthetic=1` and `is_fraud=1`. It is solely demo/reconciliation
ground truth, never treated as an assertion about the organic TalkingData rows.

## Prior project archive (PaySim; not current)

# Real-Time Fraud Detection — Lambda Architecture

Kafka + Flink + Spark + Delta Lake + Hive fraud detection system combining
real-time transaction scoring with nightly batch retraining.

**Stack:** Apache Kafka · PyFlink · Apache Spark · Delta Lake · Hive · XGBoost · Docker Compose

---

## Architecture

A Lambda architecture with two independent scoring paths reconciled against each other:

- **Speed layer** — PyFlink consumes transactions from Kafka in real time, maintains per-account
  stateful features, and scores each transaction with a pre-trained XGBoost model as it arrives.
- **Batch layer** — Apache Spark periodically reprocesses the full transaction history, retrains
  the model, and writes curated, deduplicated results to Delta Lake, queryable via Hive.
- **Reconciliation** — Speed-layer and batch-layer predictions for the same transactions are
  compared to measure how much the real-time approximation drifts from the batch "ground truth."

---

## Key Findings & Feature Investigation

### Class Imbalance
- Fraud represents **0.129%** of all transactions.
- Fraud is concentrated entirely in **TRANSFER** and **CASH_OUT** transaction types.
- **PAYMENT**, **CASH_IN**, and **DEBIT** contain **0% fraud**.
- The pipeline filters transactions to only **TRANSFER** and **CASH_OUT** before scoring, reducing the streaming volume by **~56%** while maintaining **100% fraud recall**.

### Leakage Investigation
Initial feature engineering included:
- `orig_balance_error`
- `dest_balance_error`

These features measured the deviation between expected and actual account balances after each transaction.

A single-feature AUC analysis showed that `orig_balance_error` alone achieved an **AUC of 0.947**, indicating an unusually strong predictive signal. Further investigation revealed this was caused by a **dataset artifact** rather than genuine fraud behavior.

**Investigation results:**
- **32.9%** of legitimate transactions have untracked (zero-value) origin balances in the PaySim simulator.
- **99.5%** of fraudulent transactions exhibit mathematically perfect balance reconciliation.

This behavior is a **known characteristic of the PaySim simulator**, not a realistic fraud indicator. Consequently, both balance-error features were removed from the final feature set.

### Remaining Dominant Feature
After removing the balance-error features:

- `amount_to_balance_ratio` (transaction amount divided by origin balance) accounts for approximately **96%** of model decisions.
- Fraudulent transactions cluster around ratios of **0.9999–1.0**, representing near-total account drainage.

This pattern reflects PaySim's intended fraud simulation, where fraudulent behavior follows an **account-takeover** scenario: drain the victim's account, then cash out. This is considerably more deterministic than real-world fraud, where transaction amounts are typically more diverse — a limitation of the dataset's fraud-generation process rather than the modeling approach.

### Validation Methodology
Model evaluation uses **walk-forward (expanding-window) validation** across **5 temporal folds** instead of a single random or time-based split.

This decision was made after observing that PaySim's transaction volume drops sharply after approximately **step 400**, while the absolute number of fraudulent transactions remains roughly constant — so the fraud rate varies by more than **20×** across different periods despite stable fraud counts. Walk-forward validation avoids evaluating on a single, potentially unrepresentative time window.

### Final Model Performance

**Model:** XGBoost

| Metric | Value |
|---------|------:|
| Features Used | 4 |
| ROC-AUC | **0.9995 ± 0.0003** |
| PR-AUC | **0.940 ± 0.049** |
| Validation | 5-fold Walk-Forward |

**Final features:**
1. `amount_to_balance_ratio`
2. `amount`
3. `dest_txn_count_so_far`
4. `is_transfer_type`

---

## Layer Agreement (Speed vs. Batch)

The speed layer's real-time predictions were reconciled against the batch layer's recomputed
predictions for the same transactions:

| Metric | Value |
|---|---:|
| Speed / batch prediction agreement | **98.43%** |

**Methodology:** `reconciliation/reconcile.py` joins speed-layer output (Delta table, written via
`staging_to_delta.py`) against batch-layer output (Hive table, written by `batch_retrain.py`) on
`transaction_id`, and computes the percentage of matched records where both layers agree on the
fraud/not-fraud classification at a 0.5 probability threshold.

---

## Performance

### Speed Layer — End-to-End Scoring Latency

`flink-job/fraud_scorer.py` stamps a `scored_at` timestamp immediately after XGBoost inference,
right before the sink. This is diffed against `event_timestamp`, which the Kafka producer
(`producer/kafka_producer.py`) attaches at publish time. `latency_ms = scored_at - event_timestamp`
therefore covers **Kafka publish → consume → stateful feature computation → XGBoost inference**.
It does not include producer-side serialization or FileSink checkpoint flush delay (checkpointed
every 10s), so true "event to durable output" latency runs slightly higher, especially at the tail.

Measured over **18,600 records** replayed at high throughput against a **single-partition,
single-parallelism** (`env.set_parallelism(1)`) local deployment:

| Percentile | Latency |
|---|---:|
| Min (best case) | **270 ms** |
| p50 | **8,054 ms** |
| p95 | **20,922 ms** |
| p99 | **21,386 ms** |
| Max | **21,490 ms** |
| Mean | **9,393 ms** |

**Interpretation:** the 270ms floor is the true per-record cost with no queueing — Kafka consume,
feature lookup, and inference with nothing waiting ahead of it. The steep climb from p50 to p95/p99,
plateauing near the max, is characteristic of **consumer-side backpressure**: the producer publishes
faster than a single Flink subtask can drain the partition, so a backlog builds and later messages
wait longer before being picked up. p95/p99/max converging to a similar value (rather than climbing
indefinitely) indicates the system reached steady-state lag rather than unbounded queue growth. The
straightforward fix — not yet implemented — is increasing Kafka partition count and Flink parallelism
so multiple subtasks can drain the topic concurrently.

Latencies were computed with `reconciliation/latency_report.py`, which reads the Delta table
written by `staging_to_delta.py` and calculates percentile statistics over all non-null
`latency_ms` values.

### Batch Layer — End-to-End Job Timing

`spark-batch/batch_retrain.py` wraps each pipeline stage with `time.perf_counter()` checkpoints,
writing a per-stage breakdown to `data/batch_job_timings.json` on completion.

Measured over the **full filtered dataset (2,770,409 TRANSFER/CASH_OUT transactions)**:

| Stage | Time | Share of total |
|---|---:|---:|
| Load + filter (CSV → Spark DataFrame) | 7.35s | 13% |
| Feature engineering (Spark transforms) | 5.53s | 10% |
| Spark → pandas conversion | 15.45s | 27% |
| XGBoost training | 6.33s | 11% |
| XGBoost inference + eval | 0.53s | 1% |
| Hive table write | 19.00s | 34% |
| **Total wall-clock** | **56.60s** | 100% |

**Throughput:** 2,770,409 rows / 56.60s ≈ **48,946 records/sec** (end-to-end, including model
training).

**Interpretation:** model training itself (6.33s) is a small fraction of total runtime. The two
dominant costs are the Spark→pandas materialization (27%) and the Hive write (34%) — together
over 60% of the job. This indicates the bottleneck is data movement between engines, not compute,
and is where future optimization effort would have the highest return (e.g., avoiding full
in-memory pandas conversion, or a more direct Delta→Hive write path).

---

## Known Limitations

- Speed-layer latency figures reflect a **local, single-partition deployment** with no autoscaling
  or partition tuning — they characterize the architecture's behavior under load, not a
  production-tuned SLA.
- PaySim is a **simulated** dataset with a deterministic fraud-generation process (see Remaining
  Dominant Feature, above); reported AUC/PR-AUC figures reflect performance on this simulation
  and should not be read as real-world fraud detection accuracy.
- Batch-layer timing was measured on a MacBook Air (Apple Silicon, local Docker Compose stack),
  not a distributed cluster — absolute numbers won't transfer directly to a production Spark
  cluster, but the relative stage breakdown (where time is spent) is architecture-independent.

---

## Repository Structure

```
producer/            # Kafka producer replaying PaySim transactions with event timestamps
flink-job/            # PyFlink speed-layer stateful stream scoring
spark-batch/          # Spark batch retraining + Hive/Delta Lake writes
reconciliation/       # Speed/batch agreement + latency percentile reporting
data/                 # Local outputs: staging JSON, Delta table, timing/latency reports
docker-compose.yml    # Kafka, Zookeeper, Flink, Hive Metastore, Postgres
```
