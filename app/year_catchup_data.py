"""The year's big releases, for "Fill in your year" (see app/year_catchup.py). One list per year.

A member with an empty or thin library has nothing for "Fill in your year" to ask
about, so their Year in Review stays blank. This list is the shortcut: the titles
most people watched, played, read or heard that year. Tapping one and picking the
month saves it to the library, finished in that month, and the recap counts it.

The list leans on how many people got to a title, not on how good it is (the Best
of the year guides do that). Sources, checked 2026-11-27: worldwide box office for
2026 releases (The Numbers) and the US weekend number ones (Wikipedia); Nielsen's
streaming top 10 for the first half of 2026 (via TVLine); Circana's US sales charts
through September 2026; the UK Official Charts and US album sales through mid-July
2026; and the Best of 2026 guides for books, manga, podcasts and audiobooks, where
sales charts say little.

Entry fields:
    kind     movie | tv | anime | game | book | album | manga | podcast | audiobook
    title    the title as it goes into the library
    year     the year the library row gets (a show's first season, not this one)
    creator  director, author, artist or host when sure, else None
    out      "YYYY-MM": the month it came out, or the month this season started. Month
             buttons start here, and the title isn't shown before that month.
    season   for a returning show, which season came out that year
    feature  lower comes first in the email and the grid; the email shows the six
             lowest the member hasn't answered and doesn't already have
"""

