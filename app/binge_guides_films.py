"""Film series for the "how long does it take" guides (/binge-calculator/<slug>).

``minutes`` is the theatrical running time with credits, as listed on each
film's Wikipedia page in November 2026. ``alt`` is the running time of the cut
the guide's switch names (the extended editions of the Middle-earth films).
"""

REVIEWED = "2026-11-10"


def _film(name, year, minutes, **extra):
    return {"name": name, "year": year, "minutes": minutes, **extra}


GUIDES = {
    "marvel-infinity-saga": {
        "name": "the Marvel Infinity Saga", "kind": "film", "reviewed": REVIEWED,
        "card": "Marvel: the Infinity Saga",
        "heading": "How long does it take to watch every Marvel film in the Infinity Saga?",
        "summary": "The 23 Marvel films from Iron Man to Spider-Man: Far From Home run 49 hours 58 minutes. Every running time, and a marathon planner.",
        "see_also": ["star-wars-films", "harry-potter-films", "middle-earth-films"],
        "lead": [
            "The Infinity Saga is the first 23 films of the Marvel Cinematic Universe, from Iron Man in 2008 to "
            "Spider-Man: Far From Home in 2019. Their running times add up to 2,998 minutes: two minutes short of 50 hours.",
            "That figure includes the credits, which matter here because nearly every film has a scene during or after "
            "them. The shortest films are The Incredible Hulk and Thor: The Dark World at 112 minutes each. The "
            "longest is Avengers: Endgame at 3 hours 1 minute.",
        ],
        "parts": [
            _film("Iron Man", 2008, 126, note="Phase One"),
            _film("The Incredible Hulk", 2008, 112, note="Phase One"),
            _film("Iron Man 2", 2010, 125, note="Phase One"),
            _film("Thor", 2011, 114, note="Phase One"),
            _film("Captain America: The First Avenger", 2011, 124, note="Phase One"),
            _film("The Avengers", 2012, 143, note="Phase One"),
            _film("Iron Man 3", 2013, 130, note="Phase Two"),
            _film("Thor: The Dark World", 2013, 112, note="Phase Two"),
            _film("Captain America: The Winter Soldier", 2014, 136, note="Phase Two"),
            _film("Guardians of the Galaxy", 2014, 122, note="Phase Two"),
            _film("Avengers: Age of Ultron", 2015, 141, note="Phase Two"),
            _film("Ant-Man", 2015, 117, note="Phase Two"),
            _film("Captain America: Civil War", 2016, 147, note="Phase Three"),
            _film("Doctor Strange", 2016, 115, note="Phase Three"),
            _film("Guardians of the Galaxy Vol. 2", 2017, 136, note="Phase Three"),
            _film("Spider-Man: Homecoming", 2017, 133, note="Phase Three"),
            _film("Thor: Ragnarok", 2017, 130, note="Phase Three"),
            _film("Black Panther", 2018, 134, note="Phase Three"),
            _film("Avengers: Infinity War", 2018, 149, note="Phase Three"),
            _film("Ant-Man and the Wasp", 2018, 118, note="Phase Three"),
            _film("Captain Marvel", 2019, 124, note="Phase Three"),
            _film("Avengers: Endgame", 2019, 181, note="Phase Three"),
            _film("Spider-Man: Far From Home", 2019, 129, note="Phase Three"),
        ],
        "sections": [
            ("pace", "A pace that works", [
                "One film a night takes 23 nights. Two on each weekend day is four a weekend, which finishes in six "
                "weekends. The phases make good milestones: Phase One and Phase Two are six films and about twelve "
                "and a half hours each, and Phase Three is eleven films and 25 hours, half the saga on its own.",
                "Infinity War and Endgame are two halves of one story and run five and a half hours together. Keep a "
                "free day for them. The list is in release order, which is the order the films were written to be seen "
                "in and the one we would give a first-time viewer.",
            ]),
            ("not-counted", "What the total leaves out", [
                "Only the 23 films of the Infinity Saga are counted. The Marvel films released since 2021, known as "
                "the Multiverse Saga, are a separate and still unfinished run, and the Disney+ series add far more "
                "hours than the films do.",
                "If you leave when the credits start you save roughly ten minutes a film, close to four hours over "
                "the saga, but you miss the scenes that set up the next film. Tick off the films you have already "
                "seen in the list below and the planner counts only the rest.",
            ]),
        ],
        "faq": [
            ("How many films are in the Infinity Saga?",
             "23, released from 2008 to 2019 in three phases of six, six and eleven films."),
            ("What is the longest Marvel film in the Infinity Saga?",
             "Avengers: Endgame, at 181 minutes. Avengers: Infinity War is next at 149."),
            ("Could I watch the Infinity Saga in a week?",
             "Only at a little over seven hours a day, about three films daily. Ten days at five hours a day is more comfortable."),
        ],
    },
    "star-wars-films": {
        "name": "the Star Wars films", "kind": "film", "reviewed": REVIEWED, "in_order": "star-wars",
        "card": "Star Wars: the films",
        "heading": "How long does it take to watch all the Star Wars films?",
        "summary": "The nine Star Wars saga films run 20 hours 24 minutes, or just under 25 hours with Rogue One and Solo. Trilogy totals and a planner.",
        "see_also": ["marvel-infinity-saga", "middle-earth-films", "harry-potter-films"],
        "lead": [
            "The nine films of the Skywalker saga, Episodes I to IX, run 1,224 minutes in their theatrical versions. "
            "That is 20 hours 24 minutes. Add the two stand-alone films, Rogue One and Solo, and the total is 24 "
            "hours 53 minutes.",
            "The three trilogies are close in length. The original three are the shortest at about six hours 17 "
            "minutes, the prequels run six hours 56 minutes, and the sequels seven hours 11 minutes. The Last Jedi "
            "is the longest single film, at 152 minutes.",
        ],
        "parts": [
            _film("A New Hope", 1977, 121, title="Star Wars: Episode IV - A New Hope", creator="George Lucas", note="Episode IV",
                  aka=["Star Wars", "Star Wars: A New Hope"]),
            _film("The Empire Strikes Back", 1980, 124, title="Star Wars: Episode V - The Empire Strikes Back", creator="Irvin Kershner", note="Episode V"),
            _film("Return of the Jedi", 1983, 132, title="Star Wars: Episode VI - Return of the Jedi", creator="Richard Marquand", note="Episode VI"),
            _film("The Phantom Menace", 1999, 134, title="Star Wars: Episode I - The Phantom Menace", creator="George Lucas", note="Episode I"),
            _film("Attack of the Clones", 2002, 142, title="Star Wars: Episode II - Attack of the Clones", creator="George Lucas", note="Episode II"),
            _film("Revenge of the Sith", 2005, 140, title="Star Wars: Episode III - Revenge of the Sith", creator="George Lucas", note="Episode III"),
            _film("The Force Awakens", 2015, 138, title="Star Wars: Episode VII - The Force Awakens", creator="J.J. Abrams", note="Episode VII"),
            _film("Rogue One", 2016, 134, title="Rogue One: A Star Wars Story", creator="Gareth Edwards", optional=True,
                  note="Stand-alone. Ends minutes before A New Hope begins."),
            _film("The Last Jedi", 2017, 152, title="Star Wars: Episode VIII - The Last Jedi", creator="Rian Johnson", note="Episode VIII"),
            _film("Solo", 2018, 135, title="Solo: A Star Wars Story", creator="Ron Howard", optional=True, note="Stand-alone. Han Solo's early years."),
            _film("The Rise of Skywalker", 2019, 141, title="Star Wars: Episode IX - The Rise of Skywalker", creator="J.J. Abrams", note="Episode IX"),
        ],
        "sections": [
            ("pace", "A pace that works", [
                "A trilogy fits in a day with meal breaks, so three Saturdays covers the saga. One film a night takes "
                "nine nights, or eleven with the two stand-alone films.",
                "Watching all nine in one go is more than 20 hours before a single break, so give it a weekend at "
                "least. If you want one long day, the original trilogy at a little over six hours is the one to pick.",
            ]),
            ("versions", "Which versions are counted", [
                "The times are for the theatrical releases. The versions of the original trilogy on Disney+ and on "
                "current discs are the later special editions, which add a few minutes to each film. Across the three "
                "it is about ten minutes, so the plan barely changes.",
                "The list is in release order. For story order, and for where the series such as The Clone Wars and "
                "Andor fit, see the Star Wars in order guide. The animated Clone Wars film from 2008 and The "
                "Mandalorian and Grogu from 2026 follow the TV series and are not counted here.",
            ]),
        ],
        "faq": [
            ("How long are all nine Star Wars films?",
             "20 hours 24 minutes for Episodes I to IX in their theatrical versions."),
            ("Which Star Wars film is the longest?",
             "The Last Jedi, at 152 minutes. The shortest is the original Star Wars from 1977, at 121."),
            ("How long is the original Star Wars trilogy?",
             "377 minutes, or 6 hours 17 minutes, for A New Hope, The Empire Strikes Back and Return of the Jedi."),
        ],
    },
    "middle-earth-films": {
        "name": "The Lord of the Rings films", "kind": "film", "reviewed": REVIEWED, "in_order": "lord-of-the-rings",
        "card": "The Lord of the Rings films",
        "heading": "How long does it take to watch The Lord of the Rings films?",
        "summary": "The Lord of the Rings trilogy runs 9 hours 18 minutes in cinemas and 12 hours 6 minutes extended. Add The Hobbit and plan a marathon.",
        "alt": {"label": "Extended editions", "summary": "extended",
                "note": "Uses the extended edition of each film in place of the theatrical cut."},
        "see_also": ["the-lord-of-the-rings", "star-wars-films", "harry-potter-films"],
        "lead": [
            "The three Lord of the Rings films run 558 minutes in their theatrical cuts: 9 hours 18 minutes. The "
            "extended editions run 726 minutes, which is 12 hours 6 minutes, and they are the versions most "
            "marathons use.",
            "The Hobbit trilogy adds 7 hours 54 minutes in its theatrical cuts or 8 hours 52 minutes extended. All six films "
            "in their extended editions come to just under 21 hours. The Hobbit films are left out of the default "
            "total below. Tick them to add them, and use the switch to change between cuts.",
        ],
        "parts": [
            _film("The Hobbit: An Unexpected Journey", 2012, 169, alt=182, creator="Peter Jackson", optional=True),
            _film("The Hobbit: The Desolation of Smaug", 2013, 161, alt=186, creator="Peter Jackson", optional=True),
            _film("The Hobbit: The Battle of the Five Armies", 2014, 144, alt=164, creator="Peter Jackson", optional=True),
            _film("The Fellowship of the Ring", 2001, 178, alt=228, title="The Lord of the Rings: The Fellowship of the Ring", creator="Peter Jackson"),
            _film("The Two Towers", 2002, 179, alt=235, title="The Lord of the Rings: The Two Towers", creator="Peter Jackson"),
            _film("The Return of the King", 2003, 201, alt=263, title="The Lord of the Rings: The Return of the King", creator="Peter Jackson",
                  note="The extended edition is 4 hours 23 minutes, the longest film on this page."),
        ],
        "sections": [
            ("marathon", "Planning a one-day marathon", [
                "The extended trilogy is 12 hours 6 minutes on paper, but about 45 minutes of that is the extra credit "
                "roll listing fan club members at the end of each film. Skip those and the watching time is about 11 "
                "hours 20 minutes.",
                "With an hour for meals between films, a marathon that starts at 9 in the morning ends around 10:30 at "
                "night. The theatrical cuts make a gentler day: start at 10 and you finish a little after 9 in the "
                "evening with the same breaks.",
            ]),
            ("cuts", "Theatrical or extended", [
                "The extended editions add 50 minutes to The Fellowship of the Ring, 56 to The Two Towers and 62 to "
                "The Return of the King. For a first viewing the theatrical cuts are tighter and are the versions that "
                "won the awards. Most fans prefer the extended editions on a rewatch, mainly for the added scenes "
                "with Saruman, Faramir and the houses of healing.",
                "For The Hobbit the difference is smaller, 58 minutes over three films. The 2024 animated film The "
                "War of the Rohirrim and the Rings of Power series are not counted.",
            ]),
        ],
        "faq": [
            ("How long are the Lord of the Rings extended editions?",
             "12 hours 6 minutes in total: 3 hours 48 minutes, 3 hours 55 minutes and 4 hours 23 minutes, including the extended credits."),
            ("How long is the theatrical Lord of the Rings trilogy?",
             "9 hours 18 minutes: 178, 179 and 201 minutes."),
            ("How long are all six Middle-earth films?",
             "17 hours 12 minutes in the theatrical cuts, or 20 hours 58 minutes with every film in its extended edition."),
        ],
    },
    "harry-potter-films": {
        "name": "the Harry Potter films", "kind": "film", "reviewed": REVIEWED, "in_order": "harry-potter",
        "card": "Harry Potter: the films",
        "heading": "How long does it take to watch all the Harry Potter films?",
        "summary": "The eight Harry Potter films run 19 hours 38 minutes in total. Every running time, how to split a marathon, and a finish-date planner.",
        "see_also": ["harry-potter", "middle-earth-films", "star-wars-films"],
        "lead": [
            "The eight Harry Potter films run 1,178 minutes in total, which is 19 hours 38 minutes. They are all "
            "between two and two and three quarter hours long.",
            "The films get shorter as the books get longer. Chamber of Secrets, from the second-shortest book, is the "
            "longest film at 161 minutes. Order of the Phoenix, the longest book, is the second-shortest film at 138. "
            "The last film, Deathly Hallows: Part 2, is the shortest of all at 130.",
        ],
        "parts": [
            _film("Sorcerer's Stone", 2001, 152, title="Harry Potter and the Sorcerer's Stone", creator="Chris Columbus",
                  aka=["Harry Potter and the Philosopher's Stone", "Philosopher's Stone"],
                  note="Philosopher's Stone outside the US."),
            _film("Chamber of Secrets", 2002, 161, title="Harry Potter and the Chamber of Secrets", creator="Chris Columbus"),
            _film("Prisoner of Azkaban", 2004, 141, title="Harry Potter and the Prisoner of Azkaban", creator="Alfonso Cuarón"),
            _film("Goblet of Fire", 2005, 157, title="Harry Potter and the Goblet of Fire", creator="Mike Newell"),
            _film("Order of the Phoenix", 2007, 138, title="Harry Potter and the Order of the Phoenix", creator="David Yates"),
            _film("Half-Blood Prince", 2009, 153, title="Harry Potter and the Half-Blood Prince", creator="David Yates"),
            _film("Deathly Hallows: Part 1", 2010, 146, title="Harry Potter and the Deathly Hallows: Part 1", creator="David Yates"),
            _film("Deathly Hallows: Part 2", 2011, 130, title="Harry Potter and the Deathly Hallows: Part 2", creator="David Yates"),
        ],
        "sections": [
            ("pace", "A pace that works", [
                "One film a night takes eight nights. For a weekend marathon, three films on Saturday and three on "
                "Sunday is about seven and a half hours each day, and the two parts of Deathly Hallows, four hours 36 "
                "minutes together, make a natural third day or a Friday night start.",
                "With children, the tone matters more than the clock. The first two films are gentle. From Goblet of "
                "Fire on they are darker and most carry a higher age rating, so many families watch one or two a "
                "year as the children grow up.",
            ]),
            ("not-counted", "What the total leaves out", [
                "Extended cuts of the first two films exist on some disc releases, with about seven and thirteen "
                "minutes of extra scenes. Streaming services carry the theatrical versions, which are the ones "
                "counted here.",
                "The three Fantastic Beasts films are a prequel series and are not counted, and neither is the "
                "new television adaptation of the books. Reading the seven novels takes about 90 hours, more than "
                "four times as long as watching the films.",
            ]),
        ],
        "faq": [
            ("How long are all eight Harry Potter films?",
             "19 hours 38 minutes, or 1,178 minutes."),
            ("Which Harry Potter film is the longest?",
             "Chamber of Secrets, at 161 minutes. The shortest is Deathly Hallows: Part 2, at 130."),
            ("Can I watch all the Harry Potter films in one day?",
             "Only by staying up for nearly 20 hours with no breaks. Two days of about ten hours each is the practical minimum."),
        ],
    },
}
