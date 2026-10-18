"""Console-capable frozen worker; GUI launches it with CREATE_NO_WINDOW."""
if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()  # Before dispatch: SDK spawn reuses this EXE.
    import sys
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            stream.reconfigure(encoding="utf-8", errors="replace")
    mode = sys.argv.pop(1) if len(sys.argv) > 1 else "--help"
    if mode == "--bridge":
        from aglass_vrc.gui_runner import main
    elif mode == "--key":
        from aglass_vrc.usbkey_runner import main
    elif mode == "--cli":
        from aglass_vrc.cli import main
    elif mode == "--self-test":
        from aglass_vrc.packaged_check import worker_check as main
    else:
        print("aGlass2OSC background helper. Launch aGlass2OSC.exe for the GUI.\n"
              "CLI: aGlass2OSC-worker.exe --cli --help\n"
              "USB Key: aGlass2OSC-worker.exe --key --help")
        raise SystemExit(0 if mode in ("--help", "-h") else 2)
    raise SystemExit(main())
