window.BENCHMARK_DATA = {
  "lastUpdate": 1782911289619,
  "repoUrl": "https://github.com/JosephOIbrahim/Cognitive-Bridge",
  "entries": {
    "Cognitive Bridge engine benchmarks": [
      {
        "commit": {
          "author": {
            "email": "joseph@josephibrahim.com",
            "name": "Joseph Ibrahim"
          },
          "committer": {
            "email": "joseph@josephibrahim.com",
            "name": "Joseph Ibrahim"
          },
          "distinct": true,
          "id": "1ce2e523581400ee7edb25c2f5abb0fafe6e0158",
          "message": "[bench] add pytest-benchmark suite + published benchmark dashboard\n\nIntroduce a dedicated benchmarks/ suite (pytest-benchmark) over the engine\nhot paths — resolve() at 50/100/500, shadow stacks, structural detection,\ncascade, trust, red-team, and the USDA export/text-resolve round trip. It\nlives outside testpaths=[\"tests\"], so the merge gate never runs it.\n\nA new Benchmarks workflow runs on push to main and publishes the timing\nhistory to a GitHub Pages dashboard (dev/bench) via\nbenchmark-action/github-action-benchmark, commenting on >2x regressions\nwithout failing the build (the coarse guards in test_performance.py remain\nthe gate). Adds a bench extra and a benchmarks badge.\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>",
          "timestamp": "2026-07-01T09:07:25-04:00",
          "tree_id": "48e7772bc729b6d230d58037486844793d93f7ea",
          "url": "https://github.com/JosephOIbrahim/Cognitive-Bridge/commit/1ce2e523581400ee7edb25c2f5abb0fafe6e0158"
        },
        "date": 1782911288658,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/test_bench_engine.py::test_resolve_50",
            "value": 9615.64591133814,
            "unit": "iter/sec",
            "range": "stddev: 0.000009789078785882126",
            "extra": "mean: 103.99717389976533 usec\nrounds: 3318"
          },
          {
            "name": "benchmarks/test_bench_engine.py::test_resolve_100",
            "value": 4724.476023176859,
            "unit": "iter/sec",
            "range": "stddev: 0.000035336376380714175",
            "extra": "mean: 211.66368399253182 usec\nrounds: 3136"
          },
          {
            "name": "benchmarks/test_bench_engine.py::test_resolve_500",
            "value": 694.7527545156561,
            "unit": "iter/sec",
            "range": "stddev: 0.0015329424267930848",
            "extra": "mean: 1.4393609719433869 msec\nrounds: 499"
          },
          {
            "name": "benchmarks/test_bench_engine.py::test_resolve_shadow_stacks_100x3",
            "value": 2342.0975751754017,
            "unit": "iter/sec",
            "range": "stddev: 0.00007915687630817784",
            "extra": "mean: 426.9676936602904 usec\nrounds: 2161"
          },
          {
            "name": "benchmarks/test_bench_engine.py::test_structural_detection_500",
            "value": 13560.77661085831,
            "unit": "iter/sec",
            "range": "stddev: 0.00000542802302919063",
            "extra": "mean: 73.74208931362276 usec\nrounds: 9573"
          },
          {
            "name": "benchmarks/test_bench_engine.py::test_cascade_50_dependents",
            "value": 1157.0052677303916,
            "unit": "iter/sec",
            "range": "stddev: 0.000026835065122029947",
            "extra": "mean: 864.3002999991722 usec\nrounds: 50"
          },
          {
            "name": "benchmarks/test_bench_engine.py::test_trust_500_conflicts_50_paths",
            "value": 3117.423924676487,
            "unit": "iter/sec",
            "range": "stddev: 0.000022236681697888106",
            "extra": "mean: 320.7776754660584 usec\nrounds: 2576"
          },
          {
            "name": "benchmarks/test_bench_engine.py::test_red_team_200_locals",
            "value": 2549.0075275555264,
            "unit": "iter/sec",
            "range": "stddev: 0.000030230310931281705",
            "extra": "mean: 392.30955153709976 usec\nrounds: 2212"
          },
          {
            "name": "benchmarks/test_bench_engine.py::test_usda_export_100",
            "value": 811.6211331193149,
            "unit": "iter/sec",
            "range": "stddev: 0.0004898156316278979",
            "extra": "mean: 1.2321019736840586 msec\nrounds: 950"
          },
          {
            "name": "benchmarks/test_bench_engine.py::test_usda_resolve_via_text_100",
            "value": 421.33522127729725,
            "unit": "iter/sec",
            "range": "stddev: 0.0000687836757578625",
            "extra": "mean: 2.3734070865674455 msec\nrounds: 335"
          }
        ]
      }
    ]
  }
}