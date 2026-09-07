import asyncio

from .assisstant import run_assistant


def main() -> None:
    asyncio.run(run_assistant())
