import json
import os

from cryptography.fernet import Fernet
from sqlalchemy import LargeBinary
from sqlalchemy.types import TypeDecorator


def _load_key() -> bytes:
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        raise ValueError(
            "ENCRYPTION_KEY is not set in .env. "
            "Generate a new key with the command below and put it in .env:\n"
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return key.encode()


_fernet = Fernet(_load_key())


class EncryptedJSON(TypeDecorator):
    """
    A column whose value is JSON-serialized and encrypted with Fernet
    (AES-128 in CBC mode + HMAC) before being stored in the database.
    Reading and writing is fully transparent to the rest of the code.
    """

    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        raw = json.dumps(value, ensure_ascii=False).encode("utf-8")
        return _fernet.encrypt(raw)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        raw = _fernet.decrypt(bytes(value))
        return json.loads(raw.decode("utf-8"))


class EncryptedString(TypeDecorator):
    """Same logic as EncryptedJSON but for plain text values like the bot token."""

    impl = LargeBinary
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _fernet.encrypt(value.encode("utf-8"))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return _fernet.decrypt(bytes(value)).decode("utf-8")
