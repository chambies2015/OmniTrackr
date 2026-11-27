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

from .dated_text import Dated

BALLOT_WINDOW_QUESTION = "When can I fill in a ballot?"

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
    "reviewed": "2026-11-23",
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
    "tips": (
        "Each show's voters lean a different way, and knowing which way is most of what a good ballot comes down to.",
        "At the Game Awards the jury's vote outweighs the public's nine to one. When critics and players disagree "
        "about a game, side with the critics.",
        "At the Golden Globes, read the nominations before you assume which side a film is on. The studio picks "
        "drama or musical or comedy, and a film you would call a drama can turn up on the comedy list.",
        "At the Grammys every voting member can vote in the six General Field awards, among them Album, Record and "
        "Song of the Year and Best New Artist. Most members then vote in no more than ten other categories, spread "
        "over up to three genre fields where they work. The general awards reflect the whole membership, and the "
        "genre awards the people closest to that music.",
        "At the Oscars, Best Picture is counted by ranking, which favors the film most voters like over the one a "
        "few voters love. For that category, pick the nominee you think almost everyone would put near the top.",
    ),
    "faq": (
        ("When does awards season start?",
         Dated("The Game Awards open it on December 10, 2026. The Golden Globes follow on January 10, 2027, the Grammys on "
               "February 7 and the Oscars close it on March 14.",
               ("2026-12-11",
                "The Game Awards opened it on December 10, 2026. The Golden Globes follow on January 10, 2027, the "
                "Grammys on February 7 and the Oscars close it on March 14."),
               ("2027-01-11",
                "The Game Awards opened it on December 10, 2026, and the Golden Globes followed on January 10, 2027. "
                "The Grammys are on February 7 and the Oscars close it on March 14."))),
        # The answer after the first sentence is written from each show's state when the page is drawn
        # (awards.season_faq), so it never promises a date that has already gone by.
        (BALLOT_WINDOW_QUESTION, "From the day a show's nominees are announced until its ceremony starts."),
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
        ("Grammy.com: the voting process", "https://www.grammy.com/awards/voting-process/"),
        ("Oscars dates (TheWrap)", "https://www.thewrap.com/creative-content/movies/academy-sets-2027-and-2028-oscars-dates/"),
        ("10th Crunchyroll Anime Awards (Wikipedia)", "https://en.wikipedia.org/wiki/10th_Crunchyroll_Anime_Awards"),
    ),
}


def _game(title: str, year=2025) -> dict:
    return {"kind": "game", "title": title, "year": year}


def _album(name: str, artist: str) -> dict:
    return {"name": name, "detail": artist, "kind": "album", "creator": artist}


def _track(name: str, detail: str) -> dict:
    return {"name": name, "detail": detail}


_CLAIR = "Clair Obscur: Expedition 33"

