"""TV series for the "how long does it take" guides (/binge-calculator/<slug>).

Episode counts are per season as first broadcast, checked against TVmaze. For
shows made for ad-supported channels, ``minutes`` is a typical episode on a
streaming copy without ad breaks. For shows whose episodes vary a lot (Game of
Thrones, Stranger Things, Succession) the season carries a ``total`` in minutes
instead, added up from the listed running time of each episode.
"""

REVIEWED = "2026-11-10"

GUIDES = {
    "breaking-bad": {
        "name": "Breaking Bad", "kind": "tv", "reviewed": REVIEWED,
        "summary": "Breaking Bad is 62 episodes over five seasons, about 49 hours without ads. Season lengths, a pace planner and what the total leaves out.",
        "titles": [{"kind": "tv", "title": "Breaking Bad", "year": 2008}],
        "see_also": ["better-call-saul", "the-sopranos", "the-wire"],
        "lead": [
            "Breaking Bad is 62 episodes over five seasons. A streaming copy without ads runs about 47 minutes an episode, "
            "so the whole show takes roughly 49 hours: a little over two days if you never slept, or about a month of "
            "ordinary evenings.",
            "It is one of the easier long dramas to finish, because the seasons are short. The first is only seven "
            "episodes, cut down by the 2007 writers' strike. The last is sixteen, shown in two halves a year apart, "
            "which is why some box sets call the second half a sixth season.",
        ],
        "parts": [
            {"name": "Season 1", "episodes": 7, "minutes": 47, "note": "2008. Shortened by the writers' strike."},
            {"name": "Season 2", "episodes": 13, "minutes": 47, "note": "2009"},
            {"name": "Season 3", "episodes": 13, "minutes": 47, "note": "2010"},
            {"name": "Season 4", "episodes": 13, "minutes": 47, "note": "2011"},
            {"name": "Season 5", "episodes": 16, "minutes": 47, "note": "2012 and 2013, eight episodes each year."},
        ],
        "sections": [
            ("pace", "A pace that works", [
                "Two episodes a night finishes the show in 31 nights. If weeknights are tight, one episode Monday to "
                "Friday and three on each weekend day is eleven a week, which gets you to the finale in under six weeks.",
                "Nothing here is filler, so there is no shortcut worth taking. The one episode people argue about is "
                "\"Fly\" in season 3, which never leaves the lab. Plenty of viewers rank it among the best, so watch it "
                "and decide for yourself.",
                "The last eight episodes are hard to stop in the middle of. If you can, keep a weekend free for them.",
            ]),
            ("not-counted", "What the total leaves out", [
                "El Camino, the 2019 film that follows Jesse after the finale, adds 2 hours 2 minutes. Watch it after "
                "the last episode, never before.",
                "Better Call Saul is a separate 63-episode series and has its own page here. The short online "
                "\"minisodes\" from the early seasons are not counted either. They are jokes, and the story does not need them.",
            ]),
        ],
        "faq": [
            ("How many episodes of Breaking Bad are there?",
             "62 across five seasons: 7, 13, 13, 13 and 16. Season 5 aired as two runs of eight episodes, in 2012 and 2013."),
            ("Should I watch Better Call Saul before Breaking Bad?",
             "No. Better Call Saul was made afterwards and assumes you know how Breaking Bad ends. Its last episodes are "
             "set after the Breaking Bad finale, so watching it first spoils both shows."),
            ("How long would Breaking Bad take in one sitting?",
             "About 49 hours with no breaks at all. Nobody should try that. At four hours a day it is a 13-day project."),
        ],
    },
    "better-call-saul": {
        "name": "Better Call Saul", "kind": "tv", "reviewed": REVIEWED,
        "summary": "Better Call Saul runs 63 episodes over six seasons, about 50 hours. See each season's length and plan the watch around Breaking Bad.",
        "titles": [{"kind": "tv", "title": "Better Call Saul", "year": 2015}],
        "see_also": ["breaking-bad", "mad-men", "succession"],
        "lead": [
            "Better Call Saul is 63 episodes: five seasons of ten and a final season of thirteen. Episodes run a little "
            "under 50 minutes without ads, and the last season runs longer, so the full series comes to about 50 hours.",
            "That is almost exactly the length of Breaking Bad, which surprises people, because Saul feels like the "
            "slower show. It spends its time on small cons and court filings, and most of it is set six years before "
            "Walter White walks into Saul's office.",
        ],
        "parts": [
            {"name": "Season 1", "episodes": 10, "minutes": 46, "note": "2015"},
            {"name": "Season 2", "episodes": 10, "minutes": 46, "note": "2016"},
            {"name": "Season 3", "episodes": 10, "minutes": 46, "note": "2017"},
            {"name": "Season 4", "episodes": 10, "minutes": 46, "note": "2018"},
            {"name": "Season 5", "episodes": 10, "minutes": 46, "note": "2020"},
            {"name": "Season 6", "episodes": 13, "minutes": 53, "note": "2022, in two parts. Several episodes pass an hour."},
        ],
        "sections": [
            ("pace", "A pace that works", [
                "Ten-episode seasons split neatly into weeks: two episodes on five nights, or one long Saturday. At that "
                "rate the first five seasons take five weeks and the last takes about a week and a half.",
                "The early seasons are slow on purpose. If you are unsure whether to continue, give it until the end of "
                "season 1 before deciding. Season 6 is the opposite: its second half works best watched close together, "
                "because the final four episodes jump forward in time and lean on details from much earlier.",
            ]),
            ("order", "Where it fits with Breaking Bad", [
                "Watch Breaking Bad first. Better Call Saul is a prequel in name, but every season opens with a "
                "black-and-white scene set after Breaking Bad, and the final stretch is a direct sequel to it.",
                "Both shows back to back come to about 98 hours across 125 episodes. El Camino, the Breaking Bad "
                "film, is not needed for Saul and can go anywhere after the Breaking Bad finale.",
            ]),
        ],
        "faq": [
            ("How many seasons of Better Call Saul are there?",
             "Six, with 63 episodes in total. Seasons 1 to 5 have ten episodes each and season 6 has thirteen."),
            ("Is Better Call Saul longer than Breaking Bad?",
             "By one episode and about an hour. Breaking Bad is 62 episodes and roughly 49 hours; Better Call Saul is 63 and roughly 50."),
            ("Can I watch Better Call Saul without seeing Breaking Bad?",
             "You can follow the plot, but the opening scenes of each season and most of the final episodes are written "
             "for people who already know Breaking Bad. It is better second."),
        ],
    },
    "the-sopranos": {
        "name": "The Sopranos", "kind": "tv", "reviewed": REVIEWED,
        "summary": "The Sopranos is 86 episodes over six seasons, about 79 hours. Season-by-season lengths and how long it takes at one or two episodes a night.",
        "titles": [{"kind": "tv", "title": "The Sopranos", "year": 1999}],
        "see_also": ["the-wire", "mad-men", "breaking-bad"],
        "lead": [
            "The Sopranos is 86 episodes. Five seasons have thirteen each and the sixth has twenty-one, shown in two "
            "parts across 2006 and 2007. It was made for HBO with no ad breaks, so episodes are close to a full hour: "
            "about 55 minutes on average, which puts the whole series near 79 hours.",
            "Running times vary more than on a network show. A few early episodes are under 45 minutes and some late "
            "ones pass 70, so a season can take an hour more or less than the figure below.",
        ],
        "parts": [
            {"name": "Season 1", "episodes": 13, "minutes": 55, "note": "1999"},
            {"name": "Season 2", "episodes": 13, "minutes": 55, "note": "2000"},
            {"name": "Season 3", "episodes": 13, "minutes": 55, "note": "2001"},
            {"name": "Season 4", "episodes": 13, "minutes": 55, "note": "2002"},
            {"name": "Season 5", "episodes": 13, "minutes": 55, "note": "2004"},
            {"name": "Season 6", "episodes": 21, "minutes": 55, "note": "2006 and 2007: twelve episodes, then the final nine."},
        ],
        "sections": [
            ("pace", "A pace that works", [
                "One episode a night is the way it was written to be seen, and at that rate it takes 86 nights, a bit "
                "over twelve weeks. Two a night halves that to about six weeks, which is still slow enough to let the "
                "dream sequences and the therapy scenes sink in.",
                "The seasons are self-contained enough to pause between. Each one builds to its own ending, so stopping "
                "for a week after a finale costs you nothing.",
            ]),
            ("not-counted", "What the total leaves out", [
                "The Many Saints of Newark, the 2021 prequel film, runs two hours and is not counted. It is set in the "
                "1960s and 70s but leans on what you know about the characters as adults, so save it for after the series.",
                "Season 6 is sometimes sold as two seasons, 6A and 6B. Either way it is the same 21 episodes.",
            ]),
        ],
        "faq": [
            ("How many episodes of The Sopranos are there?",
             "86 across six seasons. Seasons 1 to 5 have 13 episodes each and season 6 has 21."),
            ("How long is each episode of The Sopranos?",
             "About 55 minutes on average. HBO episodes have no ad breaks and no fixed length, so they range from "
             "about 43 minutes to a little over 70."),
            ("Do I need to watch The Many Saints of Newark first?",
             "No. It was made 14 years after the finale and plays best once you have seen the series."),
        ],
    },
    "the-wire": {
        "name": "The Wire", "kind": "tv", "reviewed": REVIEWED,
        "summary": "The Wire is 60 episodes over five seasons, about 59 hours. How long each season takes, and why it is best watched a season at a time.",
        "titles": [{"kind": "tv", "title": "The Wire", "year": 2002}],
        "see_also": ["the-sopranos", "breaking-bad", "succession"],
        "lead": [
            "The Wire is 60 episodes across five seasons, each close to a full hour because HBO runs no ads. The series "
            "finale is 93 minutes on its own. In total it takes about 59 hours.",
            "Every season looks at Baltimore through a different institution: the drug trade and the police who chase "
            "it, the docks, city hall, the schools, and the newspaper. Characters carry over, but each season is built "
            "like one long novel, and that shapes the best way to schedule it.",
        ],
        "parts": [
            {"name": "Season 1", "episodes": 13, "minutes": 58, "note": "2002. The Barksdale case."},
            {"name": "Season 2", "episodes": 12, "minutes": 58, "note": "2003. The docks."},
            {"name": "Season 3", "episodes": 12, "minutes": 58, "note": "2004. City hall."},
            {"name": "Season 4", "episodes": 13, "minutes": 58, "note": "2006. The schools."},
            {"name": "Season 5", "episodes": 10, "total": 615, "note": "2008. The newspaper. Ends with a 93-minute finale."},
        ],
        "sections": [
            ("pace", "A pace that works", [
                "The Wire does not recap. Names, deals and grudges from episode 2 matter in episode 11, so long gaps hurt "
                "more here than with most shows. Two episodes a night gets through a season in under a week and keeps "
                "the case in your head.",
                "Breaks between seasons are fine and even useful. Finishing one season a month, with a week or two off "
                "in between, takes about five months and never feels like homework.",
            ]),
            ("slow-start", "The slow start is real", [
                "The first three or four episodes introduce about thirty characters and explain almost nothing. That "
                "is roughly four hours before the show clicks for most people. Season 2 does it again by moving to the "
                "port with a new cast.",
                "Subtitles help with the slang. They do not add time, and they save you from rewinding.",
            ]),
        ],
        "faq": [
            ("How many episodes are in each season of The Wire?",
             "13, 12, 12, 13 and 10, for 60 in total."),
            ("Can I skip season 2 of The Wire?",
             "It is the season people most often suggest skipping and you should not. Its characters and the port "
             "storyline come back, and season 5 pays off things that start there."),
            ("How long is the final episode of The Wire?",
             "The finale, \"-30-\", runs 93 minutes, about half an hour longer than a normal episode."),
        ],
    },
    "game-of-thrones": {
        "name": "Game of Thrones", "kind": "tv", "reviewed": REVIEWED, "in_order": "game-of-thrones",
        "summary": "Game of Thrones is 73 episodes over eight seasons, about 71 hours. Season lengths, the long final episodes, and a finish-date planner.",
        "titles": [{"kind": "tv", "title": "Game of Thrones", "year": 2011}],
        "see_also": ["a-song-of-ice-and-fire", "the-sopranos", "succession"],
        "lead": [
            "Game of Thrones is 73 episodes over eight seasons and takes about 71 hours. The first six seasons have ten "
            "episodes each at a little under an hour. The last two are shorter in episodes and longer in minutes: "
            "seven episodes in season 7, six in season 8, with most of the final run close to 80 minutes each.",
            "So the last season is not the quick finish it looks like. Its six episodes add up to a little over seven "
            "hours, only about two hours less than a full ten-episode season.",
        ],
        "parts": [
            {"name": "Season 1", "episodes": 10, "total": 570, "note": "2011"},
            {"name": "Season 2", "episodes": 10, "total": 550, "note": "2012"},
            {"name": "Season 3", "episodes": 10, "total": 550, "note": "2013"},
            {"name": "Season 4", "episodes": 10, "total": 550, "note": "2014"},
            {"name": "Season 5", "episodes": 10, "total": 570, "note": "2015"},
            {"name": "Season 6", "episodes": 10, "total": 570, "note": "2016. The finale runs 68 minutes."},
            {"name": "Season 7", "episodes": 7, "total": 441, "note": "2017. Ends with an 80-minute episode."},
            {"name": "Season 8", "episodes": 6, "total": 432, "note": "2019. \"The Long Night\" is 82 minutes."},
        ],
        "sections": [
            ("pace", "A pace that works", [
                "At two episodes a night the first six seasons take 30 nights and the last two take about another week. "
                "The show has a large cast spread over two continents, and episodes cut between five or six storylines, "
                "so it holds together better at a steady daily pace than in occasional bursts.",
                "Each season's ninth episode is where the biggest events land. If you are planning weekends around it, "
                "episodes 9 and 10 of a season make a good Saturday pair.",
            ]),
            ("not-counted", "What the total leaves out", [
                "House of the Dragon is a separate series set nearly two centuries earlier and is not counted here. It "
                "does not need to be seen first or at all.",
                "The books tell the same story as far as roughly season 5, then the show goes past them. Reading the "
                "five published novels takes about twice as long as watching the whole series; there is a page for that too.",
            ]),
        ],
        "faq": [
            ("How many episodes of Game of Thrones are there?",
             "73: ten in each of seasons 1 to 6, seven in season 7 and six in season 8."),
            ("How long is the last season of Game of Thrones?",
             "A little over seven hours. There are only six episodes, but four of them run about 80 minutes."),
            ("Is it quicker to watch Game of Thrones or read the books?",
             "Watching. The series is about 71 hours. The five published books are about 148 hours at an average "
             "reading speed, and the story is not finished on the page."),
        ],
    },
    "mad-men": {
        "name": "Mad Men", "kind": "tv", "reviewed": REVIEWED,
        "summary": "Mad Men is 92 episodes over seven seasons, about 72 hours without ads. Season lengths and a planner for finishing by a date you pick.",
        "titles": [{"kind": "tv", "title": "Mad Men", "year": 2007}],
        "see_also": ["the-sopranos", "succession", "better-call-saul"],
        "lead": [
            "Mad Men is 92 episodes: six seasons of thirteen and a final season of fourteen that aired in two halves, "
            "seven episodes in 2014 and seven in 2015. Episodes run about 47 minutes without ads, which makes the "
            "series roughly 72 hours long.",
            "The story covers the whole of the 1960s, starting in March 1960 and ending in late 1970, and each season "
            "jumps forward a year or more. That makes season breaks the natural place to pause.",
        ],
        "parts": [
            {"name": "Season 1", "episodes": 13, "minutes": 47, "note": "2007. Set in 1960."},
            {"name": "Season 2", "episodes": 13, "minutes": 47, "note": "2008. Set in 1962."},
            {"name": "Season 3", "episodes": 13, "minutes": 47, "note": "2009. Set in 1963."},
            {"name": "Season 4", "episodes": 13, "minutes": 47, "note": "2010"},
            {"name": "Season 5", "episodes": 13, "minutes": 47, "note": "2012. Opens with a double-length premiere, counted as two."},
            {"name": "Season 6", "episodes": 13, "minutes": 47, "note": "2013. Another double-length premiere."},
            {"name": "Season 7", "episodes": 14, "minutes": 47, "note": "2014 and 2015, seven episodes each."},
        ],
        "sections": [
            ("pace", "A pace that works", [
                "Mad Men is quiet. Very little happens in any one episode and a great deal happens across a season, so "
                "it rewards attention more than speed. One or two episodes a night is plenty: at two a night you finish "
                "in 46 nights, about six and a half weeks.",
                "Thirteen-episode seasons fit a fortnight at one a night with a day to spare. Treating each season as "
                "its own two-week block, with a gap before the next, takes about four months and matches how the "
                "show skips time between seasons.",
            ]),
            ("counting", "How the episodes are counted", [
                "Seasons 5 and 6 each begin with a two-hour premiere. Streaming services usually split those into two "
                "episodes, which is how they are counted here, and how the total reaches 92.",
                "There are no specials, films or spin-offs to add. When the last episode ends, you are done.",
            ]),
        ],
        "faq": [
            ("How many episodes of Mad Men are there?",
             "92 across seven seasons: 13 in each of the first six and 14 in the last."),
            ("How long is an episode of Mad Men?",
             "About 47 minutes without ads. It filled a one-hour slot on AMC."),
            ("Why was the last season of Mad Men split in two?",
             "AMC aired the final 14 episodes as two runs of seven, a year apart, as it had done with Breaking Bad. "
             "On streaming they sit together as season 7."),
        ],
    },
    "lost": {
        "name": "Lost", "kind": "tv", "reviewed": REVIEWED,
        "summary": "Lost is 121 episodes over six seasons, about 87 hours without ads. Season lengths, where the short seasons fall, and a pace planner.",
        "titles": [{"kind": "tv", "title": "Lost", "year": 2004}],
        "see_also": ["supernatural", "stranger-things", "game-of-thrones"],
        "lead": [
            "Lost is 121 episodes over six seasons. It was a network show built for hour-long slots, so on streaming "
            "each episode runs about 43 minutes, and the whole series comes to roughly 87 hours.",
            "The first three seasons are long, 23 to 25 episodes each, and hold more than half the total. Season 4 "
            "drops to 14 because of the 2007 writers' strike, and the last two have 17 and 18. If the early seasons feel "
            "endless, it helps to know the back half moves much faster.",
        ],
        "parts": [
            {"name": "Season 1", "episodes": 25, "minutes": 43, "note": "2004 to 2005"},
            {"name": "Season 2", "episodes": 24, "minutes": 43, "note": "2005 to 2006"},
            {"name": "Season 3", "episodes": 23, "minutes": 43, "note": "2006 to 2007"},
            {"name": "Season 4", "episodes": 14, "minutes": 43, "note": "2008. Cut short by the writers' strike."},
            {"name": "Season 5", "episodes": 17, "minutes": 43, "note": "2009"},
            {"name": "Season 6", "episodes": 18, "minutes": 43, "note": "2010. The finale runs about 104 minutes and is counted as two."},
        ],
        "sections": [
            ("pace", "A pace that works", [
                "Three episodes a night is a little over two hours and finishes the show in 41 nights. Lost was "
                "written with a cliffhanger before every ad break and a bigger one at the end, so stopping after "
                "exactly one episode takes more willpower than it should.",
                "The mysteries pile up faster than they are answered. Watching steadily, without month-long gaps, makes "
                "a real difference to how satisfying the answers are, because you still remember the questions.",
            ]),
            ("slow-stretch", "The slow stretch", [
                "The first six episodes of season 3 are the usual low point: the story narrows to a few characters in "
                "cages while the rest of the cast waits. It is a bit over four hours, and the season recovers "
                "strongly afterwards. Do not judge the show by that run.",
                "Counts differ between services because the double-length premieres and finales are sometimes listed "
                "as one episode and sometimes as two. The running time is the same either way.",
            ]),
        ],
        "faq": [
            ("How many episodes of Lost are there?",
             "121 when double-length episodes are counted as two: 25, 24, 23, 14, 17 and 18 across the six seasons."),
            ("How long is the Lost finale?",
             "\"The End\" runs about 104 minutes without ads. It aired as a two-and-a-half-hour event."),
            ("Why is season 4 of Lost so short?",
             "The 2007 to 2008 writers' strike stopped production. The season was cut to 14 episodes and the lost hours "
             "were partly made up in seasons 5 and 6."),
        ],
    },
    "friends": {
        "name": "Friends", "kind": "tv", "reviewed": REVIEWED,
        "summary": "Friends is 236 episodes over ten seasons, about 87 hours at 22 minutes each. Season counts and how long a full rewatch takes at your pace.",
        "titles": [{"kind": "tv", "title": "Friends", "year": 1994}],
        "see_also": ["the-office", "supernatural", "lost"], "skip_minutes": 1,
        "lead": [
            "Friends is 236 episodes over ten seasons. Each one filled a half-hour slot and runs about 22 minutes "
            "without ads, so the complete series is roughly 87 hours.",
            "That is close to the length of Lost, with nearly twice as many episodes. Nine of the ten seasons have 24 "
            "or 25 episodes; only the last is shorter, at 18. Because the episodes are short and mostly stand alone, it "
            "is one of the easiest long shows to fit around a normal week.",
        ],
        "parts": [
            {"name": "Season 1", "episodes": 24, "minutes": 22, "note": "1994 to 1995"},
            {"name": "Season 2", "episodes": 24, "minutes": 22, "note": "1995 to 1996"},
            {"name": "Season 3", "episodes": 25, "minutes": 22, "note": "1996 to 1997"},
            {"name": "Season 4", "episodes": 24, "minutes": 22, "note": "1997 to 1998"},
            {"name": "Season 5", "episodes": 24, "minutes": 22, "note": "1998 to 1999"},
            {"name": "Season 6", "episodes": 25, "minutes": 22, "note": "1999 to 2000"},
            {"name": "Season 7", "episodes": 24, "minutes": 22, "note": "2000 to 2001"},
            {"name": "Season 8", "episodes": 24, "minutes": 22, "note": "2001 to 2002"},
            {"name": "Season 9", "episodes": 24, "minutes": 22, "note": "2002 to 2003"},
            {"name": "Season 10", "episodes": 18, "minutes": 22, "note": "2003 to 2004"},
        ],
        "sections": [
            ("pace", "A pace that works", [
                "Three episodes is 66 minutes, about the length of one drama episode, and at three a night the whole "
                "run takes 79 nights. Four a night is under an hour and a half and brings it down to 59.",
                "A season at four a night takes six evenings. That is the pace most rewatchers settle into: one season "
                "a week, ten weeks, done.",
            ]),
            ("counting", "Skipping intros, and what is not counted", [
                "The theme song runs about 45 seconds and the end credits a little less. Skipping both saves about a "
                "minute an episode, which over 236 episodes is close to four hours. The skip box in the planner does "
                "that sum for you.",
                "Clip shows are counted, since they are numbered episodes; there are a handful and they are safe to "
                "skip. The 2021 reunion special (1 hour 44 minutes) is not counted. Some DVD sets carry extended "
                "cuts a few minutes longer than the broadcast versions that streaming services use.",
            ]),
        ],
        "faq": [
            ("How many episodes of Friends are there?",
             "236 over ten seasons. Seasons 3 and 6 have 25, season 10 has 18 and the rest have 24."),
            ("How long would it take to watch all of Friends without stopping?",
             "About 87 hours, or a little over three and a half days."),
            ("Is Friends longer than The Office?",
             "Yes, by 35 episodes and about 13 hours. The US Office is 201 episodes and roughly 74 hours."),
        ],
    },
    "the-office": {
        "name": "The Office (US)", "kind": "tv", "reviewed": REVIEWED,
        "summary": "The Office (US) is 201 episodes over nine seasons, about 74 hours. Season-by-season counts, the Superfan cuts, and a rewatch planner.",
        "titles": [{"kind": "tv", "title": "The Office", "year": 2005, "aka": ["The Office (US)"]}],
        "see_also": ["friends", "mad-men", "succession"], "skip_minutes": 1,
        "lead": [
            "The American version of The Office is 201 episodes over nine seasons. A standard episode is about 22 "
            "minutes without ads, so the full run is roughly 74 hours.",
            "The seasons are uneven. The first is a six-episode trial that takes barely two hours. Season 4 was "
            "shortened by the 2007 writers' strike, and seasons 5 to 7 are the longest. Steve Carell leaves near the "
            "end of season 7, which leaves 53 episodes, about 19 hours, without Michael Scott.",
        ],
        "parts": [
            {"name": "Season 1", "episodes": 6, "minutes": 22, "note": "2005"},
            {"name": "Season 2", "episodes": 22, "minutes": 22, "note": "2005 to 2006"},
            {"name": "Season 3", "episodes": 25, "minutes": 22, "note": "2006 to 2007"},
            {"name": "Season 4", "episodes": 19, "minutes": 22, "note": "2007 to 2008. Shortened by the writers' strike."},
            {"name": "Season 5", "episodes": 28, "minutes": 22, "note": "2008 to 2009"},
            {"name": "Season 6", "episodes": 26, "minutes": 22, "note": "2009 to 2010"},
            {"name": "Season 7", "episodes": 26, "minutes": 22, "note": "2010 to 2011. Michael's last full season."},
            {"name": "Season 8", "episodes": 24, "minutes": 22, "note": "2011 to 2012"},
            {"name": "Season 9", "episodes": 25, "minutes": 22, "note": "2012 to 2013"},
        ],
        "sections": [
            ("counting", "How the 201 is counted", [
                "The count treats every hour-long episode as two half-hours, the way the show is usually sold and "
                "syndicated. Some services list those as single long episodes, so you may see a lower number for the "
                "same footage. The running time does not change.",
                "Peacock also carries \"Superfan\" episodes for several seasons, which put deleted scenes back in. Those "
                "run noticeably longer, often 30 minutes or more, and would add many hours to the total. The figures "
                "here are for the broadcast cuts.",
            ]),
            ("pace", "A pace that works", [
                "Four episodes a night is just under an hour and a half and takes 51 nights. Most people rewatch "
                "The Office in the background over a couple of months, and at that pace the seasons line up roughly "
                "one per week.",
                "If you are new and season 1 feels stiff, keep going. It is only six episodes, and the show finds its "
                "tone early in season 2.",
            ]),
        ],
        "faq": [
            ("How many episodes of The Office are there?",
             "201 in the US version, counting hour-long episodes as two: 6, 22, 25, 19, 28, 26, 26, 24 and 25."),
            ("How long does it take to watch The Office up to Michael leaving?",
             "Michael's exit, \"Goodbye, Michael\", comes near the end of season 7. Seasons 1 to 7 are 152 episodes, about 56 hours."),
            ("Is the UK Office included?",
             "No. The British series is a separate show: 12 episodes and a two-part Christmas special, about seven and a half hours in all."),
        ],
    },
    "supernatural": {
        "name": "Supernatural", "kind": "tv", "reviewed": REVIEWED,
        "summary": "Supernatural is 327 episodes over fifteen seasons, about 229 hours. Season counts, the original five-season story, and a long-haul planner.",
        "titles": [{"kind": "tv", "title": "Supernatural", "year": 2005}],
        "see_also": ["lost", "friends", "one-piece"],
        "lead": [
            "Supernatural is 327 episodes over fifteen seasons, about 42 minutes each without ads. That is roughly 229 "
            "hours: nine and a half days of continuous television, and one of the longest live-action dramas you can "
            "watch from start to finish.",
            "Most seasons have 22 or 23 episodes. Season 3 has 16 because of the 2007 writers' strike, and the last "
            "two have 20 each. At that size the question is less how long it takes than how to keep going.",
        ],
        "parts": [
            {"name": "Season 1", "episodes": 22, "minutes": 42, "note": "2005 to 2006"},
            {"name": "Season 2", "episodes": 22, "minutes": 42, "note": "2006 to 2007"},
            {"name": "Season 3", "episodes": 16, "minutes": 42, "note": "2007 to 2008. Shortened by the writers' strike."},
            {"name": "Season 4", "episodes": 22, "minutes": 42, "note": "2008 to 2009"},
            {"name": "Season 5", "episodes": 22, "minutes": 42, "note": "2009 to 2010. The end of the original story."},
            {"name": "Season 6", "episodes": 22, "minutes": 42, "note": "2010 to 2011"},
            {"name": "Season 7", "episodes": 23, "minutes": 42, "note": "2011 to 2012"},
            {"name": "Season 8", "episodes": 23, "minutes": 42, "note": "2012 to 2013"},
            {"name": "Season 9", "episodes": 23, "minutes": 42, "note": "2013 to 2014"},
            {"name": "Season 10", "episodes": 23, "minutes": 42, "note": "2014 to 2015"},
            {"name": "Season 11", "episodes": 23, "minutes": 42, "note": "2015 to 2016"},
            {"name": "Season 12", "episodes": 23, "minutes": 42, "note": "2016 to 2017"},
            {"name": "Season 13", "episodes": 23, "minutes": 42, "note": "2017 to 2018"},
            {"name": "Season 14", "episodes": 20, "minutes": 42, "note": "2018 to 2019"},
            {"name": "Season 15", "episodes": 20, "minutes": 42, "note": "2019 to 2020"},
        ],
        "sections": [
            ("first-five", "The five-season version", [
                "The show's creator, Eric Kripke, planned a five-season story, and the season 5 finale, \"Swan Song\", "
                "was written as an ending. Seasons 1 to 5 are 104 episodes and about 73 hours.",
                "Plenty of viewers stop there and are happy. If you want a goal that feels finishable, untick seasons "
                "6 to 15 in the planner and aim for that first. You can always carry on.",
            ]),
            ("pace", "A pace for the whole thing", [
                "Two episodes a night takes 164 nights, about five and a half months. Three a night brings it under "
                "four months. Either way this is a long project, and the people who finish tend to treat it like a "
                "habit: same time most evenings, no guilt about a missed week.",
                "Roughly half of each season is monster-of-the-week episodes that stand alone. Fan guides list which "
                "ones the main plot needs, and skipping the rest can take a third off the total, though some of the "
                "best-loved comedy episodes are in that pile.",
            ]),
        ],
        "faq": [
            ("How many episodes of Supernatural are there?",
             "327 across fifteen seasons, which aired from 2005 to 2020."),
            ("How long does it take to watch the first five seasons of Supernatural?",
             "About 73 hours for 104 episodes. At two episodes a night that is 52 nights."),
            ("How long would Supernatural take watching every day?",
             "At two hours a day, about 115 days. At four hours a day, 58."),
        ],
    },
    "stranger-things": {
        "name": "Stranger Things", "kind": "tv", "reviewed": REVIEWED,
        "summary": "Stranger Things is 42 episodes over five seasons, about 45 hours, and the episodes keep getting longer. Season totals and a planner.",
        "titles": [{"kind": "tv", "title": "Stranger Things", "year": 2016}],
        "see_also": ["lost", "game-of-thrones", "breaking-bad"],
        "lead": [
            "Stranger Things finished at the end of 2025 with 42 episodes over five seasons. Added up from each "
            "episode's listed running time, the complete series is about 45 hours.",
            "The episode count hides how lopsided it is. Seasons 1 to 3 run between about seven and eight hours each. Season 4 is "
            "nearly 13 hours, almost twice the length of season 1, and ends with an episode of 2 hours 22 minutes. "
            "Season 5 is over ten hours for eight episodes. The last two seasons are more than half the total.",
        ],
        "parts": [
            {"name": "Season 1", "episodes": 8, "total": 405, "note": "2016"},
            {"name": "Season 2", "episodes": 9, "total": 467, "note": "2017"},
            {"name": "Season 3", "episodes": 8, "total": 449, "note": "2019"},
            {"name": "Season 4", "episodes": 9, "total": 773, "note": "2022. No episode is under an hour; the finale is 2 h 22 min."},
            {"name": "Season 5", "episodes": 8, "total": 620, "note": "2025. Released in three batches; the finale is just over two hours."},
        ],
        "sections": [
            ("pace", "A pace that works", [
                "For seasons 1 to 3, two episodes a night works and each season takes four or five nights. From season "
                "4 on, plan by the hour instead. Two episodes there can mean two and a half to three hours, and the "
                "last two episodes of season 4 together are nearly four.",
                "A sensible schedule is one early season per week, then a fortnight each for seasons 4 and 5. That is "
                "seven weeks with free evenings in every one of them.",
            ]),
            ("counting", "Why the planner uses minutes here", [
                "Most pages in this section multiply episodes by a typical length. That would be badly wrong for "
                "Stranger Things, where episodes range from 42 minutes to 142. The season totals above are sums of "
                "the running times listed for each episode, credits included.",
                "The animated spin-off and the stage play are not counted. Neither is needed to follow the series.",
            ]),
        ],
        "faq": [
            ("How many episodes of Stranger Things are there?",
             "42: eight in season 1, nine in season 2, eight in season 3, nine in season 4 and eight in season 5."),
            ("What is the longest episode of Stranger Things?",
             "The season 4 finale, \"The Piggyback\", at 2 hours 22 minutes. The series finale is the second longest, at just over two hours."),
            ("Can I watch Stranger Things in a week?",
             "Only at about six and a half hours a day. Two weeks at a little over three hours a day is more realistic."),
        ],
    },
    "succession": {
        "name": "Succession", "kind": "tv", "reviewed": REVIEWED,
        "summary": "Succession is 39 episodes over four seasons, about 41 hours. Season lengths, the 88-minute finale, and a plan for finishing it in a month.",
        "titles": [{"kind": "tv", "title": "Succession", "year": 2018}],
        "see_also": ["mad-men", "the-sopranos", "better-call-saul"],
        "lead": [
            "Succession is 39 episodes over four seasons: ten, ten, nine and ten. It is an HBO drama with no ad breaks, "
            "and episodes run about an hour, so the whole series takes about 41 hours.",
            "It is the shortest prestige drama in this section and the easiest to finish in a month. The final season "
            "is the longest, a little over eleven hours, and ends with an 88-minute finale.",
        ],
        "parts": [
            {"name": "Season 1", "episodes": 10, "total": 590, "note": "2018"},
            {"name": "Season 2", "episodes": 10, "total": 610, "note": "2019"},
            {"name": "Season 3", "episodes": 9, "total": 563, "note": "2021. One episode shorter because of pandemic production limits."},
            {"name": "Season 4", "episodes": 10, "total": 676, "note": "2023. Ends with an 88-minute finale."},
        ],
        "sections": [
            ("pace", "A pace that works", [
                "Ten episodes a week, two on each weeknight, finishes a season by Friday and the series in four weeks. "
                "One a night takes 39 nights, which is closer to how it aired and gives the dialogue room. A lot of the "
                "show is people saying the opposite of what they mean, and it is easy to miss at speed.",
                "Season 4 takes place over about ten days, with most episodes covering a single day. That makes it the "
                "one season worth watching quickly, ideally inside a week.",
            ]),
            ("slow-start", "Give it until episode 6", [
                "The first half of season 1 is the weakest stretch. The characters are unpleasant by design and the "
                "show has not yet found the comedy in that. It turns at about the midpoint of the season, which is "
                "roughly five hours in.",
                "There are no spin-offs, specials or films to add. The 39 episodes are the whole thing.",
            ]),
        ],
        "faq": [
            ("How many episodes of Succession are there?",
             "39: ten in season 1, ten in season 2, nine in season 3 and ten in season 4."),
            ("How long is the Succession finale?",
             "\"With Open Eyes\" runs 88 minutes, the longest episode of the series."),
            ("Can I finish Succession in a weekend?",
             "Not comfortably. It is about 41 hours, so even a three-day weekend would need more than 13 hours a day. "
             "A season per weekend, about ten hours, is doable."),
        ],
    },
}
