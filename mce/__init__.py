import sys

# Windows consoles and pipes default to the locale code page, so printing Hebrew or ✓/⚠️ would crash.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _excepthook(kind, err, tb):
    """Known failures (ffmpeg, the Premiere bridge) print one plain line; anything else keeps its traceback
    (Claude reads it to fix the problem) plus a pointer to the health check."""
    import traceback

    from .ff import FFError
    if issubclass(kind, (FFError, ConnectionError)) or getattr(err, "friendly", False):
        print(f"❌ {err}", file=sys.stderr)
        return
    if issubclass(kind, KeyboardInterrupt):
        print("\nStopped.", file=sys.stderr)
        return
    traceback.print_exception(kind, err, tb)
    print("❌ Unexpected error. If it keeps happening, run: uv run python setup/doctor.py", file=sys.stderr)


sys.excepthook = _excepthook
