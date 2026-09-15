import json
import os

from cryptography.fernet import Fernet, MultiFernet
from sqlalchemy import LargeBinary
from sqlalchemy.types import TypeDecorator


def _load_fernet() -> MultiFernet:
    """Builds a MultiFernet from ENCRYPTION_KEY, which may hold one key
    (the original, backward-compatible format) or several comma-separated
    keys for gradual key rotation.

    New values are always encrypted with the FIRST key in the list.
    Decryption tries every key in order, so old rows keep working while
    ENCRYPTION_KEY still lists their (now-retired) key after the new one.
    Once every row has been re-saved under the new key (e.g. by re-entering
    each bot's token), the old key can be dropped from the list.
    """
    raw = os.getenv("ENCRYPTION_KEY")
    if not raw:
        raise ValueError(
            "ENCRYPTION_KEY is not set in .env. "
            "Generate a new key with the command below and put it in .env:\n"
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    keys = [part.strip() for part in raw.split(",") if part.strip()]
    if not keys:
        raise ValueError("ENCRYPTION_KEY is set but empty after parsing.")
    return MultiFernet([Fernet(key.encode()) for key in keys])


_fernet = _load_fernet()


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
