"""Games season guides for /new-releases: the winter releases worth planning around.

Same fields as the guides in release_guides.py (that module adds these to GUIDES). A games
season guide has ``focus: "games"``, like the anime and TV season guides: its sections are
all game picks, grouped by kind of game, and it is never the "current" guide on Release
Radar. Games already written up in the broader winter guide (winter-2026-27) stay there and
are only mentioned in ``also`` here.
"""

GUIDES = {
    "winter-2027-games": {
        "name": "Winter 2027 games: the new releases worth playing from January to March",
        "period": "January to March 2027",
        "eyebrow": "GAMES RELEASE GUIDE",
        "hub_label": "Winter 2027 games",
        "focus": "games",
        "search_title": "Winter 2027 games: Stranger Than Heaven, Metro 2039, Tomb Raider, Until Dawn 2 and more",
        "summary": ("Fourteen winter 2027 games worth playing, from Stranger Than Heaven, Metro 2039 and Tomb Raider "
                    "to Terranigma and Witchbrook, with what to play first."),
        "published": "2026-11-20",
        "reviewed": "2026-11-20",
        "starts": "2027-01-01",
        "ends": "2027-03-31",
        "lead": [
            "The first three months of 2027 are the most crowded start to a year for games in a long time. Grand "
            "Theft Auto VI came out on November 19, and Microsoft said openly that it moved Fable to February to give "
            "it a window of its own. Between January 14 and February 12 there are fifteen games on our list, and "
            "three of them come out on the same day, February 4.",
            "This guide is the short version. We went through the publishers' announcements as they stood on "
            "November 20 and picked fourteen games: six big releases, four remakes and remasters, and four smaller "
            "games that are easy to miss in a season this busy. For each one we say when it comes out and on what, "
            "what it is, what to play first if anything, and the thing most likely to put you off. None of them are "
            "out yet, so read these as bets, not reviews. We say where we are guessing.",
            "A few housekeeping notes. Dates are for the US, and the platforms are the ones announced so far. Three "
            "of the season's biggest games, Metroid Ravenous, Persona 4 Revival and Fable, are written up in our "
            "broader winter releases guide, so they are only listed at the bottom of this one. God of War Laufey, "
            "which was due on February 16, moved to May 20 on November 4 and has left the winter altogether.",
        ],
        "sections": [
            {
                "format": "games",
                "id": "big",
                "label": "Big releases",
                "heading": "Six big games, and what each one asks of you",
                "intro": [
                    "These are the six games most people will be talking about this winter. Four of them continue "
                    "long-running series, one rebuilds a game from 1996, and one is Owlcat's second Warhammer 40,000 "
                    "role-playing game. Until Dawn 2 is the only one tied to a single console. Two of them, Stranger "
                    "Than Heaven and Wo Long 2, are on Game Pass from the day they come out.",
                ],
                "picks": [
                    {"kind": "game", "title": "Stranger Than Heaven", "year": 2027, "creator": None,
                     "date": "2027-01-15",
                     "released": "PS5, Xbox Series X|S, PC · on Game Pass from launch",
                     "why": "Ryu Ga Gotoku Studio, the team behind Yakuza and Like a Dragon, goes back to 1915. Makoto "
                            "Daito, the son of an American father and a Japanese mother, stows away from San Francisco "
                            "to Japan and makes his name first as a singer and showman, then in the underworld, beside "
                            "his oldest friend and biggest rival, Yu Shinjo.",
                     "note": "PC Gamer calls it a Yakuza prequel, and that is the draw for fans: this is the story of "
                             "how the Tojo Clan, the crime family at the center of every Yakuza game, began, told over "
                             "about fifty years and five places in Japan. Each era is its own place to explore, which "
                             "plays to the studio's strength. Nobody is better at making a few city blocks feel lived "
                             "in, full of bars, arcades and side stories. The tone is meant to be closer to straight "
                             "drama than the series' usual mix of crime saga and slapstick, and the fighting is new, "
                             "built around targeting an enemy's limbs rather than the combo brawling of the older games "
                             "or the turn-based battles of the recent Like a Dragon ones. Music runs through all of it. "
                             "Makoto's voice is what gets him noticed, Snoop Dogg and Ado are among the artists on the "
                             "theme song, and Tupac Shakur appears as a character called Amaru, built from archival "
                             "footage and photographs with his estate's permission and, the studio says, without AI.",
                     "first": "Nothing. It is set decades before Yakuza 0, so it works as a first RGG game. If you want "
                              "to try the studio before January, Yakuza 0 (2015) is still the usual recommendation.",
                     "caveat": "RGG games are long and talky, with a lot of cutscenes between the fights, and the new "
                               "combat system is untested. Nobody knows yet how much of the series' comedy survives "
                               "the more serious tone."},
                    {"kind": "game", "title": "Warhammer 40,000: Dark Heresy", "year": 2027, "creator": None,
                     "date": "2027-01-28",
                     "released": "PS5, Xbox Series X|S, PC (Steam, GOG, Epic) · Switch 2 later",
                     "why": "Owlcat's second Warhammer 40,000 role-playing game puts you in the Inquisition. You start "
                            "as a lowly acolyte in the Calixis Sector and gather a war band of zealots and outcasts to "
                            "investigate crimes and heresy across it.",
                     "note": "Owlcat makes big, branching computer role-playing games in the tradition of Baldur's Gate: "
                             "two Pathfinder games, and Warhammer 40,000: Rogue Trader in 2023, which won over a lot of "
                             "players who had never cared about the setting. Dark Heresy takes its name and its corner "
                             "of the galaxy from the 2008 tabletop role-playing game, and the premise suits a story-led "
                             "game better than most Warhammer does. You are not commanding armies. You are a small team "
                             "of investigators deciding who is guilty, who is a heretic, and how far you are willing to "
                             "go to find out, in a setting where the authorities you work for are often worse than the "
                             "people you are hunting. Owlcat says the tactical combat has been revamped since Rogue "
                             "Trader, whose fights were turn-based. Players who bought a Founder's Pack can try a beta "
                             "that closes on January 7.",
                     "first": "Nothing, though Rogue Trader (2023) shows what Owlcat does with the setting. It is a "
                              "separate story and a very long game.",
                     "caveat": "Owlcat's games have launched with a lot of bugs before, Rogue Trader included, and were "
                               "in much better shape a few months later. If you can wait for the first patches, wait. "
                               "The Switch 2 version has no date yet."},
                    {"kind": "game", "title": "Until Dawn 2", "year": 2027, "creator": None,
                     "date": "2027-01-28",
                     "released": "PS5",
                     "why": "A new horror story in which your choices decide who lives. Dead True, a team of "
                            "ghost-hunting YouTubers who fake their footage, travel to Akishima Island in the South "
                            "Pacific, where a luxury resort shut down in the 1970s. Part of the story goes back twelve "
                            "years, to Blackwood Sanatorium.",
                     "note": "The first Until Dawn, in 2015, turned a slasher film into something you play: eight friends "
                             "at a mountain lodge, any of whom could die by the end, with a psychiatrist, Dr. Hill, "
                             "played by Peter Stormare, interrupting between chapters to ask what scares you. It was "
                             "remade for PS5 in 2024. The sequel comes from a different team. Firesprite, Sony's "
                             "studio in Liverpool, is making it, and the story was written with AdHoc Studio, the team "
                             "behind Dispatch, which is the best sign yet for the writing. Dacre Montgomery, Billy in "
                             "Stranger Things, plays Owen, and Stormare's Dr. Hill comes back. A cast of fake ghost "
                             "hunters is a good joke for a horror game, because everyone in it has spent years "
                             "pretending to be scared. Like the original, it is at its best played with friends on the "
                             "sofa, passing the controller and arguing about every choice.",
                     "first": "Nothing. The 2015 original, or its 2024 remake, is worth playing for its own sake, but "
                              "Dr. Hill is the only link announced so far.",
                     "caveat": "The original's quick-time events and fixed camera angles are part of the style, and some "
                               "players find them dated. It is PS5 only, with no PC version announced."},
                    {"kind": "game", "title": "Metro 2039", "year": 2027, "creator": None,
                     "date": "2027-02-04",
                     "released": "PS5, Xbox Series X|S, PC",
                     "why": "The fourth Metro game. It is 2039, the last survivors of a nuclear war have spent "
                            "twenty-five years in the tunnels under a poisoned Moscow, and a leader called Hunter has "
                            "united them under a regime, the Novoreich, that rules through propaganda and fear.",
                     "note": "4A Games' Metro series, inspired by Dmitry Glukhovsky's novels, has always been a shooter "
                             "where the atmosphere does as much work as the guns: a gas mask whose glass cracks, a "
                             "lighter held up in the dark, ammunition you can spend as money or fire. Metro Exodus in "
                             "2019 took the series above ground and across Russia on a train, and it was the best of "
                             "the three. Metro 2039 goes back underground with a new lead, the Stranger, a recluse "
                             "haunted by violent waking nightmares who leaves his exile for the one place he swore "
                             "he would never go back to. A Metro that has finally been united under one ruler is a new "
                             "situation for the series, which has always been about rival stations. Exodus's weapon "
                             "customization, stripping guns down and rebuilding them "
                             "from parts, comes back.",
                     "first": "Metro Exodus (2019) is the best place to start and runs well on current consoles. The "
                              "first two games are collected in Metro Redux.",
                     "caveat": "Metro games are bleak and slow, with long stretches of creeping through the dark and "
                               "very little humor. On the harder settings, ammunition and gas mask filters run out "
                               "fast."},
                    {"kind": "game", "title": "Tomb Raider: Legacy of Atlantis", "year": 2027, "creator": None,
                     "date": "2027-02-12",
                     "released": "PS5, Xbox Series X|S, Switch 2, PC · $59.99, or $69.99 with 48 hours' early access",
                     "why": "A complete reimagining of the first Tomb Raider, from 1996, rebuilt in Unreal Engine 5. "
                            "Lara Croft goes after an Atlantean artifact through Peru, Greece, Egypt and an island "
                            "shrouded in myth.",
                     "note": "The 1996 original is one of the founding games of 3D action adventure, and it has aged in "
                             "all the ways early 3D games do, with grid-based jumps and tank controls. Crystal "
                             "Dynamics, which has made Tomb Raider since 2006, is rebuilding it with Flying Wild Hog, "
                             "the Polish studio behind the Shadow Warrior reboots, and Amazon Games is publishing. The "
                             "rooms of Peru's Lost Valley have been opened up into connected areas, Lara has a grappling "
                             "hook, the cog puzzle comes back in a new form, and the story has been expanded to tie into "
                             "the rest of her life. For anyone who first met Lara in the 2013 reboot, which made her a "
                             "survivor rather than an adventurer, this is a chance to see the confident, wisecracking "
                             "version she started as, with the dinosaur still waiting in the valley.",
                     "first": "Nothing. Tomb Raider I-III Remastered (2024) has the original game if you want to "
                              "compare the two.",
                     "caveat": "It slipped once already, from 2026. The Deluxe Edition's 48-hour head start also means "
                               "videos and spoilers will be out before the standard edition unlocks."},
                    {"kind": "game", "title": "Wo Long 2: Wings of Ember", "year": 2027, "creator": None,
                     "date": "2027-03-04",
                     "released": "PS5, Xbox Series X|S, Switch 2, PC · on Game Pass from launch · $69.99",
                     "why": "Team Ninja's sequel to Wo Long: Fallen Dynasty, a demanding action game set during China's "
                            "Three Kingdoms period, with demons. This time the fighting spreads into open fields that "
                            "recreate the Battle of Changban and the Battle of Red Cliffs.",
                     "note": "Team Ninja makes hard action games: Ninja Gaiden, the two Nioh games, and Wo Long in "
                             "2023, the most aggressive of them, built around deflecting attacks rather than dodging "
                             "them. The sequel keeps the morale system, which makes you stronger the better you fight, "
                             "and adds what the first one lacked: open fields in place of linear levels, fights in the "
                             "air, and the chance to recruit enemy officers to your side. The Three Kingdoms is familiar "
                             "ground for anyone who played Dynasty Warriors, Koei Tecmo's other long-running series. A "
                             "free alpha demo in September let players fight through the Changban field with Liu Bei's army, holding off "
                             "Cao Cao's pursuers.",
                     "first": "Wo Long: Fallen Dynasty (2023) teaches you the deflect-or-die combat. The sequel shouldn't "
                              "need it for the story.",
                     "caveat": "It is hard, in the way of Dark Souls, and bosses will kill you many times. The Digital "
                               "Deluxe Edition's season pass covers two expansions that are not due until August and "
                               "October 2027."},
                ],
            },
            {
                "format": "games",
                "id": "remakes",
                "label": "Remakes",
                "heading": "Four old games made new, two of them from 1995",
                "intro": [
                    "Old games are a big part of this winter. We picked these four because most players never had a "
                    "fair chance at the originals. Terranigma never came out in North America, Romancing SaGa 3 took "
                    "twenty-four years to leave Japan, and Muramasa was stuck on the Wii and the Vita. Danganronpa 2x2 "
                    "is the odd one: a new story built inside an old game.",
                ],
                "picks": [
                    {"kind": "game", "title": "Danganronpa 2x2", "year": 2027, "creator": None,
                     "date": "2027-01-14",
                     "released": "PS5, Xbox Series X|S, Switch 2, Switch, PC",
                     "why": "A new murder mystery built on Danganronpa 2: Goodbye Despair. The same students are "
                            "stranded on the same tropical Jabberwock Island and forced into the same killing game, but "
                            "the victims and the culprits are new. The original game comes with it, with updated art.",
                     "note": "Danganronpa is a visual novel series about high school students trapped by Monokuma, a "
                             "sadistic bear, who makes them kill each other and then hold a class trial to find the "
                             "killer. Get the verdict right and only the murderer is executed. Get it wrong and everyone "
                             "else is. Goodbye Despair, from 2012, is the fan favorite, with the series' best cast and "
                             "its best cases. A second set of murders on the same island is an unusual idea, and a "
                             "clever one: people who know every twist of the original get to be surprised by it again, "
                             "and new players can play the original first and then the new version. Spike Chunsoft publishes it, and Gemdrops made it.",
                     "first": "Danganronpa: Trigger Happy Havoc (2010). Goodbye Despair spoils it, and 2x2 is built on "
                              "Goodbye Despair, which is included.",
                     "caveat": "It is a lot of reading, and the minigames inside the trials can be fiddly. The series is "
                               "gory and its humor is often crude."},
                    {"kind": "game", "title": "Terranigma", "year": 1995, "creator": None,
                     "date": "2027-01-14",
                     "released": "PS5, Xbox Series X|S, Switch 2, Switch, PC · physical editions from $39.99",
                     "why": "Quintet's 1995 action role-playing game, released for the Super Nintendo in Japan and "
                            "Europe but never in North America until now. A boy named Ark opens a forbidden box, his "
                            "village freezes, and he has to bring the world back to life, first the continents, then "
                            "plants and animals, then people.",
                     "note": "Terranigma is the last of a loose trilogy Quintet made for the Super Nintendo, after Soul "
                             "Blazer and Illusion of Gaia, and the most ambitious of the three. Its second half takes "
                             "Ark across a version of our own Earth as humanity rebuilds, and the towns you help grow "
                             "and change as the story moves forward through history. For players in Europe it was one "
                             "of the great games of the 16-bit era, and for players in America it has been a name "
                             "heard about for thirty years. This release, from Clear River Games, adds the comforts "
                             "people now expect from an old game: a rewind button, saving anywhere, a quick magic button "
                             "and a CRT filter. A new Arranged Mode makes magic stronger and adds a minimap. The $199.99 "
                             "Gaia Edition comes with a replica of the box Ark opens.",
                     "first": "Nothing. Soul Blazer and Illusion of Gaia share its themes, not its story.",
                     "caveat": "It is a thirty-year-old game with modern options added, not a remake. The fighting is "
                               "simple, and some puzzles assume you have a guide open, as games of the period often "
                               "did."},
                    {"kind": "game", "title": "Romancing SaGa 3: Destinies United", "year": 2027, "creator": None,
                     "date": "2027-02-04",
                     "released": "Switch 2, Switch, PS5, Xbox Series X|S, PC (Steam on February 5) · $59.99",
                     "why": "A full 3D remake of Square's 1995 role-playing game. You choose one of eight heroes and set "
                            "off in whatever direction you like, with more than twenty companions who can join you on "
                            "the way.",
                     "note": "The SaGa games are the strangest of Square's role-playing series. There is no fixed path. "
                             "You choose where to go, and the story assembles itself from what you do, a structure the "
                             "remake calls the Free Scenario System. Characters learn new skills in sudden flashes of "
                             "inspiration in the middle of a fight. Romancing SaGa 3 sold more than a million copies in "
                             "Japan but didn't come to the West until a remaster in 2019. This version is from Square "
                             "Enix and Xeen, the pairing that remade Romancing SaGa 2 as Revenge of the Seven in 2024, "
                             "and it rebuilds the game in 3D with voiced scenes, overhauled combat and a choice of "
                             "difficulty. It keeps the odd parts that fans are fond of, including a war mode and a "
                             "trading business you can run on the side. It is also that rare game that moved its release "
                             "forward: it was due on February 16 and now comes out twelve days early.",
                     "first": "Nothing. If you want to know whether SaGa suits you, Romancing SaGa 2: Revenge of the Seven "
                              "(2024) is the most approachable game in the series.",
                     "caveat": "SaGa games are confusing on purpose and explain very little. If you like a clear main "
                               "quest, the freedom can feel like being lost."},
                    {"kind": "game", "title": "Muramasa: Revenant Blades", "year": 2027, "creator": None,
                     "date": "2027-02-04",
                     "released": "Switch 2, PS5, Switch, PC",
                     "why": "Vanillaware's hand-painted 2D sword-fighting game, set in Genroku-era Japan, remastered "
                            "with its four extra stories folded in. That makes six heroes in all, among them Momohime and "
                            "Kisuke from the original.",
                     "note": "Vanillaware's games are painted by hand and animated in layers, and they look like nothing "
                             "else: Odin Sphere, Dragon's Crown, 13 Sentinels and Unicorn Overlord. Muramasa: The Demon "
                             "Blade came out on the Wii in 2009 and returned on the PlayStation Vita as Muramasa "
                             "Rebirth, with a set of downloadable side stories called Genroku Legends. Revenant Blades "
                             "puts all of it in one game, adds new English voices, an illustration gallery, a character "
                             "viewer and a replay mode, and keeps a classic mode with the Vita versions and sharper "
                             "graphics. The fighting is fast and easy to pick up, with parries and skills you master by "
                             "using them, and you forge more than a hundred swords as you go.",
                     "first": "Nothing. If you played Muramasa Rebirth on the Vita, the Genroku Legends stories are the "
                              "part you are most likely to have missed.",
                     "caveat": "The combat is shallow on the default difficulty, and you cross the same areas many times. "
                               "It is a game for looking at as much as for playing."},
                ],
            },
            {
                "format": "games",
                "id": "smaller",
                "label": "Smaller games",
                "heading": "Four smaller games to fit between the big ones",
                "intro": [
                    "These four come from smaller studios with less marketing behind them, and in a season this "
                    "crowded they are the easiest to miss. Two of them, Cassette Beasts 2002 and No Rest for the "
                    "Wicked, only have a month so far.",
                ],
                "picks": [
                    {"kind": "game", "title": "Witchbrook", "year": 2027, "creator": None,
                     "date": "2027-01-28",
                     "released": "PC ($25 on Steam), PS5, Xbox Series X|S, Switch 2, Switch",
                     "why": "A life sim about a student at Witchbrook College, learning magic and making a life in the "
                            "town of Mossport around the lessons: friends, jobs and a home to decorate.",
                     "note": "Chucklefish published Stardew Valley in 2016 and made Starbound and the Wargroove games, "
                             "and Witchbrook, made with Robotality, is the game it has been showing off since 2017. It "
                             "was due in 2025, then 2026. The idea takes one line to explain: Stardew Valley's town life "
                             "with a school timetable in place of a farm. You go to classes, learn spells, and use them "
                             "around town, and the pixel art is some of the most detailed the genre has seen. If you "
                             "want one gentle game for the cold months, this is the one we would pick, and it costs $25 "
                             "on Steam.",
                     "caveat": "Three release dates in a row make us cautious, though the date was confirmed at "
                               "Nintendo's Indie World show in October. Chucklefish hasn't said much lately about "
                               "playing with friends, so don't buy it for that until it is confirmed."},
                    {"kind": "game", "title": "Demi and the Fractured Dream", "year": 2027, "creator": None,
                     "date": "2027-02-27",
                     "released": "PS5, Xbox Series X|S, Switch 2, Switch, PC",
                     "why": "An action adventure from Yarn Owl, published by Annapurna Interactive. Demi, one of the "
                            "Voidsent, travels the world of Somnus, through a Desert Kingdom and a Marsh Kingdom, to "
                            "slay three Accursed Beasts before their awakening ends the world.",
                     "note": "Its developers have named The Legend of Zelda, Okami and Jak and Daxter as influences, and "
                             "the previews describe dungeons and puzzles in the Zelda manner. Annapurna's name on a game "
                             "usually means a distinct look and a story worth paying attention to. It published What "
                             "Remains of Edith Finch, Outer Wilds and Stray. Demi was due in 2026 and now comes out at "
                             "the end of February, four days after Fable. If you have wanted a game like Zelda that "
                             "isn't Zelda, this is the one to watch this winter.",
                     "caveat": "It is the game here with the least to go on: a few previews and some trailers. We will "
                               "know more once people outside the press have played it."},
                    {"kind": "game", "title": "Cassette Beasts 2002", "year": 2027, "creator": None,
                     "date": "2027-03-01", "month_only": True,
                     "released": "PS5, Xbox Series X|S, Switch 2, PC · the day hasn't been set",
                     "why": "A sequel to the 2023 monster-collecting game in which you record monsters on cassette tapes "
                            "and turn into them. This one is set in 2002, in a quiet suburb on the outer edge of London "
                            "and in Nodnol, a remixed version of the city in the 2000s.",
                     "note": "Cassette Beasts was one of the best games inspired by Pokémon in years, because it changed "
                             "the part that matters. You don't send monsters out to fight. You become them, and any two "
                             "can be fused into a new creature. The sequel has more than 250 beasts and over 50,000 "
                             "possible fusions, a 3D camera behind the player in place of the old view from above, "
                             "trading, co-op and one-on-one battles, and Neil Newbon, Astarion in Baldur's Gate 3, in "
                             "the cast. It is set in 2002, so nobody has a smartphone. Bytten Studio calls it a good entry point to the "
                             "series, and Raw Fury publishes it.",
                     "first": "Nothing. Cassette Beasts (2023) is cheap now if you want to try the idea first.",
                     "caveat": "Only the month is set. We will add the day when Raw Fury announces it. Its battles "
                               "are turn-based, which won't suit anyone hoping for action."},
                    {"kind": "game", "title": "No Rest for the Wicked", "year": 2024, "creator": None,
                     "date": "2027-03-01", "month_only": True,
                     "released": "PS5 and PC first · the full release, after early access on PC since April 2024",
                     "why": "Moon Studios' painterly action role-playing game leaves early access and comes to "
                            "PlayStation 5 at the same time. You play a Cerim, sent to an island overrun by a plague "
                            "called the Pestilence.",
                     "note": "Moon Studios made Ori and the Blind Forest and Ori and the Will of the Wisps, two of the "
                             "best-looking platformers ever made. No Rest for the Wicked brings that hand-painted look "
                             "to an action role-playing game seen from above, with slow, weighty fights closer to Dark "
                             "Souls than to Diablo. The early access version was praised for its art and combat and "
                             "criticized for its performance when it first came out, and it has changed a lot since. "
                             "The studio moved the full release from October after playtesting, saying the game wasn't "
                             "quite there yet and that it wanted more time on performance and the class system. That is "
                             "a better reason to delay than most, and the March release is the version to wait for if "
                             "you skipped early access. A last closed beta runs in December.",
                     "caveat": "Only the month is set, PS5 and PC come first, and the Xbox Series and Switch 2 versions "
                               "have no date. It is hard and asks for patience in its first hours."},
                ],
            },
        ],
        "also": [
            ("Metroid Ravenous (January 28, Switch 2).",
             "A new 2D Metroid from MercurySteam and Nintendo. We wrote it up in our broader winter releases guide."),
            ("Persona 4 Revival (February 18).",
             "A full remake of the 2008 Persona 4, the murder mystery set over a year at a country high school, also in "
             "the winter guide."),
            ("Fable (February 23).",
             "Playground Games' new start for the fairy-tale role-playing series, moved from 2026 to keep clear of "
             "Grand Theft Auto VI. Also in the winter guide."),
            ("Titan Quest II (January 19).",
             "Grimlore Games' sequel to the 2006 mythological action RPG leaves early access, on PC, PS5 and Xbox "
             "Series."),
            ("Usual June (January 20, Xbox Series and PC).",
             "Finji's supernatural action game, from the publisher of Night in the Woods and Tunic. It was due in "
             "October."),
            ("Tropico 7 (January 28).",
             "The island dictatorship city-builder returns, on PC, PS5, Xbox Series and Switch 2."),
            ("Fate/Extra Record (January 28).",
             "A remake of the 2010 PSP role-playing game Fate/Extra, on PC, PS5, PS4, Switch and Switch 2."),
            ("Hyrule Warriors: Age of Calamity, Definitive Edition (February 25, Switch 2).",
             "The Breath of the Wild prequel from Koei Tecmo and Nintendo, rereleased for Switch 2."),
            ("Trine 6: Together in Time (March 4).",
             "Frozenbyte's co-op puzzle platformer series continues, on PC and every current console."),
            ("Lords of the Fallen II (first three months of 2027).",
             "Hexworks' dark fantasy action RPG, moved from autumn 2026. CI Games has only said the first quarter."),
            ("God of War Laufey (now May 20).",
             "Once due on February 16, it was delayed to May on November 4, so it has left this guide."),
        ],
        "plan_heading": "A plan for the winter",
        "plan": [
            "Clear some time in mid-January. Danganronpa 2x2 and Terranigma both come out on Thursday the 14th and "
            "Stranger Than Heaven the next day, and RGG's games run to dozens of hours. If you only start one in "
            "January, make it the one you are most likely to finish before February arrives.",
            "January 28 is the busiest day of the season. Until Dawn 2, Dark Heresy, Witchbrook, Metroid Ravenous, "
            "Tropico 7 and Fate/Extra Record all come out that Thursday. Until Dawn 2 is a weekend with friends, "
            "Witchbrook is something to dip into, and Dark Heresy is the one that asks for weeks, so you can "
            "reasonably play two of them at once, but not three.",
            "February is the crunch. Metro 2039, Romancing SaGa 3 and Muramasa arrive on the 4th, Tomb Raider on the "
            "12th, Persona 4 Revival on the 18th, Fable on the 23rd and Demi on the 27th. Few people will play all of "
            "that in a month, so pick one long game and one short one, and save the rest for spring, when prices "
            "start to fall. March is quieter so far: Wo Long 2 on the 4th, Trine 6 the same day, and Cassette Beasts "
            "2002 and No Rest for the Wicked some time in the month. We will add their days when they are set, and "
            "the date at the top of the page says when we last checked.",
        ],
        "method": [
            "Prepared by OmniTrackr with AI assistance and reviewed by the site owner before publishing. None of these "
            "games had come out when we wrote about them, so this is a guide to what we think is worth trying, not a "
            "set of reviews. We worked from the publishers' own announcements and the coverage listed below, checked "
            "each date against a second source where we could, and picked games we would recommend to a friend, with "
            "an honest note on who should skip them.",
            "Game dates move more than film or TV dates. While we were putting this guide together, God of War Laufey "
            "slipped from February to May and Romancing SaGa 3 moved forward twelve days. Where only a month has been "
            "announced, we say so. Platforms are the ones confirmed so far, and prices are given only where the "
            "publisher has announced them.",
        ],
        "related": [
            ("The best games of 2026", "/best-of/2026/games"),
            ("Resident Evil in order", "/in-order/resident-evil"),
            ("Final Fantasy VII in order", "/in-order/final-fantasy-vii"),
            ("If you liked The Last of Us", "/if-you-liked/the-last-of-us"),
            ("Winter 2027 TV premieres", "/new-releases/winter-2027-tv"),
            ("How to track games on OmniTrackr", "/game-tracker"),
        ],
        "sources": [
            ("Gematsu: Stranger Than Heaven launches January 15, 2027", "https://www.gematsu.com/2026/06/stranger-than-heaven-launches-january-15-2027"),
            ("PC Gamer: everything we know about Stranger Than Heaven", "https://www.pcgamer.com/games/action/stranger-than-heaven-guide/"),
            ("RPG Site: Warhammer 40,000: Dark Heresy release date", "https://www.rpgsite.net/news/21725-warhammer-40k-dark-heresy-release-date-ps5-xbox-seriex-x-pc-steam-epic-gog"),
            ("Gematsu: Dark Heresy launches January 28, 2027, later for Switch 2", "https://www.gematsu.com/2026/11/warhammer-40000-dark-heresy-launches-january-28-2027-for-ps5-xbox-series-and-pc-later-for-switch-2"),
            ("PlayStation Blog: Until Dawn 2 launches January 28", "https://blog.playstation.com/2026/09/03/until-dawn-2-launches-january-28/"),
            ("Gematsu: Metro 2039 launches February 4, 2027", "https://www.gematsu.com/2026/09/metro-2039-launches-february-4-2027"),
            ("GamesRadar+: Metro 2039 and a crowded February", "https://www.gamesradar.com/games/fps/metro-2039-release-date-lands-ahead-of-tomb-raider-god-of-war-laufey-persona-4-and-fable-in-an-increasingly-crowded-february/"),
            ("PlayStation Blog: Tomb Raider: Legacy of Atlantis launches February 12", "https://blog.playstation.com/2026/06/02/tomb-raider-legacy-of-atlantis-launches-feb-12-2027-on-ps5/"),
            ("Gematsu: Tomb Raider: Legacy of Atlantis adds Switch 2, delayed to February 12", "https://www.gematsu.com/2026/06/tomb-raider-legacy-of-atlantis-adds-switch-2-version-delayed-to-february-12-2027"),
            ("Gematsu: Wo Long 2: Wings of Ember launches March 4, 2027", "https://www.gematsu.com/2026/09/wo-long-2-wings-of-ember-launches-march-4-2027-alpha-demo-now-available"),
            ("Gematsu: Danganronpa 2x2 launches January 14, 2027", "https://www.gematsu.com/2026/09/danganronpa-2x2-launches-january-14-2027"),
            ("Gematsu: Terranigma launches January 14, 2027", "https://www.gematsu.com/2026/09/terranigma-launches-january-14-2027"),
            ("Game Informer: Terranigma gets its first official North American release", "https://www.gameinformer.com/2026/08/25/famed-1995-jrpg-terranigma-is-coming-to-modern-platforms-including-its-first-official"),
            ("RPG Site: Romancing SaGa 3: Destinies United announced", "https://www.rpgsite.net/news/21322-romancing-saga-3-destinies-united-release-date"),
            ("Inven Global: Romancing SaGa 3 launches 12 days earlier", "https://www.invenglobal.com/articles/28522/romancing-saga-3-destinies-united-to-launch-12-days-earlier"),
            ("PlayStation Blog: Muramasa: Revenant Blades launches February 4", "https://blog.playstation.com/2026/09/10/muramasa-revenant-blades-launches-february-4-2027/"),
            ("PC Gamer: Witchbrook delayed again, now set for 2027", "https://www.pcgamer.com/games/rpg/witchbrook-is-delayed-again-now-set-for-release-in-2027/"),
            ("Game Informer: Witchbrook gets a January release date", "https://www.gameinformer.com/2026/10/28/cozy-magical-sim-witchbrook-gets-a-january-release-date"),
            ("Gematsu: Demi and the Fractured Dream delayed to February 2027", "https://www.gematsu.com/2026/06/demi-and-the-fractured-dream-delayed-to-february-2027"),
            ("GamesRadar+: the games behind Demi and the Fractured Dream", "https://www.gamesradar.com/games/action/zelda-okami-and-jak-and-daxter-inspired-demi-and-the-fractured-dream-its-devs-tell-me-and-i-can-feel-it-after-playing-only-one-dungeon"),
            ("Gematsu: Cassette Beasts 2002 launches in March 2027", "https://www.gematsu.com/2026/08/cassette-beasts-2002-launches-in-march-2027"),
            ("Creative Bloq: Cassette Beasts 2002 in a Zone 6 suburb", "https://www.creativebloq.com/features/cassette-beasts-2002-is-pokemon-in-a-zone-6-suburb-with-no-paddington-and-not-a-wizard-in-sight"),
            ("GamingBolt: Cassette Beasts 2002 adds Neil Newbon", "https://gamingbolt.com/cassette-beasts-2002-launches-in-march-2027-includes-baldurs-gate-3-actor-neil-newbon"),
            ("Game Informer: No Rest for the Wicked 1.0 delayed to March 2027", "https://www.gameinformer.com/2026/09/01/no-rest-for-the-wicked-10-launch-delayed-to-march-2027"),
            ("Game Informer: God of War Laufey delayed to May", "https://www.gameinformer.com/2026/11/04/god-of-war-laufey-delayed-to-may"),
            ("Gematsu: Usual June delayed to January 20, 2027", "https://www.gematsu.com/2026/10/usual-june-delayed-to-january-20-2027"),
            ("Gematsu: Lords of the Fallen II delayed to Q1 2027", "https://www.gematsu.com/2026/06/lords-of-the-fallen-ii-delayed-to-q1-2027"),
            ("Shacknews: 2027 video game release dates", "https://www.shacknews.com/article/150148/2027-video-games"),
            ("Wikipedia: 2027 in video games", "https://en.wikipedia.org/wiki/2027_in_video_games"),
        ],
    },
}
