"""
Database migrations for the OmniTrackr API.
Handles schema migrations and table creation.
"""
from sqlalchemy import inspect, text

from . import database, models
from .database import engine


MEDIA_TABLES = {
    "movies": models.Movie, "tv_shows": models.TVShow, "anime": models.Anime,
    "video_games": models.VideoGame, "music": models.Music, "books": models.Book,
}


class MigrationIntegrityError(RuntimeError):
    """An ambiguous or interrupted schema upgrade needs explicit recovery."""


def _restore_interrupted_sqlite_review_tables():
    """Restore the original table only for the prior rebuild's empty destination."""
    if engine.dialect.name != "sqlite":
        return
    tables = set(inspect(engine).get_table_names())
    candidates = [table for table in MEDIA_TABLES if table + "_old" in tables]
    if not candidates:
        return
    with engine.connect() as conn:
        try:
            # sqlite3's legacy transaction mode does not begin transactions for
            # DDL. An explicit transaction makes the drop/rename recoverable.
            conn.exec_driver_sql("BEGIN IMMEDIATE")
            for table in candidates:
                old = table + "_old"
                if table not in tables:
                    raise MigrationIntegrityError(f"Cannot safely restore {old}: its replacement is missing")
                inspector = inspect(conn)
                source = {column["name"]: column for column in inspector.get_columns(old)}
                target = {column["name"]: column for column in inspector.get_columns(table)}
                expected = set(MEDIA_TABLES[table].__table__.columns.keys())
                # The interrupted rebuild predates nullable added-at tracking.
                # Restore its complete source first; the normal column upgrade
                # below then leaves those historical dates unknown.
                required = expected - {"added_at"}
                recognized = (
                    required <= source.keys()
                    and set(target) - {"added_at"} in (required, required - {"review_public"})
                    and all(
                        "added_at" not in columns
                        or (columns["added_at"]["nullable"]
                            and str(columns["added_at"]["type"]).upper() in {"DATETIME", "TIMESTAMP"})
                        for columns in (source, target)
                    )
                    and "TEXT" not in str(source["review"]["type"]).upper()
                    and "TEXT" in str(target["review"]["type"]).upper()
                )
                if not recognized:
                    raise MigrationIntegrityError(f"Cannot safely restore {old}: unrecognized interrupted schema")
                if conn.exec_driver_sql(f'SELECT 1 FROM "{table}" LIMIT 1').first() is not None:
                    raise MigrationIntegrityError(f"Cannot safely restore {old}: replacement {table} has rows; ownership and ID conflicts require explicit recovery")
                if conn.exec_driver_sql("SELECT 1 FROM sqlite_schema WHERE type='trigger' AND tbl_name=? LIMIT 1", (table,)).first():
                    raise MigrationIntegrityError(f"Cannot safely restore {old}: replacement {table} has triggers")
                conn.exec_driver_sql(f'DROP TABLE "{table}"')
                # SQLite updates inbound FK and trigger references that the
                # original rename had redirected to the *_old table.
                conn.exec_driver_sql(f'ALTER TABLE "{old}" RENAME TO "{table}"')
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if isinstance(exc, MigrationIntegrityError):
                raise
            raise MigrationIntegrityError("Interrupted media-table restoration rolled back") from exc
    for table in candidates:
        print(f"Restored {table} from an interrupted review migration")


