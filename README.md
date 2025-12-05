<p align="center">
<img width="256" height="256" alt="omnitrackr_256x256" src="https://github.com/user-attachments/assets/baf5d9f6-bd5b-425a-be43-0ba675cb7a87" />
</p>

<h1 align="center">OmniTrackr</h1>

## Overview

OmniTrackr is a full-featured, multi-user web application for managing and tracking movies, TV shows, anime, and video games. Originally a local desktop app, it has evolved into a production-ready platform with user authentication, cloud database support, and a modern responsive UI.

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
- **Account Management:** Change username, email, password, and account deactivation/reactivation
- **Profile Pictures:** Upload, change, and reset profile pictures with automatic optimization and validation
- **Privacy Settings:** Control visibility of your movies, TV shows, anime, video games, and statistics (private or visible to friends)
- **Friends System:** Add friends by username, send/accept/deny friend requests, manage friends list
- **Friend Profiles:** View friends' movie, TV show, anime, and video game collections and statistics with privacy-aware access
- **Notifications:** Real-time notification system with bell icon, friend request notifications, and auto-dismissal
- **CRUD API:** Full REST API for managing movies, TV shows, anime, and video games
- **PostgreSQL Database:** Production-ready database
- **Search and Sort:** Automatic filtering by title/director and sorting by rating or year
- **Modern UI:** Responsive single-page application with dark mode by default, modern card-based design, and beautiful landing page
- **Poster Integration:** Automatic poster fetching from OMDB API (movies/TV shows/anime) and RAWG API (video games) with intelligent caching to reduce API calls
- **Decimal Ratings:** Support for precise ratings from 0-10.0 with one decimal place (e.g., 7.5, 8.4)
- **Export/Import:** JSON export/import with smart conflict resolution for movies, TV shows, anime, and video games
- **Statistics Dashboard:** Comprehensive analytics with animated visualizations, watch progress, rating distributions, year analysis, and director insights across all media types
- **SEO Optimized:** Meta tags, structured data, sitemap, and robots.txt for better search engine visibility
- **Security:** Security headers, bot filtering, content validation, image processing, rate limiting, and comprehensive protection against common web vulnerabilities
- **Persistent Storage:** Profile pictures stored in database for persistence across deployments


## Export/Import Functionality

OmniTrackr now includes powerful export/import capabilities:

### Exporting Data
- Click the **"Export Data"** button in any media tab (Movies, TV Shows, Anime, or Video Games)
- Your entire collection will be downloaded as a JSON file with timestamp
- The export includes all metadata: titles, directors/creators/developers, years, ratings, reviews, watched status, and poster URLs
- Export files are named `omnitrackr-export-YYYY-MM-DD.json`

### Importing Data
- Click the **"Import Data"** button in any tab to select a JSON file
- The system will automatically detect and import movies, TV shows, anime, and video games
- **Smart conflict resolution**: Existing entries (matched by title + director/creator/developer + year) will be updated rather than duplicated
- **Backward compatibility**: Old export files without newer media types can still be imported
- Import results show how many items were created vs updated
- Any errors during import are reported for easy troubleshooting

## Friends & Social Features

OmniTrackr includes a complete social system for connecting with other users:

### Friends List
- **Friends Sidebar:** Toggleable sidebar showing your friends list (can be hidden/shown)
- **Add Friends:** Send friend requests to other users by username
- **Friend Management:** View friends, unfriend users, and manage your connections
- **Friend Profiles:** Click on any friend's name to view their profile
  - View friends' movie, TV show, anime, and video game collections with search/filter functionality
  - View friends' statistics dashboard (if privacy allows)
  - Privacy-aware: Only shows data that friends have made visible
  - Accordion-style modal with collapsible sections for easy navigation

### Friend Requests
- **Send Requests:** Send friend requests to any user by entering their username
- **Request Status:** Track sent and received friend requests
- **Accept/Deny:** Accept or deny incoming friend requests with one click
- **Cancel Requests:** Cancel sent friend requests before they're accepted
- **Auto-expiration:** Friend requests automatically expire after 30 days

### Notifications System
- **Notification Bell:** Visual bell icon with red dot badge showing unread count
- **Real-time Updates:** Notification count updates every 30 seconds automatically
- **Notification Types:** Friend requests, friend acceptances, and system messages
- **Auto-dismissal:** Notifications automatically removed when friend requests are accepted/denied
- **Manual Dismissal:** Dismiss any notification with the X button
- **Dropdown Menu:** Click the bell to view all notifications, newest first
- **Action Buttons:** Accept/deny friend requests directly from notifications

