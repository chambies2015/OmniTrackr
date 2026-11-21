"""The holiday gift guide at /holidays/gifts: hand-written gift ideas for fans of each format.

Each section is one kind of fan (the nine formats OmniTrackr tracks) with four gifts.
A gift is either a title (``kind`` is one of title_pages.KINDS, so it can be matched
against a member's library and link to its title page) or a thing, such as a
turntable, with ``kind`` set to None. ``store`` and ``search`` build the Amazon
search link at render time (see affiliate.search_links); nothing here is a product
listing, and prices are left out on purpose because they change by the day.

The writing is our own. Facts were checked on the date in ``reviewed``.
"""
from __future__ import annotations

GUIDE = {
    "path": "/holidays/gifts",
    "published": "2026-11-04",
    "reviewed": "2026-11-04",
    "search_title": "Holiday gift guide for movie, TV, anime, game, music, book, manga, podcast and audiobook fans",
    "headline": "Gifts for people who have already watched, played and read everything",
    "deck": ("Thirty-six gift ideas for fans of movies, TV, anime, games, music, books, manga, podcasts and "
             "audiobooks, with what to check before you buy. Members can turn their own library into a gift list "
             "and send one link to the family."),
    "summary": ("Holiday gift ideas for fans of movies, TV, anime, games, music, books, manga, podcasts and "
                "audiobooks, with a note on what to check before you buy each one."),
    "intro": [
        "Buying for someone with strong taste is hard for a simple reason: they already own the obvious thing. The "
        "film fan has the film. The gamer bought the big release the week it came out. What is left is the stuff "
        "around it, like a better edition, the book about it, a player for it or the next one they haven't got to yet.",
        "So this guide is sorted by the kind of fan, with four ideas for each, from a stocking filler to a splurge. "
        "Every gift has a line on who it suits and a line on what to check before you buy. That second line is the "
        "useful one. It is where you find out that a game only runs on one console, or that the cheap projector "
        "needs a dark room.",
        "If you are the fan, there is a shortcut. OmniTrackr members can make a gift list from their own library: "
        "the titles they haven't started yet, the favourites they'd like to own, and anything from this page. Send "
        "the link to family, and they can mark what they're getting so nobody buys the same box set twice. You "
        "never see which ones they picked.",
    ],
    "sizes": [
        ("small", "Stocking filler", "A paperback, a single record, a small accessory."),
        ("main", "Main present", "A box set, a new game, a hardback or a figure."),
        ("big", "Splurge", "Hardware, or a collector's set for the person who has everything else."),
    ],
    "sections": [
        {
            "key": "movies",
            "kind": "movie",
            "name": "For the movie fan",
            "tagline": "Better editions, a book to read between films, and a bigger screen.",
            "intro": [
                "Most film fans stream most of what they watch, and they know that a film can vanish from a service "
                "overnight. A disc of a film they love is the one copy nobody can take back, and the good editions "
                "come with hours of extras that never make it to streaming.",
            ],
            "gifts": [
                {"id": "criterion-edition", "kind": None, "size": "main", "store": "movies-tv",
                 "name": "A Criterion Collection edition of a film they love",
                 "search": "Criterion Collection Blu-ray",
                 "why": "The Criterion Collection has been putting out restored editions of important films since 1984, "
                        "when it started on laserdisc. Most discs come with a commentary, interviews and a printed "
                        "essay, and every title has a spine number, which collectors care about more than they admit.",
                 "for": "Someone who rewatches old favourites and reads about them afterwards.",
                 "check": "Look at their shelf or their library first, because there are well over a thousand titles and "
                          "they may have the one you picked. Discs need a player, and plenty of people no longer have one."},
                {"id": "lord-of-the-rings-4k", "kind": "movie", "title": "The Lord of the Rings: The Fellowship of the Ring",
                 "year": 2001, "creator": "Peter Jackson", "size": "big", "store": "movies-tv",
                 "name": "The Lord of the Rings trilogy in 4K",
                 "search": "Lord of the Rings Motion Picture Trilogy 4K Ultra HD theatrical and extended",
                 "why": "Peter Jackson's three films were remastered for 4K in 2020, and the set has both the theatrical "
                        "cuts and the extended editions. The extended versions add roughly two hours across the "
                        "trilogy, much of it scenes that readers of the books missed in the cinema.",
                 "for": "The fan who watches all three every December anyway.",
                 "check": "It needs a 4K Blu-ray player and a 4K TV to be worth the price. The ordinary Blu-ray set of the "
                          "extended editions costs much less and still looks good."},
                {"id": "ebert-great-movies", "kind": "book", "title": "The Great Movies", "year": 2002,
                 "creator": "Roger Ebert", "size": "small", "store": "stripbooks",
                 "name": "The Great Movies by Roger Ebert",
                 "search": "Roger Ebert The Great Movies",
                 "why": "For years Roger Ebert wrote a column about films he thought had lasted, and this book collects "
                        "one hundred of those essays. Each is a few pages long, which makes it a good thing to read "
                        "before watching one of them. There are three more volumes if it goes down well.",
                 "for": "Someone who wants to see the classics but doesn't know where to start.",
                 "check": "The essays give away endings now and then. Ebert assumes you have either seen the film or "
                          "don't mind."},
                {"id": "mini-projector", "kind": None, "size": "big", "store": "electronics",
                 "name": "A small projector for movie nights",
                 "search": "portable projector native 1080p",
                 "why": "A film on a bedroom wall, or on a sheet in the garden in summer, is a different evening from the "
                        "sofa. Small projectors are much cheaper than they were, and most will take a phone or a "
                        "streaming stick.",
                 "for": "A family with kids, or anyone with a blank wall and no room for a bigger TV.",
                 "check": "Cheap projectors exaggerate their brightness and resolution. Look for native 1080p (not "
                          "\"supports 1080p\"), read reviews for how dark the room needs to be, and plan on a speaker, "
                          "because the built-in sound is usually weak."},
            ],
        },
        {
            "key": "tv",
            "kind": "tv",
            "name": "For the TV fan",
            "tagline": "Box sets to keep and a book about the shows that changed TV.",
            "intro": [
                "A series is a big commitment, so the best TV gifts are either something they already love in a "
                "form they can keep, or something that makes the watching easier. A box set also makes a good "
                "gift for someone who keeps saying they'll get round to a show.",
            ],
            "gifts": [
                {"id": "the-wire", "kind": "tv", "title": "The Wire", "year": 2002, "creator": "David Simon",
                 "size": "main", "store": "movies-tv",
                 "name": "The Wire: The Complete Series",
                 "search": "The Wire complete series Blu-ray",
                 "why": "Five seasons about Baltimore, each one looking at a different part of the city: the drug "
                        "trade, the docks, City Hall, the schools and the local paper. It rewards being watched "
                        "without a phone in your hand, which is easier with a box set and a free week.",
                 "for": "Someone who loved a slow crime drama and hasn't seen this one, or has and wants to own it.",
                 "check": "The Blu-ray set is the remastered widescreen version. The show also streams on HBO Max, so "
                          "check whether they already subscribe."},
                {"id": "revolution-was-televised", "kind": "book", "title": "The Revolution Was Televised", "year": 2012,
                 "creator": "Alan Sepinwall", "size": "small", "store": "stripbooks",
                 "name": "The Revolution Was Televised by Alan Sepinwall",
                 "search": "Alan Sepinwall The Revolution Was Televised",
                 "why": "The TV critic Alan Sepinwall on the dramas that changed American television around the turn "
                        "of the century, from Oz and The Sopranos to Breaking Bad and Mad Men, with interviews with "
                        "the people who made them.",
                 "for": "The person who reads recaps after every episode.",
                 "check": "It spoils every show it covers, on purpose. Best for someone who has watched most of them."},
                {"id": "streaming-stick", "kind": None, "size": "small", "store": "electronics",
                 "name": "A streaming stick for the spare TV",
                 "search": "4K streaming stick",
                 "why": "Older TVs in bedrooms and guest rooms often have slow apps or none at all. A streaming stick "
                        "from Amazon, Roku or Google plugs into an HDMI port and turns the old set into one you'd "
                        "actually watch a series on.",
                 "for": "Anyone whose second TV still needs a laptop and a cable.",
                 "check": "Match it to the services they use and the voice assistant they already have. A 4K stick only "
                          "helps on a 4K TV."},
                {"id": "twin-peaks-z-to-a", "kind": "tv", "title": "Twin Peaks", "year": 1990,
                 "creator": "David Lynch and Mark Frost", "size": "big", "store": "movies-tv",
                 "name": "Twin Peaks: From Z to A",
                 "search": "Twin Peaks From Z to A Blu-ray",
                 "why": "All of Twin Peaks in one box: the two original seasons, the film Fire Walk with Me, the 2017 "
                        "series The Return, and many hours of extras, including the deleted scenes known as The "
                        "Missing Pieces.",
                 "for": "The Lynch fan who has everything else.",
                 "check": "It's a collector's set and priced like one. If they only want to watch it, the separate sets "
                          "cost far less."},
            ],
        },
        {
            "key": "anime",
            "kind": "anime",
            "name": "For the anime fan",
            "tagline": "Ghibli to keep, a classic series, and a figure for the shelf.",
            "intro": [
                "Anime fans tend to know exactly what they like and exactly which edition is the right one. If you "
                "aren't sure, a classic everyone loves is safer than this season's hit, and a disc is safer than a "
                "subscription to a service they might already have.",
            ],
            "gifts": [
                {"id": "spirited-away", "kind": "anime", "title": "Spirited Away", "year": 2001, "creator": "Hayao Miyazaki",
                 "size": "main", "store": "movies-tv",
                 "name": "Spirited Away on Blu-ray",
                 "search": "Spirited Away Blu-ray GKIDS",
                 "why": "Miyazaki's film about a girl working in a bathhouse for spirits is the one to start a Ghibli "
                        "shelf with. In the US the Ghibli films stream on HBO Max, so a disc is how you keep them. "
                        "GKIDS publishes the current editions, with both the Japanese audio and the English dub.",
                 "for": "Anyone, really. It works for a ten-year-old and for their grandparents.",
                 "check": "Amazon also lists older Disney editions and pricier steelbooks of the same film. The standard "
                          "GKIDS Blu-ray is the safe choice."},
                {"id": "cowboy-bebop", "kind": "anime", "title": "Cowboy Bebop", "year": 1998,
                 "creator": "Shinichirō Watanabe", "size": "main", "store": "movies-tv",
                 "name": "Cowboy Bebop: The Complete Series",
                 "search": "Cowboy Bebop complete series Blu-ray",
                 "why": "Twenty-six episodes about a crew of broke bounty hunters on a spaceship, with Yoko Kanno's "
                        "jazz score and some of the best English dubbing ever done. People who don't watch anime "
                        "often like this one.",
                 "for": "The fan who wants the classics on the shelf, or a friend you're trying to convert.",
                 "check": "Make sure it's the 1998 anime and not the 2021 Netflix live-action series. The film, Knockin' "
                          "on Heaven's Door, is sold separately."},
                {"id": "nendoroid", "kind": None, "size": "main", "store": "toys-and-games",
                 "name": "A Nendoroid of their favourite character",
                 "search": "Nendoroid Good Smile Company",
                 "why": "Nendoroids are small posable figures with big heads, made by Good Smile Company, with "
                        "swappable faces, hands and props. There are more than two thousand of them, so most popular "
                        "characters have one.",
                 "for": "Someone with a desk, a shelf or a monitor stand that could use a small friend.",
                 "check": "Fakes are common on marketplaces. Buy from a listing sold by a known shop, and look for the "
                          "Good Smile Company logo on the box."},
                {"id": "crunchyroll-gift-card", "kind": None, "size": "small", "store": "aps",
                 "name": "A Crunchyroll gift card",
                 "search": "Crunchyroll gift card",
                 "why": "Crunchyroll carries most of each season's new anime, usually within hours of the Japanese "
                        "broadcast, and a gift card covers a few months without ads.",
                 "for": "A fan who watches each season as it airs.",
                 "check": "Some big shows stream on Netflix or Hulu instead. If they already pay for Crunchyroll, a card "
                          "simply extends their membership."},
            ],
        },
        {
            "key": "games",
            "kind": "game",
            "name": "For the gamer",
            "tagline": "The big release, a party game, a better controller and something for the table.",
            "intro": [
                "With games, the platform decides everything. Before buying, find out what they play on: PlayStation, "
                "Xbox, Switch, Switch 2 or PC. If you can't ask, a controller or a board game avoids the problem.",
            ],
            "gifts": [
                {"id": "gta-vi", "kind": "game", "title": "Grand Theft Auto VI", "year": 2026, "creator": "Rockstar Games",
                 "size": "main", "store": "videogames",
                 "name": "Grand Theft Auto VI",
                 "search": "Grand Theft Auto VI",
                 "why": "Out on November 19 for PlayStation 5 and Xbox Series X|S, thirteen years after GTA V. It will be "
                        "the game everyone is talking about over the holidays.",
                 "more": ("/new-releases/november-2026", "More in our November release guide"),
                 "for": "Adults who have been waiting for it since the first trailer.",
                 "check": "Rated M, with graphic violence, drugs and sex. There's no PC version at launch, so buy the right "
                          "console edition, and check they haven't pre-ordered it already."},
                {"id": "mario-kart-world", "kind": "game", "title": "Mario Kart World", "year": 2025, "creator": "Nintendo",
                 "size": "main", "store": "videogames",
                 "name": "Mario Kart World",
                 "search": "Mario Kart World Nintendo Switch 2",
                 "why": "The Switch 2's launch racer, with an open world between the tracks and up to 24 racers at once. "
                        "It's the easiest game to hand to a room of relatives who range from expert to never held a "
                        "controller.",
                 "for": "Families with a Switch 2, and anyone who hosts.",
                 "check": "Switch 2 only. It came bundled with some consoles at launch, so check they don't already "
                          "have it."},
                {"id": "8bitdo-controller", "kind": None, "size": "small", "store": "videogames",
                 "name": "An 8BitDo controller",
                 "search": "8BitDo Ultimate controller",
                 "why": "8BitDo's controllers work across Switch, PC and phones and cost less than the official ones. "
                        "The Ultimate models come with a charging dock, which means one fewer cable on the floor.",
                 "for": "A PC player who plays with a pad, or a Switch owner who needs a second controller.",
                 "check": "Read the box for the systems it supports. Some models are PC-only, and most won't work on "
                          "PlayStation or Xbox."},
                {"id": "wingspan", "kind": None, "size": "main", "store": "toys-and-games",
                 "name": "Wingspan, the board game",
                 "search": "Wingspan board game Stonemaier",
                 "why": "A card game about attracting birds to a nature reserve, designed by Elizabeth Hargrave and "
                        "published by Stonemaier Games in 2019. It plays like a calm engine-building video game on a "
                        "table, and it works for one to five players.",
                 "for": "The gamer in a family that wants something to play together over the break.",
                 "check": "The first game takes a while as everyone learns the rules. After that, a game is about an hour."},
            ],
        },
        {
            "key": "music",
            "kind": "album",
            "name": "For the music fan",
            "tagline": "A first turntable, a record to play on it, and headphones that shut out the room.",
            "intro": [
                "Record sales in the US have grown every year for well over a decade, and a lot of people who stream "
                "everything would quite like a record player. If they already have one, a record is the easy gift. "
                "If they listen on the move, headphones last longer than any album.",
            ],
            "gifts": [
                {"id": "audio-technica-lp60x", "kind": None, "size": "big", "store": "electronics",
                 "name": "An Audio-Technica AT-LP60X turntable",
                 "search": "Audio-Technica AT-LP60X turntable",
                 "why": "A fully automatic turntable: press start and the arm lowers itself, which is kinder to records "
                        "and to beginners. It has a built-in preamp, so it plugs straight into powered speakers.",
                 "for": "Someone who keeps buying records at gigs and has nothing to play them on.",
                 "check": "It has no speakers of its own. Budget for a pair of powered speakers, or get the Bluetooth "
                          "version (AT-LP60XBT) if they already have a Bluetooth speaker."},
                {"id": "rumours-vinyl", "kind": "album", "title": "Rumours", "year": 1977, "creator": "Fleetwood Mac",
                 "size": "small", "store": "popular",
                 "name": "Rumours by Fleetwood Mac on vinyl",
                 "search": "Fleetwood Mac Rumours vinyl",
                 "why": "One of the best-selling albums ever made, and one that suits a record: eleven songs over two "
                        "sides, with no track you'd want to skip. A good first record for a new turntable.",
                 "for": "Anyone setting up a record collection, or a fan of the band who only has it on their phone.",
                 "check": "Several pressings are on sale at very different prices. The standard black vinyl is fine for "
                          "most people."},
                {"id": "noise-cancelling-headphones", "kind": None, "size": "big", "store": "electronics",
                 "name": "Noise-cancelling headphones",
                 "search": "noise cancelling over-ear headphones",
                 "why": "Albums sound better without the bus, the dishwasher or the open-plan office. Sony, Bose and "
                        "Apple all make over-ear headphones that cancel noise well. Reviews mostly disagree about "
                        "comfort and the app.",
                 "for": "Commuters, students and anyone who works in a noisy room.",
                 "check": "Ask whether they use an iPhone or Android, because some features only work with one. If they "
                          "care about wired listening, check for a headphone jack."},
                {"id": "just-kids", "kind": "book", "title": "Just Kids", "year": 2010, "creator": "Patti Smith",
                 "size": "small", "store": "stripbooks",
                 "name": "Just Kids by Patti Smith",
                 "search": "Patti Smith Just Kids",
                 "why": "Patti Smith's memoir of her years with Robert Mapplethorpe in New York, from the late 1960s to "
                        "the making of Horses. It won the National Book Award in 2010, and it's the music book for "
                        "someone who doesn't usually read music books.",
                 "for": "A music fan who also reads, or a reader who loves New York.",
                 "check": "It's more about friendship and art than about records. Fans expecting a rock biography may be "
                          "surprised, usually happily."},
            ],
        },
        {
            "key": "books",
            "kind": "book",
            "name": "For the reader",
            "tagline": "Something to read on, something beautiful, a novel and a light for bedtime.",
            "intro": [
                "Readers are easy to buy for and hard to surprise. The safest book gifts are a beautiful edition of "
                "something they already love, or a novel they haven't heard of. If you know their library, start "
                "from the books they've marked as want to read.",
            ],
            "gifts": [
                {"id": "kindle-paperwhite", "kind": None, "size": "big", "store": "electronics",
                 "name": "A Kindle Paperwhite",
                 "search": "Kindle Paperwhite",
                 "why": "A screen that reads like paper, a warm light for reading in bed, weeks of battery and room for "
                        "thousands of books. It's waterproof, so the bath is fine too.",
                 "for": "Someone who reads a lot on holiday, or reads in bed while someone else sleeps.",
                 "check": "Kindles work with Amazon's store and, in the US, library books borrowed through Libby. If they "
                          "buy their ebooks from Kobo, get them a Kobo instead."},
                {"id": "penguin-clothbound", "kind": None, "size": "small", "store": "stripbooks",
                 "name": "A Penguin Clothbound Classic",
                 "search": "Penguin Clothbound Classics",
                 "why": "Hardback classics with patterned cloth covers designed by Coralie Bickford-Smith, at not much more "
                        "than the price of a paperback. They look lovely in a row, so one this year sorts out next "
                        "year's present too.",
                 "for": "Someone who loves a classic and owns it in a battered paperback.",
                 "check": "It's the same text as the regular Penguin Classics edition, in a nicer book. Check which ones "
                          "they already have."},
                {"id": "piranesi", "kind": "book", "title": "Piranesi", "year": 2020, "creator": "Susanna Clarke",
                 "size": "small", "store": "stripbooks",
                 "name": "Piranesi by Susanna Clarke",
                 "search": "Susanna Clarke Piranesi",
                 "why": "A short, strange novel about a man who lives in an endless house of halls and statues, with the "
                        "sea washing through the lower rooms. It won the Women's Prize for Fiction in 2021, and you can "
                        "read it in an evening or two over the break.",
                 "for": "A fantasy reader, or anyone who liked a book they couldn't quite explain.",
                 "check": "It's best read knowing as little as possible. Don't read the back cover to them."},
                {"id": "book-light", "kind": None, "size": "small", "store": "aps",
                 "name": "A rechargeable book light",
                 "search": "rechargeable clip on book light warm",
                 "why": "For reading in bed without keeping anyone else awake. One with a warm light setting is easier "
                        "on tired eyes than the cold white kind.",
                 "for": "Anyone who reads paper books at night.",
                 "check": "Pick one that charges over USB-C, so it shares a cable with their phone."},
            ],
        },
        {
            "key": "manga",
            "kind": "manga",
            "name": "For the manga reader",
            "tagline": "A long series in one box, a deluxe edition, and two that work for new readers.",
            "intro": [
                "Manga series run long, and the gift people remember is the one that saved them buying twenty "
                "volumes one at a time. If you don't know how far they've read, a box set that starts at volume one "
                "is safer than volume 47, or try a short series.",
            ],
            "gifts": [
                {"id": "one-piece-box-set", "kind": "manga", "title": "One Piece", "year": 1997, "creator": "Eiichiro Oda",
                 "size": "big", "store": "stripbooks",
                 "name": "One Piece Box Set 1: East Blue and Baroque Works",
                 "search": "One Piece Box Set 1 East Blue Baroque Works",
                 "why": "Viz's first One Piece box set holds volumes 1 to 23, the East Blue and Baroque Works arcs. It's "
                        "the cheapest way into a series that has run past a hundred volumes in Japan.",
                 "for": "Someone who started the anime and wants to read the story properly.",
                 "check": "It's big and heavy. Later box sets carry on the story, so check how far they've read before "
                          "buying the second."},
                {"id": "berserk-deluxe", "kind": "manga", "title": "Berserk", "year": 1989, "creator": "Kentaro Miura",
                 "size": "main", "store": "stripbooks",
                 "name": "Berserk Deluxe Edition, volume 1",
                 "search": "Berserk Deluxe Edition Volume 1",
                 "why": "Dark Horse's hardcover editions collect three volumes each at a larger size than the paperbacks. "
                        "Kentaro Miura's dark fantasy is one of the most admired manga ever drawn, and the art earns "
                        "the bigger page.",
                 "for": "An adult fantasy reader who likes it grim.",
                 "check": "Very violent, with scenes of sexual violence. Don't give it without knowing the reader."},
                {"id": "frieren", "kind": "manga", "title": "Frieren: Beyond Journey's End", "year": 2020,
                 "creator": "Kanehito Yamada and Tsukasa Abe", "size": "small", "store": "stripbooks",
                 "name": "Frieren: Beyond Journey's End, volume 1",
                 "search": "Frieren Beyond Journey's End Vol 1",
                 "why": "An elf mage who outlives the rest of her adventuring party sets out to understand the human "
                        "friends she barely noticed while they were alive. It's gentle and funny, and it gets sad in "
                        "places.",
                 "for": "Someone who loved the anime and wants to read ahead, or a fantasy reader new to manga.",
                 "check": "Viz publishes it in English. The series is still running, so there's always a next volume "
                          "for next year."},
                {"id": "uzumaki", "kind": "manga", "title": "Uzumaki", "year": 1998, "creator": "Junji Ito",
                 "size": "main", "store": "stripbooks",
                 "name": "Uzumaki by Junji Ito",
                 "search": "Junji Ito Uzumaki 3-in-1 deluxe edition",
                 "why": "Junji Ito's horror story about a small town cursed by spirals, collected by Viz in one "
                        "hardcover. It's the horror manga to give someone who says they don't read manga.",
                 "for": "Horror fans, and anyone who stays up too late with a book.",
                 "check": "Body horror throughout. The 2024 Adult Swim anime adapts it, if they'd rather watch first."},
            ],
        },
        {
            "key": "podcasts",
            "kind": "podcast",
            "name": "For the podcast listener",
            "tagline": "Earbuds they'll forget they're wearing, books from the shows, and a microphone of their own.",
            "intro": [
                "Podcasts are free, which is lovely for listeners and awkward for gift buyers. The good gifts are "
                "what they listen with, the books their favourite hosts have written, or the kit to start their own.",
            ],
            "gifts": [
                {"id": "wireless-earbuds", "kind": None, "size": "main", "store": "electronics",
                 "name": "Wireless earbuds that fit",
                 "search": "wireless earbuds noise cancelling",
                 "why": "Podcast listeners wear earbuds for hours: on walks, doing the dishes, falling asleep. For "
                        "speech, comfort and battery life matter more than sound quality, so you don't need the most "
                        "expensive pair.",
                 "for": "Anyone who listens while doing something else, which is most podcast listeners.",
                 "check": "AirPods pair most easily with iPhones. On Android, look at Samsung, Google or Sony."},
                {"id": "end-is-always-near", "kind": "book", "title": "The End Is Always Near", "year": 2019,
                 "creator": "Dan Carlin", "size": "small", "store": "stripbooks",
                 "name": "The End Is Always Near by Dan Carlin",
                 "search": "Dan Carlin The End Is Always Near",
                 "why": "The host of Hardcore History on how past societies faced collapse, from the Bronze Age to "
                        "nuclear near misses. It reads the way the show sounds.",
                 "for": "Hardcore History listeners waiting for the next episode, which could be some time.",
                 "check": "There's an audiobook read by Carlin himself, if they'd rather listen to this one too."},
                {"id": "night-vale-novel", "kind": "book", "title": "Welcome to Night Vale", "year": 2015,
                 "creator": "Joseph Fink and Jeffrey Cranor", "size": "small", "store": "stripbooks",
                 "name": "Welcome to Night Vale: A Novel",
                 "search": "Welcome to Night Vale novel Fink Cranor",
                 "why": "The first novel from the podcast's writers, set in the same desert town where every conspiracy "
                        "theory is true. Fans will know the voice, and newcomers don't need to have heard an episode.",
                 "for": "A fan of the show, or someone who likes their fiction funny and odd.",
                 "check": "There's a second novel, It Devours!, if they already have this one."},
                {"id": "usb-microphone", "kind": None, "size": "main", "store": "electronics",
                 "name": "A USB microphone for the one who wants to start a podcast",
                 "search": "dynamic USB microphone podcast",
                 "why": "Anyone who listens to enough podcasts thinks about making one. A dynamic USB microphone, such as "
                        "the Shure MV7 or the cheaper Samson Q2U, picks up less of the room than the big condenser "
                        "mics, which matters in an ordinary bedroom.",
                 "for": "Someone who has talked about starting a show for over a year.",
                 "check": "They'll want headphones too, to hear themselves while recording."},
            ],
        },
        {
            "key": "audiobooks",
            "kind": "audiobook",
            "name": "For the audiobook listener",
            "tagline": "Credits to spend, two great listens, and a way to fall asleep to them.",
            "intro": [
                "Audiobooks are expensive one at a time, which makes them a good gift. The person on your list "
                "probably already has an app, so ask which one before buying a membership.",
            ],
            "gifts": [
                {"id": "audible-gift-membership", "kind": None, "size": "main", "store": "aps",
                 "name": "An Audible gift membership",
                 "search": "Audible gift membership",
                 "why": "You can give several months of Audible, and each month comes with a credit to spend on any "
                        "audiobook. That's the useful part, since a long audiobook bought on its own can cost more than "
                        "the hardback.",
                 "for": "Someone who listens a lot and buys one title at a time.",
                 "check": "If they borrow audiobooks through Libby or get them with Spotify Premium, a membership may go "
                          "unused. A single audiobook might suit them better."},
                {"id": "project-hail-mary-audiobook", "kind": "audiobook", "title": "Project Hail Mary", "year": 2021,
                 "creator": "Andy Weir", "size": "main", "store": "audible",
                 "name": "Project Hail Mary, read by Ray Porter",
                 "search": "Project Hail Mary Ray Porter",
                 "why": "Andy Weir's novel about a schoolteacher who wakes up alone on a spaceship with no memory of how "
                        "he got there. Ray Porter is very good at a man panicking and coping at the same time, and the "
                        "audiobook does something with one character that a page can't. About sixteen hours.",
                 "for": "Anyone who liked The Martian, and anyone with a long drive over the holidays.",
                 "check": "If they've seen the film with Ryan Gosling, they know the story. The audiobook still has a lot "
                          "to give."},
                {"id": "world-war-z-complete", "kind": "audiobook", "title": "World War Z", "year": 2013,
                 "creator": "Max Brooks", "size": "small", "store": "audible",
                 "name": "World War Z: The Complete Edition",
                 "search": "World War Z Complete Edition audiobook full cast",
                 "why": "Max Brooks's oral history of a zombie war, performed as a set of interviews by a large cast that "
                        "includes Mark Hamill and Alan Alda. The book was written as people talking, so it suits audio "
                        "better than almost anything.",
                 "for": "Horror and history listeners alike.",
                 "check": "Get the Complete Edition; the first audiobook from 2006 was abridged. It has very little in "
                          "common with the Brad Pitt film."},
                {"id": "sleep-headphones", "kind": None, "size": "small", "store": "electronics",
                 "name": "Headband headphones for listening in bed",
                 "search": "sleep headphones headband bluetooth",
                 "why": "A soft headband with thin speakers inside, for people who fall asleep to an audiobook and wake "
                        "up with an earbud in the pillow. Side sleepers like them most.",
                 "for": "Anyone who listens at bedtime.",
                 "check": "The sound is basic, which is fine for speech. Look for a washable band."},
            ],
        },
    ],
    "faq": [
        ("What do I get someone who already owns everything they like?",
         "Look one step to the side of what they own: a better edition of a favourite, the book about it, the next "
         "film by the same director, or the thing they play it on. If they track their library on OmniTrackr, ask them "
         "to make a gift list. It suggests the titles they haven't started and the favourites they'd like to own."),
        ("How do gift lists work?",
         "A member builds the list on this page from their library, from the ideas in this guide, or by typing "
         "anything they like. Then they send one link to family and friends. Anyone with the link can see the list "
         "and mark a gift as one they're getting, without an account. The member who made the list never sees "
         "which gifts were marked, so the surprise stays intact. The link can be switched off or replaced at any time."),
        ("Do you earn money if I buy something here?",
         "Yes, through the Amazon Associates programme: if you buy after following one of our Amazon links, Amazon "
         "pays us a small commission, and you pay the same price. Nobody paid to be in this guide and we weren't sent "
         "anything for free. The links are searches rather than single listings, so you can pick the edition and the "
         "seller yourself, or buy it somewhere else."),
        ("Are discs still worth buying when everything streams?",
         "For films and series someone loves, yes. Streaming catalogues change every month and a film can leave a "
         "service without warning. A disc also tends to have better picture and sound than a stream, and the "
         "commentaries and extras that streaming leaves out. If they don't have a player, though, buy them something else."),
        ("What if I don't know which console they play on?",
         "Ask, or ask someone who lives with them. If you can't, skip the game and pick something that doesn't depend "
         "on it, like a board game, a book about games or a gift card for the store they already use."),
        ("Why are there no prices?",
         "Prices change every day in December, and a printed price is usually wrong by the time you read it. Each gift "
         "is marked as a stocking filler, a main present or a splurge, which stays true for longer."),
    ],
    "method": [
        "Prepared by OmniTrackr and reviewed by the site owner before publishing. We started from the nine kinds of fan "
        "OmniTrackr tracks for and picked four gifts each, at different sizes. Every pick is something we'd be happy to "
        "get, and we chose a few safe classics on purpose, because a gift has to work for someone whose taste you "
        "only half know.",
        "Facts such as release dates, editions and what is in a box set were checked against the publishers' and "
        "makers' own listings in November 2026. Editions and availability vary by country. The Amazon links are "
        "affiliate links, which is one of the ways we pay for hosting; they never decided what went in.",
    ],
}

SECTIONS = GUIDE["sections"]
GIFTS = {gift["id"]: gift for section in SECTIONS for gift in section["gifts"]}
SIZE_LABELS = {key: label for key, label, _ in GUIDE["sizes"]}
