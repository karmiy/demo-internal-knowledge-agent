import argparse

from app.ingestion.worker import run_worker


def main() -> None:
    parser = argparse.ArgumentParser(description="Process pending knowledge documents")
    parser.add_argument("--once", action="store_true", help="process at most one document")
    args = parser.parse_args()
    run_worker(once=args.once)


if __name__ == "__main__":
    main()
