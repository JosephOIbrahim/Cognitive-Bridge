"""SessionStart hook: check for running processes that might conflict.

Scans for running Houdini, Python pipeline, and Node.js processes
that could indicate a previous session's work is still active.
Outputs a reminder to Claude if any are found.
"""
import json
import subprocess
import sys


# Process names to check for (case-insensitive match on process name)
WATCH_PROCESSES = {
    "houdini.exe": "Houdini is running",
    "houdinifx.exe": "HoudiniFX is running",
    "hbatch.exe": "Houdini batch renderer is running",
    "karma.exe": "Karma renderer is running",
}

# Zombie bridge processes to auto-kill (these are safe to terminate --
# they're background bridges that will be restarted on demand)
ZOMBIE_PROCESSES = {
    "synapse_bridge": "Synapse MCP bridge",
    "mcp_bridge": "MCP bridge",
}


def main():
    try:
        # Get running processes via tasklist
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=5,
            encoding="utf-8", errors="replace"
        )
        if result.returncode != 0:
            sys.exit(0)

        running = []
        zombies_killed = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip().strip('"')
            if not line:
                continue
            proc_name = line.split('","')[0].strip('"').lower()
            proc_name_no_ext = proc_name.replace(".exe", "")
            if proc_name in WATCH_PROCESSES:
                running.append(WATCH_PROCESSES[proc_name])
            if proc_name_no_ext in ZOMBIE_PROCESSES:
                # Auto-kill zombie bridge processes
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/IM", proc_name],
                        capture_output=True, timeout=5
                    )
                    zombies_killed.append(ZOMBIE_PROCESSES[proc_name_no_ext])
                except Exception:
                    pass

        messages = []
        if zombies_killed:
            messages.append(
                "ZOMBIE CLEANUP: Killed stale processes: "
                + ", ".join(zombies_killed)
                + ". Fresh connections will be established on demand."
            )
        if running:
            messages.append(
                "PROCESS CHECK: The following are already running: "
                + ", ".join(running)
                + ". Check if these are from a previous session before "
                "starting new pipelines or renders."
            )
        if messages:
            print(" | ".join(messages))

    except Exception:
        # Don't block session start if check fails
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
