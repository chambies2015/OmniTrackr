<p align="center">
  <img width="256" height="256" alt="OmniTrackr logo" src="https://github.com/user-attachments/assets/baf5d9f6-bd5b-425a-be43-0ba675cb7a87" />
</p>

<h1 align="center">OmniTrackr</h1>

OmniTrackr is a free multi-user media tracker for movies, TV shows, anime, video games, music, and books. It combines private personal tracking, ratings, reviews, statistics, friends, public review pages, and JSON export/import in one browser-based dashboard.

Live site: [https://www.omnitrackr.xyz/](https://www.omnitrackr.xyz/)

## Highlights

- Track six built-in media categories: movies, TV shows, anime, video games, music, and books.
- Add ratings, long-form reviews, status fields, years, metadata, posters, cover art, and category-specific fields.
- Choose which individual reviews are public.
- Browse public reviews at `/reviews` and individual review detail pages.
- Use account privacy settings for movies, TV shows, anime, video games, music, books, and statistics.
- Customize visible tabs so users can hide categories they do not use.
- Add friends, manage friend requests, view privacy-aware friend profiles, and receive notifications.
- Create custom tabs for additional collection types with custom fields and optional poster uploads.
- Export and import JSON for built-in categories and custom tabs.
- View statistics for completion, ratings, years, directors, genres, TV/anime season data, music, books, and high-level library insights.
- Use public content pages for onboarding and discovery: `/about`, `/guides`, `/compare`, `/use-cases`, `/demo`, `/media-tracking`, `/tv-show-tracker`, `/game-tracker`, `/changelog`, `/roadmap`, `/privacy`, `/terms`, and `/contact`.
- Run with SQLite locally or PostgreSQL in production.

## Tech Stack

Backend:

- FastAPI
- SQLAlchemy
- Pydantic
- PostgreSQL in production, SQLite for local development
- python-jose JWT utilities
- bcrypt password hashing
- FastAPI-Mail and itsdangerous for email workflows
- Pillow for image validation and optimization
- SlowAPI for selected rate limits

Frontend:

- Vanilla JavaScript
- Server-rendered public pages
- Single-page authenticated dashboard
- Responsive CSS with light/dark theme support

Deployment:

- Render web service
- Render PostgreSQL
- Environment-based configuration

## Built-In Media Categories

OmniTrackr includes first-class CRUD flows for:

- Movies: title, director, year, rating, watched status, review, public-review toggle, poster.
- TV shows: title, year, seasons, episodes, rating, watched status, review, public-review toggle, poster.
- Anime: title, year, seasons, episodes, rating, watched status, review, public-review toggle, poster.
- Video games: title, release date, genres, rating, played status, review, public-review toggle, cover art, RAWG link.
- Music: title, artist, year, genre, rating, listened status, review, public-review toggle, cover art.
- Books: title, author, year, genre, rating, read status, review, public-review toggle, cover art.

Metadata sources:

- OMDB API for movie and TV metadata when configured.
- Jikan API for anime metadata.
- RAWG API for video game metadata when configured.
- iTunes Search API for music metadata.
- Open Library API for book metadata.

## Public Pages And SEO

The public site is more than a login screen. These pages help visitors, search engines, and policy reviewers understand what OmniTrackr provides:

- `/about` - product overview.
- `/guides` - step-by-step usage guide.
- `/compare` - comparison with spreadsheets and category-specific tracker apps.
- `/use-cases` - workflows for watchlists, reviews, privacy, friends, and backups.
- `/demo` - sample media library with fictional demo data.
- `/media-tracking` - hub linking the major guide pages.
- `/tv-show-tracker` and `/game-tracker` - category-specific tracker guides.
- `/reviews` - public user reviews when users choose to share individual reviews.
- `/changelog` - product, security, and content update history.
- `/roadmap` - planned improvements.
- `/privacy`, `/terms`, and `/contact` - policy and support pages.

SEO/security support includes sitemap, robots.txt, llms.txt, structured data, canonical links, page-specific metadata, favicon/image endpoints, and CSP nonce handling for public pages.

## Account And Privacy

Users can:

- Register, verify email, log in, log out, reset passwords, and reactivate eligible deactivated accounts.
- Change username, email, and password with appropriate verification.
- Upload profile pictures with file type, magic-byte, size, and image processing validation.
- Export account data at any time.
- Set category privacy for movies, TV shows, anime, video games, music, books, and statistics.
- Control which dashboard tabs are visible in their own interface.
- Use a Data & Privacy Dashboard inside account settings.

Public reviews are opt-in per item. A review is not public just because it exists in a user's private library.

## Friends And Notifications

The friends system supports:

- Sending, accepting, denying, and canceling friend requests.
- Auto-expiring friend requests.
- Viewing friends in a sidebar.
- Opening privacy-aware friend profiles.
- Receiving notification-bell updates for friend activity.

Friend profile access respects the other user's privacy settings.

## Custom Tabs

Custom tabs let users create additional collection types beyond the six built-in categories.

Supported custom-tab features include:

- Custom field definitions.
- Text, number, date, boolean, and rating-style fields.
- Optional required fields.
- Manual entry or selected API-backed source types.
- Optional poster uploads.
- Searchable custom-tab item lists.
- JSON export/import support.

Example uses include comics, podcasts, board games, collectibles, or niche watchlists.

## Export And Import

OmniTrackr exports user data as JSON with export metadata and lists for:

- Movies
- TV shows
- Anime
- Video games
- Music
- Books
- Custom tabs

Import supports backward-compatible JSON files and smart update behavior to reduce duplicates where matching records already exist.

## Security Notes

Current security measures include:

- Password hashing with bcrypt.
- JWT-based auth with production-only secure cookie behavior.
- Required production `SECRET_KEY`.
- Required production `DATABASE_URL`.
- Production CORS guard against wildcard origins.
- Security headers and CSP middleware.
- Parser-based CSP nonce/style handling for public HTML.
- Bot filtering for common scanner paths and suspicious user agents.
- Server-side proxying for OMDB and RAWG keys.
- Upload validation for profile pictures and custom-tab posters.
- Data isolation by authenticated user.
- Tests covering public-page CSP, URL handling, review rendering, static JS safety, and endpoint access patterns.

## Local Development

Requirements:

- Python 3.12
- A virtual environment
- SQLite for local development or PostgreSQL if you want to mirror production

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Create a `.env` file. For local SQLite development, this is enough:

```env
ENVIRONMENT=development
DATABASE_URL=sqlite:///./movies.db
SECRET_KEY=replace-with-a-local-development-secret
APP_URL=http://localhost:8000
SITE_URL=http://localhost:8000
ALLOWED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
```

Start the app:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open:

```text
http://127.0.0.1:8000/
```

## Environment Variables

Core:

| Variable | Required | Purpose |
| --- | --- | --- |
| `ENVIRONMENT` | Recommended | Use `production` on Render and `development` locally. |
| `DATABASE_URL` | Required in production | PostgreSQL URL in production, SQLite URL locally. |
| `SECRET_KEY` | Required in production | JWT and signed-token secret. |
| `APP_URL` | Recommended | Base URL used in email links. |
| `SITE_URL` | Recommended | Public site URL for sitemap, reviews, and SEO output. |
| `SITE_DOMAIN` | Optional | Domain used in seller/ads metadata. |
| `ALLOWED_ORIGINS` | Required in production | Comma-separated CORS allowlist. |

Email:

| Variable | Purpose |
| --- | --- |
| `MAIL_USERNAME` | SMTP username. |
| `MAIL_PASSWORD` | SMTP password or provider API key. |
| `MAIL_FROM` | Sender address. |
| `MAIL_PORT` | SMTP port, commonly `587` or `2525`. |
| `MAIL_SERVER` | SMTP host. |
| `MAIL_STARTTLS` | Usually `True`. |
| `MAIL_SSL_TLS` | Usually `False` for STARTTLS. |

External metadata:

| Variable | Purpose |
| --- | --- |
| `OMDB_API_KEY` | Optional movie/TV metadata and posters. |
| `RAWG_API_KEY` | Optional video game metadata and cover art. |

Public content and ads:

| Variable | Purpose |
| --- | --- |
| `ADSENSE_PUBLISHER_ID` | Publisher ID used by `ads.txt` and seller metadata. |
| `PUBLIC_REVIEW_MIN_CHARS` | Minimum review length for public review feeds. Defaults to `80`. |

iTunes Search API and Open Library API do not require keys.

## Testing

Run the full test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Useful focused runs:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_seo_security.py
.\.venv\Scripts\python.exe -m pytest tests\test_static_security.py
.\.venv\Scripts\python.exe -m pytest tests\test_statistics.py
```

## Deployment Notes

For Render:

- Use Python 3.12.
- Provide a PostgreSQL `DATABASE_URL`.
- Set `ENVIRONMENT=production`.
- Set a strong `SECRET_KEY`.
- Set `APP_URL` and `SITE_URL` to the production domain.
- Set `ALLOWED_ORIGINS` to the production origin, not `*`.
- Configure SMTP variables if email verification/password reset should send real email.
- Configure `OMDB_API_KEY` and `RAWG_API_KEY` if you want those metadata integrations enabled.

Database migrations are handled by the app startup migration helper in `app/migrations.py`.

## API Overview

Authenticated API areas include:

- `/auth/*`
- `/account/*`
- `/friends/*`
- `/notifications/*`
- `/movies/*`
- `/tv-shows/*`
- `/anime/*`
- `/video-games/*`
- `/music/*`
- `/books/*`
- `/statistics/*`
- `/custom-tabs/*`
- `/export/`
- `/import/`

Public endpoints include the landing page, public content pages, public reviews, SEO files, static assets, and selected image routes.

## Screenshots

<img width="1909" height="971" alt="OmniTrackr dashboard screenshot" src="https://github.com/user-attachments/assets/3ebb53c7-5cc3-4225-a028-2b3eb5dfbdb7" />
<img width="1909" height="968" alt="OmniTrackr collection screenshot" src="https://github.com/user-attachments/assets/f2debd1d-23bc-4c15-baac-f457c562d72a" />
<img width="1913" height="973" alt="OmniTrackr settings screenshot" src="https://github.com/user-attachments/assets/fd49c269-5402-46d8-a5c2-921fa48520f9" />
<img width="1913" height="973" alt="OmniTrackr statistics screenshot" src="https://github.com/user-attachments/assets/8abbd7a1-c81e-48aa-878b-624e3042ca22" />

## Support

For support, account questions, bug reports, privacy requests, or feature ideas, email:

```text
omnitrackr@gmail.com
```

You can also use the public contact page at `/contact`.

## License

No license file is currently included in this repository. Add one before distributing or accepting external contributions under defined terms.
