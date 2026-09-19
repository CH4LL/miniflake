from __future__ import annotations

from app.config import Settings


def connect_snowflake(settings: Settings):
    import snowflake.connector
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization

    key_bytes = settings.load_private_key_bytes()
    passphrase = settings.snowflake_private_key_passphrase
    private_key = serialization.load_pem_private_key(
        key_bytes,
        password=passphrase.encode() if passphrase else None,
        backend=default_backend(),
    )
    pkb = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return snowflake.connector.connect(
        account=settings.snowflake_account,
        user=settings.snowflake_user,
        role=settings.snowflake_role,
        warehouse=settings.snowflake_warehouse,
        database=settings.snowflake_database,
        schema=settings.snowflake_schema,
        private_key=pkb,
    )
