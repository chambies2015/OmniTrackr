"""The OmniTrackr Daily puzzle bank, written by the editors.

One entry per day, in order, starting on daily.EPOCH. Each puzzle has six clues
that go from vague to obvious; a clue never contains a word of the answer, and
tests check that. The note is shown once the puzzle is over and on its archive
page, so it is written to be worth reading on its own.

To add puzzles, append to PUZZLES. Never reorder or edit the answer of an entry
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
)
