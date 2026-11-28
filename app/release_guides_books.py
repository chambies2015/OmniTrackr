"""Book season guides for /new-releases: the winter publications worth planning around.

Same fields as the guides in release_guides.py (that module adds these to GUIDES). A book
season guide has ``focus: "books"``, like the anime, TV, games and film season guides: its
sections are all book picks, grouped by kind of book, and it is never the "current" guide
on Release Radar. Books already written up in the broader winter guide (winter-2026-27)
stay there and are only mentioned in ``also`` here.
"""

GUIDES = {
    "winter-2027-books": {
        "name": "Winter 2027 books: the new novels worth reading from January to March",
        "period": "January to March 2027",
        "eyebrow": "BOOKS RELEASE GUIDE",
        "hub_label": "Winter 2027 books",
        "focus": "books",
        "search_title": "Winter 2027 books: Ishiguro, Percival Everett, Taylor Jenkins Reid, Freida McFadden and more",
        "summary": ("Fifteen winter 2027 books worth reading, from new novels by Kazuo Ishiguro, Percival Everett and "
                    "Elif Shafak to Taylor Jenkins Reid and Freida McFadden."),
        "published": "2026-11-20",
        "reviewed": "2026-11-20",
        "starts": "2027-01-01",
        "ends": "2027-03-31",
        "lead": [
            "Publishers save some of their best books for the start of the year. The autumn is crowded with prize "
            "contenders and Christmas presents, and a big novel that comes out in January or March has the shelves at "
            "the front of the shop more or less to itself. This winter is a strong one. In the first three months of "
            "2027 there are new novels from a Nobel winner, Kazuo Ishiguro, and from Percival Everett, whose novel "
            "James won the Pulitzer Prize, as well as from Taylor Jenkins Reid, Jojo Moyes, Kate Morton and Freida "
            "McFadden, who between them sell a very large number of books.",
            "This guide is the short version. We went through the publishers' catalogs as they stood on November 20 "
            "and picked fifteen books: six literary novels, four big book-club stories, three thrillers and two "
            "novels with magic or time travel in them. For each one we say when it comes out and who publishes it, "
            "what it is about, what to read first if anything, and the thing most likely to put you off. We have "
            "not read them yet, because almost nobody has, so read these as bets, not reviews.",
            "A few housekeeping notes. Dates are for the US hardcover, which in almost every case comes out on a "
            "Tuesday with the ebook and audiobook on the same day. UK editions can come from a different publisher "
            "on a different day. Four of the season's most anticipated books, from Sarah J. Maas, T. J. Klune, "
            "Heather Fawcett and Samantha Shannon, are written up in our broader winter releases guide, so they are "
            "only listed at the bottom of this one.",
        ],
        "sections": [
            {
                "format": "books",
                "id": "literary",
                "label": "Literary fiction",
                "heading": "Six literary novels, from 160 pages to 608",
                "intro": [
                    "These are the books most likely to turn up on prize lists later in the year. Two of them are by "
                    "writers who have already won the biggest prizes there are, and two are by writers coming back to "
                    "fiction after a gap. Three are short enough to read in a weekend, which is not what you expect "
                    "from a season this serious.",
                ],
                "picks": [
                    {"kind": "book", "title": "In One Brief Moment All Eternity", "year": 2027, "creator": "Elif Shafak",
                     "date": "2027-01-12",
                     "released": "Hardcover, ebook and audiobook · Knopf · 608 pages",
                     "why": "A novel about Gustave Flaubert told by the women, real and invented, who shaped him. It "
                            "begins as he is about to write the death of Emma Bovary, and Emma answers back.",
                     "note": "Elif Shafak has spent the last few books writing long, many-voiced novels that move across "
                             "centuries: 10 Minutes 38 Seconds in This Strange World was shortlisted for the Booker in "
                             "2019, and There Are Rivers in the Sky followed a single drop of water from ancient "
                             "Nineveh to modern London. Flaubert's life gives her a lot to work with. He grew up in the "
                             "hospital in Rouen where his father was chief surgeon, a house the publisher describes as "
                             "\"part home, part hospital, part morgue,\" saw the revolution of 1848 in Paris, and "
                             "travelled through Egypt, where he met the dancer Kuchuk Hanem, and on to Beirut and "
                             "Istanbul. Kuchuk Hanem and George Sand, his friend and correspondent, are among the women "
                             "in the book. Kirkus gave "
                             "it a starred review and called it an investigation \"of art, love, and the soul.\" The "
                             "audiobook is read by Shafak with Olivia Vinall and Samuel West.",
                     "first": "Madame Bovary, if you have never read it. Any modern translation will do, and the novel "
                              "is shorter than this one.",
                     "caveat": "At 608 pages it is a commitment, and books with many narrators can feel like a set of "
                               "stories rather than one. Shafak's writing is lush, which some readers love and some "
                               "find too much."},
                    {"kind": "book", "title": "The Daughters", "year": 2027, "creator": "Leslie Jamison",
                     "date": "2027-02-09",
                     "released": "Hardcover, ebook and audiobook · Little, Brown · 304 pages",
                     "why": "Three women bound by one ancient myth: Pasiphaë, wife of King Minos, at Knossos in 1550 BC, "
                            "after the birth of the Minotaur; Beth, a suburban wife in New York in 1944; and Jac, who "
                            "goes to Crete in 1997 grieving her father and finds a community of women in the hills.",
                     "note": "Leslie Jamison is best known for her essays. The Empathy Exams (2014) made her name, and "
                             "The Recovering (2018) is one of the best books written about addiction, a mix of memoir "
                             "and literary history. The Daughters is her first novel since The Gin Closet in 2010, and "
                             "it takes on a story most people know only from the other side: the Minotaur myth told by "
                             "his mother. Retellings of Greek myths from the women's point of view have been one of the "
                             "big trends in fiction since Madeline Miller's Circe, and many of them are thinner than "
                             "their premise. Jamison's strength is thinking hard about why people want what they want, "
                             "and Pasiphaë, whose desire is the whole scandal of the story, is the right subject for "
                             "her. Splitting the book across three centuries gives it room to ask what the myth means "
                             "to women who have never been to Crete.",
                     "first": "Nothing. The myth is simple enough, and the novel tells it.",
                     "caveat": "Three timelines in 304 pages means each one gets about a hundred. The myth involves a "
                               "queen and a bull, and the book is not going to look away from it."},
                    {"kind": "book", "title": "Otter Music", "year": 2027, "creator": "Karen Joy Fowler",
                     "date": "2027-02-23",
                     "released": "Hardcover, ebook and audiobook · G. P. Putnam's Sons · 176 pages",
                     "why": "Lainey Miller studies sea otters and other endangered animals on the coast at Santa Cruz. "
                            "She is divorced, happily alone and, according to her niece, has no fun at all. The novel "
                            "asks whether ecosystems, and people, can be saved.",
                     "note": "Karen Joy Fowler wrote The Jane Austen Book Club and We Are All Completely Beside "
                             "Ourselves, which was shortlisted for the Booker in 2014 and keeps one of the best "
                             "secrets in modern fiction. She "
                             "writes about animals and the people who study them better than almost anyone, with a "
                             "lot of humor and no sentimentality. Otter Music is short and sounds like a book about "
                             "living through bad news: the wildfires, the rising sea and, the publisher says, the "
                             "state of democracy all come into it. Sea otters came back from near extinction on the "
                             "California coast in the last century, which makes them a good choice for a novel "
                             "about whether any of it can be fixed.",
                     "first": "We Are All Completely Beside Ourselves (2013), which is better read before anyone tells "
                              "you what it is about.",
                     "caveat": "A short, quiet novel about a woman and her work. If you want plot, look elsewhere on "
                               "this list."},
                    {"kind": "book", "title": "Serious Music", "year": 2027, "creator": "Percival Everett",
                     "date": "2027-03-02",
                     "released": "Hardcover, ebook and audiobook · Doubleday · 304 pages",
                     "why": "In 1918 Arthur Champion is one of a handful of Black students at the Oberlin Conservatory "
                            "of Music when he crosses a vindictive professor and finds himself in the United States "
                            "Army. The novel follows him through the next decade, from the trenches to the jazz clubs "
                            "of Harlem and, somehow, into Woodrow Wilson's White House.",
                     "note": "Percival Everett has had the kind of late career most writers only imagine. Erasure "
                             "(2001) became the film American Fiction, which won the Oscar for its screenplay, and "
                             "James (2024), his retelling of Huckleberry Finn from the point of view of the enslaved "
                             "Jim, won the National Book Award and the Pulitzer Prize. Serious Music sounds like a "
                             "companion to James: another Black man moving through a famous stretch of American "
                             "history, and the publisher calls it darkly comic. Everett is very funny "
                             "and very angry at the same time, and the Wilson White House, which segregated the federal "
                             "government, is a fine target for both. He writes quickly and in many styles, so expect "
                             "something different from James even if the subject sounds close.",
                     "first": "James (2024), if you haven't read it. Erasure is the best place to see how funny he is.",
                     "caveat": "Everett's books can switch tone without warning, from slapstick to brutal violence in a "
                               "page, and the First World War and the racism of the period are not softened."},
                    {"kind": "book", "title": "Miss Lambert Steps Aboard Danger", "year": 2027, "creator": "Kazuo Ishiguro",
                     "date": "2027-03-09",
                     "released": "Hardcover, ebook and audiobook · Knopf · 240 pages",
                     "why": "London, 1938. After a music hall matinee, Richard Hadley meets the mysterious Miss Lambert "
                            "and follows her, first to a secretive gathering in the country and then onto a train, "
                            "into a plot that is not what it seems.",
                     "note": "This is Kazuo Ishiguro's first novel since Klara and the Sun (2021), and by the sound of "
                             "it the lightest he has written. The Associated Press described it as spy "
                             "fiction with the comic touch of P. G. Wodehouse, and his American publisher calls it an "
                             "entertainment, which is the word Graham Greene used for his own thrillers. Ishiguro has "
                             "been here before in a way. The Remains of the Day looks back on the 1930s, and on a "
                             "country house full of men making secret arrangements with Germany, seen by a butler who "
                             "doesn't understand what he is looking at. A light book from a writer whose novels are "
                             "usually quietly devastating could be the surprise of the year, or it could be a minor "
                             "one, and at 240 pages it costs little to find out. \"I defy any reader to resist Miss "
                             "Lambert's charms,\" says his editor at Knopf, Jordan Pavlin.",
                     "first": "Nothing. The Remains of the Day (1989) is the Ishiguro to read if you have only time for "
                              "one more.",
                     "caveat": "Ishiguro's narrators rarely say what they mean, and his plots can leave a lot unexplained "
                               "even when they are thrillers. Readers expecting a straight spy story may be puzzled."},
                    {"kind": "book", "title": "Blaze", "year": 2027, "creator": "Emma Donoghue",
                     "date": "2027-03-09",
                     "released": "Hardcover, ebook and audiobook · Summit Books (Simon & Schuster) · 160 pages",
                     "why": "New York, 2040. A pigeon called Blaze is born into a world where death is always close, in "
                            "a flock that lives in an abandoned tower and keeps away from the Talls, the last starving "
                            "humans. When she saves an older pigeon who lives alone, he brings with him a forgotten "
                            "history of the time before.",
                     "note": "Emma Donoghue has written about a boy and his mother locked in one room (Room, which she "
                             "adapted into the film), a starving child in 1850s Ireland (The Wonder) and a train "
                             "racing towards a famous crash in Paris (The Paris Express, 2025). She keeps choosing a "
                             "small, sealed-off point of view and making it big. A novel narrated by a pigeon after "
                             "the end of the world is the most extreme version of that yet. Animal stories told from "
                             "the inside have a long history, from Watership Down to Black Beauty, and they can be "
                             "more frightening than books about people, because the animals can't understand what "
                             "happened. At 160 pages it is the shortest book on this list.",
                     "first": "Nothing. Room (2010) is the Donoghue most people start with.",
                     "caveat": "A short book about the end of the human world, seen by a bird, will be bleak in places. "
                               "Some readers just won't get past the premise."},
                ],
            },
            {
                "format": "books",
                "id": "book-club",
                "label": "Book club picks",
                "heading": "Four big stories for a long winter",
                "intro": [
                    "These are the novels you are most likely to see in a book club or on a train this winter: big, "
                    "warm, plotted stories from writers whose last books sold in the millions. Three of them go back "
                    "in time, and one goes to Capri.",
                ],
                "picks": [
                    {"kind": "book", "title": "The Jewel of Sugar Hill", "year": 2027, "creator": "Fiona Davis",
                     "date": "2027-01-26",
                     "released": "Hardcover, ebook and audiobook · Dutton · 384 pages",
                     "why": "Two stories around the Morris-Jumel Mansion in upper Manhattan. In the 1800s Eliza Brown, a "
                            "woman from nothing, meets Aaron Burr and sets her heart on the house. In 2010 an architect, "
                            "Abby Dorrance, looks into the death of her father, a developer who fell at the crumbling, "
                            "supposedly haunted mansion.",
                     "note": "Fiona Davis writes novels about New York buildings: The Address is set in the Dakota, The "
                             "Lions of Fifth Avenue in the public library, The Magnolia Palace in the Frick. This one "
                             "has the best real story yet. The Morris-Jumel Mansion, built in 1765, is the oldest house "
                             "in Manhattan, and George Washington used it as his headquarters in 1776. Eliza Jumel, the "
                             "real woman behind Davis's Eliza, rose from poverty to become one of the richest women in "
                             "New York and married Aaron Burr there in 1833, long after he had shot Alexander "
                             "Hamilton. The house is said to be haunted, and it is a museum now, so you can visit after "
                             "you finish.",
                     "first": "Nothing. If you like it, The Lions of Fifth Avenue (2020) is her most popular.",
                     "caveat": "Davis's books follow a pattern, a past and a present with a secret joining them, and if "
                               "you have read one you know the shape. The modern half is usually the weaker one."},
                    {"kind": "book", "title": "Three Sisters", "year": 2027, "creator": "Jojo Moyes",
                     "date": "2027-02-09",
                     "released": "Hardcover, ebook and audiobook · Pamela Dorman Books · 400 pages",
                     "why": "Cora Gallo hasn't spoken to her father, the world-famous painter Florian, or to her sisters "
                            "Diana and Kiki, for nearly ten years. Then he summons all three to his house on Capri, "
                            "where his young nurse Sophia is waiting, and makes an announcement that splits them.",
                     "note": "Jojo Moyes wrote Me Before You and The Giver of Stars, and her strength is that her "
                             "characters are funny and furious with each other at the same time, which is what families "
                             "are like. Three estranged sisters and a vain, ageing artist on an Italian island in summer "
                             "is about as good a setup as this kind of book gets, a little King Lear and a lot of "
                             "sunshine. A famous father, a young nurse and a family announcement point to an "
                             "obvious guess, and the pleasure of a Moyes novel is usually in how far from the obvious "
                             "it ends up.",
                     "first": "Nothing. It is a standalone.",
                     "caveat": "Moyes can be sentimental, and a dying-father plot pushes in that direction. It is a "
                               "family drama first, so readers wanting a romance may find less of one than the cover "
                               "suggests."},
                    {"kind": "book", "title": "The Last Days of Vic & Coco", "year": 2027, "creator": "Taylor Jenkins Reid",
                     "date": "2027-03-02",
                     "released": "Hardcover, ebook and audiobook · Atria Books",
                     "why": "Summer 1974. Victoria Lucchese and Colette Wilson hustle pool halls across America under the "
                            "names Crown Vic and Baby Blue, while Nixon falls and the country runs short of gas. They "
                            "plan one last payday that will need them to trust each other completely.",
                     "note": "Taylor Jenkins Reid's novels, from The Seven Husbands of Evelyn Hugo to Daisy Jones & the "
                             "Six, are about women who are very good at something glamorous, told with the confidence "
                             "of a writer who knows exactly how to keep you turning pages. This is her tenth, and the "
                             "first about a con. Pool hustling is a lovely subject: it is a sport and a performance "
                             "and a lie at the same time, and you have to lose on purpose before you win. The 1970s "
                             "setting, the road and a stretch in a small Arizona town all play to her strengths. The "
                             "audiobook is read by Julia Whelan, Jennifer Beals, Edoardo Ballerini and Danny "
                             "Burstein, which is a good sign, since the audio of Daisy Jones was a big part of that "
                             "book's success.",
                     "first": "Nothing. It stands alone. Daisy Jones & the Six (2019) is the one to try if you haven't "
                              "read her.",
                     "caveat": "Reid's books are built for speed, and readers who want depth of character sometimes find "
                               "them glossy. Expect a love story inside the con."},
                    {"kind": "book", "title": "Christabel", "year": 2027, "creator": "Kate Morton",
                     "date": "2027-03-30",
                     "released": "Hardcover, ebook and audiobook · Mariner Books · 352 pages",
                     "why": "Bel Wilder, an Australian publisher, goes to a village in the Cotswolds to buy the rights to "
                            "a forgotten fairy tale, The Blackbird's Tale, from its reclusive author, Iris Archer. Iris "
                            "tells her about her childhood friend Christabel, and a violent night in a cottage in the "
                            "woods decades ago.",
                     "note": "Kate Morton writes long, layered mysteries about English houses and the secrets families "
                             "bury in them: The Forgotten Garden, The Secret Keeper, The Lake House and, most recently, "
                             "Homecoming (2023), which went back to her native Australia. Christabel brings together "
                             "the things she does best, a fairy tale, a ruined cottage and an old woman deciding how "
                             "much to tell, and at 352 pages it is shorter than her usual. A story within a story, with "
                             "a book at the center of the mystery, is a good fit for a writer whose plots work like "
                             "nesting dolls. It is the last book on this list to come out, on the final Tuesday in "
                             "March.",
                     "first": "Nothing. The Forgotten Garden (2008) is the one most readers love best.",
                     "caveat": "Morton's mysteries take their time, and the twist is usually about who someone really "
                               "was rather than who did it. Readers who want pace should look at the thrillers below."},
                ],
            },
            {
                "format": "books",
                "id": "thrillers",
                "label": "Thrillers",
                "heading": "Three thrillers, one a month",
                "intro": [
                    "The three biggest thrillers of the winter come out a month apart, which is convenient. All three "
                    "are standalones, and two of them are by writers whose earlier books have become a film or a "
                    "series.",
                ],
                "picks": [
                    {"kind": "book", "title": "The Things You'll Never Know", "year": 2027, "creator": "Ashley Audrain",
                     "date": "2027-01-12",
                     "released": "Hardcover, ebook and audiobook · Pamela Dorman Books · 400 pages",
                     "why": "Fiona finds out that she is dead, and finds that she can still watch her family. Then her "
                            "daughter finds her diary, and a betrayal Fiona kept secret all her life starts coming out.",
                     "note": "Ashley Audrain's first novel, The Push (2021), was a sensation: a mother who suspects her "
                             "daughter is dangerous, and nobody believes her. It was the kind of thriller people argued "
                             "about, because it was really about the things mothers are not supposed to feel. This is "
                             "her third, and narrating a family drama from beyond the grave is a bold way to keep that "
                             "going. A dead narrator can't explain herself to the people she is watching, which gives a "
                             "story about secrets a sharp edge. The publisher calls it a story of \"motherhood, desire, "
                             "betrayal, and loss,\" which is Audrain's ground exactly.",
                     "first": "Nothing. The Push is the one to try if you like it.",
                     "caveat": "Audrain's books are dark and sad, about bad things in families, and this one starts with "
                               "a death. If you want a puzzle more than a tragedy, start with the next one."},
                    {"kind": "book", "title": "Twist", "year": 2027, "creator": "Alice Feeney",
                     "date": "2027-02-23",
                     "released": "Hardcover, ebook and audiobook · Flatiron Books · 352 pages",
                     "why": "Ariella, a flight attendant, has two lives: a husband called Noah and a daughter in a village, "
                            "and a husband called Luka in London. Darcy lives on a London street with the partner she "
                            "thinks is perfect. When a husband is killed, his wife wants to know who did it, and why.",
                     "note": "Alice Feeney is known for one thing above everything else: twists you don't see coming, so "
                             "a book called Twist is either very confident or a dare. Her novels, Rock Paper Scissors "
                             "and Daisy Darker among them, are built like puzzle boxes, with narrators you shouldn't "
                             "trust and a final reveal that reorders everything before it. His & Hers, her 2020 "
                             "novel, became a Netflix series. A flight attendant with two families is a premise that "
                             "explains itself in a sentence, and the fun will be in how many of the people on the "
                             "page are lying. Feeney spent years as a BBC journalist, and her books move fast.",
                     "first": "Nothing. Rock Paper Scissors (2021) is her best.",
                     "caveat": "Feeney's endings divide readers: some love being fooled, others feel cheated. If you "
                               "hated the last twist of hers you read, this is more of the same."},
                    {"kind": "book", "title": "The Sleepwalker", "year": 2027, "creator": "Freida McFadden",
                     "date": "2027-03-23",
                     "released": "Print, ebook and audiobook · Poisoned Pen Press",
                     "why": "Samantha is a nurse by day. At night she has a deadly secret: the men she goes after are "
                            "predators and abusers. Then bodies start turning up that she doesn't remember killing, "
                            "and a darkly charming stranger comes into her life.",
                     "note": "Freida McFadden is the most popular thriller writer in America right now. The Housemaid "
                             "grew into a series of books and a 2025 film with Sydney Sweeney and Amanda Seyfried, and she "
                             "publishes several books a year, all of them short and all of them hard to put down. She "
                             "is also a practising doctor, and her books about hospitals and nurses tend to be the "
                             "best ones, because she knows the details. This is a standalone, not part of the "
                             "Housemaid series. A heroine who kills men who deserve it, and a sleepwalker who doesn't "
                             "know what she has done, are two good ideas in one book, and McFadden is good at making "
                             "you suspect everyone, including the narrator.",
                     "first": "Nothing. The Housemaid (2022) is the place to start if you're new to her.",
                     "caveat": "McFadden's books are fast and pulpy, and the writing is plain. Readers who like a "
                               "slower, more literary thriller won't find it here."},
                ],
            },
            {
                "format": "books",
                "id": "magic",
                "label": "Magic and time travel",
                "heading": "Two novels with a little magic in them",
                "intro": [
                    "Last, two books for readers who like their fiction a step away from the real world: a cozy fantasy "
                    "about a cheese shop, and a family novel about a grandfather who invented time travel.",
                ],
                "picks": [
                    {"kind": "book", "title": "The Magical Cheese Emporium", "year": 2027, "creator": "Sarah Beth Durst",
                     "date": "2027-01-19",
                     "released": "Hardcover, ebook and audiobook · Bramble · The Spellshop series, book 4",
                     "why": "Eloren goes home to the island of Dew and her grandmother's cheese shop, which is in trouble "
                            "because the governor has put a heavy tax on small businesses. With Garyn, her childhood "
                            "friend, she sets out to save it.",
                     "note": "Sarah Beth Durst's Spellshop books are cozy fantasy, the kind of story where the stakes "
                             "are a shop, a village and a slow romance, and the reader is promised that everything "
                             "will be all right. The Spellshop (2024) was one of the books that made the genre "
                             "popular, about a librarian who flees a revolution with a pile of forbidden spell books "
                             "and opens a shop selling jam and small spells on a remote island. Each book is a standalone set in the same world, "
                             "so you can start here. A fight against an unfair tax, a family business and a lot of "
                             "cheese is exactly what January calls for. It is the easiest book on this list.",
                     "first": "Nothing. Each book stands alone, though The Spellshop (2024) is where it began.",
                     "caveat": "Cozy fantasy is cozy on purpose. If you want danger, dark magic or a big war, this is "
                               "the wrong shelf."},
                    {"kind": "book", "title": "The Traveling House", "year": 2027, "creator": "Kristin Cashore",
                     "date": "2027-02-16",
                     "released": "Hardcover, ebook and audiobook · Dutton · 416 pages",
                     "why": "Matilda Frost, in her mid-thirties and newly single, goes back to a family whose history was "
                            "changed for ever when her grandfather Winthrop invented time travel. His time-box stopped "
                            "working when he died. When her uncle Ant disappears, she starts digging into the old "
                            "man's secrets.",
                     "note": "Kristin Cashore wrote Graceling (2008) and the books that followed it, Fire, Bitterblue "
                             "and Winterkeep, some of the best fantasy written for teenagers in the last twenty years, "
                             "about young women with dangerous gifts working out whether to use them. The Traveling "
                             "House is published for adults by Dutton, and it sounds less like a time-travel adventure "
                             "than a family novel about a family that once had time travel and lost it. That is a "
                             "clever way to use the idea. The interesting question is not where Winthrop went but what "
                             "it did to his children and grandchildren to grow up with a man who could leave whenever "
                             "he liked. The audiobook runs about fourteen and a half hours and is read by Alex "
                             "McKenna.",
                     "first": "Nothing. It has nothing to do with the Graceling books.",
                     "caveat": "Time travel plots can tie themselves in knots, and Cashore's books take time to set up "
                               "their worlds. Readers expecting Graceling should know this is a different kind of book."},
                ],
            },
        ],
        "also": [
            ("A Court of Forgotten Melody and The Stars Look Like Home (January 12).",
             "The seventh A Court of Thorns and Roses novel from Sarah J. Maas and a new T. J. Klune. Both are in our "
             "broader winter releases guide, with Heather Fawcett's Emily Wilde's History of Dark Faerie (January 19) "
             "and Samantha Shannon's The Moth Reborn (February 23)."),
            ("The Two-Body Problem and The Last Testimony (February 2).",
             "Ali Hazelwood's sequel to The Love Hypothesis and Veronica Roth's second Sixth Faction book, which brings "
             "back Tris and Four from Divergent."),
            ("The One We Buried by Kate Alice Marshall (January 26).",
             "A supernatural thriller set at a place called Sanctuary Springs, where old secrets come back after a "
             "killing."),
            ("Instant Classic by Kate Fagan (January 26).",
             "A filmmaker, a WNBA star and a forgotten basketball star of the 1950s, from the author of The Three "
             "Lives of Cate Kay."),
            ("The Society of Forgotten Wives by Pam Jenoff (February 2).",
             "Historical fiction inspired by true events, about a young woman at a newspaper who helps wives search "
             "for their missing husbands."),
            ("Stealing George Washington by Daniel Stone (February 2).",
             "Nonfiction from William Morrow about the theft of Washington's diary and other papers from the Library "
             "of Congress in the 1890s, and the Secret Service case that followed."),
            ("The Emotional Lives of Parents by Lisa Damour (February 9).",
             "The psychologist behind The Emotional Lives of Teenagers turns to the anger, envy and shame parents feel "
             "and how it shapes their children."),
            ("The Missing by C. J. Box (February 23).",
             "Two children and their nanny vanish from an elk camp, and the Wyoming game warden Joe Pickett "
             "investigates."),
            ("Cardinal Rule by Liz Tomforde (March 2).",
             "The first book in a new four-part romance series about the Wilder family in Northern California."),
        ],
        "plan_heading": "A plan for the winter",
        "plan": [
            "If you use a library, place your holds now. The queues for the big names fill up long before publication "
            "day, and a hold placed in November is often ready in the first week. The books on this list most likely "
            "to have long waits are the Reid, the McFadden, the Moyes and the Maas from our winter guide.",
            "January 12 is the heaviest day of the season, with Shafak, Audrain, Maas and Klune all out that Tuesday. "
            "Shafak is 608 pages, so if you want to read her this winter, start in January. The Magical Cheese "
            "Emporium on the 19th is a good book for the week after, and The Jewel of Sugar Hill on the 26th. "
            "February has Moyes and Jamison on the 9th, Cashore on the 16th, and Fowler and Feeney on the 23rd.",
            "March is the strongest month, and it is a month of short books. Everett and Reid are out on the 2nd, "
            "Ishiguro and Donoghue on the 9th, McFadden on the 23rd and Morton on the 30th. Blaze, Otter Music and "
            "the Ishiguro are all under 250 pages, so you could read all three in a long weekend. Publishing dates "
            "rarely move once a book is in the catalog, but they can, and the date at the top of the page says when "
            "we last checked.",
        ],
        "method": [
            "Prepared by OmniTrackr with AI assistance and reviewed by the site owner before publishing. None of these "
            "books had been published when we wrote about them, and we have not read them, so this is a guide to what "
            "we think is worth reading, not a set of reviews. We worked from the publishers' own catalog pages and the "
            "coverage listed below, checked each date against a second source, and picked books we would recommend "
            "to a friend, with an honest note on who should skip them.",
            "Book dates are the firmest of any format. Once a book has a catalog page and a price, it almost always "
            "comes out on that Tuesday. They differ between countries, though, and a UK or Irish edition can come from "
            "another publisher on another day: Blaze, for instance, is published by Picador in the UK. The dates, publishers and page counts here are for the first US "
            "edition, usually the hardcover.",
        ],
        "related": [
            ("The best books of 2026", "/best-of/2026/books"),
            ("The Cosmere in order", "/in-order/cosmere"),
            ("Discworld in order", "/in-order/discworld"),
            ("Winter 2027 movies", "/new-releases/winter-2027-movies"),
            ("How to track books on OmniTrackr", "/book-tracker"),
        ],
        "sources": [
            ("Penguin Random House: In One Brief Moment All Eternity", "https://www.penguinrandomhouse.com/books/743979/in-one-brief-moment-all-eternity-by-elif-shafak/"),
            ("BookBrowse: In One Brief Moment All Eternity", "https://www.bookbrowse.com/bb_briefs/detail/index.cfm/ezine_preview_number/27688/in-one-brief-moment-all-eternity"),
            ("Hachette Book Group: The Daughters", "https://www.hachettebookgroup.com/titles/leslie-jamison/the-daughters/9780316375184/"),
            ("Penguin Random House: Otter Music", "https://www.penguinrandomhouse.com/books/837913/otter-music-by-karen-joy-fowler/"),
            ("Penguin Random House: Serious Music", "https://www.penguinrandomhouse.com/books/818005/serious-music-by-percival-everett"),
            ("Lit Hub: Kazuo Ishiguro's next novel is a 1930s spy caper", "https://lithub.com/kazuo-ishiguros-next-novel-out-next-year-will-be-a-1930s-spy-caper/"),
            ("Associated Press: a new Ishiguro novel heads to 1930s England", "https://abcnews.com/Entertainment/wireStory/new-ishiguro-heads-1930s-england-spies-music-wit-133921076"),
            ("Simon & Schuster: Blaze", "https://www.simonandschuster.net/books/Blaze/Emma-Donoghue/9781668240427"),
            ("The Bookseller: Picador buys Emma Donoghue's Blaze", "https://www.thebookseller.com/rights/picador-snaps-up-emma-donoghues-brilliant-novel-blaze"),
            ("Penguin Random House: The Jewel of Sugar Hill", "https://www.penguinrandomhouse.com/books/734631/the-jewel-of-sugar-hill-by-fiona-davis/"),
            ("Penguin Random House: Three Sisters", "https://www.penguinrandomhouse.com/books/778236/three-sisters-by-jojo-moyes/"),
            ("Grazia: Taylor Jenkins Reid's new book", "https://graziamagazine.com/us/articles/taylor-jenkins-reid-new-book-vic-coco/"),
            ("Kirkus: the cast of the new Taylor Jenkins Reid audiobook", "https://www.kirkusreviews.com/news-and-features/articles/cast-of-new-taylor-jenkins-reid-audiobook-revealed/"),
            ("NetGalley: Christabel", "https://www.netgalley.com/catalog/book/919874"),
            ("Penguin Random House: The Things You'll Never Know", "https://www.penguinrandomhouse.com/books/746128/the-things-youll-never-know-by-ashley-audrain/"),
            ("NetGalley: Twist", "https://www.netgalley.com/catalog/book/892770"),
            ("Books of Brilliance: The Sleepwalker release date", "https://booksofbrilliance.com/2026/10/10/freida-mcfadden-the-sleepwalker-release-date/"),
            ("Penguin Random House: The Traveling House", "https://penguinrandomhouse.com/books/773905/the-traveling-house-by-kristin-cashore"),
            ("Darling Reader: fantasy books releasing in January 2027", "https://www.darlingreader.com/fantasy-books-releasing-in-january-2027/"),
            ("NetGalley: Stealing George Washington", "https://www.netgalley.com/catalog/book/900664"),
            ("The Bookish Bulletin: most anticipated January 2027 books", "https://www.thebookishbulletin.com/blog/most-anticipated-january-2027-books"),
            ("The Bookish Bulletin: most anticipated February 2027 books", "https://www.thebookishbulletin.com/blog/most-anticipated-february-2027-books"),
            ("The Bookish Bulletin: most anticipated March 2027 books", "https://www.thebookishbulletin.com/blog/most-anticipated-march-2027-books"),
            ("Beyond the Bookends: January 2027 book releases", "https://www.beyondthebookends.com/january-2027-book-releases/"),
            ("Beyond the Bookends: February 2027 book releases", "https://www.beyondthebookends.com/february-2027-book-releases/"),
            ("Penguin Random House: coming soon", "https://www.penguinrandomhouse.com/the-read-down/coming-soon/"),
        ],
    },
}
