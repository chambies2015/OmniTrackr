"""Book series for the "how long does it take" guides (/binge-calculator/<slug>).

Reading time starts from word counts, because page counts change with every
edition. ``audio`` is the length in minutes of the unabridged audiobook named in
the guide's ``audio`` note, as listed by Audible in November 2026. ``approx``
marks a word count we estimated ourselves (the guide says how).
"""
from .dated_text import Dated

REVIEWED = "2026-11-10"
UPDATED = "2026-11-20"  # guides that gained a third section
WIDENED = "2026-11-27"  # guides that gained a fourth section on November 27


def _book(name, year, words, audio, creator, **extra):
    return {"name": name, "year": year, "words": words, "audio": audio, "creator": creator, **extra}


ROWLING, TOLKIEN, MARTIN, JORDAN, HERBERT, SANDERSON = (
    "J.K. Rowling", "J.R.R. Tolkien", "George R.R. Martin", "Robert Jordan", "Frank Herbert", "Brandon Sanderson")

GUIDES = {
    "harry-potter": {
        "name": "Harry Potter", "kind": "book", "reviewed": UPDATED, "in_order": "harry-potter",
        "heading": "How long does it take to read Harry Potter?",
        "summary": "The seven Harry Potter books are about 1.08 million words: roughly 90 hours to read or 116 to hear. Book-by-book times and a planner.",
        "audio": {"narrator": "Jim Dale", "note": "Audiobook lengths are for the Jim Dale recordings."},
        "see_also": ["harry-potter-films", "the-lord-of-the-rings", "the-stormlight-archive"],
        "lead": [
            "The seven Harry Potter novels come to about 1,084,000 words. At an average reading speed of 200 words a "
            "minute that is roughly 90 hours. The audiobooks read by Jim Dale run a little over 116 hours at normal speed.",
            "The books are far from equal. The first is under 77,000 words and takes an average reader about six and a "
            "half hours. Order of the Phoenix, the longest, is 257,000 words, almost as much as the first three "
            "books together. Three quarters of the reading is in books four to seven.",
        ],
        "parts": [
            _book("Philosopher's Stone", 1997, 76944, 498, ROWLING, title="Harry Potter and the Philosopher's Stone",
                  aka=["Harry Potter and the Sorcerer's Stone", "Sorcerer's Stone"],
                  note="Published in the US as Sorcerer's Stone."),
            _book("Chamber of Secrets", 1998, 85141, 542, ROWLING, title="Harry Potter and the Chamber of Secrets"),
            _book("Prisoner of Azkaban", 1999, 107253, 709, ROWLING, title="Harry Potter and the Prisoner of Azkaban"),
            _book("Goblet of Fire", 2000, 190637, 1236, ROWLING, title="Harry Potter and the Goblet of Fire"),
            _book("Order of the Phoenix", 2003, 257045, 1588, ROWLING, title="Harry Potter and the Order of the Phoenix",
                  note="The longest book."),
            _book("Half-Blood Prince", 2005, 168923, 1112, ROWLING, title="Harry Potter and the Half-Blood Prince"),
            _book("Deathly Hallows", 2007, 198227, 1296, ROWLING, title="Harry Potter and the Deathly Hallows"),
        ],
        "sections": [
            ("pace", "A pace that works", [
                "Half an hour a day gets an average reader through all seven books in about six months. An hour a day "
                "takes three. The first three books go quickly at either pace, about three weeks in total at an hour a "
                "day, which is a good way to find out whether you want to commit to the long ones.",
                "Reading aloud to a child is much slower, close to audiobook speed. Allow about 116 hours, which at "
                "one chapter a night (there are 199 chapters) is most of seven months.",
            ]),
            ("listening", "Reading or listening", [
                "Narrators speak more slowly than most people read, so the audiobooks take about 26 hours longer than "
                "reading at the default speed. At 1.25x the two are nearly level.",
                "The lengths here are for Jim Dale's recordings. Stephen Fry's are a little longer book for book, "
                "about 29 hours for Order of the Phoenix against Dale's 26 and a half. The full-cast editions that "
                "came out between late 2025 and mid 2026 are close to Dale's lengths.",
            ]),
            ("editions", "British and American editions", [
                "The first book is Harry Potter and the Philosopher's Stone in Britain and the Sorcerer's Stone in the US, "
                "and the American editions change some words and spellings. The story and the length are the same.",
                "Page counts are another matter. The American hardcover of the first book is 309 pages and the first British "
                "edition is 223, mostly because of the type size. That gap is why this page works from word counts. Whichever "
                "copy you have, it takes the same time to read.",
            ]),
        ],
        "faq": [
            ("How many words are in the Harry Potter series?",
             "About 1,084,000 across the seven novels, from 76,944 in the first book to 257,045 in Order of the Phoenix."),
            ("How long does it take to read the first Harry Potter book?",
             "About six and a half hours at 200 words a minute. The Jim Dale audiobook is 8 hours 18 minutes."),
            ("Is it faster to watch the Harry Potter films?",
             "Much faster. The eight films run about 19 hours 38 minutes, against roughly 90 hours for the books."),
        ],
    },
    "the-lord-of-the-rings": {
        "name": "The Lord of the Rings", "kind": "book", "reviewed": WIDENED, "in_order": "lord-of-the-rings",
        "heading": "How long does it take to read The Lord of the Rings?",
        "summary": "The Lord of the Rings is about 481,000 words: roughly 40 hours to read, or 54 as an audiobook. Volume lengths, The Hobbit, and a planner.",
        "audio": {"narrator": "Rob Inglis", "note": "Audiobook lengths are for the Rob Inglis recordings."},
        "see_also": ["middle-earth-films", "a-song-of-ice-and-fire", "the-wheel-of-time"],
        "lead": [
            "The Lord of the Rings is about 481,000 words across its three volumes, not counting the appendices. At "
            "200 words a minute that is close to 40 hours of reading. The unabridged audiobook read by Rob Inglis "
            "runs 54 hours.",
            "It is one novel, published in three volumes in 1954 and 1955 because of the cost of paper. The Fellowship "
            "of the Ring is the longest of the three, and The Hobbit, which comes first in the story, is a separate "
            "and much shorter book. It is left out of the total below and you can tick it to add it.",
        ],
        "parts": [
            _book("The Hobbit", 1937, 95356, 664, TOLKIEN, optional=True, note="The prequel, written for children. A quick read."),
            _book("The Fellowship of the Ring", 1954, 187790, 1147, TOLKIEN),
            _book("The Two Towers", 1954, 156198, 1000, TOLKIEN),
            _book("The Return of the King", 1955, 137115, 1099, TOLKIEN, note="The story only. The appendices add more than 100 pages."),
        ],
        "sections": [
            ("pace", "A pace that works", [
                "Tolkien's prose is slower going than a modern fantasy novel. There are songs, long descriptions of "
                "landscape and several languages. Many readers find 30 pages an hour more honest than 40, which puts "
                "the three volumes at about 53 hours. Use the reading-speed setting in the planner to match yourself.",
                "At 40 hours, an hour a day finishes it in under six weeks. The book is divided into six parts of "
                "roughly equal size, two per volume, and one part a week is a comfortable schedule that reaches the "
                "end in a month and a half.",
            ]),
            ("listening", "Reading or listening", [
                "There are two unabridged audiobooks. Rob Inglis's recording runs 54 hours and is the one counted "
                "here. Andy Serkis's 2021 recording is slower and more acted, at about 65 hours. Either one at 1.25x "
                "is still a long listen: 43 and 52 hours.",
                "The appendices at the back of The Return of the King are reference material: family trees, "
                "calendars and a timeline. One of them, the tale of Aragorn and Arwen, is worth reading as an "
                "epilogue. The Silmarillion is a different kind of book and is not counted.",
            ]),
            ("structure", "How the story is split", [
                "The Lord of the Rings is divided into six books, two to each volume. From the second volume on, Tolkien "
                "tells the two main storylines one after the other instead of cutting between them: Book III follows the rest "
                "of the Fellowship, and Book IV goes back in time to follow Frodo and Sam on their own.",
                "So there is a long stretch without Frodo, then nearly as long with little else. Plenty of readers slow down "
                "in Book IV. Knowing the shape helps, and so does treating each book as a unit: six books at one a week is "
                "the six-week plan above.",
            ]),
            ("after", "After the last page", [
                "The Silmarillion is the history of everything before The Hobbit, from the making of the world to the "
                "end of the First Age. Christopher Tolkien edited it from his father's papers and published it in 1977, "
                "four years after Tolkien died, and it reads more like a book of myths than a novel. If the opening "
                "chapters lose you, skip to Of Beren and Lúthien, the story Aragorn sings part of on Weathertop, and go "
                "back once you are hooked.",
                "Three of its stories were later published at full length as books of their own: The Children of Húrin "
                "in 2007, Beren and Lúthien in 2017 and The Fall of Gondolin in 2018. The Children of Húrin reads most like "
                "a novel and is the one to start with. None of them are counted in the totals above.",
            ]),
        ],
        "faq": [
            ("How many words is The Lord of the Rings?",
             "About 481,000 without the appendices: 187,790 in The Fellowship of the Ring, 156,198 in The Two Towers "
             "and 137,115 in The Return of the King."),
            ("Should I read The Hobbit first?",
             "It helps and it is short, about eight hours. The Lord of the Rings explains what it needs to, so you can also start there."),
            ("Is the book longer than the films?",
             "Yes. The extended editions of the three films run about 12 hours, and reading the book takes around 40."),
        ],
    },
    "a-song-of-ice-and-fire": {
        "name": "A Song of Ice and Fire", "kind": "book", "reviewed": WIDENED, "in_order": "game-of-thrones",
        "heading": "How long does it take to read A Song of Ice and Fire?",
        "summary": "The five published A Song of Ice and Fire novels are about 1.77 million words: roughly 148 hours to read, or 201 hours on audio.",
        "audio": {"narrator": "Roy Dotrice", "note": "Audiobook lengths are for the Roy Dotrice recordings."},
        "see_also": ["game-of-thrones", "the-wheel-of-time", "the-stormlight-archive"],
        "lead": [
            "The five novels of A Song of Ice and Fire published so far come to about 1.77 million words. At 200 "
            "words a minute that is roughly 148 hours of reading. The audiobooks, read by Roy Dotrice, run a little "
            "over 201 hours.",
            "Two of the five, A Storm of Swords and A Dance with Dragons, are more than 420,000 words each and take "
            "about 35 hours apiece. Two further novels are planned and neither had been published when this page was "
            "last checked, so finishing book five means stopping mid-story.",
        ],
        "parts": [
            _book("A Game of Thrones", 1996, 298000, 2026, MARTIN),
            _book("A Clash of Kings", 1998, 326000, 2232, MARTIN),
            _book("A Storm of Swords", 2000, 424000, 2854, MARTIN, note="Split into two volumes in some paperback editions."),
            _book("A Feast for Crows", 2005, 300000, 2031, MARTIN),
            _book("A Dance with Dragons", 2011, 422000, 2935, MARTIN, note="Also sold as two paperbacks in some countries."),
        ],
        "sections": [
            ("pace", "A pace that works", [
                "An hour a day takes about five months. The chapters help: each is told from one character's point of "
                "view and runs 10 to 20 pages, so a chapter or two a night is a natural unit. There are 344 chapters "
                "in the five books, which at two a night is a little under six months.",
                "The first three books read fastest, because the plot moves quickly and the cast is still gathered in "
                "a few places. Most readers slow down in books four and five.",
            ]),
            ("feast-and-dance", "Books four and five overlap", [
                "A Feast for Crows and A Dance with Dragons cover the same stretch of time. One follows the characters "
                "in the south, the other those in the north and across the sea. Some readers combine them with a "
                "chapter-by-chapter reading order from fan sites. That takes the same total time, about 60 hours, "
                "and is best saved for a second read.",
                "Word counts for this series vary by a few percent between sources, so the figures here are rounded to "
                "the nearest thousand. The Dunk and Egg novellas and Fire & Blood are separate books and are not counted.",
            ]),
            ("with-the-show", "Reading alongside the show", [
                "If you want to alternate, the early seasons line up with the books. Season 1 adapts A Game of Thrones and "
                "season 2 A Clash of Kings. A Storm of Swords is long enough that the show split it across seasons 3 and 4. "
                "Season 5 draws on books four and five together.",
                "Season 6 goes past the books entirely. If you read first and watch second, finish A Dance with Dragons "
                "before season 6, and treat seasons 6 to 8 as the only ending there is for now.",
            ]),
            ("meanwhile", "While you wait for The Winds of Winter", [
                "The sixth book, The Winds of Winter, still has no publication date, and George R.R. Martin's updates on "
                "his blog have not given one, so plan on these five as the whole series for now. A seventh, A Dream of "
                "Spring, is meant to end it.",
                "The three Dunk and Egg novellas, The Hedge Knight, The Sworn Sword and The Mystery Knight, are set about "
                "ninety years before A Game of Thrones and were collected in 2015 as A Knight of the Seven Kingdoms. They "
                "are a few evenings' reading, and HBO's series of the same name, whose six-episode first season began in "
                "January 2026, adapts The Hedge Knight. Fire & Blood, the history of the Targaryen kings that House of "
                "the Dragon is based on, is written as a chronicle rather than a novel, which suits some readers more "
                "than others.",
            ]),
        ],
        "faq": [
            ("How many words are in A Song of Ice and Fire?",
             "About 1.77 million in the five published novels, ranging from about 298,000 for A Game of Thrones to 424,000 for A Storm of Swords."),
            ("How long is the A Game of Thrones audiobook?",
             "33 hours 46 minutes in Roy Dotrice's recording. All five audiobooks together are about 201 hours."),
            ("Is it quicker to watch Game of Thrones?",
             "Yes, about twice as quick. The series is around 70 hours and reaches an ending, which the books have not."),
        ],
    },
    "the-wheel-of-time": {
        "name": "The Wheel of Time", "kind": "book", "reviewed": UPDATED,
        "heading": "How long does it take to read The Wheel of Time?",
        "summary": "The Wheel of Time is fourteen novels and about 4.3 million words: roughly 357 hours to read or 450 on audio. Book-by-book times.",
        "audio": {"narrator": "Michael Kramer and Kate Reading", "note": "Audiobook lengths are for the Michael Kramer and Kate Reading recordings."},
        "see_also": ["the-stormlight-archive", "a-song-of-ice-and-fire", "the-lord-of-the-rings"],
        "lead": [
            "The Wheel of Time is fourteen novels and about 4.29 million words. At 200 words a minute that is "
            "roughly 357 hours of reading, the longest finished series in this section by a wide margin. The "
            "audiobooks read by Michael Kramer and Kate Reading run 450 hours.",
            "For scale, that is almost four times the length of Harry Potter. Robert Jordan wrote the first eleven "
            "books and died in 2007. Brandon Sanderson completed the last three from Jordan's notes, and the final "
            "volume came out in 2013, so unlike several other long fantasies this one does end.",
        ],
        "parts": [
            _book("New Spring", 2004, 121815, 758, JORDAN, optional=True, note="A prequel novel. Usually read after book five or later."),
            _book("The Eye of the World", 1990, 305902, 1797, JORDAN),
            _book("The Great Hunt", 1990, 267078, 1594, JORDAN),
            _book("The Dragon Reborn", 1991, 251392, 1488, JORDAN),
            _book("The Shadow Rising", 1992, 393823, 2473, JORDAN, note="The longest book by word count."),
            _book("The Fires of Heaven", 1993, 354109, 2187, JORDAN),
            _book("Lord of Chaos", 1994, 389823, 2492, JORDAN),
            _book("A Crown of Swords", 1996, 295028, 1824, JORDAN),
            _book("The Path of Daggers", 1998, 226687, 1405, JORDAN, note="The shortest of the main fourteen."),
            _book("Winter's Heart", 2000, 238789, 1452, JORDAN),
            _book("Crossroads of Twilight", 2003, 271632, 1564, JORDAN),
            _book("Knife of Dreams", 2005, 315163, 1939, JORDAN, note="The last book Jordan finished."),
            _book("The Gathering Storm", 2009, 297502, 1978, JORDAN, note="Completed by Brandon Sanderson."),
            _book("Towers of Midnight", 2010, 328123, 2301, JORDAN),
            _book("A Memory of Light", 2013, 353906, 2507, JORDAN),
        ],
        "sections": [
            ("pace", "A pace that works", [
                "An hour a day takes almost exactly a year. That is the honest number, and it is why a tracker helps "
                "with this series more than most: a book a month is a pace people keep up, and it finishes in fourteen "
                "months with room for a break.",
                "On audio, each book is 23 to 42 hours. A daily commute of an hour in total gets through an average "
                "book in about a month at normal speed, or three weeks at 1.5x.",
            ]),
            ("slow-books", "The slow middle", [
                "Readers call books seven to ten \"the slog\". The plot spreads across many characters and moves "
                "slowly, most of all in Crossroads of Twilight. Together those four books are about 1.03 million words, "
                "or 86 hours. They are also among the shorter books in the series, and Knife of Dreams, which follows, "
                "is widely seen as a return to form.",
                "New Spring is a short prequel set twenty years earlier. It was written late and assumes you know the "
                "world, so it is left out of the total here. Reading it first is not recommended.",
            ]),
            ("halfway", "A place to pause", [
                "Lord of Chaos, book six, ends with one of the largest battles in the series. It is the natural place to take "
                "a break before the slower run of books seven to ten. By then you have read about 1.96 million words, a "
                "little under half of the fourteen books.",
                "Each book ends with a glossary of names and places. Use it. With a cast this large, a month away can make "
                "the opening chapters of the next book hard going.",
            ]),
        ],
        "faq": [
            ("How many books are in The Wheel of Time?",
             "Fourteen main novels, published from 1990 to 2013, plus the prequel New Spring."),
            ("How many words is The Wheel of Time?",
             "About 4.29 million in the fourteen main books, or about 4.41 million with New Spring."),
            ("How long is the Wheel of Time audiobook?",
             "450 hours for the fourteen main books in the Kramer and Reading recordings, which is nearly 19 days of continuous listening."),
        ],
    },
    "dune": {
        "name": "Dune", "kind": "book", "reviewed": WIDENED, "in_order": "dune",
        "heading": "How long does it take to read Dune?",
        "summary": "Dune is about 188,000 words, roughly 16 hours to read or 21 on audio. Times for all six Frank Herbert novels and where to stop.",
        "audio": {"narrator": "Scott Brick, Simon Vance and cast", "note": "Audiobook lengths are for the Macmillan Audio recordings led by Scott Brick and Simon Vance."},
        "see_also": ["the-lord-of-the-rings", "a-song-of-ice-and-fire", "star-wars-films"],
        "lead": [
            "Dune, the first novel, is about 188,000 words. At 200 words a minute it takes close to 16 hours to read, "
            "and the unabridged audiobook runs 21 hours.",
            "Frank Herbert wrote five sequels. All six books together are roughly 870,000 words, about 72 hours of "
            "reading or 97 of listening. The sequels are left out of the total below, so the page answers for "
            "the first book. Tick them in the planner to add them.",
        ],
        "parts": [
            _book("Dune", 1965, 188000, 1262, HERBERT),
            _book("Dune Messiah", 1969, 80000, 537, HERBERT, approx=True, optional=True, note="By far the shortest. Closes Paul's story."),
            _book("Children of Dune", 1976, 150000, 1011, HERBERT, approx=True, optional=True),
            _book("God Emperor of Dune", 1981, 140000, 948, HERBERT, approx=True, optional=True, note="Set 3,500 years later."),
            _book("Heretics of Dune", 1984, 160000, 1084, HERBERT, approx=True, optional=True, note="Another 1,500 years on, with a new cast."),
            _book("Chapterhouse: Dune", 1985, 150000, 1002, HERBERT, approx=True, optional=True, note="Ends on an open question."),
        ],
        "sections": [
            ("where-to-stop", "Where you can stop", [
                "Dune works as a single book, and many readers stop there. Dune Messiah is short, about seven hours, "
                "and changes how the first book reads, so the two together make a complete story in about 22 hours. "
                "Children of Dune rounds off the first trilogy at about 35 hours.",
                "The last three books are a different project. God Emperor jumps thousands of years ahead and is "
                "mostly conversation. Heretics and Chapterhouse start again with new characters, and Chapterhouse ends "
                "without resolving its plot, because Herbert died in 1986 before writing a seventh book.",
            ]),
            ("counting", "How these lengths were worked out", [
                "The word count for Dune itself is widely published. Reliable counts for the sequels are harder to "
                "find, so we estimated them from the length of each unabridged audiobook at the pace the first book is "
                "read, and rounded to the nearest 10,000 words. Treat them as good to within about ten percent.",
                "The prequels and sequels written by Brian Herbert and Kevin J. Anderson are not counted. The two "
                "Denis Villeneuve films released so far cover the first novel only.",
            ]),
            ("films", "Reading before the films", [
                Dated("Denis Villeneuve's two films split the first novel in half, so reading Dune before or after them "
                      "takes the same 16 hours. Dune: Part Three, his version of Dune Messiah, opens on December 18, 2026. "
                      "Messiah is the shortest book in the series, about seven hours, so it fits easily before then.",
                      ("2026-12-18",
                       "Denis Villeneuve's first two films split the first novel in half, so reading Dune before or after "
                       "them takes the same 16 hours. Dune: Part Three, his version of Dune Messiah, came out on December "
                       "18, 2026. Messiah is the shortest book in the series, about seven hours, so it is an easy read "
                       "before or after the film.")),
                "The films change some things, most of all how Chani feels about Paul by the end. Reading the book afterwards "
                "is a good way to see what was moved.",
            ]),
            ("jumps", "How far apart the books are", [
                "Each sequel starts some years after the one before it, and the gaps grow. Dune Messiah opens twelve years "
                "after Dune, and Children of Dune nine years after Messiah. Then God Emperor of Dune jumps about 3,500 "
                "years, Heretics of Dune another 1,500, and Chapterhouse: Dune carries straight on from Heretics. Herbert "
                "died in 1986 with the story unfinished.",
                "That shape is why the first three are often read as a trilogy. Dune, Messiah and Children of Dune follow "
                "Paul and his children, and come to 418,000 words, about 35 hours at the planner's usual pace and a little "
                "under half the series. God Emperor follows one of those children thousands of years on, and Heretics and "
                "Chapterhouse have an almost entirely new cast, so the last page of Children of Dune is a good place to "
                "decide whether to go on.",
            ]),
        ],
        "faq": [
            ("How long does it take to read Dune?",
             "About 16 hours at 200 words a minute, or about 21 hours at a slower 150. The audiobook is 21 hours 2 minutes."),
            ("How many pages is Dune?",
             "It depends on the edition: a little over 500 pages in the larger paperbacks and nearly 900 in the small mass-market edition."),
            ("Do I need to read all six Dune books?",
             "No. The first book stands alone, and Dune Messiah and Children of Dune finish the story of Paul and his "
             "family. The later three are for readers who want more of Herbert's ideas."),
        ],
    },
    "the-stormlight-archive": {
        "name": "The Stormlight Archive", "kind": "book", "reviewed": UPDATED, "in_order": "cosmere",
        "heading": "How long does it take to read The Stormlight Archive?",
        "summary": "The five Stormlight Archive books so far are about 2.18 million words: roughly 182 hours to read, or 269 hours on audio. Book-by-book times.",
        "audio": {"narrator": "Michael Kramer and Kate Reading", "note": "Audiobook lengths are for the Michael Kramer and Kate Reading recordings."},
        "see_also": ["the-wheel-of-time", "a-song-of-ice-and-fire", "harry-potter"],
        "lead": [
            "The Stormlight Archive stands at five novels and about 2.18 million words. At 200 words a minute that "
            "is roughly 182 hours of reading. The audiobooks, read by Michael Kramer and Kate Reading, total 269 hours.",
            "Every book is enormous and each is longer than the one before, from about 383,000 words for The Way of "
            "Kings to about 491,000 for Wind and Truth. The fifth book closes the first half of a planned ten. "
            "Brandon Sanderson has said the sixth is years away, so this is a good moment to catch up.",
        ],
        "parts": [
            _book("The Way of Kings", 2010, 383389, 2730, SANDERSON),
            _book("Words of Radiance", 2014, 399431, 2895, SANDERSON),
            _book("Edgedancer", 2016, 40000, 384, SANDERSON, optional=True, approx=True, note="A novella set between books two and three."),
            _book("Oathbringer", 2017, 451912, 3305, SANDERSON),
            _book("Dawnshard", 2020, 56000, 425, SANDERSON, optional=True, approx=True, note="A novella set between books three and four."),
            _book("Rhythm of War", 2020, 455891, 3446, SANDERSON),
            _book("Wind and Truth", 2024, 491000, 3768, SANDERSON, approx=True, note="The longest so far, and the end of the first arc."),
        ],
        "sections": [
            ("pace", "A pace that works", [
                "An hour a day takes six months. Each book is 32 to 41 hours of reading, so a book every five or six "
                "weeks is a realistic rhythm. The books are divided into five parts with short interludes between "
                "them, and the end of a part is the natural place to put a book down for a few days.",
                "These are popular on audio, and long. The Way of Kings is 45 and a half hours and Wind and Truth is "
                "nearly 63. At 1.5x the full set comes down from 269 hours to 179, about the same as reading.",
            ]),
            ("novellas", "The two novellas", [
                "Edgedancer and Dawnshard are short books that sit between the main novels. Together they add about "
                "eight hours of reading. They are left out of the default total, but both set up things the next "
                "novel takes for granted, so most readers include them. Tick them in the planner to add them.",
                "Sanderson's other series share a universe with Stormlight. None of them are required, and none are "
                "counted here.",
            ]),
            ("focus", "Whose book is it?", [
                "Each novel gives one character a run of flashback chapters that tell their past alongside the main story: "
                "Kaladin in The Way of Kings, Shallan in Words of Radiance, Dalinar in Oathbringer, Eshonai and Venli in "
                "Rhythm of War and Szeth in Wind and Truth. The chapters are spread through the book, so the history arrives "
                "in pieces.",
                "That is a reason not to skim them. The flashbacks usually explain the choice that character makes at the "
                "climax.",
            ]),
        ],
        "faq": [
            ("How many Stormlight Archive books are there?",
             "Five novels so far, published from 2010 to 2024, out of a planned ten. There are also two novellas, Edgedancer and Dawnshard."),
            ("How long is The Way of Kings?",
             "About 383,000 words: roughly 32 hours of reading, or 45 hours 30 minutes as an audiobook."),
            ("How long is the Wind and Truth audiobook?",
             "62 hours 48 minutes, the longest in the series."),
        ],
    },
}
