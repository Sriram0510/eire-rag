import os

import psycopg
from dotenv import load_dotenv

load_dotenv()  # reads .env into environment variables
conn_str = os.environ["DATABASE_URL"]  # crash loudly if missing

with psycopg.connect(conn_str) as conn:
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    distance = conn.execute(
        "SELECT '[1,2,3]'::vector <=> '[2,4,6]'::vector;"
    ).fetchone()[0]
    print(f"Connected. Cosine distance: {distance}")