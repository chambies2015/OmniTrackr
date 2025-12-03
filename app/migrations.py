"""
Database migrations for the OmniTrackr API.
Handles schema migrations and table creation.
"""
from sqlalchemy import inspect, text

from . import database
from .database import engine


def run_migrations():
    """Run all database migrations."""
    try:
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

        if inspector.has_table("movies"):
            existing_columns = {col["name"] for col in inspector.get_columns("movies")}
            if "review" not in existing_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE movies ADD COLUMN review VARCHAR"))
                    conn.commit()
            if "poster_url" not in existing_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE movies ADD COLUMN poster_url VARCHAR"))
                    conn.commit()
            
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

            if "creator" in tv_columns and "year_started" in tv_columns:
                with engine.connect() as conn:
                    conn.execute(text("CREATE TABLE tv_shows_backup AS SELECT * FROM tv_shows"))

                    conn.execute(text("DROP TABLE tv_shows"))

                    conn.execute(text("""
                        CREATE TABLE tv_shows (
                            id INTEGER PRIMARY KEY,
                            title VARCHAR,
                            year INTEGER,
                            seasons INTEGER,
                            episodes INTEGER,
                            rating FLOAT,
                            watched BOOLEAN DEFAULT 0,
                            review VARCHAR,
                            poster_url VARCHAR
                        )
                    """))

                    conn.execute(text("""
                        INSERT INTO tv_shows (id, title, year, seasons, episodes, rating, watched, review, poster_url)
                        SELECT id, title, year_started, seasons, episodes, rating, watched, review, NULL
                        FROM tv_shows_backup
                    """))

                    conn.execute(text("DROP TABLE tv_shows_backup"))

                    conn.commit()
                    print("Successfully migrated tv_shows table to new schema")
            else:
                if "poster_url" not in tv_columns:
                    with engine.connect() as conn:
                        conn.execute(text("ALTER TABLE tv_shows ADD COLUMN poster_url VARCHAR"))
                        conn.commit()
                
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

    except Exception as e:
        print(f"Migration warning: {e}")
        pass

