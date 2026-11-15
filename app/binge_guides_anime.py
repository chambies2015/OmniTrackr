"""Anime for the "how long does it take" guides (/binge-calculator/<slug>).

Episode counts are for the original Japanese broadcast, checked against TVmaze.
``minutes`` is a typical episode with its opening and ending. ``skip`` is how
many of a part's episodes fan filler lists mark as anime-only, for the guide's
"skip filler" switch.
"""

REVIEWED = "2026-11-10"
ONE_PIECE_EPISODES = 1180  # aired by 2026-11-10; the anime was between batches that week

GUIDES = {
    "fullmetal-alchemist-brotherhood": {
        "name": "Fullmetal Alchemist: Brotherhood", "kind": "anime", "reviewed": REVIEWED, "in_order": "fullmetal-alchemist",
        "summary": "Fullmetal Alchemist: Brotherhood is 64 episodes, about 26 hours. How long each part takes and how it differs from the 2003 series.",
        "titles": [{"kind": "anime", "title": "Fullmetal Alchemist: Brotherhood", "year": 2009,
                    "aka": ["Fullmetal Alchemist Brotherhood"]}],
        "see_also": ["hunter-x-hunter-2011", "death-note", "attack-on-titan"],
        "lead": [
            "Fullmetal Alchemist: Brotherhood is 64 episodes of about 24 minutes, which comes to a little under 26 "
            "hours. It ran as one continuous series from April 2009 to July 2010, with no seasons and no long breaks.",
            "It adapts the whole manga from the first chapter to the last, so there is nothing to read afterwards and "
            "almost nothing to skip. Home releases split it into five parts of twelve or thirteen episodes, which is "
            "the breakdown used below.",
        ],
        "parts": [
            {"name": "Part 1", "episodes": 13, "minutes": 24, "note": "Episodes 1 to 13"},
            {"name": "Part 2", "episodes": 13, "minutes": 24, "note": "Episodes 14 to 26"},
            {"name": "Part 3", "episodes": 13, "minutes": 24, "note": "Episodes 27 to 39"},
            {"name": "Part 4", "episodes": 13, "minutes": 24, "note": "Episodes 40 to 52"},
            {"name": "Part 5", "episodes": 12, "minutes": 24, "note": "Episodes 53 to 64"},
        ],
        "sections": [
            ("pace", "A pace that works", [
                "Four episodes a night is about an hour and a half and finishes the series in 16 nights. Each "
                "thirteen-episode part is then three or four evenings, which suits the story: the parts end at "
                "natural turning points.",
                "The first dozen episodes move very fast. They cover ground the 2003 series had already animated, and "
                "the studio assumed many viewers knew it. If the opening feels rushed, that is why, and it settles down "
                "once the story reaches new material around episode 14.",
            ]),
            ("versions", "Brotherhood and the 2003 series", [
                "There are two Fullmetal Alchemist anime. The 2003 series is 51 episodes and invents its own second "
                "half and ending, because the manga was unfinished at the time. Brotherhood is the later, complete "
                "adaptation. You do not need the first to watch the second.",
                "Not counted here: four short bonus episodes released on disc, and the 2011 film The Sacred Star of "
                "Milos, a stand-alone side story of about 110 minutes.",
            ]),
        ],
        "faq": [
            ("How many episodes of Fullmetal Alchemist: Brotherhood are there?",
             "64, shown weekly from April 2009 to July 2010 with no season breaks."),
            ("Do I need to watch the 2003 Fullmetal Alchemist first?",
             "No. Brotherhood starts the story again from the beginning and follows the manga to its ending."),
            ("Is there filler in Fullmetal Alchemist: Brotherhood?",
             "Almost none. Episode 27 is mostly a recap and can be skipped; everything else adapts the manga."),
        ],
    },
    "death-note": {
        "name": "Death Note", "kind": "anime", "reviewed": REVIEWED,
        "summary": "Death Note is 37 episodes, about 14 hours: short enough for a long weekend. See how its two halves split and plan your own pace.",
        "titles": [{"kind": "anime", "title": "Death Note", "year": 2006}],
        "see_also": ["cowboy-bebop", "fullmetal-alchemist-brotherhood", "attack-on-titan"],
        "lead": [
            "Death Note is 37 episodes of about 23 minutes, a little over 14 hours in total. It is one of the shortest "
            "complete series that regularly lands on lists of the best anime, and it is a common first one.",
            "The story has two halves. The first 25 episodes are the duel between Light and the detective L. The last "
            "12 jump ahead several years and bring in new opponents. Most viewers think the first half is stronger, "
            "but the series only has one ending and it is in episode 37.",
        ],
        "parts": [
            {"name": "Part 1: Light and L", "episodes": 25, "minutes": 23, "note": "Episodes 1 to 25"},
            {"name": "Part 2: Near and Mello", "episodes": 12, "minutes": 23, "note": "Episodes 26 to 37. Episode 26 is partly a recap."},
        ],
        "sections": [
            ("pace", "A pace that works", [
                "At four hours a day Death Note takes four days, which makes it a realistic long-weekend watch. At a "
                "calmer three episodes a night it takes 13 nights.",
                "It is a show of plans inside plans, and episodes end on reveals, so it is harder than most to stop "
                "watching mid-arc. A natural break comes after episode 25. If you need a pause, take it there.",
            ]),
            ("not-counted", "What the total leaves out", [
                "Two feature-length \"Relight\" specials retell the series in condensed form with a few new scenes. They "
                "are recaps of between an hour and a half and two hours, and you do not need them after watching the episodes.",
                "The Japanese live-action films, the 2015 drama and the 2017 Netflix film are separate adaptations of "
                "the same manga and are not counted.",
            ]),
        ],
        "faq": [
            ("How many episodes of Death Note are there?",
             "37, in a single season that aired from October 2006 to June 2007."),
            ("Can I watch Death Note in a weekend?",
             "Just about. It is a little over 14 hours, so about seven hours on each of two days, or under five hours a day across a three-day weekend."),
            ("Does the Death Note anime cover the whole manga?",
             "Yes. It adapts all 108 chapters, though the second half is compressed and the final scene differs from the manga's."),
        ],
    },
    "cowboy-bebop": {
        "name": "Cowboy Bebop", "kind": "anime", "reviewed": REVIEWED,
        "summary": "Cowboy Bebop is 26 episodes, about 10 and a half hours, plus an optional two-hour film. Where the film fits and how to pace the series.",
        "titles": [{"kind": "anime", "title": "Cowboy Bebop", "year": 1998}],
        "see_also": ["death-note", "fullmetal-alchemist-brotherhood", "hunter-x-hunter-2011"],
        "lead": [
            "Cowboy Bebop is 26 episodes, which the show calls sessions, at about 24 minutes each. The series takes "
            "roughly ten and a half hours. The 2001 film adds just under two more.",
            "Most sessions are self-contained: a bounty, a chase, a different genre each week. Only a handful carry "
            "the main story of Spike's past, and they are spread from session 5 to the two-part finale. That makes "
            "Bebop unusually easy to watch a little at a time.",
        ],
        "parts": [
            {"name": "Sessions 1 to 13", "episodes": 13, "minutes": 24, "note": "Ends with the two-part \"Jupiter Jazz\"."},
            {"name": "Sessions 14 to 26", "episodes": 13, "minutes": 24, "note": "Ends with the two-part \"The Real Folk Blues\"."},
            {"name": "Cowboy Bebop: The Movie", "episodes": 1, "total": 115, "optional": True, "unit": "film",
             "note": "2001. Set between sessions 22 and 23."},
        ],
        "sections": [
            ("pace", "A pace that works", [
                "Two sessions a night finishes the series in 13 nights, and nothing is lost by taking longer. Because "
                "the episodes stand alone, this is a good series for a busy month: one session fits in a lunch break.",
                "Watch in broadcast order all the same. The crew joins the ship one at a time over the first nine "
                "sessions, and the last three only work if you have spent the full run with them.",
            ]),
            ("film", "Where the film fits", [
                "Cowboy Bebop: The Movie (also released as Knockin' on Heaven's Door) is a 115-minute stand-alone case "
                "set late in the series, between sessions 22 and 23. You can watch it there or after the finale. "
                "It is left out of the default total and you can tick it in the planner.",
                "The 2021 Netflix live-action series is a separate ten-episode remake and is not counted.",
            ]),
        ],
        "faq": [
            ("How many episodes of Cowboy Bebop are there?",
             "26 sessions, first shown in Japan in 1998 and 1999, plus one film from 2001."),
            ("Do I have to watch every episode of Cowboy Bebop?",
             "The stand-alone sessions are most of what people love about it, so yes. If you only want Spike's story, "
             "it runs through sessions 5, 12, 13, 25 and 26."),
            ("How long is the Cowboy Bebop movie?",
             "115 minutes. With the film, the whole of Cowboy Bebop is about 12 hours 20 minutes."),
        ],
    },
    "hunter-x-hunter-2011": {
        "name": "Hunter x Hunter (2011)", "kind": "anime", "reviewed": REVIEWED,
        "summary": "Hunter x Hunter (2011) is 148 episodes, about 57 hours. Arc-by-arc lengths, including the 61-episode Chimera Ant arc, and a planner.",
        "titles": [{"kind": "anime", "title": "Hunter x Hunter", "year": 2011, "aka": ["Hunter x Hunter (2011)", "Hunter × Hunter"]}],
        "see_also": ["fullmetal-alchemist-brotherhood", "naruto-and-shippuden", "one-piece"],
        "lead": [
            "The 2011 Hunter x Hunter anime is 148 episodes of about 23 minutes, close to 57 hours. It ran weekly "
            "from October 2011 to September 2014 with no filler arcs, which is rare for a show of its length.",
            "It is built from seven arcs of very different sizes. The shortest is five episodes. The Chimera Ant arc "
            "is 61, about 23 hours on its own and two fifths of the whole series, so most of a plan for this show is "
            "really a plan for that arc.",
        ],
        "parts": [
            {"name": "Hunter Exam", "episodes": 21, "minutes": 23, "note": "Episodes 1 to 21"},
            {"name": "Zoldyck Family", "episodes": 5, "minutes": 23, "note": "Episodes 22 to 26"},
            {"name": "Heavens Arena", "episodes": 10, "minutes": 23, "note": "Episodes 27 to 36"},
            {"name": "Yorknew City", "episodes": 22, "minutes": 23, "note": "Episodes 37 to 58"},
            {"name": "Greed Island", "episodes": 17, "minutes": 23, "note": "Episodes 59 to 75"},
            {"name": "Chimera Ant", "episodes": 61, "minutes": 23, "note": "Episodes 76 to 136"},
            {"name": "13th Hunter Chairman Election", "episodes": 12, "minutes": 23, "note": "Episodes 137 to 148"},
        ],
        "sections": [
            ("pace", "A pace that works", [
                "Four episodes a night finishes the series in 37 nights. The early arcs are short enough to clear in a "
                "few evenings each, and each one changes the setting and the rules, so the show keeps feeling new.",
                "The Chimera Ant arc starts slowly, with a narrator and a new cast, and it loses some viewers in its "
                "first ten episodes. It is also the part most fans rank highest once it is over. If you stall there, "
                "set a small target of three episodes a night for a week and see where you are.",
            ]),
            ("ending", "Where the anime stops", [
                "Episode 148 is a proper stopping point, and one of the better endings a long anime has managed, but "
                "the manga continues past it. The later Dark Continent material has not been animated.",
                "The 1999 series is an older adaptation of the first few arcs and is not counted. The two 2013 films, "
                "Phantom Rouge and The Last Mission, are side stories outside the manga. Episodes 13 and 26 are "
                "recaps and can be skipped.",
            ]),
        ],
        "faq": [
            ("How many episodes of Hunter x Hunter are there?",
             "The 2011 series has 148. The older 1999 series has 62 plus three short follow-up series released on video."),
            ("How long is the Chimera Ant arc?",
             "61 episodes, numbers 76 to 136. That is about 23 hours, more than the first three arcs put together."),
            ("Does Hunter x Hunter have filler?",
             "The 2011 series has no filler arcs. Two episodes, 13 and 26, are recaps."),
        ],
    },
    "dragon-ball-z": {
        "name": "Dragon Ball Z", "kind": "anime", "reviewed": REVIEWED, "in_order": "dragon-ball",
        "summary": "Dragon Ball Z is 291 episodes, about 116 hours. Saga-by-saga lengths, how much shorter Dragon Ball Z Kai is, and a pace planner.",
        "titles": [{"kind": "anime", "title": "Dragon Ball Z", "year": 1989}],
        "see_also": ["naruto-and-shippuden", "one-piece", "hunter-x-hunter-2011"],
        "lead": [
            "Dragon Ball Z is 291 episodes in its original Japanese run, which aired from 1989 to 1996. At about 24 "
            "minutes each that is roughly 116 hours, a little under five days of continuous watching.",
            "It was made weekly alongside the manga, and when the anime caught up it stretched: fights run for many "
            "episodes, and whole side plots were added to buy time. That padding is why Dragon Ball Z Kai exists. "
            "Kai is a re-edit of the same footage that tells the story in 167 episodes.",
        ],
        "parts": [
            {"name": "Season 1: Saiyan saga", "episodes": 39, "minutes": 24, "note": "Episodes 1 to 39"},
            {"name": "Season 2: Namek and Captain Ginyu", "episodes": 35, "minutes": 24, "note": "Episodes 40 to 74"},
            {"name": "Season 3: Frieza", "episodes": 33, "minutes": 24, "note": "Episodes 75 to 107"},
            {"name": "Season 4: Garlic Jr., Trunks and the Androids", "episodes": 32, "minutes": 24,
             "note": "Episodes 108 to 139. The ten Garlic Jr. episodes are not in the manga."},
            {"name": "Season 5: Imperfect and Perfect Cell", "episodes": 26, "minutes": 24, "note": "Episodes 140 to 165"},
            {"name": "Season 6: Cell Games", "episodes": 29, "minutes": 24, "note": "Episodes 166 to 194"},
            {"name": "Season 7: Great Saiyaman and World Tournament", "episodes": 25, "minutes": 24, "note": "Episodes 195 to 219"},
            {"name": "Season 8: Babidi and Majin Buu", "episodes": 34, "minutes": 24, "note": "Episodes 220 to 253"},
            {"name": "Season 9: Fusion and Kid Buu", "episodes": 38, "minutes": 24, "note": "Episodes 254 to 291"},
        ],
        "sections": [
            ("kai", "Dragon Ball Z or Kai", [
                "Kai cuts the anime-only material and tightens the fights. Its international version is 167 episodes, "
                "about 64 hours at 23 minutes each, so it saves roughly 52 hours. If you want the story, Kai is the "
                "efficient choice. If you grew up on the original and want the music and the pacing you remember, "
                "the 291-episode run is the one.",
                "The nine seasons above follow the way the uncut series is sold on disc and on most streaming "
                "services. The first English TV broadcast cut and merged early episodes, which is why older guides "
                "give a total of 276.",
            ]),
            ("pace", "A pace that works", [
                "Five episodes a night is two hours and finishes the series in 59 nights. One disc season a week "
                "takes nine weeks, which is about the same, and gives you a clear target every Sunday.",
                "The Frieza fight is the famous slow patch: the planet has five minutes to live for about ten "
                "episodes. It is fine to watch that stretch with one eye. The original Dragon Ball (153 episodes) "
                "comes first in the story, and Dragon Ball Z's films and TV specials are not counted here.",
            ]),
        ],
        "faq": [
            ("How many episodes of Dragon Ball Z are there?",
             "291 in the original Japanese run. The first English broadcast edited that down to 276."),
            ("How long is Dragon Ball Z Kai?",
             "167 episodes in the international version, about 64 hours. In Japan it aired as 159 episodes."),
            ("Do I need to watch Dragon Ball before Dragon Ball Z?",
             "It helps but is not required. Z opens five years after Dragon Ball ends and reintroduces the main "
             "characters. The original series is 153 episodes, about 61 hours."),
        ],
    },
    "naruto-and-shippuden": {
        "name": "Naruto and Naruto Shippuden", "kind": "anime", "reviewed": REVIEWED,
        "summary": "Naruto and Naruto Shippuden are 720 episodes, about 276 hours, or about 163 hours without filler. Plan either version at your own pace.",
        "titles": [{"kind": "anime", "title": "Naruto", "year": 2002},
                   {"kind": "anime", "title": "Naruto Shippuden", "year": 2007,
                    "aka": ["Naruto: Shippuden", "Naruto Shippūden", "Naruto: Shippūden"]}],
        "alt": {"label": "Skip filler", "summary": "without filler",
                "note": "Takes out the episodes fan filler lists mark as anime-only: about 90 in Naruto and 205 in Shippuden."},
        "see_also": ["one-piece", "dragon-ball-z", "hunter-x-hunter-2011"],
        "lead": [
            "Naruto is 220 episodes and its sequel, Naruto Shippuden, is 500. Together that is 720 episodes of about "
            "23 minutes, or roughly 276 hours: eleven and a half days without a break.",
            "A large share of that is filler, meaning stories the anime invented while it waited for the manga. Fan "
            "filler lists mark about 90 episodes of Naruto and 205 of Shippuden as anime-only, around 41 percent of "
            "each. Skip them and the total drops to 425 episodes and about 163 hours.",
        ],
        "parts": [
            {"name": "Naruto", "episodes": 220, "minutes": 23, "skip": 90,
             "note": "2002 to 2007. Episodes 136 to 219 are one long run of filler."},
            {"name": "Naruto Shippuden", "episodes": 500, "minutes": 23, "skip": 205,
             "note": "2007 to 2017. Filler arcs are spread throughout."},
            {"name": "The Last: Naruto the Movie", "episodes": 1, "total": 112, "optional": True, "unit": "film",
             "note": "2014. Part of the main story, set before the final episodes of Shippuden."},
        ],
        "sections": [
            ("filler", "How to handle the filler", [
                "In the first series it is simple. The story runs to episode 135, and nearly everything from 136 to "
                "219 is filler. Many viewers stop at 135, watch episode 220, and go straight to Shippuden. That alone "
                "saves about 32 hours.",
                "Shippuden is harder, because the filler comes in blocks of ten to twenty episodes between story arcs, "
                "and flashback episodes are mixed into the final war. Keep a filler list open in another tab and check "
                "it at the start of each arc. Some filler is well liked, so skipping it all is a choice and you can "
                "always go back.",
            ]),
            ("pace", "A pace that works", [
                "Without filler, five episodes a night is under two hours and takes 85 nights, a little under three "
                "months. With everything included, the same pace takes 144 nights, close to five months.",
                "The Last: Naruto the Movie is canon and worth adding near the end. Boruto, the sequel series about "
                "the next generation, is not counted.",
            ]),
        ],
        "faq": [
            ("How many episodes of Naruto are there in total?",
             "720: 220 in Naruto and 500 in Naruto Shippuden."),
            ("How long does Naruto take without filler?",
             "About 425 episodes and 163 hours, against 276 hours with everything included."),
            ("Can I skip the original Naruto and start with Shippuden?",
             "It is not a good idea. Shippuden picks up two and a half years later and depends on relationships set "
             "up in the first series. Watch at least episodes 1 to 135."),
        ],
    },
    "attack-on-titan": {
        "name": "Attack on Titan", "kind": "anime", "reviewed": REVIEWED,
        "summary": "Attack on Titan is 87 episodes and two feature-length finale specials, about 37 hours. Season lengths and how the Final Season is split.",
        "titles": [{"kind": "anime", "title": "Attack on Titan", "year": 2013, "aka": ["Shingeki no Kyojin"]}],
        "see_also": ["fullmetal-alchemist-brotherhood", "death-note", "hunter-x-hunter-2011"],
        "lead": [
            "Attack on Titan is 87 regular episodes and two long specials that close the story. Episodes run about 24 "
            "minutes and the specials together run nearly two and a half hours, so the complete series takes about 37 "
            "hours.",
            "The numbering is the confusing part. There are four seasons, but the fourth, called The Final Season, was "
            "released in four pieces over three years: Part 1, Part 2, and then The Final Chapters as two specials. "
            "They are all listed below so you can see where you are.",
        ],
        "parts": [
            {"name": "Season 1", "episodes": 25, "minutes": 24, "note": "2013"},
            {"name": "Season 2", "episodes": 12, "minutes": 24, "note": "2017"},
            {"name": "Season 3", "episodes": 22, "minutes": 24, "note": "2018 and 2019, in two halves of 12 and 10."},
            {"name": "The Final Season Part 1", "episodes": 16, "minutes": 24, "note": "2020 to 2021"},
            {"name": "The Final Season Part 2", "episodes": 12, "minutes": 24, "note": "2022"},
            {"name": "The Final Chapters", "episodes": 2, "total": 146, "unit": "special",
             "note": "2023. Two specials, about 61 and 85 minutes."},
        ],
        "sections": [
            ("pace", "A pace that works", [
                "Four episodes a night is a little over an hour and a half and gets through the regular episodes in 22 "
                "nights. Add two evenings for the specials and the whole series fits in under four weeks.",
                "Season 1 is the longest and the most traditional. From the second half of season 3 the show becomes a "
                "different kind of story, more political and much darker, and it is best watched without long gaps. A "
                "lot of what happens depends on remembering who knew what and when.",
            ]),
            ("counting", "Why episode counts differ", [
                "The two Final Chapters specials were broadcast as feature-length episodes. Some streaming services "
                "cut them into regular-length episodes, so you will see totals higher than 89 for exactly the same "
                "footage.",
                "Not counted: the eight bonus episodes released with manga volumes, the recap films, and the parody "
                "series Attack on Titan: Junior High. None of them are needed for the story.",
            ]),
        ],
        "faq": [
            ("How many episodes of Attack on Titan are there?",
             "89 as broadcast: 87 regular episodes plus two feature-length specials. Services that split the specials list more."),
            ("How long is the Attack on Titan finale?",
             "The Final Chapters are two specials of about 61 and 85 minutes, roughly two hours 26 minutes together."),
            ("Does the anime finish the story?",
             "Yes. The Final Chapters adapt the last chapters of the manga, which ended in 2021."),
        ],
    },
    "one-piece": {
        "name": "One Piece", "kind": "anime", "reviewed": REVIEWED, "ongoing": True,
        "summary": "One Piece has 1,180 episodes as of November 2026, about 472 hours. Saga-by-saga lengths and a planner for catching up from any point.",
        "titles": [{"kind": "anime", "title": "One Piece", "year": 1999}],
        "see_also": ["naruto-and-shippuden", "dragon-ball-z", "hunter-x-hunter-2011"],
        "lead": [
            "One Piece has aired 1,180 episodes as of November 2026 and is still going. At about 24 minutes each that "
            "is roughly 472 hours, or close to 20 days of continuous watching. No other series in this section comes "
            "near it.",
            "The good news for anyone catching up is that the gap has stopped growing so quickly. One Piece aired "
            "almost every week from 1999 to 2025. Since April 2026 it has moved to a seasonal schedule of about 26 "
            "episodes a year, so a steady viewer now gains on it much faster than before.",
        ],
        "parts": [
            {"name": "East Blue", "episodes": 61, "minutes": 24, "note": "Episodes 1 to 61"},
            {"name": "Alabasta", "episodes": 74, "minutes": 24, "note": "Episodes 62 to 135"},
            {"name": "Sky Island", "episodes": 71, "minutes": 24, "note": "Episodes 136 to 206"},
            {"name": "Water 7", "episodes": 119, "minutes": 24, "note": "Episodes 207 to 325. Includes Enies Lobby."},
            {"name": "Thriller Bark", "episodes": 59, "minutes": 24, "note": "Episodes 326 to 384"},
            {"name": "Summit War", "episodes": 132, "minutes": 24, "note": "Episodes 385 to 516. Includes Marineford."},
            {"name": "Fish-Man Island", "episodes": 58, "minutes": 24, "note": "Episodes 517 to 574"},
            {"name": "Dressrosa", "episodes": 172, "minutes": 24, "note": "Episodes 575 to 746. Includes Punk Hazard."},
            {"name": "Whole Cake Island", "episodes": 143, "minutes": 24, "note": "Episodes 747 to 889. Includes Zou."},
            {"name": "Wano Country", "episodes": 196, "minutes": 24, "note": "Episodes 890 to 1085"},
            {"name": "Final saga so far", "episodes": ONE_PIECE_EPISODES - 1085, "minutes": 24,
             "note": "Episodes 1086 onward: Egghead, then Elbaf from April 2026."},
        ],
        "sections": [
            ("pace", "What catching up really takes", [
                "At two hours a day, which is five episodes, the current run takes 236 days: about eight months. At "
                "one hour a day it is well over a year. Three hours a day brings it down to 158 days, a little over "
                "five months.",
                "Those numbers look impossible until you break them down by saga. East Blue is a two-week job at five "
                "episodes a night. Use the list below to tick off the sagas you have finished and the planner will "
                "show only what is left.",
            ]),
            ("shorter", "Ways to shorten it", [
                "Skipping openings, recaps and previews saves more here than anywhere else. From the middle of the "
                "series onward, episodes often open with several minutes of recap. The skip box in the planner takes "
                "three minutes off each episode, which is 59 hours across the whole run, and in later sagas the real "
                "saving is larger.",
                "Fan filler lists mark fewer than one episode in ten as filler, far less than Naruto, so there is no "
                "big block to cut. The films are side stories and are not counted, and neither is the Netflix "
                "live-action series.",
            ]),
        ],
        "faq": [
            ("How many episodes of One Piece are there?",
             "1,180 had aired by November 10, 2026. The count goes up by about 26 a year on the current seasonal schedule."),
            ("How long would it take to watch all of One Piece?",
             "About 472 hours. That is 236 days at two hours a day, or just under 20 days with no breaks at all."),
            ("Where should I start One Piece?",
             "At episode 1. The story is one continuous voyage, and later sagas pay off details from the very first arc."),
        ],
    },
}
