"""Release guides: the new movies, shows, games, anime and books worth planning around.

Content only; app/new_releases.py and app/routers/new_releases.py turn it into
pages at /new-releases/<slug>. A guide covers one stretch of the calendar
(``starts`` to ``ends``) and goes live on its ``published`` date. Most picks are
not out when the guide is written, so the writing says why a release is worth a
place in your plans and who should wait for reviews. It is not a review.

Guide fields: name, period (shown in the eyebrow), search_title, summary,
published, reviewed, starts, ends, lead (paragraphs), sections, also (shorter
mentions: (title, sentence)), plan_heading, plan (paragraphs), related
((label, path)), sources ((label, url)). Optional: focus (one format, e.g. "anime", for a
guide that covers a single format, such as an anime season; it is never the "current"
guide), eyebrow (replaces "RELEASE GUIDE"), hub_label (its card label on /new-releases),
method (paragraphs replacing the standard "How we chose" note; keep the AI-assistance line).

Section fields: format (new_releases.FORMAT_ORDER), heading, intro (paragraphs), picks.
A focused guide's sections share one format, so each also has an id and a label.

Pick fields: kind, title, year (the year OmniTrackr files it under: a returning
series keeps its first season's year), creator (director or author; None for TV,
anime and games), date (ISO release date in the US; with month_only=True only
the month is firm), released (where, in a few words), why (what it is; stands on
its own, also shown by Pick for me), note (why it is on the list), first
(optional: what to catch up on first, with optional first_link and
first_label), caveat.
"""

