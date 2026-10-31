"""Hand-written "Switch from X" guides, one per service the Import Studio reads.

Each guide is served at /switch/<slug> through templates/switch_source.html. The text is
maintained here in code, so the few inline links and <code> tags are trusted HTML; plain
fields (questions, table cells) are escaped when the page is drawn.

When an importer changes, update its guide and the "reviewed" date together.
"""
from __future__ import annotations

GUIDES: dict[str, dict] = {
    "letterboxd": {
        "name": "Letterboxd",
        "kinds": "films",
        "reviewed": "2026-10-31",
        "title": "Switch from Letterboxd: import your films, diary and ratings | OmniTrackr",
        "description": ("Move your Letterboxd films, half-star ratings, reviews and dated diary into OmniTrackr. "
                        "Upload the export ZIP as it is and preview every film before anything is saved."),
        "h1": "Switch from Letterboxd without losing your diary",
        "lead": "Your Letterboxd export already holds every film you logged. Here is how to bring it across, ratings and diary dates included.",
        "intro": [
            "Letterboxd is the best place on the web to talk about films, and plenty of people who import here keep their "
            "account for the reviews and lists from people they follow. What Letterboxd can't do is hold the rest of what you "
            "watch, read and play. If you track shows in one app, books in another and games nowhere, OmniTrackr is a place "
            "to put all of it side by side, starting with the films you already logged.",
            "The import reads the whole ZIP Letterboxd gives you. A film that shows up in several of its files becomes one "
            "entry here, and the dates in your diary carry over to your journal.",
        ],
        "export": [
            "Sign in on the Letterboxd website and open Settings.",
            "Go to the Data tab and choose to export your data. The download is a ZIP named after your username and the date.",
            "Keep the ZIP as it is. There is no need to unzip it.",
        ],
        "export_note": 'Letterboxd describes what is inside on <a href="https://letterboxd.com/user/exportdata/">its export page</a>.',
        "mapping": [
            ("watched.csv, diary.csv, ratings.csv, reviews.csv", "One movie entry per film, marked watched"),
            ("Star rating, half stars included", "Rating out of 10: 3.5 stars becomes 7/10"),
            ("Your latest review", "A private note on the film"),
            ("Dated diary entries and rewatches", "Journal entries on the day you logged them"),
            ("watchlist.csv", "Films marked unwatched, ready for Next Up"),
        ],
        "stays": [
            "Likes, lists and tags. Lists are a Letterboxd feature worth keeping there.",
            "Anything in the archive's deleted folder, since you removed it on purpose.",
            "Directors. Letterboxd's export doesn't include them, so films show an unknown director until you add one.",
        ],
        "after": [
            "Open the Journal tab. Your diary calendar starts with your real history, and Year in Review counts it.",
            "Pick two or three watchlist films for Next Up so the list becomes something to choose from.",
            "Add your shows, anime and books next. That is where a single library starts to pay off.",
        ],
        "faq": [
            ("Will my current Letterboxd rating win over older diary ratings?",
             "Yes. The ratings file is read last, so the rating you show on Letterboxd today is the one that arrives."),
            ("Can I import only my watchlist?",
             "Yes. Upload watchlist.csv from the ZIP on its own and every film in it arrives unwatched."),
            ("What if I already added some films by hand?",
             "A film with the same title and year is skipped and your own entry is left exactly as it is, rating and review included."),
            ("Does it keep syncing after the import?",
             "No. Importing copies your history once. Run a fresh export later and import it again to add new films; the ones you already have are skipped."),
        ],
        "hub": "letterboxd-heading",
        "related": ("imdb", "trakt", "libib"),
    },
    "imdb": {
        "name": "IMDb",
        "kinds": "movies, shows and games",
        "reviewed": "2026-10-31",
        "title": "Switch from IMDb: import your ratings and watchlist | OmniTrackr",
        "description": ("Bring years of IMDb ratings and your watchlist into OmniTrackr. One CSV fills movies, TV shows "
                        "and games, with ratings kept out of 10 and a preview before anything is saved."),
        "h1": "Switch from IMDb and keep every rating",
        "lead": "IMDb ratings are often the longest record people have. One export file can fill your movies, shows and games here.",
        "intro": [
            "Many people have rated films on IMDb for a decade or more, usually right after the credits, and never looked at "
            "the list again. IMDb is a reference site first, so your ratings sit behind a few menus and there is little to do with "
            "them once they are there. Imported here, they become a library you can sort, filter, review and share.",
            "IMDb mixes categories in one file. The Title Type column decides where each row goes, so films, series and video "
            "games each land on their own shelf.",
        ],
        "export": [
            "Sign in on the IMDb website and open Your Ratings from the account menu.",
            "Use the page's menu to export. IMDb builds the file in the background, so it isn't ready immediately.",
            "Open your exports page from the same menu and download the CSV once it appears.",
            "Repeat for your Watchlist or any list you want. Each one exports separately.",
        ],
        "export_note": "IMDb moves these menus around from time to time. If a step looks different, look for an Export option on the ratings or list page itself.",
        "mapping": [
            ("Movie, TV Movie, Short, TV Special, Video", "Movies"),
            ("TV Series, TV Mini Series", "TV shows"),
            ("Video Game", "Games, with the release date and genres"),
            ("Your Rating", "Rating out of 10, unchanged"),
            ("A title with your rating", "Marked watched or played"),
            ("Watchlist and list rows with no rating", "Unwatched, ready for Next Up"),
        ],
        "stays": [
            "Episode ratings. Those rows are listed as needing attention with the reason, and the series itself imports normally.",
            "Podcast and music video entries, which aren't categories here.",
            "Season and episode counts, which aren't in IMDb's file. Add them later on shows you want progress for.",
        ],
        "after": [
            "Anime arrives under TV shows because IMDb files it that way. If you want it on the Anime shelf, import a MyAnimeList or AniList list for those titles.",
            "Set the episode you're on for the two or three shows you're watching now.",
            "Look at Statistics. A long IMDb history makes the rating spread and decade charts interesting straight away.",
        ],
        "faq": [
            ("Do I need to convert my ratings?", "No. IMDb already rates out of ten, so 8 stays 8/10."),
            ("What happens if a title is in both my ratings and my watchlist?",
             "It is created once, from whichever file you import first. The second file skips it as a duplicate."),
            ("Why did some rows need attention?",
             "Usually because they were episode ratings or a title type that isn't tracked here. The preview names the reason for each one."),
        ],
        "hub": "imdb-heading",
        "related": ("letterboxd", "trakt", "steam"),
    },
    "goodreads": {
        "name": "Goodreads",
        "kinds": "books",
        "reviewed": "2026-10-31",
        "title": "Switch from Goodreads: import your shelves, ratings and reviews | OmniTrackr",
        "description": ("Import your Goodreads library into OmniTrackr: books, star ratings, reviews and what you've read. "
                        "Preview the export CSV first; books you already track are never replaced."),
        "h1": "Switch from Goodreads and bring your shelves",
        "lead": "Goodreads hands over your whole library as one CSV. It takes about two minutes to bring it in.",
        "intro": [
            "Goodreads has the biggest catalog of book pages and reader reviews anywhere, and that is a good reason to keep "
            "an account. As a personal reading log it is slower, and it only knows about books. If you also listen to "
            "audiobooks, read manga or keep a film watchlist, OmniTrackr holds them all in the same place as your reading.",
            "The Goodreads file includes every shelf, so to-read books come across too. They arrive unread, so they show up "
            "as unfinished.",
        ],
        "export": [
            "On the Goodreads website, open My Books.",
            "Find Import and export in the tools on the left.",
            "Choose to export your library. Goodreads prepares the file and then shows a download link on the same page.",
            "Download <code>goodreads_library_export.csv</code>.",
        ],
        "export_note": "",
        "mapping": [
            ("Title, Author, Year Published", "Book title, author and year"),
            ("My Rating (stars)", "Rating out of 10: 4 stars becomes 8/10. Unrated books stay unrated."),
            ("Exclusive Shelf is read, or a Date Read exists", "Marked read"),
            ("to-read and currently-reading", "Unread"),
            ("My Review", "A private note"),
        ],
        "stays": [
            "Custom shelves and the dates themselves.",
            "Private notes, page counts and the average rating from other readers.",
            "Your Goodreads friends and groups. Invite the friends you want to keep up with once you're set up.",
        ],
        "after": [
            "Choose one or two to-read books for Next Up.",
            "Set this year's reading goal. Books you already marked read this year count toward it.",
            "If you listen to audiobooks, add them on the Audiobooks shelf so narrator and listening hours are tracked.",
        ],
        "faq": [
            ("Are my Goodreads reviews made public here?",
             "No. Imported reviews stay private. You can publish any one of them later from the book itself."),
            ("Will books I already added be duplicated?",
             "No. Books are matched on title and author, and a match is skipped so your entry stays as it is."),
            ("I also have a StoryGraph account. Can I import both?",
             'Yes. Import one, then the other. Books that appear in both are created once. See the <a href="/switch/storygraph">StoryGraph guide</a>.'),
        ],
        "hub": "goodreads-heading",
        "related": ("storygraph", "libib", "anilist"),
    },
    "storygraph": {
        "name": "The StoryGraph",
        "kinds": "books",
        "reviewed": "2026-10-31",
        "title": "Switch from The StoryGraph: import your reading history | OmniTrackr",
        "description": ("Move your StoryGraph books, quarter-star ratings and reviews into OmniTrackr. The export CSV is "
                        "recognized automatically and previewed before anything is saved."),
        "h1": "Switch from The StoryGraph, quarter stars included",
        "lead": "The StoryGraph's export is detailed and reads cleanly here. Even quarter-star ratings come across exactly.",
        "intro": [
            "A lot of readers moved to The StoryGraph from Goodreads for its charts and mood tags, and those are worth keeping "
            "if you use them. OmniTrackr is for the reader who also watches, plays and listens, and wants one record of all of it.",
            "The StoryGraph rates in quarter stars. Those are doubled and kept, so 3.75 stars becomes 7.5/10.",
        ],
        "export": [
            "Open your account settings on The StoryGraph.",
            "Look for the option to export your library and start it.",
            "Download the CSV once it's ready. The StoryGraph says when the file is done.",
        ],
        "export_note": "",
        "mapping": [
            ("Title, Authors", "Book title and author"),
            ("Star Rating", "Rating out of 10, quarter stars kept: 4.25 becomes 8.5/10"),
            ("Read Status is read", "Marked read"),
            ("to-read, currently-reading, paused, did-not-finish", "Unread"),
            ("Review", "A private note"),
        ],
        "stays": [
            "Moods, pace, content warnings and tags.",
            "Publication years, which aren't in the file. Books arrive without a year until you add one.",
            "Reading dates and read counts.",
        ],
        "after": [
            "Look through did-not-finish books. They arrive unfinished, so they're easy to find and remove if you don't want them.",
            "Set a reading goal for the year.",
            "Add the films and shows you've been meaning to track. That's the part The StoryGraph doesn't cover.",
        ],
        "faq": [
            ("Why don't my books have a year?",
             "The StoryGraph's export doesn't include one. You can add it from each book if you want it."),
            ("Will a book I already track be duplicated if it has a year and the import doesn't?",
             "No. Books are matched on title and author, so the year doesn't matter for spotting a duplicate."),
            ("Does it read the file without me choosing a format?",
             "Yes. The Read Status and Star Rating columns give it away, so Detect automatically works."),
        ],
        "hub": "storygraph-heading",
        "related": ("goodreads", "libib", "spotify"),
    },
    "myanimelist": {
        "name": "MyAnimeList",
        "kinds": "anime and manga",
        "reviewed": "2026-10-31",
        "title": "Switch from MyAnimeList or Kitsu: import your anime and manga lists | OmniTrackr",
        "description": ("Import your MyAnimeList or Kitsu anime and manga lists into OmniTrackr from the XML export, "
                        "compressed or not. Scores, completed status and comments come across."),
        "h1": "Switch from MyAnimeList or Kitsu",
        "lead": "MyAnimeList's export is an XML file, often gzipped. Upload it as it comes and your anime and manga land on their own shelves.",
        "intro": [
            "MyAnimeList has the biggest anime database and the forums to go with it, and Kitsu users can export in the same "
            "format. Both are anime-only. OmniTrackr is useful when you also want your live-action shows, films and games in "
            "the same list, with one set of statistics across all of them.",
            "Anime goes to the Anime shelf with its episode count. Manga goes to the Manga shelf with chapters and volumes.",
        ],
        "export": [
            "On MyAnimeList, open the list export page from your profile or list settings.",
            "Export your anime list, your manga list, or both. Each is its own file.",
            "On Kitsu, use the export in your settings and choose the MyAnimeList format.",
            "Keep the <code>.xml.gz</code> file as downloaded. It doesn't need unzipping.",
        ],
        "export_note": "",
        "mapping": [
            ("Anime entries", "Anime, with the series episode count"),
            ("Manga entries", "Manga, with chapter and volume counts"),
            ("My Score", "Rating out of 10, unchanged. A score of 0 means unrated."),
            ("Completed", "Marked watched or read"),
            ("My Comments", "A private note"),
        ],
        "stays": [
            "Release years. The XML doesn't include them.",
            "Your current episode or chapter. The count in the file is the series total, so set your place after importing.",
            "Tags, priority and rewatch counts.",
        ],
        "after": [
            "Set the episode you're on for anything marked Watching on MyAnimeList.",
            "Check the Anime statistics for your genre mix and how many episodes you've put in.",
            "Add the films and live-action shows you watch. They sit next to your anime here.",
        ],
        "faq": [
            ("Do I need to unzip the .gz file?", "No. Compressed and uncompressed exports both work."),
            ("Will anime I already track be duplicated?",
             "No. An imported title with no year matches the same title you already have, whatever its year, and is skipped."),
            ("My manga went to Books in an earlier import. Will it appear twice?",
             "No. A manga title already on your Books shelf from an older import is recognized and skipped."),
        ],
        "hub": "mal-heading",
        "related": ("anilist", "trakt", "libib"),
    },
    "anilist": {
        "name": "AniList",
        "kinds": "anime, manga and light novels",
        "reviewed": "2026-10-31",
        "title": "Switch from AniList: import your anime and manga by username | OmniTrackr",
        "description": ("Bring your AniList anime and manga into OmniTrackr with just your username. No file to download; "
                        "scores keep their decimals and you preview everything first."),
        "h1": "Switch from AniList with just your username",
        "lead": "AniList doesn't give you an export file, so there's nothing to download. Type your username and the lists come across.",
        "intro": [
            "AniList's list pages and activity feed are some of the nicest in anime tracking. If you only track anime and manga, "
            "you may never need anything else. If you also want your films, shows, books and games in the same place, this is "
            "the quickest move on the switching list, because there is no file to wait for.",
            "Your browser asks AniList for your public lists and the usual preview opens. Nothing is saved until you confirm.",
        ],
        "export": [
            "Make sure your AniList lists are public. If they're private, switch them to public in AniList's settings for a minute.",
            "In the Import Studio, type your AniList username under On AniList? No file needed.",
            "Select Fetch my AniList lists and check the preview.",
        ],
        "export_note": "",
        "mapping": [
            ("Anime", "Anime, with the episode count and start year"),
            ("Manga, manhwa, manhua, one-shots", "Manga, with chapters and volumes"),
            ("Light novels", "Books"),
            ("Score", "Rating out of 10 with decimals kept: 85/100 becomes 8.5/10"),
            ("Completed or Rewatching", "Marked finished"),
            ("Notes", "A private note"),
        ],
        "stays": [
            "Favorites, custom lists and activity.",
            "Your progress through each title. Set the episode or chapter you're on after importing.",
            "Private entries, since only public lists can be read.",
        ],
        "after": [
            "Planning, watching, paused and dropped titles arrive unfinished. Remove the dropped ones you don't want to see.",
            "Add the manga you read in print to the Manga shelf if it isn't on AniList.",
            "Look at the Year in Review once December comes around. Imported finishes count.",
        ],
        "faq": [
            ("Which scoring system do I need to use on AniList?",
             "Any of them. Scores are always read on AniList's ten-point decimal scale."),
            ("Are English or romaji titles used?", "The English title when AniList has one, otherwise the romaji title."),
            ("My list is private. Can I still import it?",
             'Make it public for a moment, or use a MyAnimeList-format XML file made with a community tool and follow the <a href="/switch/myanimelist">MyAnimeList guide</a>.'),
        ],
        "hub": "anilist-heading",
        "related": ("myanimelist", "trakt", "steam"),
    },
    "trakt": {
        "name": "Trakt",
        "kinds": "movies and shows",
        "reviewed": "2026-10-31",
        "title": "Switch from Trakt: import your watch history, ratings and watchlist | OmniTrackr",
        "description": ("Import your Trakt movies and shows into OmniTrackr from the data export ZIP. Ratings out of 10, "
                        "watched history and your watchlist come across; shows are finished only when they really are."),
        "h1": "Switch from Trakt and keep your watch history",
        "lead": "Trakt's data export is a ZIP of JSON files. Upload it whole and your films and shows arrive with ratings and watched status.",
        "intro": [
            "Trakt is excellent at scrobbling from Plex, Kodi and streaming apps, and if you rely on that, keep it running. "
            "OmniTrackr is a better fit when you want your films and shows next to the books, games, anime and albums you get "
            "through, with reviews and stats that cover the lot.",
            "A show only counts as finished when you rated it or watched every aired episode, so series you're halfway through stay unfinished.",
        ],
        "export": [
            "On the Trakt website, open your settings and find the data section.",
            "Request an export of your data.",
            "Download the archive when Trakt has it ready.",
        ],
        "export_note": "You can also upload a single JSON file from inside the archive, such as your watchlist on its own.",
        "mapping": [
            ("Watched movies", "Movies marked watched"),
            ("Watched shows", "TV shows, marked watched only when every aired episode is in your history"),
            ("Ratings for movies and shows", "Rating out of 10, unchanged"),
            ("Watchlist", "Unwatched, ready for Next Up"),
        ],
        "stays": [
            "Collections and custom lists. Owning a copy or listing a title isn't the same as watching it.",
            "Episode and season ratings.",
            "Check-ins and scrobble times.",
        ],
        "after": [
            "Set your episode on shows you're in the middle of. They arrive unfinished.",
            "Use the binge calculator on a long show in your watchlist to see when you'd finish it.",
            "Add the books and games you've been keeping track of elsewhere.",
        ],
        "faq": [
            ("Do I need to unzip the Trakt export?", "No. Upload the ZIP as it is, or any one JSON file inside it."),
            ("Why is a show I watched marked unfinished?",
             "It had aired episodes missing from your history and no rating. Mark it watched yourself if you're done with it."),
            ("Will this keep syncing with Trakt?",
             "No. It's a one-time copy. Import a newer export later to add what's new; titles you already have are skipped."),
        ],
        "hub": "trakt-heading",
        "related": ("letterboxd", "imdb", "myanimelist"),
    },
    "steam": {
        "name": "Steam",
        "kinds": "games and hours played",
        "reviewed": "2026-10-31",
        "title": "Import your Steam library and playtime | OmniTrackr",
        "description": ("Paste your Steam profile link to bring your games and hours played into OmniTrackr. Untouched "
                        "games go to your backlog, and importing again refreshes your hours without touching your ratings."),
        "h1": "Bring your Steam library, hours included",
        "lead": "Steam has no export file. Paste your profile link and your games come across with the hours you've played each one.",
        "intro": [
            "Steam knows what you own and how long you've played it, but it can't tell a finished game from a sale purchase you "
            "never opened, and it has nowhere for your thoughts on a game. OmniTrackr turns the library into a backlog you can "
            "work through, with ratings, reviews and the games you play elsewhere.",
            "You decide how much playtime counts as played. Anything under it goes to your backlog.",
        ],
        "export": [
            "On Steam, open your profile, choose Edit Profile, then Privacy Settings, and set Game details to Public. You can switch it back after.",
            "Copy your profile address. It looks like <code>steamcommunity.com/id/yourname</code> or <code>steamcommunity.com/profiles/</code> followed by 17 digits.",
            "In the Import Studio, paste it into the Steam box, choose the playtime that counts as played, and select Fetch my Steam games.",
        ],
        "export_note": "",
        "mapping": [
            ("Games you own", "Games, with Steam cover art"),
            ("Hours played", "Time spent on your Statistics tab"),
            ("Playtime over the amount you chose", "Marked played"),
            ("Everything else", "Your backlog"),
        ],
        "stays": [
            "Ratings, reviews and completion dates, because Steam doesn't have them.",
            "Free games you've never launched.",
            "Achievements.",
        ],
        "after": [
            "Rate the five games you played most. They're at the top of the list when you sort by time played.",
            "Pick a backlog game for Next Up.",
            "Run the import again every so often. Games you already track keep their rating and review and only their hours are updated.",
        ],
        "faq": [
            ("Why does it say my library is private?",
             "Steam only shares a library when Game details is set to Public. Change it, import, then change it back if you like."),
            ("Will importing again duplicate my games?",
             "No. Games you already have keep their entry. Only the hours are refreshed."),
            ("What about games on other stores?",
             'Add them by search, or put them in a spreadsheet and import it. <a href="/switch/libib">Libib</a> exports also bring games.'),
        ],
        "hub": "steam-heading",
        "related": ("imdb", "libib", "anilist"),
    },
    "spotify": {
        "name": "Spotify",
        "kinds": "albums and podcasts",
        "reviewed": "2026-10-31",
        "title": "Import your Spotify albums and podcasts | OmniTrackr",
        "description": ("Turn your Spotify saved albums, liked songs and followed podcasts into an OmniTrackr music and "
                        "podcast library. Upload the account data ZIP and preview it first."),
        "h1": "Bring your Spotify albums and podcasts",
        "lead": "Spotify will send you a copy of your library. Upload it here and your saved albums and followed podcasts become a library you can rate and review.",
        "intro": [
            "Spotify is where most people listen, but it keeps no record of what you thought of an album, and liked songs pile "
            "up into one long playlist. Importing gives you an album shelf with ratings and reviews, and a podcast shelf, next "
            "to the films, shows and books you already track.",
            "OmniTrackr tracks albums, not single songs. Your saved albums all come across. An album you've liked three or more "
            "songs from comes across too, because by then you know it.",
        ],
        "export": [
            "Sign in at spotify.com, open your account page, and go to Privacy settings.",
            "Under Download your data, tick Account data and request it. You don't need the extended streaming history.",
            "Confirm the email Spotify sends. The download link usually arrives within a few days.",
            "Upload <code>my_spotify_data.zip</code> as it is, or just the <code>YourLibrary.json</code> file from inside it.",
        ],
        "export_note": "",
        "mapping": [
            ("Saved albums", "Music, marked listened"),
            ("Liked songs, three or more from one album", "That album, marked listened"),
            ("Followed podcasts", "Podcasts with their publisher as host, still in progress"),
        ],
        "stays": [
            "Single songs, playlists and liked songs from albums you only liked one or two tracks on.",
            "Streaming history and play counts.",
            "Release years. Spotify's file doesn't include them, so albums show no year until you add one.",
        ],
        "after": [
            "Rate a handful of albums. Rating ten is enough for your music statistics to start showing a pattern.",
            "Mark the podcasts you're caught up on as listened. They arrive as ones you're still following.",
            "Write a short review of an album you keep going back to, and share it if you want.",
        ],
        "faq": [
            ("Why didn't every liked song come across?",
             "OmniTrackr tracks albums. A song comes across as its album once you've liked three songs from that album."),
            ("Can I use my extended streaming history instead?",
             "Not yet. It's usually much larger than the 5 MB limit and doesn't say which albums you saved. Use the Account data download."),
            ("Will albums I already added be duplicated?",
             "No. Albums are matched on title and artist, and a match is skipped. Your rating and review stay as they are."),
        ],
        "hub": "spotify-heading",
        "related": ("rate-your-music", "podcast-apps", "libib"),
    },
    "podcast-apps": {
        "name": "your podcast app",
        "short": "Podcast apps (OPML)",
        "kinds": "podcast subscriptions",
        "reviewed": "2026-10-31",
        "title": "Import podcast subscriptions from Pocket Casts, Overcast and more (OPML) | OmniTrackr",
        "description": ("Move your podcast subscriptions into OmniTrackr from Pocket Casts, Overcast, AntennaPod, Castro, "
                        "Podcast Addict or any app that exports OPML. Every show is previewed before it is saved."),
        "h1": "Bring your podcasts over from any podcast app",
        "lead": "Almost every podcast app can export its subscriptions as one OPML file. Upload it here and each show lands on your Podcasts shelf.",
        "intro": [
            "Podcast apps are good at playing episodes and bad at remembering what you thought of a show. Once you've "
            "switched apps a couple of times, the list of what you've listened to is gone. OmniTrackr keeps that list, with a "
            "rating and a few words on each show, next to everything else you track.",
            "OPML is a plain list of feeds, and nearly every podcast app reads and writes it. That makes it the one export "
            "here that works the same whichever app you use.",
        ],
        "export": [
            "Pocket Casts: in the app's settings, open Import and Export and export your podcasts as OPML.",
            "Overcast: sign in at overcast.fm, open your account page and download the OPML export.",
            "AntennaPod, Podcast Addict and Castro: look in settings for export subscriptions, backup, or OPML.",
            "Save the file somewhere you can reach from a browser, then choose it in the Import Studio.",
        ],
        "export_note": ("Apple Podcasts on iPhone has no subscription export at the time of writing. Add those shows by "
                        "searching on the Podcasts tab instead. Spotify listeners can use the <a href=\"/switch/spotify\">Spotify guide</a>."),
        "mapping": [
            ("Each subscribed feed", "A podcast, still in progress"),
            ("Show title", "Podcast title"),
            ("Folders and groups", "Ignored; the shows inside them still come across"),
        ],
        "stays": [
            "Episode lists and played status. Overcast's detailed export lists episodes, but only the shows are imported.",
            "Hosts and genres, which most OPML files don't carry. Add them from each show if you want them.",
            "Your playback position.",
        ],
        "after": [
            "Mark the shows you're caught up on as listened, and the limited series you finished.",
            "Rate your five favorites. Friends can see your picks on the categories you share.",
            "Remove the shows you subscribed to once and never played. An import is a good moment to tidy up.",
        ],
        "faq": [
            ("My app saved the file as .xml, not .opml. Will it work?",
             "Yes. Both endings are read, and the file is recognized by what's inside it."),
            ("Does this subscribe me to anything or play episodes?",
             "No. It only adds the shows to your library. Keep listening in your usual app."),
            ("A show appears twice in my file. Will I get two entries?",
             "No. A repeated title is created once, and a show already in your library is skipped."),
        ],
        "hub": "podcasts-heading",
        "related": ("spotify", "rate-your-music", "libib"),
    },
    "rate-your-music": {
        "name": "Rate Your Music",
        "short": "Rate Your Music",
        "kinds": "albums",
        "reviewed": "2026-10-31",
        "title": "Switch from Rate Your Music: import your album ratings | OmniTrackr",
        "description": ("Import your Rate Your Music album ratings, reviews and catalog into OmniTrackr. RYM's 10-point "
                        "ratings are kept as they are, and every album is previewed before it is saved."),
        "h1": "Switch from Rate Your Music and keep your ratings",
        "lead": "Rate Your Music lets you export your catalog as a CSV. Here is how it comes across, ratings and reviews included.",
        "intro": [
            "RYM has the deepest music database and the charts to match, and anyone who has rated hundreds of albums there "
            "should keep the account. What it doesn't do is sit next to the films, books and games you also care about. "
            "Importing gives you one record of all of it, with your music ratings intact.",
            "RYM's export stores ratings as whole numbers out of 10, where five stars is 10. They come across unchanged.",
        ],
        "export": [
            "Sign in on rateyourmusic.com and open your profile page.",
            "Look for the option to export your data, usually near the bottom of the profile, and choose the plain text or CSV export of your catalog.",
            "Save the CSV and choose it in the Import Studio. It's recognized by its RYM Album column.",
        ],
        "export_note": "",
        "mapping": [
            ("Title, artist (first and last name, or band name)", "Album title and artist"),
            ("Release_Date", "Year"),
            ("Rating", "Rating out of 10, unchanged"),
            ("Rated, or owned without a rating", "Marked listened"),
            ("Wishlist", "Not listened yet"),
            ("Review", "A private note"),
        ],
        "stays": [
            "Genre votes, descriptors and lists.",
            "Ratings for films, which RYM keeps separately.",
            "Purchase dates and media type.",
        ],
        "after": [
            "Look at your music statistics. A full RYM history fills the decade and rating charts at once.",
            "Write up one album you rated 10 and share the review.",
            "Add the podcasts and audiobooks you listen to, so all your listening is in one place.",
        ],
        "faq": [
            ("Do my ratings need converting?", "No. RYM's export is already out of 10, so a 4.5-star album arrives as 9/10."),
            ("Why do some artist names have odd characters?",
             "RYM escapes characters like ampersands in its file. They're turned back into normal text on import."),
            ("Will albums I already track be duplicated?",
             "No. Albums are matched on title and artist, and a match is skipped."),
        ],
        "hub": "rym-heading",
        "related": ("spotify", "libib", "podcast-apps"),
    },
    "libib": {
        "name": "Libib",
        "kinds": "books, films, music and games",
        "reviewed": "2026-10-31",
        "title": "Switch from Libib: import books, movies, music and games | OmniTrackr",
        "description": ("Move your Libib libraries into OmniTrackr in one go. Books, films, albums and games are sorted onto "
                        "their own shelves, with star ratings, reviews and completed status."),
        "h1": "Switch from Libib with every shelf in one file",
        "lead": "Libib catalogs books, films, music and games, and its CSV export holds all four. Each item lands on the matching shelf here.",
        "intro": [
            "Libib is built for cataloging what you own, with barcode scanning and lending. If you keep a physical collection, "
            "keep using it for that. OmniTrackr is about what you've watched, read, played and heard, owned or not, and it adds "
            "shows, anime, manga, podcasts and audiobooks to the four kinds Libib covers.",
            "Each row's item type decides its shelf. A file with books and games in it fills both at once.",
        ],
        "export": [
            "Sign in to Libib on the web and open the library you want to move.",
            "Use the library's export option and download the CSV.",
            "Repeat for each library. Books and films are often kept in separate ones.",
        ],
        "export_note": "",
        "mapping": [
            ("item_type book, movie, music, videogame", "Books, movies, music, games"),
            ("Creators", "Author or artist (the first one listed)"),
            ("publish_date", "Year, or release date for games"),
            ("Rating (stars)", "Rating out of 10: 4 stars becomes 8/10"),
            ("Status Completed, or a completed date", "Marked finished"),
            ("Review", "A private note"),
        ],
        "stays": [
            "Barcodes, prices, copies, lending and groups.",
            "Directors. Libib lists cast as a film's creators, so films show an unknown director for you to fill in.",
            "Item types other than these four, such as board games. They're listed as needing attention in the preview.",
        ],
        "after": [
            "Unfinished items arrive in your backlog. Pick one per shelf for Next Up.",
            "Add the TV shows and anime you watch, which Libib doesn't track.",
            "Keep Libib for your physical shelves if you like. The two do different jobs.",
        ],
        "faq": [
            ("Can I import several Libib libraries?",
             "Yes. Import each CSV in turn. Items already added by an earlier file are skipped."),
            ("Why do my films show an unknown director?",
             "Libib's creators field for films is usually the cast. Rather than guess, the director is left for you to add."),
            ("What happens to board games?",
             "They're listed as needing attention with the reason and aren't imported. Everything else in the file still comes across."),
        ],
        "hub": "libib-heading",
        "related": ("goodreads", "steam", "spotify"),
    },
}


def path(slug: str) -> str:
    return f"/switch/{slug}"


def short_name(slug: str) -> str:
    guide = GUIDES[slug]
    return guide.get("short") or guide["name"]
