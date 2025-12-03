"""
CRUD operations for the OmniTrackr API.
Re-exports all CRUD functions for backward compatibility.
"""
# User CRUD operations
from .users import (
    get_user_by_username,
    get_user_by_email,
    get_user_by_username_or_email,
    get_user_by_id,
    create_user,
    update_user,
    deactivate_user,
    reactivate_user,
    update_privacy_settings,
    get_privacy_settings,
    update_tab_visibility,
    get_tab_visibility,
    update_profile_picture,
    reset_profile_picture,
)

# Movie CRUD operations
from .movies import (
    get_movies,
    get_movie_by_id,
    create_movie,
    update_movie,
    delete_movie,
)

# TV Show CRUD operations
from .tv_shows import (
    get_tv_shows,
    get_tv_show_by_id,
    create_tv_show,
    update_tv_show,
    delete_tv_show,
)

# Anime CRUD operations
from .anime import (
    get_anime,
    get_anime_by_id,
    create_anime,
    update_anime,
    delete_anime,
)

# Video Game CRUD operations
from .video_games import (
    get_video_games,
    get_video_game_by_id,
    create_video_game,
    update_video_game,
    delete_video_game,
)

# Export/Import operations
from .export_import import (
    get_all_movies,
    get_all_tv_shows,
    get_all_anime,
    get_all_video_games,
    find_movie_by_title_and_director,
    find_tv_show_by_title_and_year,
    find_anime_by_title_and_year,
    find_video_game_by_title_and_release_date,
    import_movies,
    import_tv_shows,
    import_anime,
    import_video_games,
)

# Statistics operations
from .statistics import (
    get_watch_statistics,
    get_rating_statistics,
    get_year_statistics,
    get_director_statistics,
)

# Friends, Friend Requests, Notifications, and Friend Profile operations
from .friends import (
    create_friend_request,
    get_friend_request,
    get_friend_requests_by_user,
    accept_friend_request,
    deny_friend_request,
    cancel_friend_request,
    expire_friend_requests,
    create_friendship,
    get_friends,
    are_friends,
    remove_friendship,
    create_notification,
    get_notifications,
    get_unread_notification_count,
    mark_notification_read,
    delete_notification,
    get_friend_profile_summary,
    get_friend_movies,
    get_friend_tv_shows,
    get_friend_anime,
    get_friend_video_games,
    get_friend_statistics,
)

__all__ = [
    # User operations
    "get_user_by_username",
    "get_user_by_email",
    "get_user_by_username_or_email",
    "get_user_by_id",
    "create_user",
    "update_user",
    "deactivate_user",
    "reactivate_user",
    "update_privacy_settings",
    "get_privacy_settings",
    "update_tab_visibility",
    "get_tab_visibility",
    "update_profile_picture",
    "reset_profile_picture",
    # Movie operations
    "get_movies",
    "get_movie_by_id",
    "create_movie",
    "update_movie",
    "delete_movie",
    # TV Show operations
    "get_tv_shows",
    "get_tv_show_by_id",
    "create_tv_show",
    "update_tv_show",
    "delete_tv_show",
    # Anime operations
    "get_anime",
    "get_anime_by_id",
    "create_anime",
    "update_anime",
    "delete_anime",
    # Video Game operations
    "get_video_games",
    "get_video_game_by_id",
    "create_video_game",
    "update_video_game",
    "delete_video_game",
    # Export/Import operations
    "get_all_movies",
    "get_all_tv_shows",
    "get_all_anime",
    "get_all_video_games",
    "find_movie_by_title_and_director",
    "find_tv_show_by_title_and_year",
    "find_anime_by_title_and_year",
    "find_video_game_by_title_and_release_date",
    "import_movies",
    "import_tv_shows",
    "import_anime",
    "import_video_games",
    # Statistics operations
    "get_watch_statistics",
    "get_rating_statistics",
    "get_year_statistics",
    "get_director_statistics",
    # Friends operations
    "create_friend_request",
    "get_friend_request",
    "get_friend_requests_by_user",
    "accept_friend_request",
    "deny_friend_request",
    "cancel_friend_request",
    "expire_friend_requests",
    "create_friendship",
    "get_friends",
    "are_friends",
    "remove_friendship",
    # Notification operations
    "create_notification",
    "get_notifications",
    "get_unread_notification_count",
    "mark_notification_read",
    "delete_notification",
    # Friend Profile operations
    "get_friend_profile_summary",
    "get_friend_movies",
    "get_friend_tv_shows",
    "get_friend_anime",
    "get_friend_video_games",
    "get_friend_statistics",
]

