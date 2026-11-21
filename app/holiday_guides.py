"""Guides that sit beside the holiday hub (/holidays/christmas, /holidays/thanksgiving,
/holidays/reading-and-listening).

The hub at /holidays picks one title per screen format for each kind of holiday
break. These go deeper on one part of the season: Christmas itself (the year's new films and
specials, with dates, and older picks for Christmas Eve and the week after), the four days
of the Thanksgiving weekend, and the books, audiobooks, podcasts, manga and albums that suit December.
None of their picks repeat the hub's; the plans link back to the hub's picks by name.

Pick fields are the hub's without the festive level:
    kind     movie | tv | anime | game | book | album | manga | podcast | audiobook
    time     what it asks of you, in plain words
    why      why it is on the shelf
    note     how to approach it
    caveat   what to know first (content, pace, availability)

Optional, used by the Christmas guide (/holidays/christmas):
    release  {"date": ISO date in the US, "where": "Netflix"} for a new title; shown on the
             pick, and Pick for me only suggests it from that date (pick.is_available)
    day      a shelf's label in the row of shelves under the intro (default: its `when`)
    calendar a dated list of every new release ({key, label, after, eyebrow, heading, intro,
             items: [{date, title, format, where, note}]}), shown after the shelf named in `after`
    sources  ((label, url), ...) listed under "How we chose"

Movie, TV, anime, game, book and album picks join the Pick for me pool (pick.py).
Manga, podcast and audiobook picks are saved straight to the matching tracker
(seasonal.extra_entry), since Pick for me only suggests the first six formats.
"""

