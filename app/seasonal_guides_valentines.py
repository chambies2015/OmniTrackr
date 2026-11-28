"""The Valentine's Day hub (/valentines-day): thirty-six picks for four kinds of Valentine's night, one in every
format OmniTrackr tracks on each shelf, sorted by a romance scale, with a dated list of the new love stories
around Valentine's Day 2027.

Registered in seasonal_guides.SEASONS. Written November 2026 for February 2027 (``year``); none of its picks
repeat the February 2027 Discover edition, the other seasonal hubs and guides, the Discover trails or the
advent calendar (tests/test_valentines.py).
"""
from .dated_text import Dated

VALENTINES = {
    "path": "/valentines-day",
    "name": "Valentine's Day",
    "theme": "valentine",
    "window": ("02-01", "02-15"),
    "year": 2027,
    "published": "2026-11-21",
    "reviewed": "2026-11-21",
    "search_title": "Valentine's Day 2027 picks: romantic movies, shows, anime, games, books, music, manga, podcasts and audiobooks",
    "headline": "Valentine's Day, as romantic as you like",
    "deck": ("Thirty-six picks for a night in as a couple, a night with friends, a night on your own and a night apart, "
             "one in every format on each shelf, sorted by how romantic you want to be, with the new love stories of "
             "February 2027 and their dates."),
    "summary": ("Valentine's Day picks in nine formats for couples, friends, a night alone and long distance, each with a "
                "romance level and a caveat, plus 2027's new releases."),
    "card": "Thirty-six picks for couples, friends, a night alone and long distance, sorted by how romantic you feel.",
    "card_cta": "Find your romance level",
    "scale_name": "Romance",
    "scale_eyebrow": "THE ROMANCE SCALE",
    "scale_heading": "How romantic is it?",
    "plan_label": "Plan your Valentine's",
    "plan_heading": "Six kinds of Valentine's Day",
    "related_heading": "More for February",
    "related_months": ["02"],
    "edition_notes": {"02": "This month's Discover edition: nine more love stories, one in every format, none repeated here."},
    "intro": [
        "Valentine's Day falls on a Sunday in 2027. Galentine's Day, the night for friends, is the Saturday before it, "
        "and Presidents' Day makes Monday the 15th a holiday for a lot of people in the United States, so for once there "
        "is a whole long weekend to fill. Most Valentine's lists fill it with the same twenty romantic comedies. That "
        "works if you are one half of a happy couple who both like romantic comedies. Plenty of people aren't.",
        "So this hub is sorted by the kind of Valentine's you are actually having. There are four shelves: a night in "
        "for two, a night with friends, a night on your own and a night apart, for couples in different cities. Each "
        "shelf has one pick in every format OmniTrackr tracks: a film, a series, an anime, a game, a book, an album, a "
        "manga, a podcast and an audiobook. Every pick has a romance level from one to five, a note on how much time it "
        "takes and a caveat that says what is in it, sex scenes included.",
        Dated("After the shelves there is a calendar of the new love stories coming out around Valentine's Day 2027, with "
              "their dates and where to find them. The February Discover edition, Love in every form, opens on February 1 "
              "with nine more love stories of its own, from Past Lives to Nana. None of its picks are repeated here, and the "
              "plans near the bottom of the page borrow from both.",
              ("2027-02-01",
               "After the shelves there is a calendar of the new love stories coming out around Valentine's Day 2027, "
               "with their dates and where to find them. The February Discover edition, Love in every form, has nine "
               "more love stories of its own, from Past Lives to Nana. None of its picks are repeated here, and the "
               "plans near the bottom of the page borrow from both.")),
    ],
    "scale": [
        (1, "Barely a love story", "Friendship, family or a night on your own. Romance is a subplot at most, so it suits the anti-Valentine's crowd."),
        (2, "Love on the side", "A love story runs through it, next to something else that matters just as much."),
        (3, "A love story", "Romance is the main thread, with room for comedy, music or mystery around it."),
        (4, "Properly swoony", "Built around falling in love: the long looks, the near misses, the big declaration."),
        (5, "Hearts everywhere", "As romantic as it gets. Save it for someone you like a lot, or a night you have decided to be sappy."),
    ],
    "shelves": [
        {
            "key": "date-night-in",
            "name": "Date night in",
            "tagline": "For two people, one sofa and no reservation.",
            "intro": [
                "Most Valentine's dinners out are the same dinner: a set menu at twice the usual price, a table a few inches "
                "from the next couple and a hurry to leave before the second sitting. Staying in is the better plan more "
                "often than people admit. These nine are for two people on one sofa, and each gives you something to talk "
                "about afterwards, which is most of what a good date is.",
                "They sit between three and five on the romance scale. A few suit a couple who have been together for "
                "years. Moonstruck, Whisper of the Heart, Modern Love and the Al Green album are the safest for a first "
                "Valentine's together, when you want something warm with nothing awkward in it.",
            ],
            "picks": [
                {"kind": "movie", "title": "Moonstruck", "year": 1987, "creator": "Norman Jewison", "level": 4,
                 "time": "One film, about an hour and three quarters (102 minutes)",
                 "why": "Loretta Castorini (Cher), a widowed bookkeeper in Brooklyn, accepts a dull proposal from Johnny "
                        "Cammareri and promises to invite his estranged younger brother, Ronny (Nicolas Cage), to the "
                        "wedding. Ronny is a baker with a wooden hand and a passion for opera, and before long she is "
                        "slapping him and telling him to snap out of it. John Patrick Shanley's script won an Oscar, and "
                        "so did Cher and Olympia Dukakis, who plays Loretta's mother.",
                 "note": "It is a film about a whole family of people falling in love at the wrong time under a very large "
                         "moon, and it is funny from the first scene. It suits a couple of any age, on a first date at home "
                         "or a twentieth anniversary: nothing in it is explicit, and everyone ends up around the same "
                         "breakfast table. If neither of you has been to the opera, the night at La Bohème is the best "
                         "advert for it ever filmed.",
                 "caveat": "Rated PG. There is drinking, cheating and one bedroom scene that cuts away early. Some of the "
                           "Italian-American accents are broad."},
                {"kind": "tv", "title": "Starstruck", "year": 2021, "creator": "Rose Matafeo", "level": 4,
                 "time": "Three seasons of six episodes, about 25 minutes each",
                 "why": "Jessie (Rose Matafeo), a New Zealander in London who works at a cinema and as a nanny, goes home "
                        "with a man she meets on New Year's Eve and finds out the next morning that he is Tom Kapoor (Nikesh "
                        "Patel), a famous film star. The first season follows the year after, as they keep running into "
                        "each other and keep getting it wrong.",
                 "note": "Matafeo created it and wrote it with Alice Snedden, and it is that rare romantic comedy about two "
                         "adults rather than two types. The first season is about two and a half hours, so you can start it "
                         "with dinner and finish it by midnight. It is a good one for a newer couple, because it is very "
                         "funny about how awkward the early part of a relationship is.",
                 "caveat": "Swearing, a lot of drinking, and sex that is talked about more than shown. It went out on BBC "
                           "Three in Britain and HBO Max in the US, and where it streams now varies by country, so check "
                           "before you plan the evening around it."},
                {"kind": "anime", "title": "Whisper of the Heart", "year": 1995, "creator": "Yoshifumi Kondō", "level": 4,
                 "time": "One film, just under two hours (111 minutes)",
                 "why": "Shizuku, a fourteen-year-old in suburban Tokyo who reads constantly, notices that every library "
                        "book she borrows was checked out before her by the same boy, Seiji Amasawa. She finds him in the "
                        "end above an antique shop with a cat statue called the Baron in the window, and he turns out to "
                        "want to make violins in Italy. Hayao Miyazaki wrote the script, and it was the only feature Kondō "
                        "directed before he died in 1998.",
                 "note": "Studio Ghibli made a film about being young and in love with what you want to do as much as with "
                         "a person, and the two love stories turn out to be the same one. It is gentle and wholesome, so it "
                         "is ideal for a first Valentine's together, or for sharing an anime with someone who has never "
                         "watched one. You will have Take Me Home, Country Roads in your head for days.",
                 "caveat": "It is slow on purpose, with long scenes of homework and family dinners. It ends with a marriage "
                           "proposal between two fourteen-year-olds, which most people find sweetly old-fashioned and a "
                           "few find odd."},
                {"kind": "game", "title": "Haven", "year": 2020, "creator": "The Game Bakers", "level": 5,
                 "time": "About 15 to 20 hours; best played an evening at a time",
                 "why": "Yu and Kay have run away together to an abandoned planet called Source, because the society they "
                        "came from chooses everyone's partner and didn't choose them for each other. You play both of "
                        "them, gliding over the grass on hover boots, gathering food, cooking dinner on their ship and "
                        "talking in bed at the end of each day. Two people can play on one sofa with a controller each, "
                        "and the fights ask both of you to act at the same moment.",
                 "note": "Very few games are about a couple who are already together, and Haven is about the ordinary part: "
                         "the bickering, the inside jokes, who does the cooking. It is frank and funny about sex without "
                         "showing any. Play one evening of it as the date, then see whether you both want to come back "
                         "to it next week.",
                 "caveat": "The fights are simple and get repetitive, and some people enjoy the gliding more than "
                           "anything else in it. It talks about sex openly and has some strong language, so it isn't one "
                           "to play with children in the room."},
                {"kind": "book", "title": "Twenty Love Poems and a Song of Despair", "year": 1924, "creator": "Pablo Neruda", "level": 5,
                 "time": "A short book: about an hour read aloud",
                 "why": "Neruda was nineteen when this came out in Chile, and it became one of the best-selling books of "
                        "poetry ever written in Spanish. The twenty poems are about bodies, the sea, longing and a love "
                        "that is already ending, and the last poem, the song of despair, is the sound of being left. Most "
                        "English editions print the Spanish on the facing page, so you can read the original aloud even "
                        "if you don't speak it.",
                 "note": "Take turns reading a poem each. Poem 20, \"Tonight I can write the saddest lines\", is the famous "
                         "one, and it is better near the end of the evening than the start. W. S. Merwin's translation is "
                         "the classic English version; newer ones are looser and more modern.",
                 "caveat": "It is erotic poetry, and the woman in it is mostly a body seen through the poet's eyes, which "
                           "some readers find dated. Despite the title, a lot of it is sad."},
                {"kind": "album", "title": "Let's Stay Together", "year": 1972, "creator": "Al Green", "level": 5,
                 "time": "About 35 minutes, nine songs",
                 "why": "Al Green's fourth album, made in Memphis with the producer Willie Mitchell and the Hi Records house "
                        "band, has the title song everyone knows, a long, slow version of the Bee Gees' How Can You Mend a "
                        "Broken Heart, and very little else but Green's voice moving from a murmur to a falsetto and back. "
                        "It is the sound of a man trying very hard to be good to someone.",
                 "note": "Put it on while you cook and leave it running through dinner. It is warm without being cheesy, "
                         "and it works for any couple, new or old. If it goes down well, his next album, I'm Still in Love "
                         "with You, came out the same year and is just as good.",
                 "caveat": "Nothing to warn you about, except that it is short and you will want to play it twice."},
                {"kind": "manga", "title": "Wotakoi: Love Is Hard for Otaku", "year": 2014, "creator": "Fujita", "level": 4,
                 "time": "Eleven volumes; one or two make an evening",
                 "why": "Narumi, an office worker who hides that she loves fan comics, starts a new job and finds that her "
                        "childhood friend Hirotaka, a quiet and serious gamer, works at the same company. They start dating "
                        "because it seems convenient, and then have to work out how two adults with very time-consuming "
                        "hobbies actually share a life. Fujita began it as a web comic, and it became an anime in 2018.",
                 "note": "It is a romance about grown-ups who are already a bit set in their ways, and the jokes are about "
                         "things couples really argue over: a weekend lost to a game, a hobby you don't share, how much of "
                         "yourself to show each other's friends. Read it side by side and swap volumes. It suits couples "
                         "where one of you has a hobby the other doesn't quite understand.",
                 "caveat": "The jokes assume you know a little about anime, games and fan culture, though not much. It is "
                           "a comedy in short chapters, so it doesn't build to anything big."},
                {"kind": "podcast", "title": "Modern Love", "year": 2016, "creator": "The New York Times", "level": 3,
                 "time": "Episodes of 20 to 40 minutes, built around one essay each",
                 "why": "The Modern Love column has run in The New York Times since 2004, with readers writing about their "
                        "own relationships, and the podcast builds each episode around one of those essays. Some are read "
                        "by actors, some by their writers, and many episodes catch up with the writer years later to ask "
                        "what happened next. The archive goes back a decade: first dates, long marriages, love late in "
                        "life, divorces and friendships.",
                 "note": "Listen to one together while you cook, then talk about it over dinner. The essays are short and "
                         "specific enough to start a real conversation, and you will learn a lot about each other from "
                         "which ones you like. It is easier to dip into than to binge.",
                 "caveat": "Some episodes are about grief, illness or divorce, so read the description first if the evening "
                           "is meant to stay light. The hosts and format have changed over the years."},
                {"kind": "audiobook", "title": "Red, White & Royal Blue", "year": 2019, "creator": "Casey McQuiston", "level": 5,
                 "time": "About twelve hours (12 hours 15 minutes); a long drive or a week of evenings",
                 "why": "Alex Claremont-Diaz, the son of the first woman to be president of the United States, gets into a "
                        "fight with Prince Henry of Britain at a royal wedding and knocks over an enormous cake. To calm the "
                        "press, they have to pretend to be friends, and then they really are friends, and then they are "
                        "writing each other long secret emails. Ramón de Ocampo reads it, and he is as good with the jokes "
                        "as with the emails.",
                 "note": "It is the most fun romance on this page, and the emails, in which the two of them quote famous "
                         "love letters from history at each other, are made for listening to. Put it on for a Valentine's "
                         "drive, or a few chapters before bed. The 2023 film on Prime Video changes a lot, so if you have "
                         "only seen that, the book still has surprises.",
                 "caveat": "There are several explicit sex scenes and plenty of swearing. The American politics, written "
                           "in 2019, is a fantasy, and the book knows it."},
            ],
        },
        {
            "key": "galentines",
            "name": "Galentine's night",
            "tagline": "For a room full of friends, on the 13th or any other night.",
            "intro": [
                "Galentine's Day comes from a 2010 episode of Parks and Recreation, in which Leslie Knope takes her friends "
                "out for breakfast every February 13 to celebrate the women in her life. It caught on because a lot of "
                "people would rather spend Valentine's week with their friends than with anyone's idea of romance, and "
                "it isn't only for women. In 2027 the 13th is a Saturday, which makes it an easy night to host.",
                "These nine are for a room of friends, or a busy group chat. Most are comedies, several are about "
                "friendship first and love second, and a few are best enjoyed by talking over them. The romance levels run "
                "from one to five, so you can choose how much swooning the room can take.",
            ],
            "picks": [
                {"kind": "movie", "title": "Bridesmaids", "year": 2011, "creator": "Paul Feig", "level": 2,
                 "time": "One film, about two hours (125 minutes)",
                 "why": "Annie (Kristen Wiig), whose bakery has failed and whose love life is a man who won't let her stay "
                        "the night, is asked by her oldest friend Lillian (Maya Rudolph) to be her maid of honor. Then she "
                        "meets Helen (Rose Byrne), Lillian's rich, perfect new friend, and spends the rest of the film "
                        "losing a war over an engagement party, a dress fitting and a flight to Las Vegas. Wiig wrote it "
                        "with Annie Mumolo, and the script was nominated for an Oscar.",
                 "note": "It is a film about what happens to a friendship when one friend's life moves on and the other's "
                         "doesn't, which is why it lands so well with a group, and it is also very funny. Melissa McCarthy "
                         "was nominated for an Oscar for playing Megan, and her scenes are the ones the room will quote. "
                         "There is a love story, with a kind traffic cop played by Chris O'Dowd, but it is the side plot.",
                 "caveat": "Rated R for crude sex jokes and language. The dress-shop scene, in which food poisoning hits the "
                           "whole bridal party at once, is famous for a reason, so don't eat during it."},
                {"kind": "tv", "title": "Bridgerton", "year": 2020, "creator": "Chris Van Dusen", "level": 5,
                 "time": "Four seasons of eight episodes, about an hour each; each season mostly stands alone",
                 "why": "Shonda Rhimes's company turned Julia Quinn's Regency romance novels into one of Netflix's biggest "
                        "hits, with string quartets playing pop songs at the balls and Julie Andrews as the voice of Lady "
                        "Whistledown, the anonymous writer of the scandal sheet. Each season follows one of the eight "
                        "Bridgerton brothers and sisters into a love affair: Daphne and the Duke first, then Anthony and "
                        "Kate, then Penelope and Colin, then Benedict.",
                 "note": "Bridgerton is better with friends than on your own. It begs for commentary, and a group will spend "
                         "half of every episode arguing about who should end up with whom. Start with the first season if "
                         "nobody has seen it, or with whichever couple the room cares about most. A fifth season, about "
                         "Francesca, was confirmed for 2027 but had no date when we checked.",
                 "caveat": "There are a lot of sex scenes, especially in the first two seasons, so it is not one for a room "
                           "with parents or teenagers in it. The history is a fantasy, and the show says so: its London is "
                           "a society in which race no longer bars anyone from the aristocracy."},
                {"kind": "anime", "title": "Princess Jellyfish", "year": 2010, "creator": "Takahiro Omori", "level": 3,
                 "time": "Eleven episodes of about 23 minutes",
                 "why": "Tsukimi, who loves jellyfish more than anything, lives in an old Tokyo boarding house that rents only "
                        "to otaku women who call themselves the Amars, because they have sworn off men: a train fanatic, a "
                        "woman obsessed with the Three Kingdoms, a collector of traditional dolls and a manga artist nobody "
                        "has ever seen. One night a glamorous woman helps Tsukimi rescue a jellyfish from a pet shop, and "
                        "in the morning turns out to be Kuranosuke, the cross-dressing son of a politician. Together they "
                        "have to stop the house from being torn down.",
                 "note": "Akiko Higashimura's story is about women who are happy as they are and get dragged into fashion, "
                         "money and romance against their will, and it is as funny about clothes as it is about obsession. "
                         "It is good with a group, because everybody recognizes themselves in one of the Amars. There is a "
                         "slow love triangle, with Kuranosuke's shy older brother, but the friendship is the heart of it.",
                 "caveat": "The anime covers only the start of the manga and stops without an ending; the whole manga is "
                           "out in English from Kodansha if the group wants more. Jokes about Kuranosuke's cross-dressing "
                           "are mostly on his side, though not always."},
                {"kind": "game", "title": "Monster Prom", "year": 2018, "creator": "Beautiful Glitch", "level": 3,
                 "time": "A round takes about 30 to 45 minutes, and you will want to play several",
                 "why": "One to four players are monsters at a high school three weeks before prom, each trying to get a "
                        "date with one of six classmates: a vampire who hates anything popular, a party-loving ghost, a "
                        "gorgon who runs a business empire, a werewolf jock, a mermaid princess and a demon who likes "
                        "setting things on fire. Each turn you choose where to spend the day and how to answer whatever "
                        "happens, and the scenes are written to be read aloud and argued over.",
                 "note": "It is a dating game built for a group. Everyone shares one screen, or plays online, the writing is "
                         "fast and rude, and the best moments come from someone picking the worst possible answer on "
                         "purpose. Most rounds end with somebody going to prom alone, which is half the fun.",
                 "caveat": "Written for adults: crude jokes, sex jokes, drink and drugs. It is for a night of grown-up "
                           "friends, not a sleepover with younger brothers and sisters."},
                {"kind": "book", "title": "Bridget Jones's Diary", "year": 1996, "creator": "Helen Fielding", "level": 3,
                 "time": "About 300 pages; a weekend, or a long bath",
                 "why": "A year in the diary of a single woman in her thirties in London, who counts her calories, cigarettes "
                        "and units of alcohol at the top of every entry, works in publishing, falls for her boss Daniel "
                        "Cleaver and ignores Mark Darcy, a stiff human-rights lawyer in a reindeer jumper. It began as a "
                        "newspaper column in The Independent and borrows its plot from Pride and Prejudice.",
                 "note": "The book is more about her friends than either man. Jude, Shazzer and Tom, her \"urban family\", "
                         "spend every crisis on the phone and most Fridays drunk, and they are the reason it suits "
                         "Galentine's. If you have only seen the Renée Zellweger films, the book is sharper and meaner, and "
                         "Bridget is funnier on the page.",
                 "caveat": "It was written in the mid-1990s, and it shows: the dieting and the way it talks about weight are "
                           "hard going now, and some of the jokes have aged badly."},
                {"kind": "album", "title": "Body Talk", "year": 2010, "creator": "Robyn", "level": 2,
                 "time": "Under an hour, fifteen songs",
                 "why": "The Swedish singer put out two short Body Talk records in 2010, then gathered the best of them, with "
                        "five new songs, into this album. It has Dancing on My Own, the best song ever written about "
                        "watching the person you love kiss someone else across a club, along with Call Your Girlfriend, "
                        "Hang with Me and Indestructible. Almost every song is about love going wrong, and you can dance to "
                        "all of them.",
                 "note": "Put it on as people arrive and turn it up after the second drink. It is the soundtrack for a room "
                         "of friends who have all been through it, and Call Your Girlfriend, in which a woman tells the man "
                         "she has fallen for to let his girlfriend down gently, starts the best arguments.",
                 "caveat": "One song's title is a sentence you might not want small children repeating; otherwise it is "
                           "all heartbreak you can dance to."},
                {"kind": "manga", "title": "Paradise Kiss", "year": 2000, "creator": "Ai Yazawa", "level": 4,
                 "time": "Five volumes; two evenings",
                 "why": "Yukari, a worn-out student at a strict high school cramming for university exams, is stopped in the "
                        "street by a group of fashion students who need a model for their graduation show. Their designer, "
                        "George, is beautiful, rich and impossible, and the year that follows teaches her as much about what "
                        "she wants from her own life as about him.",
                 "note": "Nana is one of the nine picks in the February Discover edition, and Paradise Kiss is the shorter, "
                         "sharper story Ai Yazawa wrote just before it, with the same eye for clothes and the same refusal "
                         "to give anyone a fairy tale. Pass it around the group: everyone has an opinion about George, and "
                         "nobody agrees. Look closely at the outfits; Yazawa went to fashion school, and every page shows it.",
                 "caveat": "George is controlling, and the book doesn't pretend otherwise; this is a story about a first "
                           "relationship, not a model one. There are sex scenes, though not explicit ones, and the ending "
                           "isn't the one most readers hope for."},
                {"kind": "podcast", "title": "Call Your Girlfriend", "year": 2014, "creator": "Aminatou Sow and Ann Friedman", "level": 1,
                 "time": "Eight years of weekly episodes, about an hour each",
                 "why": "\"A podcast for long-distance besties everywhere.\" Two friends, Aminatou Sow on the East Coast and "
                        "Ann Friedman in Los Angeles, called each other every week to talk about politics, work, money, "
                        "health and their own lives. It ran from 2014 to 2022, and the two of them wrote a book about their "
                        "friendship, Big Friendship, in 2020.",
                 "note": "It is the opposite of a Valentine's podcast: a show about the love between friends, taken as "
                         "seriously as any romance. Start with the episodes about their own friendship from the summer of "
                         "2020, when the book came out, then send one to the friend you call most. Shine theory, "
                         "Friedman's idea that you do better when your friends do well too, runs through all of it.",
                 "caveat": "It ended in 2022, so the news they discuss is a few years old, and their politics are out in "
                           "the open. The friendship episodes have dated least."},
                {"kind": "audiobook", "title": "Book Lovers", "year": 2022, "creator": "Emily Henry", "level": 4,
                 "time": "About eleven and a half hours (11 hours 23 minutes)",
                 "why": "Nora Stephens is a ruthless New York literary agent, the kind of woman who gets dumped in the first "
                        "act of a romantic comedy when the hero runs off with a small-town girl. Her younger sister Libby "
                        "talks her into a month in Sunshine Falls, North Carolina, the setting of a bestseller Nora sold, "
                        "where the one person she keeps running into is Charlie Lastra, a brooding book editor she has "
                        "already clashed with. Julia Whelan reads it, as she has read most of Henry's novels.",
                 "note": "The romance is the hook, but the sisters are the heart of it, which makes it a good one for a group "
                         "of friends to start on the same day and talk about in the group chat as they go. Emily Henry's "
                         "next novel, Modern Classic, is out on April 6, 2027, and a film of her Beach Read opens on May 7, "
                         "so there is plenty more of her coming in the spring.",
                 "caveat": "Open-door sex scenes, lots of swearing and many in-jokes about publishing. The first chapter makes "
                           "Nora look cold on purpose, so give it a few chapters."},
            ],
        },
        {
            "key": "table-for-one",
            "name": "Table for one",
            "tagline": "For a night on your own, happily or otherwise.",
            "intro": [
                "Plenty of people spend Valentine's Day on their own, some because they want to and some because the year "
                "didn't go to plan. Either way the evening is yours, and it doesn't have to be spent pretending not to "
                "notice the date. These nine are good company. Several are about being alone and finding that you can "
                "stand yourself after all, and a few are about heartbreak and are much funnier about it than you would "
                "expect.",
                "Most sit at one or two on the romance scale. If you have just been through a breakup, start with Heartburn, "
                "Dear Sugars or Crazy Ex-Girlfriend, and save Lost in Translation and Sea Change for a night when you can "
                "take something bittersweet.",
            ],
            "picks": [
                {"kind": "movie", "title": "Lost in Translation", "year": 2003, "creator": "Sofia Coppola", "level": 2,
                 "time": "One film, about an hour and three quarters (102 minutes)",
                 "why": "Bob Harris (Bill Murray), a fading American film star in Tokyo to shoot a whisky advert, and "
                        "Charlotte (Scarlett Johansson), a young graduate left alone in the same hotel while her husband "
                        "works, meet in the bar in the middle of the night because neither of them can sleep. Over a few "
                        "days they wander the city together. Nothing much happens between them, and that is the point. "
                        "Coppola won the Oscar for the script.",
                 "note": "It is the best film there is about being lonely in company, and it is a good one to watch on your "
                         "own with the lights down, because it is about the comfort a stranger can bring. Nobody knows what "
                         "Bob whispers to Charlotte at the end, and you don't need to.",
                 "caveat": "Rated R, mostly for a strip-club scene and some language. It is slow and quiet, and some of the "
                           "jokes about Japanese people speaking English have dated badly."},
                {"kind": "tv", "title": "Crazy Ex-Girlfriend", "year": 2015, "creator": "Rachel Bloom and Aline Brosh McKenna", "level": 3,
                 "time": "Four seasons, 62 episodes of about 42 minutes",
                 "why": "Rebecca Bunch (Rachel Bloom), a miserable New York lawyer, runs into Josh Chan, the boy she dated at "
                        "summer camp when she was sixteen, and on an impulse moves across the country to West Covina, "
                        "California, where he lives, telling everyone, herself included, that it has nothing to do with "
                        "him. Every episode has two or three original songs, parodies of everything from Broadway "
                        "showstoppers to boy-band ballads, and Bloom won a Golden Globe for the first season.",
                 "note": "It looks like a silly musical comedy about a woman chasing a man, and for a while it is. Then it "
                         "becomes one of the most honest shows on television about loneliness and mental health, and why "
                         "someone would build a whole life around a fantasy. If you are spending Valentine's Day on your own "
                         "and feeling a little unhinged about it, Rebecca will make you feel much better.",
                 "caveat": "Later seasons deal with depression and a suicide attempt, carefully but directly. Some of the "
                           "songs are very rude."},
                {"kind": "anime", "title": "The Tatami Galaxy", "year": 2010, "creator": "Masaaki Yuasa", "level": 2,
                 "time": "Eleven episodes of about 23 minutes",
                 "why": "A nameless third-year student in Kyoto looks back on two wasted years at university and blames the "
                        "club he joined as a freshman. Each episode he starts again, joins a different club in search of the "
                        "\"rose-colored campus life\" he was promised, loses track of Akashi, the girl he likes, and ends "
                        "up in the same place with the same terrible friend, Ozu. It is fast, funny and drawn like nothing "
                        "else.",
                 "note": "It belongs on a night alone because it is about the stories we tell ourselves about missed "
                         "chances, and it has the best ending of any anime about regret. The narrator talks very fast, so "
                         "keep the subtitles on and don't worry about catching every line. The last two episodes pull it "
                         "all together.",
                 "caveat": "The art is flat and abstract and the narration is relentless, which puts some people off in the "
                           "first ten minutes. Give it two episodes."},
                {"kind": "game", "title": "Coffee Talk", "year": 2020, "creator": "Toge Productions", "level": 2,
                 "time": "About four hours, one night at the café at a time",
                 "why": "You run a coffee shop that opens only at night, in a rainy Seattle where elves, orcs, werewolves and "
                        "succubi live alongside humans. Customers come in, you make their drinks, they talk, and slowly you "
                        "learn their lives: an elf and a succubus whose parents won't accept them, a journalist trying to "
                        "write her first novel, an orc who makes video games. There is nothing to fight; your choices are "
                        "what you put in the cup.",
                 "note": "It is the gentlest game on this page and the best company for a night in on your own. Make a hot "
                         "drink of your own, turn the phone over and play a few nights of the café. It ends up being about "
                         "everyone's love life except yours, which is restful. The soundtrack is good on its own afterwards.",
                 "caveat": "There is almost no challenge, and the drink-making is fiddly until you learn the recipes. The "
                           "writing is earnest and sometimes heavy-handed about prejudice."},
                {"kind": "book", "title": "Heartburn", "year": 1983, "creator": "Nora Ephron", "level": 1,
                 "time": "About 180 pages; one evening",
                 "why": "Rachel Samstat, a cookery writer seven months pregnant with her second child, finds out that her "
                        "husband, a Washington journalist, is in love with another woman. The novel is Rachel telling you, "
                        "very funnily, how she found out, how they got there and what she cooked along the way, recipes "
                        "included. Ephron based it on the end of her own marriage to Carl Bernstein, and Mike Nichols filmed "
                        "her script of it in 1986 with Meryl Streep and Jack Nicholson.",
                 "note": "This is the book for the Valentine's Day after a breakup. It is about as sad a story as a marriage "
                         "can have, and one of the funniest novels of its decade, because Rachel keeps choosing to make it "
                         "funny. Ephron's mother told her that everything is copy, and this is the proof. The mashed "
                         "potatoes are worth making.",
                 "caveat": "It is very much a book of early-1980s Washington and New York, full of names, and the narrator "
                           "can be cruel about everyone, herself included."},
                {"kind": "album", "title": "Sea Change", "year": 2002, "creator": "Beck", "level": 2,
                 "time": "About 52 minutes, twelve songs",
                 "why": "Beck wrote these songs after the end of a nine-year relationship and recorded them with Nigel "
                        "Godrich, who produced Radiohead, with string arrangements by his father, David Campbell. There are "
                        "no jokes and no samples, which was a shock from the man who made Odelay. It is just slow, "
                        "beautiful songs about being left: The Golden Age, Lost Cause, Guess I'm Doing Fine.",
                 "note": "Play it on headphones, late, all the way through. It is the sound of someone being honest about how "
                         "bad it feels without making a show of it, and by the end it is strangely comforting. If you want "
                         "a happier follow-up, Morning Phase from 2014 is its sequel in all but name.",
                 "caveat": "If your heart was broken last week, it may be one sad song too many. Save it until you are "
                           "ready to feel it."},
                {"kind": "manga", "title": "My Lesbian Experience with Loneliness", "year": 2016, "creator": "Nagata Kabi", "level": 1,
                 "time": "One volume, about 150 pages; an hour or two",
                 "why": "A memoir in comics. At twenty-eight, after years of depression, an eating disorder and never having "
                        "been in a relationship, Nagata Kabi books an evening with a woman from an escort service, mostly "
                        "to find out whether she can bear to be touched. The book is about that night and everything that "
                        "led up to it, drawn in pink and black with a frankness that made it a hit when she first posted "
                        "it online.",
                 "note": "It sounds as if it should be grim, and parts of it are, but it is also funny and generous about the "
                         "gap between wanting love and being ready for it. It is on this shelf because it is the most honest "
                         "book you will find about loneliness, and because the person writing it gets better. Her later "
                         "books carry on the story.",
                 "caveat": "Frank about sex, self-harm, depression and disordered eating. It is for adults, and best on a "
                           "night when you feel steady."},
                {"kind": "podcast", "title": "Dear Sugars", "year": 2015, "creator": "Cheryl Strayed and Steve Almond", "level": 2,
                 "time": "Three years of weekly episodes, about 40 minutes each",
                 "why": "Cheryl Strayed, who wrote Wild, used to write an anonymous advice column called Dear Sugar, which "
                        "the writer Steve Almond had started before her. In this show the two of them answer letters out "
                        "loud: from people who can't get over an ex, people in love with someone married, people who are "
                        "lonely inside their marriage. They answer with long, kind, profane and very personal stories of "
                        "their own.",
                 "note": "Choose episodes by their titles, which say what the letters are about. It is a show for anyone on "
                         "their own on February 14 wondering whether they are the only one who feels like this. They aren't, "
                         "and these two will say so without lying to them. Strayed's book of the columns, Tiny Beautiful "
                         "Things, became a TV series in 2023.",
                 "caveat": "It ended in 2018. They swear a lot and talk openly about sex, cheating and abuse."},
                {"kind": "audiobook", "title": "Eleanor Oliphant Is Completely Fine", "year": 2017, "creator": "Gail Honeyman", "level": 2,
                 "time": "About eleven hours",
                 "why": "Eleanor Oliphant works in the accounts office of a Glasgow design firm, eats the same meal deal "
                        "every lunchtime, drinks two bottles of vodka every weekend and talks to almost nobody. She decides "
                        "that a singer she has seen once is the man she is meant to marry, and while she prepares for him "
                        "she is drawn, against her will, into helping an old man who collapsed in the street, along with "
                        "Raymond from the office IT department. Cathleen McCarron reads it in Eleanor's precise Glaswegian "
                        "voice.",
                 "note": "It is a book about loneliness that turns into a book about friendship, and it is the right length "
                         "to start on Valentine's Day and finish over the following week. McCarron gets every one of "
                         "Eleanor's pronouncements exactly right, and the jokes land better out loud. It is funny for a long "
                         "time before it is sad.",
                 "caveat": "Eleanor's past includes childhood abuse and a fire, and the second half deals with trauma, "
                           "suicidal thoughts and therapy. It ends in hope."},
            ],
        },
        {
            "key": "long-distance",
            "name": "Miles apart",
            "tagline": "For couples in different cities, and anyone missing someone.",
            "intro": [
                "For long-distance couples, Valentine's Day is the one day of the year when the distance is impossible to "
                "ignore. Most advice says to post a card. These nine do more: some are stories about people in love across "
                "oceans, years and even star systems, and some are things two people can share from two places at once, "
                "such as a game you play together online, an album you start at the same moment or a book you read a "
                "chapter of each night.",
                "They run from two to five on the romance scale, and not every one ends happily. Like Crazy and The Time "
                "Traveler's Wife are honest about how hard distance is; if you would rather have hope, pick Crash Landing "
                "on You, This Is How You Lose the Time War or Sky. The same shelf works for anyone missing someone, "
                "whatever the reason.",
            ],
            "picks": [
                {"kind": "movie", "title": "Like Crazy", "year": 2011, "creator": "Drake Doremus", "level": 4,
                 "time": "One film, about an hour and a half (90 minutes)",
                 "why": "Anna (Felicity Jones), a British student in Los Angeles, falls for Jacob (Anton Yelchin), an American "
                        "who designs furniture, and stays the summer with him after her student visa runs out. When she "
                        "goes home to London and tries to fly back, she is turned away at the airport and barred from the "
                        "country. The rest of the film is the years that follow: phone calls, visits and other people. The "
                        "actors improvised much of the dialogue from an outline, and it won the Grand Jury Prize at "
                        "Sundance.",
                 "note": "If you are apart, watch it together on a call and be ready to talk afterwards. It is the most "
                         "truthful film about a long-distance relationship, because it is about how love wears thin when two "
                         "people can't be in the same room, and it doesn't tell you what to make of the ending.",
                 "caveat": "Rated PG-13. It is sad and open-ended, so it isn't the film for a night when you need "
                           "cheering up."},
                {"kind": "tv", "title": "Crash Landing on You", "year": 2019, "creator": "Park Ji-eun", "level": 5,
                 "time": "Sixteen episodes of 70 to 110 minutes; a few weeks of evenings",
                 "why": "Yoon Se-ri (Son Ye-jin), a South Korean heiress who runs her own fashion company, is swept off course "
                        "by a sudden storm while paragliding and lands in a tree on the North Korean side of the "
                        "demilitarized zone, where Captain Ri Jeong-hyeok (Hyun Bin), a North Korean officer, finds her. He "
                        "hides her in his village while they look for a way to get her home, and his soldiers and the "
                        "village wives become the funniest supporting cast in any Korean drama.",
                 "note": "Start each episode at the same time and message each other through it, because you will want to. "
                         "It is long, swooning and very funny, and it is about two people who should never have met and "
                         "keep finding ways to reach each other across a border. Its two stars married in real life in 2022.",
                 "caveat": "Sixteen long episodes is a commitment, and a second love story in the middle stretch slows it "
                           "down. The North Korea it shows is softened for a romance."},
                {"kind": "anime", "title": "Voices of a Distant Star", "year": 2002, "creator": "Makoto Shinkai", "level": 3,
                 "time": "One short film, 25 minutes",
                 "why": "In 2046, Mikako, a fifteen-year-old, is chosen to pilot a giant robot for a United Nations fleet "
                        "fighting aliens, and leaves Earth. Noboru, the boy she likes, stays behind. They keep texting, and "
                        "as her ship goes deeper into space each message takes longer to arrive: weeks, then months, and "
                        "finally more than eight years. Shinkai made it almost entirely on his own, on a home computer.",
                 "note": "It is short enough to start on a call at the same moment, and it is the purest thing ever made "
                         "about how distance and time feel for two people who have to wait. It is also where Shinkai began: "
                         "Your Name and Suzume grew from the same idea of two people kept apart and reaching for each other.",
                 "caveat": "It is very short, with a thin plot and visibly homemade animation from 2002. The robot battles are "
                           "the weakest part. It is melancholy rather than tragic."},
                {"kind": "game", "title": "Sky: Children of the Light", "year": 2019, "creator": "thatgamecompany", "level": 2,
                 "time": "Free to play; an evening exploring together, or a few minutes a day",
                 "why": "From the makers of Journey, an online game in which you fly through kingdoms in the clouds as a "
                        "small caped child of light, meet other players and slowly earn the ability to talk to them, hug "
                        "them and hold their hands. When two players hold hands, one leads and the other is carried along. "
                        "It is free on phones, Nintendo Switch, PlayStation and PC, and players on any of them can play "
                        "together.",
                 "note": "It is the gentlest way for two people in different places to spend an evening side by side: meet at "
                         "the same spot, hold hands and explore, with no fighting and no score. Sit on a bench together in "
                         "one of the realms and you can talk. Add each other as friends first, because it takes a little "
                         "while to unlock chat.",
                 "caveat": "It is free and makes its money from in-game purchases and a seasonal pass, which it pushes. You "
                           "need an internet connection, and the first hour, before you can talk to anyone, can feel "
                           "aimless."},
                {"kind": "book", "title": "This Is How You Lose the Time War", "year": 2019, "creator": "Amal El-Mohtar and Max Gladstone", "level": 4,
                 "time": "About 200 pages; one long evening or a few short ones",
                 "why": "Red and Blue are agents on opposite sides of a war fought up and down the timeline, rewriting history "
                        "for their masters. Red finds a letter from Blue on a battlefield, headed \"Burn before reading\", "
                        "and writes back. Their letters, hidden in tree rings, seeds, cooling lava and the leaves at the "
                        "bottom of a cup of tea, turn from taunts into love, and the war starts to notice. It won the Hugo, "
                        "Nebula and Locus awards for best novella.",
                 "note": "Read it together, a letter at a time, one of you reading Red's and the other Blue's, on a call. The "
                         "two authors wrote it by passing chapters back and forth, and it reads best the same way. It is "
                         "short, dense and full of jokes, and it is the one pick on this page for science-fiction fans who "
                         "swear they don't read romance.",
                 "caveat": "It is confusing on purpose at first and never fully explains how the war works. It is a love "
                           "story between two women, more emotional than physical."},
                {"kind": "album", "title": "Give Up", "year": 2003, "creator": "The Postal Service", "level": 3,
                 "time": "About 44 minutes, ten songs",
                 "why": "Ben Gibbard of Death Cab for Cutie was in Seattle and the electronic producer Jimmy Tamborello was in "
                        "Los Angeles, so they made this album by post: Tamborello mailed his tracks north, Gibbard added "
                        "words and guitar and mailed them back. The band's name is a joke about it. The album has Such "
                        "Great Heights and The District Sleeps Alone Tonight, about a city that feels empty since someone "
                        "left it, and it went platinum nine years after it came out.",
                 "note": "Start it at the same moment and listen together on a call, or each on your own headphones, then "
                         "argue about which song is yours. It is a happy-sounding record about being apart, and there is no "
                         "better album for a couple in two cities.",
                 "caveat": "The electronics sound very 2003, which is part of the charm, and Gibbard's lyrics can be wistful "
                           "to the point of soppy."},
                {"kind": "manga", "title": "A Sign of Affection", "year": 2019, "creator": "suu Morishita", "level": 5,
                 "time": "Still running; the first three volumes make a good start",
                 "why": "Yuki, a deaf university student in Tokyo, falls for Itsuomi, a friend of a friend who has backpacked "
                        "around the world, speaks several languages and wants to learn hers. It is a romance about two "
                        "people working out how to reach each other: in sign language, by text, in speech and in silence. "
                        "suu Morishita is the pen name of two women, one who writes and one who draws, and it became an "
                        "anime in 2024.",
                 "note": "It is on this shelf because the distance in it isn't measured in miles. It is the gap between two "
                         "people's ways of talking, and how each of them crosses it. It is very sweet, very swoony and good "
                         "at small, specific gestures, like the first signs Itsuomi learns. Read it while you are apart from "
                         "someone and you will notice how much of a relationship is paying attention.",
                 "caveat": "It is slow and soft, with very little conflict, and some readers wish Itsuomi were less perfect. "
                           "The manga is still running, so there is no ending yet."},
                {"kind": "podcast", "title": "Alice Isn't Dead", "year": 2016, "creator": "Joseph Fink", "level": 3,
                 "time": "Three seasons, 30 episodes of about 25 minutes",
                 "why": "A woman whose wife, Alice, disappeared and was declared dead takes a job driving a long-distance "
                        "truck, because she has seen Alice in the background of news reports from all over America. As she "
                        "drives, she talks to Alice over her radio, telling her about the roads, the diners and the "
                        "strange and frightening things she finds. Jasika Nicole voices her, and Joseph Fink, who created "
                        "Welcome to Night Vale with Jeffrey Cranor, wrote it.",
                 "note": "It is a love letter in thirty parts, about how far you would drive for someone, and it is perfect "
                         "for two people in two places: each of you listens to an episode on your own commute, then you "
                         "compare notes in the evening. It is a horror story too, with a serial killer and a secret war, but "
                         "the road and the marriage are what you will remember.",
                 "caveat": "Genuinely creepy in places, with violence described in detail. It cares more about atmosphere "
                           "than answers, and the plot never fully explains itself."},
                {"kind": "audiobook", "title": "The Time Traveler's Wife", "year": 2003, "creator": "Audrey Niffenegger", "level": 4,
                 "time": "About seventeen and a half hours",
                 "why": "Henry DeTamble has a genetic disorder that throws him backward and forward through his own life "
                        "without warning, arriving naked and alone. Clare Abshire first meets him when she is six and he is "
                        "in his thirties; he first meets her when he is twenty-eight and she is twenty. The novel is their "
                        "marriage told out of order by both of them, and the unabridged audiobook gives each a narrator, "
                        "Fred Berman as Henry and Phoebe Strole as Clare.",
                 "note": "It is the great novel about loving someone who keeps leaving through no fault of his own, which is "
                         "why it speaks to people who spend most of a relationship apart. Two voices make it easier to "
                         "follow than the book, since you always know whose chapter it is. Give it a week of commutes.",
                 "caveat": "Clare is a child when she first meets the adult Henry. Nothing romantic happens then, but the "
                           "book doesn't hide how strange it is. There is grief, miscarriage and an ending that will make "
                           "you cry."},
            ],
        },
    ],
    "calendar": {
        "key": "new-for-valentines",
        "label": "New this February",
        "after": "long-distance",
        "eyebrow": "NEW FOR VALENTINE'S 2027",
        "heading": "New love stories around Valentine's Day 2027",
        "intro": [
            "Six new films, series and books with a love story at their center come out between January 8 and February 18, "
            "2027. They are listed by their US dates, with where to find each one, as the studios, networks and publishers "
            "had announced them by November 21, 2026. We haven't seen or read any of them yet, so these are descriptions, "
            "not reviews, and the dates can still move. The titles in our release guides link to their full write-ups.",
            "Most of the year's big romances arrive in the spring: Emily Henry's novel Modern Classic on April 6, the "
            "second season of Heated Rivalry on HBO Max in April and the film of Beach Read in theaters on May 7. Our "
            "spring 2027 release guides cover those.",
        ],
        "items": [
            {"date": "2027-01-08", "title": "The Guy She Was Interested In Wasn't a Guy at All", "format": "Anime",
             "where": "Crunchyroll · new episodes weekly",
             "note": "Aya falls for the stylish person who works at her favourite CD shop, who turns out to be Mitsuki, a "
                     "shy girl in her class. A sweet, funny romance between two girls who bond over old records, from "
                     "CloverWorks, the studio behind Bocchi the Rock!",
             "href": "/new-releases/winter-2027-anime#pick-the-guy-she-was-interested-in-wasn-t-a-guy-at-all"},
            {"date": "2027-01-27", "title": "She's Fine", "format": "TV",
             "where": "Apple TV · two episodes, then weekly on Wednesdays",
             "note": "Elizabeth Banks plays a woman fresh out of a messy divorce who ends up managing the love lives of her "
                     "father's retirement community. Ted Danson plays her father, Katey Sagal his girlfriend and Rob Delaney "
                     "the girlfriend's son.",
             "href": "/new-releases/winter-2027-tv#pick-she-s-fine"},
            {"date": "2027-02-02", "title": "The Two-Body Problem", "format": "Book",
             "where": "Hardcover, ebook and audiobook · Berkley",
             "note": "Ali Hazelwood's sequel to The Love Hypothesis. Olive and Adam are together now, and the title is the "
                     "academic name for what they face next: two scientists who both need jobs in the same place."},
            {"date": "2027-02-05", "title": "Remain", "format": "Film",
             "where": "In theaters · Warner Bros.",
             "note": "Jake Gyllenhaal plays a reclusive architect and Phoebe Dynevor the young woman who draws him out, in a "
                     "love story with something supernatural underneath. M. Night Shyamalan directed it from a story he "
                     "worked out with Nicholas Sparks, and the studio moved it to the week before Valentine's Day.",
             "href": "/new-releases/winter-2027-movies#pick-remain"},
            {"date": "2027-02-10", "title": "Prodigies", "format": "TV",
             "where": "Apple TV · two episodes, then weekly on Wednesdays until March 17",
             "note": "Ayo Edebiri and Will Sharpe play two former child prodigies, together since they were nine, taking a "
                     "hard look at their relationship in their thirties. Sharpe created, wrote and directed it.",
             "href": "/new-releases/winter-2027-tv#pick-prodigies"},
            {"date": "2027-02-18", "title": "The Age of Innocence", "format": "TV",
             "where": "Netflix · all eight episodes at once",
             "note": "Edith Wharton's novel of a man about to marry the right woman and in love with her cousin, with Ben "
                     "Radcliffe, Kristine Froseth and Camila Morrone, and Margo Martindale as the family's matriarch. Emma "
                     "Frost developed it and runs it.",
             "href": "/new-releases/winter-2027-tv#pick-the-age-of-innocence"},
        ],
    },
    "nights": [
        {"name": "The first one together",
         "plan": "Keep it warm and easy. Whisper of the Heart or Moonstruck, with Let's Stay Together playing while you "
                 "cook. One episode of Modern Love gives you something to talk about over dinner, and nothing in that "
                 "evening will make anyone blush in front of a person they have known for six weeks."},
        {"name": "Years in, and staying in",
         "plan": "Start Haven after dinner and give it the whole evening; it is about the everyday part of being a couple, "
                 "which you know all about. Read each other one Neruda poem before bed. If you would rather watch, the "
                 "first season of Starstruck is two and a half hours and very funny about the start of everything you have "
                 "already been through."},
        {"name": "Galentine's Saturday",
         "plan": "February 13 is a Saturday in 2027. Have everyone over for a late breakfast in Leslie Knope's honor, then "
                 "Bridesmaids, then a few rounds of Monster Prom on one screen, with Body Talk on while the food comes out. "
                 "Before everyone leaves, agree to start Book Lovers together and keep the group chat going as you listen."},
        {"name": "Alone, on purpose",
         "plan": "Coffee Talk with a hot drink, then Lost in Translation with the lights down, then Sea Change on headphones "
                 "to end the night. It is a lovely evening, and you don't have to explain it to anyone. If you want a "
                 "longer project, Eleanor Oliphant Is Completely Fine is eleven hours of excellent company."},
        {"name": "Freshly heartbroken",
         "plan": "Skip the Miles apart shelf this year. Read Heartburn in one sitting, listen to an episode of Dear Sugars and "
                 "start Crazy Ex-Girlfriend, the funniest show there is about being a mess over someone. Then call a "
                 "friend, or ask to join their Galentine's the night before."},
        {"name": "In two time zones",
         "plan": "Find an hour that works for both of you and start Voices of a Distant Star on a call at the same moment; it "
                 "is twenty-five minutes. Then meet in Sky and hold hands. Put Give Up on at the same time as you get ready "
                 "for bed. If you have the weekend, Crash Landing on You is sixteen episodes to watch in step, messaging "
                 "each other through every cliffhanger."},
    ],
    "faq": [
        ("When is Valentine's Day in 2027?",
         "Sunday, February 14, 2027. Galentine's Day, which started as a running joke on Parks and Recreation, is the day "
         "before, Saturday, February 13. Presidents' Day falls on Monday, February 15, so many people in the United States "
         "get a long weekend from Friday the 12th. This hub shows on members' dashboards from February 1 to February 15."),
        ("What is a good movie to watch on Valentine's Day?",
         "For a couple, Moonstruck (1987), a funny, generous romantic comedy that suits any age and any stage of a "
         "relationship. With friends, Bridesmaids. On your own, Lost in Translation. If you are apart, Like Crazy, though "
         "it is sad, so only if you can take it. For something new, Remain, M. Night Shyamalan's love story written with "
         "Nicholas Sparks, opens in US theaters on February 5, 2027."),
        ("What are good games for couples to play together on Valentine's Day?",
         "Haven is the game most directly about a couple: two players on one sofa control Yu and Kay, lovers on the run, "
         "and it is best played over several evenings. For couples in different places, Sky: Children of the Light is free "
         "and lets you hold hands and explore together online. For a group, Monster Prom is a dating game for up to four "
         "players that is far more fun with friends than alone."),
        ("What should I watch or read on Valentine's Day if I'm single?",
         "The Table for one shelf is for exactly that. Heartburn and Crazy Ex-Girlfriend are the funniest picks after a "
         "breakup, Lost in Translation and Sea Change suit a quiet night, and Coffee Talk is a cozy game that asks nothing "
         "of you. If you would rather not be on your own, the Galentine's shelf is built for a night with friends."),
        ("What's new for Valentine's Day 2027?",
         "The calendar on this page lists the new releases with their dates: Ali Hazelwood's The Two-Body Problem, the "
         "sequel to The Love Hypothesis (February 2), Remain in theaters (February 5), Apple TV's romantic comedy "
         "Prodigies (February 10) and Netflix's eight-part The Age of Innocence (February 18). Most of the year's big "
         "romances come later in the spring, including Emily Henry's Modern Classic on April 6 and the film of her Beach "
         "Read on May 7."),
        ("Is this the same as the February Discover edition?",
         Dated("No. The February 2027 edition, Love in every form, opens on February 1 with nine love stories of its own, "
               "one per format, from Past Lives to Nana, and none of them are repeated here. The February challenge that "
               "goes with it asks you to finish one of the nine, go back to something you already love and write a line "
               "about why. Once February starts, both are linked at the bottom of this page.",
               ("2027-02-01",
                "No. The February 2027 edition, Love in every form, has nine love stories of its own, one per format, "
                "from Past Lives to Nana, and none of them are repeated here. The February challenge that goes with it "
                "asks you to finish one of the nine, go back to something you already love and write a line about why. "
                "Both are linked at the bottom of this page."))),
        ("How does the romance scale work?",
         "It runs from one, barely a love story, to five, hearts everywhere. We set each level ourselves by asking how much "
         "of the work is about falling or being in love: a story about friendship with a romance on the side scores lower "
         "than one built around a courtship. It is not an age rating, and the caveats say what is in each pick, sex scenes "
         "included."),
        ("Can I save these picks without an account?",
         "Yes. Save to my list keeps a pick in your browser, and your list moves into a free library if you sign up. "
         "Members can add one pick or a whole shelf, and the page shows which ones are already in their library."),
    ],
    "method": [
        "Prepared by OmniTrackr and reviewed by the site owner before publishing. We started from the four kinds of "
        "Valentine's Day people actually have (a night in as a couple, a night with friends, a night on your own and a "
        "night apart) and chose one pick in each of the nine formats OmniTrackr tracks for each of them. We wanted a "
        "spread of tone, age and length, so this is not a ranking of the most romantic titles ever made. Several famous "
        "romances are missing on purpose: some are in the February Discover edition, some are in our other guides, and "
        "some are on every other list already.",
        "Romance levels and caveats are our own judgements, checked against the works themselves and public sources. "
        "They are not official ratings. Runtimes, editions and where things stream vary by country; the narrators and "
        "lengths of the audiobooks are from their publishers' and retailers' listings. The new releases are dated from "
        "the studios', networks' and publishers' announcements as of November 21, 2026, and we haven't seen or read them. "
        "Every pick links to an OmniTrackr title page, and none go to shops. Nothing here is sponsored.",
    ],
    "sources": (
        ("Final Weapon: The Guy She Was Interested In Wasn't a Guy at All premieres January 8",
         "https://finalweapon.net/2026/10/08/the-guy-she-was-interested-in-wasnt-a-guy-at-all-anime-premieres-january-8/"),
        ("TVLine: She's Fine release date", "https://www.tvline.com/2314375/shes-fine-apple-tv-release-date-christmas-with-snoop-nbc/"),
        ("Penguin Random House: The Two-Body Problem by Ali Hazelwood",
         "https://www.penguinrandomhouse.com/books/840608/the-two-body-problem-by-ali-hazelwood/"),
        ("The A.V. Club: The Love Hypothesis sequel arrives in February",
         "https://www.avclub.com/the-love-hypothesis-sequel-the-two-body-problem-announcement"),
        ("Bloody Disgusting: Remain moves to February 2027",
         "https://bloody-disgusting.com/movie/3934457/m-night-shyamalans-remain-starring-jake-gyllenhaal-pushed-to-february-2027/"),
        ("TheWrap: Prodigies premiere date and first look",
         "https://www.thewrap.com/creative-content/tv-shows/will-sharpe-ayo-edebiri-prodigies-premiere-date-first-look-apple-tv/"),
        ("Critical Report: Netflix sets The Age of Innocence for February 18",
         "https://criticalreport.substack.com/p/the-age-of-innocence-premiere-date"),
        ("HighBridge Audio: The Time Traveler's Wife, read by Fred Berman and Phoebe Strole",
         "https://highbridgeaudio.com/timetravelerswife.html"),
        ("Libro.fm: Red, White & Royal Blue, read by Ramón de Ocampo", "https://libro.fm/audiobooks/9781250233950"),
        ("Libro.fm: Book Lovers, read by Julia Whelan", "https://libro.fm/audiobooks/9780593553770"),
        ("Kirkus: Eleanor Oliphant Is Completely Fine, read by Cathleen McCarron",
         "https://www.kirkusreviews.com/audiobook-reviews/gail-honeyman/eleanor-oliphant-is-completely-fine/"),
    ),
}
