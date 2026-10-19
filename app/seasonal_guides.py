"""Seasonal hubs: hand-written picks for a time of year (/halloween first).

Each season is one evergreen page at a fixed path, refreshed each year, so links
and search results keep working. ``window`` is the stretch of the year (month-day,
inclusive, UTC) when members see the season's card on their dashboard and the
public guides promote it; the page itself stays readable all year.

Pick fields:
    kind     movie | tv | anime | game | book | album
    fright   1 to 5 on the season's ``scale``
    time     what it asks of you, in plain words
    why      why it is on the shelf
    note     how to approach it
    caveat   what to know first (content, pace, availability)

Every pick joins the Pick for me pool (pick.py), which is how saving works.
A new season is a new entry here plus a theme block in seasonal.css.
"""

SEASONS = {
    "halloween": {
        "path": "/halloween",
        "name": "Halloween",
        "theme": "halloween",
        "window": ("10-01", "11-02"),
        "published": "2026-10-19",
        "reviewed": "2026-10-19",
        "search_title": "Halloween picks: horror and spooky movies, shows, anime, games, books and music",
        "headline": "Halloween, at your own fright level",
        "deck": ("Twenty-four horror and spooky picks across movies, TV, anime, games, books and music, "
                 "sorted by how scared you want to be, with a plan for every kind of Halloween night."),
        "summary": ("Horror and spooky picks for Halloween across six formats, from gentle ghost stories for "
                    "the whole family to games that will keep the lights on, each with a fright level and caveat."),
        "card": "Twenty-four spooky picks, sorted by how scared you want to be.",
        "intro": [
            "Halloween recommendations tend to assume one kind of person: someone who already loves horror and wants "
            "the scariest thing available. Most of us are not that person every year. Some Octobers you want a proper "
            "fright with the lights off. Others you want a ghost story you can watch with a nine-year-old, or something "
            "loud and silly for a room full of friends who will talk over it anyway.",
            "So this hub is sorted by mood rather than by format. There are four shelves, each with one pick in every "
            "format OmniTrackr tracks: a film, a series, an anime, a game, a book and an album. Every pick carries a "
            "fright level from one to five, a plain note on how much time it asks of you, and a caveat that says what "
            "is actually in it. Choose the shelf that matches the night you are planning, then choose by format.",
            "If you want the quieter, stranger side of October, the kind that unsettles without a single jump scare, "
            "this month's Discover edition covers that ground, and none of its six picks are repeated here.",
        ],
        "scale": [
            (1, "Spooky, not scary", "Atmosphere and costumes. Fine for most children and for anyone who avoids horror."),
            (2, "A few jolts", "Some tension and the odd shock, nothing that lingers after the credits."),
            (3, "Unsettling", "Dread that builds, a few disturbing images, the kind of thing you think about in the shower."),
            (4, "Properly frightening", "Designed to scare, with sustained tension. Best when you know what you signed up for."),
            (5, "Lights on afterwards", "The strongest material here. Read the caveat before you start."),
        ],
        "shelves": [
            {
                "key": "start-gently",
                "name": "Start gently",
                "tagline": "For people who think they do not like horror.",
                "intro": [
                    "Most people who say they hate horror actually hate one part of it: gore, jump scares, or the feeling "
                    "of being trapped with something cruel. These six keep the atmosphere and the curiosity, a house with "
                    "rules you do not understand yet, a voice on the other side of a door, and go easy on the rest.",
                    "None of them goes above three on the fright scale, and most sit at one or two. If one of them works for "
                    "you, the shelf above it is the next step.",
                ],
                "picks": [
                    {"kind": "movie", "title": "The Others", "year": 2001, "creator": "Alejandro Amenábar", "fright": 2,
                     "time": "One film, about an hour and three quarters",
                     "why": "A mother keeps her two children in a fog-bound house on Jersey with the curtains drawn, because "
                            "the children cannot bear sunlight. Then the new servants arrive and the house starts to feel crowded. "
                            "Almost everything frightening happens in sound and shadow, and the film earns its chills by making "
                            "you watch the edges of the frame.",
                     "note": "Watch it without reading anything about it first. It is a story built around one turn, and it "
                             "plays better the less you expect. Turn the lights down rather than off.",
                     "caveat": "A handful of loud shocks and a grieving, sometimes harsh mother. No gore. Its central turn may "
                               "upset anyone recently bereaved."},
                    {"kind": "tv", "title": "The Haunting of Bly Manor", "year": 2020, "creator": "Mike Flanagan", "fright": 2,
                     "time": "Nine episodes, a long weekend",
                     "why": "A young American au pair takes a job at an English country house in the 1980s, caring for two "
                            "orphaned children who are a little too polite. Loosely drawn from Henry James's The Turn of the Screw, "
                            "it is more of a gothic romance than a horror series, and its ghosts are mostly sad rather than "
                            "vicious. It is the gentlest way into a genre that usually wants you to flinch.",
                     "note": "The first two episodes are the slowest. The eighth, told almost entirely in black and white as an "
                             "old story, is where the series explains itself, so give it until then before deciding.",
                     "caveat": "Some unsettling images of faceless figures, a death by drowning and grief throughout. "
                               "It is a different story from the earlier Hill House series and stands on its own."},
                    {"kind": "anime", "title": "Mob Psycho 100", "year": 2016, "creator": "ONE", "fright": 1,
                     "time": "Twelve episodes for the first season",
                     "why": "Mob is a shy middle-schooler with enormous psychic power who works for a fraudulent exorcist "
                            "for pocket money. The spirits they deal with are sometimes grotesque and often "
                            "ridiculous, and the animation goes wildly expressive whenever Mob's emotions boil over. It is "
                            "really a story about kindness, which is a surprisingly good Halloween mood.",
                     "note": "The art style is deliberately scrappy for the first episode or two. Stick with it until the first "
                             "big fight, when the animation shows what it can do.",
                     "caveat": "Cartoonish monsters and some bloody fights. Three seasons in total; the first stands well alone."},
                    {"kind": "game", "title": "Inscryption", "year": 2021, "creator": "Daniel Mullins Games", "fright": 3,
                     "time": "A weekend-length game",
                     "why": "You wake in a dark cabin across a table from a figure you can only see by his eyes, and he wants to "
                            "play cards. The deck-building is excellent on its own, but the real game is what happens when you "
                            "stand up from the table and start searching the room. It is a puzzle box that gets stranger the "
                            "further in you go.",
                     "note": "Go in knowing as little as possible and do not look anything up when it seems to change shape. "
                             "You do not need to know other card games; it teaches everything it needs.",
                     "caveat": "Creepy rather than frightening, but it asks you to sacrifice creatures and includes some "
                               "self-harm imagery played for unease (an eye, a tooth)."},
                    {"kind": "book", "title": "Mexican Gothic", "year": 2020, "creator": "Silvia Moreno-Garcia", "fright": 3,
                     "time": "A novel of around three hundred pages",
                     "why": "In 1950s Mexico, a glamorous socialite drives into the mountains to check on her newly married cousin, "
                            "who has written a frantic letter from her husband's crumbling English-built mansion. Noemí is witty, "
                            "stubborn and very hard to frighten, which makes her the ideal guide through a house whose family has "
                            "something wrong at its root.",
                     "note": "The first half is slow, mannered gothic, all dinners and rules. The final third accelerates hard, "
                             "so leave yourself an evening to finish it in one go.",
                     "caveat": "Contains eugenics and racism as themes, sexual coercion, incest and body horror in the last act."},
                    {"kind": "album", "title": "Juju", "year": 1981, "creator": "Siouxsie and the Banshees", "fright": 1,
                     "time": "Nine songs, well under an hour",
                     "why": "Not a horror album, but one of the records that taught goth what it sounded like: chiming, needling "
                            "guitars, tom-heavy drums and Siouxsie singing about voodoo dolls, night shifts and Halloween itself. "
                            "It is the right soundtrack for carving pumpkins and the wrong one for falling asleep.",
                     "note": "Start with Spellbound and Arabian Knights to hear the band at full tilt, then go back to the "
                             "beginning and play it through.",
                     "caveat": "Night Shift is sung from the point of view of a killer. Otherwise the darkness is all mood."},
                ],
            },
            {
                "key": "lights-off",
                "name": "Lights off",
                "tagline": "For when you want to be properly scared.",
                "intro": [
                    "This is the shelf for people who already know what they like and want it done well. Every pick here "
                    "is designed to frighten you, and each one does it differently: grief that turns into something worse, "
                    "cold and isolation, a village that keeps repeating the same June, a creature that hunts by sound.",
                    "Read the caveats. Two of these sit at five on the fright scale for good reason, and one asks for a "
                    "lot of your time. Nobody wins anything by finishing a film they are not enjoying.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Hereditary", "year": 2018, "creator": "Ari Aster", "fright": 5,
                     "time": "One film, just over two hours",
                     "why": "After her secretive mother dies, a miniature artist and her family begin to come apart, first in "
                            "the ordinary ways grief breaks people and then in ways that are not ordinary at all. Toni Collette's "
                            "performance is the engine. The film is frightening because it takes the family's pain seriously "
                            "before it turns supernatural.",
                     "note": "This is a slow film until it very suddenly is not. Watch it with someone, and plan a short walk or "
                             "a sillier episode of something afterwards.",
                     "caveat": "Graphic death, including the death of a child, self-harm, decapitation, occult imagery and "
                               "intense family conflict. Not for a casual night in."},
                    {"kind": "tv", "title": "The Terror", "year": 2018, "creator": "David Kajganich and Soo Hugh", "fright": 4,
                     "time": "Ten episodes for the first season",
                     "why": "In 1845 two Royal Navy ships set out to find the Northwest Passage and become locked in Arctic ice. "
                            "Based on Dan Simmons's novel about the real lost Franklin expedition, the first season builds horror "
                            "from cold, scurvy, bad leadership and dwindling food long before you see what is hunting the crew. "
                            "It is historical drama with something in the dark.",
                     "note": "The first season is a complete story; the second is an unrelated tale with a new cast. Watch with "
                             "subtitles on, because the ships are full of accents and wind.",
                     "caveat": "Graphic injuries, amputation, cannibalism, disease and death in large numbers. Slow, bleak pacing "
                               "by design."},
                    {"kind": "anime", "title": "Higurashi: When They Cry", "year": 2006, "creator": "Studio Deen", "fright": 4,
                     "time": "Twenty-six episodes for the first season",
                     "why": "A boy moves to Hinamizawa, a sleepy rural village in June 1983, and makes friends with a cheerful group "
                            "of girls. Then he learns about the annual festival and the deaths that follow it, and the story starts "
                            "over from the beginning with something slightly different. Each arc is a new attempt at the same "
                            "few weeks, and the cute art style makes the violence land harder.",
                     "note": "The early episodes play like a slice-of-life comedy on purpose. The structure only makes sense after "
                             "the first two or three arcs; trust it. The answer arcs come in the second season.",
                     "caveat": "Graphic violence, torture, child abuse, suicide and paranoia. The art and animation are dated and "
                               "uneven."},
                    {"kind": "game", "title": "Alien: Isolation", "year": 2014, "creator": "Creative Assembly", "fright": 5,
                     "time": "A long game, around fifteen to twenty hours",
                     "why": "Fifteen years after the first film, Ellen Ripley's daughter Amanda boards a failing space station looking "
                            "for answers and finds a single alien that cannot be killed. It hunts by sound, learns your habits and "
                            "can appear from any vent. Few games have ever made a locker feel like such a fragile place to hide.",
                     "note": "Play with headphones. The motion tracker beeps, which is the point: using it can give you away. Medium "
                             "difficulty is tense enough for most players.",
                     "caveat": "Sustained, exhausting tension with long stretches of hiding and frequent deaths that send you back "
                               "to the last save point. Some gore. Saving is manual, at wall terminals."},
                    {"kind": "book", "title": "The Shining", "year": 1977, "creator": "Stephen King", "fright": 4,
                     "time": "A long novel, best over a week of evenings",
                     "why": "Jack Torrance, a recovering alcoholic with a temper, takes a job as winter caretaker of the Overlook "
                            "Hotel in the Colorado Rockies and brings his wife and his psychic five-year-old son. The novel is "
                            "much more interested in Jack than Kubrick's film is, which makes it sadder and, in places, more "
                            "frightening: you watch a man who loves his family lose the fight with himself.",
                     "note": "Even if you know the film by heart, read it. The hotel's topiary animals and room 217 are scarier on "
                             "the page, and the ending is entirely different.",
                     "caveat": "Domestic violence, alcoholism, child endangerment and a ghost in a bathtub you will not forget. "
                               "Some dated language."},
                    {"kind": "album", "title": "Suspiria", "year": 1977, "creator": "Goblin", "fright": 3,
                     "time": "A short soundtrack album",
                     "why": "The Italian prog-rock band Goblin scored Dario Argento's film about an American ballet student at a "
                            "German dance academy run by witches. The title theme pairs a music-box melody with whispered voices, "
                            "a bouzouki and pounding drums, and it is genuinely upsetting to listen to alone in the dark. It is "
                            "also, inconveniently, very catchy.",
                     "note": "Play it loud while the rest of your night is getting ready, then turn it off before you start the film.",
                     "caveat": "Instrumental, with unsettling whispers and screams. The film itself is far more violent than the "
                               "music; this pick is the album."},
                ],
            },
            {
                "key": "family",
                "name": "Spooky, not scary",
                "tagline": "For a Halloween with the whole family.",
                "intro": [
                    "Children like being a little frightened in the same way adults do, as long as they know the story is "
                    "on their side. These six are made for that: witches, ghosts and haunted woods with a warm centre, "
                    "pitched so that an adult can enjoy them too rather than simply sit through them.",
                    "Fright levels here are judged for children roughly seven and up. Younger children vary a great deal, "
                    "so the caveats say exactly what might be too much.",
                ],
                "picks": [
                    {"kind": "movie", "title": "ParaNorman", "year": 2012, "creator": "Sam Fell and Chris Butler", "fright": 2,
                     "time": "One film, about an hour and a half",
                     "why": "Norman can see and talk to the dead, which makes him a weirdo at school and a disappointment at home. "
                            "When his small New England town's three-hundred-year-old witch's curse comes due, he is the only "
                            "one who can stop it. Laika's stop-motion is beautiful and funny, and the film's ending is braver "
                            "and kinder than most family films dare.",
                     "note": "A good bridge between little-kid Halloween and the real thing. Talk afterwards about who the witch "
                             "really was.",
                     "caveat": "Zombies, a frightening storm sequence, mild crude humour and a scene about a child's death. "
                               "Probably too intense for under-sevens."},
                    {"kind": "tv", "title": "Over the Garden Wall", "year": 2014, "creator": "Patrick McHale", "fright": 1,
                     "time": "Ten short episodes, under two hours in all",
                     "why": "Two half-brothers, anxious Wirt and cheerful Greg, are lost in a strange autumnal forest called the "
                            "Unknown, trying to get home with the help of a grumpy bluebird. It looks like an old picture book "
                            "and sounds like a vintage radio show, and its gentle eeriness feels made for the end of October. "
                            "It is short enough to watch in one sitting.",
                     "note": "Watch it in order over one evening with the lights low. Adults tend to love it as much as children "
                             "do, sometimes more.",
                     "caveat": "A few frightening images of the Beast, a creature in the woods, and themes of being lost. "
                               "Gentle by Halloween standards."},
                    {"kind": "anime", "title": "Natsume's Book of Friends", "year": 2008, "creator": "Brain's Base", "fright": 1,
                     "time": "Thirteen episodes for the first season, each a complete story",
                     "why": "Natsume, an orphaned teenager who has always seen spirits, inherits his grandmother's book of names: "
                            "the yokai she beat in contests and bound to her. Now they keep turning up to ask for their names back. "
                            "With a bodyguard spirit who looks like a lucky cat, each episode is a small, often tender ghost story "
                            "about loneliness and letting go.",
                     "note": "Each episode stands alone, which makes this ideal for a bedtime ghost story. There are many seasons "
                             "if it becomes a family habit.",
                     "caveat": "Some spirits look grotesque and a few episodes are sad. Pick the subtitled or dubbed version that "
                               "suits your children's reading."},
                    {"kind": "game", "title": "Luigi's Mansion 3", "year": 2019, "creator": "Next Level Games", "fright": 1,
                     "time": "A game of about a dozen hours, easy to play in short sessions",
                     "why": "Luigi wins a free stay at a luxury hotel that turns out to be haunted, and has to rescue Mario and "
                            "friends floor by floor with a ghost-sucking vacuum. Each floor has its own theme, from a film studio "
                            "to a pirate ship, and the slapstick is pure cartoon. A second player can join as Gooigi, a gooey "
                            "copy of Luigi who can slip through grates.",
                     "note": "Perfect for a parent and child playing side by side. The second player can drop in and out at any time, "
                             "so a younger partner can join for the fun bits.",
                     "caveat": "Nintendo Switch only. Some boss fights are tricky for small hands. Ghosts pop out, but it is far "
                               "more silly than scary."},
                    {"kind": "book", "title": "Scary Stories to Tell in the Dark", "year": 1981, "creator": "Alvin Schwartz", "fright": 3,
                     "time": "Short tales, a few minutes each",
                     "why": "Alvin Schwartz collected American folklore and urban legends into very short stories meant to be read "
                            "aloud, complete with notes on when to jump at your listener. Several generations of children have been "
                            "delighted and properly frightened by them, and they still work perfectly by torchlight.",
                     "note": "Look for an edition with Stephen Gammell's original illustrations, which are the most frightening part. "
                             "Read the stories aloud and pre-read a few first so you know which ones are for which age.",
                     "caveat": "The illustrations are genuinely disturbing for younger children. Some stories involve death and "
                               "corpses. There are three volumes."},
                    {"kind": "album", "title": "The Nightmare Before Christmas", "year": 1993, "creator": "Danny Elfman", "fright": 1,
                     "time": "A soundtrack album, under an hour",
                     "why": "Danny Elfman wrote the songs for Henry Selick's stop-motion film and sang Jack Skellington's parts himself. "
                            "This Is Halloween is the obvious opener for any party, but the album is full of real songs, from "
                            "Jack's restless Lament to Sally's quiet one. It is spooky, funny and singable.",
                     "note": "Put it on while you decorate or carve pumpkins, and it will be playing in your house until December.",
                     "caveat": "Mild menace from Oogie Boogie. Otherwise suitable for any age."},
                ],
            },
            {
                "key": "with-friends",
                "name": "Bring friends",
                "tagline": "For horror that is better with a crowd.",
                "intro": [
                    "Some horror is best shared. Comedy, co-op games and very silly ghosts work in a room full of people "
                    "because the jokes and shrieks become part of the night. These six are chosen to survive a party: "
                    "you can talk over them, arrive late, or play in a group without losing the thread.",
                    "The fright levels vary, but every pick here is funny on purpose, or funny because you are not alone.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Shaun of the Dead", "year": 2004, "creator": "Edgar Wright", "fright": 2,
                     "time": "One film, about an hour and forty minutes",
                     "why": "Shaun is a London electronics salesman whose life revolves around his flatmate and his local pub. He is "
                            "so stuck in his routine that he fails to notice the zombie apocalypse for the first morning. Edgar "
                            "Wright's comedy is packed with visual jokes and sets up nearly every gag early, so second viewings "
                            "are even better.",
                     "note": "Plan for a crowd who will quote along. If your group has seen it, try spotting the setups in the first "
                             "twenty minutes.",
                     "caveat": "Gory deaths played for laughs, one sad death that is not, and plenty of swearing."},
                    {"kind": "tv", "title": "What We Do in the Shadows", "year": 2019, "creator": "Jemaine Clement", "fright": 1,
                     "time": "Six seasons; any episode works on its own",
                     "why": "Four vampire housemates in Staten Island, and their put-upon familiar Guillermo, try to conquer the New "
                            "World while struggling with modern life. Shot as a mock documentary and spun off from the 2014 film, "
                            "it is one of the funniest sitcoms of its time.",
                     "note": "Drop in anywhere for a party. For a binge, start at the beginning; the energy vampire Colin Robinson "
                             "gets better every season.",
                     "caveat": "Lots of blood played for laughs, sexual humour and strong language."},
                    {"kind": "anime", "title": "Ghost Stories", "year": 2000, "creator": "Studio Pierrot", "fright": 2,
                     "time": "Twenty episodes, each a short ghost of the week",
                     "why": "In Japanese, this is a straightforward children's series about kids fighting ghosts haunting their old "
                            "school. The English dub is another thing entirely: the voice cast was told they could improvise, and "
                            "turned it into a gleefully rude, fourth-wall-breaking comedy. It has a cult following for exactly that "
                            "reason, and it is perfect for a group who enjoy bad taste.",
                     "note": "For a party, choose the English dub. For a genuinely spooky children's series, choose the original "
                             "Japanese with subtitles. They are almost different shows.",
                     "caveat": "The dub's humour is crude and frequently offensive, including jokes about religion, race and "
                               "disability. Not for children despite how it looks."},
                    {"kind": "game", "title": "Phasmophobia", "year": 2020, "creator": "Kinetic Games", "fright": 4,
                     "time": "Short investigations, played as long as you like",
                     "why": "Up to four players are paranormal investigators with flashlights, thermometers and spirit boxes, trying "
                            "to work out which kind of ghost haunts a house before it gets angry. The game listens to your "
                            "microphone, so the ghost can hear you say its name. Hearing your friends' voices go quiet over the "
                            "radio is half the fun.",
                     "note": "Best with three or four friends on voice chat. One person reading the ghost guide while the others "
                             "explore keeps it funny until it suddenly is not.",
                     "caveat": "PC and consoles, with optional VR. Jump scares, chase sequences and swearing are likely when it "
                               "is played with friends. Some players find the voice recognition quite unsettling."},
                    {"kind": "book", "title": "Horrorstör", "year": 2014, "creator": "Grady Hendrix", "fright": 3,
                     "time": "A short novel, one or two evenings",
                     "why": "Strange things are happening overnight at Orsk, a flat-pack furniture superstore suspiciously like a "
                            "certain Swedish one, so a few employees agree to stay after closing to find out why. The book is "
                            "designed like a furniture catalogue, and it is very funny about retail jobs before it becomes "
                            "properly creepy about them.",
                     "note": "Pass it around a group. The catalogue pages at the start of each chapter are worth showing off, and "
                             "anyone who has worked retail will recognise the managers.",
                     "caveat": "Torture and body horror in the second half. The physical edition is better than an e-book because "
                               "of the design."},
                    {"kind": "album", "title": "Thriller", "year": 1982, "creator": "Michael Jackson", "fright": 1,
                     "time": "Nine songs, about three quarters of an hour",
                     "why": "The best-selling album ever made earns its spot here for one song. The title track's werewolf funk, "
                            "creaking doors and Vincent Price's closing rap make it the most played Halloween record on earth, "
                            "and the rest of the album keeps a party dancing long after the costumes come off.",
                     "note": "Save the title track for when everyone has arrived. If anyone knows the choreography, that is your "
                             "entertainment sorted.",
                     "caveat": "None for content. Thriller is a party staple, so it is the least surprising pick in this hub."},
                ],
            },
        ],
        "nights": [
            {"name": "A quiet night in, a little nervous",
             "plan": "Start with The Others with the lights low and a blanket. If you enjoyed being uneasy, read the first "
                     "chapters of Mexican Gothic in bed; if you did not, Mob Psycho 100 will put you back together."},
            {"name": "Friends round, nobody wants nightmares",
             "plan": "Shaun of the Dead first, Thriller during the food, then two episodes of the Ghost Stories dub when "
                     "everyone is loud enough to enjoy it. Keep What We Do in the Shadows ready for when the room goes quiet."},
            {"name": "Children under ten",
             "plan": "Over the Garden Wall in one sitting, before trick-or-treating. Afterwards, The Nightmare Before Christmas "
                     "soundtrack and a floor of Luigi's Mansion 3 together. Keep ParaNorman and Scary Stories for next year."},
            {"name": "A horror fan who wants to be scared again",
             "plan": "Hereditary, with the lights off and your phone in another room. Or make it a long weekend: the first "
                     "season of The Terror, or Alien: Isolation with headphones on hard difficulty."},
            {"name": "Online with friends far away",
             "plan": "A few rounds of Phasmophobia on voice chat, then agree on one film to start at the same moment. "
                     "Shaun of the Dead is easy to sync and easy to talk over."},
        ],
        "faq": [
            ("What should I watch on Halloween if I don't like horror?",
             "Start with The Others or The Haunting of Bly Manor. Both have ghosts and atmosphere but very little gore, and "
             "both rate two out of five on our fright scale. If you would rather laugh, What We Do in the Shadows and Shaun "
             "of the Dead are comedies first."),
            ("What are good scary games to play with friends?",
             "Phasmophobia is the best-known co-op ghost hunting game, for up to four players. For a family with a younger "
             "player, Luigi's Mansion 3 has a two-player mode where the second player controls Gooigi."),
            ("Which Halloween picks are suitable for kids?",
             "The Spooky, not scary shelf is chosen for children roughly seven and up: Over the Garden Wall, Natsume's Book of "
             "Friends, Luigi's Mansion 3 and The Nightmare Before Christmas are gentle; ParaNorman and Scary Stories to Tell in "
             "the Dark are a step more frightening. Each pick's caveat says exactly what might be too much."),
            ("How does the fright scale work?",
             "It runs from one, spooky but not scary, to five, where you may want the lights on afterwards. It is an editorial "
             "judgement about how frightening a pick is for a typical adult, and for the family shelf a typical child of "
             "seven or more, not a content rating."),
            ("Where are the quieter, stranger October picks?",
             "This month's Discover edition, Stay with the strange, covers unsettling stories that avoid jump scares, from "
             "A Ghost Story to The Haunting of Hill House. None of its picks are repeated here."),
        ],
        "method": [
            "Prepared by OmniTrackr and reviewed by the site owner before publishing. We started from the kinds of night "
            "people actually plan around Halloween, then chose one pick per format for each, looking for range in tone, "
            "age and length rather than a ranked list of the scariest titles. Several famous picks are missing on purpose "
            "because they appear in our other October guides.",
            "Fright levels and caveats are editorial judgements, checked against the works themselves and public sources, "
            "not official ratings. Runtimes, editions and platforms vary by region. Links go to OmniTrackr title pages, not "
            "shops, and nothing here is sponsored.",
        ],
    },
}
