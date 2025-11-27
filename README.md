<p align="center">
<img width="256" height="256" alt="omnitrackr_256x256" src="https://github.com/user-attachments/assets/baf5d9f6-bd5b-425a-be43-0ba675cb7a87" />
</p>

<h1 align="center">OmniTrackr</h1>

## Overview

OmniTrackr is a full-featured, multi-user web application for managing and tracking movies and TV shows. Originally a local desktop app, it has evolved into a production-ready platform with user authentication, cloud database support, and a modern responsive UI.

**Live Demo:** Deployed on Render with PostgreSQL database: https://www.omnitrackr.xyz/

## Tech Stack

**Backend:**
- FastAPI (Python web framework)
- SQLAlchemy (ORM)
- PostgreSQL (Database)
- JWT (Authentication)
- bcrypt (Password hashing)
- python-jose (JWT tokens)
- Pydantic (Data validation)

**Frontend:**
- Vanilla JavaScript (No framework dependencies)
- Single-page application architecture
- Responsive CSS with dark mode support

**Deployment:**
- Render (Web hosting & PostgreSQL)
- Environment-based configuration

## Features

### Core Functionality
- **Multi-user support:** User registration, login, and isolated data per user
- **JWT Authentication:** Secure token-based authentication system
- **Email Verification:** Required email verification before account access
- **Password Reset:** Secure token-based password reset functionality
- **Password Security:** bcrypt hashing for password storage
- **CRUD API:** Full REST API for managing movies and TV shows
- **PostgreSQL Database:** Production-ready database
- **Search and Sort:** Filter by title/director and sort by rating or year
- **Modern UI:** Responsive single-page application with dark mode by default, modern card-based design, and beautiful landing page
- **Poster Integration:** Automatic poster fetching from OMDB API with intelligent caching to reduce API calls
- **Decimal Ratings:** Support for precise ratings from 0-10.0 with one decimal place (e.g., 7.5, 8.4)
- **Export/Import:** JSON export/import with smart conflict resolution
- **Statistics Dashboard:** Comprehensive analytics with animated visualizations, watch progress, rating distributions, year analysis, and director insights
- **SEO Optimized:** Meta tags, structured data, sitemap, and robots.txt for better search engine visibility
- **Security:** Security headers, bot filtering, and comprehensive protection against common web vulnerabilities


## Export/Import Functionality

OmniTrackr now includes powerful export/import capabilities:

### Exporting Data
- Click the **"Export Data"** button in either the Movies or TV Shows tab
- Your entire collection will be downloaded as a JSON file with timestamp
- The export includes all metadata: titles, directors, years, ratings, reviews, watched status, and poster URLs
- Export files are named `omnitrackr-export-YYYY-MM-DD.json`

### Importing Data
- Click the **"Import Data"** button in either tab to select a JSON file
- The system will automatically detect and import movies and TV shows
- **Smart conflict resolution**: Existing entries (matched by title + director for movies, title + year for TV shows) will be updated rather than duplicated
- Import results show how many items were created vs updated
- Any errors during import are reported for easy troubleshooting

### API Endpoints
The export/import functionality is also available via API:
- `GET /export/` - Export all data as JSON
- `POST /import/` - Import data from JSON payload
- `POST /import/file/` - Import data from uploaded JSON file

## Statistics Dashboard

OmniTrackr includes a comprehensive statistics dashboard accessible via the **📊 Statistics** tab:

### Watch Progress Analytics
- **Total items** in your collection (movies + TV shows)
- **Watched vs. unwatched** counts and percentages
- **Visual progress bar** showing completion status
- **Separate tracking** for movies and TV shows

### Rating Analysis
- **Average rating** across all rated items (supports decimal ratings 0-10.0)
- **Rating distribution** with interactive animated bar charts (1-10 scale, rounded for visualization)
- **Highest and lowest rated items** showing your top and bottom-rated movies and TV shows
- **Visual representation** of your rating patterns with modern gradient designs

### Year Analysis
- **Oldest and newest** years in your collection
- **Decade breakdown** with bar charts showing distribution across decades
- **Year-based insights** to understand your viewing preferences over time

### Director Statistics
- **Most prolific directors** (directors with the most movies in your collection)
- **Highest rated directors** (directors with the best average ratings)
- **Director insights** to discover your favorite filmmakers

### API Endpoints
The statistics are also available via API:
- `GET /statistics/` - Complete statistics dashboard
- `GET /statistics/watch/` - Watch progress statistics
- `GET /statistics/ratings/` - Rating analysis
- `GET /statistics/years/` - Year-based statistics
- `GET /statistics/directors/` - Director statistics

## Authentication System

OmniTrackr uses a secure JWT-based authentication system:

