"""P03 TestTrust - helpers shared by the mutation runner and the perf-gate scripts.

Copied and adapted from UE5-UpdateBudget's Tools/run_bench.py (never imported across repositories):
  - performance_core_mask(): the P-core affinity mask of this hybrid CPU;
  - environment_record(): the facts recorded with every batch.
Added here: pinned() (wrap a command line so it runs on the P-cores) and sanitize() (no personal paths in a file
that is committed).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import struct
import subprocess

ENGINE_ROOT = r"C:\Program Files\Epic Games\UE_5.8"
ENGINE_BUILD_VERSION = os.path.join(ENGINE_ROOT, "Engine", "Build", "Build.version")


def performance_core_mask() -> int | None:
    """Affinity mask of the performance cores on a hybrid CPU; None on a non-hybrid CPU or if Windows can't say.

    Why: on this i7-14650HX (8 P-cores + 8 E-cores), UE5-UpdateBudget's baseline batch showed runs at two stable
    levels about 1.6x apart, and one run that stepped between them mid-capture: Windows had placed the game thread
    on an E-core. Pinning the process to the P-cores gives every run what a foreground game normally gets.
    Source of truth: GetLogicalProcessorInformationEx(RelationProcessorCore) reports an EfficiencyClass per physical
    core; the P-cores have the higher class. Only processor group 0 exists on a machine with < 64 logical CPUs.
    """
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
    except (ImportError, AttributeError):
        return None
    length = ctypes.c_ulong(0)
    kernel32.GetLogicalProcessorInformationEx(0, None, ctypes.byref(length))
    buffer = ctypes.create_string_buffer(length.value)
    if not length.value or not kernel32.GetLogicalProcessorInformationEx(0, buffer, ctypes.byref(length)):
        return None
    raw, offset, cores = buffer.raw, 0, []
    while offset < length.value:
        relationship, size = struct.unpack_from("<II", raw, offset)
        if relationship == 0 and size >= 48:                            # RelationProcessorCore
            efficiency_class = raw[offset + 9]                          # PROCESSOR_RELATIONSHIP.EfficiencyClass
            mask, group = struct.unpack_from("<QH", raw, offset + 32)   # GroupMask[0]: KAFFINITY Mask, WORD Group
            if group == 0:
                cores.append((efficiency_class, mask))
        offset += size
    classes = {efficiency for efficiency, _ in cores}
    if len(classes) < 2:
        return None
    best = max(classes)
    combined = 0
    for efficiency, mask in cores:
        if efficiency == best:
            combined |= mask
    return combined


PERFORMANCE_CORE_MASK = performance_core_mask()


def pin_self(mask: int) -> bool:
    """Restricts THIS process to the CPUs in mask; every process it starts afterwards inherits the mask from its
    first instruction. Copied from UE5-UpdateBudget's run_bench.py. Meant for a benchmark script whose every child is
    a timed run (the Phase 5 gate script). The mutation runner does NOT use it: it also starts builds, which must keep
    all 24 logical CPUs, so it pins each test launch separately with pinned() instead."""
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.SetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    return bool(kernel32.SetProcessAffinityMask(kernel32.GetCurrentProcess(), mask))


def applied_mask() -> str:
    """The affinity this process actually has, read back from Windows (copied from UE5-UpdateBudget's run_bench.py)."""
    import ctypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.GetProcessAffinityMask.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
                                                ctypes.POINTER(ctypes.c_size_t)]
    process_mask, system_mask = ctypes.c_size_t(0), ctypes.c_size_t(0)
    kernel32.GetProcessAffinityMask(kernel32.GetCurrentProcess(), ctypes.byref(process_mask), ctypes.byref(system_mask))
    if process_mask.value == system_mask.value:
        return f"0x{process_mask.value:X} (all logical processors)"
    return f"0x{process_mask.value:X} (performance cores only; hybrid CPU)"


def pinned(command: str, console: bool = False) -> str:
    """Wraps one command string so the process (and its children, which inherit the mask) runs on the P-cores.

    `start /wait` makes cmd wait for the program. The empty "" is start's window title, without which a quoted
    program path would be taken as the title. For a console program (UnrealEditor-Cmd), `/B` keeps it in our
    console, so its output reaches our log instead of a new window.

    Exit code: a plain `cmd /c start "" /wait ...` returns 0 whatever the program returned (tested 2026-11-21 with a
    program exiting 3 and -1: both gave 0). `start` does set ERRORLEVEL, so the command ends with
    `& exit !errorlevel!` under delayed expansion (`/v:on`; `%errorlevel%` would be expanded before start runs), and
    `/s` makes cmd strip exactly the outer pair of quotes. Tested: 3 -> 3, -1 -> 4294967295, quoted arguments intact.
    """
    if PERFORMANCE_CORE_MASK is None:
        return command
    same_console = "/B " if console else ""
    return f'cmd /v:on /s /c "start "" {same_console}/wait /affinity {PERFORMANCE_CORE_MASK:X} {command} & exit !errorlevel!"'


def affinity_description() -> str:
    if PERFORMANCE_CORE_MASK is None:
        return "all logical processors"
    return f"0x{PERFORMANCE_CORE_MASK:X} (performance cores only; hybrid CPU)"


def sanitize(text: str) -> str:
    """Replaces the user's profile path, so a committed manifest never contains a personal path."""
    home = os.path.expanduser("~")
    return text.replace(home, "%USERPROFILE%").replace(home.replace("\\", "/"), "%USERPROFILE%")


def powershell(command: str) -> str:
    result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True)
    return result.stdout.strip()


def environment_record(build_config: str, extra: dict | None = None) -> dict:
    """Facts that must accompany every batch (Benchmarks/README.md, environment record)."""
    with open(ENGINE_BUILD_VERSION, encoding="utf-8") as handle:
        build = json.load(handle)
    record = {
        "date": dt.datetime.now().isoformat(timespec="seconds"),
        "engine": f"{build['MajorVersion']}.{build['MinorVersion']}.{build['PatchVersion']} (CL {build['Changelist']})",
        "build_config": build_config,
        "compiler": "MSVC 14.44.35229, Windows SDK 10.0.22621.0",
        "cpu": powershell("(Get-CimInstance Win32_Processor).Name"),
        "gpus": powershell("(Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name + ' (driver ' + $_.DriverVersion + ')' }) -join '; '"),
        "ram_gb": powershell("[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)"),
        "os": powershell("$o=Get-CimInstance Win32_OperatingSystem; $o.Caption + ' build ' + $o.BuildNumber"),
        "power_plan": powershell("powercfg /getactivescheme"),
        "on_ac_power": powershell("(Get-CimInstance Win32_Battery | Select-Object -First 1).BatteryStatus") == "2",
        "cpu_affinity": affinity_description(),
    }
    record.update(extra or {})
    return record
