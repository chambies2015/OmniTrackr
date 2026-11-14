"""Awards season: the shows, their dates, the written guides and (once announced) the nominees.

Everything here is typed in by hand from the sources listed with each show, and
``reviewed`` says when it was last checked against them. Nothing is guessed: a
show whose nominees are not out yet has an empty ``categories`` list and its page
says when the list is due.

Adding nominees when a show announces them
-----------------------------------------
Fill in ``categories`` in the order the ballot should show them::

    {"key": "game-of-the-year", "name": "Game of the Year", "nominees": [
        {"name": "Hades II", "detail": "Supergiant Games", "kind": "game", "year": 2025},
        {"name": "Jennifer English", "detail": "Maelle in Clair Obscur: Expedition 33",
         "kind": "game", "title": "Clair Obscur: Expedition 33", "year": 2025},
        {"name": "Team Vitality", "detail": "Counter-Strike 2"},
    ]}

``name`` is what the ballot shows. ``kind`` (movie, tv, anime, game, album, book)
ties a nominee to a title members can track; ``title`` is that title when it
differs from ``name`` (a performer, a song from an album) and ``year`` its release
year. A nominee without ``kind`` (a person, a team) is only something to pick.
Keys come from the names, so never rename a category or nominee once ballots
exist: give it an explicit ``key`` with the old value instead. A winner can be
recorded here with ``"winner": "<nominee key>"`` on the category, or by a site
admin on the show's page on the night.

``ceremony_at`` is the moment picks lock, in UTC.
"""
from __future__ import annotations

SEASON = {
    "name": "Awards season 2026–27",
    "title": "Awards season 2026–27: dates, nominees and a ballot for every show",
    "search_title": "Awards season 2026–27: dates, nominees and ballots",
    "description": ("When the Game Awards, Golden Globes, Grammys and Oscars announce nominees and hand out prizes in "
                    "2026–27, where to watch each one, and a free ballot to pick the winners and keep score."),
    "lead": ("Four of the biggest shows in games, film, TV and music hand out their prizes between December and March. "
             "This page keeps their dates in one place. Once a show's nominees are out, you can fill in a ballot "
             "here, share it, and see how many you called when the winners are read out."),
    "published": "2026-11-12",
    "reviewed": "2026-11-12",
    "how": (
        "Each show gets a ballot as soon as its nominees are announced and checked against the official list. Pick "
        "one nominee per category. You can skip categories you have no opinion on, and change any pick until the "
        "show starts.",
        "Members' ballots save to their account as they go. Without an account your picks stay in your browser, and "
        "making a free account moves them over.",
        "A ballot here is for keeping score. It has no effect on the real vote. After the show, every category you "
        "called is a point, and skipped categories don't count against you.",
        "Nominees you already track are marked, and the rest can be added to your library from the ballot, so the "
        "nominee list doubles as a watchlist for the weeks before the show.",
    ),
    "voting": (
        "The four shows decide their winners in different ways, which is worth knowing before you fill in a ballot.",
        "The Game Awards lean on critics: a jury of media outlets casts 90% of the vote in most categories and the "
        "public vote makes up the other 10%. Favorites with players and favorites with the press don't always match.",
        "The Golden Globes are voted on by about 300 entertainment journalists from around the world. They split "
        "films into drama and musical or comedy, so two films win a best picture prize each year.",
        "The Grammys and the Oscars are decided by people who work in the field: voting members of the Recording "
        "Academy and of the Academy of Motion Picture Arts and Sciences. Both run a nominating round and a "
        "separate final round.",
    ),
    "faq": (
        ("When does awards season start?",
         "The Game Awards open it on December 10, 2026. The Golden Globes follow on January 10, 2027, the Grammys on "
         "February 7 and the Oscars close it on March 14."),
        ("When can I fill in a ballot?",
         "From the day a show's nominees are announced until its ceremony starts. Grammy nominations are due on "
         "November 16, 2026, Game Awards nominees in mid-November, Golden Globe nominations on December 7 and Oscar "
         "nominations on January 21, 2027."),
        ("Do I need an account?",
         "No. Picks made without an account stay in your browser. A free account saves them, gives you a link and a "
         "card to share, and keeps your score after the show."),
        ("Does a ballot here count as a real vote?",
         "No. It is a prediction game. The Game Awards run their own public vote on their website; the other three "
         "shows are voted on by their members only."),
    ),
    # Shows on the calendar that don't have a page here yet.
    "also": (
        {"name": "Crunchyroll Anime Awards 2027", "format": "Anime",
         "when": "Not announced",
         "note": ("No date had been announced when this page was last checked. The 2026 awards were held in Tokyo "
                  "on May 23, with nominees out on April 2 and a public vote until April 15. My Hero Academia: "
                  "Final Season won Anime of the Year.")},
    ),
    "sources": (
        ("The Game Awards", "https://thegameawards.com/"),
        ("Golden Globes timetable (AwardsWatch)", "https://awardswatch.com/2027-golden-globes-reveal-key-dates-adds-ai-rules-expands-podcast-pool/"),
        ("Grammy.com", "https://www.grammy.com/news/how-to-watch-2027-grammys-nominations/"),
        ("Oscars dates (TheWrap)", "https://www.thewrap.com/creative-content/movies/academy-sets-2027-and-2028-oscars-dates/"),
        ("10th Crunchyroll Anime Awards (Wikipedia)", "https://en.wikipedia.org/wiki/10th_Crunchyroll_Anime_Awards"),
    ),
}


