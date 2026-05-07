import sys


def main() -> None:
    from gitbroom.ui.app import run_app
    sys.exit(run_app())


if __name__ == "__main__":
    main()
