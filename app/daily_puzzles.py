"""The OmniTrackr Daily puzzle bank, written by the editors.

One entry per day, in order, starting on daily.EPOCH. Each puzzle has six clues
that go from vague to obvious; a clue never contains a word of the answer, and
tests check that. The note is shown once the puzzle is over and on its archive
page, so it is written to be worth reading on its own.

When every puzzle has run, the game starts over from #1 on its own (see
daily.bank_index). To add puzzles, append to PUZZLES. Never reorder or edit the answer of an entry
that has already been published: puzzle numbers in people's shared results and
the archive pages depend on the order.
"""
from __future__ import annotations


def _p(kind, title, year, creator, aliases, clues, note):
    return {"kind": kind, "title": title, "year": year, "creator": creator,
            "aliases": tuple(aliases), "clues": tuple(clues), "note": note}


PUZZLES = (
    _p("movie", "Interstellar", 2014, "Christopher Nolan", [], [
        "A science fiction film from 2014 that runs for nearly three hours.",
        "Its director wrote the script with his brother and is known for mind-bending blockbusters.",
        "A widowed farmer and former test pilot leaves his two children on an Earth choked by dust storms and crop blight.",
        "One hour on a water-covered planet near a black hole costs the crew 23 years back home.",
        "Hans Zimmer's score is built around a church pipe organ.",
        "Matthew McConaughey plays Cooper, who travels through a wormhole near Saturn.",
    ], "Christopher Nolan built this space epic on the physicist Kip Thorne's work on black holes, and the effects team's "
       "renders of Gargantua were detailed enough to be written up in a scientific paper. Under the science it is a story "
       "about a father and daughter and the time they cannot get back, which is why the bookshelf scene hits as hard as the "
       "docking sequence. Watch it on the biggest screen you can find, with the volume up."),
    _p("anime", "Jujutsu Kaisen", 2020, "MAPPA", ["jjk"], [
        "An anime series that began in 2020, adapted from a manga that ran in Weekly Shōnen Jump.",
        "It is animated by MAPPA, the studio that also made the final season of Attack on Titan.",
        "A high school student with unusual strength joins a secret school that trains people to fight curses.",
        "To save his friends, he swallows a rotting finger and becomes the host of a powerful demon.",
        "His blindfolded teacher is said to be the strongest sorcerer alive.",
        "Yuji Itadori, Megumi Fushiguro and Nobara Kugisaki are taught by Satoru Gojo.",
    ], "Gege Akutami's series became one of the defining shōnen anime of the 2020s thanks to MAPPA's fight choreography, "
       "which treats every battle like a set piece. It is a darker show than its school setting suggests, and the second "
       "season's Shibuya arc is where it shows how far it is willing to go. Start with the first season and the prequel "
       "film if you want the full story."),
    _p("game", "The Legend of Zelda: Breath of the Wild", 2017, "Nintendo",
       ["breath of the wild", "botw", "zelda breath of the wild"], [
        "An open-world video game released in 2017, on the same day as the console it launched with.",
        "It was made by Nintendo and also came out on the Wii U, the console it was first announced for.",
        "You wake up alone in a chamber with no memory after sleeping for 100 years.",
        "Weapons break as you use them, and almost any cliff can be climbed if your stamina holds out.",
        "More than a hundred shrines hide small puzzles, and each one rewards you with a Spirit Orb.",
        "The hero must defeat Calamity Ganon, which has wrapped itself around Hyrule Castle for a century.",
    ], "Breath of the Wild threw out a series formula that was decades old and replaced it with a simple promise: if you "
       "can see it, you can go there. Physics and chemistry systems let players solve problems in ways the designers never "
       "planned, which is why people still share new tricks years later. It is a game that rewards curiosity more than skill."),
    _p("tv", "Stranger Things", 2016, "The Duffer Brothers", [], [
        "A TV series that premiered in 2016 and is set in the 1980s.",
        "It was created by twin brothers for a streaming service.",
        "A boy vanishes on his way home after a long night of Dungeons & Dragons with his friends.",
        "A girl with a shaved head and psychokinetic powers escapes from a government laboratory.",
        "Christmas lights strung across a living-room wall become a way to talk to someone trapped in another dimension.",
        "Eleven, Mike, Dustin and Lucas face the Upside Down in Hawkins, Indiana.",
    ], "The Duffer Brothers built their show out of the films they grew up on, from Spielberg's suburbs to John Carpenter's "
       "synth scores, and found an audience that had never seen those films too. The first season is a tight eight-episode "
       "mystery, and later seasons grow into a bigger ensemble adventure. It is one of the titles OmniTrackr members track "
       "most, so it is a good one to compare notes on."),
    _p("book", "Dune", 1965, "Frank Herbert", [], [
        "A science fiction novel first published as a book in 1965.",
        "It won the first Nebula Award for Best Novel and shared that year's Hugo Award.",
        "A noble family takes over a desert planet that is the only source of the most valuable substance in the universe.",
        "Its young hero learns the ways of the Fremen and rides giant sandworms.",
        "The spice melange extends life and makes travel between the stars possible.",
        "Paul Atreides becomes Muad'Dib on the planet Arrakis.",
    ], "Frank Herbert spent years researching desert ecology and religion before writing this, and it shows: the planet "
       "itself is the most memorable character. It reads as a warning about charismatic leaders as much as an adventure, a "
       "point the sequels make even more directly. Denis Villeneuve's two films are a strong companion, but the novel's "
       "inner voices and politics are worth the slower start."),
    _p("album", "1989", 2014, "Taylor Swift", ["1989 taylors version"], [
        "A pop album released in 2014.",
        "It won the Grammy for Album of the Year, its singer's second win in that category.",
        "Max Martin and Shellback produced much of it, alongside Jack Antonoff and Ryan Tedder.",
        "It was re-recorded and re-released in 2023 with five previously unreleased songs from the vault.",
        "The album is named after the year its singer was born.",
        "Taylor Swift's singles from it include 'Shake It Off', 'Blank Space' and 'Style'.",
    ], "This was the record where Taylor Swift stopped hedging between country and pop and made a fully synth-driven pop "
       "album, inspired by the music of the late 1980s. Almost every track was a candidate for a single, which is rare, and "
       "'Out of the Woods' and 'Clean' reward listeners who go past the hits. The 2023 re-recording lets you compare the "
       "original with an older singer's take."),
    _p("movie", "Spirited Away", 2001, "Hayao Miyazaki", ["sen to chihiro no kamikakushi"], [
        "An animated film released in Japan in 2001.",
        "It won the Academy Award for Best Animated Feature and was for years the highest-grossing film ever in Japan.",
        "A sulky ten-year-old girl gets lost while moving to a new town with her parents.",
        "Her parents turn into pigs after eating food left out at an abandoned theme park.",
        "She takes a job at a bathhouse for spirits, run by a witch who steals people's names.",
        "Chihiro is renamed Sen and befriends Haku and the masked No-Face in this Studio Ghibli film.",
    ], "Hayao Miyazaki made this for the ten-year-old daughters of his friends, and it treats a child's growing up with total "
       "seriousness. The bathhouse is packed with small, strange details that reward a second viewing, and the quiet train "
       "ride across the flooded sea is one of the most admired scenes in animation. If you have only seen it dubbed, try "
       "the subtitled version too."),
    _p("game", "Minecraft", 2011, "Mojang", [], [
        "A video game that left early access in 2011 and became the best-selling game of all time.",
        "It was created by a Swedish developer known as Notch, and Microsoft bought his studio in 2014.",
        "Its worlds are built almost entirely from cubes and go on further than anyone could ever explore.",
        "When night falls, zombies and skeletons come out, so your first job is to build a shelter.",
        "A green, silent creature walks up behind you, hisses and explodes.",
        "Players punch trees, dig for diamonds and travel to the Nether and the End to fight the Ender Dragon.",
    ], "Few games have been as many things to as many people: a survival game, a building toy, a teaching tool and a place "
       "where friends hang out. Its blocky look made it easy to run on almost anything, and its openness turned players into "
       "creators. With A Minecraft Movie also on many OmniTrackr members' lists, it has crossed from games into film too."),
    _p("tv", "Breaking Bad", 2008, "Vince Gilligan", [], [
        "A crime drama series that first aired in 2008 and ran for five seasons.",
        "Its creator previously wrote for The X-Files.",
        "A chemistry teacher is diagnosed with terminal lung cancer around his 50th birthday.",
        "He partners with a former student to cook methamphetamine in an old RV in the New Mexico desert.",
        "His brother-in-law is an agent with the DEA.",
        "Walter White takes the name Heisenberg, with Jesse Pinkman at his side in Albuquerque.",
    ], "Vince Gilligan pitched the show as turning Mr. Chips into Scarface, and it commits to that slow change over five "
       "seasons. It is often held up as one of the best-plotted dramas on TV, with small choices in early episodes paying off "
       "much later. The prequel Better Call Saul and the film El Camino carry the same world further."),
    _p("anime", "Attack on Titan", 2013, "Wit Studio", ["shingeki no kyojin", "aot"], [
        "An anime series that began in 2013 and ended ten years later.",
        "Wit Studio animated the first three seasons, and MAPPA took over for the last one.",
        "What is left of humanity lives behind three huge concentric walls.",
        "A boy watches his mother get eaten after a colossal giant kicks a hole in the outer wall.",
        "Soldiers swing between buildings with omni-directional mobility gear, aiming for the nape of the neck.",
        "Eren Yeager, Mikasa Ackerman and Armin Arlert join the Survey Corps.",
    ], "Hajime Isayama's story starts as a monster survival tale and turns into something much harder to sum up, a long "
       "argument about freedom, war and cycles of revenge. Few series change genre this completely and keep their audience. "
       "It is best watched in order without spoilers, because the reveals in the third season change how you see everything "
       "before them."),
    _p("book", "The Hobbit", 1937, "J. R. R. Tolkien", ["there and back again"], [
        "A fantasy novel first published in 1937.",
        "Its author was an Oxford professor of Anglo-Saxon who also invented whole languages.",
        "A comfortable homebody is talked into an adventure by a wizard and thirteen dwarves.",
        "In the dark under the Misty Mountains, he wins a riddle contest and pockets a magic ring.",
        "The quest ends at the Lonely Mountain, where a dragon sleeps on a heap of treasure.",
        "Bilbo Baggins travels with Gandalf to face the dragon Smaug.",
    ], "Tolkien wrote it for his own children, and it reads like a story told aloud: funny, cosy and then suddenly "
       "frightening. It is shorter and lighter than The Lord of the Rings, which makes it a good first step into "
       "Middle-earth for readers of any age. The riddle game with Gollum is still one of fantasy's great scenes."),
    _p("movie", "Parasite", 2019, "Bong Joon Ho", ["gisaengchung"], [
        "A South Korean film from 2019 that mixes dark comedy and thriller.",
        "It was the first film not in English to win the Academy Award for Best Picture.",
        "A poor family in a semi-basement apartment cons its way into working for a rich household, one job at a time.",
        "A torrential rainstorm floods one family's home while the other worries their camping trip will be cancelled.",
        "A secret bunker is hidden beneath the wealthy family's modern house.",
        "Directed by Bong Joon Ho, it follows the Kim family and the Park family.",
    ], "Bong Joon Ho's film works as a heist comedy for its first hour and then turns, without warning, into something far "
       "sharper about class. The house was built as a set so that every staircase could tell you who is above whom. Go in "
       "knowing as little as possible, then watch it again for how carefully the first half sets up the second."),
    _p("game", "Hades", 2020, "Supergiant Games", [], [
        "An action roguelike game that left early access in 2020.",
        "It was made by the independent studio behind Bastion, Transistor and Pyre.",
        "Every time you die, you return home and try your escape again, a little stronger.",
        "Gods on Mount Olympus send you blessings, called boons, to help along the way.",
        "You fight through Tartarus, Asphodel and Elysium, and the final boss is your own father.",
        "Zagreus, a prince of the Underworld, is trying to escape his father's house.",
    ], "Supergiant solved roguelikes' biggest problem, that dying feels like wasted time, by making every death move the story "
       "forward. Characters remember what happened on your last run, and there are thousands of lines of voiced dialogue "
       "to unlock. It is a great first roguelike, and it has a God Mode for anyone who mainly wants the story."),
    _p("tv", "The Office", 2005, "Greg Daniels", ["the office us", "office us"], [
        "A comedy series that premiered in 2005 and ran for nine seasons.",
        "It is an American remake of a British show created by Ricky Gervais and Stephen Merchant.",
        "A documentary crew films the employees of a paper company's regional branch.",
        "One prank sets a co-worker's stapler in a mould of jelly.",
        "The branch is in Scranton, Pennsylvania, and the company is Dunder Mifflin.",
        "Michael Scott, Dwight Schrute, Jim Halpert and Pam Beesly.",
    ], "The first season stays close to the British original, but the show found its own warmth from the second season on, "
       "turning a cringe comedy into a workplace family. The slow romance between Jim and Pam is a big reason it is still one "
       "of the most rewatched comedies on streaming. If season one does not grab you, skip to season two."),
    _p("anime", "Frieren: Beyond Journey's End", 2023, "Madhouse",
       ["frieren", "sousou no frieren", "frieren beyond journeys end"], [
        "An anime series that began airing in 2023.",
        "It is animated by Madhouse and topped MyAnimeList's all-time score ranking soon after it aired.",
        "It begins just after a party of heroes has already defeated the Demon King.",
        "An elf who will live for thousands of years realises she never really got to know her human companions.",
        "She sets out on a long trip and collects odd everyday spells, like one that makes a field of flowers bloom.",
        "The elf mage travels with her apprentice Fern and the warrior Stark, remembering the hero Himmel.",
    ], "Most fantasy stories end with the hero's victory; this one starts there and asks what a long life is for. It is "
       "quiet, funny and often moving, and the slow pace is the point. When the action does come, in the mage exam arc, "
       "Madhouse makes it count. It is a good pick for viewers who think anime is all shouting."),
    _p("movie", "Spider-Man: Into the Spider-Verse", 2018, "Bob Persichetti, Peter Ramsey and Rodney Rothman",
       ["into the spider verse", "spider verse", "spiderman into the spiderverse"], [
        "An animated film released in 2018.",
        "It won the Academy Award for Best Animated Feature and mixes comic-book printing styles with 3D animation.",
        "A Brooklyn teenager is bitten by something strange during a night out painting graffiti.",
        "Versions of the same hero from other dimensions, including a cartoon pig and a black-and-white detective, crash into his world.",
        "The villain Kingpin builds a particle collider to reach versions of his dead wife and son.",
        "Miles Morales learns the job from an older, tired Peter B. Parker and from Gwen Stacy.",
    ], "Sony's animators invented new techniques to make every frame look like a printed comic, from halftone dots to "
       "off-register colour, and the style changed what studios thought big animated films could look like. The story about "
       "a kid growing into a role everyone already has expectations for is just as strong. Across the Spider-Verse continues it."),
    _p("game", "Elden Ring", 2022, "FromSoftware", [], [
        "An open-world action role-playing game released in 2022.",
        "It was made by the studio famous for Dark Souls and its punishing difficulty.",
        "The author of A Song of Ice and Fire helped write the history of its world.",
        "You play one of the Tarnished, guided by a maiden named Melina, on a spectral horse called Torrent.",
        "Malenia, Blade of Miquella, is one of its most notoriously difficult bosses.",
        "You gather Great Runes from demigods across the Lands Between.",
    ], "Hidetaka Miyazaki's studio took the tough, cryptic design of its earlier games and opened it up into a huge world, "
       "so when a boss is too hard you can simply ride off and come back stronger. That one change made it the studio's "
       "most popular game by far. The Shadow of the Erdtree expansion is as big as many full games."),
    _p("tv", "The Last of Us", 2023, "Craig Mazin and Neil Druckmann", [], [
        "A drama series that premiered in 2023, based on a video game.",
        "It was created by the writer of Chernobyl together with the game's own writer and director.",
        "A fungal infection has turned most of humanity into violent creatures.",
        "A hardened smuggler is hired to escort a 14-year-old girl across a ruined America.",
        "Its third episode is a love story between two survivors, Bill and Frank.",
        "Pedro Pascal plays Joel and Bella Ramsey plays Ellie.",
    ], "Game adaptations had a poor track record until this one, which kept the story's heart and changed details where TV "
       "needed something different. The detour of episode three, which barely features the leads, became the most talked "
       "about hour of the season. Players and newcomers tend to like it for different reasons, which makes it a good one to "
       "watch together."),
    _p("album", "Abbey Road", 1969, "The Beatles", [], [
        "A rock album released in 1969.",
        "It was the last album its band recorded together, although another of their albums was released after it.",
        "Side two ends with a long medley of song fragments stitched together.",
        "Its cover shows the four band members walking across a zebra crossing in north-west London.",
        "George Harrison wrote two of its best-known songs, 'Something' and 'Here Comes the Sun'.",
        "The Beatles' album that opens with 'Come Together'.",
    ], "Recorded while the band was coming apart, it is one of their most polished records, with the medley on side two "
       "showing what they could still do together. Its cover is probably the most copied album photo ever, and the crossing "
       "outside the studio still has tourists on it every day. Listen to side two in one go."),
    _p("anime", "One Piece", 1999, "Toei Animation", [], [
        "An anime series that began in 1999 and is still running, with more than a thousand episodes.",
        "It adapts Eiichiro Oda's manga, which holds the record for most copies published by a single author.",
        "A boy who ate a cursed fruit has a body made of rubber.",
        "He sets sail to find the legendary treasure left behind by the late King of the Pirates.",
        "His crew includes a swordsman who fights with three swords and a reindeer who is a doctor.",
        "Monkey D. Luffy and the Straw Hat Pirates search for Gol D. Roger's treasure.",
    ], "Its length scares people off, but fans will tell you the Arlong Park arc, about 40 episodes in, is where it hooks "
       "you. Eiichiro Oda plans his world decades ahead, and small details pay off hundreds of chapters later. The live "
       "action Netflix series is a quicker way into the early story if a thousand episodes feels like too much."),
    _p("movie", "Everything Everywhere All at Once", 2022, "Daniel Kwan and Daniel Scheinert", ["eeaao"], [
        "A film from 2022 that mixes science fiction, martial arts and family drama.",
        "It was directed by a duo known as Daniels and won seven Academy Awards, including Best Picture.",
        "A laundromat owner is being audited by the tax office when her life starts splitting into other universes.",
        "In one universe, everyone has hot dogs for fingers.",
        "Her daughter's alternate self has put all of existence on a bagel.",
        "Michelle Yeoh plays Evelyn Wang, opposite Ke Huy Quan and Jamie Lee Curtis.",
    ], "Underneath the googly eyes and multiverse chaos is a very simple story about a mother and daughter trying to understand "
       "each other. It made Michelle Yeoh the first Asian woman to win the Oscar for Best Actress and brought Ke Huy Quan back "
       "to acting. It is loud, silly and exhausting in the best way."),
    _p("game", "Stardew Valley", 2016, "ConcernedApe", [], [
        "A farming and life simulation game released in 2016.",
        "One person, Eric Barone, made almost all of it: the code, the art and the music.",
        "You quit a dull office job and move to your late grandfather's old farm.",
        "A greedy corporation called Joja is trying to take over the town.",
        "Restoring the abandoned Community Center by completing bundles is a long-term goal.",
        "Grow parsnips, fish, mine for ore and get to know the residents of Pelican Town.",
    ], "Eric Barone spent more than four years making it alone, and it has gone on to sell tens of millions of copies. It is "
       "a calm game about routines, seasons and small kindnesses, and it plays just as well with friends in co-op. Free "
       "updates have kept adding to it long after release."),
    _p("tv", "Avatar: The Last Airbender", 2005, "Michael Dante DiMartino and Bryan Konietzko", ["atla"], [
        "An animated series that first aired in 2005 and ran for three seasons, called Books.",
        "It aired on Nickelodeon and was created by Michael Dante DiMartino and Bryan Konietzko.",
        "The world is divided into four nations, each tied to a classical element.",
        "A boy frozen in an iceberg for a hundred years is found by two siblings from the Southern Water Tribe.",
        "A banished prince with a scar hunts him to win back his honour.",
        "Aang must master water, earth and fire to stop Fire Lord Ozai.",
    ], "Made as a kids' show, it is one of the best-loved fantasy stories on television for viewers of any age, with a "
       "redemption arc for Zuko that is still the standard others are measured against. Martial arts styles inspired each "
       "element's bending. The Legend of Korra follows the next Avatar."),
    _p("book", "Nineteen Eighty-Four", 1949, "George Orwell", ["1984", "nineteen eighty four"], [
        "A dystopian novel published in 1949.",
        "Its author also wrote a short allegory in which farm animals overthrow their owner.",
        "Posters everywhere tell citizens that they are being watched.",
        "The government's language, Newspeak, is designed to make disloyal thoughts impossible to put into words.",
        "The worst punishment of all waits in Room 101.",
        "Winston Smith rewrites history at the Ministry of Truth, under Big Brother.",
    ], "George Orwell's last novel gave everyday English words like doublethink and thoughtcrime, and 'Big Brother' now means "
       "something far from its original sense. It is bleaker than many readers expect, and the appendix on Newspeak is worth "
       "reading for how it changes the ending. Animal Farm is the shorter companion."),
    _p("movie", "Get Out", 2017, "Jordan Peele", [], [
        "A horror film from 2017.",
        "It was the directing debut of a comedian, who won the Academy Award for Best Original Screenplay for it.",
        "A young Black photographer visits his white girlfriend's parents for the weekend.",
        "The family's groundskeeper and housekeeper act strangely calm.",
        "A spoon stirring a teacup is enough to send him into the Sunken Place.",
        "Directed by Jordan Peele and starring Daniel Kaluuya as Chris.",
    ], "Jordan Peele used the shape of a meet-the-parents comedy to make a horror film about race in supposedly liberal "
       "America, and the details planted in the first act all come back. It made a little-known cast into stars and started "
       "a wave of 'social thrillers'. Rewatching it once you know the twist is a different, equally good film."),
    _p("anime", "Demon Slayer: Kimetsu no Yaiba", 2019, "ufotable", ["demon slayer", "kimetsu no yaiba"], [
        "An anime series that began in 2019, set in Japan's Taishō era.",
        "It is animated by ufotable, and its 2020 film became the highest-grossing film ever in Japan.",
        "A boy who sells charcoal comes home to find his family slaughtered.",
        "His surviving younger sister has been turned into a man-eating creature and travels in a wooden box on his back.",
        "He learns Water Breathing sword techniques to join a secret corps of swordsmen.",
        "Tanjiro Kamado protects his sister Nezuko and fights alongside Zenitsu and Inosuke.",
    ], "The story is straightforward shōnen, but ufotable's animation, especially the ukiyo-e styled water effects, made it a "
       "phenomenon. Episode 19 of the first season is the one fans point to. The Mugen Train film carries straight on from "
       "season one, so watch it before season two."),
    _p("game", "Portal", 2007, "Valve", [], [
        "A first-person puzzle game released in 2007.",
        "It first came out as part of Valve's Orange Box collection.",
        "A test subject is guided through a series of chambers by a polite, increasingly sinister computer.",
        "You are promised cake as a reward.",
        "Your only tool is the Aperture Science Handheld device.",
        "Chell faces GLaDOS, and the credits roll to the song 'Still Alive'.",
    ], "Valve hired the student team behind a puzzle game called Narbacular Drop and the result is a game you can finish in an "
       "afternoon and remember for years. Its dark humour comes almost entirely from one voice. Portal 2 builds it into a "
       "longer story with co-op, and both still hold up."),
    _p("tv", "Game of Thrones", 2011, "David Benioff and D. B. Weiss", ["got"], [
        "A fantasy drama series that ran from 2011 to 2019 over eight seasons.",
        "It was made for HBO and filmed largely in Northern Ireland, Croatia and Iceland.",
        "Noble houses fight over who sits on a seat made from melted swords.",
        "A wedding feast becomes a massacre in the ninth episode of season three.",
        "An exiled princess walks into a funeral pyre and comes out with three baby dragons.",
        "It is based on George R. R. Martin's novels, with Jon Snow, Daenerys Targaryen and Tyrion Lannister.",
    ], "For several years it was the show everyone talked about the morning after, partly because it was willing to kill "
       "anyone. The early seasons, closest to George R. R. Martin's books, are the most admired, and the ending is still argued "
       "about. House of the Dragon is set nearly two centuries earlier."),
    _p("movie", "Toy Story", 1995, "John Lasseter", [], [
        "An animated film from 1995.",
        "It was the first feature film made entirely with computer animation.",
        "A pull-string cowboy worries he is being replaced as a child's favourite.",
        "The new arrival is convinced he is a real space ranger on a mission.",
        "They end up trapped in the house of Sid, a neighbour who pulls things apart.",
        "Woody and Buzz Lightyear, voiced by Tom Hanks and Tim Allen, in Pixar's first feature.",
    ], "Pixar's first feature is remembered for its technology, but it lasts because of its script: a buddy comedy about "
       "jealousy and growing up that works for adults as well as children. The animation looks simple now, which is why the "
       "team chose plastic toys as their subject in the first place. The sequels are unusually strong too."),
    _p("album", "Thriller", 1982, "Michael Jackson", [], [
        "A pop album released in 1982, often called the best-selling album of all time.",
        "It was produced by Quincy Jones and won a record eight Grammy Awards in one night.",
        "Seven of its nine songs were released as singles, and all of them reached the US top ten.",
        "Its title track came with a long music video directed by John Landis.",
        "Vincent Price performs a spoken-word section on the title song.",
        "Michael Jackson's album with 'Billie Jean' and 'Beat It'.",
    ], "Quincy Jones and Michael Jackson set out to make an album with no filler, and they pulled it off across pop, funk, "
       "rock and ballads. Its videos helped break MTV's colour line and turned music videos into short films. Forty years "
       "on, 'Billie Jean' is still the one DJs reach for."),
    _p("anime", "Fullmetal Alchemist: Brotherhood", 2009, "Bones",
       ["fullmetal alchemist", "fmab", "full metal alchemist brotherhood"], [
        "An anime series from 2009, the second adaptation of its manga.",
        "It was animated by Bones and follows the manga closely all the way to its ending.",
        "Two brothers try to bring their dead mother back to life, and it goes horribly wrong.",
        "The older brother loses an arm and a leg; the younger one's soul is bound to a suit of armour.",
        "The law of equivalent exchange says nothing can be gained without losing something of equal value.",
        "Edward and Alphonse Elric hunt for the Philosopher's Stone.",
    ], "Hiromu Arakawa's story is often recommended as the perfect first long anime: it has a clear goal, a real ending and "
       "no filler. It mixes comedy, war and a well-built magic system without losing track of the two brothers at its centre. "
       "The 2003 series is a different story from the same start."),
    _p("game", "Red Dead Redemption 2", 2018, "Rockstar Games", ["rdr2", "red dead 2", "red dead redemption ii"], [
        "An open-world western game released in 2018.",
        "Its studio also makes the Grand Theft Auto series.",
        "It is a prequel, set in 1899 as the age of outlaws is coming to an end.",
        "Your gang flees after a ferry robbery in the town of Blackwater goes wrong.",
        "You have to brush and feed your horse, and your hair and beard grow over time.",
        "Arthur Morgan rides with Dutch van der Linde's gang.",
    ], "Rockstar built a world so detailed that some players spend more time hunting, fishing and riding than following the "
       "story, which is itself one of the best in games. Its slow pace is deliberate. Arthur Morgan's arc is the reason many "
       "players call it their favourite, and the first game picks up where this one leaves off."),
    _p("movie", "Jurassic Park", 1993, "Steven Spielberg", [], [
        "An adventure film from 1993, based on a best-selling novel.",
        "Its director also made Jaws and E.T.",
        "A billionaire invites scientists to approve his new island attraction before it opens to the public.",
        "Ancient DNA was recovered from mosquitoes preserved in amber.",
        "A glass of water ripples as something huge approaches.",
        "Alan Grant, Ellie Sattler and Ian Malcolm face a T. rex and velociraptors on Isla Nublar.",
    ], "Its mix of computer-generated and full-size animatronic dinosaurs still looks convincing more than thirty years "
       "later, because Spielberg kept the effects in the shadows and the rain. John Williams' theme does the rest. It is the "
       "rare blockbuster with something to say, about scientists who ask whether they can and never whether they should."),
    _p("tv", "Squid Game", 2021, "Hwang Dong-hyuk", [], [
        "A South Korean thriller series that premiered in 2021.",
        "Within weeks of its release, it became one of Netflix's most-watched series ever.",
        "Hundreds of people deep in debt agree to play children's games for a huge cash prize.",
        "Losing a round means being killed on the spot.",
        "A giant doll sings during Red Light, Green Light, and players carve shapes out of honeycomb candy.",
        "Player 456, Seong Gi-hun, competes while guards in pink jumpsuits watch.",
    ], "Hwang Dong-hyuk spent around a decade trying to get it made, and its story about debt and desperation hit a nerve "
       "around the world. The bright, toy-box sets make the violence more shocking. Watch it with subtitles rather than the "
       "dub if you can; the performances carry a lot."),
    _p("book", "To Kill a Mockingbird", 1960, "Harper Lee", [], [
        "A novel published in 1960 and set in the American South during the Great Depression.",
        "It won the Pulitzer Prize for Fiction, and its author published only one other novel, decades later.",
        "A girl called Scout narrates her childhood in a small Alabama town.",
        "Her father, a lawyer, defends a Black man falsely accused of raping a white woman.",
        "The children are fascinated by a reclusive neighbour named Boo Radley.",
        "Atticus Finch defends Tom Robinson in Maycomb.",
    ], "Told through a child's eyes, it lets readers see injustice the way Scout does, slowly and then all at once. It is "
       "taught in schools so often that many people only remember the trial, but the story of growing up around it is just as "
       "rich. The 1962 film with Gregory Peck is a faithful companion."),
    _p("anime", "Spy x Family", 2022, "Wit Studio and CloverWorks", ["spy family", "spyxfamily"], [
        "A comedy anime series that began in 2022.",
        "It was animated by Wit Studio and CloverWorks, from a manga first published online on Shōnen Jump+.",
        "A secret agent has to quickly find a pretend wife and child to get close to a political target.",
        "His new wife is secretly an assassin, and neither knows what the other really does.",
        "The adopted daughter can read minds and loves peanuts.",
        "Loid, Yor and Anya Forger, plus a big dog named Bond.",
    ], "It is a sitcom with spy-thriller trappings, and the joke that only the child knows everyone's secret never gets old. "
       "Anya's faces became one of the internet's favourite reaction images. It is light, warm and easy to share with "
       "people who do not usually watch anime."),
    _p("movie", "The Matrix", 1999, "The Wachowskis", [], [
        "A science fiction action film from 1999.",
        "It popularised 'bullet time', a slow-motion effect where the camera seems to circle a frozen moment.",
        "A software programmer who hacks at night is told the world he knows is a simulation.",
        "He is offered a choice between a red pill and a blue pill.",
        "Humans are kept in pods and used as an energy source by machines.",
        "Keanu Reeves plays Neo, guided by Morpheus and Trinity.",
    ], "The Wachowskis mixed Hong Kong action, cyberpunk anime and philosophy lectures into a blockbuster that changed how "
       "action films were shot for the next decade. Its ideas about simulated worlds sound more current now than they did "
       "then. The lobby shootout and the rooftop dodge are still the scenes everyone remembers."),
    _p("game", "The Witcher 3: Wild Hunt", 2015, "CD Projekt Red",
       ["witcher 3", "the witcher 3", "witcher 3 wild hunt", "the witcher"], [
        "An open-world role-playing game released in 2015.",
        "It was made by a Polish studio and is based on fantasy novels by Andrzej Sapkowski.",
        "A monster slayer for hire searches for his adopted daughter.",
        "A spectral army of riders is chasing her across the world.",
        "A card game played in its taverns was so popular that it became a separate release, Gwent.",
        "Geralt of Rivia searches for Ciri.",
    ], "It is remembered for side quests that are as well written as other games' main stories, starting with the Bloody "
       "Baron early on. Choices often have no right answer, and their consequences turn up hours later. The Blood and Wine "
       "expansion is a full new region and many players' favourite part."),
    _p("tv", "Arcane", 2021, "Christian Linke and Alex Yee", [], [
        "An animated series that premiered in 2021.",
        "It is based on a video game by Riot Games and was animated by the French studio Fortiche.",
        "Two orphaned sisters grow up in an undercity beneath a gleaming, wealthy city.",
        "A young inventor finds a way to harness magic through technology.",
        "It won the Emmy for Outstanding Animated Program.",
        "Vi and Jinx, in Piltover and Zaun, from League of Legends.",
    ], "You do not need to have played League of Legends to follow it; the show stands on its own as a story about two "
       "sisters on opposite sides of a divided city. Fortiche's painted 3D style looks like nothing else on TV. Season two "
       "finishes the story."),
    _p("album", "Nevermind", 1991, "Nirvana", [], [
        "A rock album released in 1991.",
        "In January 1992 it knocked Michael Jackson's Dangerous off the top of the US album chart.",
        "It was produced by Butch Vig and helped carry grunge into the mainstream.",
        "Its cover shows a baby swimming towards a dollar bill on a fishhook.",
        "Its band was formed in Aberdeen, Washington.",
        "Nirvana's album that opens with 'Smells Like Teen Spirit'.",
    ], "Few albums have shifted popular music as suddenly: within months, hair metal sounded old. Butch Vig's production "
       "made the songs heavy and catchy at once. 'In Bloom', 'Lithium' and 'Drain You' are as strong as the famous opener."),
    _p("movie", "Superman", 2025, "James Gunn", [], [
        "A superhero film released in 2025.",
        "It launched a new DC film universe under its writer and director, James Gunn.",
        "The hero is already famous when the film begins, just after his first ever defeat in a fight.",
        "An enthusiastic, badly behaved superpowered dog comes to his rescue.",
        "A tech billionaire tries to turn the public against an alien immigrant.",
        "David Corenswet plays Clark Kent, with Rachel Brosnahan as Lois Lane and Nicholas Hoult as Lex Luthor.",
    ], "James Gunn skipped the origin story everyone knows and dropped viewers into a world already full of heroes, with a "
       "hopeful, comic-book tone. It is one of the titles OmniTrackr members track most this year. Krypto the dog steals "
       "several scenes."),
    _p("anime", "Death Note", 2006, "Madhouse", [], [
        "A supernatural thriller anime that aired from 2006 to 2007.",
        "It was animated by Madhouse, from a manga by the creators of Bakuman.",
        "A brilliant high school student finds a notebook dropped by a bored spirit from another realm.",
        "Anyone whose name is written in it dies.",
        "An eccentric detective who sits with his knees up and lives on sweets sets out to catch him.",
        "Light Yagami, known as Kira, against the detective L, watched by the shinigami Ryuk.",
    ], "It is a cat-and-mouse game between two geniuses, and the fun is watching each one predict the other several moves "
       "ahead. The first half is the most celebrated. At 37 episodes it is a good short series for people new to anime."),
    _p("game", "Hollow Knight", 2017, "Team Cherry", [], [
        "A 2D action-adventure game released in 2017.",
        "It was made by a small Australian studio after a Kickstarter campaign.",
        "You explore a vast, ruined underground kingdom of insects.",
        "When you die, you must defeat your own shade to recover your money, called Geo.",
        "A mapmaker named Cornifer hums to himself as he sells you maps of each area.",
        "A small, silent wanderer with a nail for a sword explores Hallownest.",
    ], "A tiny team made one of the best-loved games of its kind, with hand-drawn art, a melancholy score and a huge map that "
       "keeps opening up. It is hard but fair, and the free expansions added a lot. Its sequel, Silksong, followed in 2025."),
    _p("tv", "Friends", 1994, "David Crane and Marta Kauffman", [], [
        "A sitcom that premiered in 1994 and ran for ten seasons.",
        "Its theme song, by the Rembrandts, includes four claps.",
        "Six people in their twenties live in Manhattan and spend their time in a coffee house.",
        "One of them is a palaeontologist, and another is a chef.",
        "'We were on a break!' became a long-running argument.",
        "Rachel, Ross, Monica, Chandler, Joey and Phoebe hang out at Central Perk.",
    ], "It is the comfort rewatch for a generation, and new viewers keep finding it on streaming. Some jokes have aged, but "
       "the ensemble timing has not. 'The One Where Everybody Finds Out' and 'The One with the Embryos' are good places to "
       "test whether it is for you."),
    _p("book", "The Hunger Games", 2008, "Suzanne Collins", [], [
        "A young adult dystopian novel published in 2008.",
        "Its author got the idea while flicking between reality TV and footage of the Iraq war.",
        "Every year, each district must send two teenagers to a televised fight to the death.",
        "A girl volunteers to take her younger sister's place.",
        "A mockingjay pin becomes a symbol of rebellion.",
        "Katniss Everdeen and Peeta Mellark represent District 12 in Panem.",
    ], "Suzanne Collins wrote a fast, first-person thriller that is also about how spectacle numbs people to violence. It set "
       "off a wave of young adult dystopias, but few match its pace. The prequels go back to the early days of the games."),
    _p("movie", "Coco", 2017, "Lee Unkrich", [], [
        "An animated film from 2017, set during Mexico's Day of the Dead.",
        "It is a Pixar film and won Academy Awards for Best Animated Feature and Best Original Song.",
        "A boy dreams of being a musician, but his family has banned music for generations.",
        "He strums a famous guitar and is transported to the Land of the Dead.",
        "He needs a family member's blessing to return before sunrise.",
        "Miguel, Héctor and the song 'Remember Me'.",
    ], "Pixar's team made many research trips to Mexico, and the result is a film full of specific detail, from marigold "
       "bridges to family altars. The ending is one of the studio's most emotional. It is a lovely film to watch with "
       "grandparents."),
    _p("game", "Celeste", 2018, "Maddy Makes Games", [], [
        "A precision platformer released in 2018.",
        "It grew out of a small game made in four days for a game jam by the creators of TowerFall.",
        "A young woman decides to climb a mountain in Canada.",
        "A dark reflection of herself, born from her anxiety, tries to stop her.",
        "Collecting strawberries is optional, and an assist mode lets anyone reach the end.",
        "Madeline climbs with the help of an air dash and her new friend Theo.",
    ], "It is very hard, but checkpoints after every screen keep frustration low, and its assist mode set an example for "
       "accessibility in games. The story about anxiety is handled with real care. The soundtrack by Lena Raine is worth "
       "listening to on its own."),
    _p("anime", "Cowboy Bebop", 1998, "Sunrise", [], [
        "A science fiction anime series from 1998.",
        "It was directed by Shinichirō Watanabe, with a jazz soundtrack by Yoko Kanno and the Seatbelts.",
        "A crew of bounty hunters travels the solar system in an old fishing ship.",
        "The crew includes a young hacker and a very clever corgi.",
        "The lead's past in a crime syndicate, and a man named Vicious, catch up with him.",
        "Spike Spiegel, Jet Black, Faye Valentine, Ed and Ein.",
    ], "It is often the first anime people recommend to friends who think they do not like anime. Each episode borrows a "
       "different genre, from noir to comedy to horror, and the music ties it all together. It is only 26 episodes, plus a "
       "film."),
    _p("tv", "The Simpsons", 1989, "Matt Groening", [], [
        "An animated sitcom that premiered as a series in 1989 and is still running.",
        "It started as short sketches on The Tracey Ullman Show.",
        "A safety inspector at a nuclear power plant lives with his family in Springfield.",
        "His son is a skateboarding troublemaker, and his daughter plays the saxophone.",
        "The family is drawn with yellow skin and big overbites.",
        "Homer, Marge, Bart, Lisa and Maggie.",
    ], "It is the longest-running American scripted primetime series, and its best seasons, roughly the third to the "
       "eighth, are some of the most quoted TV ever made. Its jokes are so dense that rewatches turn up new ones. Start "
       "anywhere in that run."),
    _p("album", "21", 2011, "Adele", ["twenty one"], [
        "A pop and soul album released in 2011.",
        "It was the best-selling album in the world in both 2011 and 2012.",
        "Its singer wrote it after a painful break-up and named it after her age at the time.",
        "It won Album of the Year at the Grammys.",
        "Its songs include 'Someone Like You' and 'Set Fire to the Rain'.",
        "Adele's album that opens with 'Rolling in the Deep'.",
    ], "Built around a huge voice and a simple idea, songs about one relationship from anger to acceptance, it became one of "
       "the best-selling albums of the century. 'Someone Like You' is just voice and piano. It is a good album to hear in order."),
    _p("movie", "Mad Max: Fury Road", 2015, "George Miller", ["fury road"], [
        "An action film from 2015, set in a desert wasteland.",
        "It was directed by George Miller, who made the first film in its series in 1979.",
        "Most of the film is one long chase there and back.",
        "A one-armed war-rig driver smuggles five women away from a tyrant who keeps them as wives.",
        "A blind guitarist strapped to a truck plays a guitar that shoots flames.",
        "Charlize Theron plays Imperator Furiosa, fleeing Immortan Joe and his War Boys.",
    ], "George Miller shot most of the stunts for real in the Namibian desert, and it shows in every crash. There is very "
       "little dialogue; the story is told through movement and design. It won six Oscars, mostly for craft, and Furiosa "
       "got her own film in 2024."),
    _p("game", "Tetris", 1984, "Alexey Pajitnov", [], [
        "A puzzle video game first made in 1984.",
        "It was created by Alexey Pajitnov, a researcher at the Soviet Academy of Sciences in Moscow.",
        "Its Game Boy version was bundled with the handheld in 1989.",
        "A 2023 film told the story of how its licensing rights were fought over during the Cold War.",
        "Shapes made of four squares fall, and any full horizontal line disappears.",
        "The long I-piece, the S and Z pieces, and the Russian folk tune 'Korobeiniki'.",
    ], "Simple enough to learn in seconds and deep enough that competitive players are still finding new techniques decades "
       "later, it may be the most perfectly designed video game. In 2023 a teenager became the first person known to reach "
       "the NES version's 'kill screen'. Tetris Effect is a beautiful modern version."),
    _p("anime", "Neon Genesis Evangelion", 1995, "Gainax", ["evangelion", "nge", "shin seiki evangelion"], [
        "A mecha anime series that first aired in 1995.",
        "It was made by Studio Gainax, and its director later retold it in four films.",
        "Teenagers pilot giant biomechanical machines to fight mysterious beings called Angels.",
        "A 14-year-old boy is summoned by his cold, distant father to pilot one.",
        "Its final two TV episodes take place almost entirely inside the main character's mind.",
        "Shinji Ikari, Rei Ayanami and Asuka Langley Soryu work for NERV in Tokyo-3.",
    ], "Hideaki Anno started with a giant-robot show and turned it into a raw portrait of depression and loneliness, which is "
       "why it is still argued about decades later. Watch the series, then the film The End of Evangelion. The four Rebuild "
       "films tell a different version."),
    _p("tv", "Severance", 2022, "Dan Erickson", [], [
        "A psychological thriller series that premiered in 2022.",
        "Ben Stiller directed most of its first season, which streams on Apple TV+.",
        "Workers at a biotech company have a chip that separates their work memories from their home memories.",
        "Their team refines data by sorting numbers that feel 'scary' on vintage-looking computers.",
        "Rewards for good work include a waffle party and a melon bar.",
        "Mark Scout, Helly R., Dylan and Irving work at Lumon Industries.",
    ], "It takes the feeling of a pointless office job and pushes it into science fiction, with sets so clean they become "
       "unsettling. The mystery deepens episode by episode, and the first season finale is one of the best of the decade. "
       "Season two came out in 2025."),
    _p("book", "Pride and Prejudice", 1813, "Jane Austen", [], [
        "A novel first published in 1813.",
        "Its author's working title for it was First Impressions.",
        "Mrs Bennet is desperate to see her five daughters married.",
        "Its first line says a single man with a good fortune must be in want of a wife.",
        "The second daughter turns down a proud, wealthy man's first proposal.",
        "Elizabeth Bennet and Mr Darcy, by Jane Austen.",
    ], "Jane Austen's sharpest comedy is about how first judgements go wrong, and her narrator is often funnier than the "
       "characters. It has been adapted many times, with the 1995 BBC series and the 2005 film the most loved. If older "
       "prose usually puts you off, try this first."),
    _p("movie", "Back to the Future", 1985, "Robert Zemeckis", [], [
        "A science fiction comedy film from 1985.",
        "It was directed by Robert Zemeckis, with Steven Spielberg as an executive producer.",
        "A teenager is sent 30 years into the past by mistake.",
        "Once there, he gets in the way of his own parents meeting.",
        "The time machine is a DeLorean that has to reach 88 miles per hour.",
        "Marty McFly and Doc Brown, with a lightning strike at the clock tower.",
    ], "Its script is often taught as a model of setup and payoff: almost every detail in the first act comes back later. "
       "Michael J. Fox replaced the original lead weeks into filming. It is a crowd-pleaser that works on every rewatch, "
       "and the two sequels make a satisfying set."),
    _p("game", "Animal Crossing: New Horizons", 2020, "Nintendo", ["animal crossing", "acnh"], [
        "A life simulation game released in March 2020.",
        "This Nintendo Switch release became a comfort for many people during the first months of lockdown.",
        "You move to a deserted island on a getaway package and slowly turn it into a village.",
        "A raccoon businessman sells you the trip and then a home loan.",
        "Loans have no interest and no deadline, and you pay them off in Bells.",
        "Tom Nook, Isabelle and Blathers the museum owl.",
    ], "Released just as much of the world went into lockdown, it gave people a place to visit friends, hold birthday parties "
       "and even graduations. It runs on a real-time clock, so it is best played a little every day. The Happy Home Paradise "
       "expansion adds holiday-home design."),
    _p("tv", "The Bear", 2022, "Christopher Storer", [], [
        "A comedy-drama series that premiered in 2022.",
        "It is made by FX and has won the Emmy for Outstanding Comedy Series.",
        "An award-winning fine-dining chef comes home to Chicago to run his late brother's sandwich shop.",
        "The kitchen staff shout 'Yes, chef!' and 'Behind!' constantly.",
        "Episode seven of the first season is filmed as one continuous take.",
        "Carmy Berzatto, Sydney and Richie run The Original Beef of Chicagoland.",
    ], "It is labelled a comedy, but it plays more like a stress dream about grief, family and the restaurant business, with "
       "short, fast episodes. Its kitchen scenes feel real enough that chefs praised them. The Christmas episode 'Fishes' "
       "in season two is a standout."),
    _p("anime", "My Hero Academia", 2016, "Bones", ["boku no hero academia", "mha", "bnha"], [
        "A superpowered action anime series that began airing in 2016.",
        "It is animated by Bones and adapted from Kōhei Horikoshi's manga.",
        "About 80 percent of people are born with a special power called a Quirk.",
        "A boy born without one is chosen by the world's greatest crime-fighter to inherit his power.",
        "He enrols at U.A. High School, which trains young people to save others for a living.",
        "Izuku Midoriya, called Deku, inherits One For All from All Might.",
    ], "Kōhei Horikoshi took American superhero comics and filtered them through a Japanese school story, and the mix "
       "worked: it became one of the biggest anime of its decade. The sports-festival arc in season two is where many fans "
       "were won over. The manga ended in 2024."),
    _p("movie", "The Shawshank Redemption", 1994, "Frank Darabont", ["shawshank"], [
        "A prison drama film from 1994, adapted from a novella by Stephen King.",
        "It disappointed at the box office before becoming one of the most loved films on home video and TV.",
        "A banker is sentenced to life for murdering his wife and her lover, a crime he says he did not commit.",
        "He befriends a fellow inmate who can get things smuggled in.",
        "A poster of Rita Hayworth hangs on his cell wall for years.",
        "Tim Robbins plays Andy Dufresne and Morgan Freeman plays Red.",
    ], "Frank Darabont's film is about patience and hope more than prison, which is why so many people call it their "
       "favourite. It has sat at the top of IMDb's user ratings for many years. Morgan Freeman's narration makes it as easy to "
       "rewatch as a favourite book."),
    _p("movie", "The Godfather", 1972, "Francis Ford Coppola", [], [
        "A crime drama film from 1972, adapted from a best-selling novel.",
        "It won the Academy Award for Best Picture, and its sequel won it too two years later.",
        "It opens at a lavish wedding, where the head of a crime family hears requests from his guests.",
        "A film producer wakes up next to the severed head of his prized racehorse.",
        "The youngest son, a war hero who wanted nothing to do with the family business, shoots two men in a restaurant.",
        "Marlon Brando plays Vito Corleone and Al Pacino plays Michael.",
    ], "Francis Ford Coppola fought the studio over almost everything, from casting Al Pacino to shooting in dark, amber "
       "light, and won nearly every argument. The result is a crime film that plays like a family tragedy. Michael's slow "
       "change from outsider to head of the family is the spine of the story, and Part II continues it."),
    _p("tv", "The Sopranos", 1999, "David Chase", [], [
        "A crime drama series that premiered in 1999 and ran for six seasons.",
        "It aired on HBO and is often credited with starting television's era of prestige drama.",
        "A New Jersey mob boss secretly starts seeing a psychiatrist after a series of panic attacks.",
        "His troubles seem to start when a family of ducks leaves his swimming pool.",
        "The series ends with a sudden cut to black in a diner while 'Don't Stop Believin'' plays.",
        "James Gandolfini plays Tony, with Edie Falco as Carmela and Lorraine Bracco as Dr. Melfi.",
    ], "David Chase made a gangster story about therapy, family and suburban boredom, and showed that TV could be as "
       "ambitious as film. James Gandolfini makes a frightening man sympathetic and then makes you regret it. The ending is "
       "still argued about, which is exactly what Chase intended."),
    _p("anime", "Naruto", 2002, "Studio Pierrot", [], [
        "An anime series that began airing in Japan in 2002.",
        "It was animated by Studio Pierrot, and a sequel series following the hero as a teenager began in 2007.",
        "An orphaned boy with a nine-tailed fox spirit sealed inside him is shunned by his village.",
        "He dreams of becoming Hokage, the leader of his hidden village.",
        "His team is led by a masked teacher who is always late and reads trashy novels.",
        "He trains alongside Sasuke Uchiha and Sakura Haruno in the Hidden Leaf Village.",
    ], "For many viewers outside Japan this was the first long anime they followed every week, and its story about a lonely "
       "kid earning respect still lands. The ninja world has a clear set of rules that makes its fights easy to follow. "
       "The Chūnin exam arc is where it really gets going."),
    _p("game", "Super Mario Bros.", 1985, "Nintendo", ["super mario brothers", "super mario", "mario bros", "smb"], [
        "A side-scrolling platform game released in 1985.",
        "It was made by Nintendo, designed by Shigeru Miyamoto, and came bundled with many NES consoles.",
        "A plumber has to cross eight worlds to rescue a princess from a king of turtles.",
        "Mushrooms make you bigger, and a flower lets you throw fireballs.",
        "At the end of most castles, a mushroom retainer tells you she is in another castle.",
        "Two brothers in red and green caps face Bowser, King of the Koopas, to save Princess Peach.",
    ], "Its first screen teaches you to run, jump and avoid enemies without a single word of text, which is why designers still "
       "study it. It helped bring home video games back after the crash of 1983. Speedrunners are still shaving fractions "
       "of a second off it today."),
    _p("book", "The Great Gatsby", 1925, "F. Scott Fitzgerald", [], [
        "A novel published in 1925 and set during the Jazz Age.",
        "Its author also wrote This Side of Paradise and Tender Is the Night.",
        "A young bond salesman rents a small house on Long Island next to a mansion where huge parties are thrown.",
        "A green light at the end of a dock across the bay haunts the mansion's owner.",
        "A billboard with giant eyes watches over a grey valley of ashes.",
        "Nick Carraway narrates, and Daisy Buchanan is the woman his mysterious neighbour still loves.",
    ], "It sold poorly in its author's lifetime and is now one of the most taught American novels. It is short, and every "
       "sentence is doing work: the parties, the cars and the green light all say something about wanting a past you cannot "
       "have. Read the last page twice."),
    _p("album", "Rumours", 1977, "Fleetwood Mac", [], [
        "A rock album released in 1977.",
        "It won the Grammy for Album of the Year and is one of the best-selling albums ever made.",
        "Its band's two couples were breaking up while they recorded it.",
        "One of its songs became the theme of Bill Clinton's 1992 presidential campaign.",
        "Its songs include 'Go Your Own Way', 'Dreams' and 'The Chain'.",
        "Fleetwood Mac's album with Stevie Nicks, Lindsey Buckingham and Christine McVie.",
    ], "The band members wrote songs to and about each other while their relationships fell apart, and somehow made one of "
       "the smoothest-sounding records of the 1970s. 'Dreams' found a new generation in 2020 thanks to a viral skateboard "
       "video. Listen to it in order to hear the conversation between the songs."),
    _p("movie", "Up", 2009, "Pete Docter", [], [
        "An animated adventure film from 2009.",
        "It was the first animated film to open the Cannes Film Festival, and it won the Oscar for Best Animated Feature.",
        "Its opening minutes tell the whole story of a marriage with no dialogue.",
        "A grumpy widower ties thousands of balloons to his house and floats away.",
        "A talking dog named Dug announces that he has just met you and loves you.",
        "Carl Fredricksen and a Wilderness Explorer named Russell head for Paradise Falls.",
    ], "The wordless 'Married Life' sequence is one of the most famous openings in film, and it gives the rest of the "
       "adventure its weight. After that it becomes a silly, warm story about letting go of the past. Michael Giacchino's "
       "score won an Oscar."),
    _p("tv", "Succession", 2018, "Jesse Armstrong", [], [
        "A drama series that premiered in 2018 and ran for four seasons.",
        "It aired on HBO, was created by a British writer of Peep Show, and won the Emmy for Outstanding Drama Series three times.",
        "The ageing founder of a huge media company keeps his four adult children guessing about who will take over.",
        "The family's company is called Waystar Royco.",
        "A gangly cousin from out of town keeps getting pulled into the company's scandals.",
        "Logan Roy and his children Kendall, Shiv, Roman and Connor.",
    ], "It is a drama about terrible rich people that is also one of the funniest shows on TV, thanks to insults sharp enough "
       "to quote. Nobody gets what they want for long. The final season, which builds to one last board vote, is as good as "
       "anything before it."),
    _p("anime", "Hunter x Hunter", 2011, "Madhouse", ["hunter hunter", "hxh"], [
        "An anime series from 2011, the second adaptation of its manga.",
        "It was animated by Madhouse, from a manga by Yoshihiro Togashi, the creator of YuYu Hakusho.",
        "A boy raised on an island leaves home to find the father who left him behind.",
        "He takes a deadly exam to earn a licence that opens almost any door in the world.",
        "Fighters use Nen, an aura they shape into a personal ability with its own rules.",
        "Gon Freecss and his friend Killua Zoldyck, heir to a family of assassins.",
    ], "It starts as a bright adventure and keeps changing shape, and its Chimera Ant arc is one of the darkest and most "
       "admired stories in shōnen anime. The power system rewards clever rules over raw strength. The manga is famous for "
       "long breaks, so the 2011 series is the full story so far."),
    _p("game", "Pokémon Red and Blue", 1996, "Game Freak",
       ["pokemon red", "pokemon blue", "pokemon red blue", "pokemon green", "pokemon red and green"], [
        "A role-playing game first released in Japan in 1996, for a handheld console.",
        "It was made by Game Freak and came in two versions with slightly different creatures to catch.",
        "A boy leaves his hometown with his first partner, chosen from three, to collect eight badges.",
        "Trading between two copies over a link cable is the only way to complete the collection.",
        "Your rival, the grandson of the local professor, always seems to be one step ahead.",
        "Choose Bulbasaur, Charmander or Squirtle, and try to catch all 151.",
    ], "Satoshi Tajiri based the idea on his childhood love of collecting insects, and the link cable turned a single-player "
       "game into a playground craze. It started what became the highest-grossing media franchise in the world. Its bugs, "
       "like the famous MissingNo., became legends of their own."),
    _p("movie", "The Lion King", 1994, "Roger Allers and Rob Minkoff", [], [
        "An animated film from 1994, set on the African savanna.",
        "Its songs were written by Elton John and Tim Rice, with a score by Hans Zimmer.",
        "A young prince runs away after being made to believe he caused his father's death.",
        "A meerkat and a warthog teach him a carefree motto.",
        "His wicked uncle takes the throne with the help of hyenas.",
        "Simba, Mufasa, Scar, Timon and Pumbaa, and the song 'Hakuna Matata'.",
    ], "It borrows the bones of Hamlet and sets them to some of Disney's best songs, and the wildebeest stampede is still a "
       "remarkable piece of animation. It became one of the highest-grossing animated films ever, and the stage musical has "
       "run on Broadway since 1997."),
    _p("tv", "The Mandalorian", 2019, "Jon Favreau", [], [
        "A space western series that premiered in 2019.",
        "It was the first live-action series in its franchise, made by Jon Favreau for Disney+.",
        "A masked bounty hunter who never removes his helmet takes a job to retrieve a mysterious asset.",
        "The asset turns out to be a small green child who can use the Force.",
        "Its sets were often giant LED screens on a stage called the Volume.",
        "Pedro Pascal plays Din Djarin, who protects Grogu.",
    ], "Jon Favreau went back to the western and samurai films that inspired the original trilogy, with short, self-contained "
       "episodes that each feel like a small adventure. Grogu became an instant phenomenon. Its LED stage changed how many effects-heavy shows are filmed."),
    _p("anime", "Chainsaw Man", 2022, "MAPPA", [], [
        "An anime series that began airing in 2022.",
        "It was animated by MAPPA, from a manga by Tatsuki Fujimoto.",
        "A young man drowning in his dead father's debts hunts devils for the yakuza.",
        "His devil companion, a little dog called Pochita, merges with his heart after he is killed.",
        "He joins a government team of devil hunters led by a mysterious woman named Makima.",
        "Denji can pull a cord in his chest to grow blades from his head and arms.",
    ], "Tatsuki Fujimoto's story looks like a gory action comedy and turns out to be about a boy who has never had anything, "
       "learning what he wants. Every episode has its own ending song. The Reze film continues the story from the end of "
       "the first season."),
    _p("game", "Half-Life 2", 2004, "Valve", ["half life 2", "hl2"], [
        "A first-person shooter released in 2004.",
        "Its studio also built the Steam store, which this game helped launch by requiring it.",
        "A silent theoretical physicist arrives by train in a city controlled by an alien empire called the Combine.",
        "A gravity gun lets you pick up objects and fling them, including saw blades.",
        "A zombie-filled town called Ravenholm is one of its scariest chapters.",
        "Gordon Freeman fights alongside Alyx Vance in City 17.",
    ], "Its physics engine let players solve problems with objects, not just bullets, and its characters had faces that "
       "showed real emotion. It tells its story without ever taking control away from you. The Episode One and Two "
       "follow-ups continue the story."),
    _p("book", "Frankenstein", 1818, "Mary Shelley", [], [
        "A Gothic novel first published in 1818.",
        "Its author began it at 18, during a ghost-story contest with Lord Byron near Lake Geneva.",
        "A ship's captain trying to reach the North Pole rescues a half-frozen man from the ice.",
        "A young scientist brings a body built from parts to life, then abandons it in horror.",
        "The creature teaches himself to read by secretly watching a family in a cottage.",
        "Victor and his nameless creation, in Mary Shelley's novel.",
    ], "Often called the first science fiction novel, it is less about a monster than about a creator who refuses "
       "responsibility for what he made. The creature is eloquent and hurt, nothing like the grunting film version. It is "
       "shorter and stranger than most people expect."),
    _p("movie", "Titanic", 1997, "James Cameron", [], [
        "A romantic disaster film from 1997.",
        "It won eleven Academy Awards and was the highest-grossing film ever for more than a decade.",
        "A treasure hunter searching a shipwreck for a diamond meets an elderly survivor.",
        "A poor artist wins his ticket in a poker game moments before departure.",
        "Céline Dion's 'My Heart Will Go On' became one of the best-selling singles ever.",
        "Leonardo DiCaprio and Kate Winslet play Jack and Rose.",
    ], "James Cameron built a nearly full-size replica of the ship and spent a fortune most people thought he would never earn "
       "back. The love story carries you into the long, terrifying second half, which plays out almost in real time. It "
       "is three hours that move fast."),
    _p("album", "The Dark Side of the Moon", 1973, "Pink Floyd", [], [
        "A progressive rock album released in 1973.",
        "It stayed on the US Billboard 200 album chart for more than 900 weeks.",
        "Alan Parsons engineered it at Abbey Road Studios, with heartbeats, cash registers and clocks in the mix.",
        "Its cover shows a beam of light passing through a prism and splitting into a rainbow.",
        "Its songs deal with time, money, conflict and madness.",
        "Pink Floyd's album with 'Money', 'Time' and 'The Great Gig in the Sky'.",
    ], "It flows as one continuous piece, which made it a favourite for testing new hi-fi systems for decades. Clare Torry's "
       "wordless vocal on 'The Great Gig in the Sky' was improvised in a single session. Listen to it from start to finish, "
       "ideally on headphones."),
    _p("tv", "Sherlock", 2010, "Steven Moffat and Mark Gatiss", [], [
        "A crime drama series that premiered in 2010, with feature-length episodes.",
        "It was co-created by Steven Moffat and Mark Gatiss for the BBC.",
        "It moves a famous Victorian detective to present-day London, where clues arrive by text message.",
        "His new flatmate is an army doctor just back from Afghanistan.",
        "His greatest enemy is a consulting criminal named Jim Moriarty.",
        "Benedict Cumberbatch and Martin Freeman live at 221B Baker Street.",
    ], "Updating Conan Doyle's stories to the age of smartphones should not have worked as well as it did. On-screen text "
       "shows the detective's deductions as they happen. The first two series, especially 'A Scandal in Belgravia', are the "
       "most loved."),
    _p("anime", "Mob Psycho 100", 2016, "Bones", ["mob psycho"], [
        "An action comedy anime series that began in 2016.",
        "It was animated by Bones, from a manga by ONE, the creator of One-Punch Man.",
        "A shy middle school boy with enormous psychic power tries hard to live a normal life.",
        "He works for a fake psychic and con artist who pays him almost nothing.",
        "A meter tracks his bottled-up emotions, and when it fills, something explodes.",
        "Shigeo Kageyama works for Reigen Arataka, with the spirit Dimple floating nearby.",
    ], "Its hand-drawn fight scenes are some of the most inventive animation of the decade, but the heart of it is a kind boy "
       "learning that being strong does not make you a good person. Reigen, the fraud who gives genuinely good advice, "
       "steals the show."),
    _p("game", "Undertale", 2015, "Toby Fox", [], [
        "A role-playing game released in 2015.",
        "It was made almost entirely by one person, Toby Fox, who also wrote its music.",
        "A child falls into an underground world full of monsters.",
        "You can finish the game without killing anyone, by talking, flirting or petting your way out of fights.",
        "The game remembers what you did, even after you reset.",
        "Sans, Papyrus, Toriel and Undyne, and the song 'Megalovania'.",
    ], "It plays with what players expect from role-playing games, so that sparing an enemy feels as meaningful as beating "
       "one. It is funny, kind and occasionally unsettling. Play it blind, and play the peaceful route first."),
    _p("movie", "Star Wars", 1977, "George Lucas",
       ["a new hope", "star wars a new hope", "star wars episode iv a new hope", "episode iv a new hope"], [
        "A space adventure film from 1977.",
        "Its writer and director founded Industrial Light & Magic to make its effects.",
        "A farm boy on a desert planet finds a secret message hidden in a small robot.",
        "An old hermit gives him his father's laser sword.",
        "Rebels destroy a moon-sized battle station by firing into a small exhaust port.",
        "Luke Skywalker, Princess Leia, Han Solo and Darth Vader.",
    ], "George Lucas mixed old Flash Gordon serials, westerns and samurai films into a fairy tale that almost nobody at the "
       "studio believed in. It changed how blockbusters were made and sold. Its lived-in, dusty look is a big reason it "
       "still holds up."),
    _p("tv", "Ted Lasso", 2020, "Jason Sudeikis, Bill Lawrence, Brendan Hunt and Joe Kelly", [], [
        "A comedy series that premiered in 2020.",
        "It streams on Apple TV+ and grew out of a character from adverts for NBC's football coverage.",
        "An American college football coach is hired to manage an English football club, knowing nothing about the sport.",
        "The club's new owner secretly hopes he will fail, to spite her ex-husband.",
        "He bakes biscuits for his boss every morning and puts up a sign saying 'BELIEVE' in the locker room.",
        "Jason Sudeikis plays the coach of AFC Richmond.",
    ], "It arrived in the middle of 2020 and won people over with a lead character who is relentlessly kind without being "
       "naive. It handles anxiety and therapy with real care under the jokes. It won the Emmy for Outstanding Comedy Series "
       "twice."),
    _p("anime", "Sailor Moon", 1992, "Toei Animation", ["bishoujo senshi sailor moon", "pretty guardian sailor moon"], [
        "A magical girl anime series that began airing in 1992.",
        "It was animated by Toei Animation, from a manga by Naoko Takeuchi.",
        "A clumsy 14-year-old schoolgirl meets a talking black cat with a crescent mark on its forehead.",
        "She transforms with a brooch into a heroine in a school-uniform outfit with a tiara.",
        "She leads a team of guardians, each named after a planet.",
        "Usagi Tsukino, her cat Luna and the mysterious Tuxedo Mask.",
    ], "It turned the magical girl story into a team adventure about friendship and became a global hit in the 1990s. Many "
       "fans now in their thirties can still recite the transformation lines. Sailor Moon Crystal and the Eternal films "
       "retell the manga more closely."),
    _p("game", "God of War", 2018, "Santa Monica Studio", ["gow", "god of war 2018"], [
        "An action-adventure game released in 2018, a fresh start for a long-running series.",
        "It was made by Santa Monica Studio for the PlayStation 4.",
        "A Spartan warrior, now living quietly in Norse lands, sets out with his young son to scatter his wife's ashes.",
        "The whole game is presented as one continuous shot, with no camera cuts.",
        "He fights with a frost axe that flies back to his hand when he calls it.",
        "Kratos and his son Atreus journey to the highest peak in the nine realms.",
    ], "The series was known for rage and spectacle, and this reboot turned it into a story about a father learning to talk "
       "to his son. The one-shot camera keeps you close to them the whole time. Ragnarök finishes the Norse story."),
    _p("book", "Project Hail Mary", 2021, "Andy Weir", [], [
        "A science fiction novel published in 2021.",
        "Its author's first novel was The Martian.",
        "A man wakes up alone on a spaceship with no memory of who he is or why he is there.",
        "Tiny organisms are dimming the Sun, and Earth's survival depends on his mission.",
        "He makes friends with an alien engineer who speaks in musical notes.",
        "Ryland Grace and Rocky, a spider-like alien from 40 Eridani.",
    ], "Andy Weir loves solving science problems on the page, and this is his best book for it, with a friendship at its "
       "centre that is genuinely moving. You learn who the narrator is at the same pace he does. A film adaptation starring "
       "Ryan Gosling followed in 2026."),
    _p("movie", "Alien", 1979, "Ridley Scott", [], [
        "A science fiction horror film from 1979.",
        "It was directed by Ridley Scott, and the Swiss artist H. R. Giger designed its creature.",
        "The crew of a commercial towing spaceship answers a distress signal from an uncharted planet.",
        "A creature bursts out of a crew member's chest during a meal.",
        "The ship's science officer turns out to be an android.",
        "Sigourney Weaver plays Ripley aboard the Nostromo.",
    ], "Ridley Scott treated a monster movie like a haunted-house film set among tired workers, and kept the creature hidden "
       "for most of it. Ripley became one of film's great heroes almost by accident. James Cameron's Aliens turns the "
       "sequel into an action film."),
    _p("tv", "Better Call Saul", 2015, "Vince Gilligan and Peter Gould", [], [
        "A crime drama series that premiered in 2015 and ran for six seasons.",
        "It is a prequel to another famous series, from the same co-creator.",
        "A small-time lawyer and former con man struggles to be taken seriously by his successful older brother.",
        "Black-and-white flash-forwards show him managing a cinnamon roll shop in Omaha.",
        "His brother believes he is allergic to electricity.",
        "Bob Odenkirk plays Jimmy McGill, with Rhea Seehorn as Kim Wexler.",
    ], "Many viewers think it is even better than the show it spun off from, because it is slower and sadder, about a man who "
       "keeps choosing the wrong road. Rhea Seehorn's Kim is the real heart of it. You can watch it without having seen "
       "the original."),
    _p("anime", "Steins;Gate", 2011, "White Fox", ["steins gate", "steinsgate"], [
        "A science fiction thriller anime that aired in 2011, based on a visual novel.",
        "It was animated by White Fox.",
        "A self-proclaimed mad scientist in Akihabara accidentally finds a way to send text messages to the past.",
        "A microwave oven is part of the machine.",
        "Every change to the past shifts the world to a different timeline, and only he remembers.",
        "Rintaro Okabe, who calls himself Hououin Kyouma, tries to save his friend Mayuri.",
    ], "The first half is a slow, goofy hangout show, and that is deliberate: it makes the second half's time-travel tragedy "
       "hit much harder. Its rules are consistent enough that fans still map out its timelines. Stick with it past "
       "episode 10."),
    _p("game", "Among Us", 2018, "Innersloth", [], [
        "A multiplayer party game first released in 2018.",
        "Made by a tiny studio called Innersloth, it became a worldwide hit two years later when streamers picked it up.",
        "A crew does repair tasks on a spaceship while one or more saboteurs secretly kill them off.",
        "When a body is reported, everyone meets to discuss and vote someone out.",
        "The characters are colourful bean-shaped astronauts.",
        "Crewmates and impostors, and the phrase 'Red is sus'.",
    ], "It is the board game Mafia moved to a spaceship, and in 2020 it was how many friends hung out when they could not "
       "meet. The fun is all in the arguments. It is best with a group that knows each other well enough to lie badly."),
    _p("album", "Lemonade", 2016, "Beyoncé", [], [
        "An R&B and pop album released in 2016.",
        "It was released together with an hour-long film first shown on HBO.",
        "Its songs move from suspicion and anger over infidelity to forgiveness.",
        "In one music video, its singer smashes car windows with a baseball bat.",
        "Its songs include 'Formation', 'Sorry' and 'Hold Up'.",
        "Beyoncé's album that mentions 'Becky with the good hair'.",
    ], "It moves through rock, country, blues and hip-hop while telling one story about betrayal and repair, and it ties that "
       "personal story to the history of Black women in the American South. Watch the film once; it changes how the "
       "album sounds."),
    _p("movie", "Ratatouille", 2007, "Brad Bird", [], [
        "An animated film from 2007, set in Paris.",
        "It was directed for Pixar by Brad Bird, who also made The Incredibles.",
        "A rat with a superb sense of smell dreams of becoming a chef.",
        "He controls a clumsy kitchen boy by pulling his hair under his chef's hat.",
        "A stern food critic is won over by a simple peasant dish that reminds him of his mother.",
        "Remy and Linguini cook at Gusteau's, whose motto is 'Anyone can cook'.",
    ], "Brad Bird made a film about creativity and criticism that adults may enjoy even more than children. Anton Ego's "
       "closing review is one of the best monologues in animation. The kitchen scenes were researched in real Paris "
       "restaurants."),
    _p("tv", "The Crown", 2016, "Peter Morgan", [], [
        "A historical drama series that premiered in 2016 and ran for six seasons.",
        "It was created by Peter Morgan, who wrote the film The Queen, for Netflix.",
        "It follows the reign of a British monarch, starting with her wedding in 1947.",
        "The lead actors are replaced every two seasons as the characters age.",
        "Claire Foy, Olivia Colman and Imelda Staunton each play the lead role.",
        "The lives of Queen Elizabeth II, Prince Philip and Princess Margaret.",
    ], "It is drama, not documentary, and it invents private conversations freely, but it is beautifully made and very good "
       "on the tension between duty and family. The first two seasons, with Claire Foy, are often called the strongest. "
       "Each episode works almost as a short film."),
    _p("anime", "Haikyu!!", 2014, "Production I.G", ["haikyu", "haikyuu"], [
        "A sports anime series that began airing in 2014.",
        "It was animated by Production I.G, from a manga by Haruichi Furudate.",
        "A short boy who can jump incredibly high joins his high school's struggling team.",
        "He is forced to team up with a genius setter he lost to in middle school.",
        "Their quick attack, where the ball arrives just as he reaches the top of his jump, becomes their weapon.",
        "Shoyo Hinata and Tobio Kageyama play volleyball for Karasuno High.",
    ], "It makes volleyball tense even for people who have never watched a match, and every rival team gets its own story. "
       "Nobody is a villain; they all just want to win. Its matches can run for several episodes and still feel short."),
    _p("game", "Baldur's Gate 3", 2023, "Larian Studios", ["baldurs gate 3", "bg3", "baldurs gate iii"], [
        "A role-playing game that left early access in 2023.",
        "It was made by Larian Studios, based on the fifth edition rules of Dungeons & Dragons.",
        "You wake up aboard a crashing ship with a tadpole parasite in your brain.",
        "Dice rolls decide whether you can talk, sneak or trick your way past a problem.",
        "It won Game of the Year at The Game Awards 2023.",
        "Shadowheart, Astarion, Lae'zel and Karlach can join your party on the Sword Coast.",
    ], "It feels like playing a tabletop game with a very generous dungeon master: almost any plan you come up with is allowed, "
       "and the story bends around it. Its companions are fully voiced and remember everything. It is long, so take your "
       "time with the first act."),
    _p("movie", "Whiplash", 2014, "Damien Chazelle", [], [
        "A drama film from 2014 about music.",
        "It was expanded from a short film its director made to raise money for the feature.",
        "A first-year drummer at a top New York music school is picked for its elite jazz band.",
        "His conductor throws a chair at his head to make a point about tempo.",
        "J. K. Simmons won the Academy Award for Best Supporting Actor as the conductor.",
        "Miles Teller plays Andrew, and Terence Fletcher keeps asking whether he is rushing or dragging.",
    ], "It is shot and cut like a thriller, and the last ten minutes are as tense as any action climax. It leaves open whether "
       "greatness is worth what it costs. Damien Chazelle made it for just a few million dollars, and it won three Oscars."),
    _p("tv", "Fleabag", 2016, "Phoebe Waller-Bridge", [], [
        "A comedy-drama series that premiered in 2016 and ran for two short seasons.",
        "Its creator and star first wrote it as a one-woman stage show at the Edinburgh Fringe.",
        "A young woman runs a struggling guinea pig café in London.",
        "She keeps breaking the fourth wall to make comments to the camera.",
        "In the second season she falls for a priest, played by Andrew Scott.",
        "Phoebe Waller-Bridge's series, with Olivia Colman as the godmother.",
    ], "Twelve half-hour episodes are all there is, and almost every one is both very funny and quietly devastating. The "
       "asides to the camera become part of the story. The second season is often called one of the best seasons of TV "
       "ever made."),
    _p("anime", "Vinland Saga", 2019, "Wit Studio", [], [
        "A historical anime series that began in 2019, set in the 11th century.",
        "Wit Studio animated its first season, from a manga by Makoto Yukimura.",
        "A boy joins the band of Viking mercenaries whose leader killed his father, hoping for a duel.",
        "Its second season takes place almost entirely on a farm, where he works as a slave.",
        "It slowly turns from a revenge story into one about rejecting violence.",
        "Thorfinn chases Askeladd and dreams of a peaceful country across the sea.",
    ], "The first season is a brutal Viking war story; the second is quiet and reflective, and fans argue about which is "
       "better. Together they make one of anime's most thoughtful stories about violence. Askeladd is a great antagonist."),
    _p("game", "Pac-Man", 1980, "Namco", ["pacman"], [
        "An arcade maze game released in 1980.",
        "It was made by Namco and designed by Toru Iwatani, who said a pizza with a slice missing inspired its hero.",
        "You eat every dot in a maze while four ghosts chase you.",
        "Eating a power pellet turns the ghosts blue so you can eat them.",
        "The ghosts are named Blinky, Pinky, Inky and Clyde.",
        "A yellow circle with a mouth that goes 'wakka wakka'.",
    ], "It was designed to appeal to people who did not play shooting games, and it became one of the first video game "
       "characters known everywhere. Each ghost has its own chasing behaviour, which is why expert routes exist. Pac-Man "
       "Championship Edition is a great modern take."),
    _p("book", "The Catcher in the Rye", 1951, "J. D. Salinger", [], [
        "A novel published in 1951.",
        "Its reclusive author published very little afterwards and lived quietly in New Hampshire.",
        "A 16-year-old is expelled from his prep school and spends a few days wandering New York City.",
        "He calls almost everyone around him a 'phony'.",
        "He wonders where the ducks in Central Park go when the pond freezes over.",
        "Holden Caulfield and his little sister Phoebe.",
    ], "Its voice, rambling, funny and hurt, is why readers either love it or cannot stand its narrator. Underneath the "
       "complaining is a boy grieving his brother. It is short and reads quickly, and it reads differently at 16 and at 40."),
    _p("movie", "Knives Out", 2019, "Rian Johnson", [], [
        "A murder mystery film from 2019.",
        "It was written and directed by Rian Johnson, and its screenplay was nominated for an Academy Award.",
        "A wealthy crime novelist is found dead the morning after his 85th birthday party.",
        "His nurse throws up whenever she tells a lie.",
        "A detective with a Southern drawl is hired anonymously to investigate.",
        "Daniel Craig plays Benoit Blanc, and Ana de Armas plays Marta.",
    ], "Rian Johnson revived the Agatha Christie-style whodunit and gave it a sharp point about inheritance and class. It "
       "reveals one big secret early and still has a twist left. Glass Onion and Wake Up Dead Man bring the detective back."),
    _p("tv", "Wednesday", 2022, "Alfred Gough and Miles Millar", [], [
        "A supernatural comedy series that premiered in 2022.",
        "Tim Burton directed half of its first season's episodes for Netflix.",
        "A deadpan teenage girl from a famously macabre family is sent to a boarding school for outcasts.",
        "A disembodied hand named Thing is her companion.",
        "Her dance at a school ball went viral on TikTok.",
        "Jenna Ortega plays the daughter of Morticia and Gomez Addams at Nevermore Academy.",
    ], "It is a teen mystery wrapped in the Addams Family's gothic style, and Jenna Ortega's unblinking performance makes it. "
       "Its first season became one of Netflix's most-watched English-language series. Season two continued the story back at Nevermore."),
    _p("anime", "Violet Evergarden", 2018, "Kyoto Animation", [], [
        "A drama anime series from 2018.",
        "It was animated by Kyoto Animation, from a light novel by Kana Akatsuki.",
        "A former child soldier with mechanical arms returns from war.",
        "She takes a job writing letters for other people, to learn what love means.",
        "Her commanding officer's last words were 'I love you', and she does not understand them.",
        "She works as an Auto Memory Doll for the CH Postal Company.",
    ], "It is often called the most beautiful anime ever made, and each episode tells one small story through a letter. Bring "
       "tissues for episode 10. The film that follows the series wraps up her story."),
    _p("game", "Dark Souls", 2011, "FromSoftware", [], [
        "An action role-playing game released in 2011.",
        "It was directed by Hidetaka Miyazaki and became famous for its punishing difficulty.",
        "You play a cursed undead who escapes an asylum and is sent on a pilgrimage.",
        "Resting at a bonfire restores your health but brings every enemy back.",
        "Firelink Shrine links to almost every area of an interconnected world called Lordran.",
        "Link the First Flame, after fighting Ornstein and Smough.",
    ], "Its reputation for difficulty hides how fair it is: almost every death teaches you something. Its world folds back on "
       "itself in surprising shortcuts, and its story is told through item descriptions and ruins. It inspired a whole "
       "genre of 'soulslikes'."),
    _p("album", "Random Access Memories", 2013, "Daft Punk", [], [
        "An electronic dance album released in 2013.",
        "It won the Grammy for Album of the Year.",
        "It was recorded mostly with live musicians instead of samples, including Nile Rodgers and Giorgio Moroder.",
        "Its biggest single features Pharrell Williams.",
        "Its songs include 'Get Lucky', 'Instant Crush' and 'Giorgio by Moroder'.",
        "Daft Punk's album, by the duo who perform in robot helmets.",
    ], "Daft Punk turned away from computers to make a warm, expensive-sounding tribute to the disco and soft rock of the late "
       "1970s. 'Get Lucky' was the song of summer 2013. 'Touch' with Paul Williams is the strange, moving centrepiece."),
    _p("movie", "La La Land", 2016, "Damien Chazelle", [], [
        "A musical romance film from 2016.",
        "It won six Academy Awards and was briefly announced as Best Picture by mistake.",
        "A jazz pianist and an aspiring actress meet in Los Angeles.",
        "It opens with a song-and-dance number on a jammed freeway.",
        "Its final minutes imagine the life the couple might have had together.",
        "Ryan Gosling and Emma Stone play Sebastian and Mia.",
    ], "It borrows from old Hollywood and French musicals but ends on a bittersweet note that keeps people arguing. The "
       "epilogue does in a few minutes what most films need an hour for. 'City of Stars' won the Oscar for Best Original Song."),
    _p("tv", "Chernobyl", 2019, "Craig Mazin", [], [
        "A historical drama miniseries from 2019, five episodes long.",
        "It was written by Craig Mazin for HBO and Sky.",
        "It dramatises a 1986 disaster in the Soviet Union and the lies told about it.",
        "Miners dig a tunnel beneath a burning reactor, working naked in the heat.",
        "Its first line asks: 'What is the cost of lies?'",
        "Jared Harris plays the scientist Valery Legasov, near the city of Pripyat.",
    ], "It is a horror story where the monster is radiation and the villain is a system that would rather lie than admit "
       "failure. Five episodes are all you need. The companion podcast explains what was changed for the drama."),
    _p("anime", "Bleach", 2004, "Studio Pierrot", [], [
        "An anime series that began in 2004 and returned in 2022 for its final story.",
        "It was animated by Studio Pierrot, from a manga by Tite Kubo.",
        "A teenager who can see ghosts gains the powers of a Soul Reaper.",
        "He uses an enormous sword and fights monstrous lost souls called Hollows.",
        "His friends include a quiet giant and an archer from a rival clan of spirit hunters.",
        "Ichigo Kurosaki and Rukia Kuchiki.",
    ], "Tite Kubo's sense of style, from the character designs to the swords, made it one of the 'big three' shōnen series of "
       "the 2000s. The Soul Society arc is the classic. Thousand-Year Blood War finally adapts the ending with much bigger "
       "animation."),
    _p("game", "Grand Theft Auto V", 2013, "Rockstar North", ["gta v", "gta 5", "grand theft auto 5", "gtav", "gta5"], [
        "An open-world action game released in 2013.",
        "It was made by Rockstar North, a Scottish studio, and became one of the best-selling games ever.",
        "You can switch between three criminals at almost any moment.",
        "It is set in Los Santos, a satire of Los Angeles.",
        "Its online mode has kept players busy for more than a decade.",
        "Michael, Franklin and Trevor plan heists together.",
    ], "Its version of Los Angeles is packed with satire of celebrity, tech and politics, and the heists are its best "
       "missions. It has been released on three console generations. Its sequel became one of the most anticipated games "
       "of all time."),
    _p("movie", "Barbie", 2023, "Greta Gerwig", [], [
        "A comedy film from 2023 based on a toy.",
        "It was directed by Greta Gerwig and was the highest-grossing film of its year.",
        "A doll in a perfect pink world suddenly starts thinking about death.",
        "She travels to Los Angeles with her boyfriend, who discovers the patriarchy.",
        "It came out the same weekend as Oppenheimer, and the two were paired as one event.",
        "Margot Robbie and Ryan Gosling, whose big number is 'I'm Just Ken'.",
    ], "Greta Gerwig turned a toy commercial into a comedy about growing up and what is expected of women, with sets built "
       "by hand in bright pink. Ryan Gosling's Ken nearly steals it. America Ferrera's speech became one of the year's most "
       "shared scenes."),
    _p("tv", "Seinfeld", 1989, "Larry David", [], [
        "A sitcom that premiered in 1989 and ran for nine seasons.",
        "It was created by Larry David and the stand-up comedian it is named after.",
        "Often called 'a show about nothing', it follows four friends on Manhattan's Upper West Side.",
        "A soup seller refuses to serve customers who break his rules.",
        "One episode is spent entirely waiting for a table at a Chinese restaurant.",
        "Jerry, George, Elaine and Kramer.",
    ], "Its rule was 'no hugging, no learning', and its characters never grow, which is exactly why it still works. Its "
       "phrases, from 'yada yada' to 'double dipping', entered everyday speech. Start with season four, its best."),
    _p("movie", "Your Name", 2016, "Makoto Shinkai", ["kimi no na wa"], [
        "An animated film released in Japan in 2016.",
        "It was written and directed by Makoto Shinkai and became one of the highest-grossing anime films ever.",
        "A girl in a small mountain town and a boy in Tokyo start waking up in each other's bodies.",
        "They leave each other notes on their phones and on their skin.",
        "A comet passing the Earth turns out to matter more than either of them knows.",
        "Taki and Mitsuha, with songs by the band Radwimps.",
    ], "It starts as a body-swap comedy and turns into something bigger halfway through, which is best not spoiled. Makoto "
       "Shinkai's skies and city lights look almost photographic. Weathering With You and Suzume are his follow-ups."),
    _p("game", "Disco Elysium", 2019, "ZA/UM", [], [
        "A role-playing game released in 2019 with almost no combat.",
        "It was made by the Estonian studio ZA/UM.",
        "A detective wakes up in a wrecked hostel room with total amnesia and a terrible hangover.",
        "The voices in his head are his own skills, and they argue with him and with each other.",
        "A body hangs from a tree behind the hostel in the city of Revachol.",
        "Harry Du Bois and his patient partner Kim Kitsuragi investigate a murder.",
    ], "It is a detective novel you play, with some of the best writing in any game, and failing a check is often more "
       "interesting than passing it. Politics, grief and very dark comedy run through it. The Final Cut edition adds full "
       "voice acting."),
    _p("tv", "The Wire", 2002, "David Simon", [], [
        "A crime drama series that premiered in 2002 and ran for five seasons.",
        "It was created by David Simon, a former police reporter, for HBO.",
        "Each season looks at a different part of one American city: the drug trade, the docks, city hall, schools and the newspaper.",
        "Detectives listen in on drug dealers who use payphones and pagers.",
        "A shotgun-carrying stick-up man who robs only drug dealers whistles 'The Farmer in the Dell'.",
        "Jimmy McNulty, Stringer Bell and Omar Little, in Baltimore.",
    ], "It is often called the greatest TV drama ever made, because it treats a whole city as its main character and shows how "
       "institutions grind people down. It is slow at first and asks for attention. Season four, about four schoolboys, is "
       "the one people remember."),
    _p("book", "Harry Potter and the Philosopher's Stone", 1997, "J. K. Rowling",
       ["harry potter", "harry potter and the sorcerers stone", "philosophers stone", "sorcerers stone"], [
        "A fantasy novel for children first published in 1997.",
        "Its author wrote much of it in Edinburgh cafés, and it was turned down by several publishers.",
        "Letters start arriving for an orphan who sleeps in a cupboard under the stairs.",
        "A half-giant gamekeeper tells him he is a wizard.",
        "At school he is sorted into a house by a talking hat.",
        "Hogwarts, Ron, Hermione and the boy who lived.",
    ], "The first book of a series that got a generation reading, it is short, funny and full of small inventions, from "
       "Chocolate Frog cards to moving staircases. Later books get much darker. In the US it was published as the "
       "Sorcerer's Stone."),
    _p("movie", "Pulp Fiction", 1994, "Quentin Tarantino", [], [
        "A crime film from 1994, told out of chronological order.",
        "It won the Palme d'Or at Cannes, and its director shared the Oscar for its screenplay.",
        "Two hitmen talk about what a Quarter Pounder is called in France.",
        "A gangster's wife overdoses, and her date has to stab a needle of adrenaline into her heart.",
        "Nobody ever sees what glows inside the briefcase.",
        "John Travolta and Uma Thurman dance the twist at Jack Rabbit Slim's.",
    ], "Quentin Tarantino built a crime film out of conversations about burgers, foot massages and miracles, and shuffled the "
       "order so the ending comes in the middle. It revived John Travolta's career and was copied for years. The dialogue "
       "is the reason to watch."),
    _p("anime", "One-Punch Man", 2015, "Madhouse", ["one punch man", "onepunchman", "opm"], [
        "A superhero comedy anime series that began in 2015.",
        "Its first season was animated by Madhouse, from a webcomic by ONE redrawn by Yusuke Murata.",
        "A bald hero has become so strong that every fight ends at once, and he is bored.",
        "He trained by doing 100 push-ups, 100 sit-ups, 100 squats and a 10-kilometre run every day.",
        "His cyborg disciple talks in long, earnest speeches.",
        "Saitama and Genos work for the Hero Association.",
    ], "It is a parody of superhero and shōnen stories that is also a great example of them, with huge, lavish fights that "
       "end in a single blow. The joke never wears out because the side characters care so much. Season one is the one "
       "to watch first."),
    _p("game", "Outer Wilds", 2019, "Mobius Digital", [], [
        "A space exploration game released in 2019.",
        "It was made by Mobius Digital and published by Annapurna Interactive.",
        "You are a new astronaut in a tiny solar system, and the sun explodes after 22 minutes.",
        "Each time, you wake up at the start of the loop with only what you have learned.",
        "Everything there is to find is there from the start; you progress through knowledge, not upgrades.",
        "Your village is on Timber Hearth, and an ancient race called the Nomai left writing everywhere.",
    ], "It is a mystery you solve by being curious, and the less you know going in the better. Many players call it the best "
       "game they have played and refuse to say why. Do not look anything up."),
    _p("movie", "The Princess Bride", 1987, "Rob Reiner", [], [
        "A fantasy adventure comedy film from 1987, framed as a story read to a sick boy.",
        "It was directed by Rob Reiner, from a novel by William Goldman, who also wrote the screenplay.",
        "A farm boy whose only reply is 'As you wish' leaves to make his fortune while his love waits.",
        "A Spanish swordsman has spent 20 years looking for the six-fingered man who killed his father.",
        "A battle of wits is fought over two goblets of wine, one of them poisoned.",
        "Westley, Buttercup and Inigo Montoya.",
    ], "It was not a big hit in cinemas and became a classic on home video, with lines people quote to this day. It manages "
       "to be a sincere fairy tale and a parody of one at the same time. The novel adds even more jokes."),
    _p("album", "Purple Rain", 1984, "Prince and the Revolution", [], [
        "A pop and rock album released in 1984, the soundtrack to a film.",
        "Its singer starred in the film it came from, about a young musician in Minneapolis.",
        "It spent 24 weeks at number one on the US album chart.",
        "Its songs include 'When Doves Cry' and 'Let's Go Crazy'.",
        "Its title track was first recorded at a live show and ends with a long guitar solo.",
        "Prince and the Revolution's album.",
    ], "Prince mixed rock, funk and gospel into nine songs with almost no weak spots. 'When Doves Cry' famously has no bass "
       "line. The title track closes the album and the film, and its final minutes are some of his best guitar playing."),
    _p("anime", "Dragon Ball Z", 1989, "Toei Animation", ["dbz"], [
        "An action anime series that began in 1989, the sequel to an earlier series.",
        "It was animated by Toei Animation, from Akira Toriyama's manga.",
        "A martial artist who was sent to Earth as a baby learns he belongs to a warrior race of aliens.",
        "Fights can last for many episodes, with characters powering up while they shout.",
        "Gathering seven magic orbs summons a wish-granting serpent called Shenron.",
        "Goku, Vegeta and Gohan, and the Super Saiyan transformation.",
    ], "For many fans around the world it was their first anime, shown on afternoon TV. Akira Toriyama's clear, bold designs "
       "shaped decades of action manga. Dragon Ball Z Kai trims the filler if the original feels too long."),
)
