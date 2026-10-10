"""Startup migrations must preserve media data, privacy, and SQLite schema objects."""
import pytest
from sqlalchemy import Column, MetaData, String, Text, create_engine, event, inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable
from types import SimpleNamespace

from app import migrations, models
from app.database import Base


MEDIA = [models.Movie, models.TVShow, models.Anime, models.VideoGame, models.Music, models.Book]


@pytest.fixture
def migration_engine(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'migration.db').as_posix()}")

    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    monkeypatch.setattr(migrations, "engine", engine)
    monkeypatch.setattr(migrations.database, "DATABASE_URL", str(engine.url))
    yield engine
    engine.dispose()


def create_schema(engine, legacy_model=None, *, omit_privacy=False, old_tv=False, no_owner=False, omit_added_at=False):
    omitted = legacy_model.__table__ if legacy_model else None
    Base.metadata.create_all(engine, tables=[table for table in Base.metadata.sorted_tables if table is not omitted])
    if legacy_model:
        metadata = MetaData()
        models.User.__table__.to_metadata(metadata)
        legacy = legacy_model.__table__.to_metadata(metadata)
        legacy.c.review.type = String(255)
        if omit_privacy:
            legacy._columns.remove(legacy.c.review_public)
        if omit_added_at:
            legacy._columns.remove(legacy.c.added_at)
        if old_tv:
            legacy.c.year.name = "year_started"
            legacy.append_column(Column("creator", String))
        if no_owner:
            for constraint in list(legacy.constraints):
                if "user_id" in constraint.columns:
                    legacy.constraints.remove(constraint)
            for index in list(legacy.indexes):
                if "user_id" in index.columns:
                    legacy.indexes.remove(index)
            legacy._columns.remove(legacy.c.user_id)
        legacy.create(engine)
    with Session(engine) as db:
        user = models.User(username="migration", email="migration@example.invalid", hashed_password="unused", reviews_public=True)
        db.add(user)
        db.commit()
        user_id = user.id
    with engine.begin() as connection:
        for model in MEDIA:
            table = model.__tablename__
            columns = {column["name"] for column in inspect(connection).get_columns(table)}
            values = {"id": 17, "user_id": user_id, "title": table, "review": "Preserved review " * 1000, "rating": 0}
            if "user_id" not in columns:
                values.pop("user_id")
            if "review_public" in columns:
                values["review_public"] = False
            for column in ("director", "artist", "author", "year", "year_started", "seasons", "episodes", "release_date", "genre", "genres", "cover_art_url", "rawg_link"):
                if column in columns:
                    values[column] = None
            if "poster_url" in columns:
                values["poster_url"] = "/preserved.jpg"
            names = ", ".join(f'"{key}"' for key in values)
            binds = ", ".join(f":{key}" for key in values)
            connection.execute(text(f'INSERT INTO "{table}" ({names}) VALUES ({binds})'), values)
    return user_id


def snapshot(engine, table):
    inspector = inspect(engine)
    with engine.connect() as connection:
        return {
            "columns": [(column["name"], str(column["type"]), column["nullable"], column["default"], column["primary_key"]) for column in inspector.get_columns(table)],
            "indexes": sorted((index["name"], tuple(index["column_names"]), index["unique"]) for index in inspector.get_indexes(table)),
            "foreign_keys": [(tuple(key["constrained_columns"]), key["referred_table"], tuple(key["referred_columns"]), key["options"]) for key in inspector.get_foreign_keys(table)],
            "rows": [tuple(row) for row in connection.execute(text(f'SELECT * FROM "{table}" ORDER BY id'))],
        }


def test_fresh_models_use_text_reviews():
    assert all(isinstance(model.__table__.c.review.type, Text) for model in MEDIA)


def test_fresh_schema_startup_preserves_rows_indexes_and_privacy(migration_engine, capsys):
    engine = migration_engine
    create_schema(engine)
    before = {model.__tablename__: snapshot(engine, model.__tablename__) for model in MEDIA}
    for _ in range(2):
        migrations.run_migrations()
        assert {model.__tablename__: snapshot(engine, model.__tablename__) for model in MEDIA} == before
        assert not any(name.endswith("_old") for name in inspect(engine).get_table_names())
    assert "Migration warning" not in capsys.readouterr().out


