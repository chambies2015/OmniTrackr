"""Spring 2027 release guides for /new-releases.

Same fields as the guides in release_guides.py (that module adds these to GUIDES). The
all-format guide, spring-2027, covers March to May like the winter one covers December to
February, and becomes the "current" guide on Release Radar on March 1. The one-format
spring guides (focus "movies", "games", "anime" and "books") cover April to June, the quarter
after the winter one-format guides. There is no spring TV guide yet: in November 2026 almost
no April to June premieres had a date, so the few that did are in spring-2027's ``also``. A title written up as a pick in one guide is only mentioned in
``also`` in the others, so every pick has one home in the Pick for me pool.
"""

GUIDES = {
    "spring-2027": {
        "name": "Spring 2027 releases worth planning around",
        "period": "March to May 2027",
        "hub_label": "Spring 2027",
        "search_title": "Spring 2027 releases: Zelda, Star Wars: Starfighter, Final Fantasy VII Revelation and more",
        "summary": ("The March to May 2027 releases we would plan around, from The Legend of Zelda and Star Wars: "
                    "Starfighter to Final Fantasy VII Revelation, with what to catch up on first."),
        "published": "2026-11-21",
        "reviewed": "2026-11-22",
        "starts": "2027-03-01",
        "ends": "2027-05-31",
        "lead": [
            "Spring used to be the quiet stretch between the awards films and the summer blockbusters. That has "
            "changed. Studios now open big films in April, publishers have learned that a spring game gets more "
            "attention than one released in the autumn rush, and the anime season that starts in April is often the "
            "strongest of the year. Spring 2027 is a good example. In the space of eight weeks there is a "
            "live-action Zelda film, the last part of the Final Fantasy VII remake, a new God of War and the first "
            "Star Wars film since The Mandalorian and Grogu.",
            "This guide covers March 1 to May 31. We went through the release schedules as they stood on November "
            "21, 2026, and kept the releases with a date we could check against the studio, network or publisher: "
            "four films, three series, four games, two anime and three books. A few have only a month so far, and "
            "we say so where that is the case. Most of them are five or six months away as we write, so these are "
            "bets, not reviews. For each one we say why it is on the list, who should wait for the reviews, and "
            "what to watch, play or read first if you want to arrive ready.",
            "Three of the season's films open in March and are already written up in our winter guides: Sonic the "
            "Hedgehog 4 on March 19, Godzilla x Kong: Supernova on March 26, and Mike Flanagan's The Exorcist: "
            "Martyrs on March 12. They are listed at the bottom with links. Our spring movies, games, anime and "
            "books guides go further into April, May and June, one format at a time. There is no spring TV guide "
            "yet, because almost no shows had an April to June date when we wrote this. The streaming services "
            "usually set their spring dates in January and February, and we will write one then.",
        ],
        "sections": [
            {
                "format": "movies",
                "heading": "Four films, and one of them is a parody of another",
                "intro": [
                    "April is where the season's films are. Sam Esmail's thriller opens on the 9th, the Spaceballs "
                    "sequel on the 23rd and the Zelda film on the 30th. Star Wars takes Memorial Day weekend at the "
                    "end of May, as it did in 1977, 1980, 1983 and several times since.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Panic Carefully", "year": 2027, "creator": "Sam Esmail",
                     "date": "2027-04-09",
                     "released": "In theaters and IMAX · Warner Bros.",
                     "why": "An original thriller written and directed by Sam Esmail, the creator of Mr. Robot, with "
                            "Julia Roberts, Elizabeth Olsen, Eddie Redmayne, Brian Tyree Henry, Joe Alwyn and Aidan "
                            "Gillen.",
                     "note": "Esmail and Roberts last worked together on Leave the World Behind (2023), a slow, "
                             "unsettling Netflix film about a family whose holiday rental goes quiet when the "
                             "outside world stops working. This one is a theatrical film, and it went to Warner "
                             "Bros. in December 2024 after Netflix and Paramount also bid for it. That is unusual "
                             "for an original script with no franchise behind it. The plot is still a secret. What "
                             "we know is that it was shot in London in early 2025, with Canary Wharf dressed up as "
                             "Manhattan, and that Volker Bertelmann, who won an Oscar for All Quiet on the Western "
                             "Front and scored Conclave, wrote the music. With a cast this good and a director who "
                             "likes to keep his audience nervous, it is the film in this guide we know least about "
                             "and are most curious to see.",
                     "first": "Leave the World Behind (2023), if you haven't seen it. Esmail's Mr. Robot is the "
                              "fuller picture of how he works, but it runs to four seasons.",
                     "caveat": "We are going on the names alone. It was due on February 26 and moved to April, which "
                               "may mean nothing. Esmail's endings tend to divide people."},
                    {"kind": "movie", "title": "Spaceballs: The New One", "year": 2027, "creator": "Josh Greenbaum",
                     "date": "2027-04-23",
                     "released": "In theaters · Amazon MGM Studios",
                     "why": "The sequel to Mel Brooks's 1987 Star Wars parody, set forty years later, with Rick "
                            "Moranis back as Dark Helmet, Bill Pullman as Lone Starr, Daphne Zuniga as Princess Vespa "
                            "and Brooks himself as Yogurt.",
                     "note": "Spaceballs was a modest hit in 1987 and became one of the most quoted comedies of its "
                             "decade, mostly on video. The sequel comes out in time for its fortieth anniversary, "
                             "and Amazon's synopsis opens the way you would hope: \"Somehow, Dark Helmet has "
                             "returned!\" Rick Moranis stepped away from acting in the late 1990s to raise his "
                             "children, and this is his return, which is reason enough for many people. Josh Gad "
                             "co-wrote the script and joins the cast with Keke Palmer, Anthony Carrigan and Lewis "
                             "Pullman, Bill's son. The director, Josh Greenbaum, made Barb and Star Go to Vista Del "
                             "Mar (2021), one of the silliest and most underrated comedies of recent years, which is "
                             "the best sign there is. Brooks, who turned 100 in June 2026, produces and co-wrote it.",
                     "first": "Spaceballs (1987). It runs about an hour and a half. The jokes land harder if you "
                              "have seen the original Star Wars films recently.",
                     "first_link": "/in-order/star-wars", "first_label": "Star Wars in order",
                     "caveat": "Parody comedies have had a hard decade, and plenty of the original's jokes have aged. "
                               "Expect a lot of jokes about the film industry, sequels and reboots, which can wear "
                               "thin."},
                    {"kind": "movie", "title": "The Legend of Zelda", "year": 2027, "creator": "Wes Ball",
                     "date": "2027-04-30",
                     "released": "In theaters worldwide · Sony Pictures and Nintendo",
                     "why": "Nintendo's first live-action film, with Benjamin Evan Ainsworth as Link and Bo Bragason as "
                            "Zelda, directed by Wes Ball and produced by Nintendo's Shigeru Miyamoto and Avi Arad.",
                     "note": "The Super Mario Bros. Movie made more than a billion dollars in 2023, and Zelda is the "
                             "harder test. Mario is a cartoon. Zelda is a quiet, rather lonely series about a boy "
                             "who doesn't speak, exploring a ruined kingdom, and a film of it needs a director who "
                             "can make landscape do the talking. Wes Ball made the Maze Runner films and Kingdom of "
                             "the Planet of the Apes (2024), which was better than it had any right to be, and he "
                             "has said he wants the film to feel \"serious and cool, but fun and whimsical.\" It was "
                             "shot in New Zealand. Dichen Lachman plays Impa, and Sam Neill is in the cast. The date "
                             "has moved twice: from March 26 to May 7, then forward a week to April 30, when "
                             "Miyamoto said the team wanted to deliver it as soon as possible.",
                     "first": "Play Breath of the Wild (2017) if you want the world Ball seems to be drawing on, or "
                              "Ocarina of Time if you prefer the classic story. Neither is required.",
                     "first_link": "/in-order/zelda", "first_label": "The Zelda games in order",
                     "caveat": "Nintendo has shown very little of it, and the plot is not public. Link talking, or "
                               "not talking, will annoy somebody either way. Game adaptations are still a gamble."},
                    {"kind": "movie", "title": "Star Wars: Starfighter", "year": 2027, "creator": "Shawn Levy",
                     "date": "2027-05-28",
                     "released": "In theaters · Lucasfilm and Disney",
                     "why": "A new Star Wars story set about five years after The Rise of Skywalker, directed by Shawn "
                            "Levy, with Ryan Gosling as a cynical pilot who is \"confronted by his mysterious past\" and "
                            "pulled into an adventure.",
                     "note": "Gosling has described it as \"not a prequel\" and \"not a sequel,\" and that is the "
                             "appeal: a story in the era after the last trilogy, with new characters and nothing to "
                             "set up for a streaming series. Levy directed Free Guy and Deadpool & Wolverine and "
                             "produced Stranger Things, and he is good at big, warm crowd-pleasers. Jonathan Tropper, "
                             "who wrote Banshee and Levy's This Is Where I Leave You, wrote the script. Matt Smith, "
                             "Mia Goth, Aaron Pierre and Amy Adams are also in it, in roles Lucasfilm hasn't "
                             "described, along with a young actor, Flynn Gray. Memorial Day weekend is the "
                             "traditional Star Wars slot, and a new Star Wars film with no homework is the closest "
                             "thing this spring has to a sure bet for a family outing.",
                     "first": "Nothing, according to the people making it. If you want context, The Rise of "
                              "Skywalker (2019) is the last film set before this one.",
                     "first_link": "/in-order/star-wars", "first_label": "Star Wars in order",
                     "caveat": "The period after The Rise of Skywalker is new ground, and that film is the least "
                               "loved of the saga. Lucasfilm hasn't said who anyone except Gosling is playing."},
                ],
            },
            {
                "format": "tv",
                "heading": "Three seasons worth clearing an evening for",
                "intro": [
                    "Spring is a thin season for new television dates this far ahead, so all three of our picks are "
                    "returning shows. One is ending, one is the most talked-about romance of 2025, and one is Prime "
                    "Video's biggest new series of 2026. Only Off Campus has a day so far; the other two have a "
                    "month.",
                ],
                "picks": [
                    {"kind": "tv", "title": "Star Trek: Starfleet Academy", "year": 2026, "creator": None,
                     "date": "2027-03-01", "month_only": True,
                     "released": "Paramount+ · season 2, the final season",
                     "why": "The second and last season of the series about a new class of Starfleet cadets, now in "
                            "their second year aboard the USS Athena, with Holly Hunter as their chancellor, Nahla Ake.",
                     "note": "Starfleet Academy was always going to be a different kind of Star Trek: younger, "
                             "faster, closer to a school drama than to the bridge of the Enterprise. Paramount+ "
                             "said in March 2026, less than two weeks after the first season ended, that the second "
                             "would be the last, and it had already finished filming by then. That makes this an "
                             "ending made by people who knew it was coming. The guest casting is a good sign: Bill "
                             "Nighy plays Nyk Ake, Nahla's estranged father, and Rosemarie DeWitt plays Laytha "
                             "Sadal, the First Lady of Betazed and the mother of one of the cadets. Robert Picardo "
                             "is back as the Doctor from Voyager, and Ruaridh Aldington joins as a new cadet, Keats. "
                             "Alex Kurtzman and Noga Landau run the show.",
                     "first": "Season 1, ten episodes on Paramount+. You don't need the rest of Star Trek, though "
                              "Voyager explains the Doctor.",
                     "first_link": "/in-order/star-trek", "first_label": "Star Trek in order",
                     "caveat": "Paramount+ has said March and not the day. Longtime fans were split on the first "
                               "season's teenage tone, and a final season with little room to land its stories may not "
                               "win them back."},
                    {"kind": "tv", "title": "Heated Rivalry", "year": 2025, "creator": None,
                     "date": "2027-04-01", "month_only": True,
                     "released": "HBO Max in the US, Crave in Canada · season 2",
                     "why": "The second season of Jacob Tierney's series about two rival hockey stars, Shane "
                            "Hollander (Hudson Williams) and Ilya Rozanov (Connor Storrie), and the secret romance "
                            "that runs through their careers.",
                     "note": "Heated Rivalry came out of Canada at the end of 2025 with no great expectations and "
                             "turned into one of the most discussed shows of the season, mostly by word of mouth. It "
                             "is based on Rachel Reid's Game Changers novels, and Tierney writes, directs and "
                             "produces it himself, which may be why it feels so sure of itself. In February 2026 he "
                             "said season 2 was expected in April 2027, with filming in August. It draws on Reid's "
                             "The Long Game, which picks up Shane and Ilya years into their relationship, when "
                             "hiding it has started to cost them. Reid's third book about the couple, Unrivaled, "
                             "follows on June 1, 2027.",
                     "first": "Season 1. If you prefer to read first, the novel Heated Rivalry (2019) covers the same "
                              "ground.",
                     "caveat": "April is the creator's estimate, and HBO Max hasn't confirmed a day. The show has "
                               "frequent, explicit sex scenes and is not one to watch with your parents."},
                    {"kind": "tv", "title": "Off Campus", "year": 2026, "creator": None,
                     "date": "2027-04-28",
                     "released": "Prime Video, worldwide · season 2",
                     "why": "The second season of the college romance drama about the Briar University hockey team, "
                            "based on Elle Kennedy's novels, this time centered on Allie Hayes (Mika Abdalla) and "
                            "Dean Di Laurentis (Stephen Kalyn).",
                     "note": "Off Campus arrived on Prime Video in May 2026, and Amazon says 36 million people "
                             "watched it in its first twelve days, which would make it the service's most watched "
                             "debut season. Amazon counts viewers its own way, but the books were already huge, and "
                             "a second season was announced before the first had been out long. Season 2 follows "
                             "Allie and Dean, whose story is the third book, The Score: a careful, ambitious drama "
                             "student and the team's least serious player. Louisa Levy, who adapted the books, runs "
                             "the show with Gina Fattore. Prime Video gave the date in November, more than five "
                             "months ahead, so you can plan a weekend around it.",
                     "first": "Season 1. Readers can go to The Score, which this season adapts.",
                     "caveat": "It is a soap about very attractive college athletes, with plenty of sex. If that is "
                               "not your thing, a second season will not change your mind."},
                ],
            },
            {
                "format": "games",
                "heading": "Four games, two of them a day apart",
                "intro": [
                    "The first week of April is the most crowded of the spring for games. Exodus, a new science "
                    "fiction role-playing game from former BioWare developers, comes out on April 7, and the final "
                    "part of the Final Fantasy VII remake follows on the 8th. Pick one, or take a week off. God of "
                    "War Laufey, which moved from February, arrives on May 20.",
                ],
                "picks": [
                    {"kind": "game", "title": "Grave Seasons", "year": 2027, "creator": None,
                     "date": "2027-03-09",
                     "released": "PS5, Xbox Series X|S, Switch, PC · on Game Pass from launch",
                     "why": "A farming and dating game from Perfect Garbage and Blumhouse Games, set in the town of "
                            "Ashenridge, where somebody among the villagers you are getting to know is a serial "
                            "killer.",
                     "note": "Farming games are some of the most comforting games ever made: you plant, you water, "
                             "you make friends, the seasons turn. Grave Seasons keeps all of that and adds a murderer, "
                             "which you have to unmask while you bring in the harvest. You can romance the "
                             "villagers, the killer included, and the killer is a different person on each "
                             "playthrough, so the mystery doesn't spoil itself the second time. Blumhouse, the film "
                             "company behind Paranormal Activity and Get Out, started publishing games in 2024, and "
                             "this is the one of theirs we have been most curious about. It was due earlier and "
                             "moved to March 2027.",
                     "first": "Nothing, but if you have played Stardew Valley you will know how the farming half works "
                              "within minutes.",
                     "caveat": "It's a horror game wearing a cosy game's clothes, so expect murders and some gore. A "
                               "small team's first big release, so reviews matter."},
                    {"kind": "game", "title": "Exodus", "year": 2027, "creator": None,
                     "date": "2027-04-07",
                     "released": "PS5, Xbox Series X|S, PC",
                     "why": "A science fiction role-playing game from Archetype Entertainment, a studio of former "
                            "BioWare, Naughty Dog and Halo developers, in which you lead a crew across a galaxy where "
                            "every long journey costs time back home.",
                     "note": "Archetype was set up by Wizards of the Coast, the Dungeons & Dragons company, with a "
                             "lot of people who worked on Mass Effect, and the comparison is deliberate: a squad of "
                             "companions, conversations that change things, and a big, strange galaxy. The idea "
                             "that sets it apart is time. Travelling near the speed of light means a mission that "
                             "takes you weeks can take years for the people you left behind, so the world you "
                             "return to has moved on. You play Jun, and your companions include Salt, an octopus "
                             "mercenary who pilots a combat mech, and Emrys, one of a species called the Celestials. "
                             "It is the studio's first game. If Mass Effect is a series you still miss, this is the "
                             "game to watch this spring.",
                     "first": "Nothing. It is a new world. Mass Effect Legendary Edition is the obvious game to play "
                              "while you wait.",
                     "caveat": "A debut from a new studio, with no demo and not much played by the press so far. Its "
                               "release the day before Final Fantasy VII Revelation is a real risk of being "
                               "overlooked."},
                    {"kind": "game", "title": "Final Fantasy VII Revelation", "year": 2027, "creator": None,
                     "date": "2027-04-08",
                     "released": "PS5, Xbox Series X|S, Switch 2, PC · same day on all four",
                     "why": "The third and last part of Square Enix's remake of Final Fantasy VII, with Vincent Valentine "
                            "and Cid Highwind joining the party and the Highwind airship to fly anywhere in the "
                            "world, including Wutai.",
                     "note": "The remake began in 2020 with a game set entirely in the city of Midgar and continued "
                             "in 2024 with Rebirth, which opened up the world and ended at the most famous moment "
                             "in the original. Revelation finishes the story. Square Enix announced the date at "
                             "a State of Play in September 2026 and showed an open world you can parachute into "
                             "from the airship, with the option to play as someone other than Cloud. It is also "
                             "the first part to launch on Xbox and Switch 2 on day one rather than years later. "
                             "Naoki Hamaguchi, who directed Rebirth, is back. The trilogy has changed the original "
                             "story in ways fans still argue about, and the ending is where those changes will "
                             "have to make sense.",
                     "first": "Remake (2020) and Rebirth (2024). Together they are well over a hundred hours, so if "
                              "you are starting now, a story recap of Remake and the whole of Rebirth is a realistic "
                              "plan.",
                     "first_link": "/in-order/final-fantasy-vii", "first_label": "Final Fantasy VII in order",
                     "caveat": "Unplayable without the first two, and very large: Square Enix says the Switch 2 "
                               "version needs 130 GB free. The Premium edition unlocks it a day early."},
                    {"kind": "game", "title": "God of War Laufey", "year": 2027, "creator": None,
                     "date": "2027-05-20",
                     "released": "PS5",
                     "why": "A God of War game in which you play Faye, Kratos's late wife, fighting monsters from "
                            "several mythologies in a place called the Everywhen, with a talking gelatinous cube and "
                            "a talking sword sash for company.",
                     "note": "Faye is the most important character in God of War (2018) who never appears alive. "
                             "Her death starts the story, and the two games that followed slowly revealed that she "
                             "was a giant, Laufey, and knew far more than her husband or son. Giving her a game of "
                             "her own is a bold step for a series that has always belonged to Kratos. Deborah Ann "
                             "Woll voices her again. The talking cube and the talking sash suggest Santa Monica "
                             "Studio wants it a little lighter than the Norse games. It was due on February 16 and "
                             "moved to May 20 in November, with the studio saying it was putting in the finishing "
                             "touches.",
                     "first": "God of War (2018) and Ragnarök (2022), or at least the story of Ragnarök. Faye's "
                              "reveals there matter here.",
                     "caveat": "PlayStation 5 only. It is not the next chapter for Kratos and Atreus, if that is what "
                               "you were waiting for, and the mix of mythologies is a gamble."},
                ],
            },
            {
                "format": "anime",
                "heading": "Two returning anime that were worth the wait",
                "intro": [
                    "The spring anime season begins in April. Two of the best-loved shows of 2023 come back, and both "
                    "are gentle, character-driven series with hardly a fight between them. Our spring anime guide covers the new "
                    "shows, including Kagurabachi.",
                ],
                "picks": [
                    {"kind": "anime", "title": "Skip and Loafer", "year": 2023, "creator": None,
                     "date": "2027-04-01", "month_only": True,
                     "released": "Crunchyroll · season 2",
                     "why": "The second season of the series about Mitsumi Iwakura, a fiercely organised girl from the "
                            "countryside who moves to Tokyo for high school, and the easygoing classmate she "
                            "befriends, Sosuke Shima.",
                     "note": "The first season, twelve episodes in the spring of 2023, was one of the warmest anime "
                             "of the decade: a school story with no love triangle, no tournament and no villain, "
                             "just people being kind to each other in ways that are funny and sometimes very "
                             "moving. Fans have waited four years for more. P.A. Works is back, as is the director, "
                             "Kotomi Deai, who also writes the series, and the character designer, Manami Umeshita. "
                             "Reina Ueda and Yuto Takenaka join the cast as two new classmates. Misaki Takamatsu's "
                             "manga is still running in Afternoon, so there is plenty of story to adapt.",
                     "first": "Season 1, on Crunchyroll. The manga is published in English by Seven Seas.",
                     "caveat": "Nothing much happens, which is the point. If you need plot, this isn't it."},
                    {"kind": "anime", "title": "The Dangers in My Heart", "year": 2023, "creator": None,
                     "date": "2027-04-01", "month_only": True,
                     "released": "HIDIVE · season 3",
                     "why": "The third season of the romantic comedy about Kyotaro Ichikawa, a gloomy boy who imagines "
                            "terrible things happening to his classmates, and Anna Yamada, the popular girl who "
                            "keeps sitting next to him in the library.",
                     "note": "It starts as a joke about a teenage boy who thinks he is darker than he is, and becomes "
                             "one of the most patient and honest school romances in anime. The second season won "
                             "anime of the year at the 2024 Crunchyroll Anime Awards, an unusual result for a quiet "
                             "romance. Norio Sakurai's manga ended in September 2026 after fourteen volumes, so a "
                             "third season can head towards an ending the author has finished. Shin-Ei Animation, "
                             "which made the first two seasons, is making this one.",
                     "first": "Seasons 1 and 2, twenty-five episodes in all, on HIDIVE. A compilation film came out "
                              "in Japan in February 2026.",
                     "caveat": "The first few episodes lean on Kyotaro's violent daydreams, which put some viewers "
                               "off. It is a slow burn."},
                ],
            },
            {
                "format": "books",
                "heading": "Three books from authors who don't need an introduction",
                "intro": [
                    "Book dates are the firmest of any format, and three of the biggest names in popular fiction "
                    "publish this spring: Elle Kennedy in March, Emily Henry in April and Kristin Hannah in May. "
                    "Our spring books guide covers April to June in more depth.",
                ],
                "picks": [
                    {"kind": "book", "title": "Bad Idea", "year": 2027, "creator": "Elle Kennedy",
                     "date": "2027-03-16",
                     "released": "Paperback and ebook · Sourcebooks",
                     "why": "A standalone romance set at Briar University with the next generation of Off-Campus "
                            "characters: Ivy Di Laurentis, a dance student who wants to get to New York and ballet, "
                            "and AJ Connelly, a hockey player and her brother's former best friend.",
                     "note": "Elle Kennedy's Off-Campus books have been selling for a decade, and the Prime Video "
                             "series brought them a new audience in 2026. Bad Idea is the first of the next "
                             "generation's stories, and the timing is good: it comes out six weeks before season 2 "
                             "of the show. The heroine is a Di Laurentis, the family name of the show's Dean, and the "
                             "set-up is the kind Kennedy does best, two people who agree to something they "
                             "shouldn't and find out they mean it. It is a standalone, so you can start here.",
                     "first": "Nothing, though The Deal (2015), the first Off-Campus book, shows where the world "
                              "began.",
                     "caveat": "Explicit, like all of Kennedy's books. If you want a romance without open-door "
                               "scenes, this isn't one."},
                    {"kind": "book", "title": "Modern Classic", "year": 2027, "creator": "Emily Henry",
                     "date": "2027-04-06",
                     "released": "Hardcover, ebook and audiobook · Berkley · 432 pages",
                     "why": "Emily Henry's seventh romance for adults: Beckett Heyburn, a screenwriter who loves old "
                            "romantic films, inherits her late mentor's house in Santa Barbara and keeps finding a "
                            "rescue dog in her yard.",
                     "note": "Henry is the most reliable name in romantic comedy. Beach Read, People We Meet on "
                             "Vacation, Book Lovers, Happy Place, Funny Story and Great Big Beautiful Life were all "
                             "bestsellers, and her books are funnier and sadder than the covers suggest, built around "
                             "grief, work and family as much as the romance. In Modern Classic, Beckett's career has "
                             "stalled, her mentor Perdita has died, and the house she leaves Beckett is full of vintage "
                             "clothes and film memorabilia. The dog belongs, for now, to its foster dad, whom the "
                             "publisher describes only as an \"ornery enigma\" who lets the dog sleep in a king-sized "
                             "bed but won't give her a name. Henry has said it is a straightforward romance, and her "
                             "own take, in a small way, on the film The Holiday. The film of Beach Read opens a "
                             "month later, on May 7, so this is a good spring to catch up on her.",
                     "first": "Nothing. Henry's books are all standalones. Beach Read (2020) is the one to read if "
                              "you are new to her.",
                     "caveat": "Henry's books follow a pattern, and if the last one didn't work for you, this one "
                               "probably won't either. At 432 pages it is one of her longest."},
                    {"kind": "book", "title": "The Fire", "year": 2027, "creator": "Kristin Hannah",
                     "date": "2027-05-04",
                     "released": "Hardcover, ebook and audiobook · St. Martin's Press",
                     "why": "Kristin Hannah's first novel since The Women: after a public betrayal, Merritt Locke sets "
                            "out on a road trip across America to repair her relationship with her estranged "
                            "daughter.",
                     "note": "The Women (2024), about an army nurse in Vietnam, was one of the biggest novels of the "
                             "decade, and The Nightingale and The Four Winds before it were not far behind. Hannah "
                             "writes big, emotional books about women under pressure, and they reach readers who "
                             "don't otherwise read much fiction, which is why every library hold list will be long. "
                             "The Fire is a contemporary story, her first in a while, and the publisher calls it a "
                             "book about the bonds between women and finding your voice. We don't yet know what the "
                             "betrayal is, which is presumably the point.",
                     "first": "Nothing; it stands alone. If you have never read Hannah, The Women is the place to "
                              "start.",
                     "caveat": "Hannah's books are deliberately tear-jerking, and some readers find them heavy-handed. "
                               "No page count yet, but her recent novels have run to well over 400 pages."},
                ],
            },
        ],
        "also": [
            ("The Exorcist: Martyrs, Sonic the Hedgehog 4 and Godzilla x Kong: Supernova (March 12, 19 and 26).",
             "The three biggest March films, all written up in our winter 2027 movies guide."),
            ("Not Alone (April 16) and Beach Read (May 7).",
             "Illumination's animated rom-com with Timothée Chalamet and Selena Gomez, and the film of Emily "
             "Henry's novel. Both are in our spring 2027 movies guide."),
            ("The Catch (May 21, in theaters).",
             "Emma Stone and Chris Pine in a romantic comedy from Universal, directed by Dave McCary."),
            ("Kagurabachi (April, Crunchyroll).",
             "The season's most anticipated new anime, a sword-and-sorcery revenge story from Weekly Shonen Jump. "
             "It leads our spring 2027 anime guide."),
            ("Laid-Back Camp, season 4 (April).",
             "Rin and Nadeshiko go camping again, with a new studio, FuRyu Pictures. Still the most relaxing anime "
             "on television."),
            ("The Apothecary Diaries, season 3 part 2 (April).",
             "The second half of the third season, after the first half in October 2026. Our November guide has "
             "more."),
            ("Kirby and the World Beyond (spring, Switch 2).",
             "Nintendo's second big 3D Kirby game, in which Kirby slices a hole in the sky and finds an open world "
             "behind it. No day yet."),
            ("Persona 4 Revival on Switch 2 (May 20).",
             "The remake from our winter guide reaches Nintendo's console three months after the other versions."),
            ("Wild Things (April 16, Apple TV).",
             "A limited series about Siegfried & Roy, with Jude Law and Andrew Garfield as the Las Vegas magicians "
             "and their white tigers, from John Hoffman, who co-created Only Murders in the Building. It is based on "
             "Apple's podcast of the same name."),
            ("The Day of the Jackal, season 2 (2027, Peacock).",
             "Eddie Redmayne's assassin returns, though Peacock has said only 2027, so it may not be a spring "
             "show."),
            ("Unrivaled by Rachel Reid (June 1).",
             "The third novel about Shane and Ilya, the couple at the center of Heated Rivalry. It is in our spring "
             "2027 books guide."),
        ],
        "plan_heading": "A plan for the spring",
        "plan": [
            "March is the month to catch up. Watch the first season of Starfleet Academy before the second begins, "
            "and start Grave Seasons on the 9th if you want something to play in the evenings. If you are behind on "
            "Final Fantasy VII, this is the last chance to finish Rebirth before Revelation. The winter guides cover "
            "the big March films.",
            "April is the heaviest month of the season. Decide early whether you are an Exodus person or a Final "
            "Fantasy person for the first week, because both want your evenings. Panic Carefully opens on the 9th, "
            "the anime season starts in the first two weeks, Spaceballs opens on the 23rd, Off Campus returns on "
            "the 28th and Zelda arrives on the 30th. Emily Henry's novel on the 6th is the easiest of the lot to fit "
            "in.",
            "May is quieter until the last two weeks. Read The Fire from the 4th, place a library hold early if you "
            "use one, and save the 20th for God of War Laufey if you have a PlayStation 5. End the season on Memorial "
            "Day weekend with Star Wars: Starfighter, which nobody needs any homework for.",
        ],
        "method": [
            "Prepared by OmniTrackr with AI assistance and reviewed by the site owner before publishing. None of "
            "these releases were out when we wrote about them, so this is a guide to what we think is worth planning "
            "around, not a set of reviews. We worked from the studios', networks' and publishers' own announcements "
            "and the coverage listed below, and kept releases we could date at least to the month.",
            "Four picks have a month but no day yet: Starfleet Academy (March), and Heated Rivalry, Skip and Loafer "
            "and The Dangers in My Heart (April). We list those as the month. Book dates rarely move once a "
            "publisher has set them. Film and game dates do: Zelda, Panic Carefully, Grave Seasons and God of War "
            "Laufey have each moved at least once, and some dates here will change again. We will check every date "
            "before March and update the page.",
        ],
        "related": [
            ("The Zelda games in order", "/in-order/zelda"),
            ("Star Wars in order", "/in-order/star-wars"),
            ("Final Fantasy VII in order", "/in-order/final-fantasy-vii"),
            ("Star Trek in order", "/in-order/star-trek"),
            ("The best of 2026", "/best-of"),
        ],
        "sources": [
            ("Gematsu: The Legend of Zelda film moves up to April 30, 2027", "https://www.gematsu.com/2026/05/the-legend-of-zelda-live-action-film-release-date-moved-up-to-april-30-2027"),
            ("Nintendo Life: the live-action Zelda film's new worldwide date", "https://www.nintendolife.com/news/2026/05/the-live-action-zelda-movie-has-a-new-worldwide-release-date"),
            ("GamesRadar+: The Legend of Zelda film, everything we know", "https://www.gamesradar.com/entertainment/live-action-movies/the-legend-of-zelda-movie-release-date-cast-story-trailer/"),
            ("Disney: Star Wars: Starfighter", "https://movies.disney.com/star-wars-starfighter"),
            ("TheWrap: Starfighter, everything we know", "https://www.thewrap.com/starfighter-everything-we-know-about-ryan-goslings-star-wars-movie/"),
            ("Variety: the Spaceballs sequel is set for April 2027", "https://au.variety.com/2026/film/news/spaceballs-sequel-april-2027-release-date-34901/"),
            ("CinemaBlend: the Spaceballs: The New One synopsis", "https://www.cinemablend.com/movies/spaceballs-the-new-one-synopsis-poster-giving-everything-i-need"),
            ("Wikipedia: Panic Carefully", "https://en.wikipedia.org/wiki/Panic_Carefully"),
            ("The Numbers: 2027 theatrical release schedule", "https://www.the-numbers.com/movies/release-schedule/2027"),
            ("TVLine: Starfleet Academy sets a March 2027 premiere for its final season", "https://www.tvline.com/2283109/star-trek-starfleet-academy-season-2-premiere-month-paramount-plus/"),
            ("Paramount+: Starfleet Academy season 2, everything to know", "https://www.paramountplus.com/sneak-peak/star-trek-starfleet-academy-season-2-everything-to-know/"),
            ("Variety: Heated Rivalry season 2 eyes April 2027", "https://au.variety.com/2026/tv/news/heated-rivalry-season-2-release-date-33614/"),
            ("Bleeding Cool: Heated Rivalry season 2 expected in April 2027", "https://bleedingcool.com/tv/heated-rivalry-season-2-expected-april-2027-filming-eyed-for-august/"),
            ("Variety: Off Campus sets its season 2 date", "https://variety.com/2026/tv/news/off-campus-season-2-release-amazon-alli-and-dean-1236940329/"),
            ("TV Insider: The Day of the Jackal season 2", "https://www.tvinsider.com/1166859/"),
            ("9to5Mac: Apple TV sets Wild Things for April 16", "https://9to5mac.com/2026/11/19/apple-tv-reveals-new-series-with-andrew-garfield-jude-law-as-magicians/"),
            ("Gematsu: Grave Seasons launches March 9, 2027", "https://www.gematsu.com/2026/09/grave-seasons-launches-march-9-2027"),
            ("RPG Site: Exodus launches April 7, 2027", "https://www.rpgsite.net/news/21185-exodus-release-date-ps5-xbox-pc-steam"),
            ("GamesRadar+: Exodus finally gets a release date", "https://www.gamesradar.com/games/mass-effect/mass-effect-like-rpg-exodus-finally-gets-a-release-date-and-its-not-that-far-away/"),
            ("Automaton: Final Fantasy VII Revelation launches April 8, 2027", "https://automaton-media.com/en/news/final-fantasy-7-revelation-officially-launches-april-8-2027-concluding-the-remake-trilogy/"),
            ("RPG Site: Final Fantasy VII Revelation editions and pre-orders", "https://www.rpgsite.net/news/21279-final-fantasy-vii-revelation-release-date-new-gameplay-state-of-play-full"),
            ("Game Informer: God of War Laufey delayed to May", "https://www.gameinformer.com/2026/11/04/god-of-war-laufey-delayed-to-may"),
            ("God is a Geek: God of War Laufey moves to May 20, 2027", "https://godisageek.com/2026/11/god-of-war-laufey-release-date/"),
            ("VGC: Kirby and the World Beyond is coming in spring 2027", "https://www.videogameschronicle.com/news/kirby-and-the-world-beyond-is-an-all-new-kirby-3d-adventure-coming-in-spring-2027/"),
            ("Anime Corner: Skip and Loafer season 2 key visual and trailer", "https://animecorner.me/skip-and-loafer-season-2-reveals-new-key-visual-new-trailer/"),
            ("Final Weapon: Skip and Loafer season 2 adds cast", "https://finalweapon.net/2026/11/16/skip-and-loafer-season-2-reveals-more-cast-members/"),
            ("Anime Corner: The Dangers in My Heart season 3 in April 2027", "https://animecorner.me/the-dangers-in-my-heart-bokuyaba-season-3-new-visual-and-trailer-revealed-april-2027-release/"),
            ("Final Weapon: Laid-Back Camp season 4 premieres in April 2027", "https://finalweapon.net/2026/11/06/laid-back-camp-season-4-premieres-in-april-2027/"),
            ("Elle Kennedy: coming soon", "https://www.ellekennedy.com/coming-soon"),
            ("Penguin Random House: Modern Classic", "https://www.penguinrandomhouse.com/books/704947/modern-classic-by-emily-henry/"),
            ("Kirkus: a new Kristin Hannah novel is coming in 2027", "https://www.kirkusreviews.com/news-and-features/articles/new-novel-by-kristin-hannah-coming-in-2027/"),
            ("The Bookish Bulletin: most anticipated April 2027 books", "https://www.thebookishbulletin.com/blog/most-anticipated-april-2027-books"),
            ("The Bookish Bulletin: most anticipated May 2027 books", "https://www.thebookishbulletin.com/blog/most-anticipated-may-2027-books"),
        ],
    },
    "spring-2027-movies": {
        "name": "Spring 2027 movies: the new films worth seeing from April to June",
        "period": "April to June 2027",
        "eyebrow": "MOVIES RELEASE GUIDE",
        "hub_label": "Spring 2027 movies",
        "focus": "movies",
        "search_title": "Spring 2027 movies: Spider-Verse, How to Train Your Dragon 2, Shrek 5, Possession and more",
        "summary": ("Twelve films from April to June 2027 worth planning around, from Beyond the Spider-Verse, How to "
                    "Train Your Dragon 2 and Shrek 5 to Possession and Beach Read."),
        "published": "2026-11-21",
        "reviewed": "2026-11-21",
        "starts": "2027-04-01",
        "ends": "2027-06-30",
        "lead": [
            "The summer film season starts earlier every year. Studios used to wait for Memorial Day. Now the first "
            "big films arrive in April, and by June there is a new one almost every Friday. In 2027 the last three "
            "weeks of June bring the live-action How to Train Your Dragon 2, the end of the Spider-Verse trilogy and "
            "the first Shrek film in seventeen years, one after another. That is a lot of cinema tickets for a family "
            "to budget for, and a lot of films competing for the same screens.",
            "This guide covers April 1 to June 30. We went through the studios' release schedules as they stood on "
            "November 21, 2026 and picked twelve films: three big ones, three horror films, three for families and "
            "three for an evening without the children. For each one we say when it opens and who made it, what to "
            "watch first if anything, and the thing most likely to put you off. None of them are out yet, so read "
            "these as bets, not reviews. Where we are guessing, we say so.",
            "A few notes before you start. Dates are for the US, and most of these open in cinemas on a Friday, with "
            "previews the night before. Four of the season's biggest films, Panic Carefully, Spaceballs: The New "
            "One, The Legend of Zelda and Star Wars: Starfighter, are written up in our broader spring 2027 guide, so "
            "they are only listed at the bottom of this one, along with a few films that have a date but too little "
            "else to go on.",
        ],
        "sections": [
            {
                "format": "movies",
                "id": "big",
                "label": "Big screen",
                "heading": "Three big films for June, and how much you need to have seen",
                "intro": [
                    "June has the season's biggest films outside our spring guide. All three are tied to something "
                    "older: a prequel to a 1982 action film, a live-action remake of a 2014 animated one, and the end "
                    "of an animated trilogy that began in 2018. Only one of them needs homework.",
                ],
                "picks": [
                    {"kind": "movie", "title": "John Rambo", "year": 2027, "creator": "Jalmari Helander",
                     "date": "2027-06-04",
                     "released": "In theaters · Lionsgate",
                     "why": "A prequel set during the Vietnam War, years before First Blood, with Noah Centineo as a "
                            "young John Rambo and David Harbour as Sam Trautman, the officer who trained him.",
                     "note": "Sylvester Stallone played Rambo five times between 1982 and 2019, and the films went "
                             "from a sad, angry story about a veteran nobody wanted back home to some of the most "
                             "violent action films of their decades. This one goes back to before any of that. The "
                             "director is the reason to pay attention. Jalmari Helander made Sisu (2022), a Finnish "
                             "film about an old gold prospector who will not die however many Nazis try to kill him, "
                             "and it was one of the best action films of its year: short, brutal, funny and almost "
                             "wordless. He has called John Rambo \"a survival story about endurance, persistence, and "
                             "lost innocence,\" which sounds like Sisu again. It was shot in Bangkok in early 2026. "
                             "Stallone is an executive producer, as are the Russo brothers, and James Franco is in "
                             "the cast. Harbour plays the role Richard Crenna made famous.",
                     "first": "First Blood (1982), if you want to know where the character ends up. Helander's Sisu "
                              "is the better preparation for the kind of film this is likely to be.",
                     "caveat": "A Rambo film without Stallone is a hard sell for some fans. Expect it to be R-rated "
                               "and very violent, as the last three were."},
                    {"kind": "movie", "title": "How to Train Your Dragon 2", "year": 2027, "creator": "Dean DeBlois",
                     "date": "2027-06-11",
                     "released": "In theaters · Universal Pictures",
                     "why": "The live-action remake of DreamWorks's 2014 sequel, with Mason Thames back as Hiccup and "
                            "Cate Blanchett as his mother, Valka, the role she voiced in the animated film.",
                     "note": "Universal dated this film in April 2025, before the live-action How to Train Your "
                             "Dragon had even opened, and the first one did well enough to justify the confidence. "
                             "Dean DeBlois, who co-directed the animated films and directed the first remake, writes "
                             "and directs again, and it was filmed at Sky Studios Elstree, outside London, between "
                             "January and May 2026. The story jumps five years. If it follows the 2014 film, as the "
                             "first remake followed the 2010 one, Hiccup and Toothless are mapping the world beyond "
                             "Berk when they find a dragon rider who turns out to be Hiccup's "
                             "mother, and a warlord, Drago Bludvist, who is building a dragon army. Nico Parker "
                             "returns as Astrid, Gerard Butler as Stoick and Nick Frost as Gobber. Ólafur Darri "
                             "Ólafsson plays Drago and Phil Dunster plays the trapper Eret. John Powell, whose scores "
                             "were a big part of the animated films, is back.",
                     "first": "How to Train Your Dragon (2025), or the 2010 animated film it remade almost scene for "
                              "scene. The 2014 animated sequel tells this story, so skip it if you want surprises.",
                     "caveat": "If you have seen the 2014 film, you know exactly what happens, including a death that "
                               "upset a lot of young viewers. A remake this faithful can feel like paying twice."},
                    {"kind": "movie", "title": "Spider-Man: Beyond the Spider-Verse", "year": 2027,
                     "creator": "Bob Persichetti and Justin K. Thompson",
                     "date": "2027-06-18",
                     "released": "In theaters · Sony Pictures Animation",
                     "why": "The final part of the animated trilogy about Miles Morales, picking up straight after the "
                            "cliffhanger that ended Across the Spider-Verse in 2023.",
                     "note": "Into the Spider-Verse (2018) won the Oscar for animated feature and changed what big "
                             "studio animation looked like. Across the Spider-Verse (2023) was even more ambitious and "
                             "ended in the middle of its story, with Miles trapped in the wrong universe, so this is "
                             "the second half of a film people have been waiting four years to finish. It was "
                             "originally due in March 2024. Sony then took it off the schedule, dated it for June 4, "
                             "2027 at CinemaCon in April 2025, pushed it three weeks to June 25, and then pulled it "
                             "forward a week to Father's Day weekend. Bob Persichetti, who co-directed the first film, and Justin K. "
                             "Thompson, who co-directed the second, are directing. Phil Lord and Chris Miller wrote "
                             "the script with David Callaham, and Shameik Moore and Hailee Steinfeld are back as Miles "
                             "and Gwen.",
                     "first": "Into the Spider-Verse (2018) and Across the Spider-Verse (2023). The second one is "
                              "essential; this film starts where it stops.",
                     "caveat": "These films are dense, loud and fast, and some people find them exhausting. Endings "
                               "are hard, and this one has to finish a story with a lot of loose threads."},
                ],
            },
            {
                "format": "movies",
                "id": "scary",
                "label": "Horror",
                "heading": "Three horror films from directors on a winning streak",
                "intro": [
                    "Horror has become the most reliable genre at the box office, and studios now open it all year. "
                    "Our three come from directors whose last films did a lot with small budgets, and two of them "
                    "open in June against much bigger films.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Anything but Ghosts", "year": 2027, "creator": "Curry Barker",
                     "date": "2027-05-07",
                     "released": "In theaters · Focus Features",
                     "why": "A horror comedy about two fake paranormal investigators who finally meet real ghosts, "
                            "from Curry Barker, the director of Obsession, with Bryce Dallas Howard and Aaron Paul.",
                     "note": "Curry Barker started out making films for YouTube, and his first feature, "
                             "Obsession, made for less than a million dollars, premiered at the Toronto festival in 2025 and became a "
                             "surprise hit. Anything but Ghosts is his second. He wrote it with Cooper Tomlinson, his "
                             "regular collaborator, and both of them act in it alongside Howard, Paul and Violet "
                             "McGraw. The premise is a good one: two men who fake hauntings for a living run into the "
                             "real thing. It is set in the same world as Obsession. It was shot in Vancouver in the spring of 2026 under the working "
                             "title Faraday, on a budget of about five million dollars, which is still tiny by studio "
                             "standards. Blumhouse is a producer. A comic premise with a director this good at dread is "
                             "the most promising horror film of the spring.",
                     "first": "Obsession (2025), if you can stomach it. Nothing else.",
                     "caveat": "Ghost-hunting horror has been done many times, and the joke has to keep working for "
                               "ninety minutes. A second film after a breakout is a hard test."},
                    {"kind": "movie", "title": "Skeletons", "year": 2027, "creator": "JT Mollner",
                     "date": "2027-06-04",
                     "released": "In theaters · Sony Pictures",
                     "why": "A creature film told from the point of view of a young boy, with Brie Larson as his "
                            "mother, who is locked in a cage every night. Produced by J.J. Abrams.",
                     "note": "JT Mollner made Strange Darling (2024), a serial-killer thriller told out of order that "
                             "was one of the best-reviewed horror films of its year, and wrote the screenplay for The "
                             "Long Walk (2025). Skeletons is based on a short story by Phillip Fracassi and a draft by "
                             "Brian Duffield, who wrote Love and Monsters and directed No One Will Save You. Sony won "
                             "the film against Paramount, Neon and Warner Bros., and the cast is strong: Larson, Kyle "
                             "Gallner, Willa Fitzgerald, who was so good in Strange Darling, and John Goodman. The few "
                             "details released are intriguing. Telling a monster story through a child who doesn't "
                             "understand what is happening to his family is an old idea that works when it is done "
                             "well, and Mollner has shown he can hold back information.",
                     "first": "Nothing. Strange Darling shows what Mollner can do, if you have a strong stomach.",
                     "caveat": "We know very little about the plot. It opens against John Rambo, and a mid-budget "
                               "horror film can get lost in June."},
                    {"kind": "movie", "title": "Possession", "year": 2027, "creator": "Parker Finn",
                     "date": "2027-06-11",
                     "released": "In theaters · Paramount Pictures",
                     "why": "Parker Finn's remake of Andrzej Żuławski's 1981 film about a spy whose wife starts "
                            "behaving strangely after she asks for a divorce, with Callum Turner and Margaret Qualley.",
                     "note": "Żuławski's Possession is one of the strangest films ever made: a marriage falling apart "
                             "in divided Berlin that slowly becomes a horror film, with a performance by Isabelle Adjani "
                             "that won her the best actress prize at Cannes and is still discussed for its sheer "
                             "intensity. Remaking it is a bold idea. Parker Finn made Smile (2022) and Smile 2 (2024), "
                             "two of the most successful horror films of recent years, and this is the first film he "
                             "has directed that isn't based on his own work. Turner and Qualley take the Sam Neill and "
                             "Adjani roles, and the cast includes Paul Dano and Diego Calva. Robert Pattinson is one "
                             "of the producers. Paramount has put it on the same weekend as How to Train Your Dragon "
                             "2, for everyone who isn't going to that.",
                     "first": "The 1981 film, if you want to compare. It has been restored, and it is not for "
                              "everyone.",
                     "caveat": "Many horror fans don't want this film to exist, and the reaction to the announcement "
                               "was cool. Finn's Smile films relied heavily on jump scares, which the original never "
                               "needed."},
                ],
            },
            {
                "format": "movies",
                "id": "family",
                "label": "Family",
                "heading": "Three for a family trip to the cinema",
                "intro": [
                    "Two new animated films and the return of the most successful animated series of the 2000s. The "
                    "new ones are the bigger gamble and, on what we have seen, the more interesting.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Not Alone", "year": 2027,
                     "creator": "Eric Guillon, Claire Dodgson and Jonathan del Val",
                     "date": "2027-04-16",
                     "released": "In theaters · Universal Pictures and Illumination",
                     "why": "An animated romantic comedy with aliens: Timothée Chalamet and Selena Gomez voice Joe and "
                            "Fran, a shy rocket mechanic and an astro-botanist, whose launch preparations are "
                            "interrupted by three tiny aliens hiding in Joe's house.",
                     "note": "Illumination is the studio of Despicable Me, the Minions, Sing and The Super Mario Bros. "
                             "Movie, and apart from Migration (2023) its recent films have been sequels or "
                             "adaptations. Not Alone is an original, and the first trailer, in June 2026, was well "
                             "received. Chalamet's character is an "
                             "introvert who builds rockets, and Gomez plays the scientist he is paired with for the "
                             "first launch. The aliens, Dunk, Welly and Shirm, are on the run from an alien police "
                             "officer, Zandro, voiced by Brett Goldstein of Ted Lasso, and they need Fran's rocket to "
                             "get home. Rob Brydon, Diane Morgan and Jamie Demetriou voice them. Richard Curtis, who "
                             "wrote Notting Hill and Love Actually, is an executive producer, which may explain why "
                             "it looks like a romantic comedy first and an alien film second.",
                     "first": "Nothing. It is an original story.",
                     "caveat": "Illumination's films tend to be fast and noisy, and the jokes are aimed at children "
                               "first. A romance at the center may bore the youngest viewers."},
                    {"kind": "movie", "title": "Bad Fairies", "year": 2027, "creator": "Megan Nicole Dong",
                     "date": "2027-05-27",
                     "released": "In theaters · Warner Bros. Pictures Animation",
                     "why": "An animated musical about a gang of rebellious fairies in present-day London, led by Jayne "
                            "Staplegun (Cynthia Erivo), with songs by the writers of Six.",
                     "note": "Toby Marlow and Lucy Moss wrote Six, the musical about Henry VIII's wives that went from a "
                             "student show in Edinburgh to Broadway, and they are writing the songs here. That is the "
                             "best reason to go. The voice cast is a list of people who can sing: Erivo, fresh from "
                             "Wicked, Kylie Minogue as Clowder the Cat Witch, Jonathan Groff as Robin Goodfellow and "
                             "Catherine Tate as the Fairy Gothmother, with James Acaster and Ncuti Gatwa. Megan Nicole "
                             "Dong directs, with a script by the comedian Deborah Frances-White. It is the first film "
                             "under Warner Bros.'s deal with Locksmith Animation, and Isabella Summers of Florence and "
                             "the Machine wrote the score. It moved from May 21 to Thursday, May 27, the start of the "
                             "Memorial Day weekend, a day before Star Wars.",
                     "first": "Nothing. If your children like it, the Six cast recording is the obvious next step.",
                     "caveat": "We know the cast and the songwriters, and almost nothing about the story. Opening a "
                               "day before Starfighter is brave or foolish, and we will find out which."},
                    {"kind": "movie", "title": "Shrek 5", "year": 2027, "creator": "Walt Dohrn and Conrad Vernon",
                     "date": "2027-06-30",
                     "released": "In theaters · Universal Pictures and DreamWorks Animation",
                     "why": "The first Shrek film since 2010, with Mike Myers, Eddie Murphy and Cameron Diaz back, and "
                            "Zendaya as Shrek and Fiona's daughter, Felicia, now a teenager.",
                     "note": "The four Shrek films made nearly three billion dollars, and the first two are still "
                             "among the best animated comedies ever made. The last one, Shrek Forever After, came out "
                             "seventeen years before this, which means the babies at the end of Shrek the Third are "
                             "teenagers now, and the story is built around that. Walt Dohrn, who co-directed Trolls "
                             "and voiced Rumpelstiltskin in Shrek Forever After, directs with Conrad Vernon, who "
                             "co-directed Shrek 2 and voices the Gingerbread Man. Michael McCullers wrote it. Skyler "
                             "Gisondo and Marcello Hernández join as the other two children, Farkle and Fergus. The "
                             "teaser in June 2026 opened with a nod to William Steig's picture book, where the whole "
                             "thing began. It was first meant for the summer of 2026 and moved a year; it now opens "
                             "on a Wednesday, ahead of the Fourth of July.",
                     "first": "Shrek (2001) and Shrek 2 (2004) are the ones everyone remembers. Shrek Forever After "
                              "(2010) is the one this follows.",
                     "caveat": "When the new animation style was first shown in 2025, a lot of fans disliked it. "
                               "Late sequels rarely match the films that made a series, and this is the fifth."},
                ],
            },
            {
                "format": "movies",
                "id": "grown-up",
                "label": "Dramas, thrillers and romance",
                "heading": "Three for an evening without the children",
                "intro": [
                    "A legal drama, a romantic comedy and a Taylor Sheridan action thriller. Between them they cover "
                    "most of what adults go to the cinema for when it isn't a franchise.",
                ],
                "picks": [
                    {"kind": "movie", "title": "A Place in Hell", "year": 2027, "creator": "Chloe Domont",
                     "date": "2027-04-23",
                     "released": "In theaters · Neon",
                     "why": "A drama about a feud between a criminal defense attorney (Michelle Williams) and the "
                            "younger lawyer brought in to replace her (Daisy Edgar-Jones), from the director of Fair "
                            "Play.",
                     "note": "Chloe Domont's Fair Play (2023) was a thriller about a couple at a hedge fund whose "
                             "relationship falls apart when she is promoted over him, and it was one of the most "
                             "talked-about films at Sundance that year. A Place in Hell is about power at work again, "
                             "this time between two women. Williams plays the established attorney, Edgar-Jones the "
                             "newcomer, Cate Fine, and Andrew Scott and Danny Huston are in the cast. Neon bought it "
                             "and first dated it for Christmas Day 2026, then moved it to April in July, which gives "
                             "it room away from the awards films. It runs 110 minutes and was shot in New York and New "
                             "Jersey in the summer of 2025. A legal drama with two actors this good is something the "
                             "cinema doesn't get many of any more.",
                     "first": "Nothing. Fair Play, on Netflix, shows how Domont handles a power struggle.",
                     "caveat": "Fair Play's last act divided people, and this could go the same way. Neon moved it "
                               "out of Christmas to make room for another of its films, Luca Guadagnino's "
                               "Artificial, so April was not its first choice."},
                    {"kind": "movie", "title": "Beach Read", "year": 2027, "creator": "Yulin Kuang",
                     "date": "2027-05-07",
                     "released": "In theaters · 20th Century Studios",
                     "why": "The film of Emily Henry's 2020 novel, with Phoebe Dynevor as January Andrews, a romance "
                            "novelist, and Patrick Schwarzenegger as Gus Everett, a writer of serious literary "
                            "fiction.",
                     "note": "In the book, January and Gus are both broke, both stuck, and spending a summer in "
                             "neighbouring houses on Lake Michigan. They make a bet: she will write a gloomy literary "
                             "novel, he will write a happy ending, and they will teach each other how. It is funnier "
                             "than it sounds and sadder too, because January is also dealing with her father's death "
                             "and a secret he left behind. Yulin Kuang, who has been attached since the film was "
                             "announced in 2023, writes and directs. Kevin Bacon, Andie MacDowell, Kristin Davis and "
                             "Tig Notaro have roles that haven't been announced. It was filmed in Toronto in June 2026. "
                             "Henry's new novel, Modern Classic, comes out a month before, on April 6, so this is a "
                             "good spring to read both.",
                     "first": "The novel, if you have time. It is about 360 pages and reads quickly.",
                     "caveat": "Some readers objected to Schwarzenegger's casting because he didn't match the Gus they "
                               "pictured. Romantic comedies live or die on chemistry, and we haven't seen a trailer."},
                    {"kind": "movie", "title": "F.A.S.T.", "year": 2027, "creator": "Ben Richardson",
                     "date": "2027-05-14",
                     "released": "In theaters · Warner Bros.",
                     "why": "An action thriller written by Taylor Sheridan about a former special forces commando "
                            "picked by the DEA to lead a secret strike team against drug dealers the CIA is "
                            "protecting.",
                     "note": "Taylor Sheridan wrote Sicario and Hell or High Water before he built an empire of "
                             "television series around Yellowstone, and this is his first film for cinemas since Those "
                             "Who Wish Me Dead in 2021. "
                             "He wrote the script in the mid-2010s, around the time of Sicario, and the premise has "
                             "the same distrust of the agencies that are supposed to be on the same side. Brandon "
                             "Sklenar, who played Spencer Dutton in Sheridan's 1923, leads a cast with LaKeith "
                             "Stanfield, Jason Clarke, Sam Claflin and Trevante Rhodes. The director, Ben Richardson, "
                             "is making his first feature. He was the cinematographer of Beasts of the Southern Wild "
                             "and Sheridan's Wind River, and he has shot several of Sheridan's series. Warner Bros. "
                             "moved it from April 23 to May 14.",
                     "first": "Nothing. Sicario (2015) is the film it is most likely to resemble.",
                     "caveat": "A script that sat on a shelf for a decade, from a writer who now works mostly in "
                               "television, with a first-time director. It could be lean and good, or a 2015 film "
                               "made in 2027."},
                ],
            },
        ],
        "also": [
            ("Panic Carefully (April 9), Spaceballs: The New One (April 23), The Legend of Zelda (April 30) and "
             "Star Wars: Starfighter (May 28).",
             "The four biggest films of the spring, all written up in our broader spring 2027 guide."),
            ("The Surgeon (April, Sony).",
             "Michelle Yeoh as a surgeon kidnapped and forced to operate on a mysterious patient, a Toronto festival "
             "pickup from the producers of John Wick. Sony hasn't confirmed the day."),
            ("Boys for Life (April 9).",
             "An R-rated comedy from Paramount, directed by Tyler Falbo."),
            ("The Catch (May 21).",
             "Emma Stone and Chris Pine in a romantic comedy from Universal, directed by Dave McCary. The plot "
             "hasn't been announced."),
            ("The Hole (June 25).",
             "Kim Jee-woon, the director of I Saw the Devil, directs Theo James and Jung Ho-yeon for Amazon MGM's "
             "Orion."),
            ("Warner Bros.'s Ocean's Eleven prequel (June 25).",
             "Bradley Cooper directs and stars with Margot Robbie in a prequel to the Ocean's heist films."),
            ("Man of Tomorrow (July 9).",
             "James Gunn's follow-up to Superman (2025) opens nine days after the end of this guide."),
        ],
        "plan_heading": "A plan for the spring",
        "plan": [
            "April is for adults and small children. Not Alone on the 16th is the family outing, and A Place in "
            "Hell on the 23rd is the one to see without them. The spring guide's films fill the rest of the month: "
            "Panic Carefully on the 9th, Spaceballs on the 23rd and Zelda on the 30th. If you are reading Beach Read "
            "before the film, start now.",
            "May starts with a choice on the 7th between Beach Read and Anything but Ghosts, which makes for a good "
            "double bill if you can stand the change of mood. F.A.S.T. follows on the 14th. Memorial Day weekend is "
            "Star Wars, with Bad Fairies opening a day earlier for families who would rather sing.",
            "June is the busiest month of the year so far. John Rambo and Skeletons open on the 4th, How to Train "
            "Your Dragon 2 and Possession on the 11th, Spider-Verse on the 18th and Shrek 5 on the 30th. If you have "
            "children and a budget, pick two of the three family films and catch the third at home later. Re-watch "
            "Across the Spider-Verse in the week before the 18th; you will need it.",
        ],
        "method": [
            "Prepared by OmniTrackr with AI assistance and reviewed by the site owner before publishing. None of these "
            "films had opened when we wrote about them, so this is a guide to what we think is worth seeing, not a set "
            "of reviews. We worked from the studios' own announcements, the release schedules and the coverage listed "
            "below, checked each date against a second source, and picked films we would recommend to a friend, with "
            "an honest note on who should skip them.",
            "Spring and summer dates move more than winter ones, because studios keep shuffling to avoid each other. "
            "While we were putting this guide together, Bad Fairies had moved from May 21 to May 27, F.A.S.T. from "
            "April 23 to May 14, A Place in Hell from Christmas 2026 to April, and Spider-Verse twice since it was "
            "given a date. We left "
            "out films whose dates disagree between sources. Dates are for the US.",
        ],
        "related": [
            ("Spring 2027 releases", "/new-releases/spring-2027"),
            ("Winter 2027 movies", "/new-releases/winter-2027-movies"),
            ("The best movies of 2026", "/best-of/2026/movies"),
            ("Spring 2027 books", "/new-releases/spring-2027-books"),
            ("How to track movies on OmniTrackr", "/movie-tracker"),
        ],
        "sources": [
            ("Variety: the John Rambo prequel's release date", "https://au.variety.com/2026/film/news/rambo-movie-release-date-37067/"),
            ("TheWrap: John Rambo is set for June 2027", "https://www.thewrap.com/industry-news/business/john-rambo-reboot-release-date-2027/"),
            ("Wikipedia: John Rambo (film)", "https://en.wikipedia.org/wiki/John_Rambo_(film)"),
            ("Wikipedia: How to Train Your Dragon 2 (2027 film)", "https://en.wikipedia.org/wiki/How_to_Train_Your_Dragon_2_(2027_film)"),
            ("Screen Daily: How to Train Your Dragon 2 begins filming at Sky Studios Elstree", "https://screendaily.com/news/how-to-train-your-dragon-2-begins-filming-at-uks-sky-studios-elstree-for-universal/5213515.article"),
            ("Bleeding Cool: Beyond the Spider-Verse shifts its date by a week", "https://bleedingcool.com/movies/spider-man-beyond-the-spider-verse-shifts-its-release-date-by-a-week"),
            ("TechRadar: Spider-Man: Beyond the Spider-Verse, everything we know", "https://www.techradar.com/streaming/entertainment/spider-man-beyond-the-spider-verse-hub"),
            ("Variety: Curry Barker's Anything but Ghosts gets a date", "https://au.variety.com/2026/film/news/curry-barker-obsession-anything-but-ghosts-release-date-40823/"),
            ("Wikipedia: Anything but Ghosts", "https://en.wikipedia.org/wiki/Anything_but_Ghosts"),
            ("The Playlist: Skeletons is set for June 2027 at Sony", "https://theplaylist.net/skeletons-jt-mollner-j-j-abrams-by-brie-larson-june-2027-sony-20260721/"),
            ("GamesRadar+: Sony wins the bidding for Skeletons", "https://www.gamesradar.com/entertainment/horror-movies/as-sony-wins-bidding-war-brie-larsons-creature-feature-drops-an-intriguing-new-plot-detail-and-now-were-itching-to-find-out-more/"),
            ("Variety: the Possession remake's release date", "https://au.variety.com/2026/film/news/possession-remake-release-date-margaret-qualley-39308/"),
            ("Fangoria: Possession remake release date", "https://www.fangoria.com/possession-remake-release-date/"),
            ("Cartoon Brew: Illumination's Not Alone and its directors", "https://www.cartoonbrew.com/feature-film/illumination-not-alone-eric-guillon-claire-dodgson-jonathan-del-val-263446.html"),
            ("Variety: the first Not Alone trailer", "https://au.variety.com/2026/film/news/not-alone-trailer-timothee-chalamet-selena-gomez-aliens-38156/"),
            ("Variety: Bad Fairies adds Kylie Minogue, Jonathan Groff and Catherine Tate", "https://au.variety.com/2026/film/news/cynthia-erivo-bad-fairies-kylie-minogue-jonathan-groff-41379/"),
            ("TheWrap: Cynthia Erivo to star in Bad Fairies", "https://www.thewrap.com/cynthia-erivo-to-star-in-bad-fairies-warner-bros-pictures-animation/"),
            ("GamesRadar+: Shrek 5 release date, plot and trailer", "https://www.gamesradar.com/entertainment/animation-movies/shrek-5-release-date-plot-trailer-news"),
            ("TheWrap: the first Shrek 5 teaser", "https://www.thewrap.com/creative-content/movies/shrek-5-teaser-trailer-mike-myers-eddie-murphy-zendaya/"),
            ("Bloody Disgusting: A Place in Hell moves from Christmas 2026 to April 2027", "https://bloody-disgusting.com/movie/3961082/a-place-in-hell-michelle-williams-thriller-moves-from-christmas-2026-to-april-2027/"),
            ("Wikipedia: A Place in Hell", "https://en.wikipedia.org/wiki/A_Place_in_Hell"),
            ("Books of Brilliance: the Beach Read film's date and cast", "https://booksofbrilliance.com/2026/09/18/beach-read-movie-release-date-cast/"),
            ("The Playlist: F.A.S.T. moves to May 2027", "https://theplaylist.net/f-a-s-t-taylor-sheridan-brandon-sklenar-may-2027-20260804/"),
            ("Wikipedia: F.A.S.T. (film)", "https://en.wikipedia.org/wiki/F.A.S.T._(film)"),
            ("TheWrap: Sony acquires The Surgeon at Toronto", "https://www.thewrap.com/creative-content/movies/sony-pictures-acquires-michelle-yeoh-tiff-action-thriller-the-surgeon/"),
            ("The Numbers: 2027 theatrical release schedule", "https://www.the-numbers.com/movies/release-schedule/2027"),
        ],
    },
    "spring-2027-anime": {
        "name": "Spring 2027 anime: the new shows worth a first episode",
        "period": "April to June 2027",
        "eyebrow": "ANIME SEASON GUIDE",
        "hub_label": "Spring 2027 anime",
        "focus": "anime",
        "search_title": "Spring 2027 anime: Kagurabachi, Gundam RG XARX-ZERO, Eleceed and the shows worth watching",
        "summary": ("Seven spring 2027 anime worth a first episode, from Kagurabachi, Eleceed and a new Gundam to a "
                    "bookshop mystery and a time-travel romance, with where to watch."),
        "published": "2026-11-21",
        "reviewed": "2026-11-21",
        "starts": "2027-04-01",
        "ends": "2027-06-30",
        "lead": [
            "The spring anime season starts in the first two weeks of April, and it is often the strongest of the "
            "year. April is when Japanese television schedules reset for the new business year, and studios like "
            "to open their biggest new series then. Spring 2027 has the most "
            "anticipated adaptation in years, Kagurabachi, a Gundam series from the director of Ghost in the Shell: "
            "Stand Alone Complex, and the long-delayed adaptation of one of the most popular Korean webtoons.",
            "This guide covers the season that runs from April to June. We went through the announced shows as they "
            "stood on November 21, 2026 and picked seven: three action series to start first, two fantasy shows from "
            "the same studio, and two quieter shows for people who want a mystery or a romance. Every one of them has "
            "been announced for April. No broadcaster has given a day this far ahead, so each date here is the month. "
            "For each show we say where it will stream if that is known, what it is based on, what to read or watch "
            "first, and who should skip it.",
            "Two of the best returning shows of the season, Skip and Loafer and The Dangers in My Heart, are written "
            "up in our broader spring 2027 guide, and a few more returning series are listed at the bottom of this "
            "page. Most spring shows are twelve or thirteen episodes, one a week, and the season ends in late June.",
            "A note on watching. Most new anime now reach streaming services outside Japan within hours of the "
            "Japanese broadcast, with subtitles, and English dubs follow a few weeks later for the bigger shows. "
            "That only works once a streaming deal is in place, and for four of our seven, nobody has announced one "
            "yet. Crunchyroll has Kagurabachi and Eleceed. The rest usually get their deals in the weeks before the "
            "season, and we will add them here when they do.",
        ],
        "sections": [
            {
                "format": "anime",
                "id": "action",
                "label": "Action",
                "heading": "Three action series to start first",
                "intro": [
                    "A sword-and-revenge story from Weekly Shonen Jump, a Gundam in a brand-new timeline and a Korean "
                    "webtoon about a teenager and a cat. If you only have time for one new show this spring, it is "
                    "probably in this group.",
                    "They suit different viewers. Kagurabachi is the one for people who watched Jujutsu Kaisen or "
                    "Demon Slayer and want the next big fight series. The Gundam is for science fiction fans, and "
                    "because it starts a new timeline, it is a good first Gundam for anyone who has always been put "
                    "off by the forty-year back catalog. Eleceed is the lightest of the three, and the funniest.",
                ],
                "picks": [
                    {"kind": "anime", "title": "Kagurabachi", "year": 2027, "creator": None,
                     "date": "2027-04-01", "month_only": True,
                     "released": "Crunchyroll, worldwide outside Japan, mainland China and the Koreas · Cypic",
                     "why": "Chihiro Rokuhira trained as a swordsmith under his father until a band of sorcerers, the "
                            "Hishaku, killed him and stole six enchanted blades. Chihiro takes the seventh, Enten, and "
                            "goes after them.",
                     "note": "Takeru Hokazono's manga began in Weekly Shonen Jump in September 2023 and became a "
                             "running joke online in its first weeks, with fans pretending it was already a classic. "
                             "Then it turned out to be good. It is a lean, cinematic revenge story "
                             "with very little filler, and the sword fights are drawn like storyboards for an action "
                             "film. With the eleventh volume, in May 2026, the series passed four million copies in "
                             "print and digital. The studio is Cypic, which made Umamusume: Cinderella Gray and The "
                             "Summer Hikaru Died, two of the best-looking shows of recent years, and Tetsuya Takeuchi "
                             "directs. Taihi Kimura voices Chihiro, Tomokazu Seki his father, Kunishige, and Katsuyuki "
                             "Konishi plays Shiba. The first twenty minutes have been touring "
                             "conventions since Anime Expo in the summer of 2026, and the first full episode will "
                             "screen in Japan before the broadcast. Crunchyroll has the streaming rights almost "
                             "everywhere outside Asia.",
                     "first": "Nothing. If you want a head start, the manga is published in English by VIZ Media.",
                     "first_link": "/if-you-liked/jujutsu-kaisen", "first_label": "If you liked Jujutsu Kaisen",
                     "caveat": "The story is a straight revenge plot, and Chihiro is a quiet, flat hero by design. The "
                               "hype is enormous, which is its own risk. Violent."},
                    {"kind": "anime", "title": "Mobile Suit Gundam RG XARX-ZERO", "year": 2027, "creator": None,
                     "date": "2027-04-01", "month_only": True,
                     "released": "Japan and North America in April · SOLA ANIMATION · streaming service not announced",
                     "why": "A Gundam series in an entirely new timeline, directed by Kenji Kamiyama, about Ray Azumi, "
                            "a war orphan who wakes up on the surface of the Moon and becomes the pilot of the Gundam "
                            "ZERO.",
                     "note": "Gundam has a lot of timelines, and most new series slot into one of them. This one "
                             "doesn't. Kamiyama has said it is not set in the Universal Century of the original "
                             "1979 series or in any of the other established eras. Its calendar is called After "
                             "Apocalypse: an alien object gave humanity new technologies, and they led to the "
                             "catastrophe the era is named for. Kamiyama directed Ghost in the Shell: Stand Alone Complex and The Lord of the Rings: "
                             "The War of the Rohirrim, and he built the setting with the novelist Toh EnJoe, who wrote "
                             "Godzilla Singular Point. Go Shiina, who co-wrote the music for Demon Slayer, is "
                             "composing. It is part of a larger project, announced at San Diego Comic-Con in 2026, "
                             "that includes a game, Gundam Rogue Orbit; the series is a prequel set about a hundred "
                             "years before it. It has been confirmed for Japan and North America in April, with "
                             "other regions to follow. Takeo Otsuka voices Ray.",
                     "first": "Nothing. A new timeline means no homework, which makes this the easiest way into Gundam "
                              "in years.",
                     "caveat": "Kamiyama's work is cerebral and slow to warm up, and fans who want classic Gundam "
                               "politics may find the science fiction too abstract. It is also partly an advert for a "
                               "game."},
                    {"kind": "anime", "title": "Eleceed", "year": 2027, "creator": None,
                     "date": "2027-04-01", "month_only": True,
                     "released": "Crunchyroll · Dandelion Animation Studio",
                     "why": "The anime of the Korean webtoon about Jiwoo, a kind teenager with superhuman reflexes, and "
                            "Kayden, a feared secret agent who is stuck in the body of a fat old cat.",
                     "note": "Eleceed, by Jeho Son and ZHENA, is one of the most popular action series on Naver "
                             "Webtoon, and the premise is a good one: a ruthless veteran fighter, trapped as a "
                             "grumpy cat, decides to train the soft-hearted boy who takes him in. It is funny, the "
                             "fights escalate nicely, and the relationship between the two of them carries it. The "
                             "anime was due in 2026 and was pushed to 2027 in June, then dated for April in October. "
                             "The staff is experienced. Yosuke Kuroda, who adapted My Hero Academia for television, "
                             "writes the scripts, and Taku Iwasaki, who scored Gurren Lagann and Soul Eater, writes "
                             "the music. Hiroshi Nishikiori directs. Junya Enoki, the voice of Yuji Itadori in Jujutsu "
                             "Kaisen, plays Jiwoo. The Japanese version gives most characters Japanese names, so Jiwoo "
                             "Seo is also Yuu Kazahaya, which may take getting used to if you have read the webtoon.",
                     "first": "Nothing. The webtoon is free to start on the Webtoon app if you want to read ahead.",
                     "caveat": "A delay of a year can mean production trouble. Webtoon adaptations have a mixed record "
                               "in anime, and Solo Leveling is the exception rather than the rule."},
                ],
            },
            {
                "format": "anime",
                "id": "fantasy",
                "label": "Fantasy",
                "heading": "Two fantasy shows from the same studio",
                "intro": [
                    "Studio 8bit, which made That Time I Got Reincarnated as a Slime, has two series in April: a "
                    "travelling story about a witch and a mercenary who start out as enemies, and a spin-off about "
                    "one of Slime's villains. It is a lot for one studio in one season, so watch the first episodes "
                    "for how well they hold up.",
                    "8bit has been making Slime since 2018 and knows that world well, so the spin-off is the safer "
                    "of the two. Witch and Mercenary is a new property for the studio and a different tone: slower, "
                    "more serious and closer to a road story than to an adventure in a game-like world.",
                ],
                "picks": [
                    {"kind": "anime", "title": "Witch and Mercenary", "year": 2027, "creator": None,
                     "date": "2027-04-01", "month_only": True,
                     "released": "Studio 8bit · Seven Seas publishes the novels and manga in English",
                     "why": "Zig, a hard-bitten mercenary, and Siasha, a solitary witch, start as enemies and end up "
                            "travelling together in search of somewhere she can live in peace.",
                     "note": "The light novels by Chohokiteki Kaeru are a slower, grittier kind of fantasy than the "
                             "comedies about being reborn in another world that fill most anime seasons. The appeal "
                             "is the partnership: a practical, unsentimental fighter and a woman with enormous power "
                             "who only wants somewhere to live. Taito Ban, the voice of "
                             "Jinwoo in Solo Leveling, plays Zig, and Saori Hayami, Yor in Spy x Family, plays "
                             "Siasha. Shinpei Ezaki directs, with Daishiro Tanimura writing the series and Rei Ishizuka "
                             "on music. Seven Seas has licensed both the novels and Makoto Miyagi's manga in English, "
                             "so it is easy to read ahead. If you liked the quieter travelling episodes of Frieren, or "
                             "the long road sections of Spice and Wolf, this is the closest thing this spring.",
                     "first": "Nothing. The first novel is a good read if you want to compare.",
                     "first_link": "/if-you-liked/frieren", "first_label": "If you liked Frieren",
                     "caveat": "Studio 8bit's recent work has been uneven, and a show this dependent on atmosphere "
                               "needs good animation. Streaming outside Japan hasn't been announced."},
                    {"kind": "anime", "title": "That Time I Got Reincarnated as a Slime: Clayman REVENGE",
                     "year": 2027, "creator": None,
                     "date": "2027-04-01", "month_only": True,
                     "released": "Studio 8bit · TV series, a spin-off of the main Slime anime",
                     "why": "A spin-off about Clayman, the demon lord Rimuru destroys in the second season of Slime, "
                            "who is sent seventy years into the past to try another path through his life.",
                     "note": "Slime is one of the most successful isekai of the last decade, and Clayman, a vain, "
                             "scheming puppet master, is one of its most memorable villains, mostly because of how "
                             "thoroughly he loses. The spin-off manga by Wataru Kajika, from a story by the series "
                             "creator, Fuse, gives him a second chance, which is a clever twist on the usual "
                             "reincarnation plot: the villain gets the do-over this time. Takehito Koyasu, who voiced "
                             "Dio in JoJo's Bizarre Adventure, is back as Clayman, and he is a big part of the fun. "
                             "Kentaro Sugimoto directs. The timing means fans get a full season of Clayman while they "
                             "wait for the main show: Slime's fourth season, which runs to five parts, comes back for "
                             "its third part in July 2027.",
                     "first": "Slime seasons 1 and 2, or at least season 2, which ends Clayman's story in the main "
                              "series. All of it is on Crunchyroll.",
                     "caveat": "This is for people who already watch Slime. A spin-off about a villain only works if "
                               "you remember why he was hated."},
                ],
            },
            {
                "format": "anime",
                "id": "quieter",
                "label": "Mystery and romance",
                "heading": "Two quieter shows for people who want a story",
                "intro": [
                    "A mystery set in a secondhand bookshop and a time-travel romance set in 1907. Neither has a fight "
                    "in it, as far as we know, and both come from long-running source material with an ending already "
                    "written.",
                    "Shows like these rarely top the streaming charts, and they are often the ones people are still "
                    "recommending years later. Skip and Loafer and The Dangers in My Heart, both back this spring, "
                    "started out the same way.",
                ],
                "picks": [
                    {"kind": "anime", "title": "The Case Files of Biblia Bookstore", "year": 2027, "creator": None,
                     "date": "2027-04-01", "month_only": True,
                     "released": "CloverWorks",
                     "why": "Shioriko Shinokawa, the shy owner of a secondhand bookshop in Kamakura who solves "
                            "mysteries connected to old books, and Daisuke Goura, a large, intimidating young man who "
                            "can't read books because of something in his past.",
                     "note": "En Mikami's novels have sold millions of copies in Japan and have already been a manga, "
                             "a TV drama and a live-action film. Each case turns on a real book, its edition, a note "
                             "in the margin or a missing page, and on what the book meant to the person who owned it, "
                             "so the stories are as much about families and grudges as about who did it. Daisuke "
                             "works in the shop and listens, because he can't read, and Shioriko, who can barely talk "
                             "to people, explains. The team is the one that made SHOSHIMIN: How to Become Ordinary, a "
                             "smart, dry mystery series: director Mamoru Kanbe, writer Toshiya Oono and composer "
                             "Takahiro Obata, with CloverWorks animating. Riko Akechi and Shunsuke Takeuchi voice the "
                             "leads.",
                     "first": "Nothing. If you like it, the earlier SHOSHIMIN is the natural next show.",
                     "caveat": "Slow, talky and gentle. The books discussed are mostly Japanese classics, which may mean "
                               "little outside Japan. Streaming hasn't been announced."},
                    {"kind": "anime", "title": "Rainy Day Serenade", "year": 2027, "creator": None,
                     "date": "2027-04-01", "month_only": True,
                     "released": "Tezuka Productions · Kodansha USA publishes the manga in English from January 2027",
                     "why": "Hina Katagiri keeps dreaming of her younger self in a garden. When she finds the place, a "
                            "young man, Takaaki, mistakes her for his fiancée, and she realises she is in Japan in "
                            "1907.",
                     "note": "Haruka Kawachi's manga ran for eleven years in Kodansha's Kiss, a magazine for adult "
                             "women, and finished in November 2025 at fourteen volumes, so the anime has a complete "
                             "story to adapt. Time-travel romances are common, but this one has room to be about "
                             "the period itself: late Meiji Japan, a time of rapid change, seen by a modern woman whom "
                             "everyone takes for someone else. Tezuka Productions is animating, with Takashi Kamei "
                             "directing, Yoko Yonaiyama writing the series and Nobuteru Yuki, the character designer "
                             "of Escaflowne and Record of Lodoss War, designing the characters. Yume Miyamoto plays "
                             "Hina and Takeo Otsuka, who also leads the new Gundam, plays Takaaki. Kodansha USA is "
                             "publishing the manga in English as two-in-one omnibus volumes from January 2027, so "
                             "readers can start before the anime.",
                     "first": "Nothing. The first English omnibus is out three months before the anime.",
                     "caveat": "A romance between a modern woman and a man engaged to someone else in 1907 raises "
                               "questions the show may or may not handle well. Streaming hasn't been announced."},
                ],
            },
        ],
        "also": [
            ("Skip and Loafer, season 2, and The Dangers in My Heart, season 3 (April).",
             "Two of the gentlest and best-loved shows of 2023 come back. Both are written up in our spring 2027 "
             "guide."),
            ("Laid-Back Camp, season 4 (April).",
             "Rin, Nadeshiko and the outdoor club go camping again, now animated by FuRyu Pictures, the series' "
             "third studio."),
            ("The Apothecary Diaries, season 3 part 2 (April).",
             "The second half of the third season of Maomao's palace mysteries, following the first half in "
             "October 2026."),
            ("Kindergarten Wars (spring).",
             "Sunrise and Felix Film adapt Yo Chiba's comedy about Rita, a former assassin who now guards a "
             "kindergarten for the children of the rich and powerful. Announced for spring, with no month yet."),
            ("LONA (spring).",
             "An original series from WIT Studio about Ao and her apprentice Sango, who analyse the brains of the "
             "dead after dead people start attacking the living. Posuka Demizu, the artist of The Promised "
             "Neverland, drew the original characters."),
            ("Fate Rewinder (April).",
             "Rie Matsumoto, the director of Kyousogiga and Blood Blockade Battlefront, adapts Futa Kimura's "
             "time-travel action manga for Bones Film. Reports disagree on whether it is a film or a series, so we "
             "have left it off the picks until that is clear."),
            ("That Time I Got Reincarnated as a Slime, season 4 part 3 (July).",
             "The main series returns just after this season ends."),
            ("Gundam Rogue Orbit (March 5, 2027).",
             "The game that the new Gundam series is a prequel to, out a month before it."),
        ],
        "plan_heading": "A plan for the season",
        "plan": [
            "In the first week of April, try a first episode of everything that looks interesting and drop what "
            "doesn't grab you by the third. That is how most people watch an anime season, and with seven shows "
            "here plus the returning ones, nobody needs to keep all of them. Kagurabachi is the one to watch live if "
            "you watch anything live, because it will be the show everyone is talking about.",
            "For the quieter shows, wait a few weeks and watch two or three episodes at once. The Case Files of "
            "Biblia Bookstore is a case-a-week mystery that works best in pairs, and Rainy Day Serenade will build "
            "slowly. If you are reading ahead, the Witch and Mercenary novels and the Rainy Day Serenade omnibus are "
            "the easiest to find in English.",
            "Slime fans can spend the season on Clayman and go straight into the main series in July. Everyone else "
            "can use late June, when the season ends, to catch up on whatever they dropped too early. Streaming "
            "deals for several of these shows are still to be announced, and we will add them to this page when "
            "they are.",
        ],
        "method": [
            "Prepared by OmniTrackr with AI assistance and reviewed by the site owner before publishing. None of these "
            "shows had aired when we wrote about them, so this is a guide to what we think is worth a first episode, "
            "not a set of reviews. We worked from the studios' and licensors' announcements and the coverage listed "
            "below, and kept only shows announced for April.",
            "Anime dates are announced late. This far ahead, studios give the month and broadcasters give the day "
            "and time a few weeks before the season, along with the streaming deals outside Japan. Kindergarten Wars "
            "and LONA have been announced only for spring, which usually means April, so we list them at the bottom "
            "until there is a month. We will check every show again in March.",
        ],
        "related": [
            ("Spring 2027 releases", "/new-releases/spring-2027"),
            ("Winter 2027 anime", "/new-releases/winter-2027-anime"),
            ("If you liked Jujutsu Kaisen", "/if-you-liked/jujutsu-kaisen"),
            ("The best anime of 2026", "/best-of/2026/anime"),
            ("How to track anime and episodes on OmniTrackr", "/anime-tracker"),
        ],
        "sources": [
            ("Anime News Network: Kagurabachi TV anime by Cypic in April 2027", "https://www.animenewsnetwork.com/press-release/2026-04-27/kagurabachi-set-for-tv-anime-adaptation-by-cypic-in-april-2027/.236851"),
            ("The Outer Haven: Kagurabachi comes to Crunchyroll in April 2027", "https://www.theouterhaven.net/kagurabachi-comes-to-crunchyroll-april-2027/"),
            ("Automaton: Mobile Suit Gundam RG XARX-ZERO in April 2027", "https://automaton-media.com/en/news/mobile-suit-gundam-rg-xarx-zero-to-release-in-april-2027-a-brand-new-anime-directed-by-kenji-kamiyama/"),
            ("Anime Corner: Gundam RG XARX-ZERO and Kenji Kamiyama's RG project", "https://animecorner.me/mobile-suit-gundam-rg-xarx-zero-anime-announced-as-part-of-kenji-kamiyamas-new-multimedia-rg-project/"),
            ("Final Weapon: Eleceed premieres in April 2027", "https://finalweapon.net/2026/10/21/eleceed-anime-premieres-in-april-2027/"),
            ("Final Weapon: the Eleceed anime is delayed to 2027", "https://finalweapon.net/2026/06/26/eleceed-anime-gets-delayed-to-2027/"),
            ("Anime Corner: Witch and Mercenary trailer, cast and April 2027 date", "https://animecorner.me/witch-and-the-mercenary-anime-reveals-first-trailer-new-cast-april-2027-release/"),
            ("Anime Corner: Slime season 4 part 3 in July, Clayman REVENGE in April", "https://animecorner.me/tensura-season-4-cour-3-set-for-july-2027-clayman-revenge-anime-announced-for-april/"),
            ("Anitrendz: The Case Files of Biblia Bookstore from the SHOSHIMIN director", "https://www.anitrendz.com/news/2026/04/21/the-case-files-of-biblia-bookstore-tv-anime-from-shoshimin-director-to-air-in-2027"),
            ("Anime News Network: Biblia Bookstore anime sets an April debut", "https://www.animenewsnetwork.com/news/2026-10-03/antiquarian-bookshop-biblia-case-files-anime-new-video-unveils-more-cast-and-staff-april-debut/.242446"),
            ("Anime Corner: Rainy Day Serenade key visual, cast and April 2027 premiere", "https://animecorner.me/rainy-day-serenade-anime-reveals-key-visual-teaser-trailer-main-cast-april-2027-premiere/"),
            ("Anitrendz: Kindergarten Wars is coming in spring 2027", "https://www.anitrendz.com/news/2026/03/28/kindergarten-wars-is-coming-in-spring-2027-reveals-cast-new-visual-and-trailer"),
            ("Anitrendz: WIT Studio's original anime LONA", "https://www.anitrendz.com/news/2026/06/28/wit-studios-new-original-anime-reveals-lona-title-brain-analyzing-premise-spring-2027-start-date"),
            ("Anime Corner: Fate Rewinder trailer and April 2027 date", "https://animecorner.me/fate-rewinder-anime-new-trailer-key-visual-and-april-2027-release-date-revealed/"),
            ("Final Weapon: Laid-Back Camp season 4 premieres in April 2027", "https://finalweapon.net/2026/11/06/laid-back-camp-season-4-premieres-in-april-2027/"),
            ("LiveChart: spring 2027 anime", "https://www.livechart.me/spring-2027/tv"),
        ],
    },
    "spring-2027-books": {
        "name": "Spring 2027 books: the new novels worth reading from April to June",
        "period": "April to June 2027",
        "eyebrow": "BOOKS RELEASE GUIDE",
        "hub_label": "Spring 2027 books",
        "focus": "books",
        "search_title": "Spring 2027 books: Brit Bennett, Anne Tyler, Abby Jimenez, Kate Quinn and more",
        "summary": ("Fourteen spring 2027 books worth reading, from new novels by Brit Bennett, Anne Tyler and Louise "
                    "Erdrich to Abby Jimenez, Carley Fortune and Kate Quinn."),
        "published": "2026-11-21",
        "reviewed": "2026-11-21",
        "starts": "2027-04-01",
        "ends": "2027-06-30",
        "lead": [
            "April to June is when publishers bring out the books they hope people will take on holiday, and the "
            "list for 2027 is unusually strong. Brit Bennett has her first novel in seven years. Anne Tyler, Louise "
            "Erdrich and Richard Powers all publish within a fortnight of each other. Carley Fortune goes back to "
            "the lake town of her first book, Katherine Center and Abby Jimenez have new romantic comedies, and the "
            "sequel to The Lost Apothecary finally arrives. So does the next book about the couple from Heated "
            "Rivalry, the most talked-about romance on television.",
            "This guide is the short version. We went through the publishers' catalogs as they stood on November 21, "
            "2026 and picked fourteen books: five romances, four literary novels, three historical novels and two "
            "for something different, a sword-and-sorcery collection and a book about the scale of life. For each "
            "one we say when it comes out and who publishes it, what it is about, what to read first if anything, "
            "and the thing most likely to put you off. We have not read them yet, because almost nobody has, so read "
            "these as bets, not reviews.",
            "Dates are for the first US edition, and nearly all of them fall on a Tuesday, the day American "
            "publishers release new books. Two of the biggest novels of the season, Emily Henry's Modern Classic on "
            "April 6 and Kristin Hannah's The Fire on May 4, are written up in our broader spring 2027 guide, so they "
            "are only listed at the bottom of this one.",
        ],
        "sections": [
            {
                "format": "books",
                "id": "romance",
                "label": "Romance",
                "heading": "Five romances, from a letters romance to a hockey marriage",
                "intro": [
                    "Romance is the best-selling kind of fiction in America, and spring is its busiest season. "
                    "These five range from a closed-door letters romance to some of the most explicit books on the "
                    "list, so each entry says which is which.",
                ],
                "picks": [
                    {"kind": "book", "title": "Feels Like Falling", "year": 2027, "creator": "Abby Jimenez",
                     "date": "2027-04-20",
                     "released": "Hardcover, ebook and audiobook · Forever · 384 pages",
                     "why": "Elizabeth is tired of being the dependable one for her father, her disabled sister and "
                            "her best friend. Mike Maddox, a coworker she can't stand, has had feelings for her for "
                            "years and is trying to make up for a past that cost him his best friend.",
                     "note": "Abby Jimenez is one of the most popular romance writers in America, and she has a "
                             "particular gift: her books are very funny and they are about real trouble, illness, "
                             "money, caring for family, without either side cancelling the other out. Part of Your "
                             "World, Yours Truly and Just for the Summer were all bestsellers. The set-up here is a "
                             "classic, enemies who aren't really enemies, and the publisher's description gives it "
                             "weight: Mike's job may be on the line, and he tries to win Elizabeth's trust by showing "
                             "up for her and her sister. The question the book seems to ask is "
                             "whether she can trust her own judgment of him over what everyone else says. Jimenez also "
                             "runs a bakery in Minnesota, and food tends to turn up in her books.",
                     "first": "Nothing. Her books are standalones, though some characters cross over. Part of Your "
                              "World (2022) is the usual place to start.",
                     "caveat": "Open-door romance, with explicit scenes. Jimenez's books can be heavier than their "
                               "covers suggest, which is a plus or a minus depending on your mood."},
                    {"kind": "book", "title": "The Lovebirds", "year": 2027, "creator": "Katherine Center",
                     "date": "2027-05-18",
                     "released": "Hardcover, ebook and audiobook · St. Martin's Press · 320 pages",
                     "why": "Addie Mitchell works as the assistant to January Knox, her old grade-school frenemy and "
                            "now a big Texas influencer. When a childhood friend of theirs, Denton Hayes, emails "
                            "January from Antarctica, January tells Addie to delete it. Addie writes back as January "
                            "instead.",
                     "note": "Katherine Center publishes a romantic comedy almost every May, and they are some of the "
                             "kindest books in the genre: Things You Save in a Fire, Hello Stranger, The Rom-Commers, "
                             "The Love Haters and, in 2026, The Shippers. The Lovebirds is a letters romance, a "
                             "modern Cyrano. Denton was the boy everyone liked in middle school and is now a "
                             "penguinologist at the bottom of the world, and the correspondence Addie carries on in "
                             "January's name turns into something real. Then he arrives in Texas, expecting to pick up "
                             "where the emails left off, with the wrong woman. Center lives in Houston and sets most of "
                             "her books in Texas, and she is good at the comedy of people pretending to be someone they "
                             "are not, and better at the moment when they have to stop.",
                     "first": "Nothing. Her books are standalones, and The Rom-Commers (2024) is a good one to start "
                              "with.",
                     "caveat": "A romance built on a lie needs the reveal to land, and the set-up asks you to forgive "
                               "Addie a lot. Closed-door, so lighter on heat than most of the romances here."},
                    {"kind": "book", "title": "Only in Summer", "year": 2027, "creator": "Carley Fortune",
                     "date": "2027-05-18",
                     "released": "Hardcover, ebook and audiobook · Berkley",
                     "why": "The third novel set in the lake town of Barry's Bay: Eleanor Florek, cousin of Charlie and "
                            "Sam from Every Summer After, buys a cottage there and finds out the house next door is "
                            "about to be torn down for an enormous new lake house.",
                     "note": "Carley Fortune's first novel, Every Summer After (2022), about a woman who goes back to "
                             "the Ontario lake where she spent every teenage summer, made her one of the defining "
                             "names of summer romance, and she has come back to Barry's Bay twice since: One Golden "
                             "Summer followed Charlie, and now his cousin Eleanor gets a book. Fortune writes about "
                             "lake country the way other writers write about cities, with the docks, the cottages and "
                             "the old families all part of the story, and Kirkus's description suggests this one "
                             "will be about what happens when new money comes to an old place. It is her sixth novel. "
                             "If you read one book on a dock this year, it may as well be this.",
                     "first": "Nothing, though it will mean more if you have read Every Summer After (2022), where "
                              "Charlie and Sam first appear.",
                     "caveat": "We know the set-up and little else, and the publisher hasn't announced a page count. "
                               "Fortune's books follow a recognisable shape: dual timelines and a lot of longing."},
                    {"kind": "book", "title": "Bad in Bed", "year": 2027, "creator": "Ali Hazelwood",
                     "date": "2027-06-01",
                     "released": "Hardcover, paperback and ebook · Berkley · 224 pages",
                     "why": "After her engagement ends and her ex complains publicly about her in bed, Billie van "
                            "Buren, a sheltered doctoral student, asks her longtime frenemy Dr. Max Austin, a medical "
                            "fellow, to help her get some practice.",
                     "note": "Ali Hazelwood was a neuroscientist before she was a novelist, and The Love Hypothesis "
                             "(2021), about a graduate student who fake-dates a professor, made the academic romance a "
                             "genre of its own. Amazon has since adapted it for Prime Video. Bad in Bed is back in "
                             "that world: Billie is a statistician working on a doctorate, and her skills with data "
                             "are what throw her together with Max. The arrangement is meant to have no strings, and "
                             "you can guess how that goes. At 224 pages it is one of her shortest books, and Berkley "
                             "says this is the first time it has been published in print, so it may have appeared in "
                             "another format first. Hazelwood is prolific, and this is a quick summer read.",
                     "first": "Nothing. The Love Hypothesis is the one to read if you are new to her.",
                     "caveat": "The premise is explicit and so is the book. Short and light, so don't expect the depth "
                               "of her longer novels."},
                    {"kind": "book", "title": "Unrivaled", "year": 2027, "creator": "Rachel Reid",
                     "date": "2027-06-01",
                     "released": "Paperback, ebook and audiobook · Harlequin · Game Changers, book 7",
                     "why": "The third and last novel about Shane Hollander and Ilya Rozanov, after Heated Rivalry "
                            "and The Long Game: they are out, married and playing for the same team, and part of the "
                            "hockey world is turning against them.",
                     "note": "Rachel Reid's hockey romances had a devoted following for years before the television "
                             "series Heated Rivalry turned Shane and Ilya into two of the most talked-about characters "
                             "of 2025. The first two books about them are the source for the show, and Unrivaled "
                             "picks up years later. According to the publisher's description, the couple are now "
                             "public and married, and the backlash is being led by a podcast, Top Shelf, and an online "
                             "campaign called #TakeBackHockey, so this time the trouble comes from outside the "
                             "relationship: fame, and homophobia in professional sport. Reid delayed it from 2026, saying "
                             "she needed a little more time because of her schedule and her health. Good Morning "
                             "America revealed the cover in November 2026, along with special editions with sprayed "
                             "edges and illustrated endpapers. The timing works for fans of the show: season 2 is "
                             "expected in April, about two months earlier.",
                     "first": "Heated Rivalry (2019) and The Long Game (2022). The other Game Changers books are "
                              "optional.",
                     "caveat": "Very explicit, like the rest of the series. A book about a married couple has less of "
                               "the secrecy that made the first one so tense."},
                ],
            },
            {
                "format": "books",
                "id": "literary",
                "label": "Literary fiction",
                "heading": "Four literary novels from writers at the top of their game",
                "intro": [
                    "Three Pulitzer Prize winners and the author of one of the biggest novels of the 2020s. Tyler's is "
                    "the shortest at 240 pages; Bennett's the longest at 400.",
                ],
                "picks": [
                    {"kind": "book", "title": "I'm Hungry", "year": 2027, "creator": "Louise Erdrich",
                     "date": "2027-04-20",
                     "released": "Hardcover, ebook and audiobook · Harper · 304 pages",
                     "why": "Fargo, North Dakota, in 1975. Bazil, a young writer who takes whatever work she can get, "
                            "falls in with the city's poets, lovers and hustlers, among them her tougher Chippewa "
                            "cousin, the owner of a gift shop and a rich New York lawyer passing through.",
                     "note": "Louise Erdrich won the Pulitzer Prize for The Night Watchman (2020) and the National Book "
                             "Award for The Round House (2012), and her novels have been mapping the northern plains "
                             "and the Ojibwe communities of North Dakota and Minnesota for forty years. I'm Hungry is "
                             "set in the mid-1970s, a couple of years after the occupation of Wounded Knee, and the "
                             "publisher calls it both a moral fable and \"a love letter to downtown Fargo.\" Erdrich "
                             "is a member of the Turtle Mountain Band of Chippewa and runs Birchbark Books, an "
                             "independent bookshop in Minneapolis, and she writes about place better than almost "
                             "anyone. A novel about a young woman learning to be a writer, in a small city that "
                             "rarely gets a novel of its own, is a good fit for her.",
                     "first": "Nothing. The Sentence (2021), set in a Minneapolis bookshop, is the most enjoyable of "
                              "her recent novels if you want another.",
                     "caveat": "Erdrich's books move between voices and between comedy and grief, and a \"moral "
                               "fable\" may be looser than a conventional novel."},
                    {"kind": "book", "title": "The Return Trip Is Shorter", "year": 2027, "creator": "Anne Tyler",
                     "date": "2027-04-27",
                     "released": "Hardcover, ebook and audiobook · Knopf · 240 pages",
                     "why": "Ben Sullivan, widowed and living alone for the first time in more than thirty years, "
                            "would like to be left alone. Then his youngest sister, Cecily, turns up on his doorstep "
                            "after a breakup and needs somewhere to stay.",
                     "note": "Anne Tyler has been writing short, funny, forgiving novels about families for six "
                             "decades. She won the Pulitzer Prize for Breathing Lessons (1988) and has written more "
                             "than twenty novels since her first, in 1964. The set-up is pure Tyler: a man who would rather sit with "
                             "his grief, two bossy older sisters who keep trying to drag him out of it, and a chatty, "
                             "forgetful younger one who moves in and makes it impossible. Knopf's description says "
                             "Cecily's future takes an unexpected turn and Ben has to step up, which in a Tyler novel "
                             "usually means something small that turns out to matter a great deal. At 240 pages it is "
                             "a weekend's reading, and the kind of book you can give to almost anyone.",
                     "first": "Nothing. If you are new to Tyler, Breathing Lessons (1988) or the much shorter Three "
                              "Days in June (2025) are the places to start.",
                     "caveat": "Tyler's novels are small and quiet on purpose. If you want a plot that goes somewhere "
                               "dramatic, this isn't it."},
                    {"kind": "book", "title": "Late Light", "year": 2027, "creator": "Richard Powers",
                     "date": "2027-05-04",
                     "released": "Hardcover, ebook and audiobook · W. W. Norton · 320 pages",
                     "why": "After Charlie Borneman dies, his older brother Richie goes through his house in the "
                            "mountains of eastern Tennessee and finds proof of the visions Charlie had all his life, "
                            "while the tech company Richie works for prepares to launch a lifelike AI.",
                     "note": "Richard Powers won the Pulitzer Prize for The Overstory (2018), the novel about trees "
                             "that people still press on their friends, and his last book, Playground (2024), "
                             "was about the ocean and artificial intelligence. Late Light comes back to AI, from a "
                             "more personal angle. It begins in 1966 in Lincolnwood, Illinois, when Charlie, aged "
                             "five, has a vision of being connected to everything, and it follows the two brothers "
                             "across the decades that follow. Richie's half of the story is set inside a company "
                             "building a machine that may know people better than they know themselves, and the "
                             "question of what a person is, and what is lost when one dies, runs through both. "
                             "Powers is one of the few novelists who can make science and technology feel urgent "
                             "without turning his characters into mouthpieces, most of the time.",
                     "first": "Nothing. Playground is the closest of his earlier books, and The Overstory the best "
                              "known.",
                     "caveat": "Powers writes big ideas into his characters' conversations, and some readers find him "
                               "preachy. Grief and illness are at the center of it."},
                    {"kind": "book", "title": "The Last Diva", "year": 2027, "creator": "Brit Bennett",
                     "date": "2027-06-08",
                     "released": "Hardcover, ebook and audiobook · Riverhead Books · 400 pages",
                     "why": "Roz Randall and Cleo Wright form a singing group as teenagers in 1963 and spend the "
                            "next sixty years as rivals. When Cleo dies a legend, Roz is the one person who could tell "
                            "her real story.",
                     "note": "Brit Bennett's The Vanishing Half (2020), about twin sisters, one of whom lives as a white "
                             "woman, was one of the biggest literary novels of its decade, and readers have waited "
                             "seven years for the next one. The Last Diva is a novel about music, friendship and "
                             "fame, moving from the girl groups of the 1960s through soul, gospel and disco to the "
                             "present, and Riverhead's description asks who owns a star's secrets once she is gone. "
                             "Bennett is very good at the long arc of a life and at two women who define themselves "
                             "against each other, which is what this sounds like. It is the literary novel of the "
                             "summer most likely to be everywhere, on holiday reading tables and in book clubs, and "
                             "it has the makings of a film.",
                     "first": "Nothing. The Vanishing Half is the place to start if you haven't read her.",
                     "caveat": "After a seven-year wait, expectations are very high. Novels about musicians often "
                               "struggle to make the music itself come alive on the page."},
                ],
            },
            {
                "format": "books",
                "id": "historical",
                "label": "Historical fiction",
                "heading": "Three historical novels, two of them set in wartime",
                "intro": [
                    "Two world wars and Georgian London. All three come from authors whose earlier books were "
                    "bestsellers, and all three mix history with something else: time travel, a potion, a "
                    "blackmailer.",
                ],
                "picks": [
                    {"kind": "book", "title": "The Enigmas", "year": 2027, "creator": "Emilia Hart",
                     "date": "2027-04-06",
                     "released": "Hardcover, ebook and audiobook · St. Martin's Press · 368 pages",
                     "why": "London, 1940. Beatrice Bone's younger sister, Clemmie, dies in a fire while doing secret "
                            "war work at a place known as the Park, and an old pocket watch engraved \"memento mori\" "
                            "sends Beatrice back in time to try to save her.",
                     "note": "Emilia Hart's first novel, Weyward (2023), about three women in three centuries linked "
                             "by a strain of witchcraft, was one of the most successful debuts of its year, and The "
                             "Sirens followed. The Enigmas has the same shape, two women in two wars. In 1940 "
                             "Beatrice learns that saving her sister changes other things, and she has to choose "
                             "between Clemmie's life and her country's future. In 1915 her mother, Alice, is treating "
                             "wounded soldiers at the Endell Street hospital, the London military hospital run and "
                             "staffed entirely by women, while her husband is at the front, and she starts to have "
                             "visions that seem to be passing to her eldest daughter. Wartime codebreaking, time "
                             "travel and a family gift handed down through the women: it is a very readable "
                             "combination, and Hart is good at making the supernatural feel like part of history.",
                     "first": "Nothing. Weyward is the one to read if you like it.",
                     "caveat": "Time travel to change history raises more questions than a novel can answer, and the "
                               "ending will decide whether it works for you. Grief is at the center."},
                    {"kind": "book", "title": "The Lost Elixir", "year": 2027, "creator": "Sarah Penner",
                     "date": "2027-05-04",
                     "released": "Hardcover, ebook and audiobook · Park Row",
                     "why": "The sequel to The Lost Apothecary: in London in 1802, Eliza Fanning, now grown up with "
                            "children and a potion shop of her own, has an elixir said to change fate, and when her "
                            "children are kidnapped, the elixir is the ransom.",
                     "note": "The Lost Apothecary (2021) was a huge debut: a hidden shop in 1790s London where a "
                             "woman named Nella sold poisons to women who needed to be rid of a man, and a "
                             "present-day story about a woman who finds traces of it. Eliza was the girl who walked "
                             "into Nella's shop, and The Lost Elixir follows her as an adult, with potions taking the "
                             "place of poisons. The present-day half follows Gaynor Baymont, an archivist whose "
                             "childhood was changed by a terrible accident, as an old letter leads her to a vial, a "
                             "hidden tunnel and the missing elixir, with somebody else looking for it too. Penner has "
                             "said it works as a prequel as well as a sequel, and that it answers some of the "
                             "questions readers had about Nella. She also says it can be read on its own.",
                     "first": "The Lost Apothecary, ideally. It is short and quick, and you will get more out of "
                              "Eliza's story.",
                     "caveat": "Dual-timeline novels often have one half that is much stronger than the other, and in "
                               "the first book that half was the past. No page count yet."},
                    {"kind": "book", "title": "The Violet Pact", "year": 2027, "creator": "Kate Quinn",
                     "date": "2027-05-18",
                     "released": "Hardcover, ebook and audiobook",
                     "why": "In Cambridge in 1912, Jass Lennox, the daughter of a Scottish viscount, Gerren, a Cornish "
                            "medical student, and Ben, a scholar obsessed with climbing, swear a pact on the roof of "
                            "King's College Chapel. By 1918 the war has broken them apart, and a blackmailer is "
                            "hunting their secrets.",
                     "note": "Kate Quinn writes the historical novels that book clubs fight over: The Alice Network, "
                             "about women spies in the First World War, The Rose Code, about the codebreakers of "
                             "Bletchley Park, and The Briar Club. The Violet Pact is in three parts, 1912, 1914 and "
                             "1918. Jass joins the suffragettes and Gerren patches up the injured protesters. Ben's "
                             "dream of climbing Everest and a love affair that goes wrong split the three of them "
                             "before the war finishes the job. In 1918 Gerren, now a surgeon, is called to Castle "
                             "Kinross, a Scottish castle turned into a hospital for wounded soldiers, which is Jass's "
                             "home now that she is Lady Kinross. Friendship, class and a mystery in a big house in "
                             "wartime: it is a set-up Quinn handles better than almost anyone.",
                     "first": "Nothing. The Rose Code (2021) is her best if you want another.",
                     "caveat": "Quinn's books are long and packed with history, and the romance can be more melodrama "
                               "than some readers like. The publisher hasn't put up its page for it yet."},
                ],
            },
            {
                "format": "books",
                "id": "different",
                "label": "Fantasy and science",
                "heading": "Two for something different",
                "intro": [
                    "A collection of linked fantasy novellas and the most ambitious popular science book of the "
                    "spring. Neither is the kind of book that usually makes a seasonal list, and both deserve to.",
                ],
                "picks": [
                    {"kind": "book", "title": "Sorceress", "year": 2027, "creator": "Silvia Moreno-Garcia",
                     "date": "2027-06-01",
                     "released": "Hardcover, ebook and audiobook · Del Rey · 304 pages",
                     "why": "Three linked sword-and-sorcery novellas about Yalxi, a ruthless sorceress whose pearl ring "
                            "holds a nahual, an animal spirit that shares its power with her, and her loyal "
                            "companion.",
                     "note": "Silvia Moreno-Garcia changes genre with almost every book. Mexican Gothic (2020) was a "
                             "haunted-house novel set in 1950s Mexico, Velvet Was the Night a noir and The Bewitching "
                             "a witchcraft novel. Sorceress is old-fashioned sword and sorcery, the genre of Conan and "
                             "Fritz Leiber's Fafhrd and the Gray Mouser, built on Mesoamerican ideas instead of the "
                             "usual European ones. The three stories take Yalxi through the canals of a city, up into "
                             "the mountains and out to an archipelago haunted by ghosts, fighting necromancers, "
                             "thieves, gods and monsters while she looks for a way to make up for her past. Linked "
                             "novellas are a good format for this kind of story: each one is an adventure, and "
                             "together they make a life.",
                     "first": "Nothing. Mexican Gothic is the best known of her books if you want another.",
                     "caveat": "Episodic by design, so it reads more like three adventures than one novel. Sword and "
                               "sorcery is violent and its heroes are not nice people."},
                    {"kind": "book", "title": "Life Beyond Measure", "year": 2027, "creator": "Ed Yong",
                     "date": "2027-04-06",
                     "released": "Hardcover, ebook and audiobook · Knopf · 448 pages",
                     "why": "Ed Yong's book about how life works at every scale, from blue whales to bacteria, with "
                            "fireflies, a bristlecone pine, shorebirds that fly for days without stopping and an ant "
                            "colony that develops a personality.",
                     "note": "Ed Yong won a Pulitzer Prize for his reporting on the pandemic at The Atlantic, and his "
                             "two earlier books are among the best popular science of the last decade: I Contain "
                             "Multitudes (2016), about the microbes that live in and on us, and An Immense World "
                             "(2022), about how other animals sense the world. Life Beyond Measure does for size and "
                             "time what An Immense World did for the senses. It asks what it is like to be very big "
                             "or very small, very fast or very slow, a salamander that barely moves or a tree that "
                             "lives for thousands of years, and argues that seeing past the human scale shows how "
                             "connected all life is. Yong reads the audiobook himself. It is the nonfiction book of "
                             "the spring we would give to the widest range of people.",
                     "first": "Nothing. An Immense World is the natural companion.",
                     "caveat": "Long and packed with examples, and some readers prefer his writing in smaller doses. "
                               "Not a book with an argument to win, if that is what you want from nonfiction."},
                ],
            },
        ],
        "also": [
            ("Modern Classic by Emily Henry (April 6) and The Fire by Kristin Hannah (May 4).",
             "The two biggest novels of the season, both written up in our spring 2027 guide."),
            ("Emerald Lake by Nita Prose (April 6).",
             "A new mystery from the author of The Maid: human remains turn up by a lake in Ontario's cottage country, "
             "and an 84-year-old grandmother knows more about the summer of 1955 than she is saying."),
            ("Doom Painting by A.K. Blakemore (April 13).",
             "A 672-page novel of revolt in the years after the Black Death, from the author of The Manningtree "
             "Witches, published by Scribner."),
            ("Vera Wong's Vacation Hacks for Catching a Killer by Jesse Q. Sutanto (April 20).",
             "The third cozy mystery starring Vera Wong, the nosy tea shop owner."),
            ("Stormside by Alex Aster (April 20).",
             "The second book in the Starside fantasy series."),
            ("Silver Dawn by Marie Lu (April 27).",
             "The sequel to Red City."),
            ("Keep Me Like a Secret by Stacy Willingham (June 8).",
             "A new thriller from the author of A Flicker in the Dark."),
            ("Significant Other by Gillian McAllister (June).",
             "Three weeks after his wedding, a man is told by MI5 that his new wife is under surveillance. From the "
             "author of Wrong Place Wrong Time; we have seen two different dates for the US edition."),
            ("Bad Idea by Elle Kennedy (March 16).",
             "The first of the next-generation Off-Campus books is in our spring 2027 guide. It comes out just before "
             "this guide starts."),
        ],
        "plan_heading": "A plan for the spring",
        "plan": [
            "April starts strong. Life Beyond Measure, The Enigmas and Emily Henry's Modern Classic all come out on "
            "the 6th, so pick the one that suits your mood and put holds on the others. Erdrich and Jimenez follow "
            "on the 20th and Anne Tyler on the 27th, which makes the end of the month a good time for a short, kind "
            "novel.",
            "May 4 is a big Tuesday, with Late Light, The Lost Elixir and Kristin Hannah's The Fire. May 18 is "
            "bigger: The Lovebirds, Only in Summer and The Violet Pact all come out that day, so if you use a "
            "library, place your holds in March. Those three are the obvious books for a Memorial Day weekend away.",
            "June 1 brings Bad in Bed, Unrivaled and Sorceress, and The Last Diva follows on the 8th. If you only buy "
            "one hardcover this spring, we would make it Bennett's. Dates are firm for books, but holds lists for "
            "the biggest names fill up months ahead, and the date at the top of the page says when we last checked.",
        ],
        "method": [
            "Prepared by OmniTrackr with AI assistance and reviewed by the site owner before publishing. None of these "
            "books had been published when we wrote about them, and we have not read them, so this is a guide to what "
            "we think is worth reading, not a set of reviews. We worked from the publishers' own catalog pages and the "
            "coverage listed below, checked each date against a second source where we could, and picked books we "
            "would recommend to a friend, with an honest note on who should skip them.",
            "Book dates are the firmest of any format, but they differ between countries. Emerald Lake, for instance, "
            "comes out in Canada a week before the US. The dates, publishers and page counts here are for the first "
            "US edition, usually the hardcover. Where a publisher hasn't yet announced a page count, or put up its "
            "own page, we say so.",
        ],
        "related": [
            ("Spring 2027 releases", "/new-releases/spring-2027"),
            ("Winter 2027 books", "/new-releases/winter-2027-books"),
            ("The best books of 2026", "/best-of/2026/books"),
            ("Spring 2027 movies", "/new-releases/spring-2027-movies"),
            ("How to track books on OmniTrackr", "/book-tracker"),
        ],
        "sources": [
            ("Hachette Book Group: Feels Like Falling", "https://www.hachettebookgroup.com/titles/abby-jimenez/feels-like-falling/9781538775653/"),
            ("BingeBooks: The Lovebirds", "https://bingebooks.com/book/the-lovebirds"),
            ("Kirkus: a new novel by Carley Fortune is coming in 2027", "https://www.kirkusreviews.com/news-and-features/articles/new-novel-by-carley-fortune-coming-in-2027/"),
            ("Penguin Random House: Bad in Bed", "https://www.penguinrandomhouse.com/books/824777/bad-in-bed-by-ali-hazelwood/"),
            ("Good Morning America: the Unrivaled cover", "https://goodmorningamerica.com/culture/story/rachel-reids-unrivaled-reveals-1st-shane-ilyas-love-137989807"),
            ("Cosmopolitan, via AOL: why Unrivaled moved to 2027", "https://www.aol.com/articles/why-next-heated-rivalry-book-123100509.html"),
            ("BookBrowse: I'm Hungry", "https://www.bookbrowse.com/bb_briefs/detail/index.cfm/ezine_preview_number/27295/im-hungry"),
            ("Penguin Random House: The Return Trip Is Shorter", "https://www.penguinrandomhouse.com/books/852743/the-return-trip-is-shorter-by-anne-tyler/"),
            ("BookBrowse: Late Light", "https://www.bookbrowse.com/bb_briefs/detail/index.cfm/ezine_preview_number/27765/late-light"),
            ("Penguin Random House: The Last Diva", "https://www.penguinrandomhouse.com/books/671903/the-last-diva-by-brit-bennett/"),
            ("BookBrowse: The Enigmas", "https://www.bookbrowse.com/bb_briefs/detail/index.cfm/ezine_preview_number/27530/the-enigmas"),
            ("Books of Brilliance: The Lost Elixir, the sequel to The Lost Apothecary", "https://booksofbrilliance.com/2026/11/02/the-lost-apothecary-sequel-the-lost-elixir/"),
            ("FantasticFiction: The Violet Pact", "https://www.fantasticfiction.com/q/kate-quinn/violet-pact.htm"),
            ("Penguin Random House: Sorceress", "https://www.penguinrandomhouse.com/books/761101/sorceress-by-silvia-moreno-garcia/"),
            ("Penguin Random House: Life Beyond Measure", "https://www.penguinrandomhouse.com/books/757705/life-beyond-measure-by-ed-yong/"),
            ("NetGalley: Emerald Lake", "https://www.netgalley.com/catalog/book/901483"),
            ("The Bookish Bulletin: most anticipated April 2027 books", "https://www.thebookishbulletin.com/blog/most-anticipated-april-2027-books"),
            ("The Bookish Bulletin: most anticipated May 2027 books", "https://www.thebookishbulletin.com/blog/most-anticipated-may-2027-books"),
            ("The Bookish Bulletin: most anticipated June 2027 books", "https://www.thebookishbulletin.com/blog/most-anticipated-june-2027-books"),
            ("BookBrowse: our most anticipated books for 2027", "https://www.bookbrowse.com/blogs/editor/index.cfm/2026/11/10/Our-Most-Anticipated-Books-for-2027"),
        ],
    },
    "spring-2027-games": {
        "name": "Spring 2027 games: the new releases worth playing from April to June",
        "period": "April to June 2027",
        "eyebrow": "GAMES RELEASE GUIDE",
        "hub_label": "Spring 2027 games",
        "focus": "games",
        "search_title": "Spring 2027 games: Pony Island 2, Mariachi Legends, Stronghold 4, Melty Blood and more",
        "summary": ("Eight spring 2027 games worth playing, from Pony Island 2 and Mariachi Legends to Stronghold 4 "
                    "and Melty Blood: Twi-Lumina, with what to play first."),
        "published": "2026-11-22",
        "reviewed": "2026-11-22",
        "starts": "2027-04-01",
        "ends": "2027-06-30",
        "lead": [
            "The biggest games of the spring all come out in its first seven weeks. Exodus, the science fiction "
            "role-playing game from former BioWare developers, arrives on April 7, Final Fantasy VII Revelation the "
            "next day, and God of War Laufey on May 20. Those three are written up in our all-format spring guide. "
            "This one is about the games that come out around them, which are easy to miss when a Final Fantasy is "
            "taking up everyone's evenings.",
            "We went through the publishers' announcements as they stood on November 22, 2026, and kept the games "
            "with at least a month: eight of them, four from small independent studios, two from Japan and two "
            "strategy games. For each one we say when it comes out and on what, what it is, what to play first if "
            "anything, and the thing most likely to put you off. None of them are out yet, so read these as bets, "
            "not reviews. We say where we are guessing.",
            "A lot of spring games still have only a season. Kirby and the World Beyond, Spyro: A Realm Beyond, Mega "
            "Man: Dual Override, Turok: Origins and The Expanse: Osiris Reborn are all due in spring 2027 with no "
            "month, so they are listed at the bottom with what we know. We will move them up into the guide when "
            "their publishers set a date. Dates are for the US, and the platforms are the ones announced so far.",
        ],
        "sections": [
            {
                "format": "games",
                "id": "indies",
                "label": "Indies",
                "heading": "Four indie games, one of them from the maker of Inscryption",
                "intro": [
                    "These come from small studios and will get a fraction of the attention Final Fantasy gets in "
                    "April. Two of them come out on the same Tuesday, April 27, three weeks after the big releases. "
                    "Haunted Paws has a month but no day, and Rustown closes the season on June 30.",
                ],
                "picks": [
                    {"kind": "game", "title": "Pony Island 2: Panda Circus", "year": 2027, "creator": None,
                     "date": "2027-04-27",
                     "released": "PC (Steam)",
                     "why": "A sequel to Daniel Mullins's 2016 puzzle game Pony Island. You play a young nomad who "
                            "died too early and has to escape the Earth Prison with your soul and your sanity, "
                            "bargaining with the deities of the underworld and beating, or breaking, their games.",
                     "note": "Mullins makes games that turn on you. Pony Island looked like a cheap arcade game about "
                             "a pony jumping fences and turned out to be a machine built by the devil, which you "
                             "escaped by hacking it from the inside. Inscryption (2021), his next game, began as a "
                             "card game in a dark cabin and kept turning into something else, and it won the Seumas "
                             "McNally Grand Prize at the Independent Games Festival. Panda Circus looks like a run of "
                             "arcade cabinets, each with its own rules and its own look, and it adds live-action "
                             "scenes with Sungwon Cho, Arian Moayed (Stewy in Succession), Caitlin Reilly and Kevin "
                             "Saxby. The store page says \"This is not a game about ponies,\" which fans of the first "
                             "one will read as a promise. If you liked Inscryption, this is the spring game we would "
                             "put first.",
                     "first": "Nothing is required, but Pony Island (2016) is short and cheap, and it is the quickest "
                              "way to find out whether this kind of game is for you. Inscryption is the fuller "
                              "version of the same idea.",
                     "caveat": "PC only so far. Half the fun of a Mullins game is not knowing what comes next, so "
                               "stay away from trailers and walkthroughs if you can. Expect some unsettling images."},
                    {"kind": "game", "title": "Mariachi Legends", "year": 2027, "creator": None,
                     "date": "2027-04-27",
                     "released": "PS5, Xbox Series X|S, Switch, PC · on Game Pass",
                     "why": "A side-scrolling Metroidvania from Halberd Studios, set in the Mexican town of Santa "
                            "Mascota. You play Pablo Cruz, a detective who has made a deal with Death herself and can "
                            "turn into La Sombra, on the trail of a man who has become immortal.",
                     "note": "The creative director, Miguel Hasson, has a one-line pitch for it: Alucard's suit in "
                             "Castlevania is \"like 90%\" of a mariachi suit already. Mariachi Legends takes the "
                             "castle-exploring structure of Symphony of the Night and moves it to a real place, "
                             "Mascota in Jalisco, where Hasson's mother comes from. The map exists by day and by "
                             "night, with a full moon as well, and some gates and enemies only appear at certain "
                             "times. You parry, collect tarot cards for new powers, and cook dishes from recipes "
                             "you find around town, which Hasson says can make you \"ridiculously "
                             "overpowered\" for a boss. It was due in 2026 and moved to April.",
                     "first": "Nothing. Castlevania: Symphony of the Night (1997) is the game it is built on, if you "
                              "have never played it.",
                     "caveat": "Metroidvanias mean a lot of walking back through places you have been, and a map "
                               "that changes between day and night doubles it. Halberd hasn't said how long it is or "
                               "what it costs."},
                    {"kind": "game", "title": "Haunted Paws", "year": 2027, "creator": None,
                     "date": "2027-05-01", "month_only": True,
                     "released": "PS5, Xbox Series X|S, Switch 2, Switch, PS4, PC · the day hasn't been set",
                     "why": "A cozy co-op horror game from LazyFlock in which two puppies sneak through a haunted "
                            "mansion to rescue their human, who has been kidnapped by the creatures living there.",
                     "note": "It is a haunted house seen from knee height, by two dogs who can dig, sniff and bark. You "
                             "make your own puppy, choosing the breed, the color of its fur and what it wears, and "
                             "each creature you beat gives up a piece of its past, so the house tells its story as you "
                             "go. It is built for two, and you can invite a friend to play for free, so one copy "
                             "covers a pair. Cozy horror is a small genre for people who like the creaking floors "
                             "more than the jump scares. A demo is out now on Switch 2 and Switch, which makes it the one game in this "
                             "guide you can try before you decide.",
                     "first": "Nothing. Play the demo on Switch first.",
                     "caveat": "Only the month is set. LazyFlock hasn't said how long it is, and a game designed for "
                               "two can feel thin if you play it on your own."},
                    {"kind": "game", "title": "Rustown", "year": 2027, "creator": None,
                     "date": "2027-06-30",
                     "released": "Xbox Series X|S, PC (Steam and Microsoft Store)",
                     "why": "A story-driven stealth adventure from Plotrick. Five years after a pandemic called the "
                            "idiot virus, you get a letter from your father, whom you thought was dead, and follow it "
                            "into Rustown, a slum where gangs of the infected and the uninfected fight over what is "
                            "left.",
                     "note": "Most games set after a pandemic turn the infected into monsters to be shot. In Rustown "
                             "they are people, living in their own part of town with their own gangs, and the game is "
                             "about slipping past both sides, following clues and piecing together the stories of the "
                             "people who live there. Plotrick showed it at the ID@Xbox showcase in October with a "
                             "trailer in English, Japanese and Korean, and its description calls it \"a story of life "
                             "and kindness that endure in a broken city.\" That and the trailer are most of what we "
                             "have to go on, so it is the riskiest pick in this guide. We included it because stealth "
                             "games that ask you to understand a place, not clear it out, are rare, and this one "
                             "comes at the end of June, when the spring rush is over.",
                     "caveat": "Xbox and PC only so far. There is no price, no length and no hands-on preview yet. "
                               "Wait for the reviews."},
                ],
            },
            {
                "format": "games",
                "id": "japan",
                "label": "From Japan",
                "heading": "Two from Japan: a fighting game and a picture book",
                "intro": [
                    "Both come from Japanese studios with a long record and a loyal following. One is an updated "
                    "version of a 2021 fighting game. The other came out in Japan in April 2026 and reaches the rest "
                    "of the world, translated, a year later.",
                ],
                "picks": [
                    {"kind": "game", "title": "Melty Blood: Twi-Lumina", "year": 2027, "creator": None,
                     "date": "2027-04-22",
                     "released": "PS5, PS4, Switch 2, Switch, Xbox One, PC · one or two players, online play",
                     "why": "An updated version of Melty Blood: Type Lumina (2021), the 2D fighting game set in the "
                            "world of Type-Moon's Tsukihime, with a reworked battle system, new characters and a new "
                            "story written by Kinoko Nasu.",
                     "note": "Type Lumina brought Melty Blood back in 2021 after more than a decade away, built on the "
                             "remake of Tsukihime that came out the same year, and it was a fast air-dashing fighter. "
                             "Twi-Lumina builds on it. Len, the cat familiar from the older "
                             "Melty Blood games, returns, and Aniplex has confirmed White Len as well. Nasu, who "
                             "created Tsukihime and the Fate series, has written a new story centered on Shiki Tohno "
                             "in Souya City. The developer, French-Bread, also makes Under Night In-Birth, so the "
                             "fighting is in experienced hands. If you play fighting games online, the date matters: "
                             "April 22 is a Thursday, and the first few weeks are when the most people are playing.",
                     "first": "Nothing for the fighting. For the story, the Tsukihime remake (A piece of blue glass "
                              "moon) introduces the characters, and it has been out in English since 2024.",
                     "caveat": "If you own Type Lumina, Aniplex hasn't said whether there is an upgrade or what it "
                               "costs. The Xbox version is for Xbox One, not Xbox Series, and the voices are Japanese "
                               "only."},
                    {"kind": "game", "title": "The Grimm Reapress and the Drearytale Monster", "year": 2026,
                     "creator": None,
                     "date": "2027-05-13",
                     "released": "Switch 2, Switch, PS5, PC · Japanese voices with English subtitles",
                     "why": "A storybook adventure from Nippon Ichi Software, drawn to look like a picture book. A "
                            "disease called Paper Mortis is turning people into picture books and picture books into "
                            "monsters, and Mono, whose sister has caught it, sets out through the Libratarium with "
                            "Mär, a monster bent on revenge.",
                     "note": "This is the third of Nippon Ichi's dark fairy tales, after The Liar Princess and the "
                             "Blind Prince (2018) and The Cruel King and the Great Hero (2022). Both looked like "
                             "children's books and told stories with real sadness in them: a wolf who blinded a "
                             "prince and has to lead him through a forest, and a dragon raising a human girl. The "
                             "Grimm Reapress keeps the hand-drawn style and gives you more to do. You solve puzzles, "
                             "fight bosses and dive into the storybooks themselves to learn the girls' stories. It came "
                             "out in Japan on April 30, 2026, on PS5, Switch 2 and Switch, and NIS America's English "
                             "release on May 13 adds a PC version.",
                     "caveat": "Japanese voices only. NIS America hasn't said how long it is or what it costs, and "
                               "the earlier games were slow, gentle ones, so look elsewhere for action."},
                ],
            },
            {
                "format": "games",
                "id": "strategy",
                "label": "Strategy",
                "heading": "Two strategy games, one going into early access and one coming out",
                "intro": [
                    "Both of these are being finished in public. Stronghold 4 opens its early access on Steam in "
                    "April, so you can buy it and play it while Firefly finishes it. Guild Saga has been in early "
                    "access since 2024 and reaches its full release, and PlayStation 5, in May.",
                ],
                "picks": [
                    {"kind": "game", "title": "Stronghold 4", "year": 2027, "creator": None,
                     "date": "2027-04-20",
                     "released": "PC (Steam) · early access, with the full release later",
                     "why": "Firefly Studios' castle-building strategy game, the first numbered Stronghold since "
                            "2011. It is set in medieval England years before the first game and follows Penryn of "
                            "Wethel, a shepherd who becomes a leader.",
                     "note": "Stronghold (2001) made castles fun to build and then to defend, with an economy behind "
                             "the walls: bread, ale, taxes and the mood of your peasants counted as much as the "
                             "archers on the battlements. Firefly has spent the last few years remaking its old games, "
                             "with Definitive Editions of Stronghold and Stronghold Crusader, and this is the new one, "
                             "built on Unreal Engine 5. Weather now changes things: snow slows the crops, and heavy "
                             "rain shortens your archers' range. Firefly's feature list has a 22-mission campaign, "
                             "sieges with moats and tunnelers, skirmishes against up to eight computer opponents and "
                             "a free build mode, and Ben Starr, Clive in Final Fantasy XVI, is in the cast. Early "
                             "access was due on December 7 and moved to April 20. Firefly called it \"a hard decision "
                             "for the team to make, but one which we think will lead to a better game.\"",
                     "first": "Nothing. If you have never played the series, Stronghold: Definitive Edition (2023) is "
                              "the original with modern controls, and the Steam demo of Stronghold 4 is free.",
                     "caveat": "This is early access, so it is unfinished: online multiplayer, the economic campaign "
                               "and co-op come later. PC only. If you want the finished game, wait for 1.0."},
                    {"kind": "game", "title": "Guild Saga: Vanished Worlds", "year": 2024, "creator": None,
                     "date": "2027-05-01", "month_only": True,
                     "released": "PS5 and PC (Steam) · the full release, after early access on PC since October 2024",
                     "why": "A turn-based tactics role-playing game from Ocelot Technologies, a small studio in "
                            "Ontario, in which you build a hero and a party and explore the islands of the Respite "
                            "Archipelago.",
                     "note": "The appeal is the way the skills combine. There are about 200 of them across ten "
                             "disciplines, and the ground and the weather matter: a Geomancer can summon a mandrake, "
                             "a Hydromancer can make it rain, and an Aeromancer can then send lightning through the "
                             "puddles. Chains like that were what people loved in Divinity: Original Sin 2, and they "
                             "are rare in a smaller game. Around the fights there is more of a role-playing game than "
                             "most tactics games bother with. You choose your hero's appearance, background and "
                             "talents, your companions have quests of their own, you can befriend or romance them, and "
                             "the side quests include a murder mystery and monster bounties. It has been on Steam in "
                             "early access since October 10, 2024, and its full release in May comes with the "
                             "PlayStation 5 version, which Ocelot's chief executive says \"feels like a "
                             "homecoming.\"",
                     "first": "Nothing.",
                     "caveat": "Only the month is set, and Ocelot says it will give the day closer to launch. Tactics "
                               "games with this many skills take patience to learn."},
                ],
            },
        ],
        "also": [
            ("Exodus (April 7).",
             "Archetype Entertainment's science fiction role-playing game, in which every long journey costs time back "
             "home. We wrote it up in our all-format spring guide."),
            ("Final Fantasy VII Revelation (April 8).",
             "The last part of the remake, on every current console and PC on the same day. Also in the spring "
             "guide."),
            ("God of War Laufey (May 20, PS5).",
             "Santa Monica Studio's game about Faye, Kratos's late wife, moved from February. Also in the spring "
             "guide."),
            ("Persona 4 Revival on Switch 2 (May 20).",
             "The Persona 4 remake from our winter guide reaches Nintendo's console three months after the other "
             "versions."),
            ("Kirby and the World Beyond (spring, Switch 2).",
             "Nintendo's second full 3D Kirby game, after Kirby and the Forgotten Land, and part of the series' 35th "
             "anniversary. Kirby cuts a hole in the sky and finds another world behind it."),
            ("Spyro: A Realm Beyond (spring).",
             "A new Spyro adventure from Toys for Bob, which remade the first three games in 2018, with true flight in "
             "place of gliding and Tom Kenny back as Spyro. On PS5, Xbox Series, Switch 2 and PC."),
            ("Mega Man: Dual Override (spring).",
             "Capcom's first new mainline Mega Man since Mega Man 11 in 2018, with Proto Man as a second playable "
             "character. On every current console, the last generation and PC."),
            ("Turok: Origins (spring).",
             "Saber Interactive's third-person dinosaur shooter, moved from autumn 2026, on PS5, Xbox Series, Switch 2 "
             "and PC."),
            ("The Expanse: Osiris Reborn (spring).",
             "Owlcat Games' role-playing game set in the world of The Expanse, aimed squarely at people who miss Mass "
             "Effect. On Game Pass from launch, as well as PS5 and PC."),
            ("Squadron 42 (April to June, PC).",
             "Cloud Imperium's single-player campaign set in the Star Citizen universe, now listed on Steam for the "
             "second quarter of 2027 after years of delays."),
            ("The Backworld (April to June, PC).",
             "A turn-based role-playing game with horror in it, from Numor Games, with three modes running from a "
             "relaxed story mode to permanent death."),
        ],
        "plan_heading": "A plan for the spring",
        "plan": [
            "Most people will spend the first half of April on Exodus or Final Fantasy VII Revelation, and the games "
            "in this guide come in behind them. Stronghold 4's early access opens on Tuesday the 20th and Melty Blood "
            "follows on Thursday the 22nd. Pony Island 2 and Mariachi Legends both arrive on the 27th, and if you can "
            "only fit in one, choose by mood: Pony Island 2 for something strange you will want to talk about, "
            "Mariachi Legends for something to explore for weeks.",
            "May is lighter. The Grimm Reapress comes out on the 13th and God of War Laufey on the 20th, and Haunted "
            "Paws and Guild Saga are due some time in the month. Haunted Paws has a demo on Switch now, which is the "
            "easiest way to decide whether to save an evening for it with a friend.",
            "June has only Rustown so far, on the 30th. The big publishers hold their summer showcases in early June "
            "every year, and that is when the spring games still without a month will either get a date or quietly "
            "move to the autumn. We will update this page as they do, and the date at the top says when we last "
            "checked.",
        ],
        "method": [
            "Prepared by OmniTrackr with AI assistance and reviewed by the site owner before publishing. None of these "
            "games had come out when we wrote about them, so this is a guide to what we think is worth trying, not a "
            "set of reviews. We worked from the publishers' own announcements and the coverage listed below, checked "
            "each date against a second source where we could, and kept games with at least a month. Games with only "
            "a season or a quarter are listed under Also on the calendar.",
            "Game dates move more than film or TV dates, and two of the games here have moved already: Mariachi "
            "Legends from 2026, and Stronghold 4's early access from December 7. Haunted Paws and Guild Saga have a "
            "month but no day, and we list them by the month. Platforms are the ones confirmed so far. None of the "
            "announcements we read gave a price, so we have left prices out.",
        ],
        "related": [
            ("Spring 2027 releases", "/new-releases/spring-2027"),
            ("Winter 2027 games", "/new-releases/winter-2027-games"),
            ("The best games of 2026", "/best-of/2026/games"),
            ("The Essential 100 games", "/essentials/games"),
            ("How to track games on OmniTrackr", "/game-tracker"),
        ],
        "sources": [
            ("Gematsu: Pony Island 2: Panda Circus launches April 27, 2027", "https://www.gematsu.com/2026/08/pony-island-2-panda-circus-launches-april-27-2027"),
            ("Game Informer: Pony Island 2: Panda Circus arrives in April 2027", "https://gameinformer.com/gamescom-2026/2026/08/25/pony-island-2-panda-circus-arrives-in-april-2027"),
            ("Gematsu: Mariachi Legends delayed to April 27, 2027", "https://www.gematsu.com/2026/08/mariachi-legends-delayed-to-april-27-2027"),
            ("GamesRadar+: Mariachi Legends and Alucard's suit", "https://www.gamesradar.com/games/action/the-metroidvania-ive-wanted-for-3-years-is-finally-out-next-year-and-it-looks-like-mexican-castlevania-alucards-suit-is-like-90-percent-of-a-mariachi-suit-already/"),
            ("Gematsu: Haunted Paws launches in May 2027", "https://www.gematsu.com/2026/10/haunted-paws-launches-in-may-2027"),
            ("Gematsu: Rustown launches June 30, 2027", "https://www.gematsu.com/2026/10/rustown-launches-june-30-2027-for-xbox-series-pc"),
            ("Gematsu: Melty Blood: Twi-Lumina launches April 22, 2027", "https://gematsu.com/2026/09/melty-blood-twi-lumina-launches-april-22-2027"),
            ("Games Press: Aniplex announces Melty Blood: Twi-Lumina", "https://www.gamespress.com/New-Entry-in-MELTY-BLOOD-Series-2D-Fighter-MELTY-BLOOD-TWI-LUMINA-To-B"),
            ("Gematsu: The Grimm Reapress and the Drearytale Monster is coming west", "https://www.gematsu.com/2026/09/the-grimm-reapress-and-the-drearytale-monster-coming-west-in-2027-for-ps5-switch-2-switch-and-pc"),
            ("The Outerhaven: The Grimm Reapress gets its release date", "https://www.theouterhaven.net/the-grimm-reapress-and-the-drearytale-monster-gets-its-release-date/"),
            ("Worthplaying: Stronghold 4 early access moves to April 2027", "https://worthplaying.com/article/2026/11/3/news/151343-stronghold-4-needs-more-time-steam-early-access-delayed-until-april-2027/"),
            ("Gematsu: Stronghold 4 announced for PC", "https://www.gematsu.com/2026/06/stronghold-4-announced-for-pc"),
            ("Gematsu: Guild Saga: Vanished Worlds comes to PS5 in May 2027", "https://www.gematsu.com/2026/11/strategy-rpg-guild-saga-vanished-worlds-coming-to-ps5-in-may-2027"),
            ("Gematsu: Persona 4 Revival comes to Switch 2 on May 20, 2027", "https://www.gematsu.com/2026/09/persona-4-revival-coming-to-switch-2-on-may-20-2027"),
            ("VGC: Kirby and the World Beyond is coming in spring 2027", "https://www.videogameschronicle.com/news/kirby-and-the-world-beyond-is-an-all-new-kirby-3d-adventure-coming-in-spring-2027/"),
            ("Gematsu: Spyro: A Realm Beyond announced", "https://www.gematsu.com/2026/06/spyro-a-realm-beyond-announced-for-ps5-xbox-series-switch-2-and-pc"),
            ("Gematsu: Mega Man: Dual Override launches in spring 2027", "https://www.gematsu.com/2026/09/mega-man-dual-override-launches-in-spring-2027"),
            ("Gematsu: Turok: Origins delayed to spring 2027", "https://www.gematsu.com/2026/08/turok-origins-delayed-to-spring-2027"),
            ("GamesRadar+: The Expanse: Osiris Reborn gets a spring 2027 window", "https://www.gamesradar.com/games/rpg/mass-effect-inspired-sci-fi-rpg-the-expanse-osiris-reborn-gets-a-spring-2027-release-window-and-it-has-a-closed-beta-coming-next-month/"),
            ("DLCompare: Squadron 42 gets a Q2 2027 window", "https://www.dlcompare.com/gaming-news/squadron-42-returns-with-a-new-trailer-and-a-q2-2027-release-window"),
            ("Gematsu: The Backworld launches in Q2 2027", "https://www.gematsu.com/2026/11/the-backworld-launches-in-q2-2027"),
            ("Shacknews: 2027 video game release dates", "https://www.shacknews.com/article/150148/2027-video-games"),
            ("Game Informer: 2027 video game release schedule", "https://gameinformer.com/2027"),
            ("Wikipedia: list of video games released in 2027", "https://en.wikipedia.org/wiki/List_of_video_games_released_in_2027"),
        ],
    },
}
