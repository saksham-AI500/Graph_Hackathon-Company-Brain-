# NLI Verifier Calibration Report (Builder Set)

- **Model**: `cross-encoder/nli-MiniLM2-L6-H768` (Quantized AVX2 ONNX)
- **Builder Calibration Dataset SHA-256**: `20b789d69c01e08abb150c1098d1bcdf07704ce2fed741289a8d5d1fc42d9bc9`
- **Dataset Path**: `data/calibration/builder_calibration_pairs.json`
- **Builder Set Composition**: 40 pairs (15 Entailed, 15 Contradicted, 10 Hard Negatives)
- **Threshold Provenance**:
  - `0.50` is retained strictly as the dev threshold (tuned on 17 October outputs).
  - Equal-error rate threshold computed from builder data: `0.10`.
- **Independent Calibration Pairs**: Pending receipt from external evaluator.

## 1. Score Distributions Per Class

| Class | Count | Min Score | Median Score | Mean Score | Max Score | Error Rate at 0.50 |
|---|---|---|---|---|---|---|
| **Entailed** | 15 | 0.9236 | 0.9887 | 0.9848 | 0.9940 | **0.0%** (FNR) |
| **Contradicted** | 15 | 0.0002 | 0.0003 | 0.0009 | 0.0050 | **0.0%** (FPR) |
| **Hard Negatives** | 10 | 0.0004 | 0.0056 | 0.0268 | 0.0915 | **0.0%** (FPR) |

## 2. Threshold Performance Metrics

- **Dev Threshold ($0.50$)**:
  - False Negative Rate (FNR): `0.00%` (0/15)
  - False Positive Rate on Contradictions: `0.00%` (0/15)
  - False Positive Rate on Hard Negatives: `0.00%` (0/10)
  - Combined Negative FPR: `0.00%` (0/25)
- **Computed Equal-Error Rate (EER) Threshold**: `0.10`
  - At threshold `0.10`: FNR = `0.00%`, FPR = `0.00%`

## 3. Detailed Pair Scores

