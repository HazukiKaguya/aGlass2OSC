"""aGlass DK I (vi-1) / DK II to VRChat native OSC. See docs/CLI.md."""
if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()  # Frozen SDK children reuse this executable.
    import sys
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            stream.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) > 1 and sys.argv[1] == "--key":
        sys.argv.pop(1)
        from aglass_vrc.usbkey_runner import main
    elif sys.argv[1:] == ["--self-test"]:
        from aglass_vrc.packaged_check import worker_check as main
    else:
        from aglass_vrc.cli import main
    raise SystemExit(main())