@pytest.mark.parametrize("model", MEDIA, ids=lambda model: model.__tablename__)
def test_legacy_sqlite_varchar_reviews_keep_complete_schema(migration_engine, capsys, model):
    engine, table = migration_engine, model.__tablename__
    create_schema(engine, model)
    with engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE TABLE migration_child (id INTEGER PRIMARY KEY, item_id INTEGER REFERENCES "{table}"(id))')
        connection.exec_driver_sql('INSERT INTO migration_child VALUES (1, 17)')
        connection.exec_driver_sql('CREATE TABLE migration_log (item_id INTEGER)')
        connection.exec_driver_sql(f'CREATE TRIGGER migration_review_log AFTER UPDATE OF review ON "{table}" BEGIN INSERT INTO migration_log VALUES (new.id); END')
    before = snapshot(engine, table)
    for _ in range(2):
        migrations.run_migrations()
        assert snapshot(engine, table) == before
        with engine.connect() as connection:
            assert connection.exec_driver_sql('PRAGMA foreign_key_check').all() == []
            assert connection.exec_driver_sql(f'PRAGMA foreign_key_list(migration_child)').one()[2] == table
    with engine.begin() as connection:
        connection.execute(text(f'UPDATE "{table}" SET review=:review WHERE id=17'), {"review": "Long legacy review " * 20000})
        assert connection.exec_driver_sql('SELECT item_id FROM migration_log').all() == [(17,)]
        assert connection.exec_driver_sql(f'SELECT length(review) FROM "{table}"').scalar_one() > 255
    assert "Migration warning" not in capsys.readouterr().out


@pytest.mark.parametrize("model", MEDIA, ids=lambda model: model.__tablename__)
def test_one_new_privacy_column_does_not_republish_other_categories(migration_engine, model):
    engine = migration_engine
    create_schema(engine, model, omit_privacy=True)
    migrations.run_migrations()
    with engine.connect() as connection:
        for candidate in MEDIA:
            public = connection.exec_driver_sql(f'SELECT review_public FROM "{candidate.__tablename__}" WHERE id=17').scalar_one()
            assert bool(public) is (candidate is model)
    migrations.run_migrations()
    with engine.connect() as connection:
        assert connection.exec_driver_sql(f'SELECT review_public FROM "{model.__tablename__}" WHERE id=17').scalar_one() == 1


def test_legacy_tv_year_rename_preserves_owner_privacy_and_metadata(migration_engine):
    engine = migration_engine
    owner_id = create_schema(engine, models.TVShow, old_tv=True)
    with engine.begin() as connection:
        connection.exec_driver_sql('CREATE TABLE migration_child (id INTEGER PRIMARY KEY, item_id INTEGER REFERENCES tv_shows(id))')
        connection.exec_driver_sql('INSERT INTO migration_child VALUES (1, 17)')
    before = snapshot(engine, "tv_shows")
    migrations.run_migrations()
    after = snapshot(engine, "tv_shows")
    assert after["rows"] == before["rows"]
    assert after["indexes"] == before["indexes"]
    assert after["foreign_keys"] == before["foreign_keys"]
    assert "year" in {column[0] for column in after["columns"]}
    assert "year_started" not in {column[0] for column in after["columns"]}
    with engine.connect() as connection:
        assert connection.exec_driver_sql('SELECT user_id, review_public, poster_url FROM tv_shows').one() == (owner_id, 0, "/preserved.jpg")
        assert connection.exec_driver_sql('PRAGMA foreign_key_check').all() == []
        assert connection.exec_driver_sql('PRAGMA foreign_key_list(migration_child)').one()[2] == "tv_shows"
    migrations.run_migrations()
    assert snapshot(engine, "tv_shows") == after


