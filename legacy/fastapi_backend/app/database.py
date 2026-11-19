from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row


class Database:
    """Connect to PostgreSQL using the standard PG environment variables."""

    @contextmanager
    def connect(self) -> Iterator[psycopg.Connection]:
        with psycopg.connect(row_factory=dict_row, connect_timeout=10) as connection:
            yield connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS device_types (
                    id UUID PRIMARY KEY,
                    name TEXT NOT NULL CHECK (length(trim(name)) > 0)
                )
                """
            )
