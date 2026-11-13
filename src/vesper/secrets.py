import os

import keyring


def get_secret(name: str) -> str:
    value = os.environ.get(f"{name.upper()}_API_KEY") or keyring.get_password(
        "vesper", "name"
    )
    if not value:
        raise RuntimeError(
            f"No secret named {name!r}: set it in the keyring or the environment"
        )
    return value