def interrupt_old_rebuild(engine, model, *, omit_added_at=False):
    table = model.__tablename__
    expected = snapshot(engine, table)
    metadata = MetaData()
    models.User.__table__.to_metadata(metadata)
    replacement = model.__table__.to_metadata(metadata)
    replacement.c.review.type = Text()
    replacement._columns.remove(replacement.c.review_public)
    if omit_added_at:
        replacement._columns.remove(replacement.c.added_at)
    with engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE TABLE migration_child (id INTEGER PRIMARY KEY, item_id INTEGER REFERENCES "{table}"(id))')
        connection.exec_driver_sql('INSERT INTO migration_child VALUES (1, 17)')
        connection.exec_driver_sql(f'ALTER TABLE "{table}" RENAME TO "{table}_old"')
        # The prior migration fails while adding indexes because the renamed
        # source retains their globally unique names; the destination is empty.
        connection.execute(CreateTable(replacement))
    return expected


@pytest.mark.parametrize("model", MEDIA, ids=lambda model: model.__tablename__)
def test_interrupted_empty_review_rebuild_restores_source_atomically(migration_engine, model):
    engine, table = migration_engine, model.__tablename__
    create_schema(engine, model)
    expected = interrupt_old_rebuild(engine, model)
    migrations.run_migrations()
    assert snapshot(engine, table) == expected
    assert table + "_old" not in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.exec_driver_sql('PRAGMA foreign_key_check').all() == []
        assert connection.exec_driver_sql('PRAGMA foreign_key_list(migration_child)').one()[2] == table
    migrations.run_migrations()
    assert snapshot(engine, table) == expected


@pytest.mark.parametrize("model", MEDIA, ids=lambda model: model.__tablename__)
@pytest.mark.parametrize("replacement_has_added_at", [False, True])
def test_pre_added_at_interrupted_rebuild_restores_data_before_nullable_upgrade(
    migration_engine, model, replacement_has_added_at,
):
    engine, table = migration_engine, model.__tablename__
    create_schema(engine, model, omit_added_at=True)
    expected = interrupt_old_rebuild(engine, model, omit_added_at=not replacement_has_added_at)
    migrations.run_migrations()
    actual = snapshot(engine, table)
    assert actual["columns"][:-1] == expected["columns"]
    assert actual["columns"][-1] == ("added_at", "TIMESTAMP", True, None, 0)
    assert [row[:-1] for row in actual["rows"]] == expected["rows"]
    assert all(row[-1] is None for row in actual["rows"])
    assert actual["indexes"] == expected["indexes"]
    assert actual["foreign_keys"] == expected["foreign_keys"]
    assert table + "_old" not in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        assert connection.exec_driver_sql("PRAGMA foreign_key_list(migration_child)").one()[2] == table
    migrations.run_migrations()
    assert snapshot(engine, table) == actual


def test_restoration_keeps_extra_original_columns_and_indexes(migration_engine):
    engine = migration_engine
    create_schema(engine, models.Movie)
    with engine.begin() as connection:
        connection.exec_driver_sql('ALTER TABLE movies ADD COLUMN import_metadata TEXT')
        connection.exec_driver_sql("UPDATE movies SET import_metadata='preserved edition metadata'")
        connection.exec_driver_sql('CREATE UNIQUE INDEX migration_edition ON movies(user_id, title, id)')
        connection.exec_driver_sql('CREATE TABLE migration_log (item_id INTEGER)')
        connection.exec_driver_sql('CREATE TRIGGER migration_review_log AFTER UPDATE OF review ON movies BEGIN INSERT INTO migration_log VALUES (new.id); END')
    expected = interrupt_old_rebuild(engine, models.Movie)
    migrations.run_migrations()
    assert snapshot(engine, "movies") == expected
    with engine.begin() as connection:
        connection.exec_driver_sql("UPDATE movies SET review='after restoration' WHERE id=17")
        assert connection.exec_driver_sql('SELECT item_id FROM migration_log').all() == [(17,)]


