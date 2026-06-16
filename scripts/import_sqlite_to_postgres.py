#!/usr/bin/env python3
import argparse
import json
import sqlite3
from pathlib import Path

import psycopg2
from psycopg2.extras import Json


def load_json(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def table_exists(conn, table_name):
    row = conn.execute(
        "select name from sqlite_master where type = 'table' and name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def sqlite_columns(conn, table_name):
    return [row[1] for row in conn.execute(f"pragma table_info({table_name})")]


def import_sites(sqlite_conn, pg_conn):
    if not table_exists(sqlite_conn, "sites"):
        return 0

    columns = sqlite_columns(sqlite_conn, "sites")
    rows = sqlite_conn.execute("select * from sites").fetchall()
    count = 0

    with pg_conn.cursor() as cur:
        for row in rows:
            data = dict(zip(columns, row))
            cur.execute(
                """
                insert into sites (
                    id, url, name, list_rules, content_rules,
                    consecutive_failure_count, refresh_frequency
                )
                values (%s, %s, %s, %s, %s, %s, %s)
                on conflict (id) do update set
                    url = excluded.url,
                    name = excluded.name,
                    list_rules = excluded.list_rules,
                    content_rules = excluded.content_rules,
                    consecutive_failure_count = excluded.consecutive_failure_count,
                    refresh_frequency = excluded.refresh_frequency
                """,
                (
                    data.get("id"),
                    data.get("url"),
                    data.get("name"),
                    Json(load_json(data.get("list_rules"))),
                    Json(load_json(data.get("content_rules"))),
                    data.get("consecutive_failure_count", 0) or 0,
                    data.get("refresh_frequency", 60) or 60,
                ),
            )
            count += 1

        cur.execute(
            "select setval(pg_get_serial_sequence('sites', 'id'), coalesce(max(id), 1), true) from sites"
        )

    return count


def import_articles(sqlite_conn, pg_conn):
    if not table_exists(sqlite_conn, "articles"):
        return 0

    columns = sqlite_columns(sqlite_conn, "articles")
    rows = sqlite_conn.execute("select * from articles").fetchall()
    count = 0

    with pg_conn.cursor() as cur:
        for row in rows:
            data = dict(zip(columns, row))
            cur.execute(
                """
                insert into articles (
                    id, site_id, title, url, content, image_url, published_at
                )
                values (%s, %s, %s, %s, %s, %s, %s)
                on conflict (url) do update set
                    site_id = excluded.site_id,
                    title = excluded.title,
                    content = excluded.content,
                    image_url = excluded.image_url,
                    published_at = excluded.published_at
                """,
                (
                    data.get("id"),
                    data.get("site_id"),
                    data.get("title"),
                    data.get("url"),
                    data.get("content"),
                    data.get("image_url"),
                    data.get("published_at"),
                ),
            )
            count += 1

        cur.execute(
            "select setval(pg_get_serial_sequence('articles', 'id'), coalesce(max(id), 1), true) from articles"
        )

    return count


def main():
    parser = argparse.ArgumentParser(
        description="Import legacy palimpsest SQLite sites/articles into PostgreSQL."
    )
    parser.add_argument("sqlite_db", type=Path)
    parser.add_argument(
        "--postgres-url",
        default="postgresql://palimpsest:palimpsest@localhost:5432/palimpsest",
    )
    args = parser.parse_args()

    if not args.sqlite_db.is_file():
        raise SystemExit(f"SQLite DB not found: {args.sqlite_db}")

    sqlite_conn = sqlite3.connect(args.sqlite_db)
    pg_conn = psycopg2.connect(args.postgres_url)

    try:
        site_count = import_sites(sqlite_conn, pg_conn)
        article_count = import_articles(sqlite_conn, pg_conn)
        pg_conn.commit()
    finally:
        sqlite_conn.close()
        pg_conn.close()

    print(f"Imported {site_count} sites and {article_count} articles.")


if __name__ == "__main__":
    main()
