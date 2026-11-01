"""Reviewed, public decision guides for selected Discover trails.

This module contains editorial content only. Catalog keys identify the existing
recommendations; the catalog remains the authority for saved-title metadata.
"""

GUIDES = {
    "one-evening-well-spent": {
        "reviewed": "2026-09-24",
        # Search result title; the page heading keeps the trail name.
        "search_title": "Something great for one evening: a film, show, game or album",
        "summary": "Choose between Before Sunset, The Good Place, Florence, and Blue by how much attention you have left, how heavy each one feels, and where you can stop for the night.",
        "lead": [
            "An evening can be short in several different ways. You might have little time, little patience for learning a new world, or enough energy to listen but not to follow a screen. Those are different needs. This guide compares four ways to spend a sitting: a conversation-led film, the beginning of a television comedy, an interactive relationship story, and a complete album.",
            "Ask what would make the evening feel finished. Before Sunset and Florence each tell a whole story in one sitting, and Blue is a fixed run of songs with a first track and a last. The Good Place is different: its first episode is the start of something much longer. Pick one, decide where you will stop, and leave the other three for another night.",
        ],
        "comparison_intro": "Start with how much attention you have left. The commitment column says what you are taking on: one film, one episode, one short game, or one album.",
        "choices": [
            {
                "key": "before-sunset",
                "pace": "Unhurried movement, concentrated conversation",
                "commitment": "One film; prior Before Sunrise context helps",
                "best_for": "An uninterrupted watch about adult choices and unfinished connections",
                "consider": "A sequel with romantic history behind its conversation; little action",
            },
            {
                "key": "good-place",
                "pace": "Brisk jokes and a quickly established premise",
                "commitment": "One introductory episode of a continuing series",
                "best_for": "Trying a comic voice before deciding on a longer watch",
                "consider": "The pilot opens questions that only later episodes answer",
            },
            {
                "key": "florence",
                "pace": "Gentle interaction and compact emotional shifts",
                "commitment": "A short, linear interactive story; pace varies by player",
                "best_for": "Participating in a story without a large system to master",
                "consider": "Limited mechanical challenge; romance and heartbreak are central",
            },
            {
                "key": "blue",
                "pace": "Intimate songs with room for words and arrangements",
                "commitment": "A complete album, or a few songs with a planned return",
                "best_for": "An evening away from screens with something substantial to hear",
                "consider": "The songs are emotionally direct, which can feel demanding if you wanted soothing",
            },
        ],
        "sections": [
            {
                "id": "choose-your-stopping-point",
                "heading": "Choose the stopping point before the title",
                "paragraphs": [
                    "Three of these picks end on their own. If you want to put something down without facing a next-episode prompt, choose the film, the game, or the album. The Good Place is the exception. Its opening will tell you whether you like the humor, but it is the first chapter of a serialized story. If you stop after the pilot with a question still hanging, the sample did its job.",
                    "Before Sunset asks for something else: context. It is a sequel to Before Sunrise, and that earlier meeting gives this conversation its weight. If you have seen the first film, this is an easy pick. If you haven't and want something you can start cold tonight, try Florence or Blue. One free evening doesn't need to turn into a trilogy.",
                ],
            },
            {
                "id": "attention-is-part-of-the-choice",
                "heading": "Match the work to your remaining attention",
                "paragraphs": [
                    "Before Sunset and Blue both pay back close listening, in different ways. In the film, a hesitation or a sudden change of subject can change what you think is going on between the two leads. On the album, one stressed word or image can change the mood of a whole song. Neither needs a notebook. Both work better with your phone in another room.",
                    "Florence gives your hands a small part to play. You follow the relationship through what you do as well as what you see. The Good Place goes the other way: its brisk comic setup pulls you along when you would rather not do any work. Pick by how much you want to take part. None of the four is the serious option.",
                ],
            },
            {
                "id": "leave-with-something-specific",
                "heading": "A small ending for your own evening",
                "paragraphs": [
                    "If you want to keep a note afterward, skip the plot summary and write down one moment where your reaction changed. Which conversation became less comfortable? When did an interaction in Florence feel easier or harder? Did one song on Blue sound different coming after the one before it? A line like that will mean more on a second visit than 'it was good.'",
                    "Or don't write anything. This trail is here to make choosing easier, and homework after the credits would undo that. Save the one pick you actually want to try and leave the rest here for a different kind of evening.",
                ],
            },
        ],
        "item_notes": {
            "before-sunset": [
                "Choose this when a long conversation sounds like enough of an event. The tension sits in the gap between what the two can say casually and what their history makes hard to say. It needs you watching. It won't work as something on in the background while you cook.",
                "If you know Before Sunrise, listen for how the characters talk to each other now. You don't need to remember every detail of the first film. If you haven't seen it, know that before you choose. A recap can tell you what happened, but it can't give you the familiarity the first film builds up.",
            ],
            "good-place": [
                "Treat the first episode as an audition for the series. It sets up a comic problem you can enjoy right away and leaves most of it unresolved. When it ends, decide for yourself whether you want more of that tone. Turn off autoplay if you don't want the decision made for you.",
                "Compare it with Blue. Both fit in one sitting, but the album ends and the pilot leaves a door open. Pick whichever of those you want tonight.",
            ],
            "florence": [
                "Florence is for someone who wants to do something but doesn't want to spend the evening learning controls or comparing character builds. Its small interactions keep your attention on the day-to-day of a relationship. It is a guided sequence. Don't expect branching choices or a test of reflexes.",
                "Before Sunset puts the feeling in what people say. Florence puts more of it in ordinary gestures. If you try both on separate evenings, compare them: intimacy feels different when you perform the gesture yourself than when you watch two people talk.",
            ],
            "blue": [
                "Blue sounds different as a whole album than as one familiar song in a playlist. Play it once in its original order, pausing if you need to, and listen to how the arrangements and moods change from one track to the next.",
                "You don't need to read up on Joni Mitchell first. If background reading sounds like work tonight, this is the easiest pick to start with. It is also the only one that needs no screen. Don't mistake that for background calm, though. These songs are heavy.",
            ],
        },
        "related": [
            {"slug": "notice-the-details", "reason": "For another evening built around close attention, with reflective film, design, ambient music, and essays."},
            {"slug": "small-adventures", "reason": "For warmer outings and detours when you want more movement than this conversation-led selection offers."},
        ],
        "sources": [
            {"key": "before-sunset", "label": "Criterion: Before Sunset", "url": "https://www.criterion.com/films/28693-before-sunset", "supports": "Film edition details, credits, and relationship to Before Sunrise."},
            {"key": "good-place", "label": "Peacock: The Good Place series overview (US)", "url": "https://www.peacocktv.com/stream-tv/the-good-place", "supports": "Series format and opening premise; page may vary by region."},
            {"key": "florence", "label": "Annapurna Interactive: Florence", "url": "https://annapurnainteractive.com/games/florence", "supports": "Publisher's description of the interactive relationship story."},
            {"key": "blue", "label": "Joni Mitchell: Blue", "url": "https://jonimitchell.com/music/album.cfm?id=5", "supports": "Official album identification, release information, and track sequence."},
        ],
    },
    "finding-your-feet": {
        "reviewed": "2026-09-24",
        "search_title": "Stories about starting over: Kiki, Stardew Valley and more",
        "summary": "Compare Kiki's Delivery Service, Stardew Valley, Walter Mitty, and A Wizard of Earthsea by pace, commitment, and the kind of beginning you want to explore.",
        "lead": [
            "Starting over can mean leaving home, making somewhere habitable, taking a risk, or accepting responsibility for something that went wrong. Those changes don't feel alike. This trail looks at them in four forms, and none of the four pretends a fresh start makes uncertainty go away.",
            "Two are complete films, one is a farming game where you set your own routine, and one is a fantasy novel about what learning costs. Choose by the company you want: Kiki earning her own living, Stardew's daily decisions, Walter Mitty heading out into the world, or Earthsea's harder account of growing up.",
        ],
        "comparison_intro": "A comforting work can still be a challenge. The table shows where each one puts its weight, so you can pick the kind of fresh start that fits your mood.",
        "choices": [
            {
                "key": "kiki",
                "pace": "Everyday encounters, with bursts of tension",
                "commitment": "One self-contained anime film",
                "best_for": "A warm story about independence, work, and uncertain confidence",
                "consider": "Self-doubt and peril remain part of its gentle world",
            },
            {
                "key": "stardew",
                "pace": "Self-directed goals within timed in-game days",
                "commitment": "An open-ended game suited to recurring sessions",
                "best_for": "Making small, visible changes through your own actions",
                "consider": "Resource management can turn a relaxing plan into an efficiency project",
            },
            {
                "key": "walter-mitty",
                "pace": "An outward-moving, visually expansive adventure",
                "commitment": "One feature film",
                "best_for": "A buoyant nudge toward curiosity and leaving familiar routines",
                "consider": "Its polished, sentimental tone simplifies the messiness of change",
            },
            {
                "key": "earthsea",
                "pace": "Measured and mythic, with consequences that keep growing",
                "commitment": "A novel to read across sittings; pace varies by reader",
                "best_for": "A more searching story about ability, limits, and responsibility",
                "consider": "Danger and darker themes make it less comforting than the other choices",
            },
        ],
        "sections": [
            {
                "id": "different-kinds-of-beginning",
                "heading": "What kind of beginning are you looking for?",
                "paragraphs": [
                    "Kiki and Stardew set a new life among ordinary tasks. Deliveries, planting, and meeting the neighbors make the change concrete: you come to belong somewhere because you keep showing up. Walter Mitty looks outward instead, at the experiences a fixed routine keeps out of reach. Earthsea takes the thrill of a new ability and asks what happens when confidence gets ahead of judgment.",
                    "If you came here wanting encouragement, choose by that difference. Walter Mitty gives the most direct push forward. Kiki leaves room for confidence to falter and come back. Stardew lets you decide which small project counts as progress. In Earthsea, learning to accept a limit is part of growing up, and the book takes its time getting there.",
                ],
            },
            {
                "id": "comfort-and-control",
                "heading": "A cozy setting can still be hard work",
                "paragraphs": [
                    "Stardew looks like the obvious relaxing choice, but its freedom comes with decisions. A clock, limited resources, and plenty of tempting jobs can put pressure on a player who hates leaving things unfinished. For a first session, try picking one small aim, such as learning where everything in town is, and leave the rest for later. Nothing in the game requires you to play efficiently.",
                    "The films take that management off your hands. Kiki shows a young person's working day without asking you to optimize it, and Walter Mitty carries you through an adventure someone else planned. Earthsea asks for a different effort: patience with a slow narrative and its moral complications. If making decisions is what wore you out today, a story to follow will be more restful than a farm to run.",
                ],
            },
            {
                "id": "pair-by-contrast",
                "heading": "Pair by contrast if you want to return",
                "paragraphs": [
                    "Kiki and Earthsea pair well. In both, a young person's growing ability changes who they think they are, but Kiki is warm where Earthsea is grave. After one, ask yourself whether being good at something means feeling confident or acting responsibly while still unsure. The second will push back on the first instead of repeating its reassurance.",
                    "Stardew and Walter Mitty are a different contrast: settling into one place against leaving the familiar behind. See which version of change appeals to you more. Neither one is braver. If you want a reason to come back to this trail, jot down your answer. Take the picks in any order, and stop whenever you like.",
                ],
            },
        ],
        "item_notes": {
            "kiki": [
                "Kiki's Delivery Service is an anime film, so you get a full story without a season to commit to. It is here for its everyday scale. Independence means errands, awkward encounters, and stretches when an ability Kiki has always relied on falters. The film is warm enough to make those setbacks bearable and honest enough not to wave them away.",
                "Choose it over Walter Mitty when you want to stay close to the daily work, and the feelings, of making a new home. Choose Walter Mitty when a wider horizon and more movement sound better.",
            ],
            "stardew": [
                "Part of the pleasure of a new farm is that you can see it improve. A patch of land changes because you spent time on it. That sets Stardew apart from the other three: you decide how fast to go and where to put your effort, within limits the game sets.",
                "On a first visit, find out what you enjoy before you open an optimization guide. If you catch yourself watching the clock more than the farm, the game may not suit your mood that night. One of the films might suit it better.",
            ],
            "walter-mitty": [
                "Walter Mitty offers travel to unfamiliar places as the answer to the gap between the life he imagines and the one he lives. Its polished images and sentimental energy make it the most openly motivational pick here. They also make it the weakest fit if you want an honest look at what money and circumstance do to plans for a new life.",
                "Take the scale lightly. A big screen adventure doesn't have to become a big personal plan. Set beside Stardew, it raises one simple question: does a fresh start mean building a routine or breaking one?",
            ],
            "earthsea": [
                "A Wizard of Earthsea is for when reassurance on its own sounds thin. In this book, a skill can't be separated from the person using it. Le Guin's deliberate, mythic voice keeps you at more of a distance than Kiki does. That makes it the better choice when you want a story to think about over several sittings.",
                "Start with the novel itself and skip the background reading about Earthsea. You can follow how your view of Ged changes without memorizing a guide to the setting. If you want to track that change, a short note at the end of a chapter is enough.",
            ],
        },
        "related": [
            {"slug": "make-something", "reason": "For a closer look at learning through practice, revision, and the pressure to make good work."},
            {"slug": "found-family", "reason": "For stories that shift the focus from becoming independent to making room for other people."},
        ],
        "sources": [
            {"key": "kiki", "label": "GKIDS: Kiki's Delivery Service", "url": "https://gkids.com/films/kikis-delivery-service/", "supports": "Distributor's film identification and premise about independence, work, and self-doubt."},
            {"key": "stardew", "label": "Stardew Valley: About", "url": "https://www.stardewvalley.net/about/", "supports": "Developer's description of farming, relationships, and open-ended play."},
            {"key": "walter-mitty", "label": "20th Century Studios: The Secret Life of Walter Mitty", "url": "https://www.20thcenturystudios.com/movies/the-secret-life-of-walter-mitty", "supports": "Official film premise and credits."},
            {"key": "earthsea", "label": "Ursula K. Le Guin: A Wizard of Earthsea", "url": "https://www.ursulakleguin.com/a-wizard-of-earthsea", "supports": "Author's book page identifying the novel, Ged's early story, and its place in Earthsea."},
        ],
    },
    "beautifully-strange-worlds": {
        "reviewed": "2026-09-24",
        "search_title": "Strange worlds like Spirited Away, Mushishi and Outer Wilds",
        "summary": "Find your way into Spirited Away, Mushishi, Outer Wilds, or Piranesi with spoiler-free comparisons of pace, uncertainty, and how much each world leaves you to work out.",
        "lead": [
            "An unfamiliar world can ask you to admire it, live beside it, investigate it, or rethink what you thought you knew about it. Each of these four asks for something different. None needs a glossary or a long backstory before you start.",
            "First ask how much uncertainty you want to carry. Spirited Away gives you Chihiro to follow through its strangeness. Mushishi breaks its odd encounters into separate episodes. In Outer Wilds, the investigating is your job. Piranesi keeps you close to a narrator whose observations slowly shift your sense of where you are. The comparisons below give away no plot discoveries.",
        ],
        "comparison_intro": "A quiet work can still be unsettling, and a beautiful game can still feel urgent. Before you choose on atmosphere, look at how each one handles uncertainty.",
        "choices": [
            {
                "key": "spirited-away",
                "pace": "A flowing adventure with busy scenes and quieter passages",
                "commitment": "One self-contained anime feature film",
                "best_for": "Following a character through a vivid world without solving its mechanics",
                "consider": "Transformations, peril, and intense images interrupt the wonder",
            },
            {
                "key": "mushishi",
                "pace": "Patient, contemplative encounters",
                "commitment": "An episodic series; begin with an episode, then decide",
                "best_for": "A world revealed through individual lives and local consequences",
                "consider": "Melancholy and disturbing situations can accompany its quiet tone",
            },
            {
                "key": "outer-wilds",
                "pace": "Self-directed exploration under recurring time pressure",
                "commitment": "A connected mystery across multiple play sessions",
                "best_for": "Learning a world's behavior through curiosity and experimentation",
                "consider": "Flight controls, hazards, and disorientation ask more of the player",
            },
            {
                "key": "piranesi",
                "pace": "Measured observation with accumulating uncertainty",
                "commitment": "A standalone novel; reading pace varies",
                "best_for": "An intimate point of view and a setting you gradually learn to interpret",
                "consider": "Isolation and manipulation make this more than a dreamy escape",
            },
        ],
        "sections": [
            {
                "id": "rules-before-explanations",
                "heading": "Learn the rules by noticing what happens",
                "paragraphs": [
                    "You learn these worlds by seeing what happens in them. In Spirited Away, work, appetite, manners, and kindness tell you how the place operates long before you could explain it. Mushishi keeps tying strange phenomena to ordinary needs and weaknesses. There is no mythology to memorize. Each episode watches how one person lives with a condition that others might overlook.",
                    "Outer Wilds turns that habit into play: something you notice can change what you try next. Piranesi puts observations into words, so you watch both the place and the man describing it. All four share the pleasure of finding a pattern in something that first seemed baffling. They differ in who acts on that discovery: a character, a narrator, or you.",
                ],
            },
            {
                "id": "wonder-with-or-without-pressure",
                "heading": "Choose how much pressure should accompany the wonder",
                "paragraphs": [
                    "Spirited Away always gives you a direction, however surprising the surroundings. You can follow Chihiro's immediate problems without understanding every image. Mushishi has no single quest pushing it toward an ending. Its episodes let you stop after one encounter and sit with an uneasy outcome. Neither asks you to learn a system, though both can be emotionally intense.",
                    "Outer Wilds asks for persistence. Travel, hazards, and the time limit can cut an investigation short, so an evening of wandering is not always a relaxing one. With Piranesi you set the pace by putting the book down, but its narrow point of view keeps the uncertainty close. If you are tired, pick the amount of guidance you want. A quieter-looking world won't necessarily be the easier one.",
                ],
            },
            {
                "id": "protect-the-pleasure-of-discovery",
                "heading": "Get help without giving away the discovery",
                "paragraphs": [
                    "In Outer Wilds, tell a control problem apart from a mystery problem. Looking up how a control works spoils nothing. Reading where to go next can spoil a lot. If you want puzzle help, a narrow hint leaves more of the deduction to you than a full walkthrough does. And once curiosity has turned into frustration, there is no prize for staying stuck. Take as much help as keeps you interested.",
                    "With Piranesi, let the book introduce its world and save the detailed discussions for afterward. A list of what you are wondering about will do more for you than a page of explanations found online. Spirited Away and Mushishi are also best met without much preparation, although their images and moods hold up even if you already know the plot.",
                ],
            },
        ],
        "item_notes": {
            "spirited-away": [
                "This is the easiest way in if you want one complete story told mostly in pictures. Chihiro gives the strange surroundings a human scale: a huge, crowded place makes sense through her immediate problem of what to do next. On a first watch, let the unexplained background details stay unexplained.",
                "Choose it over Mushishi if you want the momentum of one developing story; choose Mushishi if you prefer a series of smaller encounters and room to pause between them. Compared with Outer Wilds, its guided sequence also removes the pressure of deciding which mystery to investigate next.",
            ],
            "mushishi": [
                "Mushishi, also styled Mushi-shi, shows its world through separate cases, each complete in itself. A wandering investigator links the episodes, and each encounter changes the lives of the people caught up in the strange phenomena. It often feels closer to a folktale than to a quest with levels to clear.",
                "Watch the first episode and see whether its slow pace suits you. Calm doesn't mean comforting here. The series is interested in how people live alongside forces they can't simply control, and some episodes end in sadness that stays unresolved. Keep that in mind if you want something for bedtime.",
            ],
            "outer-wilds": [
                "Outer Wilds is for curiosity that wants something to do. You choose a question, travel toward it, and test what you think you know. What you learn changes what you are able to notice next. That is why reading a solution too early costs so much in this game.",
                "If the solar system feels too big, take one question into each session and forget about finishing a location. Put the game away for the night if flying or the time limit is taking more out of you than the mystery is giving back.",
            ],
            "piranesi": [
                "Piranesi shows its strange setting through one narrator's habits of attention, so you see it from very close up. Halls, tides, and statues are all the context you need to begin. Read detailed explanations first and you trade the pleasure of revising your understanding for waiting for facts you already know to turn up.",
                "In Outer Wilds you find things out by testing a route. In Piranesi you find them out by interpreting a description. Write down your first questions if you like, then look back at the end to see which assumptions you made yourself. Feeling lost early on doesn't mean you missed some background reading.",
            ],
        },
        "related": [
            {"slug": "distant-futures", "reason": "For speculative worlds that turn questions about ecosystems, language, and society into personal stories."},
            {"slug": "clever-mysteries", "reason": "For more discovery through clues, with choices that put the puzzle closer to the foreground."},
        ],
        "sources": [
            {"key": "spirited-away", "label": "GKIDS: Spirited Away", "url": "https://gkids.com/films/spirited-away/", "supports": "Distributor's anime film identification, credits, and opening premise."},
            {"key": "mushishi", "label": "Fuji TV: Mushishi (Japanese)", "url": "https://www.fujitv.co.jp/b_hp/mushishi/", "supports": "Original broadcaster's description of the 2005 series, Ginko, and its self-contained episodes."},
            {"key": "outer-wilds", "label": "Mobius Digital: Outer Wilds", "url": "https://www.mobiusdigitalgames.com/outer-wilds.html", "supports": "Developer's description of the exploration mystery and changing solar system."},
            {"key": "piranesi", "label": "Bloomsbury: Piranesi", "url": "https://www.bloomsbury.com/us/piranesi-9781635575637/", "supports": "Publisher's identification of the novel and its house setting; the linked synopsis contains more plot detail."},
        ],
    },
    "notice-the-details": {
        "reviewed": "2026-10-16",
        "search_title": "Slow, attentive picks like After Yang and Music for Airports",
        "summary": "Choose between After Yang, Abstract, Music for Airports, and Braiding Sweetgrass by the kind of attention each one asks for, from close watching to slow reading.",
        "lead": [
            "People talk about paying attention as one skill, but it takes several forms. You can attend to a person you are losing, to the decisions behind an ordinary object, to a sound that keeps almost repeating, or to a plant you have walked past for years. This trail puts four of those forms side by side: a quiet science-fiction drama, a documentary series about designers, an ambient album, and a book of essays.",
            "None of them is a puzzle to solve, and none asks you to keep up with a large fictional world. The decision is about what you want your attention to rest on tonight. After Yang turns toward memory and family, Abstract toward work and craft, Music for Airports toward sound and space, and Braiding Sweetgrass toward the living world and our obligations to it.",
        ],
        "comparison_intro": "Each pick asks you to slow down, each in its own way. The commitment column says what you are taking on: one film, a set of standalone episodes, an album, or a book of essays.",
        "choices": [
            {
                "key": "yang",
                "pace": "Calm and deliberate, built from small scenes and memories",
                "commitment": "One feature film, best watched without interruption",
                "best_for": "A reflective evening about family, memory, and what we fail to notice in people close to us",
                "consider": "Loss sits at the center; the science fiction is a frame, and there is no action plot",
            },
            {
                "key": "abstract",
                "pace": "Brisk documentary episodes, one designer at a time",
                "commitment": "Standalone episodes; watch one or several in any order",
                "best_for": "Seeing the decisions behind objects, buildings, and images you use every day",
                "consider": "Each episode centers one discipline, so interest varies from episode to episode",
            },
            {
                "key": "airports",
                "pace": "Slow, looping instrumental pieces with no narrative",
                "commitment": "One album of four long tracks, foreground or background",
                "best_for": "Attention without a story, or a calm setting for reading and quiet work",
                "consider": "Repetition and the absence of lyrics or beat can feel static in the wrong mood",
            },
            {
                "key": "braiding-sweetgrass",
                "pace": "Unhurried essays that join science, story, and reflection",
                "commitment": "A book to read one essay at a time over days or weeks",
                "best_for": "Changing how you look at plants, land, and reciprocity, a little at a time",
                "consider": "Its spiritual and personal tone will not suit readers who want only field science",
            },
        ],
        "sections": [
            {
                "id": "two-kinds-of-attention",
                "heading": "Watching closely versus letting something surround you",
                "paragraphs": [
                    "After Yang and Abstract both pay off if you watch closely, for different reasons. In the film, passing details about a family's routines carry much of the meaning, and the story asks what an observer can recover from small, ordinary moments. Abstract does the same for work: once a designer explains why a shoe, a typeface, or a room is shaped the way it is, the object stops being invisible.",
                    "Music for Airports works the other way. Brian Eno described ambient music as something that should reward attention while also allowing you to ignore it. That makes it the only pick here you can really use as surroundings. Try both modes in one sitting: let a track play while you read or do the dishes, then stop and listen to the same passage on purpose. You will hear things the first pass missed.",
                ],
            },
            {
                "id": "start-small",
                "heading": "Start smaller than you think you need to",
                "paragraphs": [
                    "On this trail, less is often better. One episode of Abstract, about a field you rarely think about, can stay with you longer than a whole season watched as a checklist. One essay from Braiding Sweetgrass, read slowly and followed by a walk, does more than three chapters skimmed before bed. Give one thing your full attention and forget about finishing the set.",
                    "After Yang is the one choice that asks for a full sitting. It is a short film with a slow pace, and it only works if you stay with that pace and leave your phone alone. If you only have part of an evening, pick the album or a single episode and keep the film for a night with fewer interruptions.",
                ],
            },
            {
                "id": "pairing-the-picks",
                "heading": "Pairings that sharpen each other",
                "paragraphs": [
                    "After Yang and Braiding Sweetgrass make a good pair. Both are about relationships that are easy to take for granted: one with a member of a household, the other with the plants and places around us. Watch one and read a chapter of the other in the same week, and each starts to read as a way of looking at things as well as a story.",
                    "Abstract and Music for Airports pair more directly. Eno's album is itself a piece of design, made for a particular kind of space. Play it after an Abstract episode and it stops being pleasant background. It becomes an answer to a design brief: what should a waiting room sound like?",
                ],
            },
        ],
        "item_notes": {
            "yang": [
                "Choose After Yang when you want a film that leaves you room to think and doesn't explain itself. The premise is simple: a family tries to repair Yang, an android who has been part of their household. What the film does with that premise is quieter and more personal than the setup suggests, and the less you know beforehand the better it works.",
                "It is the strongest pick here for watching with someone else, because it gives you a lot to talk about afterward without asking you to agree on an interpretation. If you prefer your science fiction to explain how its world works, this may feel too reticent.",
            ],
            "abstract": [
                "Abstract profiles one designer per episode, across fields such as illustration, architecture, typography, footwear, and stage design. Pick the discipline you know least about. Episodes about familiar subjects can be enjoyable, but the series is at its best when it shows you decisions you had no idea anyone made.",
                "Treat it as a sampler. Each episode is a portrait of one person and how they work, and none tries to teach you the whole field, so stop whenever you have found the one that changes how you see something around you.",
            ],
            "airports": [
                "Music for Airports was one of the records that defined ambient music as a genre. Its four pieces are built from overlapping loops that drift in and out of alignment, so the music changes without ever announcing a change. There is no melody to follow in the usual sense, so all you can do is listen to the sound itself.",
                "A good way in is to choose the first track and play it twice, once in the background and once with full attention. If it still feels like nothing is happening, it may simply be the wrong mood; save it for a rainy morning or a long piece of focused work and try again.",
            ],
            "braiding-sweetgrass": [
                "Robin Wall Kimmerer is a botanist and a member of the Citizen Potawatomi Nation, and the book draws on both of those ways of knowing. Its essays move between plant science, Indigenous teachings, and her own life as a mother and teacher. The book asks what would change if we treated the natural world as a web of relationships and stopped treating it as a store of resources.",
                "This is the slowest pick in the trail, and it should be read slowly. Each essay stands on its own, so you can read them out of order. If one essay mentions a plant that grows near you, go and look at it; the book is written to be taken that literally.",
            ],
        },
        "related": [
            {"slug": "weather-and-windows", "reason": "For atmosphere-led films, music, and fiction where setting carries much of the feeling."},
            {"slug": "make-something", "reason": "For moving from noticing how things are made to trying some making of your own."},
        ],
        "sources": [
            {"key": "yang", "label": "A24: After Yang", "url": "https://a24films.com/films/after-yang", "supports": "Distributor's film page with the director and premise of the family and their android companion."},
            {"key": "abstract", "label": "Netflix: Abstract: The Art of Design", "url": "https://www.netflix.com/title/80057883", "supports": "Series listing and format as a documentary series profiling individual designers; availability varies by region."},
            {"key": "airports", "label": "Brian Eno shop: Ambient 1: Music for Airports", "url": "https://shop.brian-eno.net/collections/music/products/ambient-1-music-for-airports-vinyl-2lp", "supports": "Official release identification for the album."},
            {"key": "braiding-sweetgrass", "label": "Milkweed Editions: Braiding Sweetgrass", "url": "https://milkweed.org/book/braiding-sweetgrass", "supports": "Publisher's description of the book, its author, and its blend of botany and Indigenous knowledge."},
        ],
    },
    "small-adventures": {
        "reviewed": "2026-10-16",
        "search_title": "Cozy adventures like Paddington 2, A Short Hike and more",
        "summary": "Compare Paddington 2, Laid-Back Camp, A Short Hike, and The Hobbit by pace, length, and how much adventure you want before you are back somewhere warm.",
        "lead": [
            "Some evenings call for an adventure without the exhaustion of an epic. You want a change of scenery, a few surprises, and good company, and you want to be home before it turns into a commitment. This trail collects four journeys of that kind: a family film, a slice-of-life camping series, a short exploration game, and the original there-and-back-again novel.",
            "All four are warm without being dull. Each has real momentum, whether it is a comic caper, a cold night outdoors, a climb to a summit, or a dragon at the end of the road. The difference is how long you want to stay and whether you want to watch, play, or read your way there.",
        ],
        "comparison_intro": "All four are gentle. They differ in how long they last, how much they ask of you, and the company they keep.",
        "choices": [
            {
                "key": "paddington-2",
                "pace": "Quick, inventive comedy with a caper plot",
                "commitment": "One family film; the first film helps but is not required",
                "best_for": "A guaranteed lift that adults and children can enjoy together",
                "consider": "Its sweetness is deliberate and constant, with no ambiguity at all",
            },
            {
                "key": "laid-back-camp",
                "pace": "Slow, low-conflict episodes about planning and enjoying trips",
                "commitment": "A series of short episodes; one makes a complete small outing",
                "best_for": "Unwinding with a show where a warm meal and a good view are the climax",
                "consider": "Very little happens by design; viewers wanting stakes may drift",
            },
            {
                "key": "short-hike",
                "pace": "Free-roaming exploration at your own speed",
                "commitment": "A compact game that most players can finish in an evening or two",
                "best_for": "A game that respects a short session and makes wandering off the path worth it",
                "consider": "Light platforming and flying controls; it is small by design",
            },
            {
                "key": "hobbit",
                "pace": "Episodic chapters with a storyteller's voice",
                "commitment": "A novel, easy to read a chapter at a time",
                "best_for": "The classic journey of a homebody who discovers he is braver than he thought",
                "consider": "Older prose rhythms, and later chapters grow darker than the opening suggests",
            },
        ],
        "sections": [
            {
                "id": "how-long-is-the-trip",
                "heading": "Decide how long the trip should be",
                "paragraphs": [
                    "The first choice is length. Paddington 2 is one film with a clear ending, the easiest option when you want something complete tonight. A Short Hike is nearly as contained: its island is small, its goal is clear, and many players reach the summit in a single relaxed evening. Both suit a night when you want an ending without having to plan for a second session.",
                    "Laid-Back Camp and The Hobbit are better as recurring visits. Each Laid-Back Camp episode is a small outing in itself, so the series is better dipped into on quiet evenings than binged. The Hobbit's chapters often end at a natural resting point, which makes it well suited to bedtime reading over a couple of weeks.",
                ],
            },
            {
                "id": "watching-playing-reading",
                "heading": "Watching, playing, or reading the journey",
                "paragraphs": [
                    "A Short Hike is the one choice where you set the pace. Its world is full of side paths, odd characters, and small tasks, and the game is noticeably better when you follow your curiosity instead of taking the fastest route up the mountain. If you would sooner explore a place on your own than be led through it, start here.",
                    "The film and the series carry you along instead. Paddington 2 is tightly plotted and full of visual jokes you only catch if you watch closely. Laid-Back Camp asks for almost nothing, which is part of its appeal: it is a show about the pleasure of planning, preparing food, and arriving somewhere cold and beautiful. The Hobbit sits between them: your imagination fills in the road, and a confident narrator leads you along it.",
                ],
            },
            {
                "id": "why-gentle-works",
                "heading": "Why gentle stories still feel like adventures",
                "paragraphs": [
                    "In none of these is the world in danger. Paddington wants to buy a birthday present. The campers want a good spot and a hot meal. The hiker wants to reach the top of a mountain to get a phone signal. Bilbo wants, at first, to go home. Small goals keep the stakes human, so the warmth feels earned.",
                    "That makes this trail a good choice when you are tired of stories that keep raising the stakes. If you finish one and want more of the same feeling, switch formats instead of looking for another title of the same kind. Going from the film to the game, or from the series to the book, keeps the gentleness and gives your attention something new to do.",
                ],
            },
        ],
        "item_notes": {
            "paddington-2": [
                "Paddington 2 follows the bear's attempt to buy a special pop-up book as a present for his Aunt Lucy, which leads him into far more trouble than a birthday gift should. The film moves quickly and its comic set pieces are carefully built, so it holds up well for adults as well as children.",
                "Choose it when you want a sure thing. It is the most crowd-pleasing pick in the trail and the easiest to share with a group of mixed ages. If the relentless kindness sounds tiring tonight, A Short Hike offers a quieter kind of warmth.",
            ],
            "laid-back-camp": [
                "Laid-Back Camp follows a group of friends who go camping, often in winter, and much of each episode is about the preparation: gear, routes, food, and the view at the end. It is closer to a relaxing travel diary than a plot-driven series.",
                "Watch one episode as a test. If the quiet pace and attention to small comforts appeal to you, the series makes an excellent wind-down show. If you find yourself waiting for something to go wrong, it may simply not be the right fit, and the film or the game will serve you better.",
            ],
            "short-hike": [
                "In A Short Hike you explore a small island park on the way to its highest peak. Climbing is easier as you collect feathers, but the island is full of reasons to wander off: fishing spots, races, odd conversations, and hidden corners. The game is short and deliberately unhurried.",
                "Resist looking up a route. The pleasure is in finding your own way and stumbling onto things. It is also the easiest game in this collection for someone who rarely plays games, because its controls are simple and its goals are always visible.",
            ],
            "hobbit": [
                "The Hobbit begins as a comic story about a comfortable homebody pulled into an adventure he did not ask for, and slowly becomes more serious as the journey goes on. Bilbo's growing courage, and the fact that he never quite stops missing home, gives the book its shape.",
                "It works well read aloud and in short sittings. If you only know the story from film adaptations, the book will feel lighter and more playful, especially in its riddles and its narrator's asides. Expect the final chapters to carry more weight than the opening suggests.",
            ],
        },
        "related": [
            {"slug": "one-evening-well-spent", "reason": "For more picks with a satisfying single sitting, from film to album."},
            {"slug": "found-family", "reason": "For stories where the company on the journey becomes the real point."},
        ],
        "sources": [
            {"key": "paddington-2", "label": "Paddington: official site", "url": "https://www.paddington.com/", "supports": "Official home of Paddington Bear, identifying the character and the films."},
            {"key": "laid-back-camp", "label": "Laid-Back Camp: official anime site (Japanese)", "url": "https://yurucamp.jp/", "supports": "Official identification of the TV anime series."},
            {"key": "short-hike", "label": "A Short Hike: official site", "url": "https://ashorthike.com/", "supports": "Developer's description of hiking and climbing to the peak of a provincial park."},
            {"key": "hobbit", "label": "Tolkien Estate: The Hobbit", "url": "https://www.tolkienestate.com/writing/the-hobbit/", "supports": "Estate page identifying the book and its history."},
        ],
    },
    "clever-mysteries": {
        "reviewed": "2026-10-16",
        "search_title": "Mysteries like Knives Out, Poker Face and Odd Taxi",
        "summary": "Choose between Knives Out, Poker Face, Odd Taxi, and The Thursday Murder Club by puzzle style, pace, and how much you want to solve versus enjoy watching it unfold.",
        "lead": [
            "A good mystery gives you a reason to pay attention. The four works here each do that differently: a whodunit film built for a group watch, a series that shows you the crime first, an anime that hides its puzzle inside ordinary conversations, and a novel about friends who solve cases together. You won't need a notebook for any of them, but each pays off if you notice things.",
            "Start with what you enjoy about mysteries. If it is the reveal, start with Knives Out. If it is watching a clever person close in, try Poker Face. If you like a puzzle that builds slowly from scattered pieces, Odd Taxi is the one. If you are there for the characters as much as the crime, The Thursday Murder Club will suit you.",
        ],
        "comparison_intro": "They are all mysteries, but the puzzles work differently. None of the descriptions below gives away a solution.",
        "choices": [
            {
                "key": "knives-out",
                "pace": "A brisk, twisting whodunit with plenty of comedy",
                "commitment": "One film with a complete solution",
                "best_for": "A shared movie night where everyone guesses along",
                "consider": "Broad comic characters; a death and family cruelty drive the plot",
            },
            {
                "key": "poker-face",
                "pace": "One case per episode, shown first and then solved",
                "commitment": "An episodic series; most episodes stand alone",
                "best_for": "Watching a culprit get caught when you already know who did it",
                "consider": "Violence and grim situations sit under a playful tone",
            },
            {
                "key": "odd-taxi",
                "pace": "Slow-building conversations that lock together over the series",
                "commitment": "One short series, best watched in order",
                "best_for": "A patient puzzle where small details pay off much later",
                "consider": "Animal character designs hide mature themes; early episodes feel unconnected",
            },
            {
                "key": "thursday-murder-club",
                "pace": "Light, witty chapters that shift between characters",
                "commitment": "A novel, the first in a series",
                "best_for": "Cozy crime where friendship is as important as the case",
                "consider": "Cozier than most crime fiction, but still about murder, grief, and illness",
            },
        ],
        "sections": [
            {
                "id": "whodunit-or-howcatchem",
                "heading": "Whodunit or howcatchem?",
                "paragraphs": [
                    "Knives Out and Poker Face come from the same filmmaker, Rian Johnson, but they ask different questions. Knives Out is a classic whodunit: everyone has a motive, and the pleasure is in the moment the story reveals how wrong you were. Poker Face is a howcatchem in the tradition of Columbo. Each episode shows the crime first, so the tension comes from watching the detective notice what the culprit missed.",
                    "If you tend to read the last page of a mystery first, Poker Face may suit you better, because it removes the guessing and keeps the cleverness. If you love trying to beat the detective, Knives Out gives you a fair chance and a satisfying explanation at the end.",
                ],
            },
            {
                "id": "slow-and-fast-puzzles",
                "heading": "Fast puzzles and slow ones",
                "paragraphs": [
                    "Odd Taxi works on a much longer fuse. Its early episodes feel like a series of strange, funny conversations between a taxi driver and his passengers. Only gradually do you realize that many of those conversations connect, and that small details from the first episodes matter. It is the best pick here for viewers who like being surprised by how a story was put together.",
                    "The Thursday Murder Club sits between the two speeds. Each chapter moves quickly, but the investigation unfolds over the whole book, with several threads running at once. Its narrators include the investigators themselves, which lets you see how differently each of them thinks.",
                ],
            },
            {
                "id": "playing-fair",
                "heading": "Enjoying a mystery without spoiling it",
                "paragraphs": [
                    "Mysteries are easy to spoil, so a small rule helps: avoid reading episode summaries or reviews until you have finished. Odd Taxi in particular is best watched without knowing anything beyond its premise, because so much of its pleasure is in how pieces fall into place.",
                    "If you want something to do while you watch or read, write down the one detail that seemed odd at the time. It is a simple habit that makes reveals more satisfying, whether you were right or not. And if you are watching with friends, Knives Out is ideal for pausing halfway to compare theories.",
                ],
            },
        ],
        "item_notes": {
            "knives-out": [
                "Knives Out follows detective Benoit Blanc as he investigates the death of a wealthy crime novelist after his birthday party, surrounded by a family with plenty to hide. The film is funny and quick, and it plays fair with the audience in a way that makes the solution feel earned.",
                "It is the best choice for a group, because everyone can guess along and the ending gives you something to argue about. If you have already seen it, its sequels continue Blanc's cases with new casts and settings.",
            ],
            "poker-face": [
                "Poker Face follows Charlie Cale, who can tell when someone is lying, as she travels from place to place and keeps stumbling into crimes. Each episode starts by showing you the crime, then follows Charlie as she works out what happened.",
                "Treat it like a short story collection. Most episodes stand alone, with a light ongoing thread, so you can stop after one or two without losing track. It is a good fit for a weeknight when a full film is too much.",
            ],
            "odd-taxi": [
                "Odd Taxi follows Odokawa, a taciturn taxi driver whose passengers turn out to be connected to a missing person case. Its animal characters and dry humor make it look lighter than it is. Underneath, it is a carefully constructed crime story about loneliness, money, and the strange ways city lives overlap.",
                "Give it at least three episodes before deciding. The early conversations can feel like they are going nowhere, and that is part of the design. Viewers who stay usually find the payoff worth the patience.",
            ],
            "thursday-murder-club": [
                "The Thursday Murder Club follows four friends in a retirement village who meet each week to look at unsolved cases, until a real murder happens nearby. The book's warmth comes from the group: their competence, their banter, and their frank conversations about age and loss.",
                "It is the most social pick in this trail and the gentlest in tone. If you enjoy it, there are several follow-up novels, so it can become a longer reading habit. Choose another option if you want a darker or more tightly plotted puzzle.",
            ],
        },
        "related": [
            {"slug": "beautifully-strange-worlds", "reason": "For worlds you understand by observing their rules, including a solar-system mystery game."},
            {"slug": "weather-and-windows", "reason": "For quieter stories where what is left unsaid carries as much as what is shown."},
        ],
        "sources": [
            {"key": "knives-out", "label": "Independent Cinema Office: Knives Out", "url": "https://www.independentcinemaoffice.org.uk/films/knives-out", "supports": "Film identification, director, running time, and premise of Benoit Blanc's investigation."},
            {"key": "poker-face", "label": "Peacock: Poker Face (US)", "url": "https://www.peacocktv.com/stream-tv/poker-face", "supports": "Series overview and lead character; availability varies by region."},
            {"key": "odd-taxi", "label": "Odd Taxi: official anime site (Japanese)", "url": "https://oddtaxi.jp/", "supports": "Official identification of the TV anime series."},
            {"key": "thursday-murder-club", "label": "Penguin: The Thursday Murder Club", "url": "https://www.penguin.co.uk/books/313038/the-thursday-murder-club-by-osman-richard/9780241988268", "supports": "Publisher's identification of the novel, its author, and its retirement-village premise."},
        ],
    },
    "found-family": {
        "reviewed": "2026-10-16",
        "search_title": "Found family stories like Spy x Family and The Bear",
        "summary": "Compare Hunt for the Wilderpeople, The Bear, Spy x Family, and The Miseducation of Lauryn Hill by tone, intensity, and how each one shows care being learned.",
        "lead": [
            "Found family stories are about people who were not supposed to belong to each other and end up doing so anyway. The best of them do not pretend this is easy. Care has to be practiced, mistakes have to be forgiven, and the family that results is often stranger and more fragile than the one anyone planned.",
            "This trail approaches that idea from four directions: a comic adventure in the New Zealand bush, a high-pressure restaurant drama, a spy comedy about a fake family becoming a real one, and an album about love, faith, and self-respect. They differ hugely in tone, so the choice comes down to how much intensity you want tonight.",
        ],
        "comparison_intro": "All four involve learning to care for someone, but at very different volumes. Compare the tone and intensity before choosing.",
        "choices": [
            {
                "key": "wilderpeople",
                "pace": "A comic chase with quiet, sad moments in between",
                "commitment": "One feature film",
                "best_for": "Laughing and being moved in the same evening",
                "consider": "Grief and child welfare themes sit under the jokes",
            },
            {
                "key": "the-bear",
                "pace": "Fast, loud, and often deliberately overwhelming",
                "commitment": "A serialized drama with short episodes",
                "best_for": "An ensemble that earns its closeness through hard work and conflict",
                "consider": "High stress, shouting, and depictions of grief and addiction",
            },
            {
                "key": "spy-family",
                "pace": "Light episodes that mix missions and household comedy",
                "commitment": "A series of mostly self-contained episodes",
                "best_for": "Warm, funny company with a clever premise",
                "consider": "Stylized action violence and some jokes aimed at older viewers",
            },
            {
                "key": "miseducation",
                "pace": "A full album moving between soul, hip-hop, and reggae",
                "commitment": "One album, best heard in order at least once",
                "best_for": "A voice working out love, faith, and self-worth in public",
                "consider": "Explicit lyrics and direct material about relationships and betrayal",
            },
        ],
        "sections": [
            {
                "id": "choose-your-volume",
                "heading": "Choose the volume you can handle tonight",
                "paragraphs": [
                    "The Bear is the loudest choice by a distance. Its kitchen is a place of shouting, panic, and old grief, and its sense of family comes from surviving that pressure together. It can be thrilling, but it can also be draining. If your day has already been stressful, save it for another night.",
                    "Spy x Family is the opposite: a light, funny series where the danger is mostly a joke and the real question is whether three people pretending to be a family will start to mean it. Hunt for the Wilderpeople sits between them. It is very funny, but its two main characters are both grieving, and the film lets that sadness show.",
                ],
            },
            {
                "id": "care-is-practiced",
                "heading": "Care as something you practice",
                "paragraphs": [
                    "A common thread in these picks is that affection grows out of routine. In The Bear, the cooks learn to trust each other through the discipline of the kitchen. In Spy x Family, packed lunches, school interviews, and family outings slowly turn a cover story into a home. In Hunt for the Wilderpeople, surviving in the bush forces a boy and his foster uncle to depend on each other before they are ready to like each other.",
                    "Lauryn Hill's album turns the same idea inward. Its songs move between love, heartbreak, faith, and motherhood, and between them are recorded conversations in a classroom where young people talk about love. It is the only pick here without characters in the usual sense, but it is just as concerned with how people learn to care, including for themselves.",
                ],
            },
            {
                "id": "pairings",
                "heading": "Pairings worth trying",
                "paragraphs": [
                    "Hunt for the Wilderpeople and Spy x Family make a good double bill. Both are comedies about a child joining an unlikely household, and both use humor to make room for real feeling. One is set in the New Zealand bush and the other in a spy's household, and seeing the same kind of story told both ways is half the fun.",
                    "The Bear and The Miseducation of Lauryn Hill pair in a different way. Both are about talented people trying to stay true to their work while carrying grief, expectation, and complicated relationships. Listening to the album after a few episodes can feel like stepping out of the kitchen into a quieter room where the same questions are still being asked.",
                ],
            },
        ],
        "item_notes": {
            "wilderpeople": [
                "Hunt for the Wilderpeople follows Ricky, a city kid placed with foster parents in rural New Zealand, and his gruff foster uncle Hec. When circumstances push them into the bush, a national manhunt follows. Taika Waititi's direction keeps the jokes coming, but the film never forgets that both characters are lonely.",
                "It is the most balanced pick in the trail: funny enough for a light night, moving enough to stay with you. It is also a good choice for watching with teenagers, though its themes of grief and foster care may need a word beforehand for younger viewers.",
            ],
            "the-bear": [
                "The Bear follows a talented chef who returns to Chicago to run his family's struggling sandwich shop after his brother's death. The staff, the debts, and the grief all come with it. The series is known for its intensity, and for making ordinary kitchen work feel urgent.",
                "Start with the first few episodes and see how the pressure sits with you. If the chaos is too much, that's a fair reaction and says nothing bad about your taste. If you stay, you get a group of people who become a family through work, argument, and hard-won respect.",
            ],
            "spy-family": [
                "In Spy x Family, a spy needs a family for a mission, so he adopts a girl and marries a woman. What he does not know is that his daughter can read minds and his wife is an assassin. The joke is that each of them is hiding something, and each of them starts to care more than they meant to.",
                "Its episodes are light and often self-contained, which makes it a good wind-down show. Its action is stylized and its comedy broad, so choose it when you want warmth and laughter more than tension.",
            ],
            "miseducation": [
                "The Miseducation of Lauryn Hill was her debut solo album, and it remains one of the most celebrated records of its era. It moves between soul, hip-hop, and reggae, and its songs range from sharp critiques of a relationship to a tender song for her son.",
                "Listen to the whole album in order once, including the classroom interludes. They shape how the songs feel and give the record its sense of a conversation about love. After that, it is easy to return to individual songs on their own.",
            ],
        },
        "related": [
            {"slug": "finding-your-feet", "reason": "For stories about starting over, where belonging is something you build."},
            {"slug": "small-adventures", "reason": "For warm journeys where good company counts for more than high stakes."},
        ],
        "sources": [
            {"key": "wilderpeople", "label": "New Zealand Film Commission: Hunt for the Wilderpeople", "url": "https://www.nzfilm.co.nz/films/hunt-wilderpeople", "supports": "Film identification, director, and premise of the foster child and his uncle in the bush."},
            {"key": "the-bear", "label": "FX: The Bear", "url": "https://www.fxnetworks.com/shows/the-bear", "supports": "Network's series page and premise of the Chicago restaurant and its crew."},
            {"key": "spy-family", "label": "SPY×FAMILY: official anime site (Japanese)", "url": "https://spy-family.net/", "supports": "Official identification of the TV anime series and its credits."},
            {"key": "miseducation", "label": "Lauryn Hill: official site", "url": "https://www.laurynhill.com/", "supports": "Artist's official site identifying the album and its artist."},
        ],
    },
    "weather-and-windows": {
        "reviewed": "2026-10-16",
        "search_title": "Atmospheric picks like In the Mood for Love and Punisher",
        "summary": "Choose between In the Mood for Love, The Garden of Words, Punisher, and The Memory Police by mood, length, and how heavy the atmosphere becomes.",
        "lead": [
            "Some works are remembered less for what happens than for how they feel: the light in a corridor, the sound of rain, a song playing in the next room. This trail gathers four of them. In each, setting and weather carry emotions the characters cannot say out loud, and the atmosphere does as much of the storytelling as the plot.",
            "They are patient works, and none is light comfort. The choice is about which atmosphere you want to sit inside: a Hong Kong corridor in the early 1960s, a rainy garden in Tokyo, a late-night album, or an island where things keep disappearing.",
        ],
        "comparison_intro": "These picks share a mood but differ in weight. Compare length and emotional heaviness before choosing; the descriptions avoid major plot turns.",
        "choices": [
            {
                "key": "in-the-mood-for-love",
                "pace": "Slow, repetitive, and precisely composed",
                "commitment": "One feature film, best in a single sitting",
                "best_for": "A visually rich evening about restraint and longing",
                "consider": "Very little is said directly; the drama lives in gesture and music",
            },
            {
                "key": "garden-of-words",
                "pace": "Quiet scenes framed by rain and seasons",
                "commitment": "A short anime film, well under an hour",
                "best_for": "A concise, beautiful watch when time is limited",
                "consider": "An age-gap relationship and emotional distress complicate its beauty",
            },
            {
                "key": "punisher",
                "pace": "Spacious songs that build slowly and end loudly",
                "commitment": "One album, ideally heard late at night",
                "best_for": "Wry, detailed songwriting that turns anxiety into something you can listen to",
                "consider": "Explicit lyrics and themes of depression, grief, and self-harm",
            },
            {
                "key": "memory-police",
                "pace": "Calm, clear prose with a growing sense of dread",
                "commitment": "A novel to read across several sittings",
                "best_for": "A calm, unsettling story about memory and resistance",
                "consider": "State coercion and violence make it far from cozy",
            },
        ],
        "sections": [
            {
                "id": "setting-as-feeling",
                "heading": "When the setting says what characters cannot",
                "paragraphs": [
                    "In the Mood for Love is the clearest example of this trail's idea. Two neighbors pass each other again and again in narrow corridors and stairways, and the repetition, the clothing, the rain, and a recurring piece of music build an emotional world the characters never openly name. The events matter less than the small changes in those patterns, which is where the meaning sits.",
                    "The Garden of Words uses weather more literally. Two strangers meet in a garden on rainy mornings, and the rainy season frames their conversations. When the weather changes, so does what is possible between them. Its animation of rain, light, and leaves is a large part of its appeal, and its short length makes it easy to fit into an evening.",
                ],
            },
            {
                "id": "music-and-words",
                "heading": "An album and a novel as places to stay",
                "paragraphs": [
                    "Punisher builds atmosphere through songwriting. Phoebe Bridgers sets sharp, specific details, often funny, against quiet arrangements, so a song can drift from a joke into an admission before you notice the shift. The album is best heard late at night and in order, when its slow builds and its loud closing track have room to land.",
                    "The Memory Police builds atmosphere through absence. On an unnamed island, objects disappear and people are expected to forget them, while a police force makes sure they do. Yoko Ogawa's prose is calm and clear, which makes each loss feel more unsettling. It is the darkest pick in the trail and the one that lingers longest.",
                ],
            },
            {
                "id": "choosing-weather",
                "heading": "Choosing for the weather you are in",
                "paragraphs": [
                    "Mood trails work best when you match them to your own state. If you are tired but want something beautiful, The Garden of Words is short and visually generous. If you have a full evening and the patience for something slow, In the Mood for Love will repay it. If you want company for a late walk or a sleepless night, Punisher fits.",
                    "Save The Memory Police for when you have the emotional room. Its atmosphere is quiet but heavy, and it is better read in a few sittings with time to think between them. If you finish it wanting something gentler, the Notice the details trail offers attentive works with a lighter touch.",
                ],
            },
        ],
        "item_notes": {
            "in-the-mood-for-love": [
                "Set in Hong Kong in the early 1960s, Wong Kar-wai's film follows two neighbors who come to suspect that their spouses are having an affair with each other. What follows is a story of closeness held carefully in check. The film's images, costumes, and music are as important as its dialogue.",
                "Watch it without distractions and let its repetitions work on you. If you find yourself impatient, notice what changes each time a scene seems to repeat; that is where much of the story lives.",
            ],
            "garden-of-words": [
                "Makoto Shinkai's short film follows a student who skips class on rainy mornings to sketch shoe designs in a Tokyo garden, where he keeps meeting the same woman. Their conversations become a refuge from difficulties neither fully explains.",
                "It is the shortest pick in the trail and the most visually lush. Be aware that the relationship involves an adult and a teenager. The film treats it with restraint, but some viewers will find that uncomfortable, and it is better to know that before you choose it.",
            ],
            "punisher": [
                "Punisher was Phoebe Bridgers' second album, and it is full of sharp, specific images: hotel rooms, tour buses, late-night drives, and dreams. Its humor is dry and its sadness is direct, often in the same verse.",
                "Listen to it in order at least once. The album builds toward its final song, which grows from quiet to overwhelming. If its themes of depression and self-harm feel too close tonight, it is fine to save it for another time.",
            ],
            "memory-police": [
                "The Memory Police follows a novelist on an island where things vanish: birds, roses, photographs, and more. Most people forget them as soon as they disappear, while a few cannot forget and must hide. The book was first published in Japanese in 1994; its English translation by Stephen Snyder appeared in 2019.",
                "Read it slowly. Its plain style can make it seem simple, but the slow build of loss and fear is where its force comes from. It pairs well with In the Mood for Love as another story about what can and cannot be said.",
            ],
        },
        "related": [
            {"slug": "notice-the-details", "reason": "For quiet works about attention and memory, with a gentler tone."},
            {"slug": "beautifully-strange-worlds", "reason": "For more imagined places with their own rules, from bathhouses for spirits to an endless house."},
        ],
        "sources": [
            {"key": "in-the-mood-for-love", "label": "Criterion: In the Mood for Love", "url": "https://www.criterion.com/films/198-in-the-mood-for-love", "supports": "Film edition details, director, and setting in 1960s Hong Kong."},
            {"key": "garden-of-words", "label": "Makoto Shinkai Works: The Garden of Words", "url": "https://en.shinkaiworks.com/film/kotonoha.html", "supports": "Official film page and premise of the rainy-morning meetings in a garden."},
            {"key": "punisher", "label": "Phoebe Bridgers: official site", "url": "https://www.phoebefuckingbridgers.com/", "supports": "Artist's official site identifying the album and its artist."},
            {"key": "memory-police", "label": "Penguin Random House: The Memory Police", "url": "https://www.penguinrandomhouse.com/books/252774/the-memory-police-by-yoko-ogawa/9781101911815", "supports": "Publisher's page identifying the novel, its author, and its translator, Stephen Snyder."},
        ],
    },
    "make-something": {
        "reviewed": "2026-10-16",
        "search_title": "Picks that inspire making: Chicory, Jiro and The Creative Act",
        "summary": "Compare Jiro Dreams of Sushi, The Great Pottery Throw Down, Chicory, and The Creative Act by how each one shows craft, practice, and getting started.",
        "lead": [
            "Watching someone make something can be oddly motivating. You see the repetition, the mistakes, and the small decisions behind a finished piece, and suddenly your own unfinished project looks like a normal stage of the work. This trail gathers four works about making: a documentary about a sushi master, a friendly pottery competition, a painting adventure game, and a book of short reflections on creativity.",
            "They take very different views of craft. Jiro is about devotion and exacting standards. Pottery Throw Down is about learning in public and being kind about it. Chicory is about creative pressure and self-doubt. The Creative Act is about getting out of your own way. Choose by the voice you need to hear today.",
        ],
        "comparison_intro": "Each of these can nudge you toward making something, but with a different kind of encouragement. Compare the tone and commitment before choosing.",
        "choices": [
            {
                "key": "jiro",
                "pace": "Calm, observational documentary",
                "commitment": "One feature-length film",
                "best_for": "Seeing what decades of focused practice look like",
                "consider": "Its idea of mastery is demanding and its workplace culture is strict",
            },
            {
                "key": "pottery-throw-down",
                "pace": "Friendly competition episodes with clear weekly challenges",
                "commitment": "A series of episodes; any season works as a starting point",
                "best_for": "Watching people learn, fail, and help each other",
                "consider": "Eliminations, and availability varies by region",
            },
            {
                "key": "chicory",
                "pace": "Exploration and puzzles at your own speed",
                "commitment": "A full-length adventure game played over several sessions",
                "best_for": "Making marks right away inside a story about creative pressure",
                "consider": "Frank about anxiety, depression, and burnout under its bright style",
            },
            {
                "key": "creative-act",
                "pace": "Short reflections you can open anywhere",
                "commitment": "A book to dip into before or between creative sessions",
                "best_for": "A gentle push to start or to keep going",
                "consider": "Philosophical, with no step-by-step advice",
            },
        ],
        "sections": [
            {
                "id": "two-ideas-of-craft",
                "heading": "Two very different ideas of practice",
                "paragraphs": [
                    "Jiro Dreams of Sushi and The Great Pottery Throw Down both show people working with their hands, but they come from opposite ends of the craft spectrum. Jiro's restaurant is about refinement over decades: apprentices repeat the same tasks for years before they are trusted with more. The film admires that devotion while letting you see its costs.",
                    "Pottery Throw Down shows the other end, where amateur potters learn quickly under time pressure and often get it wrong. Pieces collapse, glazes go strange, and the judges are visibly moved when something works. If Jiro makes mastery feel distant, Pottery Throw Down makes learning feel possible.",
                ],
            },
            {
                "id": "making-while-you-play",
                "heading": "A game that lets you make marks right away",
                "paragraphs": [
                    "Chicory is the only pick where you make something yourself. You play a character who picks up a giant magic paintbrush and can paint directly onto a black-and-white world. Painting solves puzzles and changes the landscape, but you can also simply decorate, and the game never grades your art.",
                    "Its story is about what happens when making becomes a responsibility: expectation, comparison, and the fear of not being good enough. That makes it an unusually honest game about creativity. If you have ever stalled on a project because it mattered too much, its themes may feel familiar.",
                ],
            },
            {
                "id": "from-watching-to-making",
                "heading": "Turning inspiration into a small start",
                "paragraphs": [
                    "The risk of this trail is that watching people make things can replace making things. A simple rule helps: after an episode, a chapter, or a play session, spend ten minutes on something of your own. It does not need to be good. The idea is to start doing while the feeling is still fresh.",
                    "The Creative Act is designed for exactly that moment. Its short sections can be read in a minute or two and then put down. Open it at random before you start, take the one idea that seems to apply, and close the book. Treat it as a warm-up for a session. It makes no attempt to be a manual.",
                ],
            },
        ],
        "item_notes": {
            "jiro": [
                "Jiro Dreams of Sushi follows Jiro Ono, a sushi chef in Tokyo, along with his sons and apprentices. It is a calm, beautifully shot film about repetition, standards, and succession, and about a man who has spent his life trying to make one thing a little better each day.",
                "Watch it as a study of practice as much as a food film. Notice how much of the work is preparation that diners never see. It may also raise questions about whether that level of devotion is admirable, costly, or both.",
            ],
            "pottery-throw-down": [
                "The Great Pottery Throw Down sets home potters a series of challenges, from throwing on the wheel to building larger pieces, judged by professional potters. It is known for its supportive atmosphere: contestants help each other, and the judging is generous as well as honest.",
                "Pick any season and start with the first episode. Even if you have never touched clay, you will quickly start to see how material, time, and technique shape each decision. It is the most relaxing pick in the trail.",
            ],
            "chicory": [
                "Chicory: A Colorful Tale is an adventure game where painting is your main tool. You explore, solve puzzles, help townsfolk, and slowly uncover a story about the pressures of being the person everyone expects to make beautiful things.",
                "Paint badly on purpose for a while. The game is more enjoyable once you stop trying to make each mark perfect.",
            ],
            "creative-act": [
                "Rick Rubin is a music producer known for working with artists across many genres. The Creative Act gathers his thoughts on creativity into short sections about attention, habits, doubt, and finishing work. It applies to any kind of making, not only music.",
                "Do not read it straight through like a manual. It works best as a book you open for a few minutes before you begin, or when you are stuck. Readers who want concrete techniques may find it too abstract, so pair it with something more hands-on.",
            ],
        },
        "related": [
            {"slug": "finding-your-feet", "reason": "For stories about learning, starting over, and growing into new abilities."},
            {"slug": "notice-the-details", "reason": "For works about paying close attention, including a documentary series about designers."},
        ],
        "sources": [
            {"key": "jiro", "label": "Magnolia Pictures: Jiro Dreams of Sushi", "url": "https://www.magpictures.com/jirodreamsofsushi/", "supports": "Distributor's official film site about the documentary and its subject, Jiro Ono."},
            {"key": "pottery-throw-down", "label": "BBC Programmes: The Great Pottery Throw Down", "url": "https://www.bbc.co.uk/programmes/b09qy65b", "supports": "Broadcaster's programme page for the series' original BBC run; later series aired on Channel 4."},
            {"key": "chicory", "label": "Chicory: A Colorful Tale official site", "url": "https://www.chicorygame.com/", "supports": "Developer's description of the painting adventure game."},
            {"key": "creative-act", "label": "Penguin Random House: The Creative Act", "url": "https://www.penguinrandomhouse.com/books/717356/the-creative-act-by-rick-rubin/", "supports": "Publisher's page identifying the book and its author."},
        ],
    },
    "distant-futures": {
        "reviewed": "2026-10-16",
        "search_title": "Sci-fi like Arrival, Citizen Sleeper and Scavengers Reign",
        "summary": "Choose between Arrival, Scavengers Reign, Citizen Sleeper, and The Left Hand of Darkness by how each one makes a large science-fiction idea personal.",
        "lead": [
            "Good science fiction uses an imagined world to look at the present from an unfamiliar angle. Predicting the future is beside the point. The four picks in this trail all do that at a human scale: a linguist trying to talk to visitors, survivors stranded on a planet that does not care about them, a worker trying to build a life on a space station, and an envoy trying to understand a society unlike his own.",
            "They differ most in how much they ask of you. Arrival is the most accessible. Scavengers Reign is the strangest and most intense. Citizen Sleeper asks you to make choices. The Left Hand of Darkness asks for patience. Choose by the kind of effort you want to give tonight.",
        ],
        "comparison_intro": "Each pick turns a big idea into a personal story. Compare intensity and commitment before choosing; the descriptions avoid major twists.",
        "choices": [
            {
                "key": "arrival",
                "pace": "Measured, with tension building toward a clear resolution",
                "commitment": "One feature film",
                "best_for": "Thoughtful first-contact science fiction that is moving and easy to follow",
                "consider": "Grief and a nonlinear structure; best watched without spoilers",
            },
            {
                "key": "scavengers-reign",
                "pace": "Slow, eerie survival with sudden violence",
                "commitment": "One complete season of animated episodes",
                "best_for": "Strange ecosystems and creatures that feel truly alien",
                "consider": "Adult animation with body horror and frequent peril",
            },
            {
                "key": "citizen-sleeper",
                "pace": "Turn-based days driven by dice and choices",
                "commitment": "A narrative game played over several sessions",
                "best_for": "Making choices about who to help and how to survive",
                "consider": "Reading-heavy, with themes of poverty, illness, and exploitation",
            },
            {
                "key": "left-hand-darkness",
                "pace": "Deliberate, thoughtful, with a long journey at its heart",
                "commitment": "A classic novel to read across several sittings",
                "best_for": "A slow story about culture, gender, and trust that repays patience",
                "consider": "Measured pacing and a narrator whose assumptions are part of the subject",
            },
        ],
        "sections": [
            {
                "id": "communication",
                "heading": "Stories about understanding the unfamiliar",
                "paragraphs": [
                    "Arrival and The Left Hand of Darkness are both about communication. In Arrival, a linguist is asked to find a way to talk to visitors whose language works nothing like ours, and the film treats translation as a source of suspense. In Le Guin's novel, an envoy from a group of worlds tries to persuade a planet to join them, and finds that his own assumptions are the biggest obstacle.",
                    "Both need patience, of different kinds. Arrival is built to be gripping, with a clear emotional arc and a satisfying shape. The Left Hand of Darkness takes its time, and much of its power comes from slowly watching two people learn to trust each other.",
                ],
            },
            {
                "id": "survival",
                "heading": "Stories about surviving a world that does not care",
                "paragraphs": [
                    "Scavengers Reign and Citizen Sleeper are about survival, but at very different scales. Scavengers Reign strands a freighter crew on a lush, dangerous planet whose life forms follow their own logic. Every plant and creature feels like a puzzle, and the series is as fascinated as it is frightening. It ran for a single season, so it is a complete, contained watch.",
                    "Citizen Sleeper is quieter and more political. You play an escaped worker in an artificial body on a run-down space station, and each day you roll dice to decide what you can do. Survival depends on relationships, favors, and choices about whose problems to take on. Economic precarity stops being an idea and becomes something you feel each time you run short.",
                ],
            },
            {
                "id": "choosing-a-future",
                "heading": "Which future suits tonight",
                "paragraphs": [
                    "If you are new to science fiction, or watching with someone who is, start with Arrival. It is accessible, moving, and leaves plenty to discuss. If you love alien worlds and do not mind intensity, Scavengers Reign offers some of the most imaginative creature design in recent television.",
                    "Choose Citizen Sleeper if you want to participate in a story and enjoy reading. Choose The Left Hand of Darkness if you want a classic that is worth reading slowly and still feels relevant. You don't need to take on more than one. Any of them is plenty for an evening or a week.",
                ],
            },
        ],
        "item_notes": {
            "arrival": [
                "Arrival follows a linguist recruited when mysterious ships appear around the world. Her task is to understand the visitors well enough to learn why they came. The film, adapted from a short story by Ted Chiang, treats language as both a puzzle and a way of seeing.",
                "Avoid reading about it before watching. Its structure is part of its effect, and it is best experienced fresh. It is the easiest pick in this trail to share with someone who does not usually choose science fiction.",
            ],
            "scavengers-reign": [
                "Scavengers Reign follows survivors of a damaged freighter stranded on a beautiful but hostile planet as they try to stay alive until they can escape. Its creatures and ecosystems are endlessly inventive, and the series often lets you watch them work without explanation.",
                "This is adult animation in every sense, with body horror and frequent danger. It pairs well with Outer Wilds in the Beautifully strange worlds trail. Both are curious about how an alien world fits together, but the stakes here are much higher.",
            ],
            "citizen-sleeper": [
                "In Citizen Sleeper, you play a person whose mind has been placed in an artificial body owned by a corporation. Having escaped to a space station on the edge of society, you need work, food, and friends to keep going. Each day you roll dice and decide how to spend them.",
                "The game is mostly reading and choosing, with no combat or reflex challenges. That makes it approachable for people who do not usually play games, as long as they enjoy narrative. Let yourself help people even when it is inefficient; the game is about those choices.",
            ],
            "left-hand-darkness": [
                "The Left Hand of Darkness follows Genly Ai, an envoy sent to a cold planet whose people have no fixed gender. As he navigates its politics, he struggles to understand them, and his misunderstandings become part of the story. It is one of the most celebrated science-fiction novels ever written.",
                "Read it slowly and give the opening chapters time. Its long journey across the ice is often remembered as the heart of the book. Its narrator's dated assumptions are deliberate, and noticing them is part of reading it.",
            ],
        },
        "related": [
            {"slug": "beautifully-strange-worlds", "reason": "For more worlds that you understand by living alongside their rules."},
            {"slug": "clever-mysteries", "reason": "For more stories where close attention and careful reasoning pay off."},
        ],
        "sources": [
            {"key": "arrival", "label": "Paramount Movies: Arrival", "url": "https://www.paramountmovies.com/movies/arrival", "supports": "Studio's official film page."},
            {"key": "scavengers-reign", "label": "Warner Bros. Discovery: Scavengers Reign series order", "url": "https://press.wbd.com/ca/media-release/hbo-max/hbo-max-orders-adult-animated-sci-fi-drama-scavengers-reign-series", "supports": "Official announcement and premise of the stranded freighter crew on a hostile planet."},
            {"key": "citizen-sleeper", "label": "Fellow Traveller: Citizen Sleeper", "url": "https://www.fellowtraveller.games/citizen-sleeper", "supports": "Publisher's page describing the narrative game and its space-station setting."},
            {"key": "left-hand-darkness", "label": "Ursula K. Le Guin: The Left Hand of Darkness", "url": "https://www.ursulakleguin.com/the-left-hand-of-darkness", "supports": "Author's book page identifying the novel and its place in her work."},
        ],
    },
}
