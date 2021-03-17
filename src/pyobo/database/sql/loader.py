# -*- coding: utf-8 -*-

"""Upload the Ooh Na Na nomenclature database to PostgreSQL.

After installing with pip, run with: ``pyobo database sql load``.
This will take care of downloading the latest data from Zenodo (you
might need to set up an API key) and loading it into a SQL database.
Use ``--help`` for options on configuration.
"""

import gzip
import io
import logging
import time
from contextlib import closing
from textwrap import dedent

import click
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from tabulate import tabulate

logger = logging.getLogger(__name__)


def echo(s, **kwargs) -> None:
    """Wrap echo with time logging."""
    click.echo(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] ', nl='')
    click.secho(s, **kwargs)


#: Number of test rows if --test is used
TEST_N = 1_000_000


def load(uri: str, refs_table: str, refs_path: str, alts_table: str, alts_path: str, test: bool):
    """Load the database.

    :param uri:
    :param refs_table:
    :param refs_path:
    :param alts_table:
    :param alts_path:
    :param test:
    :return:
    """
    logger.debug('connecting to database %s', uri)
    engine: Engine = create_engine(uri)

    _load_names(
        engine=engine,
        table=alts_table,
        path=alts_path,
        test=test,
        target_col='alt',
        target_col_size=64,
        add_unique_constraints=False,
    )
    with engine.begin() as connection:
        connection.execute(f'CREATE INDEX ON {alts_table} (prefix, alt);')

    _load_names(
        engine=engine,
        table=refs_table,
        path=refs_path,
        test=test,
        target_col='name',
        target_col_size=4096,
    )


def _load_names(
    engine: Engine,
    table: str,
    path: str,
    test: bool,
    target_col: str,
    target_col_size: int,
    add_unique_constraints: bool = True,
    use_md5: bool = False,
) -> None:
    drop_statement = f'DROP TABLE IF EXISTS {table};'

    if use_md5:
        md5_ddl = "md5_hash VARCHAR(32) GENERATED ALWAYS AS (md5(prefix || ':' || identifier)) STORED,"
    else:
        md5_ddl = ''

    create_statement = dedent(f'''\
    CREATE TABLE {table} (
        id           SERIAL,  /* automatically the primary key */
        prefix       VARCHAR(32) NOT NULL,
        identifier   VARCHAR(64) NOT NULL,
        {md5_ddl}
        {target_col} VARCHAR({target_col_size}) NOT NULL  /* largest name's length is 2936 characters */
    ) WITH (
        autovacuum_enabled = false,
        toast.autovacuum_enabled = false
    );
    ''').rstrip()

    copy_statement = dedent(f'''\
    COPY {table} (prefix, identifier, {target_col})
    FROM STDIN
    WITH CSV HEADER DELIMITER E'\\t' QUOTE E'\\b';
    ''').rstrip()

    cleanup_statement = dedent(f'''\
    ALTER TABLE {table} SET (
        autovacuum_enabled = true,
        toast.autovacuum_enabled = true
    );
    ''').rstrip()

    index_curie_statement = f'CREATE INDEX ON {table} (prefix, identifier);'
    index_md5_statement = f'CREATE INDEX ON {table} (md5_hash);'

    unique_curie_stmt = dedent(f'''\
    ALTER TABLE {table}
        ADD CONSTRAINT {table}_prefix_identifier_unique UNIQUE (prefix, identifier);
    ''').rstrip()

    unique_md5_hash_stmt = dedent(f'''\
    ALTER TABLE {table}
        ADD CONSTRAINT {table}_md5_hash_unique UNIQUE (md5_hash);
    ''').rstrip()

    with closing(engine.raw_connection()) as connection:
        with closing(connection.cursor()) as cursor:
            echo('Preparing blank slate')
            echo(drop_statement, fg='yellow')
            cursor.execute(drop_statement)

            echo('Creating table')
            echo(create_statement, fg='yellow')
            cursor.execute(create_statement)

            echo('Start COPY')
            echo(copy_statement, fg='yellow')
            try:
                with gzip.open(path, 'rt') as file:
                    if test:
                        echo(f'Loading testing data (rows={TEST_N}) from {path}')
                        sio = io.StringIO(''.join(line for line, _ in zip(file, range(TEST_N))))
                        sio.seek(0)
                        cursor.copy_expert(copy_statement, sio)
                    else:
                        echo(f'Loading data from {path}')
                        cursor.copy_expert(copy_statement, file)
            except Exception:
                echo('Copy failed')
                raise
            else:
                echo('Copy ended')

            try:
                connection.commit()
            except Exception:
                echo('Commit failed')
                raise
            else:
                echo('Commit ended')

            echo('Start re-enable autovacuum')
            echo(cleanup_statement, fg='yellow')
            cursor.execute(cleanup_statement)
            echo('End re-enable autovacuum')

            echo('Start index on prefix/identifier')
            echo(index_curie_statement, fg='yellow')
            cursor.execute(index_curie_statement)
            echo('End indexing')

            if use_md5:
                echo('Start index on MD5 hash')
                echo(index_md5_statement, fg='yellow')
                cursor.execute(index_md5_statement)
                echo('End indexing')

            if add_unique_constraints:
                echo('Start unique on prefix/identifier')
                echo(unique_curie_stmt, fg='yellow')
                cursor.execute(unique_curie_stmt)
                echo('End unique')

            if add_unique_constraints and use_md5:
                echo('Start unique on md5_hash')
                echo(unique_md5_hash_stmt, fg='yellow')
                cursor.execute(unique_md5_hash_stmt)
                echo('End unique')

    with closing(engine.raw_connection()) as connection:
        connection.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with connection.cursor() as cursor:
            sql = f"VACUUM ANALYSE {table}"
            echo(sql, fg='yellow')
            cursor.execute(sql)

    with engine.connect() as connection:
        select_statement = f"SELECT * FROM {table} LIMIT 10;"  # noqa:S608
        click.secho('Example query:', fg='green', bold=True)
        click.secho(select_statement, fg='green')
        result = connection.execute(select_statement)
        if use_md5:
            headers = ['id', 'prefix', 'identifier', target_col, 'md5_hash']
        else:
            headers = ['id', 'prefix', 'identifier', target_col]
        click.echo(tabulate(map(tuple, result), headers=headers))
