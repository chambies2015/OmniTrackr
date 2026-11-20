"""TV season guides for /new-releases: the winter premieres worth planning around.

Same fields as the guides in release_guides.py (that module adds these to GUIDES). A TV
season guide has ``focus: "tv"``, like the anime season guide: its sections are all TV
picks, grouped by kind of show, and it is never the "current" guide on Release Radar.
Picks already written up in the broader winter guide (winter-2026-27) stay there and are
only mentioned in ``also`` here.
"""

GUIDES = {
    "winter-2027-tv": {
        "name": "Winter 2027 TV premieres: the new and returning shows worth your time",
        "period": "January to March 2027",
        "eyebrow": "TV PREMIERES GUIDE",
        "hub_label": "Winter 2027 TV premieres",
        "focus": "tv",
        "search_title": "Winter 2027 TV premieres: The Pitt, Ahsoka, 3 Body Problem, The Wanted Man and more",
        "summary": ("Nineteen winter 2027 TV premieres worth your time, from The Pitt, Ahsoka and 3 Body Problem "
                    "to The Wanted Man and Criminal, with what to watch first."),
        "published": "2026-11-20",
        "reviewed": "2026-11-20",
        "starts": "2027-01-01",
        "ends": "2027-03-31",
        "lead": [
            "January is American television's second premiere season. The networks bring their dramas back after the "
            "holiday break and launch the new shows they held back in the fall, and the streaming services, knowing "
            "that most people spend the cold months on the sofa, put out some of their biggest series of the year. "
            "This winter is crowded even by those standards. Between New Year's Day and the end of February, dozens of "
            "shows start or come back, and in one stretch of eight days in January six of the series in this guide "
            "arrive one after another.",
            "This guide is the short version. We went through the network schedules and the streaming services' "
            "announcements as they stood on November 20 and picked nineteen shows: six returning series, six new "
            "dramas, four new network shows and three comedies. For each one we say when and where it starts, how it "
            "is being released, what you need to have watched first, and the thing most likely to put you off. None of "
            "them are out yet, so read these as bets, not reviews. We say where we're guessing.",
            "A few housekeeping notes. Dates are for the US. Where a service has only announced a month, as HBO Max has "
            "for The Pitt, we say so and will add the day once it is set. Two of the biggest new shows of the season, "
            "HBO's Harry Potter series, which starts on Christmas Day, and Apple's Neuromancer, are covered in our "
            "broader winter releases guide, so we haven't written them up twice. Anime has a season guide of its own.",
        ],
        "sections": [
            {
                "format": "tv",
                "id": "returning",
                "label": "Returning",
                "heading": "Six returning shows, and how much you need to have seen",
                "intro": [
                    "A new season of a show you liked is the easiest decision of the winter, and the hardest one if you "
                    "dropped it halfway through. For each of these we say how the earlier seasons went and how much you "
                    "need to have watched. Two of them, Ahsoka and Blue Eye Samurai, have kept their fans waiting more "
                    "than three years. One, Mayor of Kingstown, is ending.",
                ],
                "picks": [
                    {"kind": "tv", "title": "The Pitt", "year": 2025, "creator": None,
                     "date": "2027-01-01", "month_only": True,
                     "released": "HBO Max · season 3, 15 episodes · HBO Max has only said January so far",
                     "why": "Noah Wyle's emergency room drama, told in real time: each season is a single fifteen-hour "
                            "shift at a Pittsburgh hospital, one hour to an episode. Season 3 takes place on a cold "
                            "November day, four months after the end of season 2.",
                     "note": "The Pitt was the surprise of 2025, a medical drama with the shape of an old network show "
                             "that won the Emmy for best drama series in its first year. The real-time format is what "
                             "makes it work. There are no time jumps, so every case has to be dealt with on the floor, "
                             "and the doctors visibly run out of patience and energy as the hours go by. Season 3 "
                             "changes the balance. Dr. Robby, Wyle's character, has been away on a sabbatical, and he "
                             "doesn't walk back in at the start, so the rest of the ensemble carries more of the early "
                             "episodes. Supriya Ganesh's Dr. Mohan is not coming back, and Chris Diamantopoulos joins as "
                             "the hospital's chief medical officer.",
                     "first": "Seasons 1 and 2, fifteen episodes each. You can't really start here: the relationships "
                              "between the staff build hour by hour, and season 3 assumes you know them.",
                     "first_link": "/best-of/2026/tv", "first_label": "Season 2 in our best TV of 2026",
                     "caveat": "It doesn't cut away from injuries, and it can be hard to watch if you have spent time in "
                               "an emergency room yourself. We will add the premiere date when HBO Max announces it."},
                    {"kind": "tv", "title": "3 Body Problem", "year": 2024, "creator": None,
                     "date": "2027-01-14",
                     "released": "Netflix · season 2, all episodes at once, fewer than season 1's eight",
                     "why": "The second season of David Benioff, D.B. Weiss and Alexander Woo's adaptation of Liu "
                            "Cixin's trilogy. The San-Ti, an alien civilization centuries away, are coming, and Earth is "
                            "building a fleet and trusting a few chosen people with plans that nobody else is allowed "
                            "to know.",
                     "note": "Season 1 was uneven, but it had some of the most striking science-fiction images on "
                             "television that year: the countdown only one woman can see, the ship sliced apart on the "
                             "Panama Canal, the video game that turns out to be a recruiting tool. It also left the story "
                             "in an awkward place, with most of the first novel told and the second, The Dark Forest, "
                             "only just begun. For a lot of readers, us included, The Dark Forest is the best of the "
                             "three books, because it is where Liu's biggest idea arrives: his answer to why the "
                             "universe seems so quiet. If the show gets that right, this season should be better than "
                             "the first. Netflix has taken almost three years to make it, and the third season, already "
                             "filming, is expected to be the last.",
                     "first": "Season 1, eight episodes. The books aren't needed, but if you have read them, know that "
                              "the show mixes characters from all three and moves much of the story from China to "
                              "Britain.",
                     "caveat": "It is slow in places and very bleak about humanity's chances. Netflix hasn't said "
                               "exactly how many episodes there are, only that there are fewer than last time."},
                    {"kind": "tv", "title": "Ahsoka", "year": 2023, "creator": None,
                     "date": "2027-01-20",
                     "released": "Disney+ · season 2",
                     "why": "Dave Filoni's Star Wars series about Ahsoka Tano (Rosario Dawson), Anakin Skywalker's former "
                            "apprentice. Season 2 picks up with Ahsoka and Sabine Wren stranded in another galaxy while "
                            "Grand Admiral Thrawn is back in theirs, preparing a war against the New Republic.",
                     "note": "Ahsoka is the most Filoni of the Star Wars shows: slower, stranger and more mystical than "
                             "The Mandalorian, and built almost entirely on the animated series he made before it. "
                             "Season 1 had some of the best images of the live-action era, the space whales carrying a "
                             "ship between galaxies and Anakin's lessons in the World Between Worlds, and some very stiff "
                             "stretches in between. The reason to go back is Thrawn. Lars Mikkelsen was the best thing in "
                             "season 1, and this is the first time the character gets to be a threat on the scale the "
                             "books and cartoons promised. Rory McCann takes over Baylan Skoll after the death of Ray "
                             "Stevenson, which is a hard part to recast.",
                     "first": "Season 1, eight episodes. Ideally Star Wars Rebels too, especially its last two seasons, "
                              "where Thrawn first appears on screen; the show assumes you already care about Ezra and "
                              "Sabine.",
                     "first_link": "/in-order/star-wars", "first_label": "Star Wars in order",
                     "caveat": "If season 1 lost you, there is no sign this one is a different show. Disney hasn't said "
                               "how many episodes there are or whether they come out weekly."},
                    {"kind": "tv", "title": "Blue Eye Samurai", "year": 2023, "creator": None,
                     "date": "2027-01-19",
                     "released": "Netflix · season 2, all six episodes at once",
                     "why": "The animated revenge story of Mizu (Maya Erskine), a mixed-race swordswoman in 17th-century "
                            "Japan hunting the four white men who might be her father. Season 2 takes her to London in "
                            "1657.",
                     "note": "Season 1 was one of the best-looking animated series ever made, made to look like a "
                             "moving woodblock print and choreographed like a live-action martial arts film, and it won "
                             "the Emmy for outstanding animated program. It was also properly adult: violent, sad and "
                             "funny in the same scenes. It ended with Mizu sailing for England after the man she believes "
                             "is her father, so season 2 is in a sense a new show in a new country, with Jonathan Pryce, "
                             "Joel Kim Booster and Sherry Cola joining the cast. Michael Green and Amber Noizumi, who "
                             "created it, already have a third and final season, so this is the middle chapter.",
                     "first": "Season 1, eight episodes. There is no way into season 2 without it.",
                     "caveat": "It is very violent and has explicit sex scenes. It is animated, but it is not for "
                               "children. Six episodes is short, and it will end on the way to season 3."},
                    {"kind": "tv", "title": "Mayor of Kingstown", "year": 2021, "creator": None,
                     "date": "2027-01-15",
                     "released": "Paramount+ · fifth and final season, eight episodes",
                     "why": "Taylor Sheridan and Hugh Dillon's crime drama about Mike McLusky (Jeremy Renner), who keeps "
                            "an uneasy peace between the prisons, the police and the gangs in a Michigan town whose only "
                            "industry is locking people up. In the final season an FBI agent (David Morse) comes to town "
                            "asking questions the McLuskys would rather nobody asked.",
                     "note": "Of all the Sheridan shows, Kingstown is the bleakest and the least talked about, and it has "
                             "been good for longer than it gets credit for. It is about a system, not a hero: Mike can't "
                             "fix anything, only keep it from getting worse for another week, and the show is honest about "
                             "how much violence that takes. Renner is very good in a part that is mostly listening and "
                             "threatening people in a low voice, and Edie Falco, who arrived in season 4 as the new "
                             "warden, gave it a second centre. A final season of eight episodes, announced in advance, "
                             "gives the writers a real chance to land it, which Sheridan's shows have not always done.",
                     "first": "Seasons 1 to 4, forty episodes. If that is too much, season 1 introduces everyone who "
                              "matters; you will be lost on the details but not on the stakes.",
                     "caveat": "It is relentlessly grim: prison violence, police corruption, very little relief. Mike is "
                               "a fixer for bad people, and the show doesn't pretend otherwise."},
                    {"kind": "tv", "title": "Presumed Innocent", "year": 2024, "creator": None,
                     "date": "2027-02-19",
                     "released": "Apple TV · season 2, a new case · two episodes, then weekly until April 2",
                     "why": "David E. Kelley's legal thriller starts again with a new story. Rachel Brosnahan plays Lelia "
                            "Reynolds, a defense attorney caught up in a murder case that sets her against her husband, "
                            "the district attorney (Matthew Rhys), and puts their careers and their marriage at risk.",
                     "note": "Season 1 adapted Scott Turow's 1987 novel, with Jake Gyllenhaal as a prosecutor accused of "
                             "killing a colleague, and it worked best as a slow puzzle about a marriage under suspicion. "
                             "Apple has now made the show an anthology, and season 2 is based on a different book, "
                             "Dissection of a Murder, the first legal thriller by Jo Murray. The two leads are reason "
                             "enough to try it. Rhys spent two seasons as Perry Mason, so he knows his way around a "
                             "courtroom drama, and Brosnahan, who won an Emmy for The Marvelous Mrs. Maisel, is at her "
                             "best playing someone who thinks faster than everyone in the room. Courtney B. Vance and "
                             "Fiona Shaw are in the cast, and Judith Light guest-stars.",
                     "first": "Nothing. It is a new story with new characters, and season 1 isn't needed.",
                     "caveat": "Kelley loves a late twist, and his shows sometimes bend their last few episodes to fit "
                               "one in. The finale isn't until April 2, so this one runs into spring."},
                ],
            },
            {
                "format": "tv",
                "id": "new",
                "label": "New dramas",
                "heading": "Six new dramas to start first",
                "intro": [
                    "January is when the streaming services release the dramas they hope will hold an audience through "
                    "the dark months, and this winter they have bunched them up badly: four of these six start within "
                    "two weeks of each other. We picked the ones with the most behind them, whether that is a writer "
                    "with a strong record, a book or comic worth adapting, or a cast you rarely see on television, and "
                    "we say which ones are built for a weekend binge and which come out once a week.",
                ],
                "picks": [
                    {"kind": "tv", "title": "The Wanted Man", "year": 2027, "creator": None,
                     "date": "2027-01-06",
                     "released": "Apple TV · two episodes, then weekly on Wednesdays until February 17 (eight in all)",
                     "why": "Hugh Laurie plays Felix Carmichael, a London crime boss sent to Staplehurst prison after "
                            "someone inside his own firm betrays him. To survive inside, and to break out and save his "
                            "family and his business, he has to become the man he used to be.",
                     "note": "George Kay wrote it, and he has a good record with exactly this kind of story. He "
                             "co-created Lupin for Netflix and Hijack for Apple, two shows about a clever man under "
                             "pressure working out his next move faster than everyone around him. Laurie has spent the "
                             "last decade playing men whose good manners are a warning, in The Night Manager and "
                             "Roadkill, and a gangster who has gone soft and has to remember how to frighten people is "
                             "a good fit for him. The cast around him is strong too, with Thandiwe Newton, Stephen "
                             "Dillane, Gina McKee and Fionn Whitehead. Of the January dramas, this is the easiest one to "
                             "recommend to someone who just wants a good thriller.",
                     "first": "Nothing. If you have never seen Hijack, it is seven episodes and shows what Kay does "
                              "with a ticking clock.",
                     "caveat": "Prison dramas lean on violence, and a story about a crime boss asks you to root for a "
                               "man who has hurt a lot of people. It comes out weekly, so you can't finish it until "
                               "mid-February."},
                    {"kind": "tv", "title": "Criminal", "year": 2027, "creator": None,
                     "date": "2027-01-13",
                     "released": "Prime Video · four episodes on January 13 (\"Coward\"), four more on January 27 (\"Lawless\")",
                     "why": "Ed Brubaker and Sean Phillips's crime comic, adapted for television by Brubaker himself. Leo "
                            "Patterson (Charlie Hunnam) and his best friend Ricky Lawless were raised in crime, and a "
                            "murder from their childhood and a heist that went wrong still follow them.",
                     "note": "Criminal began in 2006, and every story in it stands on its own while sharing a city, a "
                             "few bars and the same handful of families. None of them ends well. Brubaker is running the "
                             "show with Jordan Harper, a crime novelist, and the season is split the way the first two "
                             "books are. The first four episodes follow Leo, a careful planner whose rule is never to "
                             "take a risk he can avoid. The second four bring in Ricky's brother Tracy (Luke Evans), who "
                             "chose the army over prison twenty years earlier and comes home when Ricky gets in too "
                             "deep. The cast is unusually deep for a streaming crime show, with Adria Arjona, Emilia "
                             "Clarke, Richard Jenkins and John Hawkes, and the first half is directed by Anna Boden and "
                             "Ryan Fleck.",
                     "first": "Read Coward, the first collected volume. It is a short book, and the first four episodes "
                              "are named after it.",
                     "caveat": "Brubaker's stories are bleak and violent, and they usually end with someone paying for "
                               "it. Prime Video is splitting the season in two, so the end of part one has to wait two "
                               "weeks."},
                    {"kind": "tv", "title": "Bosch: Start of Watch", "year": 2027, "creator": None,
                     "date": "2027-01-10",
                     "released": "MGM+ · two episodes, then weekly on Sundays until February 21 (eight in all)",
                     "why": "A prequel to Bosch set in Los Angeles in 1992, with Cameron Monaghan as a 26-year-old Harry "
                            "Bosch in his first year in uniform, learning the job from his training officer (Omari "
                            "Hardwick) and getting pulled into a big heist and the corruption around it.",
                     "note": "Bosch ran for seven seasons on Prime Video with Titus Welliver in the lead, then three more "
                             "as Bosch: Legacy, and it was always the most grown-up cop show on streaming: slow, careful "
                             "and interested in how a case actually gets built. This one is a bigger risk. Michael "
                             "Connelly never wrote a novel about Bosch's early years, so there is no book to follow, "
                             "only scraps of backstory scattered through the series. Connelly is an executive producer, "
                             "though, and the year is a deliberate choice. 1992 was the year of the Rodney King verdict "
                             "and the riots that followed it, the worst moment in the LAPD's modern history. We don't "
                             "know yet how much of that the show takes on.",
                     "first": "Nothing. If you have never seen Bosch, its first season is the place to start, but this "
                              "is set more than twenty years earlier and works on its own.",
                     "caveat": "MGM+ is a separate subscription, or a paid channel inside Prime Video; it isn't included "
                               "with Prime itself. A prequel can't surprise you about who survives, and fans of Welliver "
                               "may not take to a new Harry."},
                    {"kind": "tv", "title": "Bloodaxe", "year": 2027, "creator": None,
                     "date": "2027-01-20",
                     "released": "Prime Video · all eight episodes at once · season 2 already being filmed",
                     "why": "Michael Hirst, who made Vikings, and his son Horatio tell the story of Erik Bloodaxe (Xavier "
                            "Molyneux) and his wife Gunnhild (Jessica Madsen), fighting rival kings for the throne of "
                            "Norway in the tenth century.",
                     "note": "Vikings ran for six seasons and made Hirst's name for a particular kind of history: real "
                             "people, the sagas as the plot, and a great deal of mud. Erik Bloodaxe is a good subject for "
                             "it. He was a son of Harald Fairhair, remembered as the first king of a united Norway, and "
                             "the sagas say he killed several of his brothers to inherit the crown, lost it to his "
                             "youngest brother Haakon and ended up ruling at York in England. Gunnhild may be the better "
                             "part: the Icelandic sagas make her a sorceress and the real power behind him. Jesper "
                             "Christensen plays Harald and Levi Miller plays Haakon, so the family war looks like the "
                             "spine of the season. Amazon has already ordered a second season, so it won't be cut off "
                             "halfway.",
                     "first": "Nothing. If you want the history, the chapters on Harald and his sons in Snorri "
                              "Sturluson's Heimskringla are short and readable, and Egil's Saga has Erik and Gunnhild as "
                              "its villains.",
                     "caveat": "Hirst played loose with dates and with who did what in Vikings, and there's no reason "
                               "to think this is different, so don't watch it as history. Expect battles, executions "
                               "and a lot of blood."},
                    {"kind": "tv", "title": "The Land", "year": 2027, "creator": None,
                     "date": "2027-02-15",
                     "released": "Hulu · two episodes, then weekly · the day after the Super Bowl",
                     "why": "Dan Fogelman's drama about a fictional version of the Cleveland Browns. Head coach Danny "
                            "Roarke (Christopher Meloni) gets one last chance to turn the team around, and it rests on "
                            "the quarterback they have just drafted, who is his son. Upstairs, the owner (William H. "
                            "Macy) has to choose which of his two daughters takes over.",
                     "note": "Fogelman made This Is Us, which turned a family melodrama into a weekly event, and a "
                             "football team is a natural place for that kind of story: fathers and sons, money, and a "
                             "season that decides everything. Hulu is treating it as an event too, opening it the day "
                             "after the Super Bowl, and NFL Films is one of the production companies, so the football "
                             "should look like the real thing. Some scenes were filmed at the 2026 NFL Draft in "
                             "Pittsburgh. The cast includes Mandy Moore from This Is Us, Bridget Moynahan, Chace "
                             "Crawford, Chloe Bennet and Omar Epps. If any new show this winter finds the kind of "
                             "audience This Is Us had, our bet is this one.",
                     "first": "Nothing. If you don't follow football, the one thing worth knowing is that the Browns, the "
                              "team this one is modelled on, have had very few good seasons in the last twenty-five "
                              "years. That is why the premise works.",
                     "caveat": "Fogelman's shows are built to make you cry and are not shy about it. If This Is Us was "
                               "too much for you, this will be too. Hulu hasn't said how many episodes there are."},
                    {"kind": "tv", "title": "The Age of Innocence", "year": 2027, "creator": None,
                     "date": "2027-02-18",
                     "released": "Netflix · limited series, all eight episodes at once",
                     "why": "A new adaptation of Edith Wharton's 1920 novel. In 1870s New York, the lawyer Newland Archer "
                            "(Ben Radcliffe) is about to marry May Welland (Kristine Froseth) when her cousin Ellen "
                            "Olenska (Camila Morrone) comes home after leaving her husband, a Polish count, and society "
                            "closes ranks against her.",
                     "note": "Wharton's novel won the Pulitzer Prize, the first awarded to a woman for fiction, and Martin "
                             "Scorsese's 1993 film with Daniel Day-Lewis and Michelle Pfeiffer set the bar very high. "
                             "What eight hours can do that two hours couldn't is give the slow part of the story room: "
                             "the dinners, the visits, the way a whole class of people tells Ellen to leave without ever "
                             "saying so. Emma Frost, who wrote The White Queen and The Spanish Princess, has spent most "
                             "of her career on historical drama, and Margo Martindale as the formidable Mrs. Manson "
                             "Mingott is perfect casting. It is the slowest and most grown-up show on this list.",
                     "first": "Read the novel, about 300 pages. Its last chapter is one of the great endings in American "
                              "fiction, and it is better to meet it on the page first.",
                     "caveat": "It is a drama of manners, and very little happens on the surface. If the show turns "
                               "Wharton into a glossy romance, it misses the point of the book, and we haven't seen it "
                               "yet."},
                ],
            },
            {
                "format": "tv",
                "id": "network",
                "label": "Network TV",
                "heading": "Four new network shows worth setting a reminder for",
                "intro": [
                    "The broadcast networks save a few new shows for January, after the fall finales clear the "
                    "schedule. This winter's are mostly revivals and spin-offs, which sounds tired, but two of them come "
                    "from people with very good records, and one has a star who has been carrying network shows for "
                    "more than twenty-five years. Each pick says when it airs and where it streams afterwards, if that "
                    "has been announced. The returning network shows and their dates are in the list at the bottom.",
                ],
                "picks": [
                    {"kind": "tv", "title": "The Rockford Files", "year": 2027, "creator": None,
                     "date": "2027-01-02",
                     "released": "NBC · preview on Saturday, January 2, at 8/7c after football, then Thursdays at 8/7c "
                                 "from January 7 · on Peacock the next day",
                     "why": "A new version of the 1970s private-eye show, with David Boreanaz as Jim Rockford, paroled "
                            "after serving time for a crime he didn't commit and back at work as a Los Angeles private "
                            "investigator, with both the police and organized crime after him.",
                     "note": "The original Rockford Files, with James Garner, ran on NBC from 1974 to 1980 and is still "
                             "one of the most likable shows ever made: a detective who hated fights, got punched anyway "
                             "and spent half of every episode trying to get paid. It opened every week on a message on "
                             "his answering machine, and NBC has set up a real phone line for the new one, which is a "
                             "nice nod. Boreanaz has led network shows for more than twenty-five years, from Angel to "
                             "Bones to SEAL Team, and he does weary charm well. Jacki Weaver is in the cast, and NBC has "
                             "given it the best launch it can, straight after an NFL game.",
                     "first": "Nothing. If you want to see what it will be measured against, the original's 1974 pilot "
                              "shows Garner's Rockford at his best.",
                     "caveat": "Network revivals tend to sand off whatever made the original odd, and Jim Rockford was "
                               "odd: a hero who would rather talk his way out of trouble. If this one turns him into an "
                               "action man, it is a different show with an old name."},
                    {"kind": "tv", "title": "Baywatch", "year": 2027, "creator": None,
                     "date": "2027-01-06",
                     "released": "Fox · Wednesdays at 9/8c",
                     "why": "A sequel to the lifeguard show, with Stephen Amell as Hobie Buchannon, the son of David "
                            "Hasselhoff's Mitch, now a captain on the beach, whose life is turned over when the daughter "
                            "he didn't know he had, Charlie (Jessica Belkin), turns up.",
                     "note": "The original Baywatch was cancelled by NBC after one season in 1990, came back in "
                             "syndication and became one of the most watched shows in the world. Nobody is pretending "
                             "the new one is prestige television, and that is the point. Amell spent eight years as Green "
                             "Arrow in Arrow and is a likable lead for a show that runs on rescues and soap opera. David "
                             "Chokachi has a recurring part, and Erika Eleniak and Kelly Packard from the original turn "
                             "up too. If you want an hour of sunshine in January, this is the most honest pitch on the "
                             "network schedule.",
                     "first": "Nothing. It is made for people who have never seen the original.",
                     "caveat": "It is exactly what it looks like. The old show was never character drama, and the new "
                               "one probably isn't either. Fox hasn't said how many episodes there are."},
                    {"kind": "tv", "title": "The Rookie: North", "year": 2027, "creator": None,
                     "date": "2027-01-06",
                     "released": "ABC · Wednesdays at 10/9c, after The Rookie · on Hulu the next day",
                     "why": "The second spin-off of The Rookie. Jay Ellis plays Alex Holland, a man in middle age who "
                            "joins a police department in Washington state after a home invasion changes his life: the "
                            "same late start that made Nathan Fillion's John Nolan the oldest rookie in Los Angeles.",
                     "note": "The Rookie has run for eight seasons on a simple idea that keeps working: a man starting at "
                             "the bottom of a job usually done by people in their twenties, and finding it harder and "
                             "funnier than he expected. The first spin-off, The Rookie: Feds, lasted one season. This one "
                             "copies the original more closely, which is probably wiser, and it starts on the same night "
                             "as The Rookie's ninth season, straight after it, with Fillion's Nolan appearing in the "
                             "pilot. Ellis, from Insecure and Top Gun: Maverick, is an easy lead to like.",
                     "first": "Nothing. If you have never seen The Rookie, its first season is the clearest version of "
                              "the idea.",
                     "caveat": "It is a network cop show: a case a week, tidy endings, and policing shown in a mostly "
                               "flattering light. If that isn't your kind of show, a new setting won't change your "
                               "mind."},
                    {"kind": "tv", "title": "Einstein", "year": 2027, "creator": None,
                     "date": "2027-02-12",
                     "released": "CBS · Fridays at 8/7c · streams on Paramount+",
                     "why": "Matthew Gray Gubler plays Lewis, the great-grandson of Albert Einstein: brilliant, bored and "
                            "going nowhere, until a New Jersey detective (Melissa Fumero) talks him into helping on her "
                            "cases. Tony Shalhoub plays his father.",
                     "note": "CBS has been trying to launch this for a while. It was meant for the 2025-26 season and was "
                             "held back a year, so it arrives with something to prove. The format is an old favourite, "
                             "the gifted oddball who helps the police, and it comes from producers of Monk, which makes "
                             "Tony Shalhoub, who played Monk, turning up as Lewis's father more than a cameo joke. Gubler "
                             "spent fifteen seasons as Spencer Reid on Criminal Minds and has a loyal following that has "
                             "waited a long time for him to lead his own show. Fumero spent eight seasons as Amy "
                             "Santiago in Brooklyn Nine-Nine and is very good at playing the straight one in a comedy.",
                     "first": "Nothing. It is a case-of-the-week show, made to be picked up anywhere.",
                     "caveat": "Shows about geniuses who help the police run on a formula, and the formula can wear thin "
                               "after a dozen episodes. The year's delay may mean nothing, or it may mean CBS had "
                               "doubts; we'll know in February."},
                ],
            },
            {
                "format": "tv",
                "id": "comedy",
                "label": "Comedy",
                "heading": "Three comedies for a lighter night",
                "intro": [
                    "Winter TV is heavy, and most of the shows above are about crime, war or the end of the world. These "
                    "three are comedies: one a romance timed for Valentine's week, one a workplace comedy from the "
                    "Brooklyn Nine-Nine team, and one built around a cast that is hard to resist. Two of them are on "
                    "Apple TV, whose comedies, from Ted Lasso to Shrinking and The Studio, have been its most reliable "
                    "shows.",
                ],
                "picks": [
                    {"kind": "tv", "title": "Prodigies", "year": 2027, "creator": None,
                     "date": "2027-02-10",
                     "released": "Apple TV · two episodes, then weekly on Wednesdays until March 17 (seven in all)",
                     "why": "Two former child prodigies, Didi (Ayo Edebiri) and Ren (Will Sharpe), now in their thirties, "
                            "take a hard look at the relationship they have been in since they were nine. A romantic "
                            "comedy that moves from London to Tokyo by way of Virginia.",
                     "note": "Will Sharpe created, wrote and directed it, and he has one of the most interesting records "
                             "of anyone on this list. His first series, Flowers, was a pitch-black family comedy about "
                             "depression, he won a BAFTA for acting in Giri/Haji, and most people know him as Ethan in "
                             "the second season of The White Lotus. Edebiri is the reason a lot of people will try it, "
                             "after The Bear, and the idea is a good one: two people who were told at nine that they were "
                             "special, and have been together ever since, finding out what they are like when nobody is "
                             "watching. The supporting cast is odd and promising, with John Malkovich, Tobias Menzies, "
                             "Maria Bakalova, Rina Sawayama and Reece Shearsmith.",
                     "first": "Nothing. If you have never seen Flowers, its two short seasons show the tone Sharpe likes, "
                              "sad and funny in the same moment.",
                     "caveat": "Sharpe's work can be melancholy, and a comedy about a long relationship may care more "
                               "about the cracks than the sweetness. Don't expect a light date-night show just because "
                               "it opens in Valentine's week."},
                    {"kind": "tv", "title": "Sunset P.I.", "year": 2027, "creator": None,
                     "date": "2027-02-08",
                     "released": "NBC · Mondays at 8:30/7:30c, after St. Denis Medical · on Peacock the next day · ten "
                                 "episodes",
                     "why": "A workplace comedy about the private investigators at a small Hollywood detective agency, "
                            "led by Mickey Wilder (Jake Johnson), from Dan Goor and Luke Del Tredici of the Brooklyn "
                            "Nine-Nine team.",
                     "note": "Brooklyn Nine-Nine was one of the best network comedies of the 2010s about people who are "
                             "good at their jobs and ridiculous about everything else, and this moves the same idea to "
                             "private detectives in Los Angeles. Unlike a lot of network comedies now, it isn't a "
                             "mockumentary, so there are no talking heads to camera. Jake Johnson spent seven seasons as "
                             "Nick in New Girl and is very good at playing a man who is competent in spite of himself. "
                             "Jane Levy and Keith David round out a good cast, and Akiva Schaffer, of The Lonely Island, "
                             "directed the pilot.",
                     "caveat": "Comedies often take half a season to find their voice, and the pilot may not be the best "
                               "episode. It is light and silly; if you want your detective shows to have real stakes, "
                               "this isn't one."},
                    {"kind": "tv", "title": "She's Fine", "year": 2027, "creator": None,
                     "date": "2027-01-27",
                     "released": "Apple TV · two episodes, then weekly on Wednesdays until March 24",
                     "why": "Elizabeth Banks plays Heidi, fresh out of a messy divorce and looking for a second act, who "
                            "ends up managing the love lives of her father's retirement community and has to team up "
                            "with the son (Rob Delaney) of her father's girlfriend to do it. Ted Danson plays her father "
                            "and Katey Sagal his girlfriend.",
                     "note": "This is one to watch for the cast. Ted Danson is in the middle of a late-career run as the "
                             "warmest man on television, from The Good Place to A Man on the Inside, Katey Sagal can play "
                             "funny or frightening with equal ease, and Rob Delaney, who co-created Catastrophe, is one of "
                             "the best around at awkward grown-up romance. Banks has mostly been directing and producing "
                             "in recent years, and it is good to see her lead a comedy again. Liz Heldens and Matt Ward "
                             "created it and run it.",
                     "caveat": "A retirement community played for romance is close to the setting of A Man on the "
                               "Inside, Danson's Netflix comedy, and the comparison won't help it. Jokes about older "
                               "people's love lives can go either way."},
                ],
            },
        ],
        "also": [
            ("Neuromancer (January 22, Apple TV).",
             "William Gibson's cyberpunk novel, with Callum Turner as the hacker Case and Briana Middleton as Molly. We "
             "wrote it up in our broader winter releases guide."),
            ("Common Side Effects, season 2 (January 24, Adult Swim).",
             "The animated thriller about a mushroom that could cure anything, also in the winter guide. It streams on "
             "HBO Max the next day."),
            ("The Twin (January 1, Netflix).",
             "A six-part British crime story with Jamie Dornan as estranged identical twins and Mackenzie Davis as the "
             "woman married to one of them, remade from the Norwegian series Twin."),
            ("Your Friendly Neighborhood Spider-Man, season 2 (January 13, Disney+).",
             "Marvel's animated Peter Parker series comes back, with Venom on the way."),
            ("Grown Ups (January 14, Netflix).",
             "Eight episodes from Marian Keyes's novel about a big Dublin family coming apart after a sudden death, with "
             "Sarah Greene, Aisling Bea and Robert Sheehan."),
            ("All Creatures Great and Small, season 7 (January 17, PBS).",
             "The Yorkshire vets reach 1946. Gentle Sunday-night viewing, and already renewed for an eighth season."),
            ("Ginny & Georgia, season 4 (January 21, Netflix).",
             "The mother-and-daughter drama returns, with Brianne Howey and Antonia Gentry."),
            ("Embassy (February 7, MGM+).",
             "A six-part siege thriller at the US embassy in London, with Anna Kendrick as a diplomat, Sam Heughan as "
             "her ex, an SAS soldier, and J.K. Simmons as the ambassador."),
            ("The Interrogator (February 9, Fox).",
             "Stephen Fry plays a former MI6 interrogator leading a team of unusual operatives, with Jenna Elfman and "
             "Michael Beach."),
            ("Oswald (February, Disney+).",
             "A three-part miniseries from Jon Favreau that brings back Oswald the Lucky Rabbit, the character Walt "
             "Disney and Ub Iwerks created before Mickey Mouse, mixing hand-drawn animation with live action."),
            ("Overcompensating, season 2 (February 17, Prime Video).",
             "Benito Skinner's college comedy picks up with Benny home for Christmas and still in the closet, with "
             "AnnaSophia Robb and Tom Francis joining the cast."),
            ("The Walking Dead: Daryl Dixon, final season (February, AMC and AMC+).",
             "Daryl and Carol cross Spain trying to get home, with Jimmy Smits joining for the last season."),
            ("The network returns in January.",
             "Will Trent and High Potential (January 5, ABC), The Rookie (January 6, ABC), Grey's Anatomy and 9-1-1 "
             "(January 7, ABC), NCIS (January 12, CBS), Abbott Elementary (January 13, ABC), and Ghosts and Matlock "
             "(January 21, CBS) all come back in the first three weeks."),
            ("Reality in February and March.",
             "American Idol's 25th season (February 8, ABC), Survivor 52 (February 24, CBS), and the 30th season of The "
             "Bachelor, which moves to Sundays (March 21, ABC)."),
        ],
        "plan_heading": "A plan for the winter",
        "plan": [
            "Use December to catch up. The returning shows with the most to watch first are The Pitt (thirty episodes) "
            "and Mayor of Kingstown (forty), so if you only have time for one, choose the one you are more likely to "
            "finish. Blue Eye Samurai's first season is eight episodes and makes a good holiday binge, and so is 3 Body "
            "Problem's.",
            "The first three weeks of January are crowded. The network shows arrive first, from January 2. Then, in "
            "eight days, come Criminal (January 13), 3 Body Problem (January 14), Mayor of Kingstown (January 15), Blue "
            "Eye Samurai (January 19), and Ahsoka and Bloodaxe (both January 20). The ones released all at once, 3 Body "
            "Problem, Blue Eye Samurai and Bloodaxe, are weekend shows. The weekly ones, The Wanted Man and Bosch: Start of "
            "Watch, are easier to fit around them.",
            "February is calmer and better for trying something new: Prodigies on the 10th, The Land the day after the "
            "Super Bowl, The Age of Innocence on the 18th and Presumed Innocent on the 19th. March has very few dates "
            "yet. The services usually fill in their spring schedules over December and January, so we will add March "
            "premieres here as they are set, and the date at the top of the page says when we last checked.",
        ],
        "method": [
            "Prepared by OmniTrackr with AI assistance and reviewed by the site owner before publishing. None of these "
            "shows had aired when we wrote about them, so this is a guide to what we think is worth trying, not a set "
            "of reviews. We worked from the networks' published winter schedules, the streaming services' own "
            "announcements and the coverage listed below, checked each date against a second source where we could, "
            "and picked shows we would recommend to a friend, with an honest note on who should skip them.",
            "TV dates are firmer than game dates but looser than film dates: a streaming service can move a show by a "
            "week with little notice, and the networks shuffle their schedules around sport. Where only a month has "
            "been announced, we say so. Release patterns (all at once, weekly, or a few episodes and then weekly) are "
            "given only where the service has announced them.",
        ],
        "related": [
            ("If you liked Severance", "/if-you-liked/severance"),
            ("If you liked Breaking Bad", "/if-you-liked/breaking-bad"),
            ("The best TV shows of 2026", "/best-of/2026/tv"),
            ("Star Wars in order", "/in-order/star-wars"),
            ("How to track TV shows and episodes on OmniTrackr", "/tv-show-tracker"),
        ],
        "sources": [
            ("TV Guide: ABC's winter 2027 schedule", "https://www.tvguide.com/news/abc-winter-tv-schedule-2027-high-potential-will-trent-the-rookie-premiere/"),
            ("TVLine: CBS midseason 2027 premiere dates", "https://www.tvline.com/2316765/cbs-midseason-schedule-2027-premiere-dates/"),
            ("TVLine: Fox midseason 2027 premiere dates", "https://www.tvline.com/2314075/fox-midseason-schedule-2027-premiere-dates/"),
            ("TheWrap: CBS sets Matlock and Einstein for midseason", "https://www.thewrap.com/media-platforms/tv/cbs-premiere-dates-matlock-einstein/"),
            ("Screen Rant: 2026-27 winter TV preview", "https://screenrant.com/2026-2027-winter-tv-preview-exclusive-images/"),
            ("TVLine: The Pitt season 3, everything we know", "https://www.tvline.com/2153855/the-pitt-season-3-everything-we-know-noah-wyle-hbo-max/"),
            ("What's on Netflix: 3 Body Problem season 2 release date", "https://www.whats-on-netflix.com/news/3-body-problem-season-2-netflix-release-date-season-3-filming-update/"),
            ("What's on Disney Plus: Ahsoka season 2 release date", "https://whatsondisneyplus.com/star-wars-ahsoka-season-2-disney-release-date-announced/"),
            ("Gizmodo: Blue Eye Samurai season 2 arrives in January", "https://gizmodo.com/blue-eye-samurai-season-2-will-finally-arrive-in-january-2000834434"),
            ("Seat42F: Mayor of Kingstown final season premieres January 15", "https://seat42f.com/mayor-of-kingstown-season-5-premiere-date-first-look-photos/"),
            ("The Express Tribune: Presumed Innocent season 2 release date", "https://tribune.com.pk/story/2641405/apple-tv-reveals-presumed-innocent-season-2-release-date-and-first-look-images"),
            ("Apple TV press: first look at The Wanted Man", "https://www.apple.com/uk/tv-pr/news/2026/09/apple-tv-unveils-first-look-at-the-wanted-man-a-new-crime-drama-starring-and-executive-produced-by-hugh-laurie/"),
            ("TVLine: Criminal release dates and trailer", "https://www.tvline.com/2307650/criminal-release-date-prime-video-trailer-charlie-hunnam-adria-arjona-emilia-clarke/"),
            ("Michael Connelly: Bosch: Start of Watch premieres January 10", "https://www.michaelconnelly.com/bosch-start-of-watch/"),
            ("About Amazon: Bloodaxe comes to Prime Video January 20", "https://www.aboutamazon.com/news/entertainment/bloodaxe-vikings-prime-video"),
            ("TheWrap: The Land gets a post-Super Bowl debut on Hulu", "https://www.thewrap.com/creative-content/tv-shows/dan-fogelman-nfl-tv-show-the-land-premiere-date-first-look/"),
            ("tbreak: The Age of Innocence lands on Netflix February 18", "https://tbreak.com/age-of-innocence-netflix-release-date/"),
            ("TheWrap: The Rockford Files reboot premieres in January", "https://www.thewrap.com/creative-content/tv-shows/the-rockford-files-reboot-premiere-date-nbc/"),
            ("TV Insider: Fox midseason 2027 premiere dates", "https://www.tvinsider.com/1303036/fox-midseason-2027-premiere-dates-schedule/"),
            ("TheWrap: Prodigies premiere date and first look", "https://www.thewrap.com/creative-content/tv-shows/will-sharpe-ayo-edebiri-prodigies-premiere-date-first-look-apple-tv/"),
            ("TVLine: Sunset P.I. gets a February premiere", "https://www.tvline.com/2316183/sunset-pi-nbc-premiere-date-february-2027-jake-johnson-photos/"),
            ("TVLine: She's Fine release date", "https://www.tvline.com/2314375/shes-fine-apple-tv-release-date-christmas-with-snoop-nbc/"),
            ("Collider: The Twin comes to Netflix January 1", "https://collider.com/the-twin-netflix-january-release-date/"),
            ("What's on Netflix: Grown Ups release date", "https://www.whats-on-netflix.com/news/grown-ups-marian-keys-netflix-series-release-date-first-looks/"),
            ("What's on Netflix: Ginny & Georgia season 4 release date", "https://www.whats-on-netflix.com/news/ginny-georgia-season-4-netflix-release-date-first-look/"),
            ("GamesRadar+: Your Friendly Neighborhood Spider-Man season 2 date", "https://www.gamesradar.com/entertainment/marvel-tv-shows/your-friendly-neighborhood-spider-man-season-2-confirms-venom-and-a-new-release-date/"),
            ("PinkNews: Overcompensating season 2 release date", "https://www.thepinknews.com/2026/11/09/prime-video-overcompensating-season-2-release-benito-skinner/"),
            ("TheWrap: Jon Favreau's Oswald sets its Disney+ premiere", "https://www.thewrap.com/creative-content/tv-shows/oswald-jon-favreau-miniseries-footage-description-release-date"),
            ("AMC: first look at the final season of Daryl Dixon", "https://www.amc.com/blogs/amc-debuts-first-look-at-the-final-season-of-the-walking-dead-daryl-dixon--1075773"),
        ],
    },
}