### User Registration
- Email validation and uniqueness check
- Username uniqueness check
- Password hashing with bcrypt
- Email verification required before login
- Verification email sent upon registration

### Email Verification
- Secure token-based email verification
- Verification link sent to registered email
- Resend verification email functionality
- Users must verify email before accessing the application

### Login/Logout
- Supports login with username or email
- Email verification required for login
- JWT tokens stored in localStorage
- 7-day token expiration
- Secure logout with session clearing

### Password Reset
- Secure token-based password reset
- Reset link sent to registered email
- Token expiration for security
- Users can reset forgotten passwords

### API Security
- All endpoints (except `/auth/register`, `/auth/login`, `/auth/verify-email`, `/auth/request-password-reset`, and `/auth/reset-password`) require authentication
- JWT tokens sent in Authorization header
- User data isolation - users can only access their own data
- Automatic token validation and 401 handling

## Using the Application

### Getting Started
1. **Register/Login:** Create an account or log in with existing credentials
2. **Your Personal Collection:** All your data is private and isolated to your account

### Features
- **User Authentication:** Secure login with JWT tokens, logout functionality
- **Add movies & TV shows:** Enter details like title, director/creator, year, rating, and watched status
- **Automatic Posters:** Movie/TV posters are fetched automatically from OMDB and cached
- **Search & Filter:** Search by title or director/creator and sort by rating or year
- **Inline Editing:** Edit entries directly in the table with save/cancel options
- **Delete:** Remove entries from your collection
- **Dark Mode:** Beautiful dark theme by default with light mode toggle
- **Modern UI:** Card-based design with smooth animations and gradients
- **Tabbed Interface:** Switch between Movies, TV Shows, and Statistics
- **Export/Import:** Backup your collection to JSON or import from JSON files
- **Statistics Dashboard:** Comprehensive analytics with animated visualizations showing your viewing habits and preferences

### API Access
Interactive API documentation is available at `/docs` with full Swagger UI for testing all endpoints.

## API Endpoints Overview

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login and receive JWT token
- `GET /auth/verify-email` - Verify email address with token
- `POST /auth/resend-verification` - Resend verification email
- `POST /auth/request-password-reset` - Request password reset email
- `POST /auth/reset-password` - Reset password with token

### Movies
- `GET /movies/` - List all movies (with search & sort)
- `POST /movies/` - Create new movie
- `GET /movies/{id}` - Get specific movie
- `PUT /movies/{id}` - Update movie
- `DELETE /movies/{id}` - Delete movie

### TV Shows
- `GET /tv-shows/` - List all TV shows (with search & sort)
- `POST /tv-shows/` - Create new TV show
- `GET /tv-shows/{id}` - Get specific TV show
- `PUT /tv-shows/{id}` - Update TV show
- `DELETE /tv-shows/{id}` - Delete TV show

### Data Management
- `GET /export/` - Export all user data to JSON
- `POST /import/` - Import from JSON payload
- `POST /import/file/` - Import from uploaded JSON file

### Statistics
- `GET /statistics/` - Complete statistics dashboard
- `GET /statistics/watch/` - Watch progress stats
- `GET /statistics/ratings/` - Rating analysis
- `GET /statistics/years/` - Year-based stats
- `GET /statistics/directors/` - Director stats

All endpoints (except authentication) require a valid JWT token in the Authorization header.

## Screenshots
<img width="3030" height="1896" alt="image" src="https://github.com/user-attachments/assets/1d4bde27-5cc4-413a-8013-0577fc901f8e" />
<img width="2524" height="1930" alt="image" src="https://github.com/user-attachments/assets/a07fd724-ea6e-49c8-b0f2-195883f1694b" />
<img width="2339" height="1910" alt="image" src="https://github.com/user-attachments/assets/2ac19a8f-2b03-4d13-9700-4b0a5e0506f2" />
<img width="2334" height="1923" alt="image" src="https://github.com/user-attachments/assets/a6027a18-e488-4e9f-96e0-b6c95bf1e8d6" />
<img width="2341" height="1789" alt="image" src="https://github.com/user-attachments/assets/1104c8c8-48c8-413d-811a-5b374a23e4af" />


## Recent Updates

- ✅ **Decimal Ratings:** Support for precise ratings from 0-10.0 with one decimal place
- ✅ **Modern UI Redesign:** Card-based layouts, smooth animations, and gradient designs
- ✅ **Statistics Panel Enhancement:** Animated visualizations and improved readability
- ✅ **SEO Optimization:** Meta tags, structured data, sitemap, and robots.txt
- ✅ **Security Improvements:** Security headers, bot filtering, and enhanced protection
- ✅ **Performance Optimizations:** Poster caching, deduplication, and loading state management