## Account Management

OmniTrackr provides comprehensive account management features:

### Account Settings
- **View Account Info:** See your username, email, and account status
- **Change Username:** Update your username with password confirmation (requires re-login)
- **Change Email:** Update email address with verification sent to new email
- **Change Password:** Update password with current password verification
- **Profile Pictures:** Upload, change, or remove profile pictures (max 5MB, JPEG/PNG/GIF/WebP)
  - Automatic image optimization and resizing (max 800x800px)
  - Content validation to ensure uploaded files are valid images
  - Profile pictures displayed in user display, friends list, and friend profiles
- **Privacy Settings:** Control who can see your data
  - Movies, TV shows, anime, and video games privacy toggles (private or visible to friends)
  - Statistics privacy toggle (private or visible to friends)
  - When privacy is enabled, data is fully private (not visible to friends)
- **Account Deactivation:** Soft delete your account with 90-day reactivation window
- **Account Reactivation:** Reactivate deactivated accounts within the 90-day window

### Security Features
- **Password Verification:** All sensitive changes require password confirmation
- **Email Verification:** Email changes require verification via new email address
- **Secure Tokens:** All account operations use secure, time-limited tokens
- **Data Retention:** Deactivated accounts retain data for 90 days before permanent deletion
- **File Upload Security:** 
  - Content validation using magic bytes to verify uploaded files are actual images
  - File type validation (JPEG, PNG, GIF, WebP only)
  - File size limits (5MB maximum)
  - Path traversal protection
  - Automatic image optimization and resizing
- **Rate Limiting:** Profile picture uploads limited to 10 per minute per IP address
- **Enhanced Bot Filtering:** Comprehensive filtering of scanner bots and malicious requests

## Statistics Dashboard

OmniTrackr includes a comprehensive statistics dashboard accessible via the **📊 Statistics** tab:

### Watch Progress Analytics
- **Total items** in your collection (movies + TV shows + anime + video games)
- **Watched vs. unwatched** counts and percentages
- **Visual progress bar** showing completion status
- **Separate tracking** for movies, TV shows, anime, and video games

### Rating Analysis
- **Average rating** across all rated items (supports decimal ratings 0-10.0)
- **Rating distribution** with interactive animated bar charts (1-10 scale, rounded for visualization)
- **Highest and lowest rated items** showing your top and bottom-rated movies, TV shows, anime, and video games
- **Visual representation** of your rating patterns with modern gradient designs

### Year Analysis
- **Oldest and newest** years in your collection
- **Decade breakdown** with bar charts showing distribution across decades
- **Year-based insights** to understand your viewing preferences over time

### Director Statistics
- **Most prolific directors** (directors with the most movies in your collection)
- **Highest rated directors** (directors with the best average ratings)
- **Director insights** to discover your favorite filmmakers

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

### Account Management
- **Change Username:** Update your username with password confirmation
- **Change Email:** Update email address with verification sent to new email
- **Change Password:** Update password with current password verification
- **Account Deactivation:** Soft delete account with 90-day reactivation window
- **Account Reactivation:** Reactivate deactivated accounts within the 90-day window
- **Email Change Verification:** Secure token-based email change verification

### Friends & Social Features
- **Friends List:** View your friends in a dedicated sidebar
- **Friend Requests:** Send friend requests to other users by username
- **Request Management:** Accept, deny, or cancel friend requests
- **Auto-expiration:** Friend requests expire after 30 days
- **Notifications:** Real-time notifications for friend requests and acceptances
- **Notification Bell:** Visual indicator with unread count badge
- **Auto-dismissal:** Notifications automatically removed when friend requests are accepted/denied

### API Security
- All endpoints (except `/auth/register`, `/auth/login`, `/auth/verify-email`, `/auth/resend-verification`, `/auth/request-password-reset`, `/auth/reset-password`, and `/auth/reactivate`) require authentication
- JWT tokens sent in Authorization header
- User data isolation - users can only access their own data
- Automatic token validation and 401 handling

## Using the Application

### Getting Started
1. **Register/Login:** Create an account or log in with existing credentials
2. **Your Personal Collection:** All your data is private and isolated to your account

