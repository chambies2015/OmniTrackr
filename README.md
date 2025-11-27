# OmniTrackr

## Overview

OmniTrackr is a full-featured, multi-user web application for managing and tracking movies and TV shows. Originally a local desktop app, it has evolved into a production-ready platform with user authentication, cloud database support, and a modern responsive UI.

**Live Demo:** Deployed on Render with PostgreSQL database: https://www.omnitrackr.xyz/

## Tech Stack

**Backend:**
- FastAPI (Python web framework)
- SQLAlchemy (ORM)
- PostgreSQL / SQLite (Database)
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
- **PostgreSQL Database:** Production-ready database with SQLite fallback for local development
- **Search and Sort:** Filter by title/director and sort by rating or year
- **Modern UI:** Responsive single-page application with dark mode support and landing page
- **Poster Integration:** Automatic poster fetching from OMDB API with caching
- **Export/Import:** JSON export/import with smart conflict resolution
- **Statistics Dashboard:** Comprehensive analytics with watch progress, rating distributions, year analysis, and director insights
- **Comprehensive Testing:** 83 unit tests covering all features and edge cases

## Local Development Setup

### Prerequisites
- Python 3.12+
- PostgreSQL (optional - uses SQLite by default for local development)

### Installation

1. **Clone the repository and navigate to the project directory**

2. **Create a virtual environment and install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   
   Create a `.env` file in the project root:
   ```env
   # Database (optional - defaults to SQLite if not set)
   DATABASE_URL=sqlite:///./movies.db
   
   # For PostgreSQL:
   # DATABASE_URL=postgresql://user:password@localhost:5432/omnitrackr
   
   # Security (IMPORTANT: Change in production!)
   SECRET_KEY=your-secret-key-here
   
   # Optional: OMDB API key for movie posters
   OMDB_API_KEY=your-omdb-api-key
   ```

4. **Start the server:**
   ```bash
   # Using the start script
   ./start.bat  # Windows
   
   # Or manually
   uvicorn app.main:app --reload --port 8000
   ```

5. **Access the application:**
   - **Web UI:** `http://127.0.0.1:8000`
   - **API Documentation:** `http://127.0.0.1:8000/docs`
   - **Register** a new account and start tracking your media!

## Testing

OmniTrackr includes a comprehensive test suite with **83 tests** covering all major functionality to ensure reliability and prevent regressions during development.

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage report
python -m pytest tests/ --cov=app --cov-report=html

# Run specific test file
python -m pytest tests/test_auth.py -v

# Run specific test category
python -m pytest tests/ -k statistics -v
```

### Test Coverage

The test suite provides comprehensive coverage across all features:

#### Authentication (`test_auth.py` - 20 tests)
- Password hashing and verification
- JWT token creation and validation
- User registration (including duplicate email/username checks)
- Login with username or email
- Email verification workflow
- Password reset functionality
- Resend verification email
- Unverified user login prevention

#### CRUD Operations (`test_crud.py` - 12 tests)
- User CRUD operations
- Movie CRUD operations (create, read, update, delete)
- TV Show CRUD operations (create, read, update, delete)
- Search and filtering functionality

#### API Endpoints (`test_api.py` - 31 tests)
- **Movie Endpoints:** Full CRUD with search and sorting
- **TV Show Endpoints:** Full CRUD with search and sorting
- **Error Handling:** 404 responses for non-existent resources
- **Authentication Requirements:** All protected endpoints
- **Export/Import:** JSON export and file upload import
- **Data Isolation:** Users cannot access each other's data
- **File Import:** Validation and error handling

#### Statistics (`test_statistics.py` - 8 tests)
- Statistics dashboard endpoint
- Watch statistics
- Rating statistics
- Year-based statistics
- Director statistics
- Empty data handling
- Authentication requirements
- User data isolation for statistics

#### Email Utilities (`test_email.py` - 6 tests)
- Verification token generation and validation
- Reset token generation and validation
- Token expiration handling
- Token type differentiation

### Test Architecture

- **In-memory SQLite database** for fast, isolated test execution
- **Fixtures** for reusable test data and authenticated clients
- **Comprehensive error case testing** including 404s, validation errors, and unauthorized access
- **Data isolation verification** ensuring multi-user security
- **Edge case coverage** including empty data, invalid inputs, and missing fields

All tests are designed to run independently and can be executed in parallel for faster feedback during development.

## Production Deployment (Render)

### Database Setup
1. Create a PostgreSQL database on Render
2. Copy the Internal Database URL

### Web Service Setup
1. Create a new Web Service on Render
2. Connect your GitHub repository
3. Configure:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Environment Variables
Set these in your Render dashboard:
```env
DATABASE_URL=<your-postgresql-internal-url>
SECRET_KEY=<generate-a-secure-random-string>
OMDB_API_KEY=<your-omdb-api-key>
```

The application will automatically create database tables on first startup.

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
- **Average rating** across all rated items
- **Rating distribution** with interactive bar charts (1-10 scale)
- **Highest rated items** showing your top-rated movies and TV shows
- **Visual representation** of your rating patterns

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
- **Night Mode:** Toggle between light and dark themes
- **Tabbed Interface:** Switch between Movies, TV Shows, and Statistics
- **Export/Import:** Backup your collection to JSON or import from JSON files
- **Statistics Dashboard:** Comprehensive analytics showing your viewing habits and preferences

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


## Development Roadmap
- [x] **Add notes/review section**
- [x] **TV Shows compatibility**
- [x] **Poster caching system**
- [x] **Export/import functionality**
- [x] **Statistics dashboard**
- [x] **Migrate to server/client setup** - Deployed on Render with PostgreSQL
- [x] **Account creation/login** - Full authentication system with JWT tokens
- [x] **Security implementation** - JWT authentication, bcrypt password hashing, user isolation
- [x] **Email verification**
- [x] **Password reset functionality**
- [ ] **Add friends to check each other's lists**
- [ ] **Enhanced search and filtering**
- [ ] **Social features (sharing lists, recommendations)**

