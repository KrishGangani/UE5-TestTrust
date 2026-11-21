# Gate batch 2026-11-21_050350_gate-stored

Each cell: median across valid runs of each run's statistic, then [min-max].

| Config | Valid runs | GameThreadTime median (ms) | GameThreadTime p95 (ms) | FrameTime median (ms) | Injected median (ms) |
|---|---|---|---|---|---|
| X0 | 10 | 5.236 [4.853-5.480] | 6.529 [6.086-7.034] | 5.243 [4.866-5.485] | n/a |

Invalid runs (never judged): none.

Raw files: `Benchmarks/Raw/2026-11-21_050350_gate-stored_*`; environment and per-run statistics in `2026-11-21_050350_gate-stored_manifest.json`.

```json
{
 "date": "2026-11-21T05:03:50",
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
