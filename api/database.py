"""Conexao com o PostgreSQL (banco telemetria_amv) via psycopg2."""
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

from config import settings


@contextmanager
def get_db():
    """Context manager que entrega uma conexao com search_path ihm, public.

    Uso:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ...")
    """
    conn = psycopg2.connect(
        settings.DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SET search_path TO ihm, public")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