| ID | Class | Sub-Type | Premise | Hypothesis | Score | Decision (at 0.50) |
|---|---|---|---|---|---|---|
| `E01` | entailed | - | Elena Rostova merged PR #142 to enable R... | Redis clustering was enabled in producti... | `0.9937` | PASS |
| `E02` | entailed | - | Marcus Vance refactored the database con... | Database connection pool was refactored ... | `0.9929` | PASS |
| `E03` | entailed | - | We decided in ADR-002 that all internal ... | ADR-002 specifies that microservices com... | `0.9887` | PASS |
| `E04` | entailed | - | CODEOWNERS declares that the auth/ modul... | The auth/ directory is maintained by @ac... | `0.9236` | PASS |
| `E05` | entailed | - | Issue #44 describes checkout timeouts oc... | Checkout timeouts were reported during h... | `0.9776` | PASS |
| `E06` | entailed | - | The search cluster migration was complet... | Search cluster migration finished on 202... | `0.9933` | PASS |
| `E07` | entailed | - | ADR-005 mandates that PostgreSQL connect... | PostgreSQL connections per pod are limit... | `0.9849` | PASS |
| `E08` | entailed | - | Gabriel Santos reviewed and approved PR ... | PR #305 on token refresh rotation receiv... | `0.9940` | PASS |
| `E09` | entailed | - | The notifications service uses RabbitMQ ... | Failed push deliveries in notifications ... | `0.9874` | PASS |
| `E10` | entailed | - | PR #42 updated the circuit breaker thres... | Circuit breaker thresholds for billing w... | `0.9933` | PASS |
| `E11` | entailed | - | Sarah Chen deployed the distributed trac... | Distributed tracing collector was deploy... | `0.9866` | PASS |
| `E12` | entailed | - | Issue #89 tracks memory leaks in the Web... | WebSocket push gateway memory leaks are ... | `0.9924` | PASS |
| `E13` | entailed | - | ADR-007 requires AES-256 encryption at r... | Customer payment tokens must be encrypte... | `0.9917` | PASS |
| `E14` | entailed | - | Dmitri Volkov optimized the inverted ind... | Inverted index compression was improved ... | `0.9846` | PASS |
| `E15` | entailed | - | CODEOWNERS assigns frontend/dashboard to... | The @acme/frontend team is designated as... | `0.9876` | PASS |
| `C01` | contradicted | - | Elena Rostova merged PR #142 to enable R... | PR #142 was rejected and Redis clusterin... | `0.0003` | PASS |
| `C02` | contradicted | - | Marcus Vance refactored the database con... | Marcus Vance closed PR #236 without modi... | `0.0004` | PASS |
| `C03` | contradicted | - | We decided in ADR-002 that all internal ... | ADR-002 strictly forbids gRPC and mandat... | `0.0003` | PASS |
| `C04` | contradicted | - | CODEOWNERS declares that the auth/ modul... | The auth/ module has no code owners and ... | `0.0003` | PASS |
| `C05` | contradicted | - | Issue #44 describes checkout timeouts oc... | Issue #44 reports that checkout latency ... | `0.0050` | PASS |
| `C06` | contradicted | - | The search cluster migration was complet... | The search cluster migration was permane... | `0.0002` | PASS |
| `C07` | contradicted | - | ADR-005 mandates that PostgreSQL connect... | PostgreSQL connections per pod are compl... | `0.0007` | PASS |
| `C08` | contradicted | - | Gabriel Santos reviewed and approved PR ... | Gabriel Santos submitted a blocking reje... | `0.0002` | PASS |
| `C09` | contradicted | - | The notifications service uses RabbitMQ ... | The notifications service discards all f... | `0.0021` | PASS |
| `C10` | contradicted | - | PR #42 updated the circuit breaker thres... | PR #42 deleted all circuit breaker logic... | `0.0002` | PASS |
| `C11` | contradicted | - | Sarah Chen deployed the distributed trac... | Sarah Chen uninstalled distributed traci... | `0.0002` | PASS |
| `C12` | contradicted | - | Issue #89 tracks memory leaks in the Web... | Issue #89 confirms zero memory usage in ... | `0.0004` | PASS |
| `C13` | contradicted | - | ADR-007 requires AES-256 encryption at r... | ADR-007 permits plaintext unencrypted st... | `0.0013` | PASS |
| `C14` | contradicted | - | Dmitri Volkov optimized the inverted ind... | Dmitri Volkov reverted the inverted inde... | `0.0015` | PASS |
| `C15` | contradicted | - | CODEOWNERS assigns frontend/dashboard to... | CODEOWNERS assigns frontend/dashboard ex... | `0.0003` | PASS |
| `HN01` | hard_negative | wrong_number | The background sync retry policy specifi... | The background sync retry policy specifi... | `0.0011` | PASS |
| `HN02` | hard_negative | wrong_number | PostgreSQL connection pool max size is s... | PostgreSQL connection pool max size is s... | `0.0016` | PASS |
| `HN03` | hard_negative | wrong_date | PR #1 merged on 2025-10-04 after notific... | PR #1 merged on 2025-10-05 after notific... | `0.0096` | PASS |
| `HN04` | hard_negative | wrong_date | ADR-004 was ratified by architecture rev... | ADR-004 was ratified by architecture rev... | `0.0915` | PASS |
| `HN05` | hard_negative | negation | PR #42 was approved by Gabriel Santos af... | PR #42 was not approved by Gabriel Santo... | `0.0004` | PASS |
| `HN06` | hard_negative | negation | The payment gateway supports partial ref... | The payment gateway does not support par... | `0.0004` | PASS |
| `HN07` | hard_negative | wrong_entity | Marcus Vance refactored the auth token v... | Gabriel Santos refactored the auth token... | `0.0014` | PASS |
| `HN08` | hard_negative | wrong_entity | The payments/ module is owned by @acme/p... | The payments/ module is owned by @acme/g... | `0.0480` | PASS |
| `HN09` | hard_negative | wrong_scope | The new rate limiter applies strictly to... | The new rate limiter applies strictly to... | `0.0641` | PASS |
| `HN10` | hard_negative | wrong_scope | ADR-008 mandates mutual TLS for internal... | ADR-008 mandates mutual TLS for internal... | `0.0497` | PASS |
