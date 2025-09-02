"""Entry point for running Cadence AI as a module with `python -m cadence`."""

from dotenv import load_dotenv

from .cli import main

if __name__ == "__main__":
    load_dotenv()
    main()