# The 69th Grammy Awards ballot: the four general awards, eight genre album categories and the video game
# score award. Typed from Grammy.com's list and checked against ABC News, Audacy and Us Weekly on November 17,
# 2026. Titles and names are styled the way the Recording Academy prints them.
_GRAMMYS_2027 = [
    {"name": "Album of the Year",
     "blurb": "For a whole album: the artist, and the producers, engineers and songwriters who worked on it.",
     "nominees": [
         _album("Lost Weekend", "Phoebe Bridgers"),
         _album("The Art of Loving", "Olivia Dean"),
         _album("Dandelion", "Ella Langley"),
         _album("The Romantic", "Bruno Mars"),
         _album("THIS MUSIC MAY CONTAIN HOPE.", "RAYE"),
         _album("you seem pretty sad for a girl so in love", "Olivia Rodrigo"),
         _album("LUX (Complete Works)", "ROSALÍA"),
         _album("The Life of a Showgirl", "Taylor Swift"),
     ]},
    {"name": "Record of the Year",
     "blurb": "For one recording: the performance and the production of a single track.",
     "nominees": [
         _track("Man I Need", "Olivia Dean"),
         _track("Choosin' Texas", "Ella Langley"),
         _track("I Just Might", "Bruno Mars"),
         _track("WHERE IS MY HUSBAND!", "RAYE"),
         _track("the cure", "Olivia Rodrigo"),
         _track("Berghain", "ROSALÍA, Björk and Yves Tumor"),
         _track("The Fate of Ophelia", "Taylor Swift"),
         _track("Dracula", "Tame Impala and JENNIE"),
     ]},
    {"name": "Song of the Year",
     "blurb": "A songwriters' award: it goes to the people who wrote the song.",
     "nominees": [
         _track("Berghain", "ROSALÍA, Björk and Yves Tumor. Written by Björk, Noah Goldstein, Jake Miller, "
                            "ROSALÍA and Dylan Wiggins"),
         _track("Choosin' Texas", "Ella Langley. Written by Luke Dick, Miranda Lambert, Ella Langley and "
                                  "Joybeth Taylor"),
         _track("the cure", "Olivia Rodrigo. Written by Daniel Nigro and Olivia Rodrigo"),
         _track("hate that i made you love me", "Ariana Grande. Written by Ariana Grande, Max Martin and Ilya"),
         _track("I Knew It, I Knew You", "Taylor Swift, from Toy Story 5. Written by Jack Antonoff and Taylor Swift"),
         _track("Man I Need", "Olivia Dean. Written by Olivia Dean, Tobias Jesso, Jr. and Zach Nahome"),
         _track("Risk It All", "Bruno Mars. Written by Dernst Emile II, James Fauntleroy, Philip Lawrence and "
                               "Bruno Mars"),
         _track("WHERE IS MY HUSBAND!", "RAYE. Written by RAYE and Mike Sabath"),
     ]},
    {"name": "Best New Artist",
     "nominees": [
         {"name": "Angine de Poitrine"},
         {"name": "Geese"},
         {"name": "Ella Langley"},
         {"name": "Slayyyter"},
         {"name": "Sienna Spiro"},
         {"name": "Don Toliver"},
         {"name": "Remi Wolf"},
         {"name": "The Womack Sisters"},
     ]},
    {"name": "Best Pop Vocal Album",
     "nominees": [
         _album("The Art of Loving", "Olivia Dean"),
         _album("petal", "Ariana Grande"),
         _album("The Romantic", "Bruno Mars"),
         _album("THIS MUSIC MAY CONTAIN HOPE.", "RAYE"),
         _album("you seem pretty sad for a girl so in love", "Olivia Rodrigo"),
     ]},
    {"name": "Best Rap Album",
     "nominees": [
         _album("DILLAGENCE II", "Busta Rhymes"),
         _album("AM I THE DRAMA?", "Cardi B"),
         _album("God Gotta Afro & Gold Hoops", "Rapsody"),
         _album("OCTANE", "Don Toliver"),
         _album("everything is a lot.", "Wale"),
         _album("BULLY - DELUXE", "Kanye West"),
     ]},
    {"name": "Best Rock Album",
     "nominees": [
         _album("Vol. II", "Angine de Poitrine"),
         _album("Your Favorite Toy", "Foo Fighters"),
         _album("The Wow! Signal", "Muse"),
         _album("Foreign Tongues", "The Rolling Stones"),
         _album("Frozen Charlotte", "Jack White"),
     ]},
    {"name": "Best Alternative Music Album",
     "nominees": [
         _album("I Must Be Dreaming", "Alabama Shakes"),
         _album("Lost Weekend", "Phoebe Bridgers"),
         _album("Music, Fashion, Film", "Charli xcx"),
         _album("Getting Killed", "Geese"),
         _album("The Mountain", "Gorillaz"),
         _album("LUX (Complete Works)", "ROSALÍA"),
     ]},
    {"name": "Best R&B Album",
     "nominees": [
         _album("BROWN (The Chocolate Edition)", "Chris Brown"),
         _album("When The City Sleeps", "Alex Isley"),
         _album("Kehlani", "Kehlani"),
         _album("Saturday Night", "PJ Morton"),
         _album("To Whom This May Concern", "Jill Scott"),
     ]},
    {"name": "Best Dance/Electronic Album",
     "nominees": [
         _album("CONFESSIONS II", "Madonna"),
         _album("Sexistential", "Robyn"),
         _album("SOMA", "Skrillex"),
         _album("WOR$T GIRL IN AMERICA", "Slayyyter"),
         _album("Deadbeat", "Tame Impala"),
     ]},
    {"name": "Best Contemporary Country Album",
     "nominees": [
         _album("Mount Pleasant", "Kelsea Ballerini"),
         _album("Cherry Valley", "Carter Faith"),
         _album("Dandelion", "Ella Langley"),
         _album("Cloud 9", "Megan Moroney"),
         _album("Middle of Nowhere", "Kacey Musgraves"),
     ]},
    {"name": "Best Música Urbana Album",
     "nominees": [
         _album("Cosa Nuestra: Capítulo 0", "Rauw Alejandro"),
         _album("OMERTA", "J Balvin and Ryan Castro"),
         _album("HOPI SENDÉ", "Ryan Castro"),
         _album("OMAKASE", "Alvaro Diaz"),
         _album("EL GREEN PRINT: La Saga (Disc 1) - FEID VS FERXXO", "Feid"),
         _album("Do Not Disturb: Late Checkout", "Young Miko"),
     ]},
    {"name": "Best Score Soundtrack for Video Games and Other Interactive Media",
     "blurb": "For the composer of a game's score. The nominees are listed by game.",
     "nominees": [
         {"name": "Avatar: Frontiers of Pandora - From the Ashes", "detail": "John Paesano, composer",
          "kind": "game", "title": "Avatar: Frontiers of Pandora", "year": 2023},
         {"name": "007: First Light", "detail": "Joe Henson and Alexis Leon Smith, composers", "kind": "game",
          "aka": ("007 First Light",)},
         {"name": "Ghost of Yōtei", "detail": "Toma Otowa, composer", "kind": "game", "year": 2025,
          "aka": ("Ghost of Yotei",)},
         {"name": "Marvel's Wolverine", "detail": "David Fleming, composer", "kind": "game"},
         {"name": "Star Wars: Zero Company", "detail": "Gordy Haab, composer", "kind": "game"},
     ]},
]


def _nominee(name: str, detail: str, year=None, *aka: str) -> dict:
    """A nominated game, with its studio or publisher as the second line."""
    entry = {"name": name, "detail": detail, "kind": "game"}
    if year:
        entry["year"] = year
    if aka:
        entry["aka"] = aka
    return entry


def _for_game(name: str, game: str) -> dict:
    """A performer, credited with the game they are nominated for."""
    return {"name": name, "detail": game, "kind": "game", "title": game}


_GTA6 = _nominee("Grand Theft Auto VI", "Rockstar Games", None, "GTA 6", "GTA VI", "Grand Theft Auto 6")
_CONTROL = _nominee("Control Resonant", "Remedy Entertainment / Annapurna")
_REQUIEM = _nominee("Resident Evil Requiem", "Capcom")
_PHANTOM = _nominee("Phantom Blade Zero", "S-GAME")
_ZELDA = _nominee("The Legend of Zelda: Ocarina of Time", "Nintendo")
_BOND = _nominee("007 First Light", "IO Interactive", None, "007: First Light")
_PRAGMATA = _nominee("Pragmata", "Capcom")
_DAWNWALKER = _nominee("The Blood of Dawnwalker", "Rebel Wolves / Bandai Namco")
_ACE = _nominee("Ace Combat 8: Wings of Theve", "Bandai Namco Aces / Bandai Namco")
_MIXTAPE = _nominee("Mixtape", "Beethoven & Dinosaur / Annapurna")
_RACER = _nominee("Star Wars: Galactic Racer", "Fuse Games / Secret Mode")
_BIG_WALK = _nominee("Big Walk", "House House / Panic")
_CAIRN = _nominee("Cairn", "The Game Bakers")
_MEWGENICS = _nominee("Mewgenics", "Edmund McMillen and Tyler Glaiel")
_ORBITALS = _nominee("Orbitals", "Shapefarm / Kepler")
_GEARS = _nominee("Gears of War: E-Day", "The Coalition / Xbox Game Studios")
_FORZA = _nominee("Forza Horizon 6", "Playground Games / Xbox Game Studios")
_SPORTS_RESORT = _nominee("Nintendo Switch Sports Resort", "Nintendo")
_POKOPIA = _nominee("Pokémon Pokopia", "Game Freak / Omega Force / Nintendo", None, "Pokemon Pokopia")
_NO_MANS_SKY = _nominee("No Man's Sky", "Hello Games", 2016)
_WITCHER_3 = _nominee("The Witcher 3: Wild Hunt", "CD Projekt Red", 2015)