EDITIONS = {
    2026: {
        "reviewed": "2026-11-27",
        "entries": [
            # Movies: the year's biggest at the box office, plus the November number ones.
            {"kind": "movie", "title": "Spider-Man: Brand New Day", "year": 2026, "creator": "Destin Daniel Cretton",
             "out": "2026-07", "feature": 1},
            {"kind": "movie", "title": "The Odyssey", "year": 2026, "creator": "Christopher Nolan",
             "out": "2026-07", "feature": 7},
            {"kind": "movie", "title": "Toy Story 5", "year": 2026, "creator": None, "out": "2026-06", "feature": 4},
            {"kind": "movie", "title": "Michael", "year": 2026, "creator": "Antoine Fuqua", "out": "2026-04",
             "feature": 10},
            {"kind": "movie", "title": "The Super Mario Galaxy Movie", "year": 2026,
             "creator": "Aaron Horvath and Michael Jelenic", "out": "2026-04", "feature": 12},
            {"kind": "movie", "title": "The Devil Wears Prada 2", "year": 2026, "creator": "David Frankel",
             "out": "2026-05", "feature": 16},
            {"kind": "movie", "title": "Project Hail Mary", "year": 2026, "creator": "Phil Lord and Christopher Miller",
             "out": "2026-03", "feature": 13},
            {"kind": "movie", "title": "Minions & Monsters", "year": 2026, "creator": None, "out": "2026-07",
             "feature": 24},
            {"kind": "movie", "title": "Hoppers", "year": 2026, "creator": "Daniel Chong", "out": "2026-03",
             "feature": 26},
            {"kind": "movie", "title": "The Hunger Games: Sunrise on the Reaping", "year": 2026,
             "creator": "Francis Lawrence", "out": "2026-11", "feature": 9},
            {"kind": "movie", "title": "Wuthering Heights", "year": 2026, "creator": "Emerald Fennell",
             "out": "2026-02", "feature": 28},
            # TV: the most-streamed new seasons and series of 2026.
            {"kind": "tv", "title": "The Pitt", "year": 2025, "creator": None, "out": "2026-01", "season": 2,
             "feature": 2},
            {"kind": "tv", "title": "Bridgerton", "year": 2020, "creator": None, "out": "2026-01", "season": 4,
             "feature": 5},
            {"kind": "tv", "title": "A Knight of the Seven Kingdoms", "year": 2026, "creator": None, "out": "2026-01",
             "feature": 11},
            {"kind": "tv", "title": "The Boys", "year": 2019, "creator": None, "out": "2026-04", "season": 5,
             "feature": 8},
            {"kind": "tv", "title": "One Piece", "year": 2023, "creator": None, "out": "2026-03", "season": 2,
             "feature": 17},
            {"kind": "tv", "title": "Wonder Man", "year": 2026, "creator": None, "out": "2026-01", "feature": 21},
            {"kind": "tv", "title": "His & Hers", "year": 2026, "creator": None, "out": "2026-01", "feature": 23},
            {"kind": "tv", "title": "Lanterns", "year": 2026, "creator": None, "out": "2026-08", "feature": 25},
            # Anime: the seasons people waited for.
            {"kind": "anime", "title": "Frieren: Beyond Journey's End Season 2", "year": 2026, "creator": None,
             "out": "2026-01", "feature": 14},
            {"kind": "anime", "title": "Jujutsu Kaisen Season 3", "year": 2026, "creator": None, "out": "2026-01",
             "feature": 18},
            {"kind": "anime", "title": "Steel Ball Run: JoJo's Bizarre Adventure", "year": 2026, "creator": None,
             "out": "2026-03", "feature": 27},
            {"kind": "anime", "title": "Witch Hat Atelier", "year": 2026, "creator": None, "out": "2026-04",
             "feature": 33},
            # Games: Circana's best sellers of 2026, plus GTA VI in November.
            {"kind": "game", "title": "Grand Theft Auto VI", "year": 2026, "creator": None, "out": "2026-11",
             "feature": 3},
            {"kind": "game", "title": "Resident Evil Requiem", "year": 2026, "creator": None, "out": "2026-02",
             "feature": 6},
            {"kind": "game", "title": "Pokémon Pokopia", "year": 2026, "creator": None, "out": "2026-03",
             "feature": 15},
            {"kind": "game", "title": "007 First Light", "year": 2026, "creator": None, "out": "2026-05",
             "feature": 19},
            {"kind": "game", "title": "Crimson Desert", "year": 2026, "creator": None, "out": "2026-03",
             "feature": 20},
            {"kind": "game", "title": "Tomodachi Life: Living the Dream", "year": 2026, "creator": None,
             "out": "2026-04", "feature": 22},
            {"kind": "game", "title": "Forza Horizon 6", "year": 2026, "creator": None, "out": "2026-05",
             "feature": 29},
            {"kind": "game", "title": "Marvel's Wolverine", "year": 2026, "creator": None, "out": "2026-09",
             "feature": 30},
            {"kind": "game", "title": "Pragmata", "year": 2026, "creator": None, "out": "2026-04", "feature": 36},
            # Albums: the year's big ones in the US and UK charts.
            {"kind": "album", "title": "you seem pretty sad for a girl so in love", "year": 2026,
             "creator": "Olivia Rodrigo", "out": "2026-06", "feature": 31},
            {"kind": "album", "title": "Kiss All the Time. Disco, Occasionally.", "year": 2026,
             "creator": "Harry Styles", "out": "2026-03", "feature": 32},
            {"kind": "album", "title": "Arirang", "year": 2026, "creator": "BTS", "out": "2026-03", "feature": 34},
            {"kind": "album", "title": "Nothing's About to Happen to Me", "year": 2026, "creator": "Mitski",
             "out": "2026-02", "feature": 40},
            {"kind": "album", "title": "Middle of Nowhere", "year": 2026, "creator": "Kacey Musgraves",
             "out": "2026-05", "feature": 41},
            # Books, manga, podcasts and audiobooks: from the Best of 2026 guides.
            {"kind": "book", "title": "Kin", "year": 2026, "creator": "Tayari Jones", "out": "2026-02", "feature": 35},
            {"kind": "book", "title": "London Falling", "year": 2026, "creator": "Patrick Radden Keefe",
             "out": "2026-04", "feature": 37},
            {"kind": "book", "title": "Platform Decay", "year": 2026, "creator": "Martha Wells", "out": "2026-05",
             "feature": 42},
            {"kind": "manga", "title": "Ichi the Witch", "year": 2024, "creator": "Osamu Nishi and Shiro Usazaki",
             "out": "2026-02", "feature": 38},
            {"kind": "manga", "title": "Taika's Reason", "year": 2025, "creator": "Paru Itagaki", "out": "2026-07",
             "feature": 44},
            {"kind": "podcast", "title": "Serial: The Idiot", "year": 2026, "creator": "M. Gessen", "out": "2026-03",
             "feature": 39},
            {"kind": "podcast", "title": "A History of the United States in 100 Objects", "year": 2026,
             "creator": "Roman Mars", "out": "2026-05", "feature": 45},
            {"kind": "audiobook", "title": "Vigil", "year": 2026, "creator": "George Saunders", "out": "2026-01",
             "feature": 43},
            {"kind": "audiobook", "title": "Exit Party", "year": 2026, "creator": "Emily St. John Mandel",
             "out": "2026-09", "feature": 46},
        ],
    },
}
