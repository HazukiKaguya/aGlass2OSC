"""Launch the aGlass2OSC desktop interface."""
if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        from aglass_vrc.packaged_check import gui_check
        gui_check(sys.argv[2])
    else:
        from aglass_vrc.gui import main
        main()
