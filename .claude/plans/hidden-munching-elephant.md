# CUTLASS Integration for Optimizer V8

## Context

The Optimizer V8 project (`Optimizer_V7_G3/`) has an `acceleration/` module that references `cutlass_integration.py` and `high_impact_optimizer.py` — but neither file was ever written. CUTLASS v3.5.1 is built and installed at `C:\Users\User\OneDrive\Desktop\AI_Dev\cutlass\` with Python bindings, profiler, and SM89 kernels. The `config.yaml` already has `cutlass_kernels: true`. The goal is to connect these pieces so CUTLASS benchmark data feeds into the GPU Specialist expert, turning raw GPU performance measurements into actionable optimization recommendations.

## Approach

Enhance the existing GPU Specialist expert with benchmark-driven intelligence rather than adding a new expert. Benchmark results are cached to disk (JSON) and loaded into `SystemContext` during each optimization cycle. This keeps the architecture unchanged while adding real measurement-based decision-making.

---

## Files to Create (3)

### 1. `acceleration/cutlass_integration.py` (~100 lines)
CUTLASS availability detection, path management, and benchmark cache infrastructure.

- `_setup_cutlass_path()` — adds CUTLASS Python dir to `sys.path`, sets `CUDA_INSTALL_PATH` to prevent Linux-only `/usr/bin/which` call
- `_HAS_CUTLASS` flag with lazy init (same pattern as `pynvml` in `telemetry.py`)
- `CUTLASSBenchmarkResult` dataclass: precision, matrix_size, tflops, theoretical_peak, efficiency_pct, time_ms
- `CUTLASSBenchmarkCache` dataclass: gpu_name, driver_version, cuda_version, timestamp, results list
  - `is_valid(gpu_name, driver_version)` — invalidates on hardware change or 7-day TTL
- `load_cached_benchmarks()` / `save_benchmark_cache()` — JSON to/from `data/cutlass_benchmark_cache.json`
- `is_available()` — public check for CUTLASS availability
- Uses `sort_keys=True` for He2025 determinism

### 2. `benchmarks/cutlass_bench.py` (~140 lines)
Standalone GEMM benchmark across precisions, comparing against RTX 4090 theoretical peaks.

- `_RTX4090_PEAKS` dict: fp32=82.6, tf32=165.2, fp16=330.3, bf16=330.3 TFLOPS
- `run_benchmark(sizes, precisions, warmup_iters, bench_iters)` -> `list[dict]`
  - Uses PyTorch `torch.mm()` for reliable cross-platform GEMM (not raw CUTLASS API which has Windows issues)
  - Tests FP32, TF32, FP16, BF16 at 1024/2048/4096/8192 matrix sizes
  - Explicitly toggles `torch.backends.cuda.matmul.allow_tf32` for TF32 vs FP32 isolation
  - Adds memory bandwidth test (clone-based, same as existing `pytorch_bench.py`)
  - Returns structured dicts matching `CUTLASSBenchmarkResult` fields
- `print_results()` — formatted output with efficiency bars and summary
- Runnable standalone: `python benchmarks/cutlass_bench.py`

### 3. `tests/test_cutlass_integration.py` (~90 lines)
Tests for benchmark caching and the new GPU Specialist benchmark-driven recommendations.

- `TestCUTLASSBenchmarkCache`: valid/invalid cache (hardware mismatch, expiry), save/load round-trip, missing file
- `TestGPUSpecialistWithBenchmarks`: low TF32 efficiency -> rec, no benchmark data -> no benchmark recs, high FP32 + disabled TF32 -> strong INFO rec, ComfyUI active + good FP16 -> CUTLASS path rec
- Uses `tmp_path` fixture for cache file isolation, `patch` for cache paths
- Matches existing test style in `test_experts.py` (direct `SystemContext()` construction)

---

## Files to Modify (5)

### 4. `acceleration/__init__.py`
Replace the comment-only docstring with actual imports from `cutlass_integration`.

### 5. `optimizer/models.py` (line 87)
Add one field to `SystemContext`:
```python
benchmark_data: dict[str, Any] = field(default_factory=dict)
```
After `env_vars`. This is backward-compatible — all existing code passes no `benchmark_data` and gets `{}`.

### 6. `optimizer/experts/gpu_specialist.py`
Add `_check_cutlass_perf(self, ctx, recs)` method called from `analyze()`. Produces recommendations based on `ctx.benchmark_data`:

| Condition | Recommendation | Impact | Confidence |
|-----------|---------------|--------|------------|
| TF32 efficiency < 50% | Set `NVIDIA_TF32_OVERRIDE=1` | 0.7 | 0.85 |
| FP16 efficiency < 60% | Set `CUDNN_BENCHMARK=1` | 0.6 | 0.8 |
| High FP32 but TF32 < 10% | INFO: TF32 could give ~2x | 0.8 | 0.9 |
| Mem bandwidth < 700 GB/s | Set `PYTORCH_CUDA_ALLOC_CONF` | 0.5 | 0.75 |
| ComfyUI active + FP16 > 70% | Ensure `CUTLASS_PATH` set | 0.6 | 0.7 |

Note: The orchestrator's existing dedup logic (key = `env:{name}`) handles overlaps with `_check_cuda_env` — the higher-scored recommendation wins.

### 7. `optimizer/orchestrator.py`
Add `_load_benchmark_data(self, ctx)` called from `run_cycle()` between snapshot and expert dispatch. Loads cached benchmarks via `acceleration.cutlass_integration.load_cached_benchmarks()`, computes summary metrics (per-precision peak efficiency), and populates `ctx.benchmark_data`. Wrapped in try/except ImportError for graceful degradation.

### 8. `optimizer/cli.py`
Add `--benchmark-cutlass` flag:
- Imports and runs `benchmarks.cutlass_bench.run_benchmark()`
- Caches results via `acceleration.cutlass_integration.save_benchmark_cache()`
- Prints results and confirms cache location

---

## Implementation Order

```
Step 1 (parallel):  models.py (add field)
                    acceleration/cutlass_integration.py (create)
                    benchmarks/cutlass_bench.py (create)
Step 2:             acceleration/__init__.py (update imports)
Step 3:             optimizer/experts/gpu_specialist.py (add _check_cutlass_perf)
Step 4 (parallel):  optimizer/orchestrator.py (add benchmark loading)
                    optimizer/cli.py (add --benchmark-cutlass)
Step 5:             tests/test_cutlass_integration.py (create + run)
```

## NOT in Scope (deferred)

- `high_impact_optimizer.py` — aggregator for all acceleration strategies. Can be added later once CUTLASS integration is proven.
- Updating `install_cutlass.bat` for CUTLASS 4.x — requires checking if 4.x Windows support has landed. Separate task.
- Raw CUTLASS Python API benchmarks (the `cutlass_cppgen` package has Windows `/usr/bin/which` issues). PyTorch GEMM gives us the same performance data reliably.

## Verification

1. `python -m pytest tests/ -v` — all existing tests still pass (backward-compatible `benchmark_data={}` default)
2. `python -m pytest tests/test_cutlass_integration.py -v` — new tests pass
3. `python benchmarks/cutlass_bench.py` — standalone benchmark runs, prints TFLOPS + efficiency
4. `python run.py --benchmark-cutlass` — runs benchmark, caches results, confirms file written
5. `python run.py --dry-run` — optimization cycle now loads cached benchmark data and GPU Specialist produces benchmark-informed recommendations
6. `python run.py --detect` — system state still works (no regression)
