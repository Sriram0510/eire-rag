"""Database connection helper shared by ingestion, search and (later) the API."""

import os

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector


def connect() -> psycopg.Connection:
    load_dotenv()
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)  # lets psycopg send/receive numpy arrays as pgvector values
    return conn