def _migrate_legacy_tv_columns():
    inspector = inspect(engine)
    if not inspector.has_table("tv_shows"):
        return
    columns = {column["name"] for column in inspector.get_columns("tv_shows")}
    if not {"creator", "year_started"} <= columns:
        return
    with engine.connect() as conn:
        try:
            if engine.dialect.name == "sqlite":
                conn.exec_driver_sql("BEGIN IMMEDIATE")
            if "year" in columns:
                raise MigrationIntegrityError("Legacy TV table contains both year and year_started; explicit recovery is required")
            if "user_id" not in columns:
                if conn.execute(text("SELECT 1 FROM tv_shows LIMIT 1")).first() is not None:
                    raise MigrationIntegrityError("Legacy TV rows have no user_id; explicit ownership assignment is required")
                conn.execute(text("ALTER TABLE tv_shows ADD COLUMN user_id INTEGER NOT NULL REFERENCES users(id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tv_shows_user_id ON tv_shows(user_id)"))
            # Renaming one column preserves every other column, FK, index,
            # privacy flag and nullable value instead of copying a short list.
            conn.execute(text("ALTER TABLE tv_shows RENAME COLUMN year_started TO year"))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if isinstance(exc, MigrationIntegrityError):
                raise
            raise MigrationIntegrityError("Legacy TV column migration rolled back") from exc
    print("Renamed legacy tv_shows.year_started to year")


def _migrate_review_column_types():
    # SQLite VARCHAR and TEXT both have TEXT affinity, with no VARCHAR length
    # restriction. Rebuilding a legacy table changes no storage behavior and
    # risks losing columns, indexes and references, so leave it intact.
    if engine.dialect.name == "sqlite":
        return
    for table in MEDIA_TABLES:
        inspector = inspect(engine)
        if not inspector.has_table(table):
            continue
        review = next((column for column in inspector.get_columns(table) if column["name"] == "review"), None)
        if review and "TEXT" not in str(review["type"]).upper():
            with engine.begin() as conn:
                conn.execute(text(f'ALTER TABLE "{table}" ALTER COLUMN review TYPE TEXT'))
            print(f"Migrated {table}.review to TEXT")


