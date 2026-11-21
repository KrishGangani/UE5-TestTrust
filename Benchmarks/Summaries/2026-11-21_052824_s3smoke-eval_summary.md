# Gate batch 2026-11-21_052824_s3smoke-eval

Each cell: median across valid runs of each run's statistic, then [min-max].

| Config | Valid runs | GameThreadTime median (ms) | GameThreadTime p95 (ms) | FrameTime median (ms) | Injected median (ms) |
|---|---|---|---|---|---|
| X0 | 4 | 4.893 [4.849-4.953] | 6.668 [5.688-6.785] | 4.906 [4.860-4.956] | n/a |
| X025 | 4 | 5.287 [5.167-5.368] | 7.126 [6.238-7.449] | 5.277 [5.188-5.370] | 0.250 [0.250-0.250] |
| X05 | 4 | 5.331 [5.315-5.544] | 6.333 [6.118-6.625] | 5.346 [5.316-5.543] | 0.500 [0.500-0.500] |
| X10 | 4 | 5.889 [5.826-5.987] | 6.569 [6.464-6.917] | 5.920 [5.856-6.023] | 1.000 [1.000-1.000] |

Invalid runs (never judged): none.

Raw files: `Benchmarks/Raw/2026-11-21_052824_s3smoke-eval_*`; environment and per-run statistics in `2026-11-21_052824_s3smoke-eval_manifest.json`.

```json
{
 "date": "2026-11-21T05:28:24",
 "engine": "5.8.4 (CL 58902052)",
 "build_config": "Development (packaged)",
 "compiler": "MSVC 14.44.35229, Windows SDK 10.0.22621.0",
 "cpu": "Intel(R) Core(TM) i7-14650HX",
 "gpus": "Intel(R) UHD Graphics (driver 32.0.101.7088); NVIDIA GeForce RTX 5070 Laptop GPU (driver 32.0.16.1047)",
 "ram_gb": "31.6",
 "os": "Microsoft Windows 11 Home Single Language build 26200",
 "power_plan": "Power Scheme GUID: 6fecc5ae-f350-48a5-b669-b472cb895ccf  (Turbo)",
 "on_ac_power": true,
 "cpu_affinity": "0xFFFF (performance cores only; hybrid CPU)",
 "common_args": "-windowed -ResX=1280 -ResY=720 -nosound -unattended -traceautostart=0 -deterministic -FPS=60 -novsync -csvStartOnEvent=BenchStart -csvStopOnEvent=BenchEnd -TTProbe -TTExit",
 "resolution": "1280x720 windowed, default scalability"
}
```