# The Game Awards 2026 ballot: all 30 categories announced on November 17, 2026 (Players' Voice has no nominee
# list; fans vote on it in rounds before the show). thegameawards.com turns automated readers away, so the lists
# were typed from MobileSyrup's and checked against Noisy Pixel's, with Push Square and Nintendo Everything for
# most categories. Release years are only set for games that have been out for years.
_GAME_AWARDS_2026 = [
    {"name": "Game of the Year", "nominees": [_BOND, _CONTROL, _GTA6, _PHANTOM, _REQUIEM, _ZELDA]},
    {"name": "Best Game Direction", "nominees": [_CONTROL, _GTA6, _PHANTOM, _PRAGMATA, _REQUIEM]},
    {"name": "Best Narrative", "nominees": [_BOND, _CONTROL, _GTA6, _REQUIEM, _DAWNWALKER]},
    {"name": "Best Art Direction", "nominees": [
        _CONTROL, _GTA6, _nominee("Mouse: P.I. For Hire", "Fumi / PlaySide"), _PHANTOM, _ZELDA]},
    {"name": "Best Score and Music", "nominees": [_ACE, _GTA6, _MIXTAPE, _PHANTOM, _ZELDA]},
    {"name": "Best Audio Design", "nominees": [_ACE, _CONTROL, _GTA6, _REQUIEM, _RACER]},
    {"name": "Best Performance", "nominees": [
        _for_game("Angela Sant'Albano", "Resident Evil Requiem"),
        _for_game("Liam McIntyre", "Marvel's Wolverine"),
        _for_game("Manni L. Perez", "Grand Theft Auto VI"),
        _for_game("Patrick Gibson", "007 First Light"),
        _for_game("Rahul Kohli", "Saros"),
    ]},
    {"name": "Innovation in Accessibility",
     "blurb": "For features that let more people play.",
     "nominees": [
         _nominee("Assassin's Creed Black Flag Resynced", "Ubisoft Singapore / Ubisoft", None,
                  "Assassin's Creed: Black Flag Resynced"),
         _FORZA, _GEARS,
         _nominee("Marvel's Wolverine", "Insomniac / Sony Interactive"),
         _nominee("Rhythm Heaven Groove", "Nintendo"),
     ]},
    {"name": "Games for Impact",
     "blurb": "For a game with something to say about the world outside it.",
     "nominees": [
         _BIG_WALK, _CAIRN,
         _nominee("Forever Ago", "Third Shift / Annapurna"),
         _nominee("Life is Strange: Reunion", "Deck Nine / Square Enix"),
         _nominee("lily's world XD", "SonderingEmily / Kwalee"),
         _MIXTAPE,
     ]},
    {"name": "Best Ongoing Game",
     "blurb": "For a game that is still getting new things to do, whenever it first came out.",
     "nominees": [
         _nominee("Arc Raiders", "Embark Studios", 2025),
         _nominee("Final Fantasy XIV", "Square Enix", None, "Final Fantasy 14", "Final Fantasy XIV Online"),
         _nominee("Fortnite", "Epic Games", 2017),
         _NO_MANS_SKY, _WITCHER_3,
     ]},
    {"name": "Best Community Support", "nominees": [
        _nominee("Crimson Desert", "Pearl Abyss"),
        _nominee("Helldivers 2", "Arrowhead Game Studios / Sony Interactive", 2024),
        _NO_MANS_SKY, _WITCHER_3,
        _nominee("Warframe", "Digital Extremes", 2013),
    ]},
    {"name": "Best Independent Game", "nominees": [
        _BIG_WALK, _CAIRN,
        _nominee("Denshattack!", "Undercoders / Fireshine Games"),
        _MEWGENICS,
        _nominee("Mina the Hollower", "Yacht Club Games"),
    ]},
    {"name": "Best Debut Indie Game",
     "blurb": "For a studio's first game.",
     "nominees": [
         _nominee("Dressmaker", "Cozy Lives / Free Lives"),
         _nominee("Esoteric Ebb", "Christoffer Bodegård / Raw Fury"),
         _ORBITALS,
         _nominee("Replaced", "Sad Cat Studios / Thunderful"),
         _nominee("Silver Pines", "Wych Elm / Team17"),
     ]},
    {"name": "Best Mobile Game", "nominees": [
        _nominee("Arknights: Endfield", "Hypergryph / Gryphline"),
        _nominee("Monster Hunter Outlanders", "TiMi Studio Group / Level Infinite"),
        _nominee("Neverness to Everness", "Hotta Studio / Perfect World Games"),
        _nominee("Pokémon Champions", "The Pokémon Works / The Pokémon Company", None, "Pokemon Champions"),
        _nominee("Where Winds Meet", "Everstone Studio / NetEase Games"),
    ]},
    {"name": "Best VR/AR Game", "nominees": [
        _nominee("Forefront", "Triangle Factory"),
        _nominee("Into the Radius 2", "CM Immersive"),
        _nominee("Little Nightmares VR: Altered Echoes", "ICONIK / Bandai Namco"),
        _nominee("Teenage Mutant Ninja Turtles: Empire City", "Cortopia Studios / Beyond Frames"),
        _nominee("Thief VR: Legacy of Shadow", "Maze Theory / Vertigo Games"),
    ]},
    {"name": "Best Action Game", "nominees": [
        _ACE, _GEARS,
        _nominee("Onimusha: Way of the Sword", "Capcom"),
        _PHANTOM,
        _nominee("Saros", "Housemarque / Sony Interactive"),
    ]},
    {"name": "Best Action/Adventure Game", "nominees": [_BOND, _CONTROL, _GTA6, _PRAGMATA, _REQUIEM, _ZELDA]},
    {"name": "Best Role Playing Game", "nominees": [
        _nominee("Final Fantasy Resonance", "Lancarse / Square Enix"),
        _nominee("Fire Emblem: Fortune's Weave", "Intelligent Systems / Nintendo"),
        _nominee("Monster Hunter Stories 3: Twisted Reflection", "Capcom"),
        _DAWNWALKER,
        _nominee("Trails in the Sky 2nd Chapter", "Nihon Falcom / GungHo"),
    ]},
    {"name": "Best Fighting Game", "nominees": [
        _nominee("2XKO", "Riot Games"),
        _nominee("Avatar Legends: The Fighting Game", "Gameplay Group / Paramount Games"),
        _nominee("Invincible VS", "Quarter Up / Skybound Games"),
        _nominee("Marvel Tōkon: Fighting Souls", "Arc System Works / Sony Interactive", None,
                 "Marvel Tokon: Fighting Souls"),
        _nominee("My Hero Academia: All's Justice", "Byking / Bandai Namco"),
    ]},
    {"name": "Best Family Game", "nominees": [
        _BIG_WALK,
        _nominee("Lego Batman: Legacy of the Dark Knight", "TT Games / Warner Bros. Games"),
        _SPORTS_RESORT, _POKOPIA,
        _nominee("Yoshi and the Mysterious Book", "Good-Feel / Nintendo"),
    ]},
    {"name": "Best Sim/Strategy Game", "nominees": [
        _MEWGENICS,
        _nominee("Planet Zoo 2", "Frontier Developments"),
        _POKOPIA,
        _nominee("Slay the Spire 2", "Mega Crit"),
        _nominee("Star Wars Zero Company", "Bit Reactor / Electronic Arts", None, "Star Wars: Zero Company"),
    ]},
    {"name": "Best Sports/Racing Game", "nominees": [
        _nominee("EA Sports FC 27", "EA Vancouver / EA Romania"),
        _FORZA, _SPORTS_RESORT,
        _nominee("Screamer", "Milestone"),
        _RACER,
    ]},
    {"name": "Best Multiplayer Game", "nominees": [
        _BIG_WALK,
        _nominee("Call of Duty: Modern Warfare 4", "Infinity Ward / Activision"),
        _GEARS,
        _nominee("Marathon", "Bungie / Sony Interactive"),
        _nominee("Meccha Chameleon", "Lemorion_1224"),
        _ORBITALS,
    ]},
    {"name": "Best Adaptation",
     "blurb": "For a film or series based on a game.",
     "nominees": [
         {"name": "Cyberpunk: Edgerunners 2", "detail": "Studio Trigger / CD Projekt Red / Netflix", "kind": "anime"},
         {"name": "Fallout (Season 2)", "detail": "Kilter Films / Bethesda / Amazon MGM Studios", "kind": "tv",
          "title": "Fallout", "year": 2024},
         {"name": "Mortal Kombat II", "detail": "New Line Cinema / Atomic Monster / Warner Bros. Pictures",
          "kind": "movie", "year": 2026},
         {"name": "The Super Mario Galaxy Movie", "detail": "Illumination / Nintendo / Universal Pictures",
          "kind": "movie", "year": 2026},
         {"name": "Resident Evil", "detail": "Constantin / PlayStation Productions / Columbia Pictures",
          "kind": "movie", "year": 2026},
     ]},
    {"name": "Most Anticipated Game",
     "blurb": "For a game that isn't out yet.",
     "nominees": [
         _nominee("Fable", "Playground Games / Xbox Game Studios"),
         _nominee("Final Fantasy VII Revelation", "Square Enix", None, "Final Fantasy 7 Revelation"),
         _nominee("God of War Laufey", "Santa Monica Studio / Sony Interactive"),
         _nominee("Resident Evil Veronica", "Capcom"),
         _nominee("The Witcher IV", "CD Projekt Red"),
     ]},
    {"name": "Best User Creation",
     "blurb": "For a mod or a player-made game built inside another game.",
     "nominees": [
         {"name": "A Dream of Silence: Revamped", "detail": "For Baldur's Gate 3, by lizardphunk"},
         {"name": "Create Aeronautics", "detail": "For Minecraft, by Simulated Team"},
         {"name": "Nopixel V", "detail": "For Grand Theft Auto Online, by Nopixel Studios"},
         {"name": "Star Wars Droid Tycoon", "detail": "For Fortnite, by FOAD"},
         {"name": "TTK Testing", "detail": "For Roblox, by Sable Digital"},
     ]},
    {"name": "Content Creator of the Year", "nominees": [
        {"name": "CDawg"}, {"name": "Cellbit"}, {"name": "iShowSpeed"}, {"name": "LilSimsie"}, {"name": "OhnePixel"},
    ]},
    {"name": "Best Esports Game", "nominees": [
        _nominee("Counter-Strike 2", "Valve", 2023),
        _nominee("DOTA 2", "Valve", 2013),
        _nominee("League of Legends", "Riot Games", 2009),
        _nominee("Mobile Legends: Bang Bang", "Moonton"),
        _nominee("Valorant", "Riot Games", 2020),
    ]},
    {"name": "Best Esports Athlete", "nominees": [
        {"name": "Chovy", "detail": "Gen.G"},
        {"name": "Donk", "detail": "Team Spirit"},
        {"name": "Erde", "detail": "LOUD"},
        {"name": "Yatoro", "detail": "Team Spirit"},
        {"name": "ZywOo", "detail": "Team Vitality"},
    ]},
    {"name": "Best Esports Team", "nominees": [
        {"name": "Gen.G", "detail": "League of Legends"},
        {"name": "LOUD", "detail": "Valorant"},
        {"name": "Team Falcons (Counter-Strike 2)"},
        {"name": "Team Falcons (Rocket League)"},
        {"name": "Team Spirit", "detail": "DOTA 2"},
        {"name": "Team Vitality", "detail": "Counter-Strike 2"},
    ]},
]

