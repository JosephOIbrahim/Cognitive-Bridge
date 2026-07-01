window.BENCHMARK_DATA = {
  "lastUpdate": 1782911698673,
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
      },
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
          "id": "a518d5f84f4535a32cce88c34c4f3ea3cb4d23c4",
          "message": "[bench] gate PRs on >2x regression + comment perf impact; main tracks only\n\nTwo-mode benchmark workflow:\n- push to main: update the published gh-pages baseline/history, alert-comment\n  on regression, never fail (runner noise can't red main).\n- pull_request: compare against the main baseline, comment the perf impact on\n  the PR, and fail the check on a >2x regression (the perf gate). PR runs do\n  not push to gh-pages, so they never pollute the baseline.\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>",
          "timestamp": "2026-07-01T09:14:23-04:00",
          "tree_id": "9bd60bc86c5c3542bba854891c17b58c04424bee",
          "url": "https://github.com/JosephOIbrahim/Cognitive-Bridge/commit/a518d5f84f4535a32cce88c34c4f3ea3cb4d23c4"
        },
        "date": 1782911698187,
        "tool": "pytest",
        "benches": [
          {
            "name": "benchmarks/test_bench_engine.py::test_resolve_50",
            "value": 10380.68574079457,
            "unit": "iter/sec",
            "range": "stddev: 0.000003137886420392748",
            "extra": "mean: 96.33274958610363 usec\nrounds: 3622"
          },
          {
            "name": "benchmarks/test_bench_engine.py::test_resolve_100",
            "value": 5229.183074401039,
            "unit": "iter/sec",
            "range": "stddev: 0.000004490433458863878",
            "extra": "mean: 191.23445971807786 usec\nrounds: 3550"
          },
          {
            "name": "benchmarks/test_bench_engine.py::test_resolve_500",
            "value": 740.2223305355278,
            "unit": "iter/sec",
            "range": "stddev: 0.001839310483842426",
            "extra": "mean: 1.3509454642857521 msec\nrounds: 504"
          },
          {
            "name": "benchmarks/test_bench_engine.py::test_resolve_shadow_stacks_100x3",
            "value": 2642.486325139186,
            "unit": "iter/sec",
            "range": "stddev: 0.0000068529453424810796",
            "extra": "mean: 378.43147587427063 usec\nrounds: 2259"
          },
          {
            "name": "benchmarks/test_bench_engine.py::test_structural_detection_500",
            "value": 16668.024885212504,
            "unit": "iter/sec",
            "range": "stddev: 0.0000027403721980036153",
            "extra": "mean: 59.99511081167016 usec\nrounds: 10387"
          },
          {
            "name": "benchmarks/test_bench_engine.py::test_cascade_50_dependents",
            "value": 1338.1124644486322,
            "unit": "iter/sec",
            "range": "stddev: 0.000016084091857573215",
            "extra": "mean: 747.321339998166 usec\nrounds: 50"
          },
          {
            "name": "benchmarks/test_bench_engine.py::test_trust_500_conflicts_50_paths",
            "value": 3550.93703115296,
            "unit": "iter/sec",
            "range": "stddev: 0.000006455548765036648",
            "extra": "mean: 281.6158076662115 usec\nrounds: 2948"
          },
          {
            "name": "benchmarks/test_bench_engine.py::test_red_team_200_locals",
            "value": 2892.4613758259757,
            "unit": "iter/sec",
            "range": "stddev: 0.000013668185404000507",
            "extra": "mean: 345.72631059401385 usec\nrounds: 2492"
          },
          {
            "name": "benchmarks/test_bench_engine.py::test_usda_export_100",
            "value": 1337.8123435967434,
            "unit": "iter/sec",
            "range": "stddev: 0.0001773748924061545",
            "extra": "mean: 747.4889918502873 usec\nrounds: 1227"
          },
          {
            "name": "benchmarks/test_bench_engine.py::test_usda_resolve_via_text_100",
            "value": 471.9189465868909,
            "unit": "iter/sec",
            "range": "stddev: 0.0001404547033020737",
            "extra": "mean: 2.1190079509042925 msec\nrounds: 387"
          }
        ]
      }
    ]
  }
}