def _game(title: str, year=2025) -> dict:
    return {"kind": "game", "title": title, "year": year}


_CLAIR = "Clair Obscur: Expedition 33"

SHOWS = {
    "the-game-awards-2026": {
        "name": "The Game Awards 2026",
        "short": "The Game Awards",
        "format": "Video games",
        "title": "The Game Awards 2026: date, nominees and your ballot",
        "search_title": "The Game Awards 2026: date, nominees, how to watch and a ballot",
        "description": ("The Game Awards 2026 are on December 10 in Los Angeles. When the nominees are due, how the "
                        "winners are chosen, where to watch, last year's results and a free ballot to pick the winners."),
        "lead": ("The Game Awards 2026 are on Thursday, December 10 at the Peacock Theater in Los Angeles. The "
                 "nominees are due in mid-November. When they land, this page becomes a ballot: pick a winner in "
                 "every category, save it, and see your score once the show is over."),
        "published": "2026-11-12",
        "reviewed": "2026-11-12",
        "ceremony_day": "2026-12-10",
        "ceremony_at": "2026-12-11T00:30:00",
        "lock_label": "Thursday, December 10 at 4:30 p.m. Pacific",
        "watch": "Free streams on YouTube, Twitch and other platforms",
        "nominees_day": None,
        "nominees_label": "Mid-November 2026",
        "nominees_note": ("The organizers say the nominees are coming in mid-November and had not named a day when "
                          "this page was last checked. Last year's list came out on November 17."),
        "dates": (
            ("Nominees announced", "Mid-November 2026 (day not confirmed)"),
            ("Public vote", "Opens with the nominees on thegameawards.com"),
            ("Ceremony", "Thursday, December 10, 2026"),
            ("Venue", "Peacock Theater, Los Angeles"),
            ("Ballots here lock", "December 10 at 4:30 p.m. Pacific"),
        ),
        "sections": (
            ("chosen", "How the winners are chosen", (
                "A jury of media outlets casts 90% of the vote in most categories. The public vote, on the show's "
                "website and social platforms, makes up the other 10%. The jury had 154 outlets in 2025.",
                "Players' Voice is the exception. Fans decide it entirely, in knockout rounds that opened on "
                "December 1 last year. Nominees in the accessibility, adaptation and esports categories come from "
                "specialist juries.",
                "To be eligible a game has to be out by a cut-off date in November that moves each year. In 2025 it "
                "was November 21. Expansions, DLC, remakes and remasters can be nominated alongside new games.",
            )),
            ("watch", "How to watch", (
                "The show streams free. The official site says it will be live on all platforms without listing "
                "them yet; GamingBible's guide names YouTube, Twitch, X, TikTok Live, Facebook, Instagram Live, "
                "Kick and Steam.",
                "The organizers had not posted a start time when this page was last checked. GamingBible lists "
                "4:30 p.m. Pacific, which is 7:30 p.m. Eastern and 12:30 a.m. on Friday in the UK. Ballots here "
                "lock at that time.",
            )),
            ("categories", "What the ballot will cover", (
                "Last year's show had 30 categories, from Game of the Year to Best Esports Team and Content Creator "
                "of the Year. No changes had been announced for 2026 when this page was last checked, so the "
                "ballot will follow the list the organizers publish with the nominees.",
                "Six games were nominated for Game of the Year in 2025. If your pick for this year isn't in your "
                "library yet, you will be able to add it from the ballot.",
            )),
        ),
        "categories": [],
        "last_year": {
            "heading": "Last year: The Game Awards 2025",
            "intro": (
                "The 2025 show was on December 11 at the same theater. Clair Obscur: Expedition 33 won nine awards, "
                "the most any game has taken in one night, from a record 13 nominations. It beat Death Stranding 2: "
                "On the Beach, Donkey Kong Bananza, Hades II, Hollow Knight: Silksong and Kingdom Come: Deliverance "
                "II to Game of the Year. The show drew more than 171 million streams.",
            ),
            "winners": (
                ("Game of the Year", _CLAIR, "Sandfall Interactive", _game(_CLAIR)),
                ("Best Game Direction", _CLAIR, "Sandfall Interactive", _game(_CLAIR)),
                ("Best Narrative", _CLAIR, "Sandfall Interactive", _game(_CLAIR)),
                ("Best Art Direction", _CLAIR, "Sandfall Interactive", _game(_CLAIR)),
                ("Best Score and Music", _CLAIR, "Lorien Testard", _game(_CLAIR)),
                ("Best Audio Design", "Battlefield 6", "Battlefield Studios", _game("Battlefield 6")),
                ("Best Performance", "Jennifer English", "Maelle in Clair Obscur: Expedition 33", _game(_CLAIR)),
                ("Games for Impact", "South of Midnight", "Compulsion Games", _game("South of Midnight")),
                ("Best Independent Game", _CLAIR, "Sandfall Interactive", _game(_CLAIR)),
                ("Best Debut Indie Game", _CLAIR, "Sandfall Interactive", _game(_CLAIR)),
                ("Best Ongoing Game", "No Man's Sky", "Hello Games", _game("No Man's Sky", 2016)),
                ("Best Community Support", "Baldur's Gate 3", "Larian Studios", _game("Baldur's Gate 3", 2023)),
                ("Best Mobile Game", "Umamusume: Pretty Derby", "Cygames", _game("Umamusume: Pretty Derby", None)),
                ("Best VR/AR Game", "The Midnight Walk", "MoonHood", _game("The Midnight Walk")),
                ("Best Action Game", "Hades II", "Supergiant Games", _game("Hades II")),
                ("Best Action/Adventure Game", "Hollow Knight: Silksong", "Team Cherry", _game("Hollow Knight: Silksong")),
                ("Best Role Playing Game", _CLAIR, "Sandfall Interactive", _game(_CLAIR)),
                ("Best Fighting Game", "Fatal Fury: City of the Wolves", "SNK", _game("Fatal Fury: City of the Wolves")),
                ("Best Family Game", "Donkey Kong Bananza", "Nintendo", _game("Donkey Kong Bananza")),
                ("Best Sim/Strategy Game", "Final Fantasy Tactics: The Ivalice Chronicles", "Square Enix",
                 _game("Final Fantasy Tactics: The Ivalice Chronicles")),
                ("Best Sports/Racing Game", "Mario Kart World", "Nintendo", _game("Mario Kart World")),
                ("Best Multiplayer Game", "ARC Raiders", "Embark Studios", _game("ARC Raiders")),
                ("Innovation in Accessibility", "Doom: The Dark Ages", "id Software", _game("Doom: The Dark Ages")),
                ("Best Adaptation", "The Last of Us", "Season 2, HBO", {"kind": "tv", "title": "The Last of Us", "year": 2023}),
                ("Most Anticipated Game", "Grand Theft Auto VI", "Rockstar Games", _game("Grand Theft Auto VI", 2026)),
                ("Players' Voice", "Wuthering Waves", "Kuro Games", _game("Wuthering Waves", 2024)),
                ("Best Esports Game", "Counter-Strike 2", "Valve", _game("Counter-Strike 2", 2023)),
                ("Best Esports Athlete", "Jung \"Chovy\" Ji-hoon", "League of Legends", None),
                ("Best Esports Team", "Team Vitality", "Counter-Strike 2", None),
                ("Content Creator of the Year", "MoistCr1TiKaL", "", None),
            ),
        },
        "faq": (
            ("When are The Game Awards 2026?",
             "Thursday, December 10, 2026, at the Peacock Theater in Los Angeles."),
            ("When are the nominees announced?",
             "The organizers say mid-November and had not named a day when this page was last checked. The 2025 "
             "nominees came out on November 17."),
            ("Does this ballot count toward the real vote?",
             "No. The public vote is on thegameawards.com and counts for 10% of the result. The ballot here is a "
             "prediction: you pick who you think will win and get a score after the show."),
            ("Can I change my picks?",
             "Yes, as often as you like until the show starts on December 10. After that the ballot locks."),
            ("How is the ballot scored?",
             "One point for every category you called. Categories you skipped don't count against you."),
        ),
        "sources": (
            ("thegameawards.com", "https://thegameawards.com/"),
            ("The Game Awards 2025 (Wikipedia)", "https://en.wikipedia.org/wiki/The_Game_Awards_2025"),
            ("The Game Awards (Wikipedia)", "https://en.wikipedia.org/wiki/The_Game_Awards"),
            ("GamingBible: date and start time", "https://www.gamingbible.com/news/the-game-awards-2026-date-time-tickets-378124-20261007"),
        ),
    },
    "golden-globes-2027": {
        "name": "Golden Globes 2027",
        "short": "The Golden Globes",
        "format": "Film and TV",
        "title": "Golden Globes 2027: date, nominations and your ballot",
        "search_title": "Golden Globes 2027: date, nominations, how to watch and a ballot",
        "description": ("The 84th Golden Globes are on January 10, 2027. When nominations come out, who votes, "
                        "what changed this year, where to watch and a free ballot to pick the winners."),
        "lead": ("The 84th Golden Globes are on Sunday, January 10, 2027 at the Beverly Hilton, live on CBS and "
                 "Paramount+. Nominations come out on Monday, December 7, and the ballot here opens once the list "
                 "is checked and loaded."),
        "published": "2026-11-12",
        "reviewed": "2026-11-12",
        "ceremony_day": "2027-01-10",
        "ceremony_at": "2027-01-11T00:00:00",
        "lock_label": "Sunday, January 10 at 4 p.m. Pacific",
        "watch": "CBS, streaming on Paramount+",
        "nominees_day": "2026-12-07",
        "nominees_label": "December 7, 2026",
        "nominees_note": "Nominations are announced on Monday, December 7, 2026.",
        "dates": (
            ("TV and podcast nomination ballots sent", "November 16, 2026"),
            ("Film nomination ballots sent", "November 24, 2026"),
            ("Nominations announced", "Monday, December 7, 2026"),
            ("Final ballots sent", "December 18, 2026"),
            ("Final ballots due", "January 2, 2027"),
            ("Ceremony", "Sunday, January 10, 2027"),
            ("Ballots here lock", "January 10 at 4 p.m. Pacific"),
        ),
        "sections": (
            ("chosen", "How the winners are chosen", (
                "About 300 entertainment journalists vote. The count for the 2024 ceremony was 310 voters from 76 "
                "countries. Films and series released in the calendar year are eligible.",
                "The Globes split film awards into drama and musical or comedy, so there are two best picture "
                "winners and two sets of lead acting winners each year. Last year's ceremony had 28 categories "
                "across film, TV and podcasts.",
            )),
            ("watch", "How to watch", (
                "The ceremony airs live on CBS from the Beverly Hilton in Beverly Hills and streams on Paramount+ "
                "in the United States. Nikki Glaser hosts for the third year running.",
            )),
            ("changes", "What is different this year", (
                "Podcasts got their own Globe last year, and Good Hang with Amy Poehler won the first one. For 2027 "
                "the pool of eligible podcasts grows from 25 to 30.",
                "The rules published in May 2026 also added guidelines on AI. The Cinematic and Box Office "
                "Achievement award, for the year's biggest hits, is on the timetable again.",
            )),
        ),
        "categories": [],
        "last_year": {
            "heading": "Last year: the 83rd Golden Globes",
            "intro": (
                "The 83rd ceremony was on January 11, 2026, with Nikki Glaser hosting for the second time. One "
                "Battle After Another went in with nine nominations, the most of any film, ahead of Sentimental "
                "Value with eight. On the TV side The White Lotus led with six nominations and Adolescence had five.",
            ),
            "winners": (
                ("Best Podcast (first year)", "Good Hang with Amy Poehler", "Spotify", None),
            ),
        },
        "faq": (
            ("When are the Golden Globes in 2027?",
             "Sunday, January 10, 2027, at the Beverly Hilton, live on CBS and Paramount+."),
            ("When are the 2027 Golden Globe nominations?",
             "Monday, December 7, 2026."),
            ("Who votes for the Golden Globes?",
             "About 300 entertainment journalists from around the world. The count for the 2024 ceremony was 310 "
             "voters from 76 countries."),
            ("Can I change my picks?",
             "Yes, until the ceremony starts on January 10. After that the ballot locks."),
        ),
        "sources": (
            ("AwardsWatch: 2027 Golden Globes key dates", "https://awardswatch.com/2027-golden-globes-reveal-key-dates-adds-ai-rules-expands-podcast-pool/"),
            ("83rd Golden Globe Awards (Wikipedia)", "https://en.wikipedia.org/wiki/83rd_Golden_Globe_Awards"),
            ("Golden Globe Awards (Wikipedia)", "https://en.wikipedia.org/wiki/Golden_Globe_Awards"),
        ),
    },
    "grammys-2027": {
        "name": "Grammys 2027",
        "short": "The Grammys",
        "format": "Music",
        "title": "Grammys 2027: date, nominations and your ballot",
        "search_title": "Grammys 2027: date, nominations, new categories and a ballot",
        "description": ("The 69th Grammy Awards are on February 7, 2027, on ABC for the first time since 1972. When "
                        "nominations come out, the new categories, last year's winners and a free ballot."),
        "lead": ("The 69th Grammy Awards are on Sunday, February 7, 2027 at Crypto.com Arena in Los Angeles. "
                 "Nominations are announced on Monday, November 16, and the ballot here opens once the list is "
                 "checked and loaded."),
        "published": "2026-11-12",
        "reviewed": "2026-11-12",
        "ceremony_day": "2027-02-07",
        "ceremony_at": "2027-02-08T00:00:00",
        "lock_label": "Sunday, February 7 at 4 p.m. Pacific",
        "watch": "ABC, streaming on Disney+ and Hulu",
        "nominees_day": "2026-11-16",
        "nominees_label": "November 16, 2026",
        "nominees_note": ("Nominations are announced on Monday, November 16, 2026. The livestream starts at 7:45 a.m. "
                          "Eastern on Grammy.com and the Grammys' YouTube channel, and the full list goes up at 9 a.m."),
        "dates": (
            ("Eligible releases", "August 30, 2025 to August 29, 2026"),
            ("Nominations announced", "Monday, November 16, 2026"),
            ("Final-round voting", "December 10, 2026 to January 7, 2027"),
            ("Ceremony", "Sunday, February 7, 2027, 7 p.m. Eastern"),
            ("Venue", "Crypto.com Arena, Los Angeles"),
            ("Ballots here lock", "February 7 at 4 p.m. Pacific"),
        ),
        "sections": (
            ("chosen", "How the winners are chosen", (
                "Voting members of the Recording Academy pick the winners. The first round, which decides the "
                "nominees, ran from October 12 to 22. The final round runs from December 10, 2026 to January 7, 2027.",
                "Recordings released between August 30, 2025 and August 29, 2026 are eligible, by Grammy.com's "
                "dates. Anything from this autumn waits for the 2028 show.",
            )),
            ("watch", "How to watch", (
                "The show moves to ABC this year, with streams on Disney+ and Hulu. It is the first Grammys "
                "broadcast on ABC since 1972, under a ten-year deal with Disney announced in October 2024. It "
                "starts at 7 p.m. Eastern, 4 p.m. Pacific.",
                "No host had been named when this page was last checked. Trevor Noah hosted for the sixth and last "
                "time in 2026.",
            )),
            ("changes", "New categories this year", (
                "There are 100 categories, five of them new or returning: Best Asian Pop Music Performance, Best "
                "R&B Collaboration or Duo/Group Performance, Best Traditional Pop Vocal Performance, Best Latin "
                "Song, and Best Traditional Folk Album, which is back for the first time since 2011. Best Folk "
                "Album is now Best Contemporary Folk Album.",
                "A hundred categories is too many for one ballot. The one here will cover the four general awards "
                "(Album, Record and Song of the Year, and Best New Artist) and the main genre album categories.",
            )),
        ),
        "categories": [],
        "last_year": {
            "heading": "Last year: the 68th Grammy Awards",
            "intro": (
                "The 2026 show was on February 1 at Crypto.com Arena, the last one on CBS. Kendrick Lamar won five "
                "awards, the most of the night, and Bad Bunny's Debí Tirar Más Fotos won Album of the Year.",
            ),
            "winners": (
                ("Album of the Year", "Debí Tirar Más Fotos", "Bad Bunny",
                 {"kind": "album", "title": "Debí Tirar Más Fotos", "year": 2025, "creator": "Bad Bunny"}),
                ("Record of the Year", "Luther", "Kendrick Lamar and SZA", None),
                ("Song of the Year", "Wildflower", "Billie Eilish", None),
                ("Best New Artist", "Olivia Dean", "", None),
                ("Best Pop Vocal Album", "Mayhem", "Lady Gaga",
                 {"kind": "album", "title": "Mayhem", "year": 2025, "creator": "Lady Gaga"}),
                ("Best Rap Album", "GNX", "Kendrick Lamar",
                 {"kind": "album", "title": "GNX", "year": 2024, "creator": "Kendrick Lamar"}),
                ("Best Rock Album", "Never Enough", "Turnstile",
                 {"kind": "album", "title": "Never Enough", "year": 2025, "creator": "Turnstile"}),
                ("Best Alternative Music Album", "Songs of a Lost World", "The Cure",
                 {"kind": "album", "title": "Songs of a Lost World", "year": 2024, "creator": "The Cure"}),
                ("Best R&B Album", "Mutt", "Leon Thomas",
                 {"kind": "album", "title": "Mutt", "year": 2024, "creator": "Leon Thomas"}),
                ("Best Dance/Electronic Album", "Eusexua", "FKA twigs",
                 {"kind": "album", "title": "Eusexua", "year": 2025, "creator": "FKA twigs"}),
                ("Best Música Urbana Album", "Debí Tirar Más Fotos", "Bad Bunny",
                 {"kind": "album", "title": "Debí Tirar Más Fotos", "year": 2025, "creator": "Bad Bunny"}),
                ("Best Score Soundtrack for Video Games", "Sword of the Sea", "Austin Wintory", None),
            ),
        },
        "faq": (
            ("When are the Grammys in 2027?",
             "Sunday, February 7, 2027, at Crypto.com Arena in Los Angeles, starting at 7 p.m. Eastern."),
            ("What channel are the 2027 Grammys on?",
             "ABC, with streams on Disney+ and Hulu. It is the first Grammys broadcast on ABC since 1972."),
            ("When are the 2027 Grammy nominations?",
             "Monday, November 16, 2026. The livestream starts at 7:45 a.m. Eastern and the full list is posted on "
             "Grammy.com at 9 a.m."),
            ("Which releases are eligible?",
             "Recordings released between August 30, 2025 and August 29, 2026."),
            ("Can I change my picks?",
             "Yes, until the show starts on February 7. After that the ballot locks."),
        ),
        "sources": (
            ("Grammy.com: how to watch the nominations", "https://www.grammy.com/news/how-to-watch-2027-grammys-nominations/"),
            ("Grammy.com: 69th Grammy Awards", "https://www.grammy.com/awards/69th-annual-grammy-awards-2027/"),
            ("69th Annual Grammy Awards (Wikipedia)", "https://en.wikipedia.org/wiki/69th_Annual_Grammy_Awards"),
            ("68th Annual Grammy Awards (Wikipedia)", "https://en.wikipedia.org/wiki/68th_Annual_Grammy_Awards"),
        ),
    },
    "oscars-2027": {
        "name": "Oscars 2027",
        "short": "The Oscars",
        "format": "Film",
        "title": "Oscars 2027: date, nominations and your ballot",
        "search_title": "Oscars 2027: date, nominations, key dates and a ballot",
        "description": ("The 99th Academy Awards are on March 14, 2027. Shortlist, nomination and voting dates, what "
                        "changed in the rules, last year's winners and a free ballot to pick this year's."),
        "lead": ("The 99th Academy Awards are on Sunday, March 14, 2027 at the Dolby Theatre in Hollywood, live on "
                 "ABC at 7 p.m. Eastern. Nominations are announced on Thursday, January 21, and the ballot here "
                 "opens once the list is checked and loaded."),
        "published": "2026-11-12",
        "reviewed": "2026-11-12",
        "ceremony_day": "2027-03-14",
        "ceremony_at": "2027-03-14T23:00:00",
        "lock_label": "Sunday, March 14 at 4 p.m. Pacific",
        "watch": "ABC, streaming on Hulu",
        "nominees_day": "2027-01-21",
        "nominees_label": "January 21, 2027",
        "nominees_note": "Nominations are announced on Thursday, January 21, 2027.",
        "dates": (
            ("Shortlists announced", "Tuesday, December 15, 2026"),
            ("Nominations voting", "January 11 to 15, 2027"),
            ("Nominations announced", "Thursday, January 21, 2027"),
            ("Final voting", "February 25 to March 4, 2027"),
            ("Ceremony", "Sunday, March 14, 2027, 7 p.m. Eastern"),
            ("Venue", "Dolby Theatre, Hollywood"),
            ("Ballots here lock", "March 14 at 4 p.m. Pacific"),
        ),
        "sections": (
            ("chosen", "How the winners are chosen", (
                "Members of the Academy of Motion Picture Arts and Sciences vote in two rounds. Nominations voting "
                "runs from January 11 to 15, 2027, and final voting from February 25 to March 4. There are 24 "
                "categories.",
                "Several categories, including documentary, international feature, score and song, publish a "
                "shortlist first, on December 15, 2026. It is the first look at which films are still in the race "
                "there.",
            )),
            ("watch", "How to watch", (
                "The ceremony airs live on ABC at 7 p.m. Eastern, 4 p.m. Pacific, and streams on Hulu. Conan "
                "O'Brien hosts for the third year in a row.",
            )),
            ("changes", "What changed in the rules", (
                "The international feature category now also accepts films that won the top prize at Berlin, Busan, "
                "Cannes, Sundance, Toronto or Venice. An actor can be nominated more than once in the same "
                "category. And the acting and writing categories have new rules on generative AI.",
                "The casting award is in its second year. It was handed out for the first time in 2026, to "
                "Cassandra Kulukundis for One Battle After Another.",
            )),
        ),
        "categories": [],
        "last_year": {
            "heading": "Last year: the 98th Academy Awards",
            "intro": (
                "The 2026 ceremony was on March 15. One Battle After Another won six Oscars, including Best "
                "Picture, Director and the first casting award. Sinners went in with a record 16 nominations and "
                "won four.",
            ),
            "winners": (
                ("Best Picture", "One Battle After Another", "",
                 {"kind": "movie", "title": "One Battle After Another", "year": 2025, "creator": "Paul Thomas Anderson"}),
                ("Director", "Paul Thomas Anderson", "One Battle After Another",
                 {"kind": "movie", "title": "One Battle After Another", "year": 2025, "creator": "Paul Thomas Anderson"}),
                ("Actor", "Michael B. Jordan", "Sinners",
                 {"kind": "movie", "title": "Sinners", "year": 2025, "creator": "Ryan Coogler"}),
                ("Actress", "Jessie Buckley", "Hamnet",
                 {"kind": "movie", "title": "Hamnet", "year": 2025, "creator": "Chloé Zhao"}),
                ("Supporting Actor", "Sean Penn", "One Battle After Another",
                 {"kind": "movie", "title": "One Battle After Another", "year": 2025, "creator": "Paul Thomas Anderson"}),
                ("Supporting Actress", "Amy Madigan", "Weapons",
                 {"kind": "movie", "title": "Weapons", "year": 2025, "creator": "Zach Cregger"}),
                ("Original Screenplay", "Ryan Coogler", "Sinners",
                 {"kind": "movie", "title": "Sinners", "year": 2025, "creator": "Ryan Coogler"}),
                ("Adapted Screenplay", "Paul Thomas Anderson", "One Battle After Another",
                 {"kind": "movie", "title": "One Battle After Another", "year": 2025, "creator": "Paul Thomas Anderson"}),
                ("Animated Feature", "KPop Demon Hunters", "",
                 {"kind": "movie", "title": "KPop Demon Hunters", "year": 2025}),
                ("International Feature", "Sentimental Value", "Norway",
                 {"kind": "movie", "title": "Sentimental Value", "year": 2025, "creator": "Joachim Trier"}),
                ("Documentary Feature", "Mr Nobody Against Putin", "",
                 {"kind": "movie", "title": "Mr Nobody Against Putin", "year": 2025}),
                ("Original Score", "Ludwig Göransson", "Sinners",
                 {"kind": "movie", "title": "Sinners", "year": 2025, "creator": "Ryan Coogler"}),
                ("Original Song", "Golden", "KPop Demon Hunters",
                 {"kind": "movie", "title": "KPop Demon Hunters", "year": 2025}),
                ("Casting", "Cassandra Kulukundis", "One Battle After Another",
                 {"kind": "movie", "title": "One Battle After Another", "year": 2025, "creator": "Paul Thomas Anderson"}),
                ("Cinematography", "Autumn Durald Arkapaw", "Sinners",
                 {"kind": "movie", "title": "Sinners", "year": 2025, "creator": "Ryan Coogler"}),
                ("Visual Effects", "Avatar: Fire and Ash", "",
                 {"kind": "movie", "title": "Avatar: Fire and Ash", "year": 2025, "creator": "James Cameron"}),
            ),
        },
        "faq": (
            ("When are the Oscars in 2027?",
             "Sunday, March 14, 2027, at the Dolby Theatre in Hollywood, live on ABC at 7 p.m. Eastern."),
            ("When are the 2027 Oscar nominations?",
             "Thursday, January 21, 2027. Shortlists in several categories come first, on December 15, 2026."),
            ("Who is hosting the 2027 Oscars?",
             "Conan O'Brien, for the third year in a row."),
            ("Can I change my picks?",
             "Yes, until the ceremony starts on March 14. After that the ballot locks."),
        ),
        "sources": (
            ("TheWrap: Academy sets 2027 and 2028 dates", "https://www.thewrap.com/creative-content/movies/academy-sets-2027-and-2028-oscars-dates/"),
            ("AwardsWatch: Oscars dates", "https://awardswatch.com/the-oscars-set-march-dates-for-99th-and-100th-academy-awards/"),
            ("99th Academy Awards (Wikipedia)", "https://en.wikipedia.org/wiki/99th_Academy_Awards"),
            ("98th Academy Awards (Wikipedia)", "https://en.wikipedia.org/wiki/98th_Academy_Awards"),
        ),
    },
}

# Calendar order: by ceremony.
ORDER = ("the-game-awards-2026", "golden-globes-2027", "grammys-2027", "oscars-2027")
