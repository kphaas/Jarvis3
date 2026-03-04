# JARVIS-GENERATED: True
# Intent: create a python function that returns current system uptime in seconds
# Generated: 2026-03-04T18:40:20.024825+00:00
# Validated: syntax ✓ | lint ✓ | bandit ✓
# Human review: PENDING

def get_system_uptime():
    """
    Returns the current system uptime in seconds.
    """
    with open("/proc/uptime", "r") as f:
        uptime_seconds = float(f.readline().split()[0])
    return int(uptime_seconds)