def test_restoration_ddl_failure_rolls_back_both_tables(migration_engine):
    engine = migration_engine
    create_schema(engine, models.VideoGame)
    interrupt_old_rebuild(engine, models.VideoGame)
    before = {table: snapshot(engine, table) for table in ("video_games", "video_games_old")}

    def fail_after_drop(connection, cursor, statement, parameters, context, executemany):
        if statement == 'ALTER TABLE "video_games_old" RENAME TO "video_games"':
            raise RuntimeError("simulated migration failure after DROP")

    event.listen(engine, "before_cursor_execute", fail_after_drop)
    try:
        with pytest.raises(migrations.MigrationIntegrityError, match="rolled back"):
            migrations.run_migrations()
    finally:
        event.remove(engine, "before_cursor_execute", fail_after_drop)
    assert {table: snapshot(engine, table) for table in before} == before
    with engine.connect() as connection:
        assert connection.exec_driver_sql('PRAGMA foreign_key_check').all() == []
        assert connection.exec_driver_sql('PRAGMA foreign_key_list(migration_child)').one()[2] == "video_games_old"
    migrations.run_migrations()
    assert "video_games_old" not in inspect(engine).get_table_names()


@pytest.mark.parametrize("model", MEDIA, ids=lambda model: model.__tablename__)
def test_conflicting_restoration_fails_without_mutating_either_table(migration_engine, model):
    engine, table = migration_engine, model.__tablename__
    owner_id = create_schema(engine, model)
    interrupt_old_rebuild(engine, model)
    with engine.begin() as connection:
        connection.execute(text(f'INSERT INTO "{table}" (id, user_id, title, review) VALUES (17, :owner, :title, :review)'), {"owner": owner_id, "title": "Conflicting new entry", "review": "New library content"})
    before = {name: snapshot(engine, name) for name in (table, table + "_old")}
    with pytest.raises(migrations.MigrationIntegrityError, match="has rows"):
        migrations.run_migrations()
    assert {name: snapshot(engine, name) for name in before} == before


def test_legacy_tv_without_owner_requires_assignment_without_data_changes(migration_engine):
    engine = migration_engine
    create_schema(engine, models.TVShow, old_tv=True, no_owner=True)
    before = snapshot(engine, "tv_shows")
    with pytest.raises(migrations.MigrationIntegrityError, match="ownership assignment"):
        migrations.run_migrations()
    assert snapshot(engine, "tv_shows") == before
    assert "tv_shows_backup" not in inspect(engine).get_table_names()


def test_empty_legacy_tv_can_add_owner_and_keep_schema(migration_engine):
    engine = migration_engine
    create_schema(engine, models.TVShow, old_tv=True, no_owner=True)
    with engine.begin() as connection:
        connection.exec_driver_sql('DELETE FROM tv_shows')
    migrations.run_migrations()
    columns = {column["name"]: column for column in inspect(engine).get_columns("tv_shows")}
    assert not columns["user_id"]["nullable"]
    assert "year" in columns and "year_started" not in columns
    assert "creator" in columns and "review_public" in columns
    assert inspect(engine).get_foreign_keys("tv_shows")[0]["referred_table"] == "users"
    before = snapshot(engine, "tv_shows")
    migrations.run_migrations()
    assert snapshot(engine, "tv_shows") == before


def test_postgresql_review_type_upgrade_covers_all_six_and_is_idempotent(monkeypatch):
    converted, statements = set(), []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, statement):
            sql = str(statement)
            statements.append(sql)
            converted.add(next(table for table in migrations.MEDIA_TABLES if f'"{table}"' in sql))

    inspector = SimpleNamespace(has_table=lambda table: True, get_columns=lambda table: [{"name": "review", "type": Text() if table in converted else String(255)}])
    monkeypatch.setattr(migrations, "engine", SimpleNamespace(dialect=SimpleNamespace(name="postgresql"), begin=Connection))
    monkeypatch.setattr(migrations, "inspect", lambda engine: inspector)
    migrations._migrate_review_column_types()
    assert converted == set(migrations.MEDIA_TABLES)
    assert len(statements) == 6
    migrations._migrate_review_column_types()
    assert len(statements) == 6