SHOWS = {
    "the-game-awards-2026": {
        "name": "The Game Awards 2026",
        "short": "The Game Awards",
        "ballot_name": "Game Awards",  # "The Game Awards ballot is open now."
        "nominations_name": "Game Awards",  # "Game Awards nominations on ..."
        "format": "Video games",
        "title": "The Game Awards 2026: date, nominees and your ballot",
        "search_title": "The Game Awards 2026: nominees, date, how to watch and a ballot",
        "description": ("The Game Awards 2026 are on December 10 in Los Angeles. Every nominee in all 30 categories, "
                        "who leads, where to watch, last year's results and a free ballot to pick the winners."),
        "lead": ("The Game Awards 2026 are on Thursday, December 10 at the Peacock Theater in Los Angeles. The "
                 "nominees came out on November 17, with Grand Theft Auto VI in front on eight. The ballot below "
                 "is open: pick a winner in each of 30 categories, save it, and see your score once the show is over."),
        "published": "2026-11-12",
        "reviewed": "2026-11-17",
        "ceremony_day": "2026-12-10",
        "ceremony_at": "2026-12-11T00:30:00",
        "lock_label": "Thursday, December 10 at 4:30 p.m. Pacific",
        "watch": "Free streams on YouTube, Twitch and Disney+",
        "nominees_day": "2026-11-17",
        "nominees_label": "November 17, 2026",
        "nominees_note": "The nominees were revealed on Tuesday, November 17, 2026.",
        "dates": (
            ("Nominees announced", "Tuesday, November 17, 2026"),
            ("Public vote", "Open now on thegameawards.com"),
            ("Ceremony", "Thursday, December 10, 2026, 7:30 p.m. Eastern"),
            ("Venue", "Peacock Theater, Los Angeles"),
            ("Ballots here lock", "December 10 at 4:30 p.m. Pacific"),
        ),
        "sections": (
            ("nominees", "Who is nominated", (
                "Grand Theft Auto VI has the most nominations with eight, including Game of the Year, Best Game "
                "Direction, Best Narrative and a Best Performance nomination for Manni L. Perez. Control Resonant "
                "and Resident Evil Requiem have six each, and Phantom Blade Zero has five.",
                "The six Game of the Year nominees are 007 First Light, Control Resonant, Grand Theft Auto VI, "
                "Phantom Blade Zero, Resident Evil Requiem and The Legend of Zelda: Ocarina of Time. Five of them "
                "are also up for Best Action/Adventure Game, where Pragmata takes Phantom Blade Zero's place.",
                "Nintendo is the most-nominated publisher with 12, by MobileSyrup's and Noisy Pixel's counts. Big "
                "Walk is nominated four times: Games for Impact, Best Independent Game, Best Family Game and Best "
                "Multiplayer Game.",
                "No Man's Sky won Best Ongoing Game last year and is nominated for it again, and for Best "
                "Community Support. The Witcher 3: Wild Hunt, an eleven-year-old game, is up for both as well.",
                "In esports, Chovy and Team Vitality won Best Esports Athlete and Best Esports Team last year and "
                "are both nominated again. Team Falcons are nominated twice in the team category, for "
                "Counter-Strike 2 and for Rocket League.",
            )),
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
                "The show streams free on YouTube and Twitch, and this year on Disney+ as well. GGRecon reports "
                "that Disney+ carries it live in North America and some other markets that Disney had not named. "
                "GamingBible's guide also lists X, TikTok Live, Facebook, Instagram Live, Kick and Steam.",
                "The opening act starts at 4:30 p.m. Pacific, which is 7:30 p.m. Eastern and 12:30 a.m. on Friday "
                "in the UK. That is the time the show's own FAQ gives, as VGChartz quotes it. Ballots here lock then.",
            )),
            ("categories", "What the ballot covers", (
                "The ballot has all 30 categories announced with the nominees, from Game of the Year to Best "
                "Esports Team. Best User Creation, for mods and player-made games, was not a category in 2025. "
                "Players' Voice is not on the ballot, because fans decide it entirely in their own voting rounds "
                "on thegameawards.com.",
                "Nominated games you already track are marked, and the rest can be added to your library from "
                "the ballot. That includes the five Most Anticipated nominees, none of which is out yet.",
                "The names here were checked against the lists MobileSyrup and Noisy Pixel published on "
                "November 17, then again on November 27 against Gematsu's and Game Informer's. Where they spelled a "
                "name differently, the game's own spelling is used.",
            )),
        ),
        "categories": _GAME_AWARDS_2026,
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
             Dated("Thursday, December 10, 2026, at the Peacock Theater in Los Angeles.",
                   ("2026-12-11", "They were on Thursday, December 10, 2026, at the Peacock Theater in Los Angeles."))),
            ("What time do The Game Awards start?",
             Dated("The opening act starts at 4:30 p.m. Pacific, 7:30 p.m. Eastern, which is 12:30 a.m. on Friday, "
                   "December 11 in the UK.",
                   ("2026-12-11", "The opening act started at 4:30 p.m. Pacific, 7:30 p.m. Eastern, which was "
                                  "12:30 a.m. on Friday, December 11 in the UK."))),
            ("Which game has the most nominations?",
             "Grand Theft Auto VI, with eight. Control Resonant and Resident Evil Requiem have six each."),
            ("What is nominated for Game of the Year?",
             "007 First Light, Control Resonant, Grand Theft Auto VI, Phantom Blade Zero, Resident Evil Requiem "
             "and The Legend of Zelda: Ocarina of Time."),
            ("Does this ballot count toward the real vote?",
             "No. The public vote is on thegameawards.com and counts for 10% of the result. The ballot here is a "
             "prediction: you pick who you think will win and get a score after the show."),
            ("Can I change my picks?",
             Dated("Yes, as often as you like until the show starts on December 10. After that the ballot locks.",
                   ("2026-12-11", "Not any more. Ballots locked when the show started on December 10."))),
            ("How is the ballot scored?",
             "One point for every category you called. Categories you skipped don't count against you."),
        ),
        "sources": (
            ("thegameawards.com", "https://thegameawards.com/"),
            ("The Game Awards 2025 (Wikipedia)", "https://en.wikipedia.org/wiki/The_Game_Awards_2025"),
            ("The Game Awards (Wikipedia)", "https://en.wikipedia.org/wiki/The_Game_Awards"),
            ("GamingBible: date and start time", "https://www.gamingbible.com/news/the-game-awards-2026-date-time-tickets-378124-20261007"),
            ("MobileSyrup: the nominees", "https://mobilesyrup.com/2026/11/17/the-game-awards-2026-nominees-full-list/"),
            ("Noisy Pixel: the nominees", "https://noisypixel.net/the-game-awards-2026-nominees-full-list/"),
            ("Push Square: the nominees", "https://www.pushsquare.com/news/2026/11/the-game-awards-2026-nominees-revealed-gta-6-up-for-8-awards"),
            ("GGRecon: the Disney+ stream", "https://www.ggrecon.com/articles/the-game-awards-2026-disney-plus/"),
        ),
    },
    "golden-globes-2027": {
        "name": "Golden Globes 2027",
        "short": "The Golden Globes",
        "ballot_name": "Golden Globes",  # "The Golden Globes ballot is open now."
        "nominations_name": "Golden Globe",  # "Golden Globe nominations on ..."
        "format": "Film and TV",
        "title": "Golden Globes 2027: date, nominations and your ballot",
        "search_title": "Golden Globes 2027: date, nominations, how to watch and a ballot",
        "description": ("The 84th Golden Globes are on January 10, 2027. When nominations come out, who votes, "
                        "what changed this year, where to watch and a free ballot to pick the winners."),
        "lead": ("The 84th Golden Globes are on Sunday, January 10, 2027 at the Beverly Hilton, live on CBS and "
                 "Paramount+. Nominations come out on Monday, December 7, and the ballot here opens once the list "
                 "is checked and loaded."),
        "published": "2026-11-12",
        "reviewed": "2026-11-23",
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
            ("voters", "Who the voters are now", (
                "For 80 years the Globes belonged to the Hollywood Foreign Press Association, a small group of "
                "foreign journalists based in Los Angeles, founded in 1943. In February 2021 a Los Angeles Times "
                "investigation reported that its 87 members included no Black journalists. NBC dropped the 2022 "
                "broadcast, and that year's ceremony went ahead in private, with the winners posted online. NBC "
                "aired the 2023 show on a one-year deal and drew 6.3 million viewers, the smallest audience the "
                "Globes have had on television.",
                "In June 2023 the association was wound up, and the Globes were bought by Dick Clark Productions and "
                "Eldridge, Todd Boehly's investment firm, which run them as a business. The voting body was rebuilt "
                "as the larger international group described above, and the show moved to CBS in 2024. Former "
                "association members were paid $75,000 a year to vote under the 2023 deal. That ended in February "
                "2025, so no Globes voter is paid now, which is also how the Oscars, Emmys and Grammys work. Every "
                "voter has to apply for accreditation again each year.",
            )),
            ("categories", "How the categories split", (
                "Only the biggest film awards are divided by genre. Best picture, lead actor and lead actress each "
                "come in a drama version and a musical or comedy version. Everything else is a single category: one "
                "director, one screenplay award where the Oscars have two, supporting actor and actress, score, song, "
                "animated film and non-English language film. The Cinematic and Box Office Achievement award, added "
                "in 2024, goes to one of the year's biggest hits.",
                "Studios choose which side a film enters, and the choice is not always the obvious one. The Martian "
                "won the musical or comedy prize in 2016, and Get Out was entered as a comedy two years later. Television "
                "has series awards for drama, for musical or comedy and for limited series, while the two supporting "
                "acting awards cover all of TV at once. Stand-up comedy got its own category in 2024 and podcasts in "
                "2026.",
            )),
            ("oscars", "What the Globes say about the Oscars", (
                "The Globes come early. Nominations are out on December 7, five weeks before Oscar nominations voting "
                "opens, and the ceremony is over the day before that voting starts. That makes them the first big "
                "list of the film season, but the voters are journalists rather than people who make films, and the "
                "split categories hand two films a best picture prize every year.",
                "The last three years show how that plays out. In 2024 Oppenheimer won the drama prize and then Best "
                "Picture at the Oscars. In 2025 the Globes went to The Brutalist and Emilia Pérez, and the Oscar went "
                "to Anora, which won neither. Last January Hamnet won drama and One Battle After Another won musical "
                "or comedy, and One Battle After Another went on to take Best Picture.",
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
                ("Motion Picture, Drama", "Hamnet", "",
                 {"kind": "movie", "title": "Hamnet", "year": 2025, "creator": "Chloé Zhao"}),
                ("Motion Picture, Musical or Comedy", "One Battle After Another", "",
                 {"kind": "movie", "title": "One Battle After Another", "year": 2025, "creator": "Paul Thomas Anderson"}),
                ("Director", "Paul Thomas Anderson", "One Battle After Another",
                 {"kind": "movie", "title": "One Battle After Another", "year": 2025, "creator": "Paul Thomas Anderson"}),
                ("Actress, Drama", "Jessie Buckley", "Hamnet",
                 {"kind": "movie", "title": "Hamnet", "year": 2025, "creator": "Chloé Zhao"}),
                ("Actor, Drama", "Wagner Moura", "The Secret Agent",
                 {"kind": "movie", "title": "The Secret Agent", "year": 2025, "creator": "Kleber Mendonça Filho"}),
                ("Actress, Musical or Comedy", "Rose Byrne", "If I Had Legs I'd Kick You",
                 {"kind": "movie", "title": "If I Had Legs I'd Kick You", "year": 2025, "creator": "Mary Bronstein"}),
                ("Actor, Musical or Comedy", "Timothée Chalamet", "Marty Supreme",
                 {"kind": "movie", "title": "Marty Supreme", "year": 2025, "creator": "Josh Safdie"}),
                ("Screenplay", "Paul Thomas Anderson", "One Battle After Another",
                 {"kind": "movie", "title": "One Battle After Another", "year": 2025, "creator": "Paul Thomas Anderson"}),
                ("Animated Film", "KPop Demon Hunters", "",
                 {"kind": "movie", "title": "KPop Demon Hunters", "year": 2025}),
                ("Non-English Language Film", "The Secret Agent", "Brazil",
                 {"kind": "movie", "title": "The Secret Agent", "year": 2025, "creator": "Kleber Mendonça Filho"}),
                ("Cinematic and Box Office Achievement", "Sinners", "",
                 {"kind": "movie", "title": "Sinners", "year": 2025, "creator": "Ryan Coogler"}),
                ("TV Series, Drama", "The Pitt", "",
                 {"kind": "tv", "title": "The Pitt", "year": 2025}),
                ("TV Series, Musical or Comedy", "The Studio", "",
                 {"kind": "tv", "title": "The Studio", "year": 2025}),
                ("Limited Series or TV Film", "Adolescence", "",
                 {"kind": "tv", "title": "Adolescence", "year": 2025}),
                ("Stand-Up Comedy", "Ricky Gervais", "Mortality", None),
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
            ("TV Guide: the 2026 winners", "https://www.tvguide.com/news/the-2026-golden-globes-complete-winners-list"),
            ("Hollywood Foreign Press Association (Wikipedia)", "https://en.wikipedia.org/wiki/HFPA"),
            ("AwardsWatch: Dick Clark Productions and Eldridge take over", "https://awardswatch.com/dick-clark-productions-and-eldridge-take-over-golden-globes-shutters-the-hollywood-foreign-press-association-hfpa/"),
            ("TheWrap: voter salaries end", "https://www.thewrap.com/golden-globes-ends-voter-salaries-hfpa-members/"),
        ),
    },
    "grammys-2027": {
        "name": "Grammys 2027",
        "short": "The Grammys",
        "ballot_name": "Grammys",  # "The Grammys ballot is open now."
        "nominations_name": "Grammy",  # "Grammy nominations on ..."
        "format": "Music",
        "title": "Grammys 2027: date, nominations and your ballot",
        "search_title": "Grammys 2027: nominees, date, new categories and a ballot",
        "description": ("The 69th Grammy Awards are on February 7, 2027, on ABC for the first time since 1972. The "
                        "nominees in 13 categories, who leads, last year's winners and a free ballot."),
        "lead": ("The 69th Grammy Awards are on Sunday, February 7, 2027 at Crypto.com Arena in Los Angeles. "
                 "Nominations came out on Monday, November 16, with RAYE in front on 11. The ballot below is open: "
                 "pick a winner in each of 13 categories and see your score after the show."),
        "published": "2026-11-12",
        "reviewed": "2026-11-17",
        "ceremony_day": "2027-02-07",
        "ceremony_at": "2027-02-08T00:00:00",
        "lock_label": "Sunday, February 7 at 4 p.m. Pacific",
        "watch": "ABC, streaming on Disney+ and Hulu",
        "nominees_day": "2026-11-16",
        "nominees_label": "November 16, 2026",
        "nominees_note": "Nominations were announced on Monday, November 16, 2026.",
        "dates": (
            ("Eligible releases", "August 31, 2025 to August 28, 2026"),
            ("Nominations announced", "Monday, November 16, 2026"),
            ("Final-round voting", "December 10, 2026 to January 7, 2027"),
            ("Ceremony", "Sunday, February 7, 2027, 7 p.m. Eastern"),
            ("Venue", "Crypto.com Arena, Los Angeles"),
            ("Ballots here lock", "February 7 at 4 p.m. Pacific"),
        ),
        "sections": (
            ("nominees", "Who is nominated", (
                "RAYE has the most nominations this year with 11, and Audacy counts nine for ROSALÍA, the next "
                "most. Both are up for Album and Record of the Year: RAYE with THIS MUSIC MAY CONTAIN HOPE. and "
                "WHERE IS MY HUSBAND!, ROSALÍA with LUX (Complete Works) and Berghain, which she recorded with "
                "Björk and Yves Tumor.",
                "Ella Langley is nominated in all four general categories: Dandelion for Album of the Year, "
                "Choosin' Texas for Record and Song of the Year, and Best New Artist. Olivia Dean won Best New "
                "Artist in February and is back with nominations for Album, Record and Song of the Year.",
                "Four other Best New Artist nominees also have an album in a genre category: Angine de Poitrine in "
                "rock, Geese in alternative, Slayyyter in dance/electronic and Don Toliver in rap.",
                "Taylor Swift's The Life of a Showgirl is up for Album of the Year and The Fate of Ophelia for "
                "Record of the Year. Her Song of the Year nomination is for a different song, I Knew It, I Knew "
                "You, written with Jack Antonoff for Toy Story 5.",
                "The ballot also has the award for video game scores, because its nominees are games you can "
                "track here: 007: First Light, Ghost of Yōtei, Marvel's Wolverine, Star Wars: Zero Company and the "
                "Avatar: Frontiers of Pandora expansion From the Ashes.",
            )),
            ("chosen", "How the winners are chosen", (
                "Voting members of the Recording Academy pick the winners. The first round, which decided the "
                "nominees, ran from October 12 to 22. The final round runs from December 10, 2026 to January 7, 2027.",
                "Recordings released between August 31, 2025 and August 28, 2026 are eligible, by Grammy.com's "
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
                "A hundred categories is too many for one ballot. The one here covers 13: the four general awards "
                "(Album, Record and Song of the Year, and Best New Artist), eight genre album categories and the "
                "video game score award. Titles and names are written the way the Recording Academy lists them, "
                "capitals included.",
            )),
        ),
        "categories": _GRAMMYS_2027,
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
            ("Who has the most Grammy nominations for 2027?",
             "RAYE, with 11. Nominations were announced on Monday, November 16, 2026."),
            ("Who is nominated for Album of the Year?",
             "Phoebe Bridgers, Olivia Dean, Ella Langley, Bruno Mars, RAYE, Olivia Rodrigo, ROSALÍA and Taylor Swift."),
            ("Which releases are eligible?",
             "Recordings released between August 31, 2025 and August 28, 2026."),
            ("Can I change my picks?",
             "Yes, until the show starts on February 7. After that the ballot locks."),
        ),
        "sources": (
            ("Grammy.com: how to watch the nominations", "https://www.grammy.com/news/how-to-watch-2027-grammys-nominations/"),
            ("Grammy.com: 69th Grammy Awards nominees", "https://www.grammy.com/awards/69th-annual-grammy-awards-2027/"),
            ("Grammy.com: video game score nominees", "https://www.grammy.com/awards/categories/best-score-soundtrack-for-video-games-and-other-interactive-media/"),
            ("ABC News: the full list of nominees", "https://abcnews.com/GMA/Culture/grammy-nominations-2027-full-list/story?id=138113372"),
            ("Audacy: the nominees", "https://www.audacy.com/national/music/grammy-awards-2027-nominees"),
            ("69th Annual Grammy Awards (Wikipedia)", "https://en.wikipedia.org/wiki/69th_Annual_Grammy_Awards"),
            ("68th Annual Grammy Awards (Wikipedia)", "https://en.wikipedia.org/wiki/68th_Annual_Grammy_Awards"),
        ),
    },
    "oscars-2027": {
        "name": "Oscars 2027",
        "short": "The Oscars",
        "ballot_name": "Oscars",  # "The Oscars ballot is open now."
        "nominations_name": "Oscar",  # "Oscar nominations on ..."
        "format": "Film",
        "title": "Oscars 2027: date, nominations and your ballot",
        "search_title": "Oscars 2027: date, nominations, key dates and a ballot",
        "description": ("The 99th Academy Awards are on March 14, 2027. Shortlist, nomination and voting dates, what "
                        "changed in the rules, last year's winners and a free ballot to pick this year's."),
        "lead": ("The 99th Academy Awards are on Sunday, March 14, 2027 at the Dolby Theatre in Hollywood, live on "
                 "ABC at 7 p.m. Eastern. Nominations are announced on Thursday, January 21, and the ballot here "
                 "opens once the list is checked and loaded."),
        "published": "2026-11-12",
        "reviewed": "2026-11-23",
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
            ("eligible", "Which films can compete", (
                "A film has to run longer than 40 minutes and open in a cinema between January 1 and December 31, "
                "2026. The run that qualifies it is seven days in a row at one cinema, with at least three screenings "
                "a day and one of them starting between 6 and 10 p.m., in one of six US areas: Los Angeles County, "
                "New York City, the San Francisco Bay Area, Chicago, Dallas-Fort Worth or Atlanta. A premiere on a "
                "streaming service doesn't count on its own.",
                "Best Picture asks for more. Within 45 days of that first run, a film also has to play for at least "
                "seven days in nine more of the 50 biggest US markets, and it has to meet two of the Academy's four "
                "inclusion standards, which look at who is on screen, who made the film, paid training places for "
                "newcomers, and who it was marketed to. That is why films made for streaming services still open in "
                "a handful of cinemas first.",
            )),
            ("counting", "How the votes are counted", (
                "Nominations come from the Academy's branches: actors nominate actors, directors nominate directors, "
                "cinematographers nominate cinematographers, and so on. Every voting member can nominate for Best "
                "Picture. In the final round every member can vote in every category, with one condition that began "
                "last year: you have to have watched all the nominees in a category to vote in it. The Academy checks "
                "viewing on its own online screening room, and members declare any film they saw somewhere else, such "
                "as at a festival.",
                "Most categories go to the nominee with the most votes. Best Picture works differently. It has had "
                "exactly ten nominees every year since the 2022 ceremony, and voters rank them. If no film is first on "
                "more than half the ballots, the film with the fewest first places drops out and those ballots move "
                "to their next choice, and that repeats until one film is past half. A film that most voters rank "
                "second or third can beat one that splits them, which is worth keeping in mind when you pick that "
                "category.",
            )),
            ("shortlists", "What the December shortlists tell you", (
                "In a shortlisted category, the nominees can only come from the list. Last year there were twelve "
                "lists, published on December 16, 2025: animated short, casting, cinematography, documentary feature, "
                "documentary short, international feature, live action short, makeup and hairstyling, original score, "
                "original song, sound and visual effects. Most ran to 10 or 15 titles, and the score list had 20.",
                "Two of them work differently this year. The cinematography list is now always 20 films, where it "
                "used to be anything from 10 to 20. And in visual effects, members can only vote in the final round "
                "once they have watched each finalist's three-minute before-and-after reel from the bake-off, the "
                "evening when shortlisted teams show their work to the branch.",
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
                "Cassandra Kulukundis for One Battle After Another, and it can now go to as many as three people on "
                "a film instead of two.",
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
            ("Academy: rules approved for the 99th Oscars", "https://press.oscars.org/news/awards-rules-and-campaign-promotional-regulations-approved-99th-oscarsr"),
            ("Academy: Best Picture rules", "https://www.oscars.org/sites/oscars/files/2025-04/98th_aa_best_picture.pdf"),
            ("Academy: last year's shortlists", "https://press.oscars.org/news/98th-oscarsr-shortlists-12-award-categories-announced"),
            ("NPR: voters must watch the nominees", "https://www.npr.org/2025/04/22/nx-s1-5372650/oscar-voting-changes"),
        ),
    },
}

# Calendar order: by ceremony.
ORDER = ("the-game-awards-2026", "golden-globes-2027", "grammys-2027", "oscars-2027")