def run_migrations():
    """Run all database migrations."""
    try:
        _restore_interrupted_sqlite_review_tables()
        _migrate_legacy_tv_columns()
        inspector = inspect(engine)

        if inspector.has_table("users"):
            user_columns = {col["name"] for col in inspector.get_columns("users")}
            if "is_verified" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    print("Added is_verified column to users table")
            if "verification_token" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN verification_token VARCHAR"))
                    conn.commit()
                    print("Added verification_token column to users table")
            if "reset_token" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN reset_token VARCHAR"))
                    conn.commit()
                    print("Added reset_token column to users table")
            if "reset_token_expires" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN reset_token_expires TIMESTAMP"))
                    conn.commit()
                    print("Added reset_token_expires column to users table")
            if "created_at" not in user_columns:
                with engine.connect() as conn:
                    if database.DATABASE_URL.startswith("sqlite"):
                        conn.execute(text("ALTER TABLE users ADD COLUMN created_at TIMESTAMP"))
                        conn.execute(text("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
                    else:
                        conn.execute(text("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
                    conn.commit()
                    print("Added created_at column to users table")
            if "deactivated_at" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN deactivated_at TIMESTAMP"))
                    conn.commit()
                    print("Added deactivated_at column to users table")
            if "movies_private" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN movies_private BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    print("Added movies_private column to users table")
            if "tv_shows_private" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN tv_shows_private BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    print("Added tv_shows_private column to users table")
            if "anime_private" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN anime_private BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    print("Added anime_private column to users table")
            if "video_games_private" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN video_games_private BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    print("Added video_games_private column to users table")
            if "statistics_private" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN statistics_private BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    print("Added statistics_private column to users table")
            if "reviews_public" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN reviews_public BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    print("Added reviews_public column to users table")
            if "movies_visible" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN movies_visible BOOLEAN DEFAULT TRUE"))
                    conn.commit()
                    print("Added movies_visible column to users table")
            if "tv_shows_visible" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN tv_shows_visible BOOLEAN DEFAULT TRUE"))
                    conn.commit()
                    print("Added tv_shows_visible column to users table")
            if "anime_visible" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN anime_visible BOOLEAN DEFAULT TRUE"))
                    conn.commit()
                    print("Added anime_visible column to users table")
            if "video_games_visible" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN video_games_visible BOOLEAN DEFAULT TRUE"))
                    conn.commit()
                    print("Added video_games_visible column to users table")
            if "music_private" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN music_private BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    print("Added music_private column to users table")
            if "books_private" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN books_private BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    print("Added books_private column to users table")
            if "music_visible" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN music_visible BOOLEAN DEFAULT TRUE"))
                    conn.commit()
                    print("Added music_visible column to users table")
            if "books_visible" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN books_visible BOOLEAN DEFAULT TRUE"))
                    conn.commit()
                    print("Added books_visible column to users table")
            if "profile_picture_url" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN profile_picture_url VARCHAR"))
                    conn.commit()
                    print("Added profile_picture_url column to users table")
            if "profile_picture_data" not in user_columns:
                with engine.connect() as conn:
                    if database.DATABASE_URL.startswith("postgresql"):
                        conn.execute(text("ALTER TABLE users ADD COLUMN profile_picture_data BYTEA"))
                    else:
                        conn.execute(text("ALTER TABLE users ADD COLUMN profile_picture_data BLOB"))
                    conn.commit()
                    print("Added profile_picture_data column to users table")
            if "profile_picture_mime_type" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN profile_picture_mime_type VARCHAR"))
                    conn.commit()
                    print("Added profile_picture_mime_type column to users table")
            if "failed_login_attempts" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0"))
                    conn.commit()
                    print("Added failed_login_attempts column to users table")
            if "locked_until" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN locked_until TIMESTAMP"))
                    conn.commit()
                    print("Added locked_until column to users table")
            if "last_login_at" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP"))
                    conn.commit()
                    print("Added last_login_at column to users table")
            if "login_count" not in user_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN login_count INTEGER DEFAULT 0"))
                    conn.execute(text("UPDATE users SET login_count = 0 WHERE login_count IS NULL"))
                    conn.commit()
                    print("Added login_count column to users table")
            if database.DATABASE_URL.startswith("postgresql"):
                with engine.connect() as conn:
                    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_username ON users(username)"))
                    conn.commit()

        if inspector.has_table("collections"):
            collection_columns = {col["name"] for col in inspector.get_columns("collections")}
            if "is_public" not in collection_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE collections ADD COLUMN is_public BOOLEAN DEFAULT FALSE"))
                    conn.execute(text("UPDATE collections SET is_public = FALSE WHERE is_public IS NULL"))
                    conn.commit()
                    print("Added is_public column to collections table")
            if "published_at" not in collection_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE collections ADD COLUMN published_at TIMESTAMP"))
                    conn.commit()
                    print("Added published_at column to collections table")
            collection_additions = {
                "cover_url": "VARCHAR",
                "moderation_status": "VARCHAR DEFAULT 'pending'",
                "approved_at": "TIMESTAMP",
                "approved_content_hash": "VARCHAR",
                "view_count": "INTEGER DEFAULT 0",
                "helpful_count": "INTEGER DEFAULT 0",
                "report_count": "INTEGER DEFAULT 0",
                "report_content_hash": "VARCHAR",
                "suspended_at": "TIMESTAMP",
            }
            for column_name, column_type in collection_additions.items():
                if column_name not in collection_columns:
                    with engine.connect() as conn:
                        conn.execute(text(f"ALTER TABLE collections ADD COLUMN {column_name} {column_type}"))
                        conn.commit()
                        print(f"Added {column_name} column to collections table")
            with engine.connect() as conn:
                conn.execute(text("UPDATE collections SET moderation_status = 'pending' WHERE moderation_status IS NULL"))
                conn.execute(text("UPDATE collections SET view_count = 0 WHERE view_count IS NULL"))
                conn.execute(text("UPDATE collections SET helpful_count = 0 WHERE helpful_count IS NULL"))
                conn.execute(text("UPDATE collections SET report_count = 0 WHERE report_count IS NULL"))
                conn.commit()
            with engine.connect() as conn:
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_collections_is_public ON collections(is_public)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_collections_moderation_status ON collections(moderation_status)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_collections_suspended_at ON collections(suspended_at)"))
                conn.commit()

        if inspector.has_table("collection_items"):
            collection_item_columns = {col["name"] for col in inspector.get_columns("collection_items")}
            if "curator_note" not in collection_item_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE collection_items ADD COLUMN curator_note TEXT"))
                    conn.commit()
                    print("Added curator_note column to collection_items table")

        review_public_columns_added = set()

        if inspector.has_table("movies"):
            existing_columns = {col["name"] for col in inspector.get_columns("movies")}
            if "review" not in existing_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE movies ADD COLUMN review TEXT"))
                    conn.commit()
            if "poster_url" not in existing_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE movies ADD COLUMN poster_url VARCHAR"))
                    conn.commit()
            if "review_public" not in existing_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE movies ADD COLUMN review_public BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    print("Added review_public column to movies table")
                review_public_columns_added.add("movies")
            
            rating_column = next((col for col in inspector.get_columns("movies") if col["name"] == "rating"), None)
            if rating_column:
                if database.DATABASE_URL.startswith("postgresql"):
                    col_type = str(rating_column.get("type", "")).upper()
                    if "INT" in col_type and "FLOAT" not in col_type and "NUMERIC" not in col_type and "REAL" not in col_type:
                        try:
                            with engine.connect() as conn:
                                conn.execute(text("ALTER TABLE movies ALTER COLUMN rating TYPE FLOAT USING rating::float"))
                                conn.commit()
                                print("Converted movies.rating column from INTEGER to FLOAT")
                        except Exception as e:
                            print(f"Note: Could not convert movies.rating column type (may already be correct): {e}")

        if inspector.has_table("tv_shows"):
            tv_columns = {col["name"] for col in inspector.get_columns("tv_shows")}

            if "poster_url" not in tv_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE tv_shows ADD COLUMN poster_url VARCHAR"))
                    conn.commit()
            if "review_public" not in tv_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE tv_shows ADD COLUMN review_public BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    print("Added review_public column to tv_shows table")
                review_public_columns_added.add("tv_shows")

            rating_column = next((col for col in inspector.get_columns("tv_shows") if col["name"] == "rating"), None)
            if rating_column:
                if database.DATABASE_URL.startswith("postgresql"):
                    col_type = str(rating_column.get("type", "")).upper()
                    if "INT" in col_type and "FLOAT" not in col_type and "NUMERIC" not in col_type and "REAL" not in col_type:
                        try:
                            with engine.connect() as conn:
                                conn.execute(text("ALTER TABLE tv_shows ALTER COLUMN rating TYPE FLOAT USING rating::float"))
                                conn.commit()
                                print("Converted tv_shows.rating column from INTEGER to FLOAT")
                        except Exception as e:
                            print(f"Note: Could not convert tv_shows.rating column type (may already be correct): {e}")

        if not inspector.has_table("anime"):
            print("Anime table will be created by Base.metadata.create_all")
        else:
            anime_columns = {col["name"] for col in inspector.get_columns("anime")}
            if "poster_url" not in anime_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE anime ADD COLUMN poster_url VARCHAR"))
                    conn.commit()
                    print("Added poster_url column to anime table")
            if "review_public" not in anime_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE anime ADD COLUMN review_public BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    print("Added review_public column to anime table")
                review_public_columns_added.add("anime")
            
            rating_column = next((col for col in inspector.get_columns("anime") if col["name"] == "rating"), None)
            if rating_column:
                if database.DATABASE_URL.startswith("postgresql"):
                    col_type = str(rating_column.get("type", "")).upper()
                    if "INT" in col_type and "FLOAT" not in col_type and "NUMERIC" not in col_type and "REAL" not in col_type:
                        try:
                            with engine.connect() as conn:
                                conn.execute(text("ALTER TABLE anime ALTER COLUMN rating TYPE FLOAT USING rating::float"))
                                conn.commit()
                                print("Converted anime.rating column from INTEGER to FLOAT")
                        except Exception as e:
                            print(f"Note: Could not convert anime.rating column type (may already be correct): {e}")

        if not inspector.has_table("video_games"):
            print("Video games table will be created by Base.metadata.create_all")
        else:
            video_game_columns = {col["name"] for col in inspector.get_columns("video_games")}
            if "cover_art_url" not in video_game_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE video_games ADD COLUMN cover_art_url VARCHAR"))
                    conn.commit()
                    print("Added cover_art_url column to video_games table")
            if "rawg_link" not in video_game_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE video_games ADD COLUMN rawg_link VARCHAR"))
                    conn.commit()
                    print("Added rawg_link column to video_games table")
            if "genres" not in video_game_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE video_games ADD COLUMN genres VARCHAR"))
                    conn.commit()
                    print("Added genres column to video_games table")
            if "release_date" not in video_game_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE video_games ADD COLUMN release_date TIMESTAMP"))
                    conn.commit()
                    print("Added release_date column to video_games table")
            if "review_public" not in video_game_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE video_games ADD COLUMN review_public BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    print("Added review_public column to video_games table")
                review_public_columns_added.add("video_games")
            rating_column = next((col for col in inspector.get_columns("video_games") if col["name"] == "rating"), None)
            if rating_column:
                if database.DATABASE_URL.startswith("postgresql"):
                    col_type = str(rating_column.get("type", "")).upper()
                    if "INT" in col_type and "FLOAT" not in col_type and "NUMERIC" not in col_type and "REAL" not in col_type:
                        try:
                            with engine.connect() as conn:
                                conn.execute(text("ALTER TABLE video_games ALTER COLUMN rating TYPE FLOAT USING rating::float"))
                                conn.commit()
                                print("Converted video_games.rating column from INTEGER to FLOAT")
                        except Exception as e:
                            print(f"Note: Could not convert video_games.rating column type (may already be correct): {e}")

        if not inspector.has_table("music"):
            print("Music table will be created by Base.metadata.create_all")
        else:
            music_columns = {col["name"] for col in inspector.get_columns("music")}
            if "cover_art_url" not in music_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE music ADD COLUMN cover_art_url VARCHAR"))
                    conn.commit()
                    print("Added cover_art_url column to music table")
            if "review_public" not in music_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE music ADD COLUMN review_public BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    print("Added review_public column to music table")
                review_public_columns_added.add("music")
            rating_column = next((col for col in inspector.get_columns("music") if col["name"] == "rating"), None)
            if rating_column:
                if database.DATABASE_URL.startswith("postgresql"):
                    col_type = str(rating_column.get("type", "")).upper()
                    if "INT" in col_type and "FLOAT" not in col_type and "NUMERIC" not in col_type and "REAL" not in col_type:
                        try:
                            with engine.connect() as conn:
                                conn.execute(text("ALTER TABLE music ALTER COLUMN rating TYPE FLOAT USING rating::float"))
                                conn.commit()
                                print("Converted music.rating column from INTEGER to FLOAT")
                        except Exception as e:
                            print(f"Note: Could not convert music.rating column type (may already be correct): {e}")

        if not inspector.has_table("books"):
            print("Books table will be created by Base.metadata.create_all")
        else:
            book_columns = {col["name"] for col in inspector.get_columns("books")}
            if "cover_art_url" not in book_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE books ADD COLUMN cover_art_url VARCHAR"))
                    conn.commit()
                    print("Added cover_art_url column to books table")
            if "review_public" not in book_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE books ADD COLUMN review_public BOOLEAN DEFAULT FALSE"))
                    conn.commit()
                    print("Added review_public column to books table")
                review_public_columns_added.add("books")
            rating_column = next((col for col in inspector.get_columns("books") if col["name"] == "rating"), None)
            if rating_column:
                if database.DATABASE_URL.startswith("postgresql"):
                    col_type = str(rating_column.get("type", "")).upper()
                    if "INT" in col_type and "FLOAT" not in col_type and "NUMERIC" not in col_type and "REAL" not in col_type:
                        try:
                            with engine.connect() as conn:
                                conn.execute(text("ALTER TABLE books ALTER COLUMN rating TYPE FLOAT USING rating::float"))
                                conn.commit()
                                print("Converted books.rating column from INTEGER to FLOAT")
                        except Exception as e:
                            print(f"Note: Could not convert books.rating column type (may already be correct): {e}")

        if review_public_columns_added and inspector.has_table("users"):
            try:
                with engine.begin() as conn:
                    # Existing per-item false flags are an explicit privacy
                    # choice. Only initialize a column added in this run.
                    for table in sorted(review_public_columns_added):
                        conn.execute(text(f"""
                            UPDATE "{table}" SET review_public = TRUE WHERE user_id IN
                            (SELECT id FROM users WHERE reviews_public = TRUE)
                            AND review IS NOT NULL AND review != ''
                        """))
                print("Backfilled review_public for legacy public reviews")
            except Exception as e:
                print(f"Note: Could not backfill review_public values: {e}")

        if not inspector.has_table("friend_requests"):
            with engine.connect() as conn:
                if database.DATABASE_URL.startswith("postgresql"):
                    conn.execute(text("""
                        CREATE TABLE friend_requests (
                            id SERIAL PRIMARY KEY,
                            sender_id INTEGER NOT NULL REFERENCES users(id),
                            receiver_id INTEGER NOT NULL REFERENCES users(id),
                            status VARCHAR DEFAULT 'pending',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            expires_at TIMESTAMP NOT NULL
                        )
                    """))
                    conn.execute(text("CREATE INDEX ix_friend_requests_sender_id ON friend_requests(sender_id)"))
                    conn.execute(text("CREATE INDEX ix_friend_requests_receiver_id ON friend_requests(receiver_id)"))
                    conn.execute(text("CREATE INDEX ix_friend_requests_status ON friend_requests(status)"))
                else:
                    conn.execute(text("""
                        CREATE TABLE friend_requests (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            sender_id INTEGER NOT NULL REFERENCES users(id),
                            receiver_id INTEGER NOT NULL REFERENCES users(id),
                            status VARCHAR DEFAULT 'pending',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            expires_at TIMESTAMP NOT NULL
                        )
                    """))
                    conn.execute(text("CREATE INDEX ix_friend_requests_sender_id ON friend_requests(sender_id)"))
                    conn.execute(text("CREATE INDEX ix_friend_requests_receiver_id ON friend_requests(receiver_id)"))
                    conn.execute(text("CREATE INDEX ix_friend_requests_status ON friend_requests(status)"))
                conn.commit()
                print("Created friend_requests table")

        if not inspector.has_table("friendships"):
            with engine.connect() as conn:
                if database.DATABASE_URL.startswith("postgresql"):
                    conn.execute(text("""
                        CREATE TABLE friendships (
                            id SERIAL PRIMARY KEY,
                            user1_id INTEGER NOT NULL REFERENCES users(id),
                            user2_id INTEGER NOT NULL REFERENCES users(id),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            CONSTRAINT _friendship_uc UNIQUE (user1_id, user2_id)
                        )
                    """))
                    conn.execute(text("CREATE INDEX ix_friendships_user1_id ON friendships(user1_id)"))
                    conn.execute(text("CREATE INDEX ix_friendships_user2_id ON friendships(user2_id)"))
                else:
                    conn.execute(text("""
                        CREATE TABLE friendships (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user1_id INTEGER NOT NULL REFERENCES users(id),
                            user2_id INTEGER NOT NULL REFERENCES users(id),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(user1_id, user2_id)
                        )
                    """))
                    conn.execute(text("CREATE INDEX ix_friendships_user1_id ON friendships(user1_id)"))
                    conn.execute(text("CREATE INDEX ix_friendships_user2_id ON friendships(user2_id)"))
                conn.commit()
                print("Created friendships table")

        if not inspector.has_table("notifications"):
            with engine.connect() as conn:
                if database.DATABASE_URL.startswith("postgresql"):
                    conn.execute(text("""
                        CREATE TABLE notifications (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER NOT NULL REFERENCES users(id),
                            type VARCHAR NOT NULL,
                            message VARCHAR NOT NULL,
                            friend_request_id INTEGER REFERENCES friend_requests(id),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            read_at TIMESTAMP
                        )
                    """))
                    conn.execute(text("CREATE INDEX ix_notifications_user_id ON notifications(user_id)"))
                    conn.execute(text("CREATE INDEX ix_notifications_friend_request_id ON notifications(friend_request_id)"))
                    conn.execute(text("CREATE INDEX ix_notifications_created_at ON notifications(created_at)"))
                    conn.execute(text("CREATE INDEX ix_notifications_user_id_unread ON notifications(user_id) WHERE read_at IS NULL"))
                else:
                    conn.execute(text("""
                        CREATE TABLE notifications (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL REFERENCES users(id),
                            type VARCHAR NOT NULL,
                            message VARCHAR NOT NULL,
                            friend_request_id INTEGER REFERENCES friend_requests(id),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            read_at TIMESTAMP
                        )
                    """))
                    conn.execute(text("CREATE INDEX ix_notifications_user_id ON notifications(user_id)"))
                    conn.execute(text("CREATE INDEX ix_notifications_friend_request_id ON notifications(friend_request_id)"))
                    conn.execute(text("CREATE INDEX ix_notifications_created_at ON notifications(created_at)"))
                conn.commit()
                print("Created notifications table")

        if inspector.has_table("notifications") and database.DATABASE_URL.startswith("postgresql"):
            with engine.connect() as conn:
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_notifications_user_id_unread ON notifications(user_id) WHERE read_at IS NULL"))
                conn.commit()

        if not inspector.has_table("custom_tabs"):
            with engine.connect() as conn:
                if database.DATABASE_URL.startswith("postgresql"):
                    conn.execute(text("""
                        CREATE TABLE custom_tabs (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER NOT NULL REFERENCES users(id),
                            name VARCHAR NOT NULL,
                            slug VARCHAR NOT NULL,
                            source_type VARCHAR NOT NULL DEFAULT 'none',
                            allow_uploads BOOLEAN DEFAULT TRUE NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    conn.execute(text("CREATE INDEX ix_custom_tabs_user_id ON custom_tabs(user_id)"))
                    conn.execute(text("CREATE INDEX ix_custom_tabs_slug ON custom_tabs(slug)"))
                else:
                    conn.execute(text("""
                        CREATE TABLE custom_tabs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER NOT NULL REFERENCES users(id),
                            name VARCHAR NOT NULL,
                            slug VARCHAR NOT NULL,
                            source_type VARCHAR NOT NULL DEFAULT 'none',
                            allow_uploads BOOLEAN DEFAULT 1 NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    conn.execute(text("CREATE INDEX ix_custom_tabs_user_id ON custom_tabs(user_id)"))
                    conn.execute(text("CREATE INDEX ix_custom_tabs_slug ON custom_tabs(slug)"))
                conn.commit()
                print("Created custom_tabs table")

        if not inspector.has_table("custom_tab_fields"):
            with engine.connect() as conn:
                if database.DATABASE_URL.startswith("postgresql"):
                    conn.execute(text("""
                        CREATE TABLE custom_tab_fields (
                            id SERIAL PRIMARY KEY,
                            tab_id INTEGER NOT NULL REFERENCES custom_tabs(id),
                            key VARCHAR NOT NULL,
                            label VARCHAR NOT NULL,
                            field_type VARCHAR NOT NULL,
                            required BOOLEAN DEFAULT FALSE NOT NULL,
                            "order" INTEGER NOT NULL DEFAULT 0
                        )
                    """))
                    conn.execute(text("CREATE INDEX ix_custom_tab_fields_tab_id ON custom_tab_fields(tab_id)"))
                else:
                    conn.execute(text("""
                        CREATE TABLE custom_tab_fields (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            tab_id INTEGER NOT NULL REFERENCES custom_tabs(id),
                            key VARCHAR NOT NULL,
                            label VARCHAR NOT NULL,
                            field_type VARCHAR NOT NULL,
                            required BOOLEAN DEFAULT 0 NOT NULL,
                            "order" INTEGER NOT NULL DEFAULT 0
                        )
                    """))
                    conn.execute(text("CREATE INDEX ix_custom_tab_fields_tab_id ON custom_tab_fields(tab_id)"))
                conn.commit()
                print("Created custom_tab_fields table")

        if not inspector.has_table("custom_tab_items"):
            with engine.connect() as conn:
                if database.DATABASE_URL.startswith("postgresql"):
                    conn.execute(text("""
                        CREATE TABLE custom_tab_items (
                            id SERIAL PRIMARY KEY,
                            tab_id INTEGER NOT NULL REFERENCES custom_tabs(id),
                            title VARCHAR NOT NULL,
                            field_values TEXT,
                            poster_url VARCHAR,
                            poster_data BYTEA,
                            poster_mime_type VARCHAR,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    conn.execute(text("CREATE INDEX ix_custom_tab_items_tab_id ON custom_tab_items(tab_id)"))
                    conn.execute(text("CREATE INDEX ix_custom_tab_items_title ON custom_tab_items(title)"))
                else:
                    conn.execute(text("""
                        CREATE TABLE custom_tab_items (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            tab_id INTEGER NOT NULL REFERENCES custom_tabs(id),
                            title VARCHAR NOT NULL,
                            field_values TEXT,
                            poster_url VARCHAR,
                            poster_data BLOB,
                            poster_mime_type VARCHAR,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    conn.execute(text("CREATE INDEX ix_custom_tab_items_tab_id ON custom_tab_items(tab_id)"))
                    conn.execute(text("CREATE INDEX ix_custom_tab_items_title ON custom_tab_items(title)"))
                conn.commit()
                print("Created custom_tab_items table")

        _migrate_review_column_types()

        if inspector.has_table("activity_entries"):
            with engine.connect() as conn:
                conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_activity_entries_user_occurred_at "
                    "ON activity_entries(user_id, occurred_at)"
                ))
                conn.commit()

    except MigrationIntegrityError:
        # A partially restored/ambiguous library must not serve an empty or
        # conflicting replacement while hiding the source under another name.
        raise
    except Exception as e:
        print(f"Migration warning: {e}")
        pass

    add_library_added_at_columns()
    add_notification_link_column()


def add_notification_link_column():
    """Add a nullable link column to notifications. Existing rows keep NULL (no link)."""
    try:
        inspector = inspect(engine)
        if not inspector.has_table("notifications"):
            return
        if "link" in {col["name"] for col in inspector.get_columns("notifications")}:
            return
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE notifications ADD COLUMN link VARCHAR"))
            conn.commit()
            print("Added link column to notifications table")
    except Exception as e:
        print(f"Migration warning (notification link): {e}")


LIBRARY_TABLES = ("movies", "tv_shows", "anime", "video_games", "music", "books")


def add_library_added_at_columns():
    """Add a nullable added_at column to each library table.

    Existing rows keep NULL: their real add date was never recorded, so nothing
    is backfilled. New rows get a timestamp from the model default.
    """
    try:
        inspector = inspect(engine)
        for table in LIBRARY_TABLES:
            if not inspector.has_table(table):
                continue
            columns = {col["name"] for col in inspector.get_columns(table)}
            if "added_at" in columns:
                continue
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN added_at TIMESTAMP"))
                conn.commit()
                print(f"Added added_at column to {table} table")
    except Exception as e:
        print(f"Migration warning (added_at): {e}")

