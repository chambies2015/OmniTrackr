"""Film season guides for /new-releases: the winter releases worth planning around.

Same fields as the guides in release_guides.py (that module adds these to GUIDES). A film
season guide has ``focus: "movies"``, like the anime, TV and games season guides: its
sections are all film picks, grouped by kind of film, and it is never the "current" guide on
Release Radar. Films already written up in the broader winter guide (winter-2026-27) stay
there and are only mentioned in ``also`` here.
"""

GUIDES = {
    "winter-2027-movies": {
        "name": "Winter 2027 movies: the new films worth seeing from January to March",
        "period": "January to March 2027",
        "eyebrow": "MOVIES RELEASE GUIDE",
        "hub_label": "Winter 2027 movies",
        "focus": "movies",
        "search_title": "Winter 2027 movies: Godzilla x Kong, The Exorcist: Martyrs, Sonic 4, Slayground and more",
        "summary": ("Twelve winter 2027 films worth seeing, from Godzilla x Kong, Sonic 4 and The Exorcist: Martyrs "
                    "to Slayground, Gatto and The Nightingale, with what to watch first."),
        "published": "2026-11-20",
        "reviewed": "2026-11-20",
        "starts": "2027-01-01",
        "ends": "2027-03-31",
        "lead": [
            "January has a bad name in cinemas. The awards films have already opened, the big studio pictures are "
            "saved for summer and the holidays, and what is left over has a reputation for being the films nobody "
            "knew what to do with. That reputation is out of date. The Beekeeper was a hit in January 2024, horror "
            "does well in the first months of the year, and studios now use February and March for films they "
            "expect to make a lot of money. The 2027 calendar is a good example. Sonic the Hedgehog 4 and Godzilla x "
            "Kong: Supernova both open in the last two weeks of March, a month that also has new films from Pixar "
            "and Mike Flanagan.",
            "This guide is the short version. We went through the studios' release schedules as they stood on "
            "November 20 and picked twelve films: four big ones, three horror films and thrillers, two for families "
            "and three for an evening without the children. For each one we say when it opens and where, what it "
            "is, what to watch first if anything, and the thing most likely to put you off. None of them are out "
            "yet, so read these as bets, not reviews. We say where we are guessing.",
            "A few housekeeping notes. Dates are for the US, and most of these open in cinemas on a Friday, with "
            "previews the night before. One, Ink, goes straight to Netflix after a short run in a few cinemas. Two "
            "of the season's biggest films, Children of Blood and Bone on January 15 and Greta Gerwig's Narnia: The "
            "Magician's Nephew on February 12, are written up in our broader winter releases guide, so they are "
            "only listed at the bottom of this one.",
        ],
        "sections": [
            {
                "format": "movies",
                "id": "big",
                "label": "Big screen",
                "heading": "Four big films, and how much you need to have seen",
                "intro": [
                    "These are the four films most likely to fill the large screens this winter. Three are sequels to "
                    "series people already know, and one is a new version of a film that has been made twice before. "
                    "Two of them come from Amazon MGM, which is putting its own films into cinemas before they reach "
                    "Prime Video.",
                ],
                "picks": [
                    {"kind": "movie", "title": "The Beekeeper 2", "year": 2027, "creator": "Timo Tjahjanto",
                     "date": "2027-01-15",
                     "released": "In theaters · Amazon MGM Studios",
                     "why": "Jason Statham is back as Adam Clay, the retired agent of a secret organization called the "
                            "Beekeepers. This time the organization itself goes rogue and sets out to control the "
                            "government, and Clay has to take on the people who made him.",
                     "note": "The first Beekeeper opened in January 2024 with no great expectations and turned into one "
                             "of the surprise hits of the year. It was a revenge film with a very simple engine: a "
                             "scam call cleans out the savings of Clay's kind landlady, and he works his way up the "
                             "chain of people responsible until he reaches the top. The sequel has a new director, and "
                             "he is the reason to be interested. Timo Tjahjanto made The Night Comes for Us (2018), one "
                             "of the most violent and inventive action films of the last decade, and Nobody 2 (2025). "
                             "Kurt Wimmer, who wrote the first film, is back, this time with Zak Penn, and Jeremy Irons "
                             "returns as Wallace Westwyld, the former CIA director from the first film. Pom Klementieff, Yara "
                             "Shahidi and the wrestler Adam Copeland are among the new faces.",
                     "first": "The Beekeeper (2024) sets up Clay and Irons's character. Otherwise you need nothing.",
                     "caveat": "These films are R-rated and very violent, and the script leans hard on bee jokes. If the first one felt silly, a plot about a secret society taking over the "
                               "government won't change your mind."},
                    {"kind": "movie", "title": "The Thomas Crown Affair", "year": 2027, "creator": "Michael B. Jordan",
                     "date": "2027-03-05",
                     "released": "In theaters · Amazon MGM Studios",
                     "why": "Michael B. Jordan directs and stars as Thomas Crown, a rich man who steals for the thrill of "
                            "it, in a new version of the heist film first made in 1968. Amazon calls it a heist "
                            "thriller in which \"the most dangerous man in the room is the one nobody's watching.\"",
                     "note": "The Thomas Crown Affair has been made twice. Norman Jewison's 1968 film had Steve McQueen "
                             "as a bored millionaire who robs banks and Faye Dunaway as the insurance investigator who "
                             "falls for him. John McTiernan's 1999 film made Crown, now Pierce Brosnan, an art thief, "
                             "with Rene Russo as the investigator, and it is the better film. Both work because of the "
                             "game between the two of them, and the heist is almost an excuse. Jordan directed Creed "
                             "III (2023), which had the best-staged fights of that series, and he says this one is "
                             "\"not a remake\" and \"not a reboot.\" The script is by Drew Pearce, who wrote The Fall "
                             "Guy, and Jason Hall, working from the original screenplay. Adria Arjona, Kenneth "
                             "Branagh, Lily Gladstone and Danai Gurira are in the cast, and Jon Batiste wrote the "
                             "score.",
                     "first": "The 1999 film is the one to watch, ideally on a weekend evening with a drink. The 1968 "
                              "film is worth it for McQueen and Dunaway's famous chess scene.",
                     "caveat": "Amazon has said little about the plot, so we are guessing at how close it stays to the "
                               "earlier films. A heist film lives or dies on its twist, and we can't judge that yet."},
                    {"kind": "movie", "title": "Sonic the Hedgehog 4", "year": 2027, "creator": "Jeff Fowler",
                     "date": "2027-03-19",
                     "released": "In theaters · Paramount",
                     "why": "The fourth Sonic film. Ben Schwartz is Sonic again, with Tails, Knuckles and Keanu Reeves's "
                            "Shadow, Jim Carrey is back as Dr. Robotnik, and Kristen Bell joins the series as the voice "
                            "of Amy Rose.",
                     "note": "The Sonic films were not supposed to work. The first trailer in 2019 was laughed at so "
                             "loudly that Paramount redesigned the character, and the series has since become one of the "
                             "most dependable family franchises of the decade, with each film making more than the one "
                             "before. Jeff Fowler has directed all of them, and they have kept the same simple appeal: "
                             "a fast, cheerful, rather sweet story about a found family, with Carrey free to be as "
                             "strange as he likes. The third film ended by setting up Amy Rose, who has been in the "
                             "games since 1993, and the teaser shows her hammer breaking through a wall and the "
                             "Chaos Emeralds scattered in the dark. Ben Kingsley, Nick Offerman, Matt Berry and "
                             "Richard Ayoade have also joined the cast, in roles nobody has announced.",
                     "first": "Sonic the Hedgehog 3 (2024), which introduces Shadow. The Knuckles series on Paramount+ "
                              "is optional.",
                     "caveat": "Paramount has kept the story quiet, so all we know is who is in it. The jokes are pitched "
                               "at children, and adults who didn't enjoy the first three will not be won over by the "
                               "fourth."},
                    {"kind": "movie", "title": "Godzilla x Kong: Supernova", "year": 2027, "creator": "Grant Sputore",
                     "date": "2027-03-26",
                     "released": "In theaters · Warner Bros. and Legendary",
                     "why": "The sixth film in Legendary's MonsterVerse, the American series in which Godzilla and Kong "
                            "share a world, and the third with both of them in the title. Dan Stevens returns as "
                            "Trapper, the vet who looks after the monsters.",
                     "note": "The MonsterVerse began with a serious, slow Godzilla film in 2014 and has drifted, film by "
                             "film, towards comic-book fun. Godzilla x Kong: The New Empire (2024) was almost entirely "
                             "monsters, a hollow earth and a lot of pink light, and it made a lot of money. Supernova "
                             "has a new director, Grant Sputore, whose first feature was I Am Mother (2019), a "
                             "small, smart Netflix science-fiction film about a robot raising a child, so we would "
                             "expect a change of tone. The script is by David Callaham, one of the writers of "
                             "Spider-Man: Across the Spider-Verse, and the new cast is unusually strong for this "
                             "series: Kaitlyn Dever, Jack O'Connell, Delroy Lindo, Matthew Modine and Sam Neill. "
                             "Almost nothing about the story is known yet beyond the title.",
                     "first": "Godzilla x Kong: The New Empire (2024). The Apple TV series Monarch: Legacy of Monsters "
                              "fills in the humans' side.",
                     "first_link": "/in-order/godzilla", "first_label": "The MonsterVerse in order",
                     "caveat": "If you want people to care about, the recent films have not delivered them. The plot "
                               "is still a secret, so anything we say about this one is a guess."},
                ],
            },
            {
                "format": "movies",
                "id": "scary",
                "label": "Horror and thrillers",
                "heading": "Three films for people who like to be frightened",
                "intro": [
                    "Horror is the one kind of film that reliably does well in the dead weeks after the holidays, and "
                    "this winter has three worth leaving the house for. Each comes from a director with a style of his "
                    "own, and none of them is a sequel in the usual sense.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Slayground", "year": 2027, "creator": "Jeremy Saulnier",
                     "date": "2027-01-29",
                     "released": "In theaters · A24",
                     "why": "\"Metal Mike\" Graves, who works as a scare actor at a haunted Halloween attraction, wakes "
                            "up surrounded by the bodies of his co-workers. He becomes the suspect in a mass murder, "
                            "and the film follows the manhunt across the state.",
                     "note": "Jeremy Saulnier makes thrillers in which ordinary people get into violence that is quick, "
                             "ugly and hard to take back. Blue Ruin (2013) was a revenge film about a man who is very "
                             "bad at revenge. Green Room (2015) trapped a punk band in a neo-Nazi bar and is one of the "
                             "best siege films ever made. Rebel Ridge (2024), on Netflix, was a hit about a man fighting "
                             "a corrupt small-town police force. Slayground sounds like a mix of all three, and he "
                             "wrote it himself. Cory Michael Smith, from Gotham, plays Mike, with Imogen Poots, who was "
                             "in Green Room, James Badge Dale, Sophie Wilde and Stephen Root. Trent Reznor and Atticus "
                             "Ross wrote the music. It used to be called October, and A24 changed the title when it "
                             "decided not to hold the film for a year.",
                     "first": "Nothing. Green Room is the best way into Saulnier if you haven't seen any of his films.",
                     "caveat": "Saulnier's violence is sudden and graphic. A report from an early screening put the "
                               "running time at about two and a half hours, which is long for a thriller, though it may "
                               "have been cut since."},
                    {"kind": "movie", "title": "Remain", "year": 2027, "creator": "M. Night Shyamalan",
                     "date": "2027-02-05",
                     "released": "In theaters · Warner Bros.",
                     "why": "Jake Gyllenhaal plays Tate Gordon, a reclusive architect who moves to a small town on the "
                            "coast to finish a project and meets a young woman, played by Phoebe Dynevor, who pulls "
                            "him out of himself. It is a love story from M. Night Shyamalan, with something "
                            "supernatural underneath.",
                     "note": "This is the oddest pairing of the season. Shyamalan came up with the story with Nicholas "
                             "Sparks, the author of The Notebook, and the two of them then went away and wrote it "
                             "separately: Sparks as a novel, which came out in October 2025 and went to the top of the "
                             "New York Times list, and Shyamalan as the script, which he directed. Shyamalan's recent "
                             "films, Old, Knock at the Cabin and Trap, have all been built around a single strange "
                             "idea, and they have been more fun than their reviews suggested. A romance gives him "
                             "something new to work with, and Gyllenhaal is very good at men who are not quite well. "
                             "Warner Bros. moved it from October 2026 to the week before Valentine's Day, so the "
                             "studio is selling it as a date film first.",
                     "first": "Nothing. Sparks's novel comes from the same idea, but reading it first may give away the "
                              "film.",
                     "caveat": "Shyamalan's films stand or fall on their final turn, and when it doesn't work, the whole "
                               "film goes with it. If you don't like Nicholas Sparks, the trailer suggests there is "
                               "plenty of him in here."},
                    {"kind": "movie", "title": "The Exorcist: Martyrs", "year": 2027, "creator": "Mike Flanagan",
                     "date": "2027-03-12",
                     "released": "In theaters · Universal and Blumhouse",
                     "why": "Scarlett Johansson plays an NYPD homicide detective and single mother who caught a satanic "
                            "serial killer, Father Sunday, more than a decade ago. When he is sentenced to death, the "
                            "murders start again. John Leguizamo plays the killer.",
                     "note": "Mike Flanagan is the best horror director working in television, with The Haunting of Hill "
                             "House and Midnight Mass, and his films, from Oculus to Doctor Sleep, take grief as "
                             "seriously as they take scares. He wrote and directed this one, and he has said it is the "
                             "scariest thing he has made. It is not connected to The Exorcist: Believer (2023), and "
                             "after the trailer Fangoria compared it to The Exorcist III (1990), William Peter "
                             "Blatty's own sequel, in which a detective "
                             "investigating copycat killings finds something much worse. Father Sunday's murders are "
                             "staged after the deaths of the saints. The cast is a mix of film stars, Laurence "
                             "Fishburne, Diane Lane and Chiwetel Ejiofor among them, and Flanagan regulars such as "
                             "Carla Gugino, Kate Siegel and Rahul Kohli.",
                     "first": "The Exorcist (1973) is still the one to see. The Exorcist III is the better sequel and "
                              "closer to what this looks like.",
                     "caveat": "A film about a killer who copies the martyrdoms of saints will be grisly, and the trailer "
                               "doesn't hide it. Like Flanagan's other films, it may take its time before the scares start."},
                ],
            },
            {
                "format": "movies",
                "id": "family",
                "label": "Family",
                "heading": "Two for a family trip to the cinema",
                "intro": [
                    "There are not many family films in the first three months of the year, which is why the two big "
                    "ones tend to do well. One is the sixth film in a series about prehistoric animals that began in "
                    "2002, the other an original from Pixar that looks unlike anything the studio has made before.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Ice Age: Boiling Point", "year": 2027, "creator": "John C. Donkin",
                     "date": "2027-02-05",
                     "released": "Only in theaters · 20th Century Studios",
                     "why": "Manny, Sid, Diego and Ellie, voiced as ever by Ray Romano, John Leguizamo, Denis Leary and "
                            "Queen Latifah, head into unexplored corners of the Lost World, the land of dinosaurs and lava "
                            "under the ice, with Simon Pegg's one-eyed weasel Buck. Scrat brings Baby Scrat with him.",
                     "note": "This is the first Ice Age in cinemas since Collision Course in 2016, and it has had a "
                             "complicated route there. Blue Sky, the studio that made the first five, closed after "
                             "Disney bought Fox, and the last film, The Ice Age Adventures of Buck Wild (2022), went "
                             "straight to Disney+ without most of the original voices. Boiling Point brings them all "
                             "back, along with Chris Wedge as Scrat, and adds Ashley Park as a new character. Disney "
                             "first dated it for December 18, 2026, then moved it to February when Avengers: Doomsday "
                             "took that weekend. The early films were funnier than they needed to be, and the Scrat "
                             "scenes were the best thing in them. The later ones weren't. A dinosaur world full of lava "
                             "is a good excuse for big set pieces, which is what the series does best.",
                     "first": "Nothing. Ice Age: Dawn of the Dinosaurs (2009) is the one that introduced Buck and the "
                              "dinosaurs, if your children want a warm-up.",
                     "caveat": "The series ran out of ideas a while ago, and the fourth and fifth films were the "
                               "weakest. Very young children may find the dinosaurs frightening."},
                    {"kind": "movie", "title": "Gatto", "year": 2027, "creator": "Enrico Casarosa",
                     "date": "2027-03-05",
                     "released": "In theaters · Disney and Pixar",
                     "why": "In a Venice run by cats, a black cat called Nero, voiced by Mark Ruffalo, owes a debt to a "
                            "feline mob boss, Rocco, voiced by Laurence Fishburne. An unexpected friendship makes him "
                            "wonder whether he has lived the right life.",
                     "note": "Enrico Casarosa directed Luca (2021), Pixar's summer on the Italian Riviera, and Gatto takes "
                             "him back to Italy for a crime story told by cats. The look is the news: it is painted by "
                             "hand and blended with computer animation, which Pixar has never done before, and the "
                             "first teaser looked more like an illustrated book than like anything else the studio has "
                             "made. Pixar has had an uneven few years, and its originals have struggled next to its "
                             "sequels, so Disney moved this one from June 18, 2027, where it would have opened "
                             "against Shrek 5 and the next Spider-Verse film, to March. A gangster film for children is a risk, but Pixar's best films have always "
                             "found something adult inside a simple story, and a cat wondering whether he chose the "
                             "wrong life sounds like one of those.",
                     "first": "Nothing. Luca shows what Casarosa does with Italy.",
                     "caveat": "We know very little about the story beyond the setup. A film about a mob debt may be "
                               "darker than usual for Pixar, and Disney hasn't given it a rating yet."},
                ],
            },
            {
                "format": "movies",
                "id": "grown-up",
                "label": "Dramas and comedies",
                "heading": "Three for an evening without the children",
                "intro": [
                    "The last three are for adults: a newspaper drama, a comedy about a country singer and a Second World "
                    "War story based on one of the best-selling novels of the last ten years. One of them is on Netflix, "
                    "so you can see it without leaving home.",
                ],
                "picks": [
                    {"kind": "movie", "title": "Ink", "year": 2026, "creator": "Danny Boyle",
                     "date": "2027-01-08",
                     "released": "Netflix · after a short run in select US theaters from December 11",
                     "why": "London, 1969. Rupert Murdoch, played by Guy Pearce, buys a failing broadsheet called The "
                            "Sun and hires Larry Lamb, played by Jack O'Connell, to turn it into a tabloid that can "
                            "beat the Daily Mirror. Claire Foy is in the cast.",
                     "note": "James Graham's play Ink opened in London in 2017, transferred to Broadway, and won Bertie "
                             "Carvel a Tony for his Murdoch. Graham adapted it himself, and Danny Boyle, who made "
                             "Trainspotting and Slumdog Millionaire, directs. The story is how a handful of misfits "
                             "invented a new kind of newspaper in a year, with the gossip, the competitions, the topless "
                             "page three and the habit of telling readers what they already thought, and the play was "
                             "clever about how much fun that was and what it cost. Boyle is good at energy, at people "
                             "doing something new and doing it fast, which suits the material. The film opened the "
                             "Venice festival in September and has a short run in US cinemas in December before it "
                             "reaches Netflix on January 8.",
                     "first": "Nothing, though it helps to know who Murdoch became. Succession is the unofficial sequel.",
                     "caveat": "It is a very British story about a newspaper most Americans have never read, and "
                               "Netflix has only confirmed the January date for the US and Latin America."},
                    {"kind": "movie", "title": "The Comeback King", "year": 2027, "creator": "Judd Apatow",
                     "date": "2027-02-05",
                     "released": "In theaters · Universal",
                     "why": "Glen Powell plays Aubrey King, a country star whose songs about drinking and loving are "
                            "making him famous, until his ex, played by Madelyn Cline, puts out a song that makes him "
                            "the cheater. He goes back to college to finish his degree and work out what he wants to "
                            "say in his music.",
                     "note": "Judd Apatow's films, from The 40-Year-Old Virgin and Knocked Up to The King of Staten "
                             "Island, are long, loose comedies about men who need to grow up, and this one sounds like "
                             "his most direct version of that in years. Powell co-wrote it with him. He also co-wrote "
                             "Hit Man with Richard Linklater, and that film used his movie-star confidence as a joke, "
                             "which is the right way to use it. A country singer back in a lecture hall with students "
                             "half his age is a premise with a lot of room for embarrassment. Cristin Milioti, from Palm "
                             "Springs and The Penguin, plays a professor, and the supporting cast is full of comedians: "
                             "Kumail Nanjiani, Tig Notaro, Vanessa Bayer and Mike Birbiglia.",
                     "first": "Nothing. Hit Man (2024) shows what Powell does when he writes for himself.",
                     "caveat": "Apatow's comedies often run past two hours and lose their way in the middle. If country "
                               "music isn't your thing, there will be a lot of it."},
                    {"kind": "movie", "title": "The Nightingale", "year": 2027, "creator": "Michael Morris",
                     "date": "2027-03-19",
                     "released": "In theaters · Sony Pictures and TriStar",
                     "why": "Kristin Hannah's novel about two French sisters in the Second World War. Vianne, played by "
                            "Dakota Fanning, stays in her village under German occupation, and Isabelle, played by Elle "
                            "Fanning, joins the Resistance. Mark Rylance plays their father.",
                     "note": "The Nightingale came out in 2015 and has been one of the best-loved novels of the last "
                             "decade, the kind of book that gets handed round a family. It has also taken a long time "
                             "to film. It was first dated for August 2018, with Mélanie Laurent directing, moved three "
                             "times, stalled, and only went before the cameras in Budapest in March 2026. This is the first "
                             "film in which Dakota and Elle Fanning, who have been acting since they were small "
                             "children, star together, and casting real sisters as the two sisters is the "
                             "smartest decision anyone has made on it. Michael Morris directed To Leslie (2022), the "
                             "small drama that got Andrea Riseborough an Oscar nomination, so we would expect the "
                             "performances to come first. Dana Stevens wrote the script and Shira Haas plays Rachel, "
                             "Vianne's Jewish neighbor and friend.",
                     "first": "Read the novel if you can. It is long, but it moves, and the film will have had to cut "
                              "a lot of it.",
                     "caveat": "It is a sad, sometimes harrowing story about life under occupation, and the book's "
                               "readers will notice every change. Sony moved it once already, from February 12."},
                ],
            },
        ],
        "also": [
            ("Children of Blood and Bone (January 15).",
             "Gina Prince-Bythewood's film of Tomi Adeyemi's fantasy novel. We wrote it up in our broader winter "
             "releases guide."),
            ("Narnia: The Magician's Nephew (February 12).",
             "Greta Gerwig's Narnia prequel, in cinemas first and then on Netflix. Also in the winter guide."),
            ("Pendulum (January 1).",
             "A horror film with Joseph Gordon-Levitt, Norman Reedus and Phoebe Dynevor, from Mark Heyman, a writer "
             "of Black Swan."),
            ("Fing! (January 15).",
             "A family adventure from Angel Studios with Taika Waititi and Mia Wasikowska."),
            ("Animal Friends (January 22).",
             "Ryan Reynolds and Jason Momoa voice a pony and a bear in an R-rated mix of live action and animation. "
             "It has been moved four times since its first date in August 2025."),
            ("The Prestige (January 29).",
             "Christopher Nolan's 2006 film about rival magicians is back in cinemas, in IMAX too."),
            ("Wishful Thinking (February 12).",
             "A romantic fantasy with Lewis Pullman and Maya Hawke, from Sony Pictures Classics."),
            ("Wife & Dog (February 19).",
             "A Guy Ritchie thriller with Rosamund Pike, James Norton and Anthony Hopkins."),
            ("CoComelon: The Movie (February 19).",
             "The YouTube nursery-rhyme series in cinemas, for the very youngest viewers."),
            ("K-Pop: The Debut and The Revenge of La Llorona (February 26).",
             "A musical comedy from Paramount and a new La Llorona horror film from Warner Bros., on the same day."),
            ("Day Drinker (March 26).",
             "Marc Webb directs Johnny Depp and Penélope Cruz in a thriller from Lionsgate, against Godzilla."),
        ],
        "plan_heading": "A plan for the winter",
        "plan": [
            "January starts at home. Ink reaches Netflix on the 8th, and it is the easiest film on this list to fit "
            "into a cold week. The Beekeeper 2 and Children of Blood and Bone open the following Friday, and "
            "Slayground on the 29th. If you only go to the cinema once in January, make it the one you'd regret "
            "watching on a laptop: for most people that is Slayground.",
            "February 5 is the busiest Friday of the season. Ice Age: Boiling Point, The Comeback King and Remain all "
            "open that day, which makes it an easy weekend to split: the children's film in the afternoon, and "
            "Shyamalan or Apatow after bedtime. Narnia follows on the 12th, and the rest of the month is quiet, which "
            "makes it a good time to catch up on the awards films before the Oscars.",
            "March is the strongest month. Gatto and The Thomas Crown Affair open on the 5th, The Exorcist: Martyrs "
            "on the 12th, Sonic 4 and The Nightingale on the 19th, and Godzilla x Kong on the 26th. Jack O'Connell is "
            "in both Ink and Supernova, and John Leguizamo is the voice of Sid in February and a serial killer in "
            "March, if you want a running game. Dates this far ahead can still move, and the date at the top of the "
            "page says when we last checked.",
        ],
        "method": [
            "Prepared by OmniTrackr with AI assistance and reviewed by the site owner before publishing. None of these "
            "films had opened when we wrote about them, so this is a guide to what we think is worth seeing, not a set "
            "of reviews. We worked from the studios' own announcements, the release schedules and the coverage listed "
            "below, checked each date against a second source, and picked films we would recommend to a friend, with "
            "an honest note on who should skip them.",
            "Film dates are firmer than game dates, but they still move, usually to get out of the way of a bigger "
            "film. While we were putting this guide together, The Nightingale had already moved from February to "
            "March, Remain from Halloween to February and Gatto from June to March, and Animal Friends had moved four "
            "times. Dates are for the US. Ratings are given only where the studio has announced them.",
        ],
        "related": [
            ("Godzilla and the MonsterVerse in order", "/in-order/godzilla"),
            ("The Conjuring films in order", "/in-order/the-conjuring"),
            ("Narnia in order", "/in-order/narnia"),
            ("The best movies of 2026", "/best-of/2026/movies"),
            ("Winter 2027 books", "/new-releases/winter-2027-books"),
            ("How to track movies on OmniTrackr", "/movie-tracker"),
        ],
        "sources": [
            ("The Numbers: 2027 theatrical release schedule", "https://www.the-numbers.com/movies/release-schedule/2027"),
            ("FirstShowing: 2027 release schedule", "https://www.firstshowing.net/schedule2027/"),
            ("CinemaBlend: upcoming 2027 movies", "https://www.cinemablend.com/movies/upcoming-2027-movies-new-release-dates-theaters-streaming"),
            ("BroadwayWorld: The Beekeeper 2 trailer and January 15 date", "https://www.broadwayworld.com/article/THE-BEEKEEPER-2-Trailer-Released-With-Jason-Statham-20261015"),
            ("Film Stories: The Beekeeper 2 adds to its cast", "https://filmstories.co.uk/news/the-beekeeper-2-adds-more-names-to-its-hive/"),
            ("About Amazon: The Thomas Crown Affair, in theaters March 5, 2027", "https://www.aboutamazon.com/news/entertainment/thomas-crown-affair-michael-b-jordan-amazon-mgm-studios"),
            ("CinemaBlend: what we know about The Thomas Crown Affair", "https://www.cinemablend.com/movies/michael-b-jordan-the-thomas-crown-affair-what-we-know"),
            ("Engadget: Sonic the Hedgehog 4 arrives March 19, 2027", "https://www.engadget.com/entertainment/tv-movies/sonic-the-hedgehog-4-will-arrive-on-march-19-2027-133002387.html"),
            ("JoBlo: Sonic the Hedgehog 4 title and teaser", "https://www.joblo.com/sonic-the-hedgehog-4-teaser-trailer/"),
            ("TheWrap: Sonic the Hedgehog 4 adds Ben Kingsley and Nick Offerman", "https://www.thewrap.com/creative-content/movies/sonic-the-hedgehog-4-cast-ben-kingsley-nick-offerman/"),
            ("Godzilla.com: Godzilla x Kong: Supernova teaser", "https://godzilla.com/blogs/news/godzilla-x-kong-supernova-movie-teaser-video"),
            ("Nerdist: everything we know about Godzilla x Kong: Supernova", "https://nerdist.com/article/godzilla-x-kong-supernova-legendary-monsterverse-everything-we-know"),
            ("Dread Central: Slayground opens January 29", "https://www.dreadcentral.com/news/594337/slayground-poster-january-release-date/"),
            ("The Film Stage: Slayground trailer", "https://thefilmstage.com/slayground-trailer-a-manhunt-begins-in-jeremy-saulniers-mystery-thriller/"),
            ("TheWrap: Remain trailer", "https://www.thewrap.com/creative-content/movies/m-night-shyamalan-remain-trailer-jake-gyllenhaal-nicholas-sparks/"),
            ("Bloody Disgusting: Remain pushed to February 2027", "https://bloody-disgusting.com/movie/3934457/m-night-shyamalans-remain-starring-jake-gyllenhaal-pushed-to-february-2027/"),
            ("TheWrap: Mike Flanagan's Exorcist is titled The Exorcist: Martyrs", "https://www.thewrap.com/creative-content/movies/mike-flanagan-exorcist-martyrs/"),
            ("Fangoria: The Exorcist: Martyrs trailer", "https://fangoria.com/the-exorcist-martyrs-trailer"),
            ("Disney: Ice Age: Boiling Point", "https://movies.disney.com/ice-age-boiling-point"),
            ("What's on Disney Plus: Ice Age: Boiling Point moves to February 2027", "https://whatsondisneyplus.com/disney-delays-ice-age-boiling-point/"),
            ("Cartoon Brew: first Gatto teaser", "https://www.cartoonbrew.com/feature-film/gatto-teaser-pixar-disney-enrico-casarosa-262782.html"),
            ("WDW News Today: Gatto moves to March 5, 2027", "https://wdwnt.com/2025/12/disney-pixars-gatto-new-release-date-2027/"),
            ("Netflix Tudum: Ink release dates", "https://www.netflix.com/tudum/articles/ink-release-date-danny-boyle-movie"),
            ("What's on Netflix: Ink theatrical and Netflix release", "https://www.whats-on-netflix.com/news/danny-boyles-rupert-murdoch-drama-ink-starring-claire-foy-guy-pearce-sets-netflix-and-theatrical-release/"),
            ("JoBlo: The Comeback King trailer", "https://www.joblo.com/the-comeback-king-trailer/"),
            ("TheWrap: The Nightingale moves to March 2027", "https://www.thewrap.com/creative-content/movies/dakota-and-elle-fanning-the-nightingale-march-2027/"),
            ("Wikipedia: The Nightingale (2027 film)", "https://en.wikipedia.org/wiki/The_Nightingale_(2027_film)"),
            ("TheWrap: Animal Friends pushed to January 2027", "https://www.thewrap.com/creative-content/movies/animal-friends-pushed-back-7-months-to-jan-2027/"),
        ],
    },
}