GUIDES = {
    "christmas": {
        "path": "/holidays/christmas",
        "parent": "holidays",
        "name": "Christmas 2026 guide",
        "short": "Christmas",
        "theme": "holiday",
        "published": "2026-11-20",
        "reviewed": "2026-11-20",
        "search_title": "New Christmas movies 2026, TV specials and the best Christmas episodes, with dates and where to watch",
        "headline": "Christmas 2026: what's new, and what's worth another go",
        "deck": ("Every new Christmas film, special and album of 2026 with its date and where to find it, then twenty picks "
                 "for the season: five of the new films, five Christmas episodes of shows you may already love, and ten "
                 "older picks for Christmas Eve and the week after."),
        "summary": ("Every new Christmas movie, TV special and album of 2026 with dates and platforms, plus twenty picks "
                    "from Ebenezer to the Christmas episode of The Bear."),
        "card": "New Christmas films and specials for 2026 with their dates, plus the best Christmas episodes and classics.",
        "eyebrow": "CHRISTMAS 2026",
        "related_heading": "More for the holidays",
        "intro": [
            "Christmas Day falls on a Friday this year. For a lot of people that means a long weekend straight after it, "
            "then a quiet week before New Year's Day, which is also a Friday. The new releases are spread out further "
            "than usual. Netflix put out its first Christmas film on November 4, Ebenezer opened in theaters on "
            "November 13, and the busiest single day is Wednesday, December 2, when Prime Video and Netflix each release "
            "a Christmas film and NBC lights the tree at Rockefeller Center.",
            "This guide does two jobs. The first part is the new stuff: the Christmas films, specials and albums of 2026, "
            "each with its date and where to find it, checked on November 20. Five of the films get a full write-up. The "
            "rest are listed by date in a calendar, so you can see the whole season on one screen.",
            "The second part is for the rest of December, when you want something you already know will work. There are "
            "five Christmas episodes from series that are worth an evening on their own, five picks for Christmas Eve and "
            "five for Christmas Day and the days after it, in films, TV, books, an audiobook, albums and games.",
            "The holiday hub already sorts twenty-four picks by how festive they are, from Fargo to Elf, and the advent "
            "calendar opens a new pick every morning from December 1. Nothing here repeats either of them, or the "
            "reading and listening guide, and the plans near the bottom of the page borrow from all three.",
        ],
        "shelves": [
            {
                "key": "new-this-year",
                "name": "New this Christmas",
                "when": "NEW IN 2026",
                "day": "New in 2026",
                "tagline": "Five of the year's new Christmas films, in theaters and on streaming.",
                "intro": [
                    "Most of each year's new Christmas films are romantic comedies made for streaming, and 2026 has "
                    "plenty of those. It also has a gothic Christmas Carol from a horror director, Arnold Schwarzenegger "
                    "as Santa Claus, and a sequel to the film in which Santa fought mercenaries with a sledgehammer. "
                    "These five cover that range, from a cartoon for the youngest in the house to a film that should be "
                    "kept well away from them.",
                    "Four of the five weren't out when we wrote this, and we haven't seen those four. Read their "
                    "write-ups as a description of what each film is and who it suits, not as a review. Dates are for "
                    "the United States.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Ebenezer", "year": 2026, "creator": "Ti West",
                     "release": {"date": "2026-11-13", "where": "In US theaters · Paramount Pictures"},
                     "time": "About two hours (116 minutes)",
                     "why": "Johnny Depp plays Scrooge in a new A Christmas Carol, written by Nathaniel Halpern and "
                            "directed by Ti West, who made the X horror films with Mia Goth. Ian McKellen plays Jacob "
                            "Marley, Andrea Riseborough and Tramell Tillman are the Ghosts of Christmas Past and Present, "
                            "Rupert Grint is Bob Cratchit and Sam Claflin is Scrooge's nephew Fred. Paramount calls it a "
                            "gothic retelling, set over one Christmas Eve in Victorian London.",
                     "note": "Go with someone who knows the story well. Half the fun of a new Christmas Carol is "
                             "spotting what it keeps and what it changes. If you have half an hour beforehand, read "
                             "the first chapter of Dickens: Marley's visit is the most frightening scene in the book, "
                             "and it is where a director like West has the most room.",
                     "caveat": "Rated PG-13 for frightening material, so it is past the point most younger children "
                               "will enjoy. The Muppet Christmas Carol on the holiday hub is the version for them. "
                               "Paramount hadn't announced a streaming date when we checked."},
                    {"kind": "movie", "title": "The Man with the Bag", "year": 2026, "creator": "Adam Shankman",
                     "release": {"date": "2026-12-02", "where": "Prime Video"},
                     "time": "A feature-length comedy; no runtime listed yet",
                     "why": "Arnold Schwarzenegger plays Santa Claus, thirty years after he spent Jingle All the Way "
                            "fighting other parents for a toy. A few days before Christmas his sack of presents is "
                            "stolen, and he hires a small-time thief, played by Alan Ritchson from Reacher, to help get "
                            "it back. Awkwafina, Ken Jeong, Jane Krakowski and Kyle Mooney are in the cast, and Adam "
                            "Shankman, who directed Hairspray, shot it in Manhattan.",
                     "note": "Amazon made Red One with Dwayne Johnson in 2024, and this is the same idea: a big Santa "
                             "action comedy for a night when nobody in the room wants anything sentimental. It suits a "
                             "group of adults and teenagers better than a family with small children.",
                     "caveat": "It hadn't been rated or reviewed when we checked. A heist comedy starring Schwarzenegger "
                               "and Ritchson will have fights and probably some swearing, so look at the rating on "
                               "Prime Video before putting it on for younger viewers."},
                    {"kind": "movie", "title": "In a Holidaze", "year": 2026, "creator": "Tiffany Paulsen",
                     "release": {"date": "2026-12-02", "where": "Netflix"},
                     "time": "A feature-length romantic comedy",
                     "why": "Based on Christina Lauren's 2020 novel. Maddie Ziegler plays a woman in her twenties whose "
                            "family and their oldest friends have spent every Christmas together at a cabin in Utah. "
                            "This is the last year they will have the cabin. She makes a mess of things with the family "
                            "friend she has loved for years, and then finds herself back at the start of the trip, "
                            "living the same holiday again until she works out what she actually wants. Rob Lowe plays "
                            "one of the parents.",
                     "note": "It is Groundhog Day at a ski cabin, and the book has a big following among readers of "
                             "holiday romance, so expect a lot of comparisons in the first week. If you have read it, "
                             "watch for what survived. If you haven't, the film is the quicker way in.",
                     "caveat": "A romance with adult characters, best for adults and older teenagers. Time-loop stories "
                               "tend to sag in the middle, and the novel is told from inside its heroine's head, which "
                               "is hard to put on screen."},
                    {"kind": "movie", "title": "Violent Night 2", "year": 2026, "creator": "Tommy Wirkola",
                     "release": {"date": "2026-12-04", "where": "In US theaters · Universal Pictures"},
                     "time": "111 minutes",
                     "why": "David Harbour is back as the hard-drinking Santa Claus of Violent Night (2022), the film "
                            "that took Home Alone's traps and made them bloody. This time Santa has landed on the naughty "
                            "list and lost his magic, and he has to stand up to a gangster, played by Jared Harris, who "
                            "is terrorizing a small town. Kristen Bell joins as Mrs. Claus, and Tommy Wirkola, who "
                            "directed the first film, directed this one.",
                     "note": "Watch the first film beforehand if you haven't; the sequel keeps the same Santa and the "
                             "same sense of humor. Then go with a group of adults who like their action films loud and "
                             "silly. It is the one film on this page to keep away from a family evening.",
                     "caveat": "The first film was rated R for strong bloody violence and language throughout, and "
                               "nothing about the sequel suggests it will be any gentler. Not for children, whatever the "
                               "poster looks like."},
                    {"kind": "movie", "title": "Diary of a Wimpy Kid Christmas: The Getaway", "year": 2026,
                     "creator": "Matt Danner",
                     "release": {"date": "2026-12-04", "where": "Disney+"},
                     "time": "An animated family film, about the length of an afternoon matinee",
                     "why": "Disney's fifth animated Wimpy Kid film, based on The Getaway, the twelfth book in Jeff "
                            "Kinney's series. The Heffleys skip Christmas at home and fly to a resort on a tropical "
                            "island, and Greg finds out that paradise isn't as relaxing as the brochure promised. Matt "
                            "Danner, who directed the animated The Last Straw, directed it.",
                     "note": "This is the new release for the youngest in the house. Children who have read the books "
                             "will want it the day it arrives, and it fits in the afternoon, before the grown-ups' film "
                             "in the evening.",
                     "caveat": "Slapstick and gross-out jokes in the style of the books. It is set on a beach, so it is "
                               "the least Christmassy film here, and adults without a Wimpy Kid reader at home can "
                               "skip it."},
                ],
            },
            {
                "key": "christmas-episodes",
                "name": "The Christmas episodes",
                "when": "ANY NIGHT IN DECEMBER",
                "day": "Any night",
                "tagline": "Four half-hours and one long hour, each fine to watch on its own.",
                "intro": [
                    "Long-running comedies tend to make a Christmas episode every year, and most of them are forgettable. "
                    "A few are the best thing the show ever made. These five work even if you have never seen another "
                    "episode, which makes them good for an evening when nobody can agree on a film and everyone has "
                    "half an hour.",
                    "Saving one of these adds the whole series to your library, so it is there if the episode makes "
                    "you want more. The time line names the episode and where it sits in the show, and the times are "
                    "for that one episode.",
                ],
                "picks": [
                    {"kind": "tv", "title": "The Simpsons", "year": 1989, "creator": "Matt Groening",
                     "time": "One 22-minute episode: season 1, episode 1",
                     "why": "Simpsons Roasting on an Open Fire was the first full-length Simpsons episode, shown on Fox "
                            "on December 17, 1989. Homer's Christmas bonus is cancelled, the family's Christmas money "
                            "goes on removing Bart's new tattoo, and Homer secretly takes a job as a shopping-mall Santa "
                            "to pay for presents. It ends at the dog track, which is how the family gets Santa's Little "
                            "Helper.",
                     "note": "Treat it as the start of the show, not an early curiosity. The drawing is rough, but the "
                             "jokes land, and the ending is as warm as the series ever got. Every season is on Disney+ "
                             "in the United States.",
                     "caveat": "It looks very different from the Simpsons most people know; the characters were redrawn "
                               "over the first few seasons. Nothing in it to worry about for children."},
                    {"kind": "tv", "title": "Seinfeld", "year": 1989, "creator": "Larry David and Jerry Seinfeld",
                     "time": "One 22-minute episode: season 9, episode 10",
                     "why": "The Strike, first shown on December 18, 1997, is the episode that gave the world Festivus. "
                            "George's father Frank invented it years ago as a protest against Christmas shopping: an "
                            "aluminum pole instead of a tree, the Airing of Grievances over dinner, and the Feats of "
                            "Strength to finish. The holiday came from real life. Dan O'Keefe, one of the episode's "
                            "writers, grew up with a Festivus his father had made up.",
                     "note": "This is the episode to show someone who has only heard of Festivus. Kramer goes back to "
                             "work at a bagel shop after a twelve-year strike, Elaine is one stamp away from a free sub, "
                             "and most of the cast ends up at Frank's table.",
                     "caveat": "Seinfeld is a show about four selfish people, and Festivus is a sour joke about family "
                               "holidays. The episode is less cosy than its reputation, which is most of its charm."},
                    {"kind": "tv", "title": "The Office", "year": 2005, "creator": "Greg Daniels",
                     "time": "One 22-minute episode: season 2, episode 10",
                     "why": "In Christmas Party, first shown on December 6, 2005, Michael is given a handmade oven mitt "
                            "in the office Secret Santa and turns the whole thing into a gift swap, because he has spent "
                            "twenty times the limit on a video iPod for Ryan. Everyone wants the iPod. Jim only wants Pam "
                            "to keep the teapot he filled with their private jokes. Michael Schur wrote it, years before "
                            "he made Parks and Recreation and The Good Place.",
                     "note": "Season two is where the American Office found its footing, and this episode is a fair "
                             "test of whether you will like the rest. If Michael's face at the oven mitt makes you "
                             "laugh, start the series from season two.",
                     "caveat": "Cringe comedy. Michael tries to rescue his party with a lot of vodka, and you will spend "
                               "a good part of it wincing on his behalf."},
                    {"kind": "tv", "title": "Community", "year": 2009, "creator": "Dan Harmon",
                     "time": "One 22-minute episode: season 2, episode 11",
                     "why": "In Abed's Uncontrollable Christmas, first shown on December 9, 2010, Abed wakes up seeing "
                            "the world in stop-motion, like an old Rankin/Bass special, and the rest of his study group "
                            "go along with it to find out why. The whole episode is animated that way. It starts as a "
                            "parody of the Rudolph specials and becomes a story about why Christmas is hard for him "
                            "this year.",
                     "note": "You don't need to know the characters; the first scene explains enough. It is funniest "
                             "for anyone who grew up on Rudolph the Red-Nosed Reindeer and Santa Claus Is Comin' to Town, "
                             "since half the jokes are about those specials.",
                     "caveat": "Jokes about therapy and television that will pass younger children by, and a sad "
                               "reason underneath it all: a parent who isn't coming home for Christmas."},
                    {"kind": "tv", "title": "The Bear", "year": 2022, "creator": "Christopher Storer",
                     "time": "One episode of about an hour: season 2, episode 6",
                     "why": "Fishes goes back five years to a Christmas Eve at the Berzattos' house, where Carmy's mother "
                            "Donna is cooking the Feast of the Seven Fishes for the whole family and coming apart while "
                            "she does it. Jamie Lee Curtis won an Emmy for playing Donna. Bob Odenkirk, Sarah Paulson, "
                            "John Mulaney, Gillian Jacobs and Jon Bernthal are around the table. It is the most "
                            "frightening family Christmas on television.",
                     "note": "It works without the rest of the show, but it hits harder if you have seen the first "
                             "season, which explains what happens to Mikey later. Save it for people who have "
                             "survived a difficult family Christmas of their own.",
                     "caveat": "An hour of shouting, drinking and a mother's breakdown, ending with a car driven into "
                               "the house. It is a great episode and a hard one to sit through, and not one to put on "
                               "with relatives if your own Christmases look anything like it."},
                ],
            },
            {
                "key": "christmas-eve",
                "name": "Christmas Eve",
                "when": "DECEMBER 24",
                "day": "December 24",
                "tagline": "From the last-minute wrapping to the hour after midnight.",
                "intro": [
                    "Christmas Eve is a long day of waiting, especially for anyone under ten. There are presents still "
                    "to wrap, food to start and a lot of hours to fill before bed. These five run from the afternoon, "
                    "when everyone needs a film, to the time after the children are asleep.",
                    "Each one is either set on Christmas Eve or made for it: a story to read aloud after dinner, a poet "
                    "reading his own Christmas memories, a rock album about one Christmas Eve, a game that takes place "
                    "over a single snowy night, and a film about a boy defending his house against two burglars who "
                    "planned their robbery for December 24.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Home Alone", "year": 1990, "creator": "Chris Columbus",
                     "time": "1 hour 43 minutes",
                     "why": "Eight-year-old Kevin McCallister is left behind when his family flies to Paris for "
                            "Christmas, and he has to defend the house in suburban Chicago from two burglars, Harry and "
                            "Marv, who plan to clear out the street on Christmas Eve. John Hughes wrote it, Chris "
                            "Columbus directed it and John Williams wrote the score. The last half hour, when Kevin's "
                            "traps go off one after another, is the part children ask to watch again.",
                     "note": "Put it on in the late afternoon, when the children are too excited for anything slower. "
                             "Adults tend to notice other things on a rewatch: the old man next door, and how much the "
                             "film is about a boy who thinks his family doesn't want him. ABC has it on its schedule "
                             "for 8 p.m. Eastern on Christmas Eve this year.",
                     "caveat": "Rated PG. The traps are cartoon violence, but a couple of them, the iron and the "
                               "blowtorch, make younger viewers wince, and the film opens with Kevin sent to bed in "
                               "disgrace."},
                    {"kind": "book", "title": "The Gift of the Magi", "year": 1905, "creator": "O. Henry",
                     "time": "About fifteen minutes read aloud",
                     "why": "O. Henry's short story first ran in a New York newspaper in December 1905. Della has one "
                            "dollar and eighty-seven cents to buy her husband Jim a Christmas present, so she sells her "
                            "long hair to a wig maker and buys a chain for his gold watch. Jim, meanwhile, has made a "
                            "sale of his own. Most people know the twist. The story is better than the twist: it is "
                            "funny, and the narrator keeps butting in with opinions.",
                     "note": "Read it aloud after dinner; it takes about as long as the washing up. It suits a table of "
                             "mixed ages, since the children follow the story and the adults get the jokes about money.",
                     "caveat": "The language is from 1905, with long sentences and old slang that younger listeners may "
                               "need explained. It has been out of copyright for decades, so free copies are easy to "
                               "find."},
                    {"kind": "audiobook", "title": "A Child's Christmas in Wales", "year": 1952, "creator": "Dylan Thomas",
                     "extra": {"narrator": "Dylan Thomas"},
                     "time": "About twenty minutes",
                     "why": "In 1952 Barbara Holdridge and Marianne Mantell, two recent graduates of Hunter College, "
                            "recorded Dylan Thomas reading his own work at Steinway Hall in New York. The first side of "
                            "the record was A Child's Christmas in Wales, his memory of boyhood Christmases in a Welsh "
                            "seaside town: snow, aunts, uncles asleep after dinner, and a fire at Mrs. Prothero's. It was "
                            "the first record of their company, Caedmon, which went on to sell spoken word on records "
                            "for decades. The Library of Congress added it to the National Recording Registry in 2008.",
                     "note": "Play it once the children are in bed, or let them stay up for it, since it is short. "
                             "Thomas's voice is the reason to choose the recording over the book, and it is good "
                             "company while you wrap the last presents.",
                     "caveat": "Thomas reads in a rolling, musical voice that takes a minute to tune into, and the "
                               "language is dense. It is a memory of a childhood in the 1920s, without much of a plot."},
                    {"kind": "album", "title": "Christmas Eve and Other Stories", "year": 1996,
                     "creator": "Trans-Siberian Orchestra",
                     "time": "Just over an hour (62 minutes)",
                     "why": "Trans-Siberian Orchestra's first album is a rock opera about one Christmas Eve: God sends an "
                            "angel down to Earth to bring back an example of kindness done in the spirit of the holiday. "
                            "It sets carols and a piece of Tchaikovsky's Nutcracker to electric guitars, piano and choir. "
                            "It also has Christmas Eve/Sarajevo 12/24, the medley of God Rest Ye Merry, Gentlemen and "
                            "Carol of the Bells that most people know the band by, in the same recording the metal band "
                            "Savatage released in 1995.",
                     "note": "Play it from the start and in order while the evening's cooking gets going, since it is "
                             "built as one story. In a house that argues about Christmas music, it is one of the few "
                             "records the rock fans and the carol fans might both put up with.",
                     "caveat": "Loud, theatrical and completely sincere. If big power ballads make you wince, skip "
                               "straight to Sarajevo."},
                    {"kind": "game", "title": "Batman: Arkham Origins", "year": 2013, "creator": "WB Games Montréal",
                     "time": "About twelve hours for the main story",
                     "why": "It is Christmas Eve in Gotham, early in Batman's career. The crime boss Black Mask has put "
                            "a fifty-million-dollar bounty on his head, and eight assassins have come to town to collect "
                            "it before morning. The city is under snow and strung with lights, and the Joker turns up "
                            "before the night is out. WB Games Montréal made it as a prequel to Rocksteady's Arkham "
                            "Asylum and Arkham City.",
                     "note": "This is the pick for the hours after everyone else has gone to bed. The fighting is the "
                             "same easy-to-learn, hard-to-master combat as the other Arkham games, and the story follows "
                             "one night from start to finish, which makes it a good fit for the Christmas break.",
                     "caveat": "Rated T for blood, violence and language. It came out for PlayStation 3, Xbox 360, Wii U "
                               "and PC and was never remastered, so the PC version is the simplest way to play it now. It "
                               "usually ranks below Rocksteady's games, partly because much of its city is Arkham City's "
                               "map again."},
                ],
            },
            {
                "key": "christmas-week",
                "name": "Christmas Day and after",
                "when": "DECEMBER 25 TO 31",
                "day": "December 25 to 31",
                "tagline": "For the afternoon of the day itself and the quiet week before New Year.",
                "intro": [
                    "By the afternoon of Christmas Day most houses have opened everything, eaten too much and need "
                    "something everyone can watch without thinking. Then comes the odd week before New Year, when "
                    "nobody is sure what day it is and there is finally time for something longer.",
                    "These five go in that order: a film for the afternoon, a short animated film that British "
                    "families have watched at Christmas since 1982, a record for the morning after, a book of letters "
                    "for the long evenings and a farming game to play into January. The holiday hub's family shelf, "
                    "Everyone on the sofa, has six more for the day itself.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Arthur Christmas", "year": 2011, "creator": "Sarah Smith",
                     "time": "1 hour 37 minutes",
                     "why": "Aardman, the studio behind Wallace & Gromit, imagines Santa's operation as a military one: "
                            "a sleigh the size of a spaceship, an army of elves, and Santa's elder son Steve running it "
                            "all from mission control. When one present for one girl in Cornwall is missed, only Arthur, "
                            "the clumsy younger son who answers the letters, thinks it matters. He sets off with his "
                            "grandfather, the old wooden sleigh and a team of reindeer to deliver it before she wakes up.",
                     "note": "Good for the afternoon of Christmas Day, when everyone is full and a few of the adults will "
                             "fall asleep. The jokes come fast enough for the ones who stay awake, and Bill Nighy as the "
                             "grumpy old Grandsanta is the best thing in it.",
                     "caveat": "Rated PG. A few noisy chases, and nothing much to worry about for children over four or "
                               "five."},
                    {"kind": "movie", "title": "The Snowman", "year": 1982, "creator": "Dianne Jackson",
                     "time": "26 minutes",
                     "why": "A wordless animated film of Raymond Briggs's picture book, about a boy whose snowman comes "
                            "to life one night and flies him to the North Pole. Channel 4 first showed it on December "
                            "26, 1982, and it was nominated for an Oscar for best animated short. The only singing is "
                            "Walking in the Air, written by Howard Blake and sung in the film by Peter Auty, a St Paul's "
                            "Cathedral choirboy.",
                     "note": "Watch it on the 26th as a short break from everything else. The soft, pencil-crayon "
                             "drawing looks like the book's pages moving, and the youngest children follow it easily "
                             "without any dialogue. Some copies open with a short introduction by David Bowie.",
                     "caveat": "The ending is sad: the snowman melts, and the film doesn't soften it. Small children may "
                               "need a cuddle. The 2012 sequel, The Snowman and the Snowdog, ends more gently."},
                    {"kind": "album", "title": "A Christmas Gift for You from Phil Spector", "year": 1963,
                     "creator": "Phil Spector",
                     "time": "34 minutes",
                     "why": "Phil Spector made pop records by piling up session players, pianos and echo into what "
                            "people called a wall of sound. In 1963 he made a Christmas album that way with the singers "
                            "on his label: Darlene Love, the Ronettes, the Crystals, and Bob B. Soxx and the Blue Jeans. "
                            "Darlene Love's Christmas (Baby Please Come Home) first appeared on it, and so did the "
                            "Ronettes' Sleigh Ride. It came out on November 22, 1963, the day President Kennedy was "
                            "shot, and hardly sold that year.",
                     "note": "Put it on the morning after, when the house needs waking up. Every one of its thirteen "
                             "tracks could be a single, and you will recognise half of them from other people's "
                             "Christmas playlists. It ends with Spector speaking a thank-you over Silent Night, which "
                             "you can skip.",
                     "caveat": "Spector was convicted in 2009 of murdering the actress Lana Clarkson and died in prison "
                               "in 2021, and some listeners would rather not play his records. The voices belong to the "
                               "singers: Darlene Love sang Christmas (Baby Please Come Home) on David Letterman's show "
                               "every December for almost thirty years."},
                    {"kind": "book", "title": "Letters from Father Christmas", "year": 1976, "creator": "J.R.R. Tolkien",
                     "time": "An evening, or a letter or two a night",
                     "why": "Every Christmas from 1920 into the 1940s, Tolkien wrote his children a letter in the shaky "
                            "handwriting of Father Christmas, with drawings, and left it for them to find. The letters "
                            "tell the news from the North Pole: the year the North Polar Bear climbed the Pole and fell "
                            "through the roof, the elves, and a war with goblins in the caves below. His family "
                            "published them after his death, first in 1976 as The Father Christmas Letters.",
                     "note": "Read one or two a night between Christmas and New Year, in order, so the stories of the "
                             "Polar Bear and the goblins build up. Look for an edition with the color pictures; they are "
                             "half the fun.",
                     "caveat": "Written for Tolkien's own children, so some jokes are family jokes and the early letters "
                               "are very short. Fans of The Hobbit will enjoy the goblins. Others may find it slight."},
                    {"kind": "game", "title": "Stardew Valley", "year": 2016, "creator": "ConcernedApe",
                     "time": "As long as you like; one season in the game takes about six hours",
                     "why": "Eric Barone made Stardew Valley on his own over about four years. You inherit your "
                            "grandfather's run-down farm outside a small town, then grow crops, fish, explore a mine and "
                            "get to know the townspeople. The game has its own Christmas: the Feast of the Winter Star "
                            "on the 25th day of winter, when the town holds a secret gift exchange and you are given a "
                            "neighbor to buy for.",
                     "note": "Start a new farm on the 26th with a friend or partner. Up to four people can share one "
                             "farm on most systems, online or split-screen, and the first spring in the game is a gentle "
                             "way into the new year.",
                     "caveat": "Hard to put down, and it has no ending to reach, so decide how long you will play "
                               "before you sit down. It runs on almost everything, phones included."},
                ],
            },
        ],
        "calendar": {
            "key": "release-calendar",
            "label": "Release calendar",
            "after": "new-this-year",
            "eyebrow": "EVERY NEW RELEASE, BY DATE",
            "heading": "The 2026 Christmas calendar",
            "intro": [
                "Here is everything new for Christmas 2026 that we could confirm, in date order: films in theaters "
                "and on streaming, network specials and two new albums. Titles with a full write-up above link to it. "
                "TV times are Eastern and come from the networks' announced schedules, and the films' dates come from "
                "the studios and streamers. We checked them all on November 20.",
                "Schedules move, especially for TV specials, so check the service before you plan an evening around one. "
                "Hallmark Channel and Lifetime premiere new TV films every week through December. We list two "
                "of Hallmark's bigger ones and leave the rest to the channels' own schedules.",
            ],
            "items": [
                {"date": "2026-11-04", "title": "A Dog's Perfect Christmas", "format": "Film", "where": "Netflix",
                 "note": "Dennis Quaid, Milo Ventimiglia and Mary Steenburgen in a family drama from W. Bruce Cameron's "
                         "novel, narrated by a basset hound voiced by Thomas Haden Church."},
                {"date": "2026-11-06", "title": "The 12 Dates of Christmas", "format": "Film", "where": "Hulu",
                 "note": "Lucy Hale and Ian Harding in a romantic comedy about twelve dates in the twelve weeks before "
                         "Christmas."},
                {"date": "2026-11-06", "title": "Worst Christmas Ever!", "format": "Album",
                 "where": "Sufjan Stevens · Asthmatic Kitty",
                 "note": "Sixteen tracks: fifteen picked from his two Christmas box sets of 2006 and 2012, and On This "
                         "Christmas (It Only Gets Better), his first new Christmas song in fifteen years."},
                {"date": "2026-11-06", "title": "Good Weather for Immaculate Conception", "format": "Album",
                 "where": "Alanis Morissette · Epiphany / Virgin",
                 "note": "Her first holiday album: fourteen tracks, two of them new songs, with Brandi Carlile and Steve "
                         "Martin, Joy Oladokun and Martin Short among the guests."},
                {"date": "2026-11-11", "title": "Tyler Perry's The Gospel of Christmas", "format": "Film",
                 "where": "Netflix",
                 "note": "A pastor inherits his family's struggling church in New York, with a cast full of gospel "
                         "singers, among them Fantasia Barrino, Shirley Caesar and Yolanda Adams."},
                {"date": "2026-11-12", "title": "The Christmas Switch", "format": "Film", "where": "Netflix",
                 "note": "A Swedish romantic comedy about two very different twin sisters who swap lives in the weeks "
                         "before Christmas."},
                {"date": "2026-11-13", "title": "Ebenezer", "format": "Film", "where": "In US theaters",
                 "note": "Johnny Depp as Scrooge in Ti West's gothic A Christmas Carol."},
                {"date": "2026-11-18", "title": "Guarding Stars", "format": "Film", "where": "Netflix",
                 "note": "Leighton Meester as a bodyguard and Jared Padalecki as the film star she pretends to date at "
                         "his family's Montana ranch, from Katherine Center's novel The Bodyguard."},
                {"date": "2026-11-23", "title": "Clashing Through the Snow", "format": "Film", "where": "Prime Video",
                 "note": "Christopher Briney and Michelle Randolph on a road trip across the country in the holiday rush."},
                {"date": "2026-11-28", "title": "Holiday Ever After: A Disney World Wish Come True", "format": "TV film",
                 "where": "Hallmark Channel, 8 p.m.",
                 "note": "Lacey Chabert and Travis Van Winkle, filmed at Walt Disney World."},
                {"date": "2026-11-30", "title": "The Wonderful World of Disney: Holiday Spectacular", "format": "Special",
                 "where": "ABC, 8 p.m., then Disney+ and Hulu",
                 "note": "The yearly concert special filmed at the Disney parks."},
                {"date": "2026-12-01", "title": "CMA Country Christmas", "format": "Special",
                 "where": "ABC, 9 p.m., then Disney+ and Hulu",
                 "note": "The seventeenth edition, hosted by Lady A, with Trisha Yearwood, Dan + Shay and BeBe Winans."},
                {"date": "2026-12-02", "title": "The Man with the Bag", "format": "Film", "where": "Prime Video",
                 "note": "Arnold Schwarzenegger as Santa and Alan Ritchson as the thief he hires."},
                {"date": "2026-12-02", "title": "In a Holidaze", "format": "Film", "where": "Netflix",
                 "note": "Maddie Ziegler relives the same Christmas at a Utah cabin."},
                {"date": "2026-12-02", "title": "Christmas in Rockefeller Center", "format": "Special",
                 "where": "NBC, 7 p.m.",
                 "note": "The live lighting of the Rockefeller Center tree. Hosts and singers hadn't been named when we "
                         "checked."},
                {"date": "2026-12-02", "title": "Christmas With Snoop", "format": "Special", "where": "NBC, 10 p.m., and Peacock",
                 "note": "Snoop Dogg's new holiday party special, with Martha Stewart, Gwen Stefani, Jamie Foxx and "
                         "Kristin Chenoweth among the guests."},
                {"date": "2026-12-04", "title": "Violent Night 2", "format": "Film", "where": "In US theaters",
                 "note": "David Harbour's Santa returns, with Kristen Bell as Mrs. Claus."},
                {"date": "2026-12-04", "title": "Diary of a Wimpy Kid Christmas: The Getaway", "format": "Animated film",
                 "where": "Disney+",
                 "note": "The Heffleys spend Christmas on a tropical island."},
                {"date": "2026-12-05", "title": "A Grand Biltmore Christmas", "format": "TV film",
                 "where": "Hallmark Channel, 8 p.m.",
                 "note": "Holland Roden and Niall Matter, with Andie MacDowell and Jonathan Frakes, at the Biltmore "
                         "estate."},
                {"date": "2026-12-09", "title": "Gabby's Dollhouse: Makers and Bakers Holiday", "format": "Series",
                 "where": "Netflix (US)",
                 "note": "A baking and crafting competition for young pairs of makers, for fans of the preschool show."},
                {"date": "2026-12-17", "title": "iHeartRadio Jingle Ball 2026", "format": "Special",
                 "where": "ABC, 8 p.m., then Disney+ and Hulu",
                 "note": "Highlights from the Jingle Ball concert tour, with Olivia Rodrigo, Hilary Duff and the Jonas "
                         "Brothers among the acts."},
                {"date": "2026-12-25", "title": "Disney Parks Magical Christmas Day Parade", "format": "Special",
                 "where": "ABC, 10 a.m.",
                 "note": "The parade and concert special that ABC shows every Christmas morning."},
            ],
        },
        "plan_label": "Plan your Christmas",
        "plan_heading": "Six ways to spend the season",
        "nights": [
            {"name": "Christmas Eve with young children",
             "plan": "Diary of a Wimpy Kid Christmas: The Getaway after lunch, Home Alone once it gets dark, and The Gift "
                     "of the Magi read aloud when everyone is in pajamas. If they still won't settle, The Polar Express "
                     "from the holiday hub's family shelf is the book for the last ten minutes before the light goes off."},
            {"name": "Christmas Eve for grown-ups",
             "plan": "Christmas Eve and Other Stories while the food goes in, then Ebenezer if it is still showing near "
                     "you. If you would rather stay in, A Child's Christmas in Wales with the lights low, and the Seinfeld "
                     "Festivus episode for anyone who wants to air a grievance before bed."},
            {"name": "A night out with friends in December",
             "plan": "Violent Night 2 at the cinema on its opening weekend, then back to someone's flat for The Office's "
                     "Christmas Party and Community's stop-motion episode, which make a forty-five-minute double bill. "
                     "Save The Bear's Fishes for a quieter night, when nobody has to be cheerful afterwards."},
            {"name": "Christmas Day afternoon",
             "plan": "Arthur Christmas after lunch, when the older relatives start to nod off, then The Muppet Christmas "
                     "Carol from the hub once the children wake everyone up again. Finish the day with the first "
                     "Simpsons episode, which is twenty-two minutes long and about a family that can't afford Christmas."},
            {"name": "Boxing Day and the days after",
             "plan": "The Snowman in the morning, A Christmas Gift for You from Phil Spector while the kitchen gets "
                     "cleared, and a new farm in Stardew Valley in the afternoon. Keep Letters from Father Christmas by "
                     "the bed and read one letter a night until New Year."},
            {"name": "Christmas on your own",
             "plan": "Pick one new film for the evening, The Man with the Bag if you want noise or In a Holidaze if you "
                     "want a romance, then Batman: Arkham Origins for as long as you like. Being alone at Christmas can "
                     "be peaceful. The reading and listening guide has a whole shelf for the last hour of the night if "
                     "it isn't."},
        ],
        "faq": [
            ("What new Christmas movies are out in 2026?",
             "In theaters, Ebenezer opened on November 13 and Violent Night 2 opens on December 4. On streaming, "
             "Netflix has A Dog's Perfect Christmas (November 4), Tyler Perry's The Gospel of Christmas (November 11), "
             "The Christmas Switch (November 12), Guarding Stars (November 18) and In a Holidaze (December 2). Prime "
             "Video has Clashing Through the Snow (November 23) and The Man with the Bag (December 2), Hulu has The 12 "
             "Dates of Christmas (November 6), and Disney+ has Diary of a Wimpy Kid Christmas: The Getaway (December 4). "
             "The calendar on this page has every date and where to find each one."),
            ("When can I stream Ebenezer?",
             "Paramount hadn't announced a streaming date when we checked on November 20. It opened in US theaters on "
             "November 13. Paramount's films usually move to Paramount+ some weeks after they leave theaters, so if you "
             "want to see it before Christmas, the cinema is the safe bet."),
            ("Is Violent Night 2 suitable for children?",
             "No. The first Violent Night was rated R for strong bloody violence and language throughout, and the "
             "sequel comes from the same director and writers. For a Santa film the whole family can watch, try "
             "Arthur Christmas on this page or The Muppet Christmas Carol on the holiday hub."),
            ("Is there a Doctor Who Christmas special in 2026?",
             "No. The BBC had promised one, then said on June 10, 2026 that it would not make a one-off special and "
             "would put the money into the show's long-term future instead. No date has been given for new episodes. "
             "If you want a Christmas Carol with ghosts in it this year, Ebenezer is the one."),
            ("What Christmas specials are on TV this year?",
             "The biggest new ones are on Wednesday, December 2: Christmas in Rockefeller Center at 7 p.m. and "
             "Christmas With Snoop at 10 p.m., both on NBC. ABC has its Disney Holiday Spectacular on November 30, CMA "
             "Country Christmas on December 1, iHeartRadio Jingle Ball on December 17 and the Disney Parks parade on "
             "Christmas morning. All times are Eastern and can change, so check your listings on the day."),
            ("What day of the week is Christmas 2026?",
             "Friday, December 25, so Christmas Eve is a Thursday and New Year's Eve the Thursday after. In the United "
             "Kingdom Boxing Day falls on a Saturday, and the bank holiday for it moves to Monday, December 28."),
            ("Why does saving a Christmas episode add the whole series?",
             "OmniTrackr keeps a show in your library as one entry, with its seasons and episodes inside it. Saving "
             "The Office from this page adds the series as not started. You can then mark the single episode as "
             "watched in its episode guide, or carry on from there."),
        ],
        "method": [
            "Prepared by OmniTrackr with AI assistance and reviewed by the site owner before publishing. The release "
            "dates come from the studios', streamers' and networks' own announcements, as reported by the sources "
            "below, and were checked on November 20, 2026. Dates are for the United States and TV times are Eastern. "
            "Dates move, so check the service before you plan a night around one.",
            "Several of the new films weren't out when we wrote this. We haven't seen them, so their write-ups say "
            "what each film is and who it suits, not whether it is good. The fifteen older picks were chosen to fill "
            "the gaps left by the holiday hub, the advent calendar and the reading and listening guide, which is why "
            "some famous Christmas titles live on those pages instead. Every link on a pick goes to an OmniTrackr "
            "title page, none go to shops, and nothing here is sponsored.",
        ],
        "sources": [
            ("Netflix Christmas movie schedule 2026, What's on Netflix",
             "https://www.whats-on-netflix.com/coming-soon/netflix-2026-christmas-movie-lineup/"),
            ("Netflix's 2026 Christmas lineup, TVLine",
             "https://www.tvline.com/2283714/2026-netflix-christmas-movies-schedule-full-cast-list/"),
            ("Every new Christmas movie premiere, TVLine",
             "https://www.tvline.com/2287838/2026-christmas-tv-movie-schedule-hallmark-lifetime-netflix/"),
            ("Hallmark Channel 2026 Christmas movies, TVLine",
             "https://www.tvline.com/2261153/2026-hallmark-channel-christmas-movies-schedule-full-cast-photos-list/"),
            ("New Christmas movies to stream in 2026, TV Guide", "https://www.tvguide.com/galleries/new-christmas-movies-2026/"),
            ("Ebenezer: everything you need to know, Paramount+",
             "https://www.paramountplus.com/sneak-peak/ebenezer-everything-you-need-to-know/"),
            ("Violent Night 2, Wikipedia", "https://en.wikipedia.org/wiki/Violent_Night_2"),
            ("The Man with the Bag, Wikipedia", "https://en.wikipedia.org/wiki/The_Man_with_the_Bag_(film)"),
            ("Diary of a Wimpy Kid Christmas: The Getaway release date, What's on Disney Plus",
             "https://whatsondisneyplus.com/diary-of-a-wimpy-kid-christmas-the-getaway-disney-release-date-announced/"),
            ("Every 2026 Christmas special coming to TV, Marie Claire",
             "https://www.marieclaire.com/culture/tv-shows/best-christmas-specials-2026/"),
            ("CBS and ABC 2026 holiday special schedules, Western Mass News",
             "https://www.westernmassnews.com/2026/11/05/cbs-abc-announce-2026-holiday-special-schedules/"),
            ("Sufjan Stevens announces Worst Christmas Ever!, JamBase",
             "https://www.jambase.com/article/sufjan-stevens-worst-christmas-ever-compilation-holiday-album"),
            ("Alanis Morissette announces a Christmas album, Stereogum",
             "https://stereogum.com/2514139/alanis-morissette-announces-new-christmas-album-feat-brandi-carlile-steve-martin-martin-short/music"),
            ("The 2026 Doctor Who Christmas special is cancelled, The A.V. Club",
             "https://www.avclub.com/doctor-who-christmas-special-2026-cancelled"),
            ("A Child's Christmas in Wales (1952), Library of Congress",
             "https://blogs.loc.gov/now-see-hear/2022/12/from-the-national-recording-registry-a-childs-christmas-in-wales-1952/"),
        ],
    },
    "thanksgiving": {
        "path": "/holidays/thanksgiving",
        "parent": "holidays",
        "name": "Thanksgiving weekend guide",
        "short": "Thanksgiving",
        "theme": "holiday",
        "published": "2026-11-06",
        "reviewed": "2026-11-06",
        "search_title": "Thanksgiving weekend guide: what to watch, play and listen to with family, Wednesday to Sunday",
        "headline": "Thanksgiving weekend, Wednesday to Sunday",
        "deck": ("Twenty picks for the four days of the long weekend, from the drive there to the drive home: "
                 "audiobooks for the car, games the whole table can play after dinner, films for the day after "
                 "and something for the quiet end, across all nine formats OmniTrackr tracks."),
        "summary": ("A day-by-day Thanksgiving weekend guide with twenty picks: audiobooks and podcasts for the drive, "
                    "party games for after dinner, films and shows for the day after, and quieter picks for Sunday."),
        "card": "Twenty picks for the long weekend, from the drive there to the drive home.",
        "eyebrow": "THANKSGIVING 2026",
        "related_heading": "More for the holidays",
        "intro": [
            "Thanksgiving in the United States falls on Thursday, November 26 this year, and for most families it is "
            "a four-day event. People drive or fly on Wednesday. They spend Thursday in the kitchen and at the table, "
            "Friday on the sofa with leftovers, and Saturday and Sunday getting everybody home again. Each of those "
            "days asks for something different from the people in the house, and from whatever is on the screen or "
            "the speaker.",
            "So this guide follows the weekend in order. There are four shelves of five picks, one for each stretch "
            "of it, and between them they cover every format OmniTrackr tracks: films, TV, anime, games, books, "
            "albums, manga, podcasts and audiobooks. Each pick says how long it takes, who in the room it suits, and "
            "what to know before you press play.",
            "The holiday hub already has a Thanksgiving shelf, Around the table, with six picks such as Planes, "
            "Trains and Automobiles and the Friends Thanksgiving episodes. None of them are repeated here, and the "
            "plans at the bottom of the page use both.",
        ],
        "shelves": [
            {
                "key": "the-drive-there",
                "name": "The drive there",
                "when": "WEDNESDAY",
                "tagline": "For the car, the train and the airport queue.",
                "intro": [
                    "The day before Thanksgiving is one of the busiest travel days of the American year, and most of "
                    "it is spent sitting still: in traffic, at a gate, in a car with people of very different ages "
                    "who all want something different from the speakers.",
                    "These five are for ears only. Two audiobooks, two podcasts and an album, and each one says who "
                    "in the car it works for. Download them before you leave. Signal on a highway is never as good "
                    "as you hope.",
                ],
                "picks": [
                    {"kind": "audiobook", "title": "The Hobbit", "year": 2020, "creator": "J.R.R. Tolkien",
                     "extra": {"narrator": "Andy Serkis", "length_hours": 10.4},
                     "time": "About ten and a half hours, in nineteen chapters",
                     "why": "Andy Serkis, who played Gollum in Peter Jackson's films, reads Tolkien's 1937 novel and "
                            "gives every character a voice of their own: thirteen dwarves, three trolls, a dragon "
                            "and, in the chapter called Riddles in the Dark, Gollum. Bilbo's story is one very long "
                            "journey with a lot of stops for food, which makes it good company in a car.",
                     "note": "A chapter runs about half an hour, a good length between rest stops. Ten-year-olds and "
                             "grandparents tend to enjoy it equally. Save Riddles in the Dark, the fifth chapter, for "
                             "a stretch when everyone is awake.",
                     "caveat": "Peril and a battle near the end, and the spiders and the dragon can frighten younger "
                               "children. Serkis has also recorded The Lord of the Rings, if the car wants more."},
                    {"kind": "audiobook", "title": "Remarkably Bright Creatures", "year": 2022, "creator": "Shelby Van Pelt",
                     "time": "A full novel, a long day's driving or two shorter ones",
                     "why": "Tova Sullivan is seventy, a widow, and works the night shift cleaning a small aquarium in "
                            "a town in Washington state. Marcellus, the giant Pacific octopus in one of the tanks, is "
                            "grumpy, clever and counting the days he has left, and some chapters are his. Then "
                            "Cameron, a man in his thirties who has never stuck at anything, arrives in town looking "
                            "for the father he never met. It is warm and funny about the ways families get put "
                            "together.",
                     "note": "Good for a car of adults and older teenagers who want a story with no violence in it. "
                             "Marcellus's chapters are the ones people quote at the next stop.",
                     "caveat": "Grief runs all through it: Tova's son disappeared as a teenager, years before the book "
                               "starts. A couple of the plot's coincidences are easy to see coming."},
                    {"kind": "podcast", "title": "Wow in the World", "year": 2017, "creator": "Mindy Thomas and Guy Raz",
                     "time": "Episodes of twenty to thirty minutes",
                     "why": "A science show for children of about five to ten. Each episode takes one real piece of "
                            "research, often from that month's news, and turns it into a loud, silly adventure "
                            "between the two hosts, with sound effects and a lot of shouting. The science is right, "
                            "and it is one of the few children's podcasts that the adults in the front can stand for "
                            "more than one episode.",
                     "note": "Let the youngest choose episodes from the titles, which are as silly as the shows. Two "
                             "or three in a row is about right before everyone needs a break.",
                     "caveat": "Fast and noisy. Most children decide it is babyish somewhere around eleven."},
                    {"kind": "podcast", "title": "Wait Wait... Don't Tell Me!", "year": 1998, "creator": "NPR",
                     "time": "Weekly episodes of about fifty minutes",
                     "why": "NPR's weekly news quiz. A panel of comedians answers questions about the week's news, "
                            "listeners call in to play for a prize, and a famous guest takes a quiz about something "
                            "they know nothing about. For a car with three generations in it, it works better than "
                            "most comedy: the news gives everyone something to talk about, and it is public radio, "
                            "so the jokes stay mild.",
                     "note": "Episodes from a few weeks back work just as well as the newest. Half the fun is "
                             "remembering news you had already forgotten.",
                     "caveat": "American news and politics, and the panel teases everyone. Children under about twelve "
                               "will miss most of the jokes."},
                    {"kind": "album", "title": "Graceland", "year": 1986, "creator": "Paul Simon",
                     "time": "Under forty-five minutes",
                     "why": "Simon recorded much of Graceland in Johannesburg with South African musicians, and "
                            "Ladysmith Black Mambazo sing on Homeless and Diamonds on the Soles of Her Shoes. It won "
                            "the Grammy for Album of the Year. It is a perfect car record. The bass lines carry it, "
                            "the grandparents know You Can Call Me Al, and the children will know it by the third "
                            "time round.",
                     "note": "Put it on when the car goes quiet after the first hour, and again for the last one.",
                     "caveat": "Simon made it in breach of the UN cultural boycott of apartheid South Africa. That was "
                               "controversial at the time, and still is for some listeners. Nothing in the lyrics "
                               "to worry about."},
                ],
            },
            {
                "key": "the-big-day",
                "name": "The big day",
                "when": "THURSDAY",
                "tagline": "For the kitchen, the table and the hour after pie.",
                "intro": [
                    "Thanksgiving Day has a shape. There are hours of cooking, a long meal, then a stretch when "
                    "everyone is full and nobody wants to move. The parade and the football take care of some of it.",
                    "These five cover the rest: an album to cook to, a short special to keep children busy while the "
                    "turkey rests, a sitcom about a cook who takes the day too seriously, and two games the whole "
                    "table can play once the plates are cleared, including the relatives who say they don't play "
                    "games.",
                ],
                "picks": [
                    {"kind": "album", "title": "Getz/Gilberto", "year": 1964, "creator": "Stan Getz and João Gilberto",
                     "time": "Just over half an hour; set it to repeat",
                     "why": "The American saxophonist Stan Getz recorded these bossa nova songs in New York with the "
                            "Brazilian guitarist and singer João Gilberto, with Antônio Carlos Jobim, who wrote most "
                            "of them, on piano. Astrud Gilberto sings The Girl from Ipanema in English. It is relaxed "
                            "and warm and quiet enough to talk over, and almost nobody dislikes it, which makes it the "
                            "right record for a kitchen full of people with opinions about gravy.",
                     "note": "It is short, so put it on repeat. Nobody notices the second time through.",
                     "caveat": "Mostly sung in Portuguese. If the kitchen wants something to sing along to, play "
                               "Graceland instead."},
                    {"kind": "movie", "title": "A Charlie Brown Thanksgiving", "year": 1973, "creator": "Bill Melendez",
                     "time": "A television special, about twenty-five minutes",
                     "why": "Peppermint Patty invites herself, Marcie and Franklin to Charlie Brown's for Thanksgiving "
                            "dinner, and he is too polite to say no, even though he can't cook and his family is "
                            "going to his grandmother's. Snoopy and Woodstock make the meal: toast, pretzels, popcorn "
                            "and jelly beans, served on a ping-pong table in the garden. Charles Schulz wrote it and "
                            "Vince Guaraldi wrote the music.",
                     "note": "Put it on while the turkey rests and the children are underfoot. It is about as long as "
                             "they can wait for dinner.",
                     "caveat": "Linus's short speech about the first Thanksgiving is the cheerful 1970s version, with "
                               "nothing about the Wampanoag; This Land Is Their Land, on the last shelf, tells the "
                               "rest. Apple's streaming service has shown the special free for a few days around "
                               "Thanksgiving in recent years."},
                    {"kind": "tv", "title": "Bob's Burgers", "year": 2011, "creator": "Loren Bouchard",
                     "time": "Half-hour episodes; the Thanksgiving ones stand alone",
                     "why": "Bob Belcher runs a struggling burger restaurant with his wife Linda and their three "
                            "children, and Thanksgiving is his favourite day of the year, the one holiday that is "
                            "entirely about food. The show has made Thanksgiving episodes for most of its run, and "
                            "none of them needs any background. In Turkey in a Can, from the fourth season, someone "
                            "keeps dropping Bob's carefully brined turkey in the toilet, and the family turns "
                            "detective.",
                     "note": "Watch Turkey in a Can the night before if you are hosting for the first time. It is "
                             "about a cook losing his mind over a bird, and it helps to see someone have a worse day "
                             "than you.",
                     "caveat": "Made for adults, with some innuendo. Most of it goes over younger children's heads."},
                    {"kind": "game", "title": "The Jackbox Party Pack 3", "year": 2016, "creator": "Jackbox Games",
                     "time": "Games of fifteen to twenty minutes",
                     "why": "Everybody plays on their own phone through a web browser, so nobody needs a controller or "
                            "to have played a video game before. Up to eight people play at once and anyone else in "
                            "the room can join as the audience. In Quiplash 2 you write the funniest answer you can "
                            "to a prompt and everyone votes; Trivia Murder Party is a quiz in a killer's hotel where "
                            "a wrong answer sends you to a mini-game to survive.",
                     "note": "Start with Quiplash. A grandparent who has never touched a games console can win it on "
                             "the first round, and they usually do.",
                     "caveat": "The players write the answers, so the jokes are only as clean as your relatives. It "
                               "runs on a console, PC or streaming box connected to the TV, and every player needs "
                               "a phone and must be able to read and type quickly."},
                    {"kind": "game", "title": "Clubhouse Games: 51 Worldwide Classics", "year": 2020, "creator": "NDcube",
                     "time": "Pick any game; most take a few minutes",
                     "why": "Fifty-one card, board and table games on one Nintendo Switch cartridge, among them chess, "
                            "dominoes, mahjong, mancala, backgammon and darts. Every game explains its own rules. This "
                            "is the one for the grandparent who would never pick up a Mario game, because they "
                            "already know the rules of half of them.",
                     "note": "Pass a controller to each player; most games are played on one shared screen. Dominoes "
                             "and mancala are short enough to fit between dinner and pie.",
                     "caveat": "Switch only. Some card games are poker and blackjack, played for points. Online play "
                               "needs a Nintendo Switch Online membership."},
                ],
            },
            {
                "key": "the-day-after",
                "name": "The day after",
                "when": "FRIDAY",
                "tagline": "For leftovers, long sofa days and a houseful of cousins.",
                "intro": [
                    "Black Friday is for shopping if you want it to be. In plenty of houses it is the laziest day of "
                    "the year instead: leftovers for every meal, nobody in a hurry to leave, and a room of cousins "
                    "who need something to do.",
                    "These five are for long stretches on the sofa. Three are about food, because on Friday the "
                    "kitchen is still the busiest room in the house, and there is a party game for the cousins and a "
                    "murder mystery for the evening.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Clue", "year": 1985, "creator": "Jonathan Lynn",
                     "time": "One film, about an hour and a half",
                     "why": "New England, 1954. Six guests arrive at a mansion for dinner, each given a false name "
                            "from the board game, and the butler, Wadsworth (Tim Curry, at full speed), tells them "
                            "their host has been blackmailing all of them. Then people start dying. It is quick and "
                            "very funny, Madeline Kahn's speech about flames is the line everyone "
                            "quotes, and cinemas showed one of three different endings depending on where you saw "
                            "it.",
                     "note": "Good with teenagers and anyone who played the board game as a child. Most home versions "
                             "play all three endings back to back, so let the room argue about which one is right.",
                     "caveat": "Rated PG in the US, with innuendo, a few killings played for laughs and some jokes that "
                               "have dated. It flopped in 1985 and found its audience on video."},
                    {"kind": "tv", "title": "The Great British Bake Off", "year": 2010, "creator": "Love Productions",
                     "time": "About ten hour-long episodes a series, and more than a dozen series",
                     "why": "A dozen amateur bakers in a tent in the English countryside face three challenges every "
                            "week: a signature bake, a technical challenge with half the instructions missing, and a "
                            "showstopper. One goes home each week, and the prize is a cake stand. Nobody is cruel, "
                            "the contestants help each other finish, and it suits a mixed room better than almost "
                            "anything else on television. Children like the disasters and grandparents like the "
                            "manners.",
                     "note": "Choose any series and start at the first episode; you will have a favourite baker by the "
                             "end of it. In the US it is called The Great British Baking Show and streams on Netflix "
                             "in collections whose numbers don't match the British series.",
                     "caveat": "Very gentle, with some British innuendo from the presenters. You will want to bake, "
                               "which may be a mistake with a fridge full of leftovers."},
                    {"kind": "anime", "title": "Delicious in Dungeon", "year": 2024, "creator": "Studio Trigger",
                     "time": "Twenty-four episodes in the first season",
                     "why": "Deep in a dungeon, a red dragon eats Laios's sister Falin. The rest of the party has no "
                            "money left for supplies, so they decide to go back down to rescue her and eat whatever "
                            "they can kill on the way, with help from Senshi, a dwarf who has been cooking monsters "
                            "for years. The first meal is a hotpot of giant scorpion and walking mushroom. It is an "
                            "adventure and a cookery show at once, based on Ryoko Kui's manga, and the recipes are "
                            "worked out with real care for how a monster would taste.",
                     "note": "The right show for a day of leftovers, since everyone in it is trying to make a decent "
                             "meal out of whatever is around. Teenagers who play Dungeons & Dragons will take to it "
                             "at once.",
                     "caveat": "Monster gore, mostly cartoonish, and some properly dark turns later in the season. It "
                               "streams on Netflix in most countries."},
                    {"kind": "manga", "title": "What Did You Eat Yesterday?", "year": 2007, "creator": "Fumi Yoshinaga",
                     "time": "More than twenty volumes; each chapter is one meal",
                     "why": "Shiro Kakei is a careful, budget-minded lawyer in Tokyo who cooks dinner every evening for "
                            "his partner Kenji, a cheerful hairdresser. Each chapter follows one meal from the "
                            "supermarket to the table, every step written out, while the lives of two men in their "
                            "forties move slowly around it: friends, work, ageing, and Shiro's parents learning, "
                            "over many years, to accept their son. Those chapters about his parents read very "
                            "differently in a week you have just spent with yours.",
                     "note": "Read a chapter, then cook it. The recipes work, and they are written for a small kitchen "
                             "and a tight budget, which is handy once the leftovers run out.",
                     "caveat": "Almost nothing dramatic happens, by design. The English edition is published by "
                               "Vertical; there is also a gentle live-action TV series."},
                    {"kind": "game", "title": "Mario Kart 8 Deluxe", "year": 2017, "creator": "Nintendo",
                     "time": "Races of about three minutes",
                     "why": "Four people race on one Switch with the screen split four ways. Smart steering keeps a "
                            "new player on the track and auto-accelerate means they only have to steer, so a "
                            "five-year-old and an uncle can race each other and both have a chance. The items, the "
                            "blue shell above all, do the rest. With the Booster Course Pass there are ninety-six "
                            "tracks.",
                     "note": "Turn on smart steering for anyone under eight or anyone who has never held a controller, "
                             "and start at 50cc until everybody is warmed up. Mario Kart World is the newer game, on "
                             "Switch 2; 8 Deluxe is the one most families already own.",
                     "caveat": "Switch only. The blue shell has ended friendships, and cousins remember."},
                ],
            },
            {
                "key": "the-quiet-end",
                "name": "The quiet end",
                "when": "SATURDAY AND SUNDAY",
                "tagline": "For after the guests go, and the drive home.",
                "intro": [
                    "By Saturday the house is emptying. Somebody is packing the car, somebody is asleep on the sofa, "
                    "and the adults finally get a few hours to themselves.",
                    "These five are for that stretch: a film and a half-hour of television about families at the "
                    "holiday, a history that tells the story of 1621 properly, a long novel that runs from here to "
                    "Christmas, and an album for the dark drive home.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Home for the Holidays", "year": 1995, "creator": "Jodie Foster",
                     "time": "One film, about an hour and forty minutes",
                     "why": "Claudia Larson, played by Holly Hunter, loses her job the day she flies home to Baltimore "
                            "for Thanksgiving. Waiting for her are her parents (Anne Bancroft and Charles Durning), a "
                            "sister who can't stand her, and her brother Tommy, played by Robert Downey Jr., who "
                            "spends the day making everything worse and funnier. Jodie Foster directed it, and it "
                            "understands that the funniest people at a family dinner are often the hardest to sit "
                            "next to.",
                     "note": "Watch it the weekend after, when you can laugh at the dinner scenes instead of reliving "
                             "them. Downey is the reason to stay to the end.",
                     "caveat": "Rated PG-13 in the US for language and some sexual references. Its family fights feel "
                               "real, which is the point and also occasionally the problem."},
                    {"kind": "tv", "title": "Master of None", "year": 2015, "creator": "Aziz Ansari and Alan Yang",
                     "time": "One half-hour episode: Thanksgiving, the eighth of the second season",
                     "why": "The episode follows Denise, played by Lena Waithe, and her friend Dev through Thanksgiving "
                            "dinners at Denise's family home from the 1990s to the present, as Denise realises she is "
                            "gay and comes out to her mother, played by Angela Bassett. Waithe and Ansari won the "
                            "Emmy for comedy writing for it, and Waithe was the first Black woman to win that award. "
                            "We think it is the best half-hour of television about a family holiday.",
                     "note": "It stands completely alone, so you don't need to have seen the rest of the series.",
                     "caveat": "Strong language. The scenes between Denise and her mother hurt for a long time before "
                               "they get kind."},
                    {"kind": "book", "title": "This Land Is Their Land", "year": 2019, "creator": "David J. Silverman",
                     "time": "A history of about five hundred pages",
                     "why": "Its full subtitle is The Wampanoag Indians, Plymouth Colony, and the Troubled History of "
                            "Thanksgiving. Silverman, a historian at George Washington University, tells the story "
                            "from the Wampanoag side. He starts decades before 1621, with European slave raids on the "
                            "coast and the epidemic that killed many of the peoples there, and follows the alliance "
                            "between the Wampanoag leader Ousamequin, often called Massasoit, and the Plymouth "
                            "colonists through to the war that ended it in 1675. It also explains why some Wampanoag "
                            "people mark the fourth Thursday of November as a National Day of Mourning.",
                     "note": "The chapters about 1621 can be read on their own over the weekend, while the school "
                             "version of the story is fresh in everyone's mind.",
                     "caveat": "Serious history, with violence, slavery and epidemic disease. It leaves the question of "
                               "how to mark the holiday to the reader."},
                    {"kind": "book", "title": "The Corrections", "year": 2001, "creator": "Jonathan Franzen",
                     "time": "A long novel, close to six hundred pages",
                     "why": "Enid Lambert wants her three grown children home in their Midwestern town for one last "
                            "Christmas, while their father Alfred, who has Parkinson's, can still enjoy it. Gary, Chip "
                            "and Denise all have reasons not to come. Franzen tells each of their stories in turn "
                            "until the family is finally in one house again. It won the National Book Award in 2001, "
                            "and it is very funny about families and very sad about growing old.",
                     "note": "Start it on the way home from Thanksgiving and you will reach the Lamberts' Christmas at "
                             "about the right time.",
                     "caveat": "Long, dense and often bleak, with frank sex, drug use and a close description of a "
                               "parent's decline."},
                    {"kind": "album", "title": "Harvest", "year": 1972, "creator": "Neil Young",
                     "time": "About forty minutes",
                     "why": "Young recorded most of Harvest in Nashville with a band he called the Stray Gators. It "
                            "went to number one in 1972, and it has Old Man and Heart of Gold, his only number-one "
                            "single. It is slow, a little ragged and very warm, and it sounds like the last weekend "
                            "of autumn.",
                     "note": "For the drive home, once it gets dark. Play Old Man if your father is in the passenger "
                             "seat.",
                     "caveat": "Two songs with the London Symphony Orchestra are far grander than the rest. The Needle "
                               "and the Damage Done is about friends lost to heroin."},
                ],
            },
        ],
        "plan_label": "Plan your weekend",
        "plan_heading": "Five kinds of Thanksgiving weekend",
        "nights": [
            {"name": "A long drive with children",
             "plan": "The Hobbit for the first stretch, while everyone is fresh. Wow in the World when attention runs "
                     "out, and Graceland for the last hour. When you arrive, A Charlie Brown Thanksgiving, and on the "
                     "holiday hub, Sweetness and Lightning for the night before the big meal."},
            {"name": "Hosting for the first time",
             "plan": "Bob's Burgers' Turkey in a Can the night before, to see someone have a worse day than you. "
                     "Getz/Gilberto on repeat while you cook, the Charlie Brown special to keep the children out of "
                     "the kitchen, and the Jackbox Party Pack once the plates are cleared. Keep Overcooked! 2, from "
                     "the hub, for anyone who still wants to cook after all that."},
            {"name": "Three generations and one television",
             "plan": "Clubhouse Games after lunch, so the grandparents can win at dominoes. A few episodes of Bake Off "
                     "in the afternoon, Mario Kart for the cousins before dinner, and Clue once everyone is back on "
                     "the sofa. Planes, Trains and Automobiles, on the hub, is the film to finish with."},
            {"name": "Friendsgiving",
             "plan": "Jackbox for as long as people can stand it, then Delicious in Dungeon for anyone who stays late. "
                     "Wait Wait... Don't Tell Me! on the drive over, and the Master of None episode for the morning "
                     "after, when the last guest is still asleep on your floor."},
            {"name": "Not going home this year",
             "plan": "Home for the Holidays, to remember what you are missing and what you aren't. A chapter of What "
                     "Did You Eat Yesterday? and then the same meal, cooked for yourself. This Land Is Their Land in "
                     "the afternoon, The Corrections from Sunday, and Harvest at the end of the day."},
        ],
        "faq": [
            ("When is Thanksgiving in 2026?",
             "Thanksgiving in the United States is on Thursday, November 26, 2026, the fourth Thursday of November. "
             "The Wednesday before and the Sunday after, November 25 and 29, are the busiest travel days. Canadian "
             "Thanksgiving was on Monday, October 12."),
            ("What are the best Thanksgiving TV episodes?",
             "A few that stand alone: The One with All the Thanksgivings in the fifth season of Friends, Thanksgiving "
             "Orphans in the fifth season of Cheers, A Deep-Fried Korean Thanksgiving in the third season of Gilmore "
             "Girls, Slapsgiving in the third season of How I Met Your Mother, Pangs in the fourth season of Buffy "
             "the Vampire Slayer, Turkey in a Can in the fourth season of Bob's Burgers, and Thanksgiving in the "
             "second season of Master of None. The last is the best of them and the least like a sitcom."),
            ("What games can the whole family play after Thanksgiving dinner?",
             "The Jackbox Party Pack 3 is the easiest for a big group, because everybody plays on their own phone. "
             "Clubhouse Games has card and board games older relatives already know. Mario Kart 8 Deluxe lets four "
             "people race on one screen with assists for beginners, and Overcooked! 2, on the holiday hub, is for a "
             "family that likes to shout."),
            ("What should we listen to on the Thanksgiving drive?",
             "For a car with children, The Hobbit read by Andy Serkis, or a few episodes of Wow in the World. For "
             "adults and older teenagers, the audiobook of Remarkably Bright Creatures or a stack of Wait Wait... "
             "Don't Tell Me! episodes. Graceland works for everybody, and Harvest suits the drive home after dark."),
            ("Where can I read the real history of the first Thanksgiving?",
             "David J. Silverman's This Land Is Their Land (2019) tells the story from the Wampanoag side, from the "
             "decades before 1621 to the war of 1675, and explains the National Day of Mourning held at Plymouth on "
             "Thanksgiving Day since 1970."),
            ("Are these picks suitable for children?",
             "Most of the first two shelves are, and The Great British Bake Off and Mario Kart work for all ages. "
             "Every pick has a caveat that says what is in it. The last shelf is mostly for adults."),
        ],
        "method": [
            "Prepared by OmniTrackr and reviewed by the site owner before publishing. We started from the four days "
            "most American families actually spend together at Thanksgiving, and from what each one needs: something "
            "everyone in the car can agree on, something to fill the kitchen, games for people who don't play games, "
            "and something quieter at the end. Then we chose five picks for each day across all nine formats. "
            "Nothing from the holiday hub's own Thanksgiving shelf is repeated.",
            "Caveats and running times are our own, checked against the works themselves and public sources such "
            "as publishers' and broadcasters' pages. They are not official ratings. Streaming availability changes "
            "from year to year and varies by country, so we only mention it where it is stable or where a free "
            "window is a tradition. Every link goes to an OmniTrackr title page and none go to shops. Nothing here "
            "is sponsored.",
        ],
    },

    "reading-and-listening": {
        "path": "/holidays/reading-and-listening",
        "parent": "holidays",
        "name": "December reading and listening guide",
        "short": "Reading and listening",
        "theme": "holiday",
        "published": "2026-11-06",
        "reviewed": "2026-11-06",
        "search_title": "What to read and listen to in December: books, audiobooks, podcasts, manga and albums for the holidays",
        "headline": "Long nights: what to read and listen to in December",
        "deck": ("Twenty books, audiobooks, podcasts, manga and albums for the darkest month: something to put on "
                 "while you wrap, something for the trip home, something for the snowed-in days after Christmas, "
                 "and something for the last hour of the night."),
        "summary": ("Books, audiobooks, podcasts, manga and albums for December, sorted by what you are doing: wrapping "
                    "and baking, travelling, the quiet days after Christmas, and late at night."),
        "card": "Twenty books, audiobooks, podcasts, manga and albums for the darkest month.",
        "eyebrow": "DECEMBER 2026",
        "related_heading": "More for the holidays",
        "intro": [
            "Most holiday lists are lists of things to watch, which is fair: December is the month of the big film "
            "and the box set. But a lot of the season happens with your eyes and hands busy. You wrap presents and "
            "bake and untangle lights. You sit on trains and in airport lounges, and you get through the strange, "
            "dark days between Christmas and New Year when the television has nothing left to offer.",
            "This guide is for those hours, and it only uses the formats you can read or listen to: books, "
            "audiobooks, podcasts, manga and albums. There are four shelves of five, one for each kind of December "
            "time. A few picks are Christmassy and most are simply wintry, and each says how long it takes and what "
            "to know first.",
            "For films, shows, anime and games, see the holiday hub, which sorts twenty-four picks by how festive "
            "they are. None of its books or albums are repeated here.",
        ],
        "shelves": [
            {
                "key": "hands-busy",
                "name": "While your hands are busy",
                "when": "WRAPPING, BAKING, DECORATING",
                "tagline": "For wrapping presents, baking and putting up the lights.",
                "intro": [
                    "Wrapping and baking take more time than anyone plans for, and they leave your ears free. Music "
                    "is the obvious answer, but a podcast that teaches you something works just as well, and you "
                    "won't have heard it twelve times already this month.",
                    "Three albums and two podcasts. The albums are holiday records that aren't the usual playlist, "
                    "and the podcasts are about music, so they suit a kitchen with a speaker in it.",
                ],
                "picks": [
                    {"kind": "album", "title": "Ella Wishes You a Swinging Christmas", "year": 1960, "creator": "Ella Fitzgerald",
                     "time": "A short album, about half an hour",
                     "why": "Fitzgerald recorded it in Los Angeles with an orchestra arranged and conducted by Frank "
                            "DeVol, and she sings the secular, sleigh-bell side of the season: Jingle Bells, Let It "
                            "Snow, Sleigh Ride, Rudolph and Frosty. It swings hard, it is cheerful without being "
                            "sugary, and she makes every song sound easy.",
                     "note": "Put it on the day the decorations come out. It is short enough to play twice through a "
                             "batch of wrapping and good-natured enough that nobody asks for it to be turned off.",
                     "caveat": "No carols and nothing sad. Pair it with the Sufjan Stevens set for more range. Later "
                               "reissues add extra tracks."},
                    {"kind": "album", "title": "The Nutcracker Suite", "year": 1960, "creator": "Duke Ellington",
                     "time": "About half an hour",
                     "why": "Ellington and his co-writer Billy Strayhorn rearranged Tchaikovsky's ballet music for "
                            "Ellington's big band and gave the movements new names: the Dance of the Sugar Plum "
                            "Fairy became Sugar Rum Cherry, the Russian dance became The Volga Vouty, and the march "
                            "became the Peanut Brittle Brigade. The tunes are all still there, swung.",
                     "note": "If someone in the house is going to see the ballet this month, or dancing in it, play "
                             "the two versions back to back and guess which tune is which.",
                     "caveat": "Instrumental. Some reissues pair it with Ellington's Peer Gynt suite, which is less "
                               "seasonal."},
                    {"kind": "album", "title": "Songs for Christmas", "year": 2006, "creator": "Sufjan Stevens",
                     "time": "Five EPs and forty-two songs, over two hours",
                     "why": "For several years Stevens recorded a Christmas EP as a present for friends and family, "
                            "then released five of them together in a box. It mixes carols and hymns (O Come, O Come, "
                            "Emmanuel; Amazing Grace) with songs of his own, played on banjo, recorders, piano and "
                            "whatever else was lying around. It sounds homemade, which is most of the charm.",
                     "note": "It is long enough to cover a whole afternoon of wrapping. The later EPs have more of his "
                             "own songs; the earlier ones are closer to home recordings.",
                     "caveat": "Sincere hymns sit next to jokes, sometimes in the same song, and a few of the original "
                               "songs are about loneliness at Christmas."},
                    {"kind": "podcast", "title": "Dolly Parton's America", "year": 2019, "creator": "Jad Abumrad",
                     "time": "A limited series of about nine episodes",
                     "why": "Jad Abumrad, who co-founded Radiolab, got to Dolly Parton partly because his father, a "
                            "Nashville surgeon, was her doctor. He spent hours interviewing "
                            "her and asked why people who agree on nothing else all love her. The series covers her "
                            "childhood in the Smoky Mountains, her years with Porter Wagoner, Jolene and 9 to 5, and "
                            "the way she answers, or doesn't answer, questions about politics and feminism.",
                     "note": "The episodes are long enough for one batch of cookies each. You will want to play one of "
                             "her Christmas albums when you finish.",
                     "caveat": "Some discussion of politics, gender and class, all of it gentle. Made by WNYC Studios "
                               "and free on any podcast app."},
                    {"kind": "podcast", "title": "Strong Songs", "year": 2018, "creator": "Kirk Hamilton",
                     "time": "Episodes of about an hour, one song each",
                     "why": "Kirk Hamilton, a musician and former games journalist, takes a single song apart in each "
                            "episode, from Motown to prog rock: the chords, the drum part, the moment in the bridge "
                            "where everything changes. He plays examples on guitar and keyboard as he goes. You come "
                            "out of every episode hearing a song you thought you knew differently.",
                     "note": "Pick episodes about songs everyone in the kitchen knows, then play the song itself "
                             "straight after.",
                     "caveat": "Some music theory, explained as he goes; you don't need to read music. Fine for all "
                               "ages."},
                ],
            },
            {
                "key": "on-the-way",
                "name": "On the way",
                "when": "TRAINS, PLANES, LONG DRIVES",
                "tagline": "For the trip to the in-laws and the trip back.",
                "intro": [
                    "December travel is longer than it needs to be: delayed trains, full flights, a drive across "
                    "three states in the dark. Audiobooks are made for it, and so are podcasts that tell one story "
                    "over many episodes.",
                    "Three audiobooks, one long podcast series and a manga for the child next to you. Each audiobook "
                    "is read by someone who makes it better than the page, and each one fills a long journey or "
                    "two.",
                ],
                "picks": [
                    {"kind": "audiobook", "title": "Yes Please", "year": 2014, "creator": "Amy Poehler",
                     "time": "An afternoon's listening, or one long flight",
                     "why": "Poehler's memoir of improv in Chicago and New York, Saturday Night Live and Parks and "
                            "Recreation, read by her, with guest readers dropping in, Seth Meyers and Patrick "
                            "Stewart among them. It is funny, generous about other people, and franker than most "
                            "celebrity memoirs about work, divorce and getting older.",
                     "note": "Listen rather than read. The guest readers are half the fun, and Poehler's timing is "
                             "the other half.",
                     "caveat": "Swearing, some drug stories and frank talk about her divorce. Fans of SNL and Parks "
                               "and Recreation get the most out of it."},
                    {"kind": "audiobook", "title": "The Thursday Murder Club", "year": 2020, "creator": "Richard Osman",
                     "extra": {"narrator": "Lesley Manville"},
                     "time": "A long journey's worth, about a working day",
                     "why": "Four residents of a retirement village in Kent meet every Thursday to look into old "
                            "unsolved murders, until a real one happens on their doorstep. Elizabeth seems to have "
                            "been some kind of spy, Joyce keeps a diary, Ibrahim is a retired psychiatrist and Ron "
                            "a retired union firebrand, and everyone underestimates all four of them. Lesley "
                            "Manville reads it, and her Joyce is perfect.",
                     "note": "Good for a car with grandparents in it, who tend to enjoy the four heroes running rings "
                             "round the police. There are several sequels if the journey is long.",
                     "caveat": "Murder, and gentle but real treatment of dementia and the end of life. The 2025 Netflix "
                               "film leaves out a lot of the book."},
                    {"kind": "audiobook", "title": "Mythos", "year": 2017, "creator": "Stephen Fry",
                     "time": "A long listen, two or three journeys",
                     "why": "Fry retells the Greek myths from the beginning, from Chaos and the Titans to the gods of "
                            "Olympus and the mortals they meddle with, and reads them himself. He tells them as "
                            "stories rather than lessons, with jokes and asides about where our words come from, and "
                            "his Zeus is very good. Heroes and Troy carry on from where it ends.",
                     "note": "Families with children who studied the Greek myths at school will all find something "
                             "here. Each myth stands alone, so it is easy to stop at a service station.",
                     "caveat": "The myths are full of violence, sex and gods behaving badly. Fry keeps the tone light "
                               "but leaves them in, so it is not one for small children."},
                    {"kind": "podcast", "title": "Serial", "year": 2014, "creator": "Sarah Koenig",
                     "time": "Season one: twelve episodes, about eight hours",
                     "why": "Koenig spent a year re-examining the 1999 murder of Hae Min Lee, a Baltimore teenager, and "
                            "the conviction of her former boyfriend, Adnan Syed, and released it one episode a week. "
                            "It is the podcast that made millions of people start listening to podcasts, and the "
                            "reporting still holds up a decade later.",
                     "note": "It is exactly the length of a long drive. Afterwards, read up on the case: it has changed "
                             "a great deal since 2014, and Syed was released in 2022.",
                     "caveat": "The real murder of a teenage girl, discussed in detail. Not for children."},
                    {"kind": "manga", "title": "Chi's Sweet Home", "year": 2004, "creator": "Konami Kanata",
                     "time": "Short chapters of a few pages each",
                     "why": "A grey-and-white kitten loses her mother on a walk and is taken in by the Yamada family, a "
                            "young couple and their small son, who live in a building that doesn't allow pets. Each "
                            "chapter is a few pages of Chi discovering something: the bath, a mirror, the vacuum "
                            "cleaner. The English edition from Vertical is printed in full colour.",
                     "note": "For the child in the next seat, or for you. It reads aloud well, since Chi talks in baby "
                             "talk.",
                     "caveat": "Very gentle. The first chapters show the kitten lost and crying, which can upset the "
                               "youngest readers."},
                ],
            },
            {
                "key": "snowed-in",
                "name": "Snowed in",
                "when": "THE DAYS AFTER CHRISTMAS",
                "tagline": "For the long nights and the quiet week before New Year.",
                "intro": [
                    "The week between Christmas and New Year is the one time of year when many people have days with "
                    "nothing in them. Nobody is sure what day it is, and a book you could never find time for gets "
                    "read in two sittings.",
                    "Four books and a long manga, all of them set in winter. One is a children's classic that takes "
                    "place over the twelve days of Christmas, one is a Christmas mystery, one is the funniest "
                    "Christmas book we know, and two are about surviving the cold.",
                ],
                "picks": [
                    {"kind": "book", "title": "The Dark Is Rising", "year": 1973, "creator": "Susan Cooper",
                     "time": "A children's novel of about two hundred and fifty pages",
                     "why": "On Midwinter Eve, the day before his eleventh birthday, Will Stanton, the seventh son of a "
                            "seventh son, learns that he is the last of the Old Ones, who guard the Light against the "
                            "Dark. Over the twelve days of Christmas the Dark comes for him through the snow around "
                            "his family's home in the Thames Valley. It is the second book in Cooper's sequence but "
                            "stands alone, and it won a Newbery Honor.",
                     "note": "The book starts on December 20 and ends on Twelfth Night, and in recent winters "
                             "thousands of readers have read it in real time, a chapter a day, in a read-along started "
                             "by the writer Robert Macfarlane. Start on the twentieth and you will finish on January "
                             "6.",
                     "caveat": "Written for children but properly frightening in places, with a slow middle. The 2007 "
                               "film changes almost everything."},
                    {"kind": "book", "title": "Hogfather", "year": 1996, "creator": "Terry Pratchett",
                     "time": "A novel of about four hundred pages",
                     "why": "On Hogswatchnight, the Discworld's version of Christmas Eve, the Hogfather has gone "
                            "missing. He is the Discworld's Father Christmas, and his sleigh is pulled by four wild "
                            "boars. So Death puts on the red suit and a false beard and does the rounds in his place, "
                            "while his granddaughter Susan tries to find out who would want to kill a children's "
                            "story. It is very funny, and the conversation at the end between Death and Susan about "
                            "why people need small beliefs is some of the best writing Pratchett did.",
                     "note": "You don't need to have read any other Discworld book first. Read it over two nights "
                             "around Christmas Eve.",
                     "caveat": "An assassin, a few deaths and some dark jokes. The two-part 2006 Sky adaptation is good "
                               "too, if someone in the house wants to watch instead."},
                    {"kind": "book", "title": "Hercule Poirot's Christmas", "year": 1938, "creator": "Agatha Christie",
                     "time": "A short novel, one or two evenings",
                     "why": "Simeon Lee, a rich and unpleasant old man, gathers his estranged family at his house for "
                            "Christmas and is found on Christmas Eve with his throat cut in a locked room. Poirot, "
                            "staying nearby for the holiday, is asked to help. In her dedication, Christie says her "
                            "brother-in-law had complained that her murders were getting too refined and asked for "
                            "a good violent one with lots of blood, so she wrote him this.",
                     "note": "Read it in the week after Christmas, when you can stay up and finish it in one go. The "
                             "solution is one of her fairest.",
                     "caveat": "Bloodier than most Christie, on purpose. Some attitudes, particularly towards a Spanish "
                               "character, are very much of their time."},
                    {"kind": "book", "title": "The Snow Child", "year": 2012, "creator": "Eowyn Ivey",
                     "time": "A novel of about four hundred pages",
                     "why": "Alaska, 1920. Jack and Mabel, a childless couple in their fifties, are homesteading and "
                            "close to giving up. On the night of the first snow they build a girl out of snow, and "
                            "the next morning she is gone, and a small, wild girl starts appearing at the edge of the "
                            "woods. Ivey took the idea from a Russian fairy tale and keeps you unsure for a long "
                            "time whether the girl is real. It was a finalist for the Pulitzer Prize.",
                     "note": "Read it in the darkest days of the year. It is about the hardest stretch of winter and "
                             "what gets people through it.",
                     "caveat": "Not at all Christmassy. There is hunting, a near-death in the cold and a sad ending, "
                               "though a fair one."},
                    {"kind": "manga", "title": "Golden Kamuy", "year": 2014, "creator": "Satoru Noda",
                     "time": "Thirty-one volumes, complete",
                     "why": "Hokkaido, just after the Russo-Japanese War. Saichi Sugimoto, a veteran nicknamed "
                            "Immortal, hears of a hoard of stolen Ainu gold whose location is tattooed across the "
                            "skins of escaped convicts. He teams up with Asirpa, a young Ainu girl who can hunt and "
                            "survive the northern winter better than any of the soldiers chasing them. It is a "
                            "treasure hunt, a western, a comedy and a guide to Ainu cooking all at once, and it "
                            "spends a lot of time in the snow.",
                     "note": "A binge for the dead week. The early volumes go fast, and it is hard to stop once the "
                             "convicts start turning up.",
                     "caveat": "Very violent, with gore and torture, and a lot of nudity played for laughs. Some "
                               "characters are grotesque on purpose."},
                ],
            },
            {
                "key": "after-dark",
                "name": "After everyone's asleep",
                "when": "THE LAST HOUR OF THE NIGHT",
                "tagline": "For the end of the day, with the house quiet.",
                "intro": [
                    "Holidays are crowded, and the best hour of the day is often the last one, when the house has gone "
                    "quiet and the lights on the tree are the only ones still on.",
                    "Two albums, an audiobook, a podcast and a manga, all for one person in a dark room. Nothing here "
                    "is festive. All of them are calm, and one is designed to put you to sleep.",
                ],
                "picks": [
                    {"kind": "album", "title": "The Köln Concert", "year": 1975, "creator": "Keith Jarrett",
                     "time": "About an hour of improvised solo piano",
                     "why": "Jarrett improvised the whole concert at the Cologne Opera House in January 1975, tired "
                            "and on a small, badly tuned piano that was not the one he had asked for. He worked "
                            "around its weak notes with long, repeating figures in the left hand, and the recording "
                            "became the best-selling solo piano album ever made.",
                     "note": "Listen to the first part, about twenty-six minutes, with the lights off. His humming and "
                             "groaning are part of the record.",
                     "caveat": "Long improvisations with no tunes to hum. Jarrett had two strokes in 2018 and no longer "
                               "performs."},
                    {"kind": "album", "title": "Pink Moon", "year": 1972, "creator": "Nick Drake",
                     "time": "Under half an hour",
                     "why": "Drake recorded it in two late-night sessions, almost nothing on it but his voice and his "
                            "guitar. Eleven songs, none of them long. It sold very little at the time, and he died "
                            "two years later, aged twenty-six. A car advert used the title song in 1999, and a new "
                            "generation found him.",
                     "note": "It is short enough to end one long evening. Play it twice if the first time goes too "
                             "fast.",
                     "caveat": "Quiet and sad. If this winter is a hard one for you, save it for spring."},
                    {"kind": "audiobook", "title": "The Night Circus", "year": 2011, "creator": "Erin Morgenstern",
                     "extra": {"narrator": "Jim Dale"},
                     "time": "A long novel, best in short sessions",
                     "why": "Le Cirque des Rêves appears without warning, opens only at night, and every tent is "
                            "striped in black and white. Behind it, two young magicians, Celia and Marco, have been "
                            "bound since childhood into a contest that neither of them understands, and they fall in "
                            "love. Jim Dale, who read the American Harry Potter audiobooks, gives every character "
                            "their own voice.",
                     "note": "Listen at night with the volume low, half an hour at a time. It is built from short "
                             "scenes, so you don't lose much if you drift off.",
                     "caveat": "More atmosphere than plot, and the timeline jumps around, which is harder to follow by "
                               "ear than on the page."},
                    {"kind": "podcast", "title": "Sleep With Me", "year": 2013, "creator": "Drew Ackerman",
                     "time": "Episodes of about an hour; you won't hear the end",
                     "why": "Drew Ackerman tells long, rambling, deliberately dull bedtime stories in a soft voice, "
                            "built to give an anxious mind something to hold onto until it lets go. It sounds like a "
                            "joke, and it has helped a lot of people sleep through some long nights.",
                     "note": "Set a sleep timer and don't try to follow it. Losing the thread is how it works.",
                     "caveat": "Never listen while driving. The free feed carries ads."},
                    {"kind": "manga", "title": "The Walking Man", "year": 1992, "creator": "Jiro Taniguchi",
                     "time": "One volume, an evening",
                     "why": "A man who has just moved to a Tokyo suburb goes for walks with his dog: in the rain, in "
                            "the snow, after dark. There is almost no dialogue and no plot. Each chapter is a few "
                            "pages of looking at streets, trees and neighbours, drawn in fine, patient detail, and "
                            "it slows your breathing down like very few books do.",
                     "note": "Read one or two walks before bed. If it snows where you are, go for one afterwards.",
                     "caveat": "If you need a story, this isn't it. Read right to left, like most manga."},
                ],
            },
        ],
        "plan_label": "Plan your December",
        "plan_heading": "Five kinds of December",
        "nights": [
            {"name": "A December of reading",
             "plan": "Hercule Poirot's Christmas in the first week, The Snow Child in the second, and Hogfather around "
                     "Christmas Eve. On December 20, start The Dark Is Rising and read a chapter a day until Twelfth "
                     "Night. The holiday hub's A Christmas Carol is short enough to fit in around them."},
            {"name": "The big trip home",
             "plan": "Serial for the drive there and The Thursday Murder Club for the drive back. Chi's Sweet Home for "
                     "the youngest, Mythos if the car is full of teenagers, and Yes Please if it's just you."},
            {"name": "Hosting Christmas",
             "plan": "Ella Wishes You a Swinging Christmas while the tree goes up, Dolly Parton's America through the "
                     "baking, and the Ellington Nutcracker when the guests arrive. Songs for Christmas for the "
                     "afternoon of wrapping, and the Köln Concert once everyone has gone to bed."},
            {"name": "Alone this year",
             "plan": "Strong Songs while you cook, Golden Kamuy for the long days, and The Night Circus at night. The "
                     "Walking Man for a snowy evening, and Sleep With Me if it's hard to sleep. Save Pink Moon for a "
                     "night that already feels good."},
            {"name": "Done with Christmas music",
             "plan": "Strong Songs and Dolly Parton's America instead of the radio, Pink Moon and the Köln Concert at "
                     "night, and Golden Kamuy for something with no tinsel at all. Björk's Vespertine, on the "
                     "holiday hub, is the winter album for the night you have had enough."},
        ],
        "faq": [
            ("What are good books to read in December?",
             "For winter atmosphere, The Dark Is Rising by Susan Cooper, which takes place over the twelve days of "
             "Christmas, and Eowyn Ivey's The Snow Child, set in Alaska. For Christmas itself, Terry Pratchett's "
             "Hogfather and Agatha Christie's Hercule Poirot's Christmas. The holiday hub adds A Christmas Carol, "
             "Little Women and The Bear and the Nightingale."),
            ("What audiobooks are good for a long holiday drive?",
             "The Thursday Murder Club read by Lesley Manville suits a car with several generations in it. Mythos, "
             "read by Stephen Fry, works for families with older children, and Yes Please, read by Amy Poehler with "
             "guests, for adults. Our Thanksgiving guide adds The Hobbit read by Andy Serkis."),
            ("What podcasts can I listen to while wrapping presents or baking?",
             "Dolly Parton's America is a nine-part series about Parton and the people who love her. Strong Songs "
             "takes one well-known song apart in each episode. Both are about music, so they suit a kitchen."),
            ("What should I listen to at Christmas if I'm tired of Christmas music?",
             "Keith Jarrett's The Köln Concert and Nick Drake's Pink Moon are both winter-night records with nothing "
             "festive in them. Graceland and Harvest, from our Thanksgiving guide, also work, and the holiday hub has "
             "Björk's Vespertine."),
            ("Can I track podcasts, audiobooks and manga on OmniTrackr?",
             "Yes. OmniTrackr tracks nine formats: movies, TV, anime, video games, books, music, manga, podcasts and "
             "audiobooks. Every pick in this guide can be added to your library from the page, or saved to a list "
             "before you sign up."),
        ],
        "method": [
            "Prepared by OmniTrackr and reviewed by the site owner before publishing. We started from the hours of "
            "December that happen away from a screen (wrapping, baking, travelling, the slow week after Christmas, "
            "the last hour of the night) and chose five picks for each from the five formats you can read or "
            "listen to. None of the books or albums on the holiday hub are repeated.",
            "Caveats and lengths are our own, checked against the works themselves and public sources such as "
            "publishers' and podcast pages. Audiobook lengths vary between editions and are given roughly. Every link "
            "goes to an OmniTrackr title page and none go to shops. Nothing here is sponsored.",
        ],
    },
}
