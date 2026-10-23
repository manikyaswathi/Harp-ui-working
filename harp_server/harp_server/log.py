"""
The HARP server's log: every TAPIS call (what was asked, how long it took, what TAPIS
answered), logins, submits and job status changes. It goes to the terminal running the
server and to <HARP_SERVER_DATA>/harp_server.log. Tokens are never logged.

HARP_LOG_LEVEL=DEBUG also logs the full TAPIS job requests.
"""

import logging
import os

log = logging.getLogger("harp")


def setup(data_dir):
    if getattr(log, "_harp_ready", False):
        return log
    log.setLevel(os.environ.get("HARP_LOG_LEVEL", "INFO").upper())
    log.propagate = False
    fmt = logging.Formatter("%(asctime)s %(levelname)-5s [harp] %(message)s", "%Y-%m-%d %H:%M:%S")
    handlers = [logging.StreamHandler()]
    try:
        os.makedirs(data_dir, exist_ok=True)
        handlers.append(logging.FileHandler(os.path.join(data_dir, "harp_server.log")))
    except OSError:
        pass
    for h in handlers:
        h.setFormatter(fmt)
        log.addHandler(h)
    log._harp_ready = True
    return log


def short(v, n=160):
    """A value as it goes in the log: file contents as their size, long text cut."""
    if isinstance(v, (bytes, bytearray)):
        return f"<{len(v)} bytes>"
    if isinstance(v, tuple) and len(v) == 2 and isinstance(v[1], (bytes, bytearray)):
        return f"<{v[0]}: {len(v[1])} bytes>"
    s = str(v)
    return s if len(s) <= n else s[:n] + "…"