### Features
- **User Authentication:** Secure login with JWT tokens, logout functionality
- **Account Settings:** Manage your account - change username, email, password, profile picture, privacy settings, or deactivate/reactivate
- **Profile Pictures:** Upload and manage your profile picture, visible in user display, friends list, and friend profiles
- **Privacy Controls:** Set privacy settings for movies, TV shows, anime, video games, and statistics
- **Friends & Social:** Add friends, send/accept/deny friend requests, view friends list, and explore friends' collections
- **Friend Profiles:** View friends' movies, TV shows, anime, video games, and statistics with search/filter capabilities
- **Notifications:** Real-time notifications with bell icon and unread count badge
- **Add media:** Enter details like title, director/creator/developer, year, rating, and watched/played status for movies, TV shows, anime, and video games
- **Automatic Posters:** Posters are fetched automatically from OMDB API (movies/TV shows/anime) and RAWG API (video games) with intelligent caching
- **Search & Filter:** Automatic search by title or director/creator/developer and sort by rating or year
- **Inline Editing:** Edit entries directly in the table with save/cancel options, expandable review textareas
- **Delete:** Remove entries from your collection
- **Dark Mode:** Beautiful dark theme by default with light mode toggle
- **Modern UI:** Card-based design with smooth animations, gradients, and collapsible forms
- **Tabbed Interface:** Switch between Movies, TV Shows, Anime, Video Games, and Statistics
- **Export/Import:** Backup your collection to JSON or import from JSON files (supports all media types)
- **Statistics Dashboard:** Comprehensive analytics with animated visualizations showing your viewing and gaming habits across all media types


## Screenshots
<img width="3030" height="1896" alt="image" src="https://github.com/user-attachments/assets/1d4bde27-5cc4-413a-8013-0577fc901f8e" />
<img width="2548" height="1294" alt="image" src="https://github.com/user-attachments/assets/2f58377a-6ad3-4401-8e12-76e3e68f81d4" />
<img width="1194" height="975" alt="image" src="https://github.com/user-attachments/assets/7a3ce219-5232-45af-aa4c-b057120f84ea" />
<img width="1179" height="1265" alt="image" src="https://github.com/user-attachments/assets/cbc99333-535c-40cc-87ac-37dcf68fd510" />
<img width="1177" height="942" alt="image" src="https://github.com/user-attachments/assets/82212659-4b8b-40a2-ae5c-1115f2b2f152" />
<img width="1198" height="1142" alt="image" src="https://github.com/user-attachments/assets/c248a76b-95c2-445a-b53a-350fdc5ac3f3" />



## Recent Updates

- ✅ **Video Game Support:** Full CRUD operations, privacy settings, friend viewing, and statistics integration for video game tracking
- ✅ **Anime Support:** Full CRUD operations, privacy settings, friend viewing, and statistics integration for anime tracking
- ✅ **Profile Pictures:** Upload, change, and reset profile pictures with automatic optimization, content validation, and database storage
- ✅ **Privacy Settings:** Granular privacy controls for movies, TV shows, anime, video games, and statistics with friend-aware visibility
- ✅ **Friend Profile Viewing:** View friends' collections and statistics with search/filter capabilities and privacy-aware access
- ✅ **Enhanced Security:** Content validation (magic bytes), image processing, rate limiting, and comprehensive bot filtering
- ✅ **Friends & Social Features:** Complete friends system with friend requests, toggleable friends list sidebar, and social interactions
- ✅ **Notifications System:** Real-time notifications with bell icon, unread count badge, and auto-dismissal
- ✅ **Account Management:** Full account settings - change username, email, password, and account deactivation/reactivation
- ✅ **Decimal Ratings:** Support for precise ratings from 0-10.0 with one decimal place
- ✅ **Modern UI Redesign:** Card-based layouts, smooth animations, gradient designs, and collapsible forms
- ✅ **Statistics Panel Enhancement:** Animated visualizations and improved readability across all media types
- ✅ **SEO Optimization:** Meta tags, structured data, sitemap, and robots.txt
- ✅ **Security Improvements:** Security headers, bot filtering, and enhanced protection
- ✅ **Performance Optimizations:** Poster caching, deduplication, and loading state management
- ✅ **Automatic Filtering:** Search and sort filters apply automatically without button press
- ✅ **Enhanced Editing:** Expandable review textareas that auto-resize to content

