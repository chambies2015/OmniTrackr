"""The writing for the December advent calendar (/holidays/advent-calendar), one edition per year.

Each door opens on its own day in December and holds one hand-picked title. Across
the 24 doors every format OmniTrackr tracks appears at least twice. The days are
planned around the calendar: short picks on weekday evenings, longer ones on
weekends, the longest night on the solstice and an old favorite on Christmas Eve.

Door fields:
    day      1 to 24, the day of December the door opens
    kind     movie | tv | anime | game | book | album | manga | podcast | audiobook
    hint     the line on the closed door; never names the title
    time     what it asks of you, in plain words
    why      why it is behind this door on this day
    note     how to approach it
    caveat   what to know first (content, pace, availability)

No door repeats a pick from the holiday hub, the guides beside it or the December
Discover edition (tests/test_advent_calendar.py checks this).
"""

EDITIONS = {
    2026: {
        "published": "2026-12-01",
        "reviewed": "2026-11-14",
        "search_title": "The 2026 advent calendar: 24 picks for December, one door a day",
        "headline": "The December advent calendar",
        "deck": ("Twenty-four doors, one a day from December 1 to Christmas Eve. Behind each is one film, show, anime, "
                 "game, book, album, manga, podcast or audiobook, picked for that day of the month and written up "
                 "with how long it takes and what to know first."),
        "summary": ("An advent calendar of 24 picks for December 2026, one door a day: films, TV, anime, games, books, "
                    "albums, manga, podcasts and audiobooks, each with why it suits that day, how long it takes and a caveat."),
        "card": "A new pick behind a new door every day from December 1 to 24.",
        "intro": [
            "An advent calendar is a small thing to look forward to every morning in December. Ours has 24 doors, and "
            "each one holds a title we think suits that particular day. Weekday doors hold things that fit into an "
            "evening, such as a podcast for the commute, a one-hour film or a short album. The weekend doors hold "
            "longer things: a game for a Saturday afternoon, a novel you can finish on a Sunday, a film for the "
            "Friday when the office party is over.",
            "The doors follow the month. December 21 is the longest night of the year in the northern hemisphere, so "
            "that door holds a novel set on a planet where it is always winter. December 23 is one of the busiest "
            "travel days of the year, so that door holds a long audiobook for the drive. Christmas Eve gets the film "
            "that American television has been showing on Christmas Eve for decades.",
            "Every format OmniTrackr tracks is in here at least twice, and none of the 24 picks repeat the holiday "
            "hub, the reading and listening guide or the Thanksgiving guide. If you miss a day, the door stays open. "
            "You can catch up on the whole month at any point, and nothing is taken away on December 25.",
        ],
        "how": [
            ("One door a day", "A door opens at midnight on its date. Opened doors stay open, so you can start on "
             "December 10 and go back through the first nine."),
            ("Save what you like", "Each door has an add button. Members get the title in their library as not "
             "started, and visitors can keep a list in their browser that moves into a free library at sign-up."),
            ("A reminder, if you want one", "Members with notifications on can ask for one buzz a morning when the "
             "new door opens. It never names the pick, so the door still has something behind it."),
            ("A badge for the whole month", "Open six doors for the bronze Door Opener badge, twelve for silver and "
             "all twenty-four for gold."),
        ],
        "doors": [
            {
                "day": 1, "kind": "manga", "title": "Yotsuba&!", "year": 2003, "creator": "Kiyohiko Azuma",
                "hint": "Something to read a chapter at a time all month",
                "time": "About 15 minutes a chapter",
                "why": ("The first door should hold something you can come back to on every other day of the month, "
                        "and Yotsuba&! is built for that. Each chapter is roughly one day in the life of Yotsuba, a "
                        "five-year-old who has just moved to a new town with her adoptive father and treats every "
                        "swing, cicada and doorbell as the most interesting thing that has ever happened. "
                        "Nothing much is at stake, and the jokes come from how seriously she takes all of it."),
                "note": ("Read one chapter with your morning coffee and stop there. Azuma draws ordinary places in "
                         "careful detail, so the panels reward a slow look. The English edition is published by Yen Press."),
                "caveat": ("The series is still running and new volumes arrive years apart, so you will not reach an ending. "
                           "That is fine here: no chapter needs one."),
            },
            {
                "day": 2, "kind": "podcast", "title": "Song Exploder", "year": 2014, "creator": "Hrishikesh Hirway",
                "hint": "Twenty minutes for the commute",
                "time": "15 to 30 minutes an episode",
                "why": ("In each episode a musician takes one of their own songs apart, track by track, and explains "
                        "how it was made: the demo on a phone, the drum part that was nearly cut, the lyric that came "
                        "last. Hirway edits himself out, so you only hear the artist and the separated parts of the song. "
                        "It fits into a Wednesday commute and leaves you hearing a familiar record differently."),
                "note": ("Start with a song you already know well, then play it straight after the episode. The archive "
                         "is long and covers pop, film scores, hip-hop and rock, so scroll for names you like."),
                "caveat": ("Episodes play the songs, which sometimes have explicit lyrics. A Netflix series of the same "
                           "name exists, but the podcast is the place to start."),
            },
            {
                "day": 3, "kind": "anime", "title": "Look Back", "year": 2024, "creator": "Kiyotaka Oshiyama",
                "hint": "One hour, on a school night",
                "time": "58 minutes",
                "why": ("A feature-length anime that is shorter than most television episodes with ads. Fujino is the "
                        "best artist in her class until a girl who never comes to school starts sending in comics for "
                        "the school paper. The two end up drawing manga together for years. The film follows them "
                        "through long walks home and longer nights at the desk, and it is about why people make things, "
                        "and what it costs."),
                "note": ("Watch it with the lights low and leave a few minutes after the credits before you pick up your "
                         "phone. It is adapted from a one-shot by Tatsuki Fujimoto, who wrote Chainsaw Man."),
                "caveat": ("There is a sudden act of violence in the second half and the film deals with grief. It is not "
                           "gory, but it lands hard, and it is not one for young children."),
            },
            {
                "day": 4, "kind": "movie", "title": "Klaus", "year": 2019, "creator": "Sergio Pablos",
                "hint": "The first Friday film of December",
                "time": "1 hour 36 minutes",
                "why": ("The first Friday in December is a good night to start the Christmas films, and Klaus is a newer "
                        "one that already plays like a classic. A spoiled postal cadet is sent to a frozen island town "
                        "where two families have feuded for generations, and he needs six thousand letters to earn his "
                        "way home. A reclusive toymaker turns out to be the answer. It is hand-drawn animation lit to "
                        "look almost three-dimensional, and it was nominated for the Academy Award and won the BAFTA "
                        "for animated film."),
                "note": ("This one works with any age in the room. The first half is mostly slapstick, and the warmth "
                         "builds slowly, so give it twenty minutes before deciding."),
                "caveat": ("It is a Netflix film and streams only there. The ending is sentimental by design, and "
                           "younger children may need a hand through one sad scene near the end."),
            },
            {
                "day": 5, "kind": "game", "title": "A Short Hike", "year": 2019, "creator": "adamgryu",
                "hint": "A Saturday afternoon, start to finish",
                "time": "About 2 hours",
                "why": ("Claire, a young bird, is spending the summer at her aunt's cabin in a provincial park and needs "
                        "phone signal. The only place to get it is the top of the mountain. You can climb straight "
                        "there in an hour, or spend three wandering off to fish, race other hikers and dig up buried "
                        "treasure. It won the top prize at the Independent Games Festival in 2020, and it is the right "
                        "size for the first Saturday of the month, before the weekends fill up."),
                "note": ("Talk to everyone and pick up the golden feathers, which let you climb higher. A controller is "
                         "the comfortable way to play on a computer. There is no way to fail."),
                "caveat": ("The pixel art is deliberately low resolution. If you want snow on screen, it arrives near "
                           "the summit."),
            },
            {
                "day": 6, "kind": "book", "title": "Moominland Midwinter", "year": 1957, "creator": "Tove Jansson",
                "hint": "A short book for a slow Sunday",
                "time": "About 3 hours",
                "why": ("Moomins sleep through the winter. In this one Moomintroll wakes up in January, alone, while "
                        "everyone else in the house is still asleep, and has to work out what winter is. He meets "
                        "creatures who only come out in the cold, including Too-ticky, who lives in the bathing hut, "
                        "and he learns to like a world that does not care about him much. It is one of the best books "
                        "anyone has written about the dark half of the year, and it is short enough for one Sunday."),
                "note": ("It reads well aloud, a chapter a night, if there are children in the house. It also stands on "
                         "its own for adults, and you do not need the earlier Moomin books first."),
                "caveat": ("It is quieter and stranger than the cartoon Moomins, and some of the winter creatures are a "
                           "little frightening for small children."),
            },
            {
                "day": 7, "kind": "album", "title": "Blue", "year": 1971, "creator": "Joni Mitchell",
                "hint": "Thirty-six minutes for a Monday night",
                "time": "36 minutes",
                "why": ("Blue is not a Christmas album, but it has the best December song on any record that isn't one. "
                        "\"River\" opens with a sad piano version of \"Jingle Bells\" and the line \"It's coming on "
                        "Christmas, they're cutting down trees.\" The rest of the album is ten songs of Mitchell on "
                        "guitar, piano and dulcimer, very close to the microphone. Rolling Stone put it third on its "
                        "2020 list of the greatest albums ever made."),
                "note": ("Play it from the first track to the last with nothing else on. A Monday evening in early "
                         "December, after the first week of parties, is about right."),
                "caveat": ("It is a breakup record and some of it is raw. If you need cheering up, save it for later in "
                           "the week."),
            },
            {
                "day": 8, "kind": "tv", "title": "Detectorists", "year": 2014, "creator": "Mackenzie Crook",
                "hint": "Half an hour of comedy, as many nights as you like",
                "time": "Three series of six half-hour episodes, plus two specials",
                "why": ("Andy and Lance spend their weekends in fields in rural England with metal detectors, hoping for "
                        "Saxon gold and mostly finding ring pulls. Mackenzie Crook wrote and directed it and plays Andy, "
                        "with Toby Jones as Lance. It is a comedy about friendship and getting older, very funny and "
                        "very gentle, and the English countryside looks lovely in it. It ends with a feature-length "
                        "Christmas special from 2022."),
                "note": ("Watch an episode a night, and you can save the 2022 special for Christmas week. The theme song, "
                         "by Johnny Flynn, is worth letting play."),
                "caveat": ("Where it streams depends on your country. Some of the humor is very British and very dry, "
                           "and it can take an episode or two to settle in."),
            },
            {
                "day": 9, "kind": "podcast", "title": "The Memory Palace", "year": 2008, "creator": "Nate DiMeo",
                "hint": "Ten minutes of history for the walk home",
                "time": "Usually 10 to 20 minutes an episode",
                "why": ("Nate DiMeo tells short stories from the past, mostly American and mostly about people the "
                        "history books skipped."
                        " Each episode is written and read like a short essay, with music underneath. "
                        "They are some of the most carefully written minutes in podcasting, and you can hear two in the "
                        "time it takes to walk home on a dark December evening."),
                "note": ("Any episode is a fine place to start, as they are all self-contained. If you like one, the "
                         "archive runs back more than fifteen years."),
                "caveat": ("Some stories are sad, and DiMeo is open about filling gaps in the record with his imagination. "
                           "It is history told like literature."),
            },
            {
                "day": 10, "kind": "anime", "title": "Laid-Back Camp", "year": 2018, "creator": "C-Station",
                "hint": "Winter outdoors, from the sofa",
                "time": "12 episodes of 24 minutes",
                "why": ("Rin likes to camp alone in winter, when the campsites around Mount Fuji are empty. Nadeshiko has "
                        "just moved to the area and falls asleep at the wrong campsite. They become friends over a "
                        "bowl of instant noodles. The show is about cold air, warm food and the right sleeping bag, and "
                        "it makes winter look like something to go out and enjoy. Little happens, and that is the "
                        "pleasure of it."),
                "note": ("Two or three episodes is a nice evening, and there is a season two, a film and a season three "
                         "if you get attached. Expect to want a camping stove by the end."),
                "caveat": ("There is almost no plot. People who need a story pulling them forward may find it too slow."),
            },
            {
                "day": 11, "kind": "game", "title": "Balatro", "year": 2024, "creator": "LocalThunk",
                "hint": "A Friday night of one more round",
                "time": "30 to 60 minutes a run, as many runs as you allow",
                "why": ("Balatro starts with poker hands you already know, pairs and flushes and full houses, and then "
                        "lets you break the rules with joker cards that multiply your score in ways that should not be "
                        "allowed. Each run takes half an hour or so, and each one ends with you knowing how to do "
                        "better. It won three awards at The Game Awards in 2024, including best independent game, and "
                        "it runs on almost everything, including phones."),
                "note": ("Play the first few runs without looking anything up. Working out which jokers combine is most "
                         "of the fun. Set an alarm if you have plans on Saturday morning."),
                "caveat": ("It uses the look of a casino, but there is no gambling, no real money and nothing to buy "
                           "after the price of the game. It is a game for one."),
            },
            {
                "day": 12, "kind": "movie", "title": "The Holdovers", "year": 2023, "creator": "Alexander Payne",
                "hint": "A Christmas film for grown-ups, on a Saturday",
                "time": "2 hours 13 minutes",
                "why": ("A New England boarding school, Christmas 1970. A strict classics teacher is stuck minding the "
                        "five boys who can't go home for the holidays, and soon only one is left, along with the "
                        "school's head cook, whose son has just been killed in Vietnam. Paul Giamatti, Dominic Sessa and "
                        "Da'Vine Joy Randolph make three lonely people into a family for two weeks. Randolph won the "
                        "Academy Award for it. It is funny, it is sad, and it is shot to look like a film from 1970."),
                "note": ("Save it for an evening without children around and give it the full two hours. Mid-December is "
                         "right, when term is ending and the snow is coming."),
                "caveat": ("It is rated R for language and some drug use. The grief in it is real, though the film is "
                           "warmer than it sounds."),
            },
            {
                "day": 13, "kind": "book", "title": "Small Things Like These", "year": 2021, "creator": "Claire Keegan",
                "hint": "A whole novel in one sitting",
                "time": "About 2 hours",
                "why": ("New Ross, Ireland, in the weeks before Christmas 1985. Bill Furlong sells coal and timber, and "
                        "while delivering to the convent he sees something he cannot stop thinking about. Claire Keegan "
                        "tells it in barely more than a hundred pages, with no wasted word. It was shortlisted for the "
                        "Booker Prize in 2022, one of the shortest books ever to make that list, and it is a December "
                        "book in every scene: the cold, the coal orders, the Christmas cake."),
                "note": ("Read it in one sitting on a Sunday afternoon, then give it a day before talking about it. There "
                         "is a 2024 film with Cillian Murphy, but read the book first."),
                "caveat": ("It is about Ireland's Magdalene laundries, where unmarried mothers and girls were confined and "
                           "worked. Nothing is graphic, but it is a hard subject."),
            },
            {
                "day": 14, "kind": "manga", "title": "Mushishi", "year": 1999, "creator": "Yuki Urushibara",
                "hint": "One quiet story at a time",
                "time": "One self-contained story, about 40 minutes",
                "why": ("Ginko travels through a Japan of mountains and villages, helping people troubled by mushi, "
                        "small strange forms of life that most people can't see. Each chapter is its own story, like a "
                        "folk tale, and some of them are set in deep snow. The art is soft and ink-washed. "
                        "It ran for ten volumes, and it is good for the middle of December, when you want something calm "
                        "that asks nothing of you."),
                "note": ("Read one story and stop. They are better with a gap between them. The 2005 anime is also very "
                         "good if you would rather watch."),
                "caveat": ("Some stories end sadly, and Ginko does not always save anyone. The pace is slow by design."),
            },
            {
                "day": 15, "kind": "audiobook", "title": "Holidays on Ice", "year": 1997, "creator": "David Sedaris",
                "hint": "Something to listen to while wrapping presents",
                "time": "A few hours, depending on the edition",
                "why": ("A collection of Christmas stories by David Sedaris, read by Sedaris himself. It opens with "
                        "\"SantaLand Diaries\", about the season he spent working as an elf at Macy's in New York, "
                        "which first made his name when he read it on public radio in 1992. The rest are stranger and "
                        "meaner. Hearing him read his own lines, with his timing, is funnier than reading them on the "
                        "page."),
                "note": ("Put it on while you wrap presents or write cards. Start with SantaLand Diaries and see how you "
                         "feel about the darker stories after that."),
                "caveat": ("Adult language and humor throughout, and a few stories are cruel on purpose. Not one for "
                           "the car with the kids."),
            },
            {
                "day": 16, "kind": "tv", "title": "Taskmaster", "year": 2015, "creator": "Alex Horne",
                "hint": "Laughs the whole house can share",
                "time": "About 45 minutes an episode, and many series",
                "why": ("Five comedians spend weeks doing silly tasks set by Alex Horne, usually against the clock and "
                        "with a catch hidden in the wording, and then Greg Davies scores them in a studio. People who have "
                        "never heard of any of the comedians still laugh. It is the rare show teenagers and grandparents "
                        "enjoy together, and with so many series you can drop in anywhere."),
                "note": ("Any series is a fine place to start, though most fans suggest one of the early ones. Channel 4 "
                         "shows a New Year special each year if you want something for the 1st."),
                "caveat": ("It is British, made for adult audiences, and some episodes have swearing and crude jokes. "
                           "Where it streams depends on your country."),
            },
            {
                "day": 17, "kind": "album", "title": "For Emma, Forever Ago", "year": 2007, "creator": "Bon Iver",
                "hint": "An album made in a cabin in the snow",
                "time": "37 minutes",
                "why": ("Justin Vernon recorded most of this album alone over a winter in his father's hunting cabin in "
                        "northern Wisconsin, after a band and a relationship ended. You can hear it: falsetto vocals "
                        "stacked on themselves, an acoustic guitar, a lot of empty room. It came out with almost no "
                        "fanfare and became one of the defining records of the late 2000s, \"Skinny Love\" especially. "
                        "Nine songs, and very good for a cold Thursday night."),
                "note": ("Headphones, or a quiet room. It sounds best when the house is dark and you are not doing "
                         "anything else."),
                "caveat": ("It is sad and slow. If you need something to keep a party going, this door is not it."),
            },
            {
                "day": 18, "kind": "anime", "title": "Toradora!", "year": 2008, "creator": "J.C.Staff",
                "hint": "A Friday binge for the first night of the break",
                "time": "25 episodes of 24 minutes",
                "why": ("Ryuji looks like a delinquent and is really a gentle boy who likes cleaning. Taiga is tiny, "
                        "furious and nicknamed the Palmtop Tiger. They agree to help each other win over their crushes, "
                        "and you can probably guess where that goes. What makes it worth the time is the second half, "
                        "which builds to a school Christmas party with some of the best episodes any romantic comedy "
                        "anime has had. Many schools break up around now, so it is good for starting a binge."),
                "note": ("Watch the first five episodes before you decide. The show starts loud and gets more grown-up as "
                         "it goes."),
                "caveat": ("Taiga's violent slapstick in the early episodes has dated. The ending feels rushed to some fans."),
            },
            {
                "day": 19, "kind": "game", "title": "It Takes Two", "year": 2021, "creator": "Hazelight Studios",
                "hint": "A weekend game for whoever is home",
                "time": "About 12 hours, for two players",
                "why": ("Cody and May are getting divorced, and their daughter's wish turns them into two small dolls who "
                        "have to work together to get home. It only works with two players, sharing a screen or online, "
                        "and almost every level asks the two of you to do different things at the same time. It won Game "
                        "of the Year at The Game Awards in 2021. With siblings or a partner home for the weekend, it is "
                        "the best co-op game of recent years."),
                "note": ("Play a couple of chapters a night across the weekend and into next week. Only one copy is needed "
                         "online, because the second player can join with the free Friend's Pass."),
                "caveat": ("One scene midway, with a toy elephant, upsets a lot of players, children especially. The story "
                           "is about a marriage in trouble, so think about who you play it with."),
            },
            {
                "day": 20, "kind": "album", "title": "Elvis' Christmas Album", "year": 1957, "creator": "Elvis Presley",
                "hint": "Music for decorating the tree",
                "time": "About half an hour",
                "why": ("The last Sunday before Christmas is often the day the tree finally goes up, and that needs a record "
                        "that everyone in the house knows. This is the one with \"Blue Christmas\" and the swaggering "
                        "\"Santa Claus Is Back in Town\", along with carols and gospel songs Elvis sang very straight. "
                        "Irving Berlin reportedly hated his \"White Christmas\". It is now one of the best-selling "
                        "Christmas albums ever made in the United States."),
                "note": ("Put it on loud and let it repeat. Many reissues add extra songs, but the original twelve-track "
                         "order is short enough to go round twice while the lights get untangled."),
                "caveat": ("It is 1957 pop, with all the strings and backing vocals of the time. People who like their Elvis "
                           "rough will find the gospel side very gentle."),
            },
            {
                "day": 21, "kind": "book", "title": "The Left Hand of Darkness", "year": 1969, "creator": "Ursula K. Le Guin",
                "hint": "A novel for the longest night of the year",
                "time": "About 8 hours",
                "why": ("December 21 is the winter solstice in the northern hemisphere, the longest night of the year, and "
                        "this door holds a novel set on a planet called Winter. An envoy from Earth tries to bring Gethen "
                        "into an alliance of worlds, and has to understand a people who have no fixed sex. The last third "
                        "is a long journey across a glacier that is some of the best writing about cold ever printed. It "
                        "won both the Hugo and the Nebula awards."),
                "note": ("Start it tonight and expect it to last into the new year. The first chapters are slow and full "
                         "of politics; the book opens out once the two main characters leave the city."),
                "caveat": ("The book uses \"he\" for everyone on Gethen, a choice Le Guin herself later questioned. Readers "
                           "who want fast plot may find the middle demanding."),
            },
            {
                "day": 22, "kind": "tv", "title": "Station Eleven", "year": 2021, "creator": "Patrick Somerville",
                "hint": "A miniseries for the days before Christmas",
                "time": "10 episodes of about an hour",
                "why": ("It begins on a snowy night in Toronto during a performance of King Lear, as a deadly flu begins to "
                        "spread. Twenty years later a traveling troupe performs Shakespeare for the scattered towns that "
                        "are left. It is adapted from Emily St. John Mandel's novel, and it is about why people keep "
                        "making art when they have nothing else. Mackenzie Davis and Himesh Patel lead it. It came out "
                        "in December, and it plays well across the quiet days before Christmas."),
                "note": ("Watch the first episode, which is nearly a film by itself, then pace the rest at two a night, "
                         "so the last episodes land just before Christmas."),
                "caveat": ("It opens with a pandemic, which not everyone wants to watch. The story jumps between times and "
                           "takes some patience before it fits together."),
            },
            {
                "day": 23, "kind": "audiobook", "title": "Project Hail Mary", "year": 2021, "creator": "Andy Weir",
                "hint": "A long listen for the drive home",
                "time": "About 16 hours",
                "why": ("December 23 is one of the year's heaviest travel days, so this door holds a long audiobook that "
                        "makes the miles go. A man wakes up on a spaceship with no memory and two dead crewmates, and "
                        "works out, science problem by science problem, that he has to save the Sun. Ray Porter's reading "
                        "is a favorite of many audiobook listeners, and the audio version does things with sound the "
                        "printed book cannot. The 2026 film with Ryan Gosling covers the same story."),
                "note": ("Start at the beginning of the drive and do not look up the plot. If you have seen the film, the "
                         "book still holds a lot more of the science."),
                "caveat": ("It is long, and some listeners find the science talk heavy. There is mild swearing, so it suits "
                           "older children."),
            },
            {
                "day": 24, "kind": "movie", "title": "It's a Wonderful Life", "year": 1946, "creator": "Frank Capra",
                "hint": "The old one, for Christmas Eve",
                "time": "2 hours 10 minutes",
                "why": ("George Bailey has spent his life giving up his plans for the people of Bedford Falls, and on "
                        "Christmas Eve he decides they would be better off without him. An angel shows him what that "
                        "would look like. The film did poorly in cinemas in 1946 and only became a tradition after it "
                        "started showing on American television decades later. James Stewart's performance holds up, "
                        "and the last ten minutes still get almost everyone."),
                "note": ("Watch it tonight, as it is meant to be watched, with whoever is home. Anyone who thinks they know "
                         "it from the ending should see how dark the hour before gets."),
                "caveat": ("It is black and white and long, and it takes its time setting up George's life. A colorized "
                           "version exists; the original is better."),
            },
        ],
        "faq": [
            ("When does each door open?", "At midnight on its date, from December 1 to December 24. The page counts "
             "days in the time zone of the person reading it, so a door is not opened early for one reader and late "
             "for another."),
            ("What if I miss a day?", "Nothing happens. Every door that has opened stays open, and you can go back "
             "and open the ones you missed at any time, including after Christmas."),
            ("Do I need an account?", "No. Anyone can read every opened door. Visitors can save picks to a list in "
             "their browser, and that list moves into a free OmniTrackr library when they sign up. Members also get "
             "the badge, the dashboard card and the morning reminder."),
            ("Will the reminder spoil the pick?", "No. The morning notification only says that a new door is open and "
             "repeats the hint written on it, never the title. It follows your quiet hours, and you can switch it off "
             "on this page at any time."),
            ("Why is the 25th missing?", "Advent calendars traditionally run to Christmas Eve. On the 25th you will be "
             "busy, and the holiday hub's Deck the halls shelf has picks for the day itself."),
        ],
        "method": [
            "We picked each title for a particular day of December 2026 first, and for its format second. Weekday doors "
            "hold things that take an hour or two; the Saturday and Sunday doors take longer. Where a pick is tied to "
            "a date, such as the solstice on the 21st, the travel day on the 23rd or Christmas Eve, the page says so.",
            "Every door says how long the pick takes and has a caveat about content, pace or availability. Running "
            "times come from the release versions. Streaming availability changes by country and by month, so we say "
            "where something is exclusive and otherwise leave it out. No pick was paid for, and none repeat the other "
            "holiday guides on the site.",
        ],
    },
}