GUIDES = {
    "november-2026": {
        "name": "November 2026 releases worth your time",
        "period": "November 2026",
        "search_title": "November 2026 releases: the movies, shows, games, anime and books worth it",
        "summary": ("Our picks from November 2026's new movies, TV, games, anime and books, from Grand Theft Auto VI "
                    "and the new Hunger Games to Godzilla, with what to catch up on first."),
        "published": "2026-11-01",
        "reviewed": "2026-11-01",
        "starts": "2026-11-01",
        "ends": "2026-11-30",
        "lead": [
            "November is when the entertainment calendar stops pretending to be reasonable. Studios hold back their "
            "family films for the Thanksgiving weekend, the streamers drop their prestige series before everyone "
            "goes home for the holidays, and this year the single biggest video game in a decade lands on the 19th. "
            "If you tried to keep up with all of it, you would spend the month doing nothing else.",
            "So this guide is a filter. We went through the dated releases for the month and kept the ones we would "
            "actually plan around: five films, five series, three games, four anime and four books. For each one we "
            "say why it made the cut, who should wait for the reviews, and what to watch, play or read first if you "
            "want to arrive ready. Most of them aren't out yet, so treat these as informed bets. We say "
            "plainly where we are guessing.",
            "A word on the anime section. The autumn anime season started in October, so the best November anime is "
            "already airing. Those picks are shows you can catch up on now, five or six episodes in, when it is much "
            "easier to tell which ones are worth the time.",
        ],
        "sections": [
            {
                "format": "movies",
                "heading": "Five films to plan a night around",
                "intro": [
                    "The month opens with a monster and closes with a crowded Thanksgiving weekend: Disney's new animated "
                    "film, a fourth Meet the Parents, and a Netflix film from David Fincher getting two weeks in IMAX "
                    "before it streams. In between sits the month's surest hit, the Hunger Games prequel about Haymitch.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Godzilla Minus Zero", "year": 2026, "creator": "Takashi Yamazaki",
                     "date": "2026-11-06", "released": "In theaters · Toho, released in North America by GKIDS",
                     "why": "Takashi Yamazaki's follow-up to Godzilla Minus One picks up in 1949, two years after the first "
                            "film, with Ryunosuke Kamiki and Minami Hamabe back in the lead roles.",
                     "note": "Godzilla Minus One was the surprise of 2023: a monster movie made for a fraction of a Hollywood "
                             "budget that won the Oscar for visual effects and made people cry over a fictional "
                             "kamikaze pilot. What made it work was that the human story came first and Godzilla arrived "
                             "like a natural disaster. If Yamazaki keeps that balance, this is the film of the month. "
                             "It is also the easiest November release to recommend to someone who doesn't usually watch "
                             "monster films, because the first one wasn't really made for monster fans.",
                     "first": "Watch Godzilla Minus One (2023). This is a direct sequel, and the ending of the first film "
                              "only means something if you have sat through what came before it.",
                     "caveat": "In Japanese with subtitles in most theaters. Expect it to be darker than the American "
                               "Godzilla films; the first one did not spare its characters, and the war is still very close."},
                    {"kind": "movie", "title": "Ebenezer", "year": 2026, "creator": "Ti West",
                     "date": "2026-11-13", "released": "In theaters",
                     "why": "A PG-13 version of A Christmas Carol from Ti West, the director of X and Pearl, with Johnny "
                            "Depp as Scrooge, Ian McKellen as Jacob Marley and Rupert Grint as Bob Cratchit.",
                     "note": "There have been dozens of Christmas Carols, and the story is easy to make cosy. Ti West has "
                             "spent his career on slow-building horror, and Dickens wrote a ghost story: a man visited at "
                             "night by the dead and shown his own grave. A version that takes the ghosts seriously could "
                             "be the most interesting take in years. McKellen as Marley, rattling his chains, is the "
                             "casting we are most curious about.",
                     "first": "Read the novella. It is about 30,000 words, an evening's reading, and much funnier and "
                              "stranger than most adaptations remember.",
                     "caveat": "Johnny Depp in the lead will put some people off, and that is a fair reason to skip it. "
                               "PG-13 means West can't go as far as his R-rated work, so don't expect X."},
                    {"kind": "movie", "title": "The Hunger Games: Sunrise on the Reaping", "year": 2026,
                     "creator": "Francis Lawrence", "date": "2026-11-20", "released": "In theaters · Lionsgate",
                     "why": "The story of the 50th Hunger Games, 24 years before Katniss, when a teenage Haymitch "
                            "Abernathy (Joseph Zada) is reaped for a Quarter Quell with twice the usual number of tributes.",
                     "note": "Suzanne Collins's 2025 novel is the best of the prequels, because everyone who read the "
                             "original books already knows Haymitch survives. The question is what it cost him, and the "
                             "answer is grim. Francis Lawrence has now directed five of these films and knows how to stage "
                             "the arena. The cast around Zada is strong: Ralph Fiennes as President Snow, Jesse Plemons as "
                             "Plutarch Heavensbee and Elle Fanning as Effie Trinket. This is the safest bet in the month "
                             "for a group outing.",
                     "first": "Read the novel if you have a free weekend; it is about 400 pages and moves fast. If not, "
                              "rewatch Catching Fire, which shows the grown-up Haymitch at his most guarded.",
                     "first_link": "/in-order/hunger-games", "first_label": "The Hunger Games in order",
                     "caveat": "Probably the bleakest film in the series, with children killing children as its premise "
                               "and an ending that offers very little comfort. Not for younger fans of the first film."},
                    {"kind": "movie", "title": "Hexed", "year": 2026, "creator": "Josie Trinidad and Jason Hand",
                     "date": "2026-11-25", "released": "In theaters · Walt Disney Animation Studios",
                     "why": "Disney's Thanksgiving animated film: Billie Doe (Hailee Steinfeld), a teenager with hidden "
                            "powers, is pulled into a realm of witches, with Rashida Jones as her mother.",
                     "note": "Disney has opened an animated film over Thanksgiving almost every year since Frozen, and "
                             "the originals have been hit and miss lately. We are hopeful about this one for a simple "
                             "reason: it is a story about a mother and a daughter who don't understand each other, which "
                             "is what Disney does best when it isn't selling a sequel.",
                     "caveat": "We know the premise and the voice cast, and not much else. Family films this close to "
                               "Thanksgiving are rarely screened for critics early, so you may be choosing on the trailer."},
                    {"kind": "movie", "title": "The Further Mis-Adventures of Cliff Booth", "year": 2026,
                     "creator": "David Fincher", "date": "2026-11-25",
                     "released": "Two weeks in IMAX theaters, then on Netflix from December 23",
                     "why": "Brad Pitt returns as the stuntman from Once Upon a Time in Hollywood, now in 1977, in a film "
                            "written by Quentin Tarantino and directed by David Fincher.",
                     "note": "Tarantino scripts directed by someone else are rare, and Fincher is the last "
                             "director you would expect: precise and cold where Tarantino is loose and talky. That "
                             "collision is the reason to go. Pitt won an Oscar for this character, a man who is easy "
                             "company until he very suddenly isn't, and the 1970s setting suits both of them. If you "
                             "want to see it on a big screen, the IMAX window is short.",
                     "first": "Rewatch Once Upon a Time in Hollywood (2019). It runs 2 hours 41 minutes, and Cliff's "
                              "backstory is all in there, including the part people still argue about.",
                     "caveat": "If you didn't like Once Upon a Time in Hollywood, a whole film of Cliff Booth is unlikely "
                               "to change your mind. Expect violence and a long running time."},
                ],
            },
            {
                "format": "tv",
                "heading": "Five series worth starting",
                "intro": [
                    "November is thick with returning shows (The Rings of Power, Percy Jackson, Black Doves and The "
                    "Gilded Age all come back this month), but the more interesting picks are new. We chose three new "
                    "series, one limited series about a story you probably read about in the news, and one ending.",
                ],
                "picks": [
                    {"kind": "tv", "title": "The Greatest", "year": 2026, "creator": None,
                     "date": "2026-11-04", "released": "Prime Video · eight-episode limited series",
                     "why": "A limited series about the life of Muhammad Ali, created by Ben Watkins (Cross), with Michael "
                            "B. Jordan and Lonnie Ali, Ali's widow, among the executive producers.",
                     "note": "Ali's life has too much in it for a two-hour film, which is the problem Michael Mann's Ali "
                             "ran into in 2001. The Olympic gold, the name change, the refusal to be drafted and the "
                             "three lost years, the Rumble in the Jungle, the Thrilla in Manila, and the long illness "
                             "afterwards: eight episodes give each of those room. Lonnie Ali's involvement suggests the "
                             "family trusts the project, which counts for something with a story this well guarded.",
                     "first": "Watch When We Were Kings (1996), the Oscar-winning documentary about the 1974 fight with "
                              "George Foreman in Kinshasa. It is the best 90 minutes on Ali there is.",
                     "caveat": "Boxing biopics live or die on the lead performance, and we haven't seen it. Expect "
                               "fight scenes, period racism and a slow, sad final stretch."},
                    {"kind": "tv", "title": "The Altruists", "year": 2026, "creator": None,
                     "date": "2026-11-19", "released": "Netflix · eight-episode limited series",
                     "why": "The rise and collapse of the crypto exchange FTX, with Anthony Boyle as Sam Bankman-Fried and "
                            "Julia Garner as Caroline Ellison.",
                     "note": "FTX went from a $32 billion valuation to bankruptcy in about a week in November 2022, and "
                             "the story has everything a drama needs: a small group of young people in a Bahamas "
                             "penthouse, a theory about doing good by getting rich, and billions of other people's money. "
                             "Garner was the best thing in Ozark and Inventing Anna. The question is whether the show can "
                             "make the inner circle interesting without making them likeable.",
                     "first": "Read Going Infinite (2023), Michael Lewis's book about Bankman-Fried. It is gripping, and "
                              "it is also a useful lesson in how close a writer can get to his subject.",
                     "caveat": "These are real people and real losses; some viewers will find a glossy drama about them "
                               "hard to enjoy. Expect drug use and a lot of explaining about how the money moved."},
                    {"kind": "tv", "title": "Yellowjackets", "year": 2021, "creator": None,
                     "date": "2026-11-20", "released": "Paramount+ with Showtime · season 4, the final season",
                     "why": "The last season of the series about a high-school girls' soccer team stranded in the Canadian "
                            "wilderness in 1996, and the women they became 25 years later.",
                     "note": "Few shows have started as strongly as Yellowjackets did in 2021, and few have tested their "
                             "fans' patience as much since. The third season brought back some of the dread but left a "
                             "lot of threads hanging. Ashley Lyle and Bart Nickerson, who created it, have long said they knew "
                             "how it ends. A final season is the moment to find out whether the wilderness was ever "
                             "supernatural, and whether the show knew all along.",
                     "first": "If you dropped out during season 2, the third season is worth catching up on before the "
                              "finale. It is shorter and sharper.",
                     "caveat": "Graphic violence, cannibalism, self-harm and sexual content. If season 2 lost you, season "
                               "4 may not win you back; it is an ending for people who are already invested."},
                    {"kind": "tv", "title": "Dig", "year": 2026, "creator": None,
                     "date": "2026-11-23", "released": "Peacock · ten episodes",
                     "why": "A comedy about four women on an archaeological dig in Greece who uncover an international "
                            "conspiracy, from Amy Poehler and Michael Schur, with Poehler and Hugh Laurie in the cast.",
                     "note": "Poehler and Schur made Parks and Recreation together, and Schur went on to make The Good "
                             "Place, so this is the most reliable comedy pairing on the calendar. It is based on Kate "
                             "Myers's 2023 novel Excavations. Hugh Laurie in a Schur comedy is about as safe a "
                             "bet as television offers.",
                     "first": "Read Excavations if you like a funny mystery. Otherwise, nothing needed.",
                     "caveat": "Schur's shows usually take three or four episodes to find their rhythm, and a "
                               "conspiracy plot is new territory for him. Give it until the midpoint before deciding."},
                    {"kind": "tv", "title": "Blade Runner 2099", "year": 2026, "creator": None,
                     "date": "2026-11-25", "released": "Prime Video · limited series",
                     "why": "A live-action series set 50 years after Blade Runner 2049, in a world where replicants now "
                            "outnumber humans, with Michelle Yeoh and Hunter Schafer, and Ridley Scott as executive producer.",
                     "note": "Both Blade Runner films underperformed in theaters and became the most influential science "
                             "fiction of their decades, which tells you what kind of audience this is for. A series has "
                             "time the films didn't: time for the city, the rain and the long silences. Michelle Yeoh "
                             "brings weight to anything she is in. We are less sure what a story looks like once the "
                             "replicants have won, and that is exactly why we want to see it.",
                     "first": "Watch Blade Runner 2049 (2017), and the 1982 original if you never have. The Final Cut is "
                              "the version to see.",
                     "first_link": "/if-you-liked/interstellar", "first_label": "More slow, big science fiction",
                     "caveat": "If it keeps the films' pace, expect slow episodes and few answers. The series has been in "
                               "the works for years, and long productions don't always arrive in good shape."},
                ],
            },
            {
                "format": "games",
                "heading": "Three games, and one of them is enormous",
                "intro": [
                    "Most publishers moved their games away from November 19 the moment Rockstar settled on it, so the "
                    "month is lighter than usual. Nintendo is the exception: the Switch 2 gets a remade Ocarina of Time "
                    "and a run of ports of very good games.",
                ],
                "picks": [
                    {"kind": "game", "title": "The Legend of Zelda: Ocarina of Time Remake", "year": 2026, "creator": None,
                     "date": "2026-11-05", "released": "Nintendo Switch 2 · Nintendo",
                     "why": "A full remake of the 1998 Zelda game, announced at the series' 40th anniversary presentation "
                            "in September, with full voice acting for the first time.",
                     "note": "Ocarina of Time taught a generation how to play 3D action games: lock on to an enemy, circle, "
                             "strike. Almost every adventure game since owes it something. It also shows its age now, "
                             "with fiddly menus, an infamous Water Temple, and a Hyrule Field that feels empty after Breath "
                             "of the Wild. A remake can fix all of that. The risk is the voice acting. Ocarina's characters have "
                             "only ever spoken in text boxes, and hearing Saria or Ganondorf out loud will land differently after 28 years.",
                     "first": "Nothing required. If you want to compare, the original is part of the Nintendo Switch Online "
                              "+ Expansion Pack library.",
                     "first_link": "/in-order/zelda", "first_label": "Where it fits in the Zelda timeline",
                     "caveat": "Switch 2 only. If you played the 2011 3DS version, some of the fixes will be familiar. "
                               "Purists may miss the original's fog and low-poly strangeness."},
                    {"kind": "game", "title": "Metaphor: ReFantazio", "year": 2024, "creator": None,
                     "date": "2026-11-12", "released": "Nintendo Switch 2 · Atlus",
                     "why": "Atlus's 2024 fantasy role-playing game from the team behind Persona, coming to Switch 2: a "
                            "kingdom whose king has been murdered picks his successor by popular vote, and you are a candidate.",
                     "note": "It won three awards at The Game Awards 2024, including best RPG, and it deserved them. The "
                             "election gives a fantasy adventure a modern edge, the turn-based battles are the best Atlus "
                             "has made, and the art direction looks like a medieval manuscript come to life. If you skipped "
                             "it on other machines, a portable version is the ideal way to play an 80-hour game in the "
                             "commute-sized pieces it suits.",
                     "caveat": "Long, with a calendar that makes you choose how to spend each day, which some players love "
                               "and others find stressful. Lots of reading. The Switch 2 port is new, so check reviews for "
                               "how it runs before you buy."},
                    {"kind": "game", "title": "Grand Theft Auto VI", "year": 2026, "creator": None,
                     "date": "2026-11-19", "released": "PlayStation 5 and Xbox Series X|S · Rockstar Games",
                     "why": "Rockstar's return to Vice City and the state of Leonida, a version of Florida, with two leads, "
                            "Lucia and Jason, after two delays and the longest wait between GTA games in the series' history.",
                     "note": "It has been thirteen years since GTA V, which is still selling. Rockstar makes the most "
                             "detailed open worlds in games, and the trailers suggest a Florida satire as sharp as the "
                             "original Vice City. Whether you play it or not, it will be the thing everyone talks about "
                             "for the rest of the year. Our advice is unglamorous: if you are going to buy it, buy it in "
                             "launch week, before the story gets spoiled online.",
                     "first": "Red Dead Redemption 2 (2018) is the best guide to what Rockstar does now: slow, enormous and "
                              "far more interested in its characters than GTA V was.",
                     "caveat": "Graphic violence, drugs, sex and crime as gameplay, which is the series' whole identity. "
                               "There is no PC version at launch. Expect it to need a lot of storage."},
                ],
            },
            {
                "format": "anime",
                "heading": "Four autumn anime to catch up on now",
                "intro": [
                    "Japan's autumn season started at the beginning of October, so by mid-November most shows are halfway "
                    "through their run. That is the best time to start: the duds have shown themselves, and you can binge "
                    "the first half and then watch weekly. All four of these are sequels, which is how it goes this season. "
                    "Each one has an earlier season you can start with.",
                ],
                "picks": [
                    {"kind": "anime", "title": "The Apothecary Diaries", "year": 2023, "creator": None,
                     "date": "2026-10-02", "released": "Crunchyroll · season 3, weekly since October 2; English dub from October 16",
                     "why": "Maomao, a pharmacist's daughter sold into service at the imperial palace, solves poisonings and "
                            "court intrigues with the help of her chemistry and in spite of a beautiful, persistent eunuch.",
                     "note": "It is the best mystery anime of the decade so far: each case is small and clever, and the larger "
                             "story about palace politics creeps up on you. Maomao is a great lead, dry and curious, more "
                             "excited by a new poison than a handsome man. The third season keeps the quality of the first "
                             "two, which is not something you can say about many long-running shows.",
                     "first": "Seasons 1 and 2, 48 episodes in all. They are easy to binge, and the cases are mostly "
                              "self-contained.",
                     "caveat": "The romance moves very slowly, by design. There are references to the pleasure district, "
                               "infant deaths and court violence, handled without being graphic."},
                    {"kind": "anime", "title": "Blue Box", "year": 2024, "creator": None,
                     "date": "2026-10-04", "released": "Netflix · season 2, weekly since October 4",
                     "why": "A high-school badminton player falls for the older basketball star who ends up living in his "
                            "family's house, and both of them train for national tournaments.",
                     "note": "A sports romance where the sport matters. Blue Box is about two people who are both serious about "
                             "something other than each other, and who respect that. The first season built slowly and "
                             "honestly; the second is where the tournaments and the feelings both come to a head. If you "
                             "like your romance kind and unhurried, this is the one.",
                     "first": "Season 1. It takes a few episodes to warm up, so give it four.",
                     "caveat": "Very slow. Anyone hoping for drama or rivalry will find it too gentle. Netflix only."},
                    {"kind": "anime", "title": "Ranma ½", "year": 2024, "creator": None,
                     "date": "2026-10-03", "released": "Netflix · season 3 of the remake, weekly since early October",
                     "why": "MAPPA's remake of Rumiko Takahashi's martial-arts comedy about a boy who turns into a girl "
                            "whenever he is splashed with cold water, and the many fiancées and rivals that causes.",
                     "note": "The remake has been a pleasure: it keeps the slapstick and the absurd rivalries of the 1989 "
                             "series, and the animation makes the fights look like the manga's best pages. It is the "
                             "funniest thing airing this season. Takahashi's world never really changes, which is part "
                             "of the charm; each new season is more of a good thing.",
                     "first": "The first two seasons of the remake. You don't need the 1989 version.",
                     "caveat": "A 1980s comedy at heart, with gender-swap gags and some fan service that haven't all aged "
                               "well. The plot barely moves; it is a sitcom."},
                    {"kind": "anime", "title": "Aoashi", "year": 2022, "creator": None,
                     "date": "2026-10-04", "released": "Crunchyroll · season 2, weekly since October 4",
                     "why": "A raw teenage striker from rural Ehime joins the youth academy of a Tokyo pro club and learns, "
                            "painfully, that he is going to be a full-back.",
                     "note": "The smartest football anime there is. Most sports shows are about special moves; Aoashi is "
                             "about where to stand, when to look up and how to read a game, and it makes that thrilling. "
                             "The first season came out four years ago and ended in the middle of the story, so the "
                             "second has been a long time coming. If you play or coach, you will recognise things.",
                     "first": "Season 1, 24 episodes. It takes about five to really grip.",
                     "caveat": "The opening episodes are rough on the lead, and his family situation is hard to watch. "
                               "Lots of tactical explanation, which you will either love or skip."},
                ],
            },
            {
                "format": "books",
                "heading": "Four books for the long evenings",
                "intro": [
                    "The big November books are mostly series: the end of something, the start of something, or the "
                    "next step in something long. Here are four, from a cheerful science-fiction comedy to a Danish "
                    "novel about a woman stuck in the same day, which publishes, neatly, on November 17.",
                ],
                "picks": [
                    {"kind": "book", "title": "Monsters of Ohio", "year": 2026, "creator": "John Scalzi",
                     "date": "2026-11-03", "released": "Hardcover and ebook · Tor",
                     "why": "A new standalone from John Scalzi, which his publisher calls a heartfelt exploration of a "
                            "tentacular solution to the struggles of the modern world.",
                     "note": "Scalzi is at his best when he puts something huge and ridiculous next to ordinary people and "
                             "lets them be funny about it, as he did with The Kaiju Preservation Society in 2022. A book "
                             "with tentacles and Ohio in the pitch sounds like more of that. It is the book on this list "
                             "you could give anybody, including someone who says they don't read science fiction.",
                     "first": "The Kaiju Preservation Society (2022), if you haven't read it. It is short and very funny.",
                     "caveat": "Scalzi's comedy is quick and chatty, and some readers find the jokes get in the way of the "
                               "stakes. We haven't read this one yet."},
                    {"kind": "book", "title": "The Last King of Faerie", "year": 2026, "creator": "Cassandra Clare",
                     "date": "2026-11-03", "released": "Hardcover and ebook",
                     "why": "The first book of The Wicked Powers, the trilogy Cassandra Clare has written to close out her "
                            "Shadowhunter Chronicles, nearly twenty years after City of Bones.",
                     "note": "For a lot of readers who grew up on The Mortal Instruments, this is the end of a very long "
                             "road. Clare has been building to it across five series, and the Faerie court has been the "
                             "most interesting part of her world since The Dark Artifices. If you are a fan, you have "
                             "already pre-ordered. If you aren't, this is not the place to start.",
                     "first": "The Dark Artifices trilogy, which this follows most directly. New readers should start "
                              "with City of Bones (2007).",
                     "caveat": "Long, with a very large cast, and it assumes you know them. It is the first part of a "
                               "trilogy, so expect a cliffhanger."},
                    {"kind": "book", "title": "Peregrine Hill", "year": 2026, "creator": "Nina de Gramont",
                     "date": "2026-11-10", "released": "Hardcover and ebook",
                     "why": "A historical novel from the author of The Christie Affair: Mariah, trapped in a wealthy, gilded "
                            "marriage, finds an unexpected ally in her maid.",
                     "note": "The Christie Affair (2022) was a smart, twisty take on Agatha Christie's real eleven-day "
                             "disappearance, and de Gramont is good at women who have to plan their way out of rooms they "
                             "can't simply leave. A wife and her maid on the same side is a set-up with a lot of tension "
                             "in it. It is the most likely book here to become a book-club pick.",
                     "first": "The Christie Affair, for a sense of how she writes.",
                     "caveat": "We know the premise and not much else. Expect the slow, domestic pace of a historical "
                               "drama more than a thriller's speed."},
                    {"kind": "book", "title": "On the Calculation of Volume V", "year": 2026, "creator": "Solvej Balle",
                     "date": "2026-11-17", "released": "Paperback · New Directions",
                     "why": "The fifth volume of Solvej Balle's Danish series about Tara Selter, a dealer in antique books "
                            "who wakes up every morning on November 18.",
                     "note": "The first volume was shortlisted for the International Booker Prize in 2025, and the series "
                             "has become one of the literary events of the decade: a time loop told with no tricks, just a "
                             "woman noticing how a single day behaves when she lives it hundreds of times. It is slow, "
                             "careful, oddly funny, and it gets under your skin. Publishing it the day before November 18 "
                             "is a nice touch.",
                     "first": "Start with On the Calculation of Volume I. The volumes are short, around 170 pages each, "
                              "but they need to be read in order.",
                     "caveat": "Almost nothing happens, on purpose. If you want the time loop to be solved or explained, "
                               "this is not that book."},
                ],
            },
        ],
        "also": [
            ("How to Rob a Bank (November 13, in theaters).", "David Leitch, who made Bullet Train and The Fall Guy, "
             "with Nicholas Hoult and Zoë Kravitz as bank robbers who livestream their heists. Rated R, and likely "
             "the most fun film of the month if you want something loud."),
            ("Paper Tiger (November 13, limited release).", "James Gray directing Miles Teller and Adam Driver. Gray's "
             "films rarely play wide; watch for it if you liked Armageddon Time."),
            ("The Cat in the Hat (November 6) and Focker-in-Law (November 25).", "An animated Dr. Seuss with Bill Hader "
             "as the Cat, and the first Meet the Parents film in 16 years, with Ben Stiller, Robert De Niro, Owen Wilson "
             "and Ariana Grande. Both are built for families who agree on nothing else."),
            ("The Lord of the Rings: The Rings of Power, season 3 (November 11, Prime Video).", "The show improved in its "
             "second season. Our Lord of the Rings in order guide explains where it fits."),
            ("Percy Jackson and the Olympians, season 3 (November 20, Disney+).", "The Titan's Curse, and the series' "
             "best chance yet to beat the books' momentum."),
            ("Secret Service (November 22, MGM+).", "Gemma Arterton as an MI6 officer who suspects a senior British "
             "politician of being a Russian asset, adapted from Tom Bradby's novel. Five episodes."),
            ("Pikmin 4: Switch 2 Edition and Stellar Blade on Switch 2 (November 12 and early November).", "Two very "
             "good games getting new versions. Pikmin 4 is the one to play with children over the holiday."),
            ("Sonic Pico Park (November 12).", "A Sonic version of the cooperative puzzle game Pico Park, where the "
             "fun is shouting at each other on the same sofa. Good for Thanksgiving."),
            ("Birth of the Witch by Nora Roberts (November 17).", "The first book in a new trilogy about witches and "
             "reincarnation, for readers who like Roberts' long fantasy series."),
            ("The Wrath Gods Reap by Abigail Owen (November 17).", "The end of the trilogy that began with The Games "
             "Gods Play, for romantasy readers who have been waiting."),
        ],
        "plan_heading": "A plan for the month",
        "plan": [
            "If you only make one trip to the cinema, make it Godzilla Minus Zero in the first two weeks, while it still "
            "has the big screens. Save The Hunger Games for a group outing on the weekend of the 20th, and Cliff Booth "
            "for the IMAX window over Thanksgiving if one is near you; otherwise wait for Netflix on December 23.",
            "For games, play the Ocarina remake first and finish it before November 19, because once Grand Theft Auto "
            "VI is out, it will take every free evening you give it. For television, start Dig or The Greatest now and "
            "save The Altruists for a weekend; limited series are best in two or three sittings.",
            "And keep one quiet evening for a book. The month gets loud. The time-loop novel or the Scalzi will "
            "both make a good counterweight to all the noise.",
        ],
        "related": [
            ("The Hunger Games in order", "/in-order/hunger-games"),
            ("The Legend of Zelda in order", "/in-order/zelda"),
            ("November's Discover edition: The long way round", "/discover/monthly/november-2026"),
            ("Holiday picks for Thanksgiving and the winter break", "/holidays"),
            ("The best games of 2026 so far", "/best-of/2026/games"),
        ],
        "sources": [
            ("Sweety High: the biggest movies coming to theaters in November 2026", "https://www.sweetyhigh.com/read/the-biggest-movies-coming-to-theaters-in-november-2026"),
            ("Dread Central: Godzilla Minus Zero stomps into theaters November 2026", "https://www.dreadcentral.com/news/553528/godzilla-minus-zero-stomps-into-theaters-november-2026"),
            ("Loud and Clear Reviews: new shows to stream in November 2026", "https://loudandclearreviews.com/november-2026-shows-stream/"),
            ("The TV Cave: November 2026 streaming guide", "https://www.thetvcave.com/post/november-2026-streaming-guide"),
            ("VGC: video game release dates for 2026", "https://www.videogameschronicle.com/guide/upcoming-game-release-dates-schedule/"),
            ("GamesRadar+: new games release dates", "https://www.gamesradar.com/video-game-release-dates/"),
            ("Engadget: the Ocarina of Time remake arrives November 5", "https://engadget.com/2252620/switch-2-remake-of-legend-of-zelda-ocarina-of-time-arrives-november-5"),
            ("Shacknews: GTA 6 still on track for November 2026", "https://www.shacknews.com/article/147710/gta-6-release-date-not-delayed"),
            ("PrimeTime Anime: fall 2026 premiere calendar", "https://primetimeanime.com/blog/fall-anime-2026"),
            ("Final Weapon: The Apothecary Diaries season 3 dub date", "https://finalweapon.net/2026/10/15/the-apothecary-diaries-season-3-english-dub-premieres-on-october-16/"),
            ("Time Out: the most anticipated books of November 2026", "https://www.timeout.com/usa/news/the-10-most-anticipated-books-coming-out-in-november-2026-102926"),
            ("The Bookish Bulletin: most anticipated November 2026 books", "https://www.thebookishbulletin.com/blog/most-anticipated-november-2026-books"),
        ],
    },
    "winter-2026-27": {
        "name": "Winter 2026-27 releases worth waiting for",
        "period": "December 2026 to February 2027",
        "search_title": "Winter 2026-27 releases: Dune: Part Three, Harry Potter, Fable and more worth it",
        "summary": ("The December to February releases we would plan around, from Dune: Part Three and the Harry "
                    "Potter series to Fable and Persona 4 Revival, with what to catch up on first."),
        "published": "2026-11-01",
        "reviewed": "2026-11-01",
        "starts": "2026-12-01",
        "ends": "2027-02-28",
        "lead": [
            "Winter has an odd shape. December is packed, because everyone wants the Christmas holidays, and this "
            "year two of the biggest films of the decade open on the same day. Then January goes quiet in theaters "
            "and loud everywhere else: it is when publishers put out the games they didn't want buried under the "
            "holiday rush, when the streaming services launch the series they are proudest of, and when the anime "
            "season resets.",
            "This guide covers December 1 to the end of February. We kept to releases with a firm date, which ruled "
            "out a few big names that are still listed only as 2027. For each pick we say why it's on our list and "
            "who should wait, and we suggest what to catch up on now, while the evenings are long and there's time. "
            "None of these are out as we write, so treat the opinions as our best guess, and check the date at the "
            "top: we will update the guide as release dates move.",
        ],
        "sections": [
            {
                "format": "movies",
                "heading": "Four films, two of them on the same Friday",
                "intro": [
                    "December 18 is the day people have been calling Dunesday: Dune: Part Three and Avengers: Doomsday "
                    "open against each other, and Jumanji moved to Christmas Day to keep out of their way. After that, "
                    "the best of the winter arrives in January and February, including the first Narnia film since 2010.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Dune: Part Three", "year": 2026, "creator": "Denis Villeneuve",
                     "date": "2026-12-18", "released": "In theaters and IMAX · Warner Bros. and Legendary",
                     "why": "Denis Villeneuve's third Dune film, adapted from Frank Herbert's Dune Messiah: Paul Atreides "
                            "(Timothée Chalamet) is emperor, his holy war has spread across the universe, and Chani "
                            "(Zendaya) is the only one who still sees him clearly.",
                     "note": "Dune Messiah is the book where Herbert tells you what he thought of his own hero. It is short, "
                             "talky and full of plots against a man who can see the future and hates what he sees. Part "
                             "Two's ending, with Chani walking away, already pointed this way, which suggests Villeneuve "
                             "understood the book. It is a smaller, sadder story than the first two films, and we think "
                             "that could make it the best of the three. See it in IMAX if you can.",
                     "first": "Rewatch Part Two, and read Dune Messiah if you have a weekend: it is about 250 pages, far "
                              "shorter than Dune.",
                     "first_link": "/in-order/dune", "first_label": "The Dune films and books in order",
                     "caveat": "Expect a darker, more political film than Part Two, with fewer sandworm set pieces. If "
                               "you wanted Paul to be the hero, the book's answer is no."},
                    {"kind": "movie", "title": "Avengers: Doomsday", "year": 2026, "creator": "Joe and Anthony Russo",
                     "date": "2026-12-18", "released": "In theaters · Marvel Studios",
                     "why": "The Russo brothers return to direct the Avengers against Doctor Doom, played by Robert "
                            "Downey Jr., with the Fantastic Four and the Thunderbolts joining the team.",
                     "note": "Marvel's recent films have been uneven, and the studio has said openly that it made too many. "
                             "But the Russos made Infinity War and Endgame, still the high point of the whole project, and "
                             "Downey as a villain is the kind of risk that either works completely or doesn't at all. We "
                             "would go for the spectacle and the crowd. Opening weekend audiences for a Russo Avengers "
                             "film are part of the show.",
                     "first": "The Fantastic Four: First Steps and Thunderbolts* (both 2025) are the two that matter most. "
                              "You can skip almost everything else.",
                     "caveat": "A great deal of homework if you stopped watching after Endgame, and it is the first half "
                               "of a story that finishes in Secret Wars, so the ending won't be an ending."},
                    {"kind": "movie", "title": "Children of Blood and Bone", "year": 2027, "creator": "Gina Prince-Bythewood",
                     "date": "2027-01-15", "released": "In theaters · Paramount",
                     "why": "Tomi Adeyemi's fantasy novel, set in a West African-inspired kingdom where magic has been "
                            "stamped out, directed by Gina Prince-Bythewood with Thuso Mbedu, Amandla Stenberg, Damson "
                            "Idris, Cynthia Erivo, Idris Elba and Viola Davis.",
                     "note": "The book was a huge young-adult hit in 2018, and the film has spent years in development. "
                             "Prince-Bythewood made The Woman King, which had some of the best large-scale fight "
                             "choreography of the decade and starred Mbedu, so she is a good match for a story built on "
                             "chases and battles. A cast this strong in January, usually a dumping ground for studio "
                             "leftovers, is the reason it is on this list.",
                     "first": "Read the novel, the first of a trilogy. It is about 530 pages and moves quickly.",
                     "caveat": "Young-adult fantasy, with a love story the book's fans argue about. It will likely be the "
                               "first part of a series, so expect loose ends."},
                    {"kind": "movie", "title": "Narnia: The Magician's Nephew", "year": 2027, "creator": "Greta Gerwig",
                     "date": "2027-02-12", "released": "In theaters for at least 45 days, then on Netflix",
                     "why": "Greta Gerwig adapts the Narnia prequel, in which two London children, Digory and Polly, stumble "
                            "into other worlds and watch Narnia being sung into existence, with Carey Mulligan, Daniel "
                            "Craig, Emma Mackey and Meryl Streep among the cast.",
                     "note": "Netflix moved this from Thanksgiving to February to give it a full theatrical run, the first "
                             "time the service has done that with one of its films, which tells you how much it believes "
                             "in it. The Magician's Nephew is the strangest Narnia book: a dying world, a wicked queen "
                             "waking up, a lamppost growing out of the ground. Gerwig is very good with children who feel "
                             "like real children, and this book needs exactly that.",
                     "first": "Read The Magician's Nephew. It is about 200 pages, and it explains the lamppost, the "
                              "wardrobe and the White Witch.",
                     "caveat": "Christian allegory runs through the whole series and is especially plain at the end of this "
                               "book. Younger children may find the dead world of Charn frightening."},
                ],
            },
            {
                "format": "tv",
                "heading": "Four series for the long nights",
                "intro": [
                    "One series dominates the season: HBO's Harry Potter starts on Christmas Day. January brings an "
                    "adaptation of the book that invented cyberpunk, and two good shows return.",
                ],
                "picks": [
                    {"kind": "tv", "title": "Harry Potter", "year": 2026, "creator": None,
                     "date": "2026-12-25", "released": "HBO and HBO Max · season 1, Harry Potter and the Philosopher's Stone",
                     "why": "HBO's series retelling the seven Harry Potter books, one season per book, starting on "
                            "Christmas Day with Dominic McLaughlin as Harry and John Lithgow as Dumbledore.",
                     "note": "The obvious question is why remake films that are still on television every Christmas. The "
                             "answer is time. The first film had to drop a lot of the book to fit in two and a half hours, "
                             "and a season of television can keep Peeves, the full Quidditch matches and the slow, odd "
                             "pleasure of the first term at Hogwarts. Francesca Gardiner, a writer on Succession, runs "
                             "the show, and Mark Mylod, who directed many of Succession's best episodes, directs. If it "
                             "works, it will be the family show of the decade.",
                     "first": "Reread the first book with your children, if you have them. It is the shortest of the seven.",
                     "first_link": "/in-order/harry-potter", "first_label": "Harry Potter in order",
                     "caveat": "J.K. Rowling is an executive producer, and some viewers will skip the series because of her "
                               "views. Child actors growing up over a decade of production is a real risk."},
                    {"kind": "tv", "title": "Neuromancer", "year": 2027, "creator": None,
                     "date": "2027-01-22", "released": "Apple TV",
                     "why": "An adaptation of William Gibson's 1984 novel about Case (Callum Turner), a burned-out hacker "
                            "hired for one last job inside the networked world Gibson called cyberspace.",
                     "note": "Neuromancer made the word cyberspace famous and set the look of science fiction since: The "
                             "Matrix, Ghost in the Shell and every neon-lit city in a game owe it something. People have "
                             "called it unfilmable for forty years. Television suits it better than a film would, because "
                             "the book is a heist with a long set-up. Apple has had a strong run with ambitious science "
                             "fiction lately, and that is the reason we are hopeful.",
                     "first": "Read the novel. It is under 300 pages, though the prose is dense and the first chapter "
                              "throws you in. Push through it.",
                     "caveat": "The book's future looks dated in places, and a faithful version may too. Expect violence "
                               "and drug use."},
                    {"kind": "tv", "title": "Bad Monkey", "year": 2024, "creator": None,
                     "date": "2026-12-02", "released": "Apple TV · season 2",
                     "why": "Vince Vaughn returns as Andrew Yancy, a demoted Florida detective who can't stop investigating "
                            "things nobody asked him to, in Bill Lawrence's comedy-crime series.",
                     "note": "The first season, adapted from Carl Hiaasen's novel, was one of the most enjoyable surprises "
                             "of 2024: a murder mystery in the Florida Keys with a dry narrator, a monkey and a lot of "
                             "terrible people getting what they deserve. Bill Lawrence, who made Scrubs, Ted Lasso and "
                             "Shrinking, is good at shows that are funny and kind without going soft. If December gets "
                             "too much, this is the easy one.",
                     "first": "Season 1, ten episodes.",
                     "caveat": "The first season used up Hiaasen's book, so season 2 is new material. Some violence and "
                               "strong language."},
                    {"kind": "tv", "title": "Common Side Effects", "year": 2025, "creator": None,
                     "date": "2027-01-24", "released": "Adult Swim · season 2, then on HBO Max",
                     "why": "An animated conspiracy thriller about two old school friends who find a mushroom that might "
                            "cure every disease, and the drug companies and government agents who want it gone.",
                     "note": "The best animated series of 2025 that most people didn't watch. It is funny, and it is also "
                             "a proper thriller about health care and greed, drawn in a soft, "
                             "strange style that makes the violence hit harder. The first season left a lot open, "
                             "and the second has the chance to go much bigger.",
                     "first": "Season 1, ten half-hour episodes, an easy weekend.",
                     "caveat": "Adult animation, with violence and drug use. It airs late at night on Adult Swim first, "
                               "so check when the episodes reach streaming."},
                ],
            },
            {
                "format": "games",
                "heading": "Four games, and January is the sweet spot",
                "intro": [
                    "Publishers kept clear of Grand Theft Auto VI, which means the good games came early or are coming "
                    "late. Layton arrives in December. Then Nintendo, Sega and Xbox all line up big releases for "
                    "January and February.",
                ],
                "picks": [
                    {"kind": "game", "title": "Professor Layton and the New World of Steam", "year": 2026, "creator": None,
                     "date": "2026-12-10", "released": "Switch, Switch 2, PlayStation 5 and PC · Level-5",
                     "why": "The first new main Professor Layton game in more than a decade: the gentleman puzzle-solver "
                            "and his assistant Luke arrive in Steam Bison, an American city full of steam-powered machines.",
                     "note": "The Layton games are a very particular pleasure: a mystery story stopped every few minutes "
                             "for a brain teaser, matchsticks and sliding blocks and logic problems, all wrapped in "
                             "beautiful hand-drawn art and very polite manners. It has been years since the series had a "
                             "proper new entry, and Level-5 delayed it more than once to get it right. It is the best "
                             "game on this list to share with someone who doesn't play games.",
                     "first": "Nothing required. If you want to try the series first, Professor Layton and the Curious "
                              "Village is on phones and tablets.",
                     "caveat": "Puzzle games stand or fall on their puzzles, and a few bad ones can stall you. It is the "
                               "first Layton on PlayStation, so we don't know yet how it plays without a touchscreen."},
                    {"kind": "game", "title": "Metroid Ravenous", "year": 2027, "creator": None,
                     "date": "2027-01-28", "released": "Nintendo Switch 2 · Nintendo",
                     "why": "A new 2D Metroid, announced in September: Samus Aran explores a hostile alien world, slowly "
                            "unlocking the abilities that open the rest of the map.",
                     "note": "Metroid Dread in 2021 was the best 2D Metroid in decades and proved the series still had a "
                             "lot to say. Coming only a few years later, Ravenous suggests Nintendo knows it has an audience "
                             "again. These games are short, tense and replayable, and few series have been copied as much; "
                             "the word Metroidvania exists because of them. Of the January games, this is the one we would "
                             "start first.",
                     "first": "Metroid Dread (2021) on Switch, which plays fine on Switch 2.",
                     "caveat": "Switch 2 only. Metroid games can be hard, with boss fights that will kill you a lot, and "
                               "you will sometimes be lost on purpose."},
                    {"kind": "game", "title": "Persona 4 Revival", "year": 2027, "creator": None,
                     "date": "2027-02-18", "released": "PlayStation 5, Xbox Series X|S and PC · Atlus and Sega · on Game Pass at launch",
                     "why": "A full remake of the 2008 Persona 4, in which a high-schooler spending a year in a small rural "
                            "town investigates murders linked to a television channel that only broadcasts on rainy nights.",
                     "note": "Persona 4 is the warmest game in the series: a murder mystery wrapped around a year of school, "
                             "part-time jobs and friendships that become the real story. The remake follows the success of "
                             "Persona 3 Reload, which brought an old game up to date without losing its heart. If you "
                             "have Game Pass, it costs you nothing to try on day one.",
                     "first": "Nothing required, but if you liked Metaphor: ReFantazio, this is the same team's older work.",
                     "caveat": "Seventy hours or more, with a calendar that asks you to choose how to spend each day. No "
                               "Switch 2 version has been announced."},
                    {"kind": "game", "title": "Fable", "year": 2027, "creator": None,
                     "date": "2027-02-23", "released": "Xbox Series X|S, PlayStation 5 and PC · Playground Games and Xbox Game Studios",
                     "why": "A fresh start for the British fantasy series set in Albion, made by Playground Games, the studio "
                            "behind the Forza Horizon racing games.",
                     "note": "The old Fable games promised a world that reacted to everything you did, and the promise was "
                             "always bigger than the game. That's part of why people love them. Playground has made the "
                             "best open worlds on Xbox for a decade, and the trailers keep the series' daft British humour, "
                             "which was always its best quality. It was delayed from 2026 to keep out of GTA VI's way, and "
                             "it launches on PlayStation the same day as on Xbox.",
                     "first": "Fable II (2008) is the one to play if you want a taste. It is on Xbox through backwards compatibility.",
                     "caveat": "This is Playground's first role-playing game, and nobody outside the studio has played much "
                               "of it. Big launches with this many years of development behind them don't always land."},
                ],
            },
            {
                "format": "anime",
                "heading": "Two winter anime with a lot to prove",
                "intro": [
                    "The winter anime season starts in January, and most announcements give a month, not a day. We "
                    "picked the two biggest returning shows, both of which had a rocky time last season. That is the "
                    "reason to watch: they have something to prove.",
                ],
                "picks": [
                    {"kind": "anime", "title": "Sakamoto Days", "year": 2025, "creator": None,
                     "date": "2027-01-01", "month_only": True, "released": "Netflix · season 2",
                     "why": "The legendary hitman Taro Sakamoto retired, married, got out of shape and opened a corner shop. "
                            "His old world keeps sending people to kill him, and he keeps beating them with whatever is on "
                            "the shelves.",
                     "note": "The manga is one of the best action comics running, with fights that turn a whole shopping "
                             "mall into a weapon. The first anime season didn't always keep up with it, and fans noticed. "
                             "The second season gets into the arcs where the manga really took off. If the animation "
                             "steps up, this is the action show of the winter.",
                     "first": "Season 1 on Netflix, or the manga, which is a fast read.",
                     "caveat": "Lots of comic violence, and a plot that is mostly an excuse for fights. Netflix releases "
                               "episodes weekly, so it isn't a binge until it is over."},
                    {"kind": "anime", "title": "One-Punch Man", "year": 2015, "creator": None,
                     "date": "2027-01-01", "month_only": True, "released": "Season 3, part 2 · J.C.Staff",
                     "why": "Saitama, a hero so strong he wins every fight with one punch and is bored stiff by it, is caught "
                            "up in the war between the Hero Association and the Monster Association.",
                     "note": "We'll be honest: the first half of season three, in late 2025, was a disappointment, with "
                             "animation far below the famous first season. The second half covers the best part of the "
                             "story, though, and the opening song is by JAM Project again. Watch the first episode or two "
                             "before committing.",
                     "first": "Season 1 (2015) is a classic, and twelve episodes. Seasons 2 and 3 are only worth it if you "
                              "are already invested.",
                     "caveat": "If the animation stays where it was, the manga by Yusuke Murata is the better way to read "
                               "this story. Streaming availability varies by region."},
                ],
            },
            {
                "format": "books",
                "heading": "Four books to start in the new year",
                "intro": [
                    "January is the publishers' second Christmas: the big fantasy names come back after the holidays, "
                    "when people have gift cards to spend. Here are four, all in series, and all good in winter.",
                ],
                "picks": [
                    {"kind": "book", "title": "A Court of Forgotten Melody", "year": 2027, "creator": "Sarah J. Maas",
                     "date": "2027-01-12", "released": "Hardcover, ebook and audiobook · Bloomsbury",
                     "why": "The next A Court of Thorns and Roses novel, the seventh in the series: Koschei the Deathless "
                            "threatens Prythian, and the Night Court has to hold together a set of alliances that are "
                            "starting to break.",
                     "note": "Maas is the biggest name in fantasy publishing right now, and her fans will read this the "
                             "day it comes out. Koschei has been lurking at the edges of the series for several books, "
                             "so this is the payoff. The rest of us can take it as a sign that the series is building to "
                             "something rather than circling.",
                     "first": "A Court of Thorns and Roses (2015) if you are new. The second book is where most readers "
                              "get hooked.",
                     "caveat": "Explicit sex scenes, and a long series that assumes you remember all of it. Not for "
                               "younger readers, whatever the shelving in some shops suggests."},
                    {"kind": "book", "title": "The Stars Look Like Home", "year": 2027, "creator": "T. J. Klune",
                     "date": "2027-01-12", "released": "Hardcover and ebook",
                     "why": "A new novel from the author of The House in the Cerulean Sea: when Burke learns that dogs don't "
                            "live forever, he sets off on a journey to do something about it.",
                     "note": "Klune writes the kind of book people press on friends after a hard year: warm, funny, and "
                             "willing to talk about grief without getting gloomy. A story about a dog and how long they "
                             "live is about as direct as he gets. If January is a difficult month for you, this is the "
                             "book on this list for it.",
                     "first": "The House in the Cerulean Sea (2020), if you haven't read him.",
                     "caveat": "It's sentimental, which is the point. Readers who like sharper fiction may find Klune too "
                               "sweet. Bring tissues for the dog."},
                    {"kind": "book", "title": "Emily Wilde's History of Dark Faerie", "year": 2027, "creator": "Heather Fawcett",
                     "date": "2027-01-19", "released": "Hardcover and ebook",
                     "why": "The fourth book about Emily Wilde, a prickly Cambridge scholar of faerie folklore, who follows "
                            "a missing friend into Germany's Black Forest.",
                     "note": "These books are written as Emily's own research journals, and they are a joy: a dry, socially "
                             "hopeless academic, a charming faerie colleague she would rather not admit she likes, and "
                             "folklore that is actually frightening. The Black Forest is the perfect setting for this "
                             "series, and the right book for a snowy weekend.",
                     "first": "Emily Wilde's Encyclopaedia of Faeries (2023). The series needs to be read in order.",
                     "caveat": "A slow-burn romance and a lot of footnoted folklore. The faeries are cruel in the old, "
                               "fairy-tale way, so there's some violence."},
                    {"kind": "book", "title": "The Moth Reborn", "year": 2027, "creator": "Samantha Shannon",
                     "date": "2027-02-25", "released": "Hardcover and ebook · Bloomsbury",
                     "why": "The second-to-last book in Samantha Shannon's Bone Season series, in which clairvoyant Paige "
                            "Mahoney fights an empire that hunts people like her, now as gods walk openly among humans.",
                     "note": "The Bone Season started in 2013 as a dystopian fantasy set in a future London and has grown "
                             "into something much stranger and more ambitious. Shannon also wrote The Priory of the "
                             "Orange Tree, and you can feel that scale here now. With one book left after this, it is "
                             "a good time to catch up.",
                     "first": "The Bone Season (2013). The world-building is heavy at first, and there is a glossary.",
                     "caveat": "Lots of invented slang and a large cast. It's a penultimate book, so it ends on a cliffhanger."},
                ],
            },
        ],
        "also": [
            ("The Further Mis-Adventures of Cliff Booth (December 23, Netflix).", "David Fincher's film from Quentin "
             "Tarantino's script reaches Netflix after its IMAX run. Our November guide has more."),
            ("Jumanji: Open World (December 25, in theaters).", "The third Jumanji with Dwayne Johnson, Kevin Hart, Jack "
             "Black and Karen Gillan, billed as the last. It moved to Christmas to stay out of Dunesday's way."),
            ("The Comeback King and Remain (February 5, in theaters).", "Judd Apatow directs Glen Powell, who co-wrote it, "
             "and M. Night Shyamalan directs Jake Gyllenhaal in a film he co-wrote with Nicholas Sparks, which is a "
             "combination nobody expected."),
            ("Emily in Paris, final season (December 24, Netflix).", "For people who have watched every episode and "
             "won't admit it."),
            ("Only Murders in the Building, season 6 (December 8, Hulu).", "Steve Martin, Martin Short and Selena Gomez, "
             "and another body."),
            ("Dragon Quest Monsters: The Withered World (December 3).", "Monster-collecting from the Dragon Quest series, on "
             "every major platform, for anyone who wants a gentler alternative to Pokémon."),
            ("Rayman Legends Retold (December 3).", "A new version of one of the best 2D platformers ever made, ideal "
             "for two players over the holidays."),
            ("Until Dawn 2 (January 28, PlayStation 5).", "The sequel to Supermassive's choose-who-dies horror game. "
             "Play it with friends shouting advice."),
            ("The Two-Body Problem by Ali Hazelwood (February 2).", "The sequel to The Love Hypothesis, with Olive and "
             "Adam facing the academic job market, which is scarier than any villain."),
            ("The Last Testimony by Veronica Roth (February 2).", "The second book in The Sixth Faction, which brings "
             "back Tris and Four from Divergent."),
        ],
        "plan_heading": "A plan for the winter",
        "plan": [
            "Use December's first two weeks to get ready: rewatch Dune: Part Two, read Dune Messiah if you want to go "
            "in knowing the story, and decide whether you are seeing Doomsday on the 18th as well or saving it for a "
            "quieter weekday. Both will be in theaters for weeks. On Christmas Day, Harry Potter is the obvious thing "
            "to put on once the presents are open.",
            "January is the month for games and books. Start Metroid Ravenous on the 28th, and if you have Game Pass, "
            "keep February 18 free for Persona 4 Revival. Fable comes five days later, so you will have to choose, "
            "or take a very long weekend.",
            "February ends the season with Narnia. Read The Magician's Nephew with a child over the half-term break, "
            "then go to see it together. It's a good way to end a long winter.",
        ],
        "related": [
            ("Dune: the films and books in order", "/in-order/dune"),
            ("Harry Potter in order", "/in-order/harry-potter"),
            ("If you liked Dune", "/if-you-liked/dune"),
            ("Holiday picks for Thanksgiving and the winter break", "/holidays"),
            ("The best movies of 2026 so far", "/best-of/2026/movies"),
        ],
        "sources": [
            ("The A.V. Club: Dune: Part Three and Avengers: Doomsday share December 18", "https://avclub.com/avengers-doomsday-dune-part-three-same-day-release-december-18"),
            ("TheWrap: Jumanji 3 shifts to a Christmas release", "https://www.thewrap.com/creative-content/movies/jumanji-3-new-release-date-christmas/"),
            ("Wikipedia: list of American films of 2027", "https://en.wikipedia.org/wiki/List_of_American_films_of_2027"),
            ("Boxoffice Pro: Netflix moves Narnia to February 2027", "https://www.boxofficepro.com/netflix-moves-narnia-to-february-2027-committing-to-wide-release-and-full-theatrical-window/"),
            ("Engadget: HBO Max's Harry Potter series premieres this Christmas", "https://engadget.com/entertainment/tv-movies/hbo-maxs-harry-potter-series-premieres-this-christmas-202818238.html"),
            ("Apple TV press: Neuromancer at San Diego Comic-Con", "https://www.apple.com/tv-pr/news/2026/07/apple-tvs-highly-anticipated-cyberpunk-series-neuromancer-hacks-into-san-diego-comic-con-with-first-ever-teaser/"),
            ("Den of Geek: TV premiere dates calendar", "https://www.denofgeek.com/tv/tv-premiere-dates-calendar/"),
            ("DIRECTV Insider: TV premiere dates", "https://www.directv.com/insider/tv-premiere-dates/"),
            ("GamingBolt: Professor Layton and the New World of Steam gets December 10 date", "https://gamingbolt.com/professor-layton-and-the-new-world-of-steam-gets-december-10th-release-date"),
            ("Gematsu: Metroid Ravenous announced for Switch 2", "https://www.gematsu.com/2026/09/metroid-ravenous-announced-for-switch-2"),
            ("RPG Site: Persona 4 Revival launches February 18, 2027", "https://www.rpgsite.net/news/20578-persona-4-revival-launches-on-february-18-2027"),
            ("Gematsu: Fable launches February 23, 2027", "https://www.gematsu.com/2026/06/fable-launches-february-23-2027"),
            ("GamesRadar+: new games release dates", "https://www.gamesradar.com/video-game-release-dates/"),
            ("Netflix: Sakamoto Days season 2 returns January 2027", "https://about.netflix.com/news/sakamoto-days-season-2-returns-january-2027"),
            ("Anime Corner: One-Punch Man season 3 cour 2 set for January 2027", "https://animecorner.me/one-punch-man-season-3-cour-2-visual-and-trailer-revealed-sets-january-2027-release/"),
            ("The Bookish Bulletin: most anticipated January 2027 books", "https://www.thebookishbulletin.com/blog/most-anticipated-january-2027-books"),
            ("The Bookish Bulletin: most anticipated February 2027 books", "https://www.thebookishbulletin.com/blog/most-anticipated-february-2027-books"),
        ],
    },
    "winter-2027-anime": {
        "name": "Winter 2027 anime: the new shows worth a first episode",
        "period": "January to March 2027",
        "eyebrow": "ANIME SEASON GUIDE",
        "hub_label": "Winter 2027 anime season",
        "focus": "anime",
        "search_title": "Winter 2027 anime guide: Historie, Hirayasumi, Sekiro, Shangri-La Frontier and more",
        "summary": ("Fourteen winter 2027 anime worth trying, from Historie, Hirayasumi and Sekiro to new seasons "
                    "of Shangri-La Frontier and Mashle, and what to watch first."),
        "published": "2026-11-04",
        "reviewed": "2026-11-04",
        "starts": "2027-01-01",
        "ends": "2027-03-31",
        "lead": [
            "Every January, about fifty new anime series start in Japan within about two "
            "weeks of each other. Most of them air late at night, most of them are 12 or 13 episodes long, and most "
            "of them reach the rest of the world within an hour or two on a streaming service. Nobody can watch all "
            "of them, and the season charts that list every show don't tell you which ones are worth a Thursday "
            "night.",
            "This guide is the short version. We went through the winter 2027 line-up as it stood in early November "
            "and picked fourteen shows: five new adaptations we would start first, five returning series, and four "
            "romances, comedies and family shows. For each one we say where it comes from, where you can watch it if "
            "that has been announced, what to watch or read beforehand, and the thing most likely to put you off. None "
            "of these have aired yet, so these are bets. We say where we're guessing.",
            "A few housekeeping notes. Japanese studios usually announce a month long before they announce a day, so "
            "several picks say \"January 2027\" until the broadcaster fixes a slot, usually in December. Dates are for "
            "the Japanese broadcast; the streaming release outside Japan is normally the same day or the day after. "
            "And two of the biggest returning shows, Sakamoto Days and the second half of One-Punch Man season 3, are "
            "already covered in our broader winter releases guide, so we haven't written them up twice. They are in "
            "the list at the bottom.",
        ],
        "sections": [
            {
                "format": "anime",
                "id": "new",
                "label": "New series",
                "heading": "Five new series to start first",
                "intro": [
                    "Winter is usually a season for sequels, and 2027 is no exception, but the most interesting shows "
                    "this time are adaptations of manga that took years to reach the screen. Two of them, Historie and "
                    "Hirayasumi, are the kind of manga that people press on friends who say they don't read manga. "
                    "We've also included a video game adaptation that will be watched closely, and a rock romance that "
                    "got Nirvana to license a song.",
                ],
                "picks": [
                    {"kind": "anime", "title": "Historie", "year": 2027, "creator": None,
                     "date": "2027-01-01", "month_only": True,
                     "released": "LIDENFILMS · international streaming not announced yet",
                     "why": "Hitoshi Iwaaki's historical manga about Eumenes, a Greek boy of uncertain birth who grows up "
                            "to become the secretary of Alexander the Great and one of the sharpest commanders of his "
                            "age, with Nobunaga Shimazaki in the lead.",
                     "note": "Iwaaki wrote Parasyte, and Historie has the same cool, unsentimental eye: people are clever "
                             "and cruel in about equal measure, and the violence arrives without warning. The manga has "
                             "been running in Kodansha's Afternoon magazine for over twenty years, at a famously slow "
                             "pace, and readers had more or less given up on an adaptation. The early chapters, set "
                             "around the Black Sea and in the city of Cardia long before Alexander appears, are some of "
                             "the best historical fiction in any medium. If LIDENFILMS gets the pacing right, this is the "
                             "show of the season for anyone who likes Vinland Saga.",
                     "first": "Nothing is needed. If you want to read ahead, the manga is on K MANGA, Kodansha's English "
                              "app; the first volume is enough to know whether this is for you.",
                     "caveat": "The manga is not finished and may never be, so the anime will stop somewhere mid-story. "
                               "There is torture and battlefield violence, drawn plainly. We don't know the episode count "
                               "or the streaming service outside Japan yet."},
                    {"kind": "anime", "title": "Hirayasumi", "year": 2027, "creator": None,
                     "date": "2027-01-01", "month_only": True,
                     "released": "NHK General TV · Production +h · co-produced with Viz Media; streaming to be announced",
                     "why": "Hiroto Ikuta is 29, with no girlfriend, no full-time job and no plan, and he has just been "
                            "left a small old house in a Tokyo suburb by an elderly friend. His cousin Natsumi moves in "
                            "to go to art school.",
                     "note": "Keigo Shinzo's manga is about very little and has sold over a million copies anyway: a slow, funny, slightly sad book about people who haven't worked out "
                             "their lives yet, and a man who seems fine with that. It is on NHK, which suits it, and "
                             "Viz Media is a co-producer, which usually means a wide release in English. Yuma Uchida, "
                             "who voices Sunraku in Shangri-La Frontier, plays Hiroto, so you can hear him this winter in "
                             "two shows that couldn't be further apart. Watch it on a weekend morning.",
                     "first": "Nothing. If you watched the 2025 live-action drama on NHK, this is the same story, and the "
                              "manga (from Viz) is worth reading either way.",
                     "caveat": "Nothing happens fast, and some episodes won't feel like they have a plot. If you need "
                               "stakes, this isn't the show. Streaming outside Japan hadn't been named when we wrote this."},
                    {"kind": "anime", "title": "Sekiro: No Defeat", "year": 2027, "creator": None,
                     "date": "2027-01-01", "month_only": True,
                     "released": "Crunchyroll, weekly · eight episodes · Qzil.la, produced by ARCH",
                     "why": "An eight-episode series set in the world of FromSoftware's 2019 game Sekiro: Shadows Die "
                            "Twice, in which the shinobi Wolf protects the young Divine Heir as Genichiro Ashina turns to "
                            "forbidden powers to save his clan.",
                     "note": "Sekiro won Game of the Year at The Game Awards in 2019 and is the most cinematic thing "
                             "FromSoftware has made: one hero, one castle, sword fights that are about rhythm more than "
                             "stats. That makes it a better candidate for an anime than Dark Souls or Elden Ring, which "
                             "tell their stories in item descriptions. Kenichi Kutsuna directs, Daisuke Namikawa voices "
                             "Wolf and Kenjiro Tsuda plays Genichiro. Crunchyroll has it worldwide outside a handful of "
                             "countries, and at eight episodes it asks for very little.",
                     "first": "You don't need to have played the game, and the series doesn't seem to expect it. If you "
                              "have, it is worth knowing that this is a retelling of the game's story, so you'll know "
                              "where it is going.",
                     "caveat": "The series is re-edited from a theatrical film, with added scenes, so it may feel more like "
                               "a long film cut into parts than a TV show. Qzil.la has used AI tools on past projects; "
                               "the production committee has said no generative AI is used here. Expect blood."},
                    {"kind": "anime", "title": "Bless", "year": 2027, "creator": None,
                     "date": "2027-01-01", "month_only": True,
                     "released": "Fuji TV's Noitamina block · A-1 Pictures · Crunchyroll",
                     "why": "Yukino Sonoyama's fashion manga about Aia, a boy everyone said was born to be a model, and "
                            "Jun, a girl who was bullied for her freckles, and what they do with the world of makeup "
                            "and fashion shows.",
                     "note": "The director, Shotaro Kitamura, made Makeine: Too Many Losing Heroines!, one of the best-"
                             "looking romantic comedies of 2024, and Bless is the kind of story that lives or dies on how "
                             "it looks. It is airing in Noitamina, Fuji TV's late-night slot for shows aimed at adults "
                             "rather than teenage boys, which has given us Honey and Clover, Mononoke and Anohana. "
                             "There are not many anime about craft and work this winter, and this is the best bet.",
                     "first": "Nothing. The manga is published in English by Kodansha USA if you would rather read it.",
                     "caveat": "We know the premise, the staff and a long cast list, and not much about the tone. Shows "
                               "about the fashion industry can get preachy about beauty. We'll know after two episodes."},
                    {"kind": "anime", "title": "The Guy She Was Interested In Wasn't a Guy at All", "year": 2027,
                     "creator": None, "date": "2027-01-08",
                     "released": "NTV's FuraAni block, 11 p.m. · CloverWorks · Crunchyroll",
                     "why": "Aya, a high schooler who loves rock music, falls for the stylish person who works at her "
                            "favourite CD shop. It turns out to be Mitsuki, a girl in her class, who is too nervous to "
                            "tell her.",
                     "note": "Sumiko Arai's manga started as short comics posted on Twitter and won the web manga "
                             "category of the Next Manga Awards in 2023. It is a sweet, funny romance between two girls "
                             "who bond over old records, and it takes the music seriously. The opening theme is Nirvana's "
                             "\"Breed\", which Dave Grohl himself announced, and that alone tells you how much effort is "
                             "going into this. CloverWorks made Bocchi the Rock!, so they know how to animate a guitar.",
                     "first": "Nothing. The manga is published in English by Yen Press.",
                     "caveat": "It is a light, low-stakes romance. If you want drama, this isn't it. A show about two girls "
                               "in love will also get some ugly comments online; the manga handles it gently."},
                ],
            },
            {
                "format": "anime",
                "id": "returning",
                "label": "Returning",
                "heading": "Five returning shows, and how far behind you can be",
                "intro": [
                    "A new season of a show you liked is the easiest decision of the winter, and the hardest one if you "
                    "dropped it halfway through. For each of these we say what the earlier seasons were like and how much "
                    "you need to have seen. Two of them, Shangri-La Frontier and The Fable, have firm dates; the others "
                    "are listed for January.",
                ],
                "picks": [
                    {"kind": "anime", "title": "Shangri-La Frontier", "year": 2023, "creator": None,
                     "date": "2027-01-10",
                     "released": "MBS and TBS, 5 p.m. Sundays · C2C · season 3, two cours in a row; season 2 is on Crunchyroll",
                     "why": "Rakuro Hizutome, known online as Sunraku, spends his free time beating the worst, buggiest "
                            "VR games ever made. Then he tries the best one, Shangri-La Frontier, and finds that "
                            "everything bad games taught him is useful.",
                     "note": "This is the most fun pure video-game anime on air: no trapped-in-the-game panic, just "
                             "someone who loves playing and is very good at it. The first two seasons ran for two cours "
                             "each, and this one is also two cours back to back, which means six months straight in a "
                             "Sunday early-evening slot on MBS and TBS. The announcement says the season continues the Galaxia Heroes: Chaos storyline.",
                     "first": "Seasons 1 and 2, which is around 50 episodes. It takes a few episodes to get going; by the first "
                              "big boss fight you will know whether it is for you.",
                     "caveat": "It's long, and the story leans on game mechanics: menus, stats, skill names. If that bores "
                               "you in other shows, it will here. We don't know the episode count yet."},
                    {"kind": "anime", "title": "Mashle: Magic and Muscles", "year": 2023, "creator": None,
                     "date": "2027-01-01", "month_only": True,
                     "released": "Crunchyroll, worldwide outside Japan and China · A-1 Pictures · season 3",
                     "why": "In a world where everyone uses magic, Mash Burnedead can't cast a single spell. He gets into "
                            "magic school anyway, and gets through every problem by being absurdly strong.",
                     "note": "Mashle is a parody of magic-school stories that works because it never winks: Mash answers "
                             "every spell with his fists, and nobody around him can believe it. Season 2's opening, Creepy "
                             "Nuts' \"Bling-Bang-Bang-Born\", was one of the biggest anime songs in years. Season 3 covers "
                             "the Divine Visionary final exam, where the story stops being a series of jokes and starts "
                             "heading for its ending. The manga finished in 2023 after 18 volumes, so there is a complete "
                             "story to adapt.",
                     "first": "Seasons 1 and 2, 24 episodes in all. You can't really start here.",
                     "caveat": "The joke is the same joke, told for three seasons. If season 2 started to wear on you, the "
                               "final exam arc is more action than comedy. A new character designer is in charge this "
                               "season, so expect the faces to look a little different."},
                    {"kind": "anime", "title": "Akane-banashi", "year": 2026, "creator": None,
                     "date": "2027-01-01", "month_only": True,
                     "released": "Japan in January · ZEXCS · Netflix date not set (season 1 is on Netflix)",
                     "why": "Akane Osaki trains to become a rakugo storyteller, the traditional Japanese art of one person "
                            "kneeling on a cushion and playing every part, after her father was thrown out of the craft "
                            "during the exam for his promotion.",
                     "note": "It sounds like the least promising idea for a Shonen Jump series, and it is one of the best "
                             "the magazine has run in years, because it treats a performance like a fight: the tension, "
                             "the audience, the moment it turns. Season 2 starts the apprentice training arc, with a new "
                             "cast of older performers that includes Tomokazu Seki and Shinichiro Miki. Ayumu Watanabe, "
                             "who made the film Children of the Sea, directs.",
                     "first": "Season 1 on Netflix, which has an English dub. If you haven't seen it, a Netflix release of "
                              "season 2 probably won't arrive until after the Japanese broadcast, so there is time.",
                     "caveat": "Rakugo is about words, and subtitles can only do so much with wordplay. Outside Japan you "
                               "may be waiting a few weeks, as nothing has been announced."},
                    {"kind": "anime", "title": "The Fable", "year": 2024, "creator": None,
                     "date": "2027-01-09",
                     "released": "NTV, late night · Tezuka Productions · season 2; season 1 is on Disney+ and, in the US, Hulu",
                     "why": "Akira Sato, the best hitman in Japan, is told by his boss to spend a year in Osaka living an "
                            "ordinary life and not killing anyone, and to keep it up when the people around him make it "
                            "very hard.",
                     "note": "The first season, in 2024, was a nice surprise: a crime show that is mostly about a "
                             "frighteningly competent man trying to be bad at things on purpose, with sudden, precise "
                             "violence when he can't avoid it. Okitsu's flat delivery as Akira is very funny. Season 2 "
                             "keeps the director, Ryosuke Takahashi, and adds Koichi Yamadera and Takanori Hoshino to the "
                             "cast, with a new composer, Yo Tsuji.",
                     "first": "Season 1, two cours and 25 episodes. The 2019 and 2021 live-action films tell the same early story, so "
                              "you can skip those.",
                     "caveat": "It's slow, and plenty of episodes are about part-time jobs and parakeets. Some viewers found "
                               "season 1's quieter middle stretch hard going. If you hated that, more of the same won't help."},
                    {"kind": "anime", "title": "Marriagetoxin", "year": 2025, "creator": None,
                     "date": "2027-01-01", "month_only": True,
                     "released": "Tuesdays, 11 p.m. in Japan · BONES Film · season 2; season 1 is on Crunchyroll",
                     "why": "Hikaru Gero, an assassin from a family of poison users, has to get married to keep his sister "
                            "from being forced to produce the next heir. He hires a professional marriage swindler, "
                            "Kinosaki, to teach him how to date.",
                     "note": "Season 1, in spring 2025, was better than its premise: a show that is half dating comedy, "
                             "half assassin fights, and handles both. The best episodes are the dates, where a man who "
                             "kills for a living tries to work out small talk. BONES Film is animating again, with the "
                             "same director, Motonobu Hori, and the staff said at New York Comic Con that a new marriage "
                             "prospect is coming for Gero.",
                     "first": "Season 1, 13 episodes. You need it.",
                     "caveat": "Some of the comedy is about appearances and gender and will not be to everyone's taste. "
                               "The fights get gruesome, because the poison isn't a metaphor."},
                ],
            },
            {
                "format": "anime",
                "id": "lighter",
                "label": "Romance, comedy and family",
                "heading": "Four for a lighter evening",
                "intro": [
                    "Not everything has to be a two-cour epic. These four are romances, comedies or family shows, the "
                    "kind you watch with dinner. One of them is a shojo manga that finished in 2013 and is only now "
                    "getting an anime.",
                ],
                "picks": [
                    {"kind": "anime", "title": "Dengeki Daisy", "year": 2027, "creator": None,
                     "date": "2027-01-01", "month_only": True,
                     "released": "Studio DEEN · two cours · Crunchyroll",
                     "why": "After her brother dies, 16-year-old Teru Kurebayashi is left a phone that connects her to "
                            "\"Daisy\", an anonymous hacker who looks after her. She suspects the rude young janitor at "
                            "her school knows more than he lets on.",
                     "note": "Kyousuke Motomi's manga ran from 2007 to 2013 and was a Shojo Beat favourite in English, "
                             "with a mystery that kept readers guessing for sixteen volumes. Its readers are now adults, "
                             "and two cours is enough to tell the whole story properly, which is not something many shojo "
                             "adaptations get. Studio DEEN made the first Fruits Basket and Vampire Knight anime, so this is familiar ground.",
                     "first": "Nothing. Viz published all 16 volumes in English, and they are easy to find secondhand.",
                     "caveat": "The romance is between a high school girl and an adult man. The manga is careful about it, "
                               "but it is the reason some people won't watch, and that's fair."},
                    {"kind": "anime", "title": "Now That We Draw", "year": 2027, "creator": None,
                     "date": "2027-01-01", "month_only": True,
                     "released": "ROLL2 · Seven Seas publishes the manga in English",
                     "why": "Two young manga creators, a writer and an artist, both get told by their editors that their "
                            "romance scenes are unconvincing. So they start fake-dating for research.",
                     "note": "A fake relationship is the oldest romantic comedy setup there is, and this one gives it a "
                             "good reason: they are doing it for the work, and they are each a bit too proud to say it's "
                             "working. The manga, by Kyu Takahata and Yuwji Kaba, is from Seven Seas in English. It is "
                             "also a decent look at how manga gets made, with deadlines and editors who mean well.",
                     "first": "Nothing.",
                     "caveat": "Romantic comedies live on chemistry, and we've only seen a teaser. Streaming outside Japan "
                               "hasn't been announced. Wait for two episodes."},
                    {"kind": "anime", "title": "Welcome to Demon School! Iruma-kun: IruMafia Edition", "year": 2027,
                     "creator": None, "date": "2027-01-04",
                     "released": "NHK · Tatsunoko Production · 12 episodes",
                     "why": "A what-if spin-off of Iruma-kun: here, Iruma is a poor boy in the slums who gives his last "
                            "piece of bread to an injured old man, who turns out to be Don Sullivan, head of the Babyl "
                            "mafia, and adopts him as his heir.",
                     "note": "The main Iruma-kun series is one of the kindest shows on television, a school comedy about a "
                             "boy who is better at being liked than he knows. The spin-off keeps the same voice cast and "
                             "swaps the school for a crime family played for laughs. Twelve episodes on NHK on a Monday "
                             "is the right size for it, and it is the safest pick here for watching with older children.",
                     "first": "The first season of the main series helps you get the jokes, because the spin-off puts every "
                              "familiar character in a new role. It isn't required.",
                     "caveat": "If you don't know the main show, a lot of the humour is in seeing who plays which mobster. "
                               "Streaming outside Japan hasn't been confirmed for the spin-off."},
                    {"kind": "anime", "title": "Yaiba: Samurai Legend", "year": 2025, "creator": None,
                     "date": "2027-01-09",
                     "released": "YTV and NTV, 5:30 p.m. Saturdays · WIT Studio · season 2; season 1 is on Netflix",
                     "why": "WIT Studio's remake of Gosho Aoyama's 1988 manga about Yaiba Kurogane, a wild boy who grew up "
                            "training in the jungle and wants to be the greatest samurai in Japan. Season 2 is the Kaguya arc, with "
                            "Ami Koshimizu as the new villain.",
                     "note": "Aoyama is the author of Detective Conan, and Yaiba was the series before it: a goofy, "
                             "energetic adventure with talking animals and magic swords. The 2025 remake looks great "
                             "and plays like a Saturday-morning cartoon in the best sense. It is the easiest show on this "
                             "list to put on with a ten-year-old.",
                     "first": "Season 1 on Netflix. The 1990s anime is hard to find and you don't need it.",
                     "caveat": "It's a kids' show at heart, with cartoon violence and very broad jokes. If you came for "
                               "WIT's Attack on Titan, adjust your expectations."},
                ],
            },
        ],
        "also": [
            ("Sakamoto Days, season 2 (January, Netflix).", "The retired hitman turned shopkeeper is back. We wrote it up "
             "in our winter releases guide, along with what went wrong in season 1."),
            ("One-Punch Man, season 3 part 2 (January).", "Thirteen episodes, the second half of the war with the Monster "
             "Association. Also in the winter guide, with an honest note about the animation."),
            ("Golden Kamuy, the Runaway Train arc.", "The last arc of the final season was announced in March for "
             "\"this winter\", and season charts list it for winter 2027. The format and date haven't been confirmed, but "
             "if you watched the final season in January 2026, this is the ending."),
            ("The World's Finest Assassin Gets Reincarnated in Another World as an Aristocrat, season 2 (January).",
             "The most-followed show on LiveChart's winter chart when we checked, from SILVER LINK. If you liked season 1's cold, clever hero, it's "
             "more of that."),
            ("Medaka Kuroiwa Is Impervious to My Charms, season 2 (January).", "A school comedy about a girl who can "
             "charm anyone except the one boy she wants. Light and silly, and easy to watch two episodes at a time."),
            ("Love Live! Hasunosora Jogakuin School Idol Club (January 10).", "Seven episodes for the Hasunosora "
             "school idols. For Love Live! fans."),
            ("Bride of the Barrier Master (January).", "A romance from TROYCA about a twin from a lesser branch of a "
             "family who catches the eye of the clan head. Listed with a Netflix page."),
            ("Though I Am an Inept Villainess, part 2 (January).", "The second cour of Doga Kobo's body-swap "
             "palace drama, on Crunchyroll."),
        ],
        "plan_heading": "A plan for the season",
        "plan": [
            "Use December to catch up. If you only have time for one returning show, watch season 1 of The Fable or "
            "Marriagetoxin; both are short enough to finish over the holidays. Shangri-La Frontier is closer to fifty "
            "episodes, so start it now or save it for the spring, when season 3 is halfway through.",
            "The first full week of January is when most of these start. Iruma-kun's spin-off begins on Monday the "
            "4th, The Guy She Was Interested In Wasn't a Guy at All on Friday the 8th, Yaiba and The Fable on "
            "Saturday the 9th, and Shangri-La Frontier on Sunday the 10th. The shows marked January will fill in "
            "the gaps as their dates are set. Give every new show two episodes; anime first episodes are often "
            "setup, and the second is a better test.",
            "By the end of January, cut the list down to three or four. A season is twelve weeks long, and the shows "
            "you are still watching in March are the ones worth telling people about. Keep an eye on Historie and "
            "Hirayasumi, which are the ones we think people will still be talking about next winter.",
        ],
        "method": [
            "Prepared by OmniTrackr with AI assistance and reviewed by the site owner before publishing. None of these "
            "shows had aired when we wrote about them, so this is a guide to what we think is worth trying, not a set "
            "of reviews. We worked from the season charts on LiveChart and AnimeSchedule and the studio and "
            "streaming announcements listed below, and we picked shows we would recommend to a friend, with an honest "
            "note on who should skip them.",
            "Anime dates are less fixed than film dates. Where a studio has only announced a month, we say January "
            "2027 and update the page when the day is set. Streaming services outside Japan are named only when they "
            "have been announced.",
        ],
        "related": [
            ("If you liked Frieren", "/if-you-liked/frieren"),
            ("If you liked Jujutsu Kaisen", "/if-you-liked/jujutsu-kaisen"),
            ("The best anime of 2026 so far", "/best-of/2026/anime"),
            ("Monogatari in order", "/in-order/monogatari"),
            ("How to track anime and episodes on OmniTrackr", "/anime-tracker"),
        ],
        "sources": [
            ("LiveChart: winter 2027 anime chart", "https://www.livechart.me/winter-2027/tv"),
            ("AnimeSchedule: winter 2027 anime", "https://animeschedule.net/seasons/winter-2027"),
            ("Anime Corner: Historie trailer, cast and January 2027 release", "https://animecorner.me/historie-anime-new-trailer-visual-main-cast-january-2027-release/"),
            ("Anime News Network: Historie TV anime sets January 2027 premiere", "https://animenewsnetwork.com/news/2026-05-24/historie-tv-anime-announces-lead-voice-actor-january-2027-premiere/.237768"),
            ("Anime News Network: Hirayasumi anime teaser and January 2027 debut", "https://www.animenewsnetwork.com/news/2026-03-16/hirayasumi-anime-teaser-unveils-staff-january-2027-debut/.235378"),
            ("The Outer Haven: Viz Media reveals Hirayasumi key visual and cast", "https://www.theouterhaven.net/viz-media-reveals-key-visual-first-anime-footage-and-lead-voice-cast-for-hirayasumi/"),
            ("Anime Corner: Sekiro: No Defeat runs for 8 episodes from January 2027", "https://animecorner.me/sekiro-no-defeat-full-tv-anime-to-run-for-8-episodes-starting-in-january-2027-new-visual-revealed/"),
            ("The Outer Haven: Sekiro: No Defeat heads to Crunchyroll", "https://www.theouterhaven.net/sekiro-no-defeat-heads-to-crunchyroll-as-a-series-in-january-2027/"),
            ("Final Weapon: Bless to stream on Crunchyroll", "https://finalweapon.net/2026/10/22/bless-anime-to-stream-on-crunchyroll-new-cast-members-revealed/"),
            ("Final Weapon: Bless premieres in January 2027 on Noitamina", "https://finalweapon.net/2026/09/12/bless-anime-premieres-in-january-2027/"),
            ("Final Weapon: The Guy She Was Interested In Wasn't a Guy at All premieres January 8", "https://finalweapon.net/2026/10/08/the-guy-she-was-interested-in-wasnt-a-guy-at-all-anime-premieres-january-8/"),
            ("Anime Corner: Shangri-La Frontier season 3, two cours from January 10", "https://animecorner.me/shangri-la-frontier-season-3-key-visual-revealed-two-consecutive-cours-starting-on-january-10-2027/"),
            ("Final Weapon: Shangri-La Frontier season 3 confirms its slot", "https://finalweapon.net/2026/09/16/shangri-la-frontier-season-3-confirms-two-cour-run-and-january-10-premiere/"),
            ("Anime News Network: Mashle season 3 trailer and January 2027 debut", "https://www.animenewsnetwork.com/news/2026-07-02/mashle-magic-and-muscles-season-3-anime-trailer-unveils-january-2027-debut/.239227"),
            ("The Outer Haven: Mashle season 3 coming to Crunchyroll", "https://www.theouterhaven.net/mashle-magic-and-muscles-season-3-coming-to-chrunchyroll-in-january-2027/"),
            ("Anime Corner: Akane-banashi season 2 announced for January 2027", "https://animecorner.me/akane-banashi-season-2-announced-for-january-2027/"),
            ("What's on Netflix: Akane-banashi season 2", "https://www.whats-on-netflix.com/news/anime/akane-banashi-season-2-netflix-release-date-news/"),
            ("Final Weapon: The Fable season 2 premieres January 9, 2027", "https://finalweapon.net/2026/10/13/the-fable-season-2-premieres-january-9-2027/"),
            ("Final Weapon: Marriagetoxin season 2 premieres in January 2027", "https://finalweapon.net/2026/08/03/marriagetoxin-season-2-january-2027-premiere/"),
            ("The Outer Haven: Marriagetoxin staff at New York Comic Con 2026", "https://www.theouterhaven.net/nycc-2026-marriagetoxin-production-staff-discuss-season-1-and-the-creative-process-for-season-2/"),
            ("Anime Corner: Dengeki Daisy trailer, key visual and cast", "https://animecorner.me/dengeki-daisy-reveals-main-trailer-key-visual-and-4-new-cast-members-ahead-of-january-2027-release/"),
            ("Anime News Network: Dengeki Daisy gets a TV anime by Studio DEEN", "https://www.animenewsnetwork.com/news/2026-06-08/kyousuke-motomi-dengeki-daisy-shojo-manga-gets-tv-anime-by-studio-deen/.238269"),
            ("Anime Corner: Now That We Draw trailer and January 2027 release", "https://animecorner.me/now-that-we-draw-anime-reveals-first-trailer-january-2027-release-date/"),
            ("Anime Corner: Iruma-kun: IruMafia Edition starts January 4", "https://animecorner.me/welcome-to-demon-school-iruma-kun-irumafia-edition-anime-main-visual-and-january-4-revealed/"),
            ("Final Weapon: Yaiba: Samurai Legend season 2 premieres January 9, 2027", "https://finalweapon.net/2026/09/19/yaiba-samurai-legend-season-2-premieres-on-january-9-2027/"),
            ("Final Weapon: Golden Kamuy final season continues in the Runaway Train arc", "https://finalweapon.net/2026/03/30/golden-kamuy-final-season-continues-in-runaway-train-arc/"),
        ],
    },
}
