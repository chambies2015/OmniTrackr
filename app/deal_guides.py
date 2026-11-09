"""The Black Friday and Cyber Monday guide at /holidays/black-friday.

It sits beside the holiday hub and the gift guide. The gift guide answers "what do I
buy for this person"; this one answers "is now a good time to buy it". Each section
is one format (discs, anime, games, music, books, manga, audiobooks, podcasts) with
what tends to get cheaper in the sales, what rarely does, and three things worth
watching for.

A pick's ``search`` and ``store`` build an Amazon search link at render time
(affiliate.search_links), so nothing here is a product listing. A pick can carry a
plain ``link`` (url, label) instead, for things Amazon doesn't sell, such as Record
Store Day releases, or neither when there is nothing to buy. Prices are left out on
purpose: they change by the hour that week.

The writing is our own. Facts were checked on the date in ``reviewed``.
"""
from __future__ import annotations

GUIDE = {
    "path": "/holidays/black-friday",
    "published": "2026-11-09",
    "reviewed": "2026-11-09",
    "name": "Black Friday guide",
    "search_title": "Black Friday and Cyber Monday 2026 for movie, TV, anime, game, music, book, manga and audiobook fans",
    "headline": "Black Friday for people with a backlog",
    "deck": ("What usually gets cheaper on Black Friday and Cyber Monday if you watch, play, read or listen to a lot, "
             "what almost never does, and five checks to make before you pay. Box sets, games, manga, vinyl, "
             "e-readers, audiobooks and the gear to enjoy them on, with no made-up prices."),
    "summary": ("A Black Friday and Cyber Monday 2026 guide for media fans: which box sets, games, manga, records, books "
                "and audiobooks tend to drop in the sales, which rarely do, the dates that matter, and what to check "
                "before you buy."),
    "card": "What tends to get cheaper on Black Friday, what rarely does, and what to check first.",
    "intro": [
        "Black Friday is on November 27 this year and Cyber Monday on November 30. For anyone who tracks what they "
        "watch and read, the week is less about televisions and more about the list: the series you want on disc, the "
        "manga box set you keep putting off, the game you skipped at launch. Those are the things that do get "
        "cheaper, but not all of them, and not always on the day.",
        "The pattern is fairly steady from year to year. Older stock drops: catalogue films, complete series, last "
        "year's games, books that have been out a while. The shop's own hardware drops too, since the shop sets "
        "the price. New releases, limited editions and the big console makers' own games barely move, and some of "
        "the loudest offers are on things nobody had planned to buy until they saw the banner.",
        "So this guide is sorted by format. Each section says what tends to fall in price, what usually doesn't, and "
        "names three things worth watching for, with what to check before you buy. There are no prices, because "
        "they change by the hour that week and a printed one would be wrong by the time you read it.",
    ],
    # The week, day by day. ``tone`` marks the two big days for the page's styling.
    "calendar_intro": ("Most shops no longer keep their prices for Friday. The first deals usually appear in early "
                       "November and the big ones by the Monday of Thanksgiving week. Here is how the days fall in 2026."),
    "calendar": [
        {"date": "2026-11-23", "day": "Mon to Wed", "label": "Nov 23 to 25", "tone": "",
         "name": "The early week",
         "text": "Most big shops have their Black Friday prices up by now. If something you want is already at a "
                 "price you're happy with, there's little to gain from waiting."},
        {"date": "2026-11-26", "day": "Thursday", "label": "Nov 26", "tone": "",
         "name": "Thanksgiving",
         "text": "Many online sales start or deepen today, while a lot of people are at the table. Stores that open "
                 "are often on short hours."},
        {"date": "2026-11-27", "day": "Friday", "label": "Nov 27", "tone": "big",
         "name": "Black Friday",
         "text": "The busiest day. Record Store Day runs its Black Friday event at independent record shops, with "
                 "limited pressings that are only sold there."},
        {"date": "2026-11-28", "day": "Saturday", "label": "Nov 28", "tone": "",
         "name": "Small Business Saturday",
         "text": "A good day for your local comic shop, bookshop or record store, which often run their own offers "
                 "and won't have sold out of everything."},
        {"date": "2026-11-30", "day": "Monday", "label": "Nov 30", "tone": "big",
         "name": "Cyber Monday",
         "text": "Online only. Prices from the weekend mostly hold, and subscriptions and digital storefronts tend to "
                 "push their offers today."},
        {"date": "2026-12-17", "day": "From Dec 17", "label": "to Jan 4", "tone": "",
         "name": "Steam Winter Sale",
         "text": "Valve moved its Autumn Sale to the start of October this year, so the next site-wide Steam sale is "
                 "the winter one, from December 17 to January 4."},
    ],
    # Five checks before buying anything that week.
    "checks": [
        ("Look up the price history",
         "A big percentage off means little if the price went up in October. For Amazon, camelcamelcamel and Keepa "
         "show what a listing has cost over months. For games, IsThereAnyDeal covers PC stores, PSPrices covers "
         "PlayStation and Deku Deals covers Nintendo, Xbox and PlayStation. If the Black Friday price matches the "
         "lowest it has been all year, that's a real deal. If it matches last month's price, you can take your time."),
        ("Check what you already own",
         "Collections drift. People buy a film on disc that they already have digitally, or a manga box set that "
         "repeats the four volumes they picked up singly. Look at your shelf, your digital libraries and your "
         "OmniTrackr library before you pay. Members get their own list further up this page."),
        ("Read which edition it is",
         "The cheapest listing is often a different version: the DVD rather than the Blu-ray, the theatrical cut "
         "without the extras, the paperback reissue instead of the hardback. 4K discs are almost all region-free, "
         "but ordinary Blu-rays and DVDs carry region codes, and an import may not play on an American player."),
        ("Check what it runs on",
         "The PS5 Digital Edition has no disc drive unless you add one. Some Switch 2 boxes hold a game-key card, "
         "which only unlocks a download, so you still need the space and the internet connection. An Xbox Series S "
         "plays no discs at all."),
        ("Read the renewal terms",
         "Subscription offers are usually for new or lapsed members, often on the plan with ads, and they renew at "
         "the full price when the offer ends. Put the end date in your calendar the day you sign up."),
    ],
    "sections": [
        {
            "key": "discs",
            "kinds": ["movie", "tv"],
            "name": "Movies and TV on disc",
            "tagline": "Catalogue box sets fall. This year's new releases barely move.",
            "intro": [
                "Physical media has had a rough few years, with fewer shops carrying it and some studios releasing "
                "less of it. The discs that are left still get cut hard on Black Friday to clear stock, so it's a "
                "good week to fill the gaps on the shelf. Complete-series sets and multi-film collections are where the "
                "biggest drops usually are.",
                "If you care about the Criterion Collection, the best sale is often elsewhere: Barnes & Noble has run "
                "a half-price sale on every Criterion title in July and November for years, and when it's on it "
                "usually beats Black Friday prices on those discs.",
            ],
            "drops": [
                "Complete-series TV box sets, especially shows that finished years ago",
                "Multi-film collections and trilogies in 4K",
                "Steelbook editions of films that are a year or more old",
                "4K Blu-ray players, which go on sale with the TVs",
            ],
            "holds": [
                "Films released on disc in the last month or two",
                "Boutique labels such as Arrow and Criterion on Amazon, outside their own sales",
                "Limited editions with numbered slipcases, which sell out before they get cheaper",
            ],
            "picks": [
                {"id": "back-to-the-future-4k", "kind": "movie", "title": "Back to the Future", "year": 1985,
                 "creator": "Robert Zemeckis", "store": "movies-tv",
                 "name": "Back to the Future: The Ultimate Trilogy in 4K",
                 "search": "Back to the Future Ultimate Trilogy 4K Ultra HD",
                 "why": "All three films were remastered in 4K for the first film's 35th anniversary in 2020, and the "
                        "set has turned up in most Black Friday sales since. The first film holds up as one of the "
                        "best-built comedies Hollywood made in the 1980s, and the sequels are good fun.",
                 "check": "Look at whether the listing includes the bonus disc of extras or just the films. The "
                          "steelbook versions cost more and hold the same discs."},
                {"id": "sopranos-complete", "kind": "tv", "title": "The Sopranos", "year": 1999,
                 "creator": "David Chase", "store": "movies-tv",
                 "name": "The Sopranos: The Complete Series on Blu-ray",
                 "search": "The Sopranos Complete Series Blu-ray",
                 "why": "Six seasons and 86 episodes about a New Jersey mob boss in therapy, in one box. Older HBO sets "
                        "like this one drop to some of their lowest prices of the year in November, and the series is "
                        "the kind you rewatch every few years and notice new things.",
                 "check": "It streams on HBO Max, so this is for people who want a copy that won't leave a service. "
                          "Some cheaper listings are the DVD set; the Blu-ray looks much better."},
                {"id": "uhd-player", "kind": None, "store": "electronics",
                 "name": "A 4K Blu-ray player",
                 "search": "4K UHD Blu-ray player",
                 "why": "If you're buying 4K discs, you need something to play them on, and dedicated players are "
                        "usually discounted alongside the TVs. A good player also handles ordinary Blu-rays, DVDs "
                        "and often CDs.",
                 "check": "A PS5 with a disc drive and an Xbox Series X already play 4K Blu-rays, so check before "
                          "buying a second machine. The Xbox Series S has no drive."},
            ],
        },
        {
            "key": "anime",
            "kinds": ["anime"],
            "name": "Anime",
            "tagline": "Complete-series sets are the deal. Streaming barely changes.",
            "intro": [
                "Anime on disc comes from a few American labels, including Crunchyroll, Discotek, GKIDS and Sentai, "
                "and their complete-season and complete-series sets are what tend to drop. Streaming is where most "
                "people watch new shows, and simulcast services rarely do much for Black Friday beyond the "
                "occasional cheaper annual plan.",
                "Anime figures and model kits are the other thing fans buy this week. Big figure makers sell through "
                "pre-orders, so their prices rarely move, but model kits and older figures in stock often do.",
            ],
            "drops": [
                "Complete-series Blu-ray sets of shows a few years old",
                "Studio Ghibli and other GKIDS film releases",
                "Model kits such as Bandai's Gundam range, and figures already in stock",
            ],
            "holds": [
                "Collector's editions from smaller labels, which are printed in small runs",
                "Pre-order figures, which are priced when they're announced",
                "Monthly streaming prices",
            ],
            "picks": [
                {"id": "fmab-complete", "kind": "anime", "title": "Fullmetal Alchemist: Brotherhood", "year": 2009,
                 "creator": "Bones", "store": "movies-tv",
                 "name": "Fullmetal Alchemist: Brotherhood, complete series",
                 "search": "Fullmetal Alchemist Brotherhood complete series Blu-ray",
                 "why": "Two brothers try to undo an alchemy experiment that cost one his body and the other an arm "
                        "and a leg. All 64 episodes follow Hiromu Arakawa's manga to its end, which is why it's still "
                        "the show many fans give to people who don't watch anime.",
                 "check": "There's an earlier series from 2003 simply called Fullmetal Alchemist, which tells a "
                          "different story after its first half. Make sure the box says Brotherhood."},
                {"id": "evangelion-blu-ray", "kind": "anime", "title": "Neon Genesis Evangelion", "year": 1995,
                 "creator": "Hideaki Anno", "store": "movies-tv",
                 "name": "Neon Genesis Evangelion on Blu-ray",
                 "search": "Neon Genesis Evangelion complete series Blu-ray GKIDS",
                 "why": "GKIDS put the 26-episode series and the two films that go with it out on Blu-ray in 2021, the "
                        "first time the series had been on Blu-ray in North America. It's one of the most "
                        "talked-about anime ever made, and it's worth owning in a version that can't be pulled.",
                 "check": "There's a standard edition and a much more expensive collector's edition with books and "
                          "extras. The newer Rebuild films are a separate release."},
                {"id": "gunpla-kit", "kind": None, "store": "toys-and-games",
                 "name": "A Gundam model kit",
                 "search": "Bandai HG Gundam model kit",
                 "why": "Bandai's plastic Gundam kits snap together without glue or paint, and a High Grade kit takes "
                        "an evening or two. They are cheap enough at the small sizes that a sale makes a real "
                        "difference, and they're a nice thing to do with your hands while a show plays.",
                 "check": "Start with High Grade (HG). Master Grade and Perfect Grade kits are bigger, harder and "
                          "much pricier. A pair of side cutters (nippers) makes the job far neater."},
            ],
        },
        {
            "key": "games",
            "kinds": ["game"],
            "name": "Games",
            "tagline": "Last year's games and accessories drop. New hits and Nintendo's own games don't.",
            "intro": [
                "Games have the most predictable sales of any format. A big release from the last two or three months "
                "rarely drops much, and Grand Theft Auto VI, due on November 19, won't be the exception, though it "
                "may turn up in a console bundle. Games from a year or more ago are a different story, and so are "
                "controllers, headsets and storage.",
                "Nintendo is the odd one out. Its own games, such as Mario and Zelda, keep their price for years and "
                "only get small, short discounts. Third-party Switch games behave like everyone else's.",
                "PC players should know that Steam's Autumn Sale moved to October 1 to 8 this year. Publishers can "
                "still discount their own games in Thanksgiving week, but the next site-wide sale is the Winter Sale, "
                "which starts on December 17.",
            ],
            "drops": [
                "Games released a year or more ago, often to half their launch price",
                "Controllers, headsets and charging docks",
                "Storage: SSDs for PS5 and PC, memory cards for Switch 2",
                "Annual subscriptions such as PlayStation Plus, which has been cut in past Black Friday sales",
            ],
            "holds": [
                "Big releases from September to November",
                "Nintendo's own games",
                "Collector's editions, which are made in fixed numbers",
            ],
            "picks": [
                {"id": "astro-bot", "kind": "game", "title": "Astro Bot", "year": 2024, "creator": "Team Asobi",
                 "store": "videogames",
                 "name": "Astro Bot for PS5",
                 "search": "Astro Bot PS5",
                 "why": "A bright platformer about a little robot rescuing his crew, made by the studio inside "
                        "PlayStation that builds its hardware demos. It won Game of the Year at The Game Awards in "
                        "2024, it's short enough to finish over a long weekend, and it's now old enough to be "
                        "discounted.",
                 "check": "It's PS5 only. Children can play it, but the later levels get hard."},
                {"id": "dualsense-controller", "kind": None, "store": "videogames",
                 "name": "A second PS5 or Xbox controller",
                 "search": "DualSense wireless controller PS5",
                 "why": "Most homes with a console end up wanting a second controller, for a friend, a sibling or "
                        "a spare while the first one charges. Official controllers are reliably discounted in "
                        "November, often in colours that aren't sold the rest of the year.",
                 "check": "Match the console. The DualSense Edge is the pricier pro controller with swappable sticks; "
                          "most people don't need it."},
                {"id": "microsd-express", "kind": None, "store": "electronics",
                 "name": "A microSD Express card for Switch 2",
                 "search": "microSD Express card Nintendo Switch 2",
                 "why": "The Switch 2's built-in storage fills fast, and its card slot only runs games from the newer "
                        "microSD Express cards. Memory is one of the things that's cheapest in the sales.",
                 "check": "An ordinary microSD card from the first Switch won't run Switch 2 games. Look for "
                          "\"microSD Express\" on the card itself."},
            ],
        },
        {
            "key": "music",
            "kinds": ["album"],
            "name": "Music and vinyl",
            "tagline": "Speakers and older records drop. Record Store Day pressings sell out instead.",
            "intro": [
                "Black Friday is a strange day for records. The big online shops cut the price of classic albums and "
                "turntables, while Record Store Day holds a separate event the same day at independent shops, with "
                "special pressings that cost full price and sell out by lunchtime.",
                "Streaming services sometimes offer a few months of their paid plan cheaply that week. If you already "
                "pay for one, the bigger saving is usually on the speakers or headphones you listen through.",
            ],
            "drops": [
                "Reissues of classic albums that have been in print for years",
                "Turntables, powered speakers and headphones",
                "Introductory offers on music streaming plans",
            ],
            "holds": [
                "Record Store Day releases, which are limited",
                "New albums released this autumn",
                "Box sets from the big reissue labels in their first months",
            ],
            "picks": [
                {"id": "rsd-black-friday", "kind": None,
                 "link": ("https://recordstoreday.com/SpecialReleases", "See the full Record Store Day list"),
                 "name": "Record Store Day Black Friday, November 27",
                 "why": "This year's list includes a Prince live set, 3121 Las Vegas Live, a Billy Joel concert from "
                        "1976, Billy Joel Tonight, and a four-record set of the complete Wicked soundtrack. The "
                        "pressings are only sold through independent record shops, so this is one Black Friday "
                        "event that sends you out of the house.",
                 "check": "Quantities are small and shops can't hold copies. Ask your local shop which titles they "
                          "ordered and what time they open. We don't link to these on Amazon."},
                {"id": "kind-of-blue-vinyl", "kind": "album", "title": "Kind of Blue", "year": 1959,
                 "creator": "Miles Davis", "store": "popular",
                 "name": "Kind of Blue by Miles Davis on vinyl",
                 "search": "Miles Davis Kind of Blue vinyl",
                 "why": "The best-selling jazz record ever made, recorded in two sessions in 1959 with John Coltrane, "
                        "Cannonball Adderley and Bill Evans. It's a classic that's been in print for decades, which "
                        "is why it gets discounted. It works as a first jazz record and a fiftieth.",
                 "check": "There are many pressings, from cheap reissues to costly audiophile ones. The reviews on "
                          "Discogs will tell you which is which."},
                {"id": "powered-speakers", "kind": None, "store": "electronics",
                 "name": "A pair of powered bookshelf speakers",
                 "search": "powered bookshelf speakers turntable",
                 "why": "Plenty of turntables bought in a sale end up plugged into a small Bluetooth speaker. A pair of "
                        "powered bookshelf speakers is the bigger improvement, and they work for the TV and the "
                        "computer too.",
                 "check": "Powered speakers have the amplifier built in. Passive ones need a separate amplifier. "
                          "If the turntable has no built-in preamp, look for speakers with a phono input."},
            ],
        },
        {
            "key": "books",
            "kinds": ["book"],
            "name": "Books and e-readers",
            "tagline": "E-readers and box sets drop. Ebook prices hardly change.",
            "intro": [
                "Books are already discounted most of the year online, so Black Friday makes less difference to a "
                "single paperback than to a box set or a device. E-readers are the exception: Amazon sets the price "
                "of its own Kindles and cuts it every November, and other makers follow.",
                "Before you buy anything to read, check your library card. Libby lends ebooks and audiobooks for free "
                "through most public libraries in the United States, and a Kobo e-reader can borrow from it "
                "directly.",
            ],
            "drops": [
                "Kindle and Kobo e-readers",
                "Box sets of finished series",
                "Hardbacks that have been out for a year or so",
            ],
            "holds": [
                "New hardbacks from this autumn",
                "Most ebooks, whose prices are set by publishers",
                "Signed and special editions",
            ],
            "picks": [
                {"id": "e-reader", "kind": None, "store": "electronics",
                 "name": "An e-reader",
                 "search": "Kindle e-reader",
                 "why": "A Kindle is the device Amazon cuts most reliably every Black Friday. If you read more than a "
                        "few books a year, an e-reader is easier on the eyes than a phone and lasts weeks between "
                        "charges.",
                 "check": "A Kindle reads books from Amazon's store and borrows from Libby through Amazon. A Kobo uses "
                          "its own store and has Libby built in. Pick the one that matches where you get books."},
                {"id": "song-of-ice-and-fire", "kind": "book", "title": "A Game of Thrones", "year": 1996,
                 "creator": "George R. R. Martin", "store": "stripbooks",
                 "name": "A Song of Ice and Fire box set",
                 "search": "A Song of Ice and Fire box set George R. R. Martin",
                 "why": "George R. R. Martin's five novels in one set, the books behind Game of Thrones and House of "
                        "the Dragon. Box sets of long series are where the biggest book discounts usually are, and "
                        "this one has been in print in several editions for years.",
                 "check": "The series isn't finished: the sixth book, The Winds of Winter, still has no release "
                          "date. There are paperback, hardback and illustrated sets at very different prices."},
                {"id": "kindle-unlimited", "kind": None, "store": "aps",
                 "name": "A Kindle Unlimited trial",
                 "search": "Kindle Unlimited",
                 "why": "Amazon's ebook subscription often has a longer or cheaper trial around Black Friday. It suits "
                        "fast readers of genre fiction, since much of the catalogue is romance, thrillers and fantasy "
                        "from smaller publishers.",
                 "check": "Most big new releases aren't in it. It renews at the full monthly price unless you cancel."},
            ],
        },
        {
            "key": "manga",
            "kinds": ["manga"],
            "name": "Manga",
            "tagline": "Box sets are the big saving. New volumes hardly move.",
            "intro": [
                "Manga is sold one volume at a time, which adds up quickly for a long series. Box sets of the first "
                "dozen or more volumes are where the sales help, and Viz and other publishers' sets get some of their "
                "deepest cuts of the year in November.",
                "Digital manga goes on sale too, through Kindle and BookWalker, but those volumes are tied to the "
                "store you bought them from. If you want to keep a series for good, buy it on paper.",
            ],
            "drops": [
                "Box sets of finished series and of a long series' first arc",
                "Hardcover omnibus and deluxe editions that have been out a while",
                "Digital volumes in store-wide sales",
            ],
            "holds": [
                "New single volumes in their first months",
                "Limited editions and convention exclusives",
                "Series that are still running and selling fast",
            ],
            "picks": [
                {"id": "death-note-box-set", "kind": "manga", "title": "Death Note", "year": 2003,
                 "creator": "Tsugumi Ohba and Takeshi Obata", "store": "stripbooks",
                 "name": "The Death Note complete box set",
                 "search": "Death Note complete box set Viz",
                 "why": "All thirteen volumes of the story about a student who finds a notebook that kills anyone whose "
                        "name he writes in it, and the detective trying to catch him. It's finished, short enough to "
                        "read over a holiday week and one of the best ways into manga for a thriller reader.",
                 "check": "Viz has sold a few versions: the box set of single volumes and the larger All-in-One "
                          "edition in a single book. Volume 13 is a guidebook rather than story."},
                {"id": "naruto-box-set", "kind": "manga", "title": "Naruto", "year": 1999,
                 "creator": "Masashi Kishimoto", "store": "stripbooks",
                 "name": "Naruto Box Set 1",
                 "search": "Naruto Box Set 1 volumes 1-27",
                 "why": "The first 27 volumes of Masashi Kishimoto's ninja series, which is one of the best-selling "
                        "manga ever. A long series like this is where a box set saves the most over buying volume by "
                        "volume.",
                 "check": "This set covers the first part of the story, before the time skip. Two more box sets finish "
                          "it. Check whether they already own the early volumes singly."},
                {"id": "fullmetal-edition", "kind": "manga", "title": "Fullmetal Alchemist", "year": 2001,
                 "creator": "Hiromu Arakawa", "store": "stripbooks",
                 "name": "Fullmetal Alchemist: Fullmetal Edition",
                 "search": "Fullmetal Alchemist Fullmetal Edition hardcover",
                 "why": "Viz's hardcover edition of Hiromu Arakawa's manga, in eighteen larger volumes with colour "
                        "pages. It's the version to keep on a shelf, and it pairs with the Brotherhood box set in "
                        "the anime section above.",
                 "check": "Hardcovers cost more per volume than the 3-in-1 paperbacks, which are the cheaper way to "
                          "read the whole thing."},
            ],
        },
        {
            "key": "audiobooks",
            "kinds": ["audiobook"],
            "name": "Audiobooks",
            "tagline": "Membership offers are the deal. Spend credits on long books.",
            "intro": [
                "Single audiobooks are expensive, so the deals this week are mostly about memberships. Audible has run "
                "reduced-price membership offers around Black Friday in recent years, and each month on the plan "
                "comes with a credit for any audiobook.",
                "Before you sign up for anything, look at what you already have. Spotify Premium includes a set number "
                "of audiobook listening hours each month in the United States and several other countries, and "
                "Libby lends audiobooks for free with a library card.",
            ],
            "drops": [
                "Introductory Audible membership offers",
                "Audible's own sales on single titles, often on Cyber Monday",
                "Headphones and earbuds to listen on",
            ],
            "holds": [
                "New audiobooks, which are priced alongside the hardback",
                "Library audiobooks, which are free anyway",
            ],
            "picks": [
                {"id": "audible-membership", "kind": None, "store": "aps",
                 "name": "An Audible membership offer",
                 "search": "Audible membership",
                 "why": "If you listen to more than one book a month, a membership is cheaper than buying titles one by "
                        "one, and the Black Friday offers are often the cheapest way in.",
                 "check": "The offer price lasts a few months, then it renews at the full price. If you cancel, unused "
                          "credits go with it, so spend them first. Books you've bought stay yours."},
                {"id": "way-of-kings-audiobook", "kind": "audiobook", "title": "The Way of Kings", "year": 2010,
                 "creator": "Brandon Sanderson", "store": "audible",
                 "name": "The Way of Kings, read by Michael Kramer and Kate Reading",
                 "search": "The Way of Kings audiobook Michael Kramer Kate Reading",
                 "why": "The first book of Brandon Sanderson's Stormlight Archive runs to about 45 hours. A credit "
                        "buys a book of any length, so long fantasy like this is the best use of one, and Kramer and "
                        "Reading have read Sanderson's books for years.",
                 "check": "It's the start of a long series. GraphicAudio also sells a full-cast dramatised version in "
                          "several parts, so make sure the listing is the Kramer and Reading reading."},
                {"id": "spotify-audiobook-hours", "kind": None,
                 "name": "Audiobook hours already in Spotify Premium",
                 "why": "If you pay for Spotify Premium in the United States, you already get a monthly allowance of "
                        "audiobook listening, which covers one or two books for most people. It's worth using that "
                        "up before paying for a second service.",
                 "check": "The hours reset each month and don't roll over. Extra hours cost more, and not every title "
                          "is in the catalogue."},
            ],
        },
        {
            "key": "podcasts",
            "kinds": ["podcast"],
            "name": "Podcasts and listening gear",
            "tagline": "Podcasts are free. The deal is what you listen on.",
            "intro": [
                "There's nothing to buy for most podcasts, so Black Friday is about the gear: the earbuds for the "
                "commute, the speaker in the kitchen, the microphone for the show you keep meaning to start. Amazon "
                "cuts its own Echo speakers every year, and headphone prices fall across the board.",
                "If a show you love is worth something to you, the better use of the week might be supporting it. "
                "Many podcasts sell ad-free feeds through Patreon or Apple Podcasts subscriptions.",
            ],
            "drops": [
                "Smart speakers, especially Amazon's own",
                "Earbuds and headphones from last year's range",
                "USB microphones",
            ],
            "holds": [
                "This year's flagship headphones in their first months",
                "Show memberships and ad-free feeds",
            ],
            "picks": [
                {"id": "kitchen-speaker", "kind": None, "store": "electronics",
                 "name": "A smart speaker for the kitchen",
                 "search": "Echo smart speaker",
                 "why": "Podcasts are made for doing something else at the same time, and the kitchen is where most "
                        "people do it. Amazon's own Echo speakers are among the deepest discounts of the week because "
                        "Amazon sets their price.",
                 "check": "Check that it plays from the podcast app you use. If your house runs on Google or Apple, a "
                          "Nest or HomePod will fit in better."},
                {"id": "open-ear-headphones", "kind": None, "store": "electronics",
                 "name": "Open-ear headphones for walking",
                 "search": "open ear headphones",
                 "why": "Open-ear headphones sit just outside the ear, so you can hear traffic and people while a "
                        "podcast plays. They suit long walks, runs and anyone who finds earbuds uncomfortable.",
                 "check": "They leak sound and do nothing about noise, so they're poor on a train or a plane. Speech "
                          "sounds fine; music sounds thin."},
                {"id": "support-a-show", "kind": None,
                 "name": "A membership for a show you love",
                 "why": "Most podcasts make their money from ads, and many offer an ad-free feed, bonus episodes or "
                        "early access to listeners who pay a few dollars a month. It's the one thing on this page "
                        "that goes straight to the people who make what you enjoy.",
                 "check": "Look on the show's own site for how it takes support. A Patreon feed plays in most podcast "
                          "apps; an Apple Podcasts subscription only plays in Apple's."},
            ],
        },
    ],
    "faq": [
        ("When are Black Friday and Cyber Monday in 2026?",
         "Black Friday is Friday, November 27, the day after Thanksgiving, and Cyber Monday is Monday, November 30. "
         "Many shops start their offers in the week before, and some in early November."),
        ("Is there a Steam sale on Black Friday this year?",
         "Not a site-wide one. Valve moved its Autumn Sale to October 1 to 8 in 2026, and the Winter Sale runs from "
         "December 17 to January 4. Publishers can still discount their own games on Steam in Thanksgiving week, so "
         "it's worth checking a wishlist, but the bigger sale is in December."),
        ("Are Black Friday deals real discounts?",
         "Some are and some aren't. The reliable ones are on older stock and on hardware the shop makes itself. The "
         "doubtful ones compare against a list price nobody paid. A price-history site such as camelcamelcamel or "
         "Keepa for Amazon, or IsThereAnyDeal for PC games, shows whether this week's price is the lowest of the year."),
        ("Is it better to buy films and games on disc or digitally?",
         "A disc is yours for good and can be lent or sold, and a film on disc often has better picture and sound "
         "than the stream. Digital is cheaper to store and often cheaper in the sales, but it's tied to the store's "
         "account and can, rarely, be withdrawn. For something you love and will rewatch, the disc is the safer buy."),
        ("Do you earn money if I buy something here?",
         "Yes, through the Amazon Associates programme. If you buy after following one of our Amazon links, Amazon "
         "pays us a small commission and you pay the same price. Nobody paid to be in this guide. The links are "
         "searches rather than single listings, so you choose the edition and the seller, or buy somewhere else."),
        ("Why are there no prices?",
         "Prices change several times a day during the week of Black Friday, and the same listing can be cheaper on "
         "Monday than on Friday. A printed price would be wrong by the time you read it. The price-history sites in "
         "the checks above show the real number."),
    ],
    "method": [
        "Prepared by OmniTrackr and reviewed by the site owner before publishing. We wrote this from what usually goes "
        "on sale in late November in each format OmniTrackr tracks, and chose three things in each that are either "
        "reliably discounted or worth knowing about that week. Several are older titles on purpose, because those are "
        "the ones that get cheaper.",
        "Dates, editions and what is in a set were checked against publishers', makers' and organisers' own listings "
        "and news coverage on November 9, 2026, including Valve's published Steam sale schedule and Record Store Day's "
        "Black Friday list. Offers vary by country and change daily. The Amazon links are affiliate links, which is "
        "one of the ways we pay for hosting; they never decided what went in.",
    ],
}

SECTIONS = GUIDE["sections"]
PICKS = {pick["id"]: pick for section in SECTIONS for pick in section["picks"]}
