"""Seasonal hubs: hand-written picks for a time of year (/halloween, /holidays).

Each season is one evergreen page at a fixed path, refreshed each year, so links
and search results keep working. ``window`` is the stretch of the year (month-day,
inclusive, UTC) when members see the season's card on their dashboard and the
public guides promote it; the page itself stays readable all year.

Pick fields:
    kind     movie | tv | anime | game | book | album
    level    1 to 5 on the season's ``scale`` (named by ``scale_name``: fright, festive)
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
        "summary": ("Horror and spooky picks for Halloween in six formats, from ghost stories the whole family "
                    "can watch to games you'll want the lights on for. Each has a fright level and a caveat."),
        "card": "Twenty-four spooky picks, sorted by how scared you want to be.",
        "card_cta": "Find your fright level",
        "scale_name": "Fright",
        "scale_eyebrow": "THE FRIGHT SCALE",
        "scale_heading": "How scary is it?",
        "plan_label": "Plan your night",
        "plan_heading": "Five kinds of Halloween night",
        "related_heading": "More for October",
        "related_months": ["10"],
        "edition_notes": {"10": "The quieter side of October: six unsettling works that skip the jump scares."},
        "intro": [
            "Halloween recommendations tend to assume one kind of person: someone who already loves horror and wants "
            "the scariest thing available. Most of us aren't that person every year. Some Octobers you want a proper "
            "fright with the lights off. Others you want a ghost story you can watch with a nine-year-old, or something "
            "loud and silly for a room full of friends who will talk over it anyway.",
            "So this hub is sorted by mood first. There are four shelves, and each has one pick in every format "
            "OmniTrackr tracks: a film, a series, an anime, a game, a book and an album. Every pick has a fright level "
            "from one to five, a note on how much time it takes, and a caveat that lists what is actually in it. "
            "Find the shelf that fits the night you're planning. Then pick a format.",
            "For the slower, stranger side of October, where nothing jumps out at you and the unease stays with you "
            "anyway, see this month's Discover edition. None of its six picks appear here.",
        ],
        "scale": [
            (1, "Spooky, not scary", "Atmosphere and costumes. Fine for most children and for anyone who avoids horror."),
            (2, "A few jolts", "Some tension and the odd shock. Nothing that follows you to bed."),
            (3, "Unsettling", "Dread that builds and a few disturbing images, the kind you find yourself thinking about in the shower."),
            (4, "Properly frightening", "Made to scare, with long stretches of tension. Best when you know what you signed up for."),
            (5, "Lights on afterwards", "The strongest material here. Read the caveat before you start."),
        ],
        "shelves": [
            {
                "key": "start-gently",
                "name": "Start gently",
                "tagline": "For people who think they don't like horror.",
                "intro": [
                    "Most people who say they hate horror actually hate one part of it: gore, jump scares, or the feeling "
                    "of being trapped with something cruel. These six keep the atmosphere and the mystery (a house with "
                    "rules you don't understand yet, a voice on the other side of a door) and go easy on the rest.",
                    "None of them goes above three on the fright scale, and most sit at one or two. If one of them works for "
                    "you, try the next shelf.",
                ],
                "picks": [
                    {"kind": "movie", "title": "The Others", "year": 2001, "creator": "Alejandro Amenábar", "level": 2,
                     "time": "One film, about an hour and three quarters",
                     "why": "A mother keeps her two children in a fog-bound house on Jersey with the curtains drawn, because "
                            "the children cannot bear sunlight. Then the new servants arrive and the house starts to feel crowded. "
                            "Almost all of the fear comes from sound and shadow, and you spend most of the film staring at the "
                            "edges of the frame, waiting for something to move.",
                     "note": "Watch it without reading anything about it first. The whole story turns on one reveal, and it "
                             "works better the less you expect. Keep a lamp on somewhere in the room.",
                     "caveat": "A handful of loud shocks and a grieving, sometimes harsh mother. No gore. Its central turn may "
                               "upset anyone recently bereaved."},
                    {"kind": "tv", "title": "The Haunting of Bly Manor", "year": 2020, "creator": "Mike Flanagan", "level": 2,
                     "time": "Nine episodes, a long weekend",
                     "why": "A young American au pair takes a job at an English country house in the 1980s, caring for two "
                            "orphaned children who are a little too polite. Loosely drawn from Henry James's The Turn of the Screw, "
                            "it plays more like a gothic romance than a horror series, and most of its ghosts are sad, lost "
                            "figures. For a genre that usually wants you to flinch, it is a gentle way in.",
                     "note": "The first two episodes are the slowest. The eighth, told almost entirely in black and white as an "
                             "old story, is where the series explains itself, so give it until then before deciding.",
                     "caveat": "Some unsettling images of faceless figures, a death by drowning and grief throughout. "
                               "The story has no link to the earlier Hill House series, so you can start here."},
                    {"kind": "anime", "title": "Mob Psycho 100", "year": 2016, "creator": "ONE", "level": 1,
                     "time": "Twelve episodes for the first season",
                     "why": "Mob is a shy middle-schooler with enormous psychic power who works for a fraudulent exorcist "
                            "for pocket money. The spirits they deal with are sometimes grotesque and often "
                            "ridiculous, and the animation goes wildly expressive whenever Mob's emotions boil over. Underneath "
                            "it all is a story about a boy trying to be kind, which suits Halloween better than you'd think.",
                     "note": "The art style is deliberately scrappy for the first episode or two. Stick with it until the first "
                             "big fight, when the animation shows what it can do.",
                     "caveat": "Cartoonish monsters and some bloody fights. Three seasons in total; the first stands well alone."},
                    {"kind": "game", "title": "Inscryption", "year": 2021, "creator": "Daniel Mullins Games", "level": 3,
                     "time": "A weekend-length game",
                     "why": "You wake in a dark cabin across a table from a figure you can only see by his eyes, and he wants to "
                            "play cards. The deck-building is excellent, and then you stand up from the table and start searching "
                            "the room, which is where the game really begins. Each layer you uncover is stranger than the "
                            "one before.",
                     "note": "Go in knowing as little as possible and do not look anything up when it seems to change shape. "
                             "You do not need to know other card games; it teaches everything it needs.",
                     "caveat": "More creepy than frightening. It does ask you to sacrifice creatures, and some self-harm "
                               "imagery is played for unease (an eye, a tooth)."},
                    {"kind": "book", "title": "Mexican Gothic", "year": 2020, "creator": "Silvia Moreno-Garcia", "level": 3,
                     "time": "A novel of around three hundred pages",
                     "why": "In 1950s Mexico, a glamorous socialite drives into the mountains to check on her newly married cousin, "
                            "who has written a frantic letter from her husband's crumbling English-built mansion. Noemí is witty, "
                            "stubborn and very hard to frighten, which makes her the ideal guide through a house whose family has "
                            "something wrong at its root.",
                     "note": "The first half is slow, mannered gothic, all dinners and rules. The final third accelerates hard, "
                             "so leave yourself an evening to finish it in one go.",
                     "caveat": "Contains eugenics and racism as themes, sexual coercion, incest and body horror in the last act."},
                    {"kind": "album", "title": "Juju", "year": 1981, "creator": "Siouxsie and the Banshees", "level": 1,
                     "time": "Nine songs, well under an hour",
                     "why": "One of the records that taught goth what it sounded like: chiming, needling guitars, tom-heavy "
                            "drums and Siouxsie singing about voodoo dolls, night shifts and Halloween itself. Nothing on it "
                            "is horror in the strict sense. Put it on while you carve pumpkins, and take it off before "
                            "you try to sleep.",
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
                    "This shelf is for people who already know what they like and want it done well. Every pick here "
                    "is meant to frighten you, and each goes about it differently: grief that turns into something worse, "
                    "cold and isolation, a village that keeps repeating the same June, a creature that hunts by sound.",
                    "Read the caveats. Two of these sit at five on the fright scale, and they earned it. One asks for a "
                    "lot of your time. Nobody wins anything by finishing a film they are not enjoying.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Hereditary", "year": 2018, "creator": "Ari Aster", "level": 5,
                     "time": "One film, just over two hours",
                     "why": "After her secretive mother dies, a miniature artist and her family begin to come apart, first in "
                            "the ordinary ways grief breaks people and then in ways that are not ordinary at all. Toni Collette's "
                            "performance drives the whole thing. The film scares you as much as it does because it treats the "
                            "family's pain seriously before anything supernatural happens.",
                     "note": "This is a slow film until it very suddenly is not. Watch it with someone, and plan a short walk or "
                             "a sillier episode of something afterwards.",
                     "caveat": "Graphic death, including the death of a child, self-harm, decapitation, occult imagery and "
                               "intense family conflict. Not for a casual night in."},
                    {"kind": "tv", "title": "The Terror", "year": 2018, "creator": "David Kajganich and Soo Hugh", "level": 4,
                     "time": "Ten episodes for the first season",
                     "why": "In 1845 two Royal Navy ships set out to find the Northwest Passage and become locked in Arctic ice. "
                            "Based on Dan Simmons's novel about the real lost Franklin expedition, the first season builds horror "
                            "from cold, scurvy, bad leadership and dwindling food long before you see what is hunting the crew. "
                            "It is a historical drama with something in the dark.",
                     "note": "The first season is a complete story; the second is an unrelated tale with a new cast. Watch with "
                             "subtitles on, because the ships are full of accents and wind.",
                     "caveat": "Graphic injuries, amputation, cannibalism, disease and death in large numbers. The pacing is "
                               "slow and bleak on purpose."},
                    {"kind": "anime", "title": "Higurashi: When They Cry", "year": 2006, "creator": "Studio Deen", "level": 4,
                     "time": "Twenty-six episodes for the first season",
                     "why": "A boy moves to Hinamizawa, a sleepy rural village in June 1983, and makes friends with a cheerful group "
                            "of girls. Then he learns about the annual festival and the deaths that follow it, and the story starts "
                            "over from the beginning with something slightly different. Each arc is a new attempt at the same "
                            "few weeks. The cute art style makes the violence hit harder.",
                     "note": "The early episodes play like a slice-of-life comedy on purpose. The structure only makes sense after "
                             "the first two or three arcs, so trust it. The answer arcs come in the second season.",
                     "caveat": "Graphic violence, torture, child abuse, suicide and paranoia. The art and animation are dated and "
                               "uneven."},
                    {"kind": "game", "title": "Alien: Isolation", "year": 2014, "creator": "Creative Assembly", "level": 5,
                     "time": "A long game, around fifteen to twenty hours",
                     "why": "Fifteen years after the first film, Ellen Ripley's daughter Amanda boards a failing space station looking "
                            "for answers and finds a single alien that cannot be killed. It hunts by sound, learns your habits and "
                            "can appear from any vent. Few games have ever made a locker feel like such a fragile place to hide.",
                     "note": "Play with headphones. The motion tracker beeps, and that is the point: using it can give you away. "
                             "Medium difficulty is tense enough for most players.",
                     "caveat": "Hours of tension with long stretches of hiding, and frequent deaths that send you back "
                               "to the last save point. Some gore. Saving is manual, at wall terminals."},
                    {"kind": "book", "title": "The Shining", "year": 1977, "creator": "Stephen King", "level": 4,
                     "time": "A long novel, best over a week of evenings",
                     "why": "Jack Torrance, a recovering alcoholic with a temper, takes a job as winter caretaker of the Overlook "
                            "Hotel in the Colorado Rockies and brings his wife and his psychic five-year-old son. The novel is "
                            "much more interested in Jack than Kubrick's film is, which makes it sadder and, in places, more "
                            "frightening. You watch a man who loves his family lose the fight with himself.",
                     "note": "Read it even if you know the film by heart. The hotel's topiary animals and room 217 are scarier on "
                             "the page, and the ending is entirely different.",
                     "caveat": "Domestic violence, alcoholism, child endangerment and a ghost in a bathtub you will not forget. "
                               "Some dated language."},
                    {"kind": "album", "title": "Suspiria", "year": 1977, "creator": "Goblin", "level": 3,
                     "time": "A short soundtrack album",
                     "why": "The Italian prog-rock band Goblin scored Dario Argento's film about an American ballet student at a "
                            "German dance academy run by witches. The title theme pairs a music-box melody with whispered voices, "
                            "a bouzouki and pounding drums, and it is genuinely upsetting to listen to alone in the dark. It is "
                            "also, inconveniently, very catchy.",
                     "note": "Play it loud while the rest of your night is getting ready, then turn it off before you start the film.",
                     "caveat": "Instrumental, with unsettling whispers and screams. The film is far more violent than the "
                               "music, and this pick is only the album."},
                ],
            },
            {
                "key": "family",
                "name": "Spooky, not scary",
                "tagline": "For a Halloween with the whole family.",
                "intro": [
                    "Children like being a little frightened in the same way adults do, as long as they know the story is "
                    "on their side. These six are made for that: witches, ghosts and haunted woods with a warm centre, "
                    "pitched so that the adults in the room have a good time too.",
                    "Fright levels here are judged for children roughly seven and up. Younger children vary a great deal, "
                    "so each caveat says exactly what might be too much.",
                ],
                "picks": [
                    {"kind": "movie", "title": "ParaNorman", "year": 2012, "creator": "Sam Fell and Chris Butler", "level": 2,
                     "time": "One film, about an hour and a half",
                     "why": "Norman can see and talk to the dead, which makes him a weirdo at school and a disappointment at home. "
                            "When his small New England town's three-hundred-year-old witch's curse comes due, he is the only "
                            "one who can stop it. Laika's stop-motion is beautiful and funny, and the ending is braver "
                            "and kinder than most family films dare.",
                     "note": "A good bridge between little-kid Halloween and the real thing. Talk afterwards about who the witch "
                             "really was.",
                     "caveat": "Zombies, a frightening storm sequence, mild crude humour and a scene about a child's death. "
                               "Probably too intense for under-sevens."},
                    {"kind": "tv", "title": "Over the Garden Wall", "year": 2014, "creator": "Patrick McHale", "level": 1,
                     "time": "Ten short episodes, under two hours in all",
                     "why": "Two half-brothers, anxious Wirt and cheerful Greg, are lost in a strange autumnal forest called the "
                            "Unknown, trying to get home with the help of a grumpy bluebird. It looks like an old picture book "
                            "and sounds like a vintage radio show. The eeriness is mild and very autumnal, and the whole "
                            "series runs shorter than a lot of films.",
                     "note": "Watch it in order over one evening with the lights low. Adults tend to love it as much as children "
                             "do, sometimes more.",
                     "caveat": "A few frightening images of the Beast, a creature in the woods, and themes of being lost. "
                               "Mild by Halloween standards."},
                    {"kind": "anime", "title": "Natsume's Book of Friends", "year": 2008, "creator": "Brain's Base", "level": 1,
                     "time": "Thirteen episodes for the first season, each a complete story",
                     "why": "Natsume, an orphaned teenager who has always seen spirits, inherits his grandmother's book of names: "
                            "the yokai she beat in contests and bound to her. Now they keep turning up to ask for their names back. "
                            "He has a bodyguard spirit who looks like a lucky cat, and each episode is a small, often tender "
                            "ghost story about loneliness and letting go.",
                     "note": "Each episode stands alone, so one makes a good bedtime ghost story. There are many seasons "
                             "if it becomes a family habit.",
                     "caveat": "Some spirits look grotesque and a few episodes are sad. Pick the subtitled or dubbed version that "
                               "suits your children's reading."},
                    {"kind": "game", "title": "Luigi's Mansion 3", "year": 2019, "creator": "Next Level Games", "level": 1,
                     "time": "A game of about a dozen hours, easy to play in short sessions",
                     "why": "Luigi wins a free stay at a luxury hotel that turns out to be haunted, and has to rescue Mario and "
                            "friends floor by floor with a ghost-sucking vacuum. Each floor has its own theme, from a film studio "
                            "to a pirate ship, and the slapstick is pure cartoon. A second player can join as Gooigi, a gooey "
                            "copy of Luigi who can slip through grates.",
                     "note": "Made for a parent and child playing side by side. The second player can drop in and out at any time, "
                             "so a younger partner can join for the fun bits.",
                     "caveat": "Nintendo Switch only. Some boss fights are tricky for small hands. Ghosts pop out, but it is far "
                               "more silly than scary."},
                    {"kind": "book", "title": "Scary Stories to Tell in the Dark", "year": 1981, "creator": "Alvin Schwartz", "level": 3,
                     "time": "Short tales, a few minutes each",
                     "why": "Alvin Schwartz collected American folklore and urban legends into very short stories meant to be read "
                            "aloud, complete with notes on when to jump at your listener. Children have been delighted and "
                            "properly frightened by them for generations, and they still work by torchlight.",
                     "note": "Look for an edition with Stephen Gammell's original illustrations, which are the most frightening part. "
                             "Pre-read a few before you read them aloud, so you know which ones suit which age.",
                     "caveat": "The illustrations are genuinely disturbing for younger children. Some stories involve death and "
                               "corpses. There are three volumes."},
                    {"kind": "album", "title": "The Nightmare Before Christmas", "year": 1993, "creator": "Danny Elfman", "level": 1,
                     "time": "A soundtrack album, under an hour",
                     "why": "Danny Elfman wrote the songs for Henry Selick's stop-motion film and sang Jack Skellington's parts himself. "
                            "This Is Halloween is the obvious opener for any party, but the album is full of real songs, from "
                            "Jack's restless Lament to Sally's softer one, and most of them are funny as well as spooky.",
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
                    "because the jokes and the shrieks become part of the night. We picked these six to survive a party: "
                    "you can talk over them, arrive late, or play in a group without losing the thread.",
                    "The fright levels vary. Every pick here is funny, either on purpose or because you're not alone.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Shaun of the Dead", "year": 2004, "creator": "Edgar Wright", "level": 2,
                     "time": "One film, about an hour and forty minutes",
                     "why": "Shaun is a London electronics salesman whose life revolves around his flatmate and his local pub. He is "
                            "so stuck in his routine that he fails to notice the zombie apocalypse for the first morning. Edgar "
                            "Wright packs the film with visual jokes and sets up nearly every gag early, so second viewings "
                            "are even better.",
                     "note": "Expect a crowd who will quote along. If your group has seen it, try spotting the setups in the first "
                             "twenty minutes.",
                     "caveat": "Gory deaths played for laughs, one sad death that is not, and plenty of swearing."},
                    {"kind": "tv", "title": "What We Do in the Shadows", "year": 2019, "creator": "Jemaine Clement", "level": 1,
                     "time": "Six seasons; any episode works on its own",
                     "why": "Four vampire housemates in Staten Island, and their put-upon familiar Guillermo, try to conquer the New "
                            "World while struggling with modern life. Shot as a mock documentary and spun off from the 2014 film, "
                            "it is one of the funniest sitcoms of its time.",
                     "note": "Drop in anywhere for a party. For a binge, start at the beginning; the energy vampire Colin Robinson "
                             "gets better every season.",
                     "caveat": "Lots of blood played for laughs, sexual humour and strong language."},
                    {"kind": "anime", "title": "Ghost Stories", "year": 2000, "creator": "Studio Pierrot", "level": 2,
                     "time": "Twenty episodes, each a short ghost of the week",
                     "why": "In Japanese, this is a straightforward children's series about kids fighting ghosts haunting their old "
                            "school. The English dub is another thing entirely: the voice cast was told they could improvise, and "
                            "they turned it into a gleefully rude comedy that keeps breaking the fourth wall. That is why it has "
                            "a cult following, and why it suits a group with a taste for bad taste.",
                     "note": "For a party, choose the English dub. For a genuinely spooky children's series, choose the original "
                             "Japanese with subtitles. They are almost different shows.",
                     "caveat": "The dub's humour is crude and frequently offensive, including jokes about religion, race and "
                               "disability. Not for children, whatever it looks like."},
                    {"kind": "game", "title": "Phasmophobia", "year": 2020, "creator": "Kinetic Games", "level": 4,
                     "time": "Short investigations, played as long as you like",
                     "why": "Up to four players are paranormal investigators with flashlights, thermometers and spirit boxes, trying "
                            "to work out which kind of ghost haunts a house before it gets angry. The game listens to your "
                            "microphone, so the ghost can hear you say its name. Hearing your friends' voices go quiet over the "
                            "radio is half the fun.",
                     "note": "Best with three or four friends on voice chat. Have one person read the ghost guide while the others "
                             "explore. It stays funny until it suddenly isn't.",
                     "caveat": "PC and consoles, with optional VR. Expect jump scares, chase sequences and a lot of swearing "
                               "once friends are involved. Some players find the voice recognition quite unsettling."},
                    {"kind": "book", "title": "Horrorstör", "year": 2014, "creator": "Grady Hendrix", "level": 3,
                     "time": "A short novel, one or two evenings",
                     "why": "Strange things are happening overnight at Orsk, a flat-pack furniture superstore suspiciously like a "
                            "certain Swedish one, so a few employees agree to stay after closing to find out why. The book is "
                            "laid out like a furniture catalogue. It is very funny about retail jobs before it gets "
                            "properly creepy about them.",
                     "note": "Pass it around a group. The catalogue pages at the start of each chapter are worth showing off, and "
                             "anyone who has worked retail will recognise the managers.",
                     "caveat": "Torture and body horror in the second half. Get the physical edition if you can; the design "
                               "loses a lot as an e-book."},
                    {"kind": "album", "title": "Thriller", "year": 1982, "creator": "Michael Jackson", "level": 1,
                     "time": "Nine songs, about three quarters of an hour",
                     "why": "The best-selling album ever made is here for one song. The title track's werewolf funk, "
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
             "plan": "Start with The Others, the lights low and a blanket over your knees. If you enjoyed being uneasy, read the "
                     "first chapters of Mexican Gothic in bed; if you did not, Mob Psycho 100 will put you back together."},
            {"name": "Friends round, nobody wants nightmares",
             "plan": "Shaun of the Dead first, Thriller during the food, then two episodes of the Ghost Stories dub once "
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
             "The Spooky, not scary shelf is chosen for children roughly seven and up. Over the Garden Wall, Natsume's Book of "
             "Friends, Luigi's Mansion 3 and The Nightmare Before Christmas are gentle; ParaNorman and Scary Stories to Tell in "
             "the Dark are a step more frightening. Each pick's caveat says exactly what might be too much."),
            ("How does the fright scale work?",
             "It runs from one, spooky but not scary, to five, where you may want the lights on afterwards. We set each level "
             "ourselves, judging how frightening the pick is for a typical adult, or on the family shelf for a typical child "
             "of seven or more. Official age ratings are separate and may disagree with us."),
            ("Where are the quieter, stranger October picks?",
             "This month's Discover edition, Stay with the strange, collects unsettling stories with no jump scares, from "
             "A Ghost Story to The Haunting of Hill House. None of its picks are repeated here."),
        ],
        "method": [
            "Prepared by OmniTrackr and reviewed by the site owner before publishing. We started from the kinds of night "
            "people actually plan around Halloween, then chose one pick per format for each. We wanted a spread of tone, "
            "age range and length, so this is not a ranking of the scariest titles. Several famous picks are missing on "
            "purpose because they appear in our other October guides.",
            "Fright levels and caveats are our own judgements, checked against the works themselves and public sources. "
            "They are not official ratings. Runtimes, editions and platforms vary by region. Every link goes to an "
            "OmniTrackr title page and none go to shops. Nothing here is sponsored.",
        ],
    },

    "holidays": {
        "path": "/holidays",
        "name": "Holiday",
        "theme": "holiday",
        "window": ("11-03", "12-31"),
        "published": "2026-10-22",
        "reviewed": "2026-10-22",
        "search_title": "Holiday picks: Thanksgiving, Christmas and winter movies, shows, anime, games, books and music",
        "headline": "The holidays, as festive as you like",
        "deck": ("Twenty-four picks for Thanksgiving, Christmas and the long winter break across movies, TV, anime, games, "
                 "books and music, sorted by how much tinsel you want, with a plan for every kind of holiday."),
        "summary": ("Thanksgiving, Christmas and winter picks in six formats, from full-tinsel favourites to snowy stories "
                    "with no holiday at all. Each has a festive level and a caveat."),
        "card": "Twenty-four picks for Thanksgiving, Christmas and the cold, sorted by how festive you feel.",
        "card_cta": "Find your festive level",
        "scale_name": "Festive",
        "scale_eyebrow": "THE FESTIVE SCALE",
        "scale_heading": "How festive is it?",
        "plan_label": "Plan your break",
        "plan_heading": "Five kinds of holiday break",
        "related_heading": "More for the season",
        "related_months": ["11", "12"],
        "edition_notes": {},
        "intro": [
            "Most holiday recommendations are the same list: the twenty most Christmassy films ever made, ranked. That "
            "is useful for about a week. The season actually runs from the Thanksgiving weekend to New Year's Day, and it "
            "is full of very different evenings: a table of relatives who agree on nothing, a houseful of children with "
            "days off school, a quiet night when you have had enough tinsel for one year, a long trip home.",
            "So this hub is sorted by the kind of time you have. There are four shelves, "
            "and each has one pick in every format OmniTrackr tracks: a film, a series, an anime, a game, a book and an "
            "album. Every pick has a festive level from one to five, so you can tell at a glance whether it is wall-to-wall "
            "Christmas or simply cold outside, along with a note on how much time it takes and a caveat that lists what "
            "is actually in it.",
            "Not everybody celebrates Christmas, and plenty of people who do are tired of it by the twentieth of December. "
            "The Out in the cold shelf has almost no holiday in it, just snow, long nights and good company. Everything "
            "else leans festive to some degree, and the scale tells you how far.",
        ],
        "scale": [
            (1, "Just wintry", "Snow, cold or long nights, and no holiday to speak of. Safe for anyone who has had enough."),
            (2, "A hint of the season", "A holiday episode or a festive scene or two, with the season in the background."),
            (3, "Holiday setting", "Set over Thanksgiving or Christmas. The season shapes the story without taking it over."),
            (4, "Properly festive", "The holiday is the heart of it: lights, gifts, a big dinner, a family getting through it."),
            (5, "Full tinsel", "As Christmassy as it gets. Best saved for December, or for people who start early on purpose."),
        ],
        "shelves": [
            {
                "key": "around-the-table",
                "name": "Around the table",
                "tagline": "For Thanksgiving and the long weekend with family.",
                "intro": [
                    "For a lot of people in the United States, the Thanksgiving weekend is where the season starts, "
                    "and it has its own kind of evening: full, a bit tired, with three generations in one room trying "
                    "to agree on something to put on. Most of these six are about a meal or a trip home, and none of "
                    "them has much tinsel.",
                    "Most of them sit at one to three on the festive scale, so they work just as well for a Canadian "
                    "Thanksgiving in October, a Friendsgiving, or any long dinner with people you love and occasionally "
                    "argue with.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Planes, Trains and Automobiles", "year": 1987, "creator": "John Hughes", "level": 3,
                     "time": "One film, about an hour and a half",
                     "why": "Neal Page, a tightly wound advertising executive played by Steve Martin, only wants to "
                            "get from New York to Chicago in time for Thanksgiving dinner. Every flight, train and "
                            "rental car fails him, and he keeps ending up beside Del Griffith, a talkative "
                            "shower-curtain-ring salesman played by John Candy. It is very funny, and the last few "
                            "minutes are kinder than the rest of the film prepares you for.",
                     "note": "The perfect film for the night before you travel, or the night you arrive and need to "
                             "laugh about the journey. The shared motel room is the scene everyone quotes.",
                     "caveat": "Rated R in the US, almost entirely for one long, very sweary rant at a car rental desk. "
                               "Otherwise mild."},
                    {"kind": "tv", "title": "Friends", "year": 1994, "creator": "David Crane and Marta Kauffman", "level": 2,
                     "time": "Ten seasons; the Thanksgiving episodes stand alone",
                     "why": "Friends made a Thanksgiving episode almost every year it was on the air, and together "
                            "they work as a small festival of their own: a dinner that goes wrong in every possible "
                            "way, a game of touch football that gets far too competitive, a trifle with a layer of "
                            "beef in it, and a flashback episode where everyone confesses their worst Thanksgiving.",
                     "note": "Start with The One with All the Thanksgivings in the fifth season, then The One Where "
                             "Ross Got High in the sixth. Neither needs much context, which makes them good for a "
                             "room of relatives.",
                     "caveat": "Some jokes have aged badly, especially about weight and sexuality, and the flashback "
                               "episode leans on them. It is a long series if you get pulled back in."},
                    {"kind": "anime", "title": "Sweetness and Lightning", "year": 2016, "creator": "TMS Entertainment", "level": 1,
                     "time": "Twelve episodes, each built around one meal",
                     "why": "Kohei Inuzuka is a high-school maths teacher raising his small daughter Tsumugi alone "
                            "after his wife's death, and he cannot cook. When one of his students offers the kitchen "
                            "of her mother's restaurant, the three of them start making proper dinners together, one "
                            "dish an episode. It is a show about grief and food, and about a father learning that a "
                            "home needs people eating at the same table.",
                     "note": "Watch an episode before you cook and you may end up making the same dish; the recipes "
                             "are simple and real. One or two episodes at a time suits it best.",
                     "caveat": "The early episodes deal openly with a parent's death and a child's grief. Otherwise "
                               "suitable for all ages."},
                    {"kind": "game", "title": "Overcooked! 2", "year": 2018, "creator": "Ghost Town Games", "level": 1,
                     "time": "Short levels, a few minutes each",
                     "why": "Up to four players run a kitchen together, chopping, cooking, plating and washing up "
                            "against the clock while the kitchen itself refuses to sit still: counters slide apart, "
                            "floors move and things catch fire. It only works if everyone talks, which is why it is "
                            "the best game for a family that has just eaten together and still has energy to spend.",
                     "note": "Pair a patient adult with a younger player. Running the sink is a good job for a guest "
                             "who has never played a video game, and they will be cheered as loudly as anyone.",
                     "caveat": "Can turn loud and competitive, and the later levels are hard. It plays online too, "
                               "but it is best on one sofa."},
                    {"kind": "book", "title": "Little Women", "year": 1868, "creator": "Louisa May Alcott", "level": 3,
                     "time": "A long novel, best spread over the season",
                     "why": "It opens with Jo complaining that Christmas won't be Christmas without any presents, and "
                            "within a few pages the four March sisters have given their Christmas breakfast to a "
                            "poorer family down the road. Alcott follows Meg, Jo, Beth and Amy through a few years of "
                            "growing up in Massachusetts during the Civil War, and of all the books here it suits a "
                            "season with relatives best: the sisters squabble, borrow from each other and make up by "
                            "the end of the chapter.",
                     "note": "Read the first part over Thanksgiving and save the end for the slow days after "
                             "Christmas. If you know one of the films, the novel's middle chapters, which the films "
                             "tend to rush, are the best part.",
                     "caveat": "Beth's illness is famously sad. Some of the moralising feels old-fashioned, and "
                               "editions differ: some include the sequel, Good Wives, and some stop halfway, so check "
                               "what you have."},
                    {"kind": "album", "title": "The Last Waltz", "year": 1978, "creator": "The Band", "level": 2,
                     "time": "A long live album, over two hours",
                     "why": "On Thanksgiving Day 1976, The Band played their farewell concert at the Winterland "
                            "Ballroom in San Francisco, and the audience was served a turkey dinner before the show. "
                            "Bob Dylan, Joni Mitchell, Van Morrison and Neil Young were among the guests who joined "
                            "them on stage. The album is loud and loose and sounds like a party, which suits a table "
                            "where the dishes are going round.",
                     "note": "Put it on as people arrive and let it run through the meal. Martin Scorsese's film of "
                             "the night is a separate thing, and well worth a look later in the weekend.",
                     "caveat": "Loose and very much a concert recording, with long songs and a few rough edges. Nothing to "
                               "worry about for content."},
                ],
            },
            {
                "key": "deck-the-halls",
                "name": "Deck the halls",
                "tagline": "For when you want all the Christmas at once.",
                "intro": [
                    "Some people wait until December. Others put the tree up the day after Thanksgiving and play the same "
                    "album until New Year. This shelf is for the second group, and for the first group once December "
                    "arrives: lights, snow, Santa, carols and a happy ending in every format.",
                    "Every pick here sits at four or five on the festive scale. We mixed a few classics everyone knows with "
                    "a few that tend to get forgotten, and kept each one because it holds up on the second, third and tenth "
                    "visit.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Elf", "year": 2003, "creator": "Jon Favreau", "level": 5,
                     "time": "One film, about an hour and a half",
                     "why": "Buddy was raised at the North Pole by elves. At thirty, a good deal taller than everyone "
                            "around him, he learns that he is human and travels to New York to find his real father, "
                            "a grumpy publisher of children's books who is on Santa's naughty list. Will Ferrell "
                            "plays Buddy with complete sincerity. Buddy never realises he is in a comedy, and the "
                            "film is funnier for it.",
                     "note": "A good way to open the season with a mixed-age group. The stop-motion animals at the "
                             "North Pole are a fond nod to the television specials of the 1960s.",
                     "caveat": "Mild rude humour, including one belch that goes on for a very long time. Suitable for most ages."},
                    {"kind": "tv", "title": "Dash & Lily", "year": 2020, "creator": "Joe Tracz", "level": 5,
                     "time": "Eight half-hour episodes, two evenings",
                     "why": "In the weeks before Christmas in New York, Lily, who adores the holidays, leaves a red "
                            "notebook of dares on a shelf at the Strand bookstore, and Dash, who can't stand them, "
                            "picks it up. They write back and forth across the city without meeting. Based on Rachel "
                            "Cohn and David Levithan's novel Dash & Lily's Book of Dares, it is a short, sweet "
                            "romance with New York at its most twinkly.",
                     "note": "Eight short episodes make two perfect evenings in December. If you enjoy it, the novel spends "
                             "more time on each of the dares.",
                     "caveat": "There is only one season, but it ends on a satisfying note. Teenage romance and mild "
                               "language; fine for teens and up."},
                    {"kind": "anime", "title": "Tokyo Godfathers", "year": 2003, "creator": "Satoshi Kon", "level": 4,
                     "time": "One film, about an hour and a half",
                     "why": "On Christmas Eve in Tokyo, three homeless people (a middle-aged drinker with a past, a "
                            "former drag queen and a teenage runaway) find a baby abandoned among the rubbish and "
                            "decide to return her to her parents themselves. What follows is a chain of unlikely "
                            "coincidences, the kind a Christmas miracle story needs, happening to people the rest of "
                            "the city walks past.",
                     "note": "A good film for adults who want something festive that isn't sugary. Satoshi Kon's "
                             "other films are much stranger; this is his warmest and the easiest place to start.",
                     "caveat": "Some violence, heavy drinking and homelessness shown plainly, and dated jokes about Hana, a "
                               "trans woman, though the film treats her with real affection. Not for young children."},
                    {"kind": "game", "title": "Animal Crossing: New Horizons", "year": 2020, "creator": "Nintendo", "level": 4,
                     "time": "Ten minutes a day, all season long",
                     "why": "You move to a desert island and slowly turn it into a village of friendly animal "
                            "neighbours, in real time and on the real calendar. In December the island changes with "
                            "you: festive decorations and recipes arrive, trees drop ornaments when you shake them, "
                            "and Toy Day comes on Christmas Eve. Because it runs on your clock, it is the one pick "
                            "here you can visit for a few minutes every day of the season.",
                     "note": "Start in November so your island is settled by December. Visiting a friend's or relative's "
                             "island is part of the fun, and an easy way to keep in touch with someone far away.",
                     "caveat": "Nintendo Switch only, and visiting islands over the internet needs a paid Nintendo Switch "
                               "Online membership. Very slow by design."},
                    {"kind": "book", "title": "A Christmas Carol", "year": 1843, "creator": "Charles Dickens", "level": 5,
                     "time": "A short novel, an evening or two",
                     "why": "Ebenezer Scrooge, a miser who hates Christmas, is visited on Christmas Eve by the ghost "
                            "of his old business partner and then by three spirits who show him his past, his present "
                            "and the future he is heading for. It has been adapted so often that most people know the "
                            "plot without having read it. Read it anyway. Dickens is funnier and darker than nearly "
                            "every adaptation, and the book is short enough to finish in one evening.",
                     "note": "Read it aloud over five nights. It is divided into five short parts that Dickens called "
                             "staves, and he performed it to audiences himself for years. The Muppet version on the "
                             "Everyone on the sofa shelf makes a surprisingly faithful companion.",
                     "caveat": "Victorian prose takes a few pages to settle into. The Ghost of Christmas Yet to Come is "
                               "genuinely grim, and Tiny Tim's illness may upset younger listeners."},
                    {"kind": "album", "title": "Merry Christmas", "year": 1994, "creator": "Mariah Carey", "level": 5,
                     "time": "Ten songs, under an hour",
                     "why": "Most people know one song from this album, and it has climbed back to the top of the "
                            "charts most Decembers in recent years. The rest is better than its reputation: big "
                            "gospel-inflected carols, a 1960s-style wall of sound and a singer at the height of her "
                            "powers, clearly having a wonderful time. Nobody on it is being ironic about Christmas.",
                     "note": "Save All I Want for Christmas Is You for when the room needs lifting. O Holy Night and "
                             "Jesus Oh What a Wonderful Child show what the album is really about.",
                     "caveat": "Several of the carols are religious. Unashamedly loud and sentimental, which is either the "
                               "point or the problem."},
                ],
            },
            {
                "key": "out-in-the-cold",
                "name": "Out in the cold",
                "tagline": "Winter without the holidays.",
                "intro": [
                    "Not everybody celebrates Christmas, and even people who love it can reach the middle of December and "
                    "want something else. These six have snow, ice, long nights and remote places, and almost no holiday at "
                    "all. They are for the part of the season when you want the cold outside and nothing to decorate.",
                    "Everything here sits at one or two on the festive scale. Several are also good company for the quiet "
                    "days between Christmas and New Year, when nobody is quite sure what day it is.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Fargo", "year": 1996, "creator": "Joel and Ethan Coen", "level": 1,
                     "time": "One film, about an hour and a half",
                     "why": "A Minneapolis car salesman, badly in debt, hires two criminals to kidnap his own wife so "
                            "that her wealthy father will pay the ransom. Nothing goes to plan. The case lands with "
                            "Marge Gunderson, a heavily pregnant police chief from Brainerd who is polite to everyone "
                            "and much sharper than any of them notice. The snow is so white in places that it "
                            "swallows the horizon.",
                     "note": "Watch it on a cold night with something hot to drink. Frances McDormand won an Oscar "
                             "for Marge, and her scenes at home with her husband, Norm, are the warmest in the film.",
                     "caveat": "Sudden, bloody violence, including a famous scene with a woodchipper, and plenty of "
                               "swearing. Not a family film."},
                    {"kind": "tv", "title": "Northern Exposure", "year": 1990, "creator": "Joshua Brand and John Falsey", "level": 2,
                     "time": "Six seasons; the first has only eight episodes",
                     "why": "Joel Fleischman, a New York doctor whose medical school was paid for by the state of "
                            "Alaska, is sent to work off the debt in Cicely, a tiny town of philosophers, a former "
                            "astronaut and the occasional moose. Not much happens in most episodes. People argue "
                            "about books, the town DJ reads philosophy on air and the winter lasts for months, which "
                            "makes it good company on dark evenings.",
                     "note": "Start at the beginning, and don't skip Chris's morning broadcasts. They are the heart "
                             "of the show.",
                     "caveat": "Hard to find on streaming in some regions, and some home releases replaced the "
                               "original music for licensing reasons. A few dated attitudes."},
                    {"kind": "anime", "title": "A Place Further than the Universe", "year": 2018, "creator": "Madhouse", "level": 1,
                     "time": "Thirteen episodes",
                     "why": "Mari is a high-school student who keeps meaning to do something bold and never does. "
                            "Then she meets Shirase, who has been saving for years to go to Antarctica, where her "
                            "mother disappeared on an expedition. With two more friends they talk their way onto a "
                            "civilian research trip. It is funny the whole way there, and the episodes in Antarctica "
                            "hit hard.",
                     "note": "The early episodes are about getting there, and the ship's crossing of the Southern "
                             "Ocean is a highlight. Keep tissues near for the last two episodes.",
                     "caveat": "Grief is central to the story. Otherwise there is very little to worry about; good "
                               "for teens and up."},
                    {"kind": "game", "title": "Celeste", "year": 2018, "creator": "Maddy Makes Games", "level": 1,
                     "time": "A game of about eight to ten hours",
                     "why": "Madeline climbs Celeste Mountain, a snowy and slightly haunted peak, while dealing with "
                            "an anxiety that takes the shape of a second version of herself. The jumping is precise "
                            "and difficult, but the game is generous: you restart instantly after every fall, and "
                            "nothing punishes you for trying again. It is a game about not giving up that never makes "
                            "you feel stupid for failing.",
                     "note": "If a chapter gets too hard, Assist Mode lets you slow the game down or skip the hardest "
                             "parts, without judgement. The strawberries are entirely optional.",
                     "caveat": "Hard platforming and many deaths are part of the design. Deals openly with anxiety "
                               "and panic attacks."},
                    {"kind": "book", "title": "The Bear and the Nightingale", "year": 2017, "creator": "Katherine Arden", "level": 1,
                     "time": "A novel of around three hundred pages",
                     "why": "Vasya grows up in a village at the edge of a great forest in medieval Russia, where "
                            "winter takes up most of the year and the family sleeps on top of the stove to keep warm. "
                            "She can see the household spirits her neighbours leave bread for, and when a new priest "
                            "arrives and forbids the old offerings, the spirits weaken and something hungry stirs in "
                            "the woods. It reads like a fairy tale told beside the fire, with frost on every page.",
                     "note": "Read it in the darkest weeks of the year. The first third is slow and folkloric; once "
                             "Vasya meets the frost king Morozko, the pace picks up and rarely lets go.",
                     "caveat": "The first of a trilogy, though it ends well on its own. Some frightening creatures, deaths, "
                               "religious conflict and a young woman pushed towards marriage or a convent."},
                    {"kind": "album", "title": "Vespertine", "year": 2001, "creator": "Björk", "level": 1,
                     "time": "Twelve songs, just under an hour",
                     "why": "Björk made this album as a record for staying indoors in winter, and it sounds like it: "
                            "music boxes, harp, a choir from Greenland and tiny, crackling beats built partly from "
                            "small household sounds, down to footsteps in snow. It is much softer than her other "
                            "records. Play it at low volume in a warm room while the weather does its worst outside.",
                     "note": "Listen with headphones the first time so you can hear the small sounds. Hidden Place "
                             "and Pagan Poetry are good ways in before playing it from start to finish.",
                     "caveat": "Several songs are frankly sensual, and Cocoon in particular is very intimate. "
                               "Otherwise nothing to warn about."},
                ],
            },
            {
                "key": "everyone-on-the-sofa",
                "name": "Everyone on the sofa",
                "tagline": "For the whole family, all ages at once.",
                "intro": [
                    "Holiday breaks are the one time many families spend days in the same room, and finding something that "
                    "a six-year-old, a teenager and a grandparent will all enjoy is a real challenge. These six were picked "
                    "to survive that room. None of them is sickly, and each has something in it for the adults.",
                    "Festive levels vary across the shelf. Each caveat says exactly what might be too much for younger "
                    "children, and anything with a sad stretch is flagged.",
                ],
                "picks": [
                    {"kind": "movie", "title": "The Muppet Christmas Carol", "year": 1992, "creator": "Brian Henson", "level": 5,
                     "time": "One film, about an hour and a half",
                     "why": "Michael Caine plays Scrooge completely straight, as if he were in a serious period "
                            "drama, while Kermit plays Bob Cratchit and Gonzo, as Charles Dickens himself, narrates "
                            "with Rizzo the Rat. Children get the Muppets and the slapstick. Adults get an adaptation "
                            "that keeps a surprising amount of Dickens's own words.",
                     "note": "Pair it with the book on the Deck the halls shelf. Some versions cut the song When Love "
                             "Is Gone; look for one that includes it if you want the whole film.",
                     "caveat": "The Ghost of Christmas Yet to Come can frighten small children, and Tiny Tim's fate is sad "
                               "for a scene or two. Otherwise suitable for all ages."},
                    {"kind": "tv", "title": "Bluey", "year": 2018, "creator": "Joe Brumm", "level": 2,
                     "time": "Most episodes run seven minutes and stand alone",
                     "why": "Bluey is a six-year-old Blue Heeler puppy in Brisbane who turns everything into a game, "
                            "with her little sister Bingo and her parents, Bandit and Chilli, who play along. The "
                            "episodes are short and funny, and a surprising number of them end with a lump in your "
                            "throat. Adults watching may come away with a few new games. The Christmas episodes, "
                            "Verandah Santa and the longer Christmas Swim, are favourites.",
                     "note": "Watch with children and see who laughs more. Verandah Santa is a very Australian "
                             "Christmas, with heat, cousins and a family game that gets out of hand.",
                     "caveat": "A few episodes touch on growing up and loss, and some are known for making parents "
                               "cry. Suitable for all ages."},
                    {"kind": "anime", "title": "Wolf Children", "year": 2012, "creator": "Mamoru Hosoda", "level": 1,
                     "time": "One film, about two hours",
                     "why": "Hana, a university student in Tokyo, falls in love with a man who can turn into a wolf. "
                            "After he dies, she moves to the countryside to raise their two children, Yuki and Ame, "
                            "who are not sure whether they want to grow up human or wolf. Its best-loved scene is a "
                            "joyful run through fresh snow, and the film is about a mother letting each child choose "
                            "a different life.",
                     "note": "Best for children around ten and up, with adults alongside. Leave time afterwards for "
                             "questions about growing up and leaving home.",
                     "caveat": "The father's death and a dangerous storm are upsetting, and parents may find the "
                               "ending harder than their children do. Close to two hours long."},
                    {"kind": "game", "title": "Super Mario Bros. Wonder", "year": 2023, "creator": "Nintendo", "level": 1,
                     "time": "A game of around twelve hours, in short levels",
                     "why": "Up to four players run and jump through the Flower Kingdom together, and when someone "
                            "touches a Wonder Flower the level turns strange: pipes start crawling like caterpillars, "
                            "the music changes and the whole stage rearranges itself. Players of different ages can "
                            "share it, because nobody gets left behind for long.",
                     "note": "Give younger or newer players Yoshi or Nabbit, who take no damage from enemies. Experienced "
                             "players can race ahead and come back to help.",
                     "caveat": "Nintendo Switch only. Up to four players on one console; online play is more limited. No "
                               "content concerns."},
                    {"kind": "book", "title": "The Polar Express", "year": 1985, "creator": "Chris Van Allsburg", "level": 5,
                     "time": "A picture book, about ten minutes aloud",
                     "why": "On Christmas Eve a boy who is starting to doubt Santa hears a train stop outside his "
                            "house, steaming in the snow, and climbs aboard for the North Pole. Van Allsburg's dark, "
                            "glowing pictures won the Caldecott Medal, and the story ends with a sleigh bell that "
                            "only believers can hear. It is short enough to read every year and strange enough that "
                            "older readers keep noticing new things.",
                     "note": "Read it aloud on Christmas Eve with the lights low. A small bell on a string makes a "
                             "good prop for the last page.",
                     "caveat": "None for content. The pictures are soft and shadowy, which a few very young children find a "
                               "little spooky."},
                    {"kind": "album", "title": "A Charlie Brown Christmas", "year": 1965, "creator": "Vince Guaraldi Trio", "level": 4,
                     "time": "A short album, well under an hour",
                     "why": "Pianist Vince Guaraldi's jazz trio wrote and played the music for the 1965 Peanuts "
                            "television special, and the soundtrack has become one of the best-selling jazz albums of "
                            "all time. Christmas Time Is Here, sung by a children's choir, is wistful in a way few "
                            "carols are, and Linus and Lucy will get even reluctant relatives moving.",
                     "note": "Put it on while you decorate or wrap presents, then watch the special itself, which is only "
                             "about twenty-five minutes long.",
                     "caveat": "None. Some editions add bonus tracks and alternate takes, so the running order varies."},
                ],
            },
        ],
        "nights": [
            {"name": "Thanksgiving weekend with family",
             "plan": "Planes, Trains and Automobiles on Wednesday night for whoever has made it home. The Last Waltz "
                     "through dinner on Thursday, and Overcooked! 2 once the plates are cleared and someone needs to "
                     "work off the pie. Keep the Friends Thanksgiving episodes for Friday, when nobody wants to leave "
                     "the sofa."},
            {"name": "Christmas Eve with children",
             "plan": "The Polar Express read aloud after dinner, then The Muppet Christmas Carol, or a couple of Bluey's "
                     "Christmas episodes for the youngest. A Charlie Brown Christmas while the adults wrap, and Super Mario "
                     "Bros. Wonder the next day for everyone who still has energy."},
            {"name": "You've had enough of Christmas",
             "plan": "Fargo for a cold, funny and entirely unfestive night. Then a long stretch of Northern Exposure or A "
                     "Place Further than the Universe, Celeste when you want a challenge, and Vespertine when the house has "
                     "finally gone quiet."},
            {"name": "All in from the first of December",
             "plan": "Elf to open the month, Dash & Lily across the first weekend and A Christmas Carol read one "
                     "stave a night. Animal Crossing for a few minutes every day, Mariah Carey while the tree goes "
                     "up, and Tokyo Godfathers on Christmas Eve once the children are asleep."},
            {"name": "A long journey home",
             "plan": "Download Sweetness and Lightning and Tokyo Godfathers before you leave, and pack Little Women or The "
                     "Bear and the Nightingale for the waiting room. Save Planes, Trains and Automobiles for the night you "
                     "arrive, when you can finally laugh about the trip."},
        ],
        "faq": [
            ("What are good Thanksgiving movies and shows?",
             "Planes, Trains and Automobiles is the classic Thanksgiving film: Steve Martin and John Candy trying to get to "
             "Chicago in time for dinner. For television, Friends made a Thanksgiving episode almost every season; start "
             "with The One with All the Thanksgivings. Both are on the Around the table shelf, along with picks in every "
             "other format."),
            ("What can I watch over the holidays if I don't celebrate Christmas?",
             "The Out in the cold shelf has almost no holiday in it: Fargo, Northern Exposure, A Place Further than the "
             "Universe, Celeste, The Bear and the Nightingale and Björk's Vespertine. Every pick there is one or "
             "two on our festive scale, so you get the winter without the decorations."),
            ("What can the whole family enjoy together at Christmas?",
             "The Everyone on the sofa shelf is chosen for mixed ages. The Muppet Christmas Carol and Bluey work for nearly "
             "everyone, Super Mario Bros. Wonder lets up to four people play at once with easier characters for younger "
             "players, and The Polar Express takes about ten minutes to read aloud. Each caveat says what might be too much "
             "for small children."),
            ("How does the festive scale work?",
             "It runs from one, just wintry with no holiday to speak of, to five, full tinsel. We set each level "
             "ourselves by asking how much of the work is about the season. A story that only happens to take place "
             "at Christmas scores lower than one about Christmas. It is not an age rating; the caveats cover content."),
            ("Are there holiday games to play with family far away?",
             "Animal Crossing: New Horizons lets friends and family visit each other's islands over the internet with a "
             "Nintendo Switch Online membership, which is a lovely way to swap presents across a distance. Overcooked! 2 "
             "also supports online play, though it is at its best on one sofa."),
            ("When does the holiday hub appear on my dashboard?",
             "Members see the hub on their dashboard from the third of November until the end of December. The page itself "
             "stays open all year, and anything you add to your library from it stays there."),
        ],
        "method": [
            "Prepared by OmniTrackr and reviewed by the site owner before publishing. We started from the kinds of time "
            "people actually have between Thanksgiving and New Year (a big family meal, a houseful of children, a quiet "
            "evening alone, a long trip) and chose one pick per format for each. We wanted a spread of tone, age range and "
            "length, so this is not a ranking of the best Christmas titles. Some famous favourites are missing because we "
            "preferred picks that hold up to repeat visits or suit more than one kind of household.",
            "Festive levels and caveats are our own judgements, checked against the works themselves and public sources. "
            "They are not official ratings. Runtimes, editions, episode counts and platforms vary by region. Every link "
            "goes to an OmniTrackr title page and none go to shops. Nothing here is sponsored.",
        ],
    },
}
