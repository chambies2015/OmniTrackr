"""Monthly challenges: one small, opt-in challenge a month, e.g. "finish one pick from the October edition".

Progress is never stored. It is counted from the same finishes Year in Review
and yearly goals use (journal "finished" entries and completion moments), only
for the calendar month (UTC), so editing the library keeps it right and
finishes from before a member joined still count.

A member's entry row records only that they took the challenge, when they
completed it, whether they dismissed the celebration, and an optional share
token. Public pages show the editorial guide and aggregate counts, never
anyone's titles.
"""
from __future__ import annotations

import os
import secrets
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import diary, models, title_origins, title_pages, year_in_review
from .discover_catalog import MONTHLY_EDITIONS, published_editions

SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
# Aggregate counts appear on public pages only once they stop pointing at individuals.
MIN_PUBLIC_COUNT = 3
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]
FORMAT_NOUNS = {
    "movies": ("movie", "movies"), "tv-shows": ("TV show", "TV shows"), "anime": ("anime", "anime"),
    "video-games": ("game", "games"), "music": ("album", "albums"), "books": ("book", "books"),
    "manga": ("manga series", "manga series"),
    "podcasts": ("podcast", "podcasts"),
    "audiobooks": ("audiobook", "audiobooks"),
}

# Curated challenges, keyed by month ("YYYY-MM"). Step kinds:
#   total       finish ``count`` titles this month
#   formats     finish titles in ``count`` different formats
#   reflect     rate or write a takeaway/note for ``count`` finishes
#   edition     finish one pick from the Discover monthly edition ``edition``
#   before      finish one title released before ``year``
#   category    finish ``count`` titles of one format (``category``)
#   waiting     finish ``count`` titles that were already in the library before the month began
#   revisit     revisit ``count`` titles: a journal "Revisited" entry, or another finish of a title finished before
#   stretch     finish ``count`` titles in a format the member had finished fewer than ``under`` titles in before
#               the month began; if every format already has that many, their least-finished format counts
#   recommended finish ``count`` titles that the member says a person recommended (Why I added it: a friend on
#               OmniTrackr or someone they know), whenever they said it
#   birthday    finish ``count`` titles that turn a round number in the month's year: released a whole number of
#               ``every`` years before it (2017, 2007, 1997... in 2027), going by the year saved on the title
#   day         finish ``count`` titles less than ``hours`` hours apart: a day's worth of finishes, measured in
#               hours so it works the same in every time zone and across midnight
# A challenge with ``"revisits_count": True`` also counts a logged revisit as a finish for its other steps.
CHALLENGES: dict[str, dict] = {
    "2026-10": {
        "name": "Stay with the strange",
        "tagline": "Three small steps through a month of quiet ghosts, unexplained signals and stories that refuse to resolve.",
        "published": "2026-10-10",
        "edition": "october-2026",
        "intro": [
            "October tends to arrive with a checklist: the horror marathon, the scariest-ever list, the film everyone says you must see before Halloween. This challenge asks for something gentler. It shares an idea with this month's Discover edition: a story can unsettle you without explaining itself, and the strangeness that stays with you longest is often the low-key kind.",
            "There are three steps. None of them requires you to watch anything frightening, and none of them depends on a particular streaming service. You can finish the whole thing with one film, one album and a sentence you write afterwards, or you can spread it across a book, a game and a long weekend of television. Anything you mark finished in October counts, including things you finished before you joined.",
        ],
        "steps": [
            {"kind": "edition", "edition": "october-2026",
             "label": "Finish one pick from the October edition",
             "detail": "The October edition picks six works across six formats, from David Lowery's A Ghost Story (one quiet evening) to Shirley Jackson's The Haunting of Hill House (a short novel best read slowly). Choose by the time you have, not by reputation. If you have already finished one of them this month, this step is done."},
            {"kind": "formats", "count": 2,
             "label": "Finish titles in two different formats",
             "detail": "Pair your pick with something in another medium: a film and an album, a book and an anime episode arc, a game and a season of television. Moving between formats is the fastest way to notice what each one does well. Mushi-Shi's self-contained episodes, for example, sit beside Ghosteen's long, unbroken songs in a way that makes both feel slower and stranger."},
            {"kind": "reflect", "count": 1,
             "label": "Rate it or jot a takeaway",
             "detail": "When you mark something finished, OmniTrackr offers a rating and a one-line takeaway. Use either once this month. A takeaway does not need to be clever. \"I kept thinking about the house after I closed the book\" will tell you more next year than a star count, and it stays private unless you choose to publish a review."},
        ],
        "reflection": "When a story leaves something unresolved, notice whether you lean in or reach for an explanation. Neither is wrong, and knowing which one you are this month makes your next pick easier.",
    },
    "2026-11": {
        "name": "The long way round",
        "tagline": "Slow down with something older, something on paper and a short run of titles you choose yourself.",
        "published": "2026-10-10",
        "edition": "november-2026",
        "intro": [
            "November is the month when evenings get long and recommendations get loud. Every service is pushing the newest release, and most best-of-the-year lists are already being drafted. This challenge pulls in the other direction. It asks you to finish something that has been around for a while, to spend some of your time with a book, and to keep a small, honest count of what you actually finished.",
            "Older works are not homework. A film from the 1970s or a game from the 1990s often moves at a different pace, trusts its audience with longer silences or leaves its rough edges in place. Coming back to the present afterwards tends to make newer work easier to judge. Anything you mark finished in November counts, whenever you joined.",
        ],
        "steps": [
            {"kind": "before", "year": 2000,
             "label": "Finish one title released before 2000",
             "detail": "Any format counts: a classic film, an album you know only from samples, a novel from your parents' shelf or a game you never had the console for. Pick something you are curious about, even if it isn't the one you feel you ought to have seen. The release year comes from the title in your library, so check that it is filled in."},
            {"kind": "category", "category": "books", "count": 1,
             "label": "Finish one book",
             "detail": "Short books count as much as long ones. A novella, a graphic novel, a poetry collection or a short essay collection all fit a busy month. If you are between books, the Discover guides include several that can be read in a weekend."},
            {"kind": "total", "count": 3,
             "label": "Finish three titles this month",
             "detail": "Three is a low bar on purpose. It leaves room for one long game or series alongside the two steps above, and most members reach it without changing their habits. Nobody is racing."},
        ],
        "reflection": "Which of this month's finishes felt most like its own time, and which felt like it could have been made last year?",
    },
    "2026-12": {
        "name": "Close the year kindly",
        "tagline": "Finish a few things across formats and leave notes your January self will thank you for.",
        "published": "2026-10-10",
        # The December edition (out December 1) is written around this challenge's four titles in three formats.
        "edition": "december-2026",
        "intro": [
            "December is when Year in Review fills in, and it is tempting to treat the last month as a sprint to pad the numbers. This challenge is designed for the opposite mood. It asks you to finish a handful of things across more than one format and to leave a short note on a couple of them, so that the year ends with a record you will actually want to reread.",
            "Holiday breaks are good for long games and box sets, and short gaps between plans are good for albums and films. Mix them however suits your month. Anything you mark finished in December counts, whenever you joined.",
        ],
        "steps": [
            {"kind": "total", "count": 4,
             "label": "Finish four titles this month",
             "detail": "Four is about one a week. If a long game or a thick book is taking most of your time, keep going with it and fit a couple of albums or films around it."},
            {"kind": "formats", "count": 3,
             "label": "Use at least three formats",
             "detail": "Three of the nine formats OmniTrackr tracks is enough to make your Year in Review show a fuller picture of what you enjoyed, and it is a good excuse to return to a format you drifted away from earlier in the year."},
            {"kind": "reflect", "count": 2,
             "label": "Rate or note two of them",
             "detail": "A rating and a takeaway are the details you will forget first. Add them now and your recap will say why you liked something, and your next recommendations will be better for it."},
        ],
        "reflection": "Which finish this month would you hand to a friend in January, and what would you tell them about it?",
    },
    "2027-01": {
        "name": "First things first",
        "tagline": "Start the year with the first part of something that continues this winter, one title from your backlog and the year's first note.",
        "published": "2027-01-01",
        # The January edition (out January 1) has nine picks, one per format, each the start of a January release.
        "edition": "january-2027",
        "intro": [
            "January is when the new seasons start. In the next few weeks Neuromancer arrives on Apple TV, Children of Blood and Bone opens in cinemas, CHVRCHES release their first album in more than five years and Samus Aran gets a new 2D Metroid game. This challenge, like the January edition it pairs with, asks you to go back to where one of those things started before the new one arrives. It also asks you to finish one title that has been sitting in your library, and to write down what you thought of something, so that the year's record starts with a sentence as well as a number.",
            "If you made a pledge in the 2027 New Year challenge, every finish here counts toward it too. The pledge is the target for the whole year; this is its first month, at a size you can finish by the 31st. Anything you mark finished in January counts, whenever you joined.",
        ],
        "steps": [
            {"kind": "edition", "edition": "january-2027",
             "label": "Finish one pick from the January edition",
             "detail": "The January edition has nine picks, one in each format OmniTrackr tracks, and each is the start of something that continues this winter: Neuromancer before the Apple TV series on January 22, Metroid Dread before Metroid Ravenous on January 28, the first CHVRCHES album before their fifth on January 22. The shortest is an album of under an hour and the longest an audiobook of almost eighteen. Finish any one of them in January and this step is done."},
            {"kind": "waiting", "count": 1,
             "label": "Finish one title that was already in your library",
             "detail": "Anything that was in your library before January 1 counts, whether you saved it last week or three years ago. Most libraries have a few titles that were saved and never started, or started and left at episode four. Pick the one you feel worst about and finish it. A title you add and finish in January still counts toward the other two steps, just not this one. If one of the edition's picks has been waiting in your library, it can do both."},
            {"kind": "reflect", "count": 1,
             "label": "Leave the year's first rating or takeaway",
             "detail": "Rate a January finish or write a line about it when you mark it finished. Next December your Year in Review will be built from what you record now, and a note written the week you finished something says more than a score added from memory eleven months later. Takeaways stay private unless you publish a review."},
        ],
        "reflection": "If you went back to an original this month, did knowing a new version was coming change how you read, watched or played it?",
    },
    "2027-02": {
        "name": "Love in every form",
        "tagline": "Finish one of February's nine love stories, go back to something you already love and write down why.",
        "published": "2027-02-01",
        # The February edition (out February 1) has nine love stories, one per format, no two of the same kind.
        "edition": "february-2027",
        # A rewatch or reread logged in the journal counts as a finish for every step this month.
        "revisits_count": True,
        "intro": [
            "February has Valentine's Day in the middle of it, and for two weeks every service recommends the same handful of romantic comedies. This challenge, and the February edition it pairs with, take a wider view of what a love story can be. The edition's nine picks include a first love that never happened, a couple who decide to have a baby after six days, two young women who share a name and an apartment, and marriages talked through in a therapist's office. The challenge asks you to finish one of them, to go back to something you have loved for years, and to write a line about why you love something, which is the part most of us skip.",
            "February is also the shortest month, so the steps are small. A rewatch, reread or replay that you log in your Journal counts as a finish for every step this month, so one evening with an old favourite and a sentence afterwards can cover two of the three. Anything you finish or revisit in February counts, whenever you joined.",
        ],
        "steps": [
            {"kind": "edition", "edition": "february-2027",
             "label": "Finish one pick from the February edition",
             "detail": "The February edition has nine love stories, one in each format OmniTrackr tracks. Past Lives is a single evening at 106 minutes, and To the Moon takes most players about four hours. Nana runs to twenty-one volumes and 69 Love Songs to almost three hours, so start those in the first week. If you have seen or read one of the nine before, a rewatch or reread you log this month counts too."},
            {"kind": "revisit", "count": 1,
             "label": "Go back to something you love",
             "detail": "Rewatch a film you know by heart, reread a book you keep lending out, replay a game or put an old album on from the first track. Then log it in your Journal as Revisited: the Log a revisit button on the challenge card opens the Journal with that already chosen. Logging a second finish of something you finished before counts as well, the same way your diary marks it as a rewatch or reread. If the title isn't in your library yet, add it first."},
            {"kind": "reflect", "count": 1,
             "label": "Write down what you love about one",
             "detail": "Rate one of this month's finishes or revisits, or add a line about it. A takeaway on the finish screen counts, and so does a private note when you log a revisit. Most libraries are full of scores with nothing to say what earned them, and next February the sentence is the part you will want to read again. Notes and takeaways stay private unless you publish a review."},
        ],
        "reflection": "Which of this month's love stories would you not have called a love story before you finished it?",
    },
    "2027-03": {
        "name": "Nine ways in",
        "tagline": "Finish one of March's nine ways in, try a format you hardly ever finish and say whether you'd go back.",
        "published": "2027-03-01",
        # The March edition (out March 1) has nine picks, one per format, each an easy first one for a newcomer.
        "edition": "march-2027",
        "intro": [
            "Most libraries lean on one or two formats. Plenty of members log a film every week and have never finished a podcast, and plenty of readers have not played a game since school. It is rarely a decision. Usually nobody suggested where to start, and the famous titles in a format are often the long, demanding ones its fans love most. This challenge, and the March edition it pairs with, offer nine places to start: one pick in each format OmniTrackr tracks, each chosen because it asks almost nothing of someone new. The shortest is a 38-minute album and the longest an audiobook of under nine hours.",
            "The clocks go forward on March 14 in most of North America and on March 28 in the UK and Europe, and lighter evenings are a good time to try something unfamiliar. The middle step asks you to finish something in a format you hardly ever finish, and the challenge card on your home screen lists the formats that count for you. Anything you finish in March counts, whenever you joined.",
        ],
        "steps": [
            {"kind": "edition", "edition": "march-2027",
             "label": "Finish one pick from the March edition",
             "detail": "The March edition has nine picks, one in each format, and each is the one we would hand to someone trying that format for the first time: a phone game you can finish in an evening, a podcast that got millions of people listening to podcasts, an audiobook read by the man who lived it. Sherlock Jr. is 45 minutes and Glenn Gould's Goldberg Variations under 40. Finish any one of the nine in March and this step is done."},
            {"kind": "stretch", "count": 1, "under": 3,
             "label": "Finish something in a format you hardly ever finish",
             "detail": "Any format in which you had finished fewer than three titles before March 1 counts, so if you have never finished a manga, a podcast season or a game, this is the step for it. The challenge card lists the formats that count for you. If you have already finished three or more in every format, your least-finished format counts instead. It doesn't have to be one of the edition's picks, but if one of them is in a format that counts for you, finishing it does this step and the first one at once."},
            {"kind": "reflect", "count": 1,
             "label": "Say whether you'd go back",
             "detail": "Rate one of this month's finishes or add a line about it when you mark it finished. If it was your first in a format, the useful thing to write down is whether you would try another, and what would make you: something shorter, a different genre, a friend's suggestion. Takeaways stay private unless you publish a review."},
        ],
        "reflection": "Which format would you go back to after this month, and what would you hand to a friend trying it for the first time?",
    },
    "2027-04": {
        "name": "Pass it on",
        "tagline": "Finish one of April's nine word-of-mouth hits, finish something a person recommended to you and write the line you'd say when you pass it on.",
        "published": "2027-04-01",
        # The April edition (out April 1) has nine picks, one per format, each spread mostly by people telling each other.
        "edition": "april-2027",
        "intro": [
            "April starts with a day for not believing what anyone tells you. This challenge, and the April edition it pairs with, are about the recommendations worth believing. Most of what people love best reaches them the same way: a friend, a sibling or someone at work says you have to try this, and keeps asking until you do. The edition's nine picks all found their audiences like that. A Detroit singer-songwriter's album sold an estimated half a million copies in South Africa without his knowing, a Canadian sitcom was found on Netflix three seasons in, and a game made almost entirely by one person went from a small Kickstarter to at least five million copies. The challenge asks you to finish one of the nine, to finish something a person recommended to you, and to write down the line you would say when you pass something on.",
            "The middle step counts any April finish whose Why I added it names a friend or someone you know. Most titles don't say yet, so the challenge card on your home screen lists your April finishes that don't, and a tap on one opens the box to say who it was. Titles you add from a friend's recommendation or from the friends feed already say so. Anything you finish in April counts, whenever you joined.",
        ],
        "steps": [
            {"kind": "edition", "edition": "april-2027",
             "label": "Finish one pick from the April edition",
             "detail": "The April edition has nine picks, one in each format OmniTrackr tracks, and each reached most of its audience because people told each other about it. The Velvet Underground & Nico is about 48 minutes and Searching for Sugar Man 85, so either fits an evening. Schitt's Creek is eighty episodes and Dungeon Crawler Carl a 13-hour audiobook, so start those early. Finish any one of the nine in April and this step is done."},
            {"kind": "recommended", "count": 1,
             "label": "Finish something someone recommended to you",
             "detail": "Any title you finish in April counts if a person recommended it to you: a friend on OmniTrackr or someone you know, named under Why I added it on the title. You can say who after you finish, and the challenge card lists your April finishes that don't say yet. An article, a video or something you came across yourself doesn't count for this step. If a friend has been telling you to watch, read or play something for years, this is the month to finish it, and if someone recommended one of the edition's picks to you, finishing it does this step and the first one at once."},
            {"kind": "reflect", "count": 1,
             "label": "Write the line you'd pass on",
             "detail": "Rate one of this month's finishes or add a line about it when you mark it finished. Write it the way you would say it to a friend: who it is for, and what they should know before they start. \"Keep going until season two\" has probably got more people through Schitt's Creek than any review. Takeaways stay private unless you publish a review."},
        ],
        "reflection": "Who recommended the best thing you finished this month, and have you told them you finished it?",
    },
    "2027-05": {
        "name": "Many happy returns",
        "tagline": "Finish one of May's nine birthday picks, finish something else that turns a round number this year and say how it has aged.",
        "published": "2027-05-01",
        # The May edition (out May 1) has nine picks, one per format and one per decade from 1937 to 2017.
        "edition": "may-2027",
        # Birthdays are a reason to go back to things, so a logged rewatch or reread counts as a finish this month.
        "revisits_count": True,
        "intro": [
            "Star Wars turns fifty on May 25, and it has plenty of company. Everything released in a year ending in seven has a round birthday in 2027: Of Mice and Men is ninety, The Plague eighty, JoJo's Bizarre Adventure forty and Castlevania: Symphony of the Night thirty. An anniversary is an arbitrary reason to go back to something, but it works. A restoration comes out, a cinema shows the old version, and somebody asks whether you have ever actually seen it. This challenge, and the May edition it pairs with, take the excuse. The edition has nine picks, one in each format and one from each decade between 1937 and 2017. The challenge asks you to finish one of them, to finish something else that turns 10, 20, 30 or more this year, and to write down how it has aged.",
            "The middle step goes by the release year saved on the title in your library, so anything from 2017, 2007, 1997, 1987 and every ten years before counts, and the challenge card on your home screen names a few titles already in your library that do. Plenty of these will be things you have seen before, so a rewatch, reread or replay that you log in your Journal counts as a finish for every step this month. Anything you finish or revisit in May counts, whenever you joined.",
        ],
        "steps": [
            {"kind": "edition", "edition": "may-2027",
             "label": "Finish one pick from the May edition",
             "detail": "The May edition has nine picks, one in each format OmniTrackr tracks, each with a round birthday this year, from Ear Hustle at ten to Of Mice and Men at ninety. The \"Chirping\" Crickets is 26 minutes and Star Wars 121, so either fits an evening. Den-noh Coil is 26 episodes and The Prisoner 17, so start those early. If you have seen or read one of the nine before, a revisit you log in your Journal this month counts too."},
            {"kind": "birthday", "count": 1, "every": 10,
             "label": "Finish something that turns 10, 20, 30 or more this year",
             "detail": "Anything released in a year ending in seven counts: 2017, 2007, 1997, 1987, 1977 and so on back. The step goes by the year saved on the title in your library, so check it is filled in, because a title without a year can't count. The challenge card lists a few titles already in your library that qualify. Every pick in the May edition qualifies too, so finishing one with its year saved does this step and the first one at once."},
            {"kind": "reflect", "count": 1,
             "label": "Say how it has aged",
             "detail": "Rate one of this month's finishes or revisits, or add a line about it. If you went back to something, write down what changed: what you noticed this time, what you had remembered wrong, whether it is better or worse than you thought the first time. A takeaway on the finish screen counts, and so does a private note when you log a revisit. Notes and takeaways stay private unless you publish a review."},
        ],
        "reflection": "Which of this month's finishes would you still want to go back to in another ten years?",
    },
    "2027-06": {
        "name": "All in a day",
        "tagline": "Finish one of June's nine stories that happen inside a single day, finish two things within a day of each other and write down where the day went.",
        "published": "2027-06-01",
        # The June edition (out June 1) has nine picks, one per format, each set within one day or night.
        "edition": "june-2027",
        "intro": [
            "The longest day of the year north of the equator falls on Monday, June 21, and a surprising number of stories are set on single days in June. Clarissa Dalloway goes out to buy flowers on a morning in the middle of June 1923. Cléo walks around Paris for an hour and a half on the afternoon of June 21, waiting for a test result. Katie Greenbriar comes home on June 7, 1995, to find the house empty. This challenge, and the June edition it pairs with, are about stories that fit inside one day. The edition has nine of them, one in each format, from the thirteen minutes it took Apollo 11 to land on the Moon to the twenty-four hours of the first season of 24. The challenge asks you to finish one of the nine, to finish two things within a day of each other, and to write down when and where you finished something.",
            "The middle step counts any two finishes less than 24 hours apart, so it works the same in every time zone: a film in the afternoon and an album that evening, or a book you finish late at night and a game the next day. Once you have finished one thing, the challenge card on your home screen says how long you have to finish the next. Anything you finish in June counts, whenever you joined.",
        ],
        "steps": [
            {"kind": "edition", "edition": "june-2027",
             "label": "Finish one pick from the June edition",
             "detail": "The June edition has nine picks, one in each format OmniTrackr tracks, and each one takes place within a single day or night. Days of Future Passed is about 41 minutes and Cléo from 5 to 7 is 90, so either fits an evening, and Gone Home takes most players two or three hours. The first season of 24 is twenty-four episodes, about seventeen hours, so start that one early. Finish any one of the nine in June and this step is done."},
            {"kind": "day", "count": 2, "hours": 24,
             "label": "Finish two things within a day",
             "detail": "Any two titles you finish less than 24 hours apart count, in any formats. The step goes by hours, so it works the same in every time zone and doesn't care about midnight. A short film and an album fit into one evening, and a book you finish over breakfast pairs with a game you finish after dinner. Once you have finished one thing, the challenge card shows when the next one needs to be done by, in your own time. If one of the pair is from the June edition, it does the first step as well."},
            {"kind": "reflect", "count": 1,
             "label": "Write down where the day went",
             "detail": "Rate one of this month's finishes or add a line about it when you mark it finished. This month, try writing down when and where you were: on the train at eight in the morning, on the sofa at one at night, outside on the longest evening of the year. A year from now that line will bring the day back better than a score will. Takeaways stay private unless you publish a review."},
        ],
        "reflection": "Which of this month's stories felt longer than the time it covered, and which felt shorter?",
    },
}

# Used for any month without a curated challenge, so the dashboard card never breaks.
FALLBACK = {
    "name": "A month of small finishes",
    "tagline": "Three easy steps that fit around a normal month.",
    "published": None,
    "intro": ["Finish a few titles you are already in the middle of, try more than one format and leave a note on one of them. Anything you mark finished this month counts."],
    "steps": [
        {"kind": "total", "count": 3, "label": "Finish three titles this month",
         "detail": "Anything in your library counts."},
        {"kind": "formats", "count": 2, "label": "Finish titles in two different formats",
         "detail": "A film and an album, a book and a game: any two formats."},
        {"kind": "reflect", "count": 1, "label": "Rate it or jot a takeaway",
         "detail": "Add a rating or a one-line takeaway when you mark something finished."},
    ],
    "reflection": "",
}


# ---------------------------------------------------------------- months

def month_key(today: Optional[date] = None) -> str:
    today = today or datetime.utcnow().date()
    return f"{today.year:04d}-{today.month:02d}"


def slug_for(month: str) -> str:
    year, number = month.split("-")
    return f"{MONTH_NAMES[int(number) - 1].lower()}-{year}"


def month_for_slug(slug: str) -> Optional[str]:
    """'october-2026' -> '2026-10'; None for anything else."""
    if not isinstance(slug, str) or len(slug) > 20 or "-" not in slug:
        return None
    name, _, year = slug.rpartition("-")
    if not year.isdigit() or len(year) != 4 or name.capitalize() not in MONTH_NAMES:
        return None
    return f"{year}-{MONTH_NAMES.index(name.capitalize()) + 1:02d}"


def month_label(month: str) -> str:
    year, number = month.split("-")
    return f"{MONTH_NAMES[int(number) - 1]} {year}"


def month_bounds(month: str) -> tuple[datetime, datetime]:
    year, number = (int(part) for part in month.split("-"))
    start = datetime(year, number, 1)
    end = datetime(year + 1, 1, 1) if number == 12 else datetime(year, number + 1, 1)
    return start, end


def days_left(month: str, today: Optional[date] = None) -> int:
    today = today or datetime.utcnow().date()
    year, number = (int(part) for part in month.split("-"))
    last = date(year, number, monthrange(year, number)[1])
    return max(0, (last - today).days + 1)


def challenge_for(month: str) -> dict:
    """The curated challenge for a month, or the generic fallback."""
    return CHALLENGES.get(month, FALLBACK)


def is_curated(month: str) -> bool:
    return month in CHALLENGES


def public_months(today: Optional[date] = None) -> list[str]:
    """Curated challenges that have started, newest first. Future months stay unpublished."""
    current = month_key(today)
    return sorted((month for month in CHALLENGES if month <= current), reverse=True)


# ---------------------------------------------------------------- progress

def _finishes(db: Session, user_id: int, month: str) -> list[dict]:
    """Titles finished in the month; each title counts once, however many times it was logged."""
    start, end = month_bounds(month)
    actions = diary.DIARY_ACTIONS if challenge_for(month).get("revisits_count") else ("completed",)
    entries = db.query(models.ActivityEntry).filter(
        models.ActivityEntry.user_id == user_id,
        models.ActivityEntry.action.in_(actions),
        models.ActivityEntry.occurred_at >= start,
        models.ActivityEntry.occurred_at < end,
    ).order_by(models.ActivityEntry.occurred_at.asc(), models.ActivityEntry.id.asc()).all()
    moments = db.query(models.CompletionMoment).filter(
        models.CompletionMoment.user_id == user_id,
        models.CompletionMoment.completed_at >= start,
        models.CompletionMoment.completed_at < end,
    ).order_by(models.CompletionMoment.completed_at.asc()).all()
    finished: dict[tuple, dict] = {}
    for row, item_id, reflected in (
        *((entry, entry.item_id, entry.rating is not None or bool((entry.note or "").strip())) for entry in entries),
        *((moment, moment.item_id, moment.rating is not None or bool((moment.takeaway or "").strip())) for moment in moments),
    ):
        if row.category not in FORMAT_NOUNS:
            continue
        key = year_in_review._title_key(row.category, item_id, row.title)
        found = finished.setdefault(key, {"category": row.category, "item_id": item_id,
                                          "title": row.title or "", "reflected": False, "at": None, "times": []})
        found["reflected"] = found["reflected"] or reflected
        when = getattr(row, "occurred_at", None) or getattr(row, "completed_at", None)
        if when is not None:
            found["times"].append(when)
            if found["at"] is None or when > found["at"]:
                found["at"] = when
        if found["item_id"] is None:
            found["item_id"] = item_id
    removed = {key: row["times"] for key, row in finished.items() if isinstance(key[1], str)}
    folded = year_in_review.fold_deleted_copies(finished)
    # A removed copy folded into the live one keeps its finish times (day steps read every one).
    for key, times in removed.items():
        if key in folded:
            continue
        for live_key, row in folded.items():
            if not isinstance(live_key[1], str) and (row["category"], year_in_review._plain_title(row["title"])) == key:
                row["times"].extend(times)
                break
    return list(folded.values())


def _release_years(db: Session, finishes: list[dict]) -> dict[tuple[str, int], Optional[int]]:
    """Release years of the finished titles: one query per format, not one per title.

    The card used to look each title up on its own, so a member with 100 finishes this
    month cost 100 queries on every home screen load. Years follow title_pages.item_year.
    """
    wanted: dict[str, set[int]] = {}
    for finish in finishes:
        kind = title_pages.LIBRARY_TO_KIND.get(finish["category"])
        if kind is not None and finish["item_id"] is not None:
            wanted.setdefault(kind, set()).add(finish["item_id"])
    years: dict[tuple[str, int], Optional[int]] = {}
    for kind, ids in wanted.items():
        model = title_pages.KINDS[kind][0]
        column = model.release_date if kind == "game" else getattr(model, "year", None)
        if column is None:
            continue
        ordered = sorted(ids)
        for start in range(0, len(ordered), 500):
            for item_id, value in db.query(model.id, column).filter(model.id.in_(ordered[start:start + 500])):
                if kind == "game":
                    years[(kind, item_id)] = value.year if value else None
                else:
                    years[(kind, item_id)] = value or None
    return years


def _waiting_count(db: Session, user_id: int, month: str, finishes: list[dict]) -> int:
    """Finishes of titles that were in the library before the month began: one query per format.

    A row without ``added_at`` predates the column, so it was waiting too. A title added and
    finished in the same month does not count, and neither does a finish whose row was deleted.
    """
    start, _ = month_bounds(month)
    wanted: dict[str, set[int]] = {}
    for finish in finishes:
        kind = title_pages.LIBRARY_TO_KIND.get(finish["category"])
        if kind is not None and finish["item_id"] is not None:
            wanted.setdefault(kind, set()).add(finish["item_id"])
    count = 0
    for kind, ids in wanted.items():
        model = title_pages.KINDS[kind][0]
        ordered = sorted(ids)
        for first in range(0, len(ordered), 500):
            count += db.query(func.count(model.id)).filter(
                model.user_id == user_id, model.id.in_(ordered[first:first + 500]),
                (model.added_at.is_(None)) | (model.added_at < start),
            ).scalar() or 0
    return count


def _revisit_count(db: Session, user_id: int, month: str) -> int:
    """Titles revisited in the month, counted the way the diary labels a rewatch, reread, replay or relisten.

    A journal "Revisited" entry counts, and so does a logged finish of a title that already had
    an earlier finish or revisit (diary.visit_numbers). Each title counts once however often it
    was revisited.
    """
    start, end = month_bounds(month)
    entries = db.query(models.ActivityEntry).filter(
        models.ActivityEntry.user_id == user_id,
        models.ActivityEntry.action.in_(diary.DIARY_ACTIONS),
        models.ActivityEntry.category.in_(tuple(FORMAT_NOUNS)),
        models.ActivityEntry.occurred_at >= start,
        models.ActivityEntry.occurred_at < end,
    ).all()
    if not entries:
        return 0
    visits = diary.visit_numbers(db, user_id, entries)
    return len({diary._key(entry.category, entry.title) for entry in entries
                if diary.is_repeat(entry, visits.get(entry.id, 1))})


# Words for each format in the card's "Counts for you" line.
STRETCH_LABELS = {
    "movies": "movies", "tv-shows": "TV", "anime": "anime", "video-games": "games", "music": "albums",
    "books": "books", "manga": "manga", "podcasts": "podcasts", "audiobooks": "audiobooks",
}


def _earlier_finishes(db: Session, user_id: int, month: str, finishes: list[dict], cap: Optional[int]) -> dict[str, int]:
    """Titles of each format the member had finished before the month, counted up to ``cap`` (None: no cap).

    A library row marked finished counts unless its finish is one of this month's; journal and
    completion-moment finishes from before the month count too, which keeps titles since removed
    from the library. Each title counts once. Capped counts read at most ``cap`` rows per format,
    so a large library costs nine short queries.
    """
    start, _ = month_bounds(month)
    this_month: dict[str, set[int]] = {}
    for finish in finishes:
        if finish["item_id"] is not None:
            this_month.setdefault(finish["category"], set()).add(finish["item_id"])
    counts: dict[str, int] = {}
    seen: dict[str, set] = {}
    for kind, (model, _, library, _, _) in title_pages.KINDS.items():
        query = db.query(model.id).filter(model.user_id == user_id,
                                          getattr(model, title_pages.COMPLETE_FIELD[kind]).is_(True))
        if this_month.get(library):
            query = query.filter(~model.id.in_(sorted(this_month[library])))
        if cap is None:
            counts[library] = query.count()
        else:
            seen[library] = {row_id for (row_id,) in query.limit(cap)}
    if cap is None:
        return counts
    quiet = [category for category, keys in seen.items() if len(keys) < cap]
    if quiet:
        logged = db.query(models.ActivityEntry.category, models.ActivityEntry.item_id, models.ActivityEntry.title).filter(
            models.ActivityEntry.user_id == user_id,
            models.ActivityEntry.action.in_(diary.DIARY_ACTIONS),
            models.ActivityEntry.category.in_(quiet),
            models.ActivityEntry.occurred_at < start,
        ).distinct().limit(500).all()
        moments = db.query(models.CompletionMoment.category, models.CompletionMoment.item_id, models.CompletionMoment.title).filter(
            models.CompletionMoment.user_id == user_id,
            models.CompletionMoment.category.in_(quiet),
            models.CompletionMoment.completed_at < start,
        ).distinct().limit(500).all()
        for category, item_id, title in (*logged, *moments):
            # A removed title loses its item_id (journal) or gets a negative one (moments): key it by name.
            seen[category].add(item_id if item_id is not None and item_id > 0 else year_in_review._plain_title(title))
    return {category: min(len(keys), cap) for category, keys in seen.items()}


def stretch_formats(db: Session, user_id: int, month: str, finishes: list[dict], under: int) -> list[str]:
    """Formats that count for a stretch step, in library order: fewer than ``under`` earlier finishes,
    or, when every format has that many, the least-finished ones."""
    counts = _earlier_finishes(db, user_id, month, finishes, cap=under)
    quiet = [category for category in FORMAT_NOUNS if counts.get(category, 0) < under]
    if quiet:
        return quiet
    counts = _earlier_finishes(db, user_id, month, finishes, cap=None)
    fewest = min(counts.values())
    return [category for category in FORMAT_NOUNS if counts.get(category) == fewest]


def _origins(db: Session, user_id: int, finishes: list[dict]) -> dict[tuple[str, int], str]:
    """Where each finished library title came from (its Why I added it source), in one query per 500 titles."""
    wanted = {(finish["category"], finish["item_id"]) for finish in finishes
              if finish["item_id"] is not None and finish["item_id"] > 0}
    if not wanted:
        return {}
    ids = sorted({item_id for _, item_id in wanted})
    sources: dict[tuple[str, int], str] = {}
    for first in range(0, len(ids), 500):
        for category, item_id, source in db.query(
            models.TitleOrigin.category, models.TitleOrigin.item_id, models.TitleOrigin.source,
        ).filter(models.TitleOrigin.user_id == user_id, models.TitleOrigin.item_id.in_(ids[first:first + 500])):
            if (category, item_id) in wanted:
                sources[(category, item_id)] = source
    return sources


def _recommended_count(finishes: list[dict], sources: dict[tuple[str, int], str]) -> int:
    return sum(1 for finish in finishes if sources.get((finish["category"], finish["item_id"])) in title_origins.PEOPLE)


# How many of the month's finishes the card offers to credit, newest first.
UNSAID_LIMIT = 3


def unsaid_finishes(db: Session, user_id: int, finishes: list[dict], sources: dict[tuple[str, int], str],
                    limit: int = UNSAID_LIMIT) -> list[dict]:
    """This month's finishes that are still in the library and don't say where they came from yet.

    The card offers these so a member can say who recommended one without finding it on its shelf.
    Newest finish first; titles removed from the library are left out, since there is nothing to edit.
    """
    candidates = [finish for finish in finishes
                  if finish["item_id"] is not None and finish["item_id"] > 0
                  and (finish["category"], finish["item_id"]) not in sources
                  and finish["category"] in title_origins.LIBRARY]
    candidates.sort(key=lambda finish: finish.get("at") or datetime.min, reverse=True)
    candidates = candidates[:limit * 4]
    live: dict[str, set[int]] = {}
    for category in {finish["category"] for finish in candidates}:
        model = title_origins.LIBRARY[category][0]
        ids = sorted(finish["item_id"] for finish in candidates if finish["category"] == category)
        live[category] = {row_id for (row_id,) in db.query(model.id).filter(model.user_id == user_id, model.id.in_(ids))}
    unsaid = []
    for finish in candidates:
        if finish["item_id"] in live.get(finish["category"], ()):
            unsaid.append({"category": finish["category"], "id": finish["item_id"], "title": finish["title"]})
        if len(unsaid) >= limit:
            break
    return unsaid


# The oldest release year a birthday step looks for in a library (a 160th birthday in 2027).
BIRTHDAY_OLDEST = 1867
# How many not-yet-finished titles the card names under a birthday step.
TURNING_LIMIT = 3


def birthday_years(month: str, every: int = 10) -> list[int]:
    """Release years that turn a round number in the month's year, newest first: 2017, 2007, 1997... for 2027."""
    current = int(month[:4])
    return list(range(current - every, BIRTHDAY_OLDEST - 1, -every))


def _turns_round(year: Optional[int], month: str, every: int) -> bool:
    current = int(month[:4])
    return bool(year) and year < current and (current - year) % every == 0


def _birthday_count(db: Session, month: str, finishes: list[dict], every: int) -> int:
    """This month's finishes whose saved release year makes them 10, 20, 30... years old this year."""
    years = _release_years(db, finishes)
    return sum(1 for finish in finishes
               if _turns_round(years.get((title_pages.LIBRARY_TO_KIND.get(finish["category"]), finish["item_id"])),
                               month, every))


def turning_titles(db: Session, user_id: int, month: str, every: int = 10, limit: int = TURNING_LIMIT) -> list[dict]:
    """Titles in the member's library, not finished yet, that turn a round number this year.

    The card names these under a birthday step so a member can see what already counts. One short
    query per format; newest saves first. Each entry says how old the title turns.
    """
    years = birthday_years(month, every)
    if not years:
        return []
    current = int(month[:4])
    found = []
    for kind, (model, _, category, _, _) in title_pages.KINDS.items():
        column = title_pages._year_column(kind, model)
        if kind == "game":
            matches = or_(*(and_(column >= datetime(year, 1, 1), column < datetime(year + 1, 1, 1)) for year in years))
        else:
            matches = column.in_(years)
        # Postgres puts NULLs first in a descending sort, so rows from before added_at existed would
        # crowd out this year's saves; they go last, as they do in the merge below.
        rows = db.query(model.id, model.title, column, model.added_at).filter(
            model.user_id == user_id, getattr(model, title_pages.COMPLETE_FIELD[kind]).isnot(True), matches,
        ).order_by(model.added_at.desc().nullslast(), model.id.desc()).limit(limit).all()
        for item_id, title, value, added_at in rows:
            year = value.year if kind == "game" else value
            if not (title or "").strip() or not _turns_round(year, month, every):
                continue
            found.append({"category": category, "id": item_id, "title": title, "age": current - year,
                          "_added": added_at or datetime.min})
    found.sort(key=lambda entry: entry["_added"], reverse=True)
    return [{key: value for key, value in entry.items() if key != "_added"} for entry in found[:limit]]


# How many of the open window's finishes the card names under a day step.
DAY_TITLES_LIMIT = 3


def _iso(moment: datetime) -> str:
    return moment.replace(microsecond=0).isoformat() + "Z"


def day_progress(finishes: list[dict], month: str, hours: int = 24, target: int = 2,
                 now: Optional[datetime] = None) -> dict:
    """The most titles finished less than ``hours`` apart this month, and the window still open now.

    Every logged finish time counts (a title finished twice has two chances to pair), but each title
    counts once inside a window. "open" is the stretch that started with the earliest finish in the
    last ``hours`` and hasn't closed yet: the titles in it and when it closes (never after the month
    ends, since a July finish can't count for June). It names the member's own titles, so only their
    card gets it.
    """
    span = timedelta(hours=hours)
    start, end = month_bounds(month)
    events = sorted((when, index) for index, finish in enumerate(finishes) for when in finish.get("times") or ()
                    if start <= when < end)
    best, inside, left = 0, {}, 0
    for when, index in events:
        inside[index] = inside.get(index, 0) + 1
        while when - events[left][0] >= span:
            gone = events[left][1]
            inside[gone] -= 1
            if not inside[gone]:
                del inside[gone]
            left += 1
        best = max(best, len(inside))
    now = now or datetime.utcnow()
    result = {"best": best, "open": None}
    if best >= target or not start <= now < end:
        return result
    recent = [(when, index) for when, index in events if now - span < when <= now]
    if recent:
        names, seen, latest = [], set(), {}
        for when, index in recent:
            latest[index] = when
            if index not in seen:
                seen.add(index)
                names.append((finishes[index].get("title") or "").strip() or "Untitled")
        # A title logged twice in the window (finished again, or a journal entry beside its finish
        # moment) pairs from its latest time, so the window closes a day after the earliest of each
        # title's latest finish, not a day after the very first one.
        closes = min(min(latest.values()) + span, end)
        result["open"] = {"titles": names[:DAY_TITLES_LIMIT], "count": len(seen), "until": _iso(closes)}
    return result


def _edition_titles(slug: str) -> set[tuple[str, str]]:
    """The edition's picks as (category, title), with any other names a library might give them."""
    edition = MONTHLY_EDITIONS.get(slug) or {}
    return {(item["category"], title_pages.normalize(name)) for item in edition.get("items", [])
            for name in (item["title"], *item.get("aliases", ()))}


def _step_count(db: Session, user_id: int, step: dict, finishes: list[dict], month: str) -> tuple[int, int]:
    kind = step["kind"]
    if kind == "total":
        return len(finishes), step["count"]
    if kind == "formats":
        return len({finish["category"] for finish in finishes}), step["count"]
    if kind == "reflect":
        return sum(1 for finish in finishes if finish["reflected"]), step["count"]
    if kind == "category":
        return sum(1 for finish in finishes if finish["category"] == step["category"]), step["count"]
    if kind == "edition":
        picks = _edition_titles(step["edition"])
        return sum(1 for finish in finishes if (finish["category"], title_pages.normalize(finish["title"])) in picks), 1
    if kind == "before":
        years = _release_years(db, finishes)
        count = 0
        for finish in finishes:
            year = years.get((title_pages.LIBRARY_TO_KIND.get(finish["category"]), finish["item_id"]))
            if year and year < step["year"]:
                count += 1
        return count, 1
    if kind == "waiting":
        return _waiting_count(db, user_id, month, finishes), step.get("count", 1)
    if kind == "revisit":
        return _revisit_count(db, user_id, month), step.get("count", 1)
    return 0, 1


def progress(db: Session, user_id: int, month: str) -> list[dict]:
    finishes = _finishes(db, user_id, month)
    steps = []
    for index, step in enumerate(challenge_for(month)["steps"]):
        extra = {}
        if step["kind"] == "stretch":
            formats = stretch_formats(db, user_id, month, finishes, step.get("under", 3))
            count, target = sum(1 for finish in finishes if finish["category"] in formats), step.get("count", 1)
            # Private to the member: shown on their own card, never on a shared page.
            extra = {"formats": [STRETCH_LABELS[category] for category in formats]}
        elif step["kind"] == "recommended":
            sources = _origins(db, user_id, finishes)
            count, target = _recommended_count(finishes, sources), step.get("count", 1)
            # Private to the member, like "formats": finishes the card can offer to credit to someone.
            extra = {"unsaid": [] if count >= target else unsaid_finishes(db, user_id, finishes, sources)}
        elif step["kind"] == "birthday":
            every = step.get("every", 10)
            count, target = _birthday_count(db, month, finishes, every), step.get("count", 1)
            # "years" is the same for everyone; "turning" names the member's own titles, so only their card has it.
            extra = {"years": birthday_years(month, every)[:4],
                     "turning": [] if count >= target else turning_titles(db, user_id, month, every)}
        elif step["kind"] == "day":
            hours, target = step.get("hours", 24), step.get("count", 2)
            found = day_progress(finishes, month, hours, target)
            count = found["best"]
            # "open" names the member's own titles, like "turning", so only their card has it.
            extra = {"hours": hours, "open": found["open"]}
        else:
            count, target = _step_count(db, user_id, step, finishes, month)
        steps.append({"key": f"step-{index + 1}", "kind": step["kind"], "label": step["label"],
                      "count": min(count, target), "target": target, "done": count >= target, **extra})
    return steps


# ---------------------------------------------------------------- entries

def get_entry(db: Session, user_id: int, month: str) -> Optional[models.MonthlyChallengeEntry]:
    return db.query(models.MonthlyChallengeEntry).filter_by(user_id=user_id, month=month).first()


def join(db: Session, user_id: int, month: str) -> models.MonthlyChallengeEntry:
    entry = get_entry(db, user_id, month)
    if entry is None:
        entry = models.MonthlyChallengeEntry(user_id=user_id, month=month)
        db.add(entry)
        try:
            db.commit()
        except IntegrityError:
            # A double click or second tab joined first.
            db.rollback()
            entry = get_entry(db, user_id, month)
    return entry


def leave(db: Session, user_id: int, month: str) -> bool:
    entry = get_entry(db, user_id, month)
    if entry is None:
        return False
    db.delete(entry)
    db.commit()
    return True


def record_completed(db: Session, user: models.User, month: str, entry: models.MonthlyChallengeEntry,
                     steps: list[dict]) -> bool:
    """Mark a joined challenge complete the first time every step is done, and tell the member once."""
    if entry.completed_at is not None or not steps or not all(step["done"] for step in steps):
        return False
    # Claim completion atomically so overlapping dashboard loads notify only once.
    claimed = (db.query(models.MonthlyChallengeEntry)
               .filter(models.MonthlyChallengeEntry.id == entry.id, models.MonthlyChallengeEntry.completed_at.is_(None))
               .update({"completed_at": datetime.utcnow()}, synchronize_session=False))
    if not claimed:
        db.rollback()
        db.refresh(entry)
        return False
    db.refresh(entry)
    name = challenge_for(month)["name"]
    db.add(models.Notification(
        user_id=user.id, type="challenge_complete",
        message=f"Challenge complete: {name} ({month_label(month)}). Nicely done!",
        link="/#challenge",
    ))
    db.commit()
    return True


def completion_payload(entry: Optional[models.MonthlyChallengeEntry]) -> Optional[dict]:
    if entry is None or entry.completed_at is None:
        return None
    return {
        "completed_at": entry.completed_at.isoformat(),
        "celebrate": entry.seen_at is None,
        "shared": bool(entry.share_token),
        "url": SITE_URL + share_path(entry) if entry.share_token else None,
    }


def mark_seen(db: Session, entry: models.MonthlyChallengeEntry) -> None:
    entry.seen_at = entry.seen_at or datetime.utcnow()
    db.commit()


def share(db: Session, entry: models.MonthlyChallengeEntry) -> models.MonthlyChallengeEntry:
    if not entry.share_token:
        entry.share_token = secrets.token_urlsafe(12)
    entry.seen_at = entry.seen_at or datetime.utcnow()
    db.commit()
    return entry


def unshare(db: Session, entry: models.MonthlyChallengeEntry) -> models.MonthlyChallengeEntry:
    entry.share_token = None
    db.commit()
    return entry


def share_path(entry: models.MonthlyChallengeEntry) -> str:
    return f"/challenge/{entry.share_token}"


def find_shared(db: Session, token: str) -> Optional[models.MonthlyChallengeEntry]:
    """A shared, completed entry whose owner is still active; otherwise None."""
    if not token or len(token) > 32:
        return None
    entry = db.query(models.MonthlyChallengeEntry).filter(models.MonthlyChallengeEntry.share_token == token).first()
    if entry is None or entry.completed_at is None:
        return None
    owner = db.get(models.User, entry.user_id)
    if owner is None or not owner.is_active:
        return None
    return entry


def headline(username: str, month: str) -> str:
    """'Sam completed the October 2026 challenge'."""
    return f"{username} completed the {month_label(month)} challenge"


def public_counts(db: Session, month: str) -> dict:
    """Members who took and completed the challenge, or None for counts too small to show."""
    joined, completed = db.query(
        func.count(models.MonthlyChallengeEntry.id),
        func.count(models.MonthlyChallengeEntry.completed_at),
    ).join(models.User, models.User.id == models.MonthlyChallengeEntry.user_id).filter(
        models.MonthlyChallengeEntry.month == month, models.User.is_active == True,  # noqa: E712
    ).one()
    return {
        "joined": int(joined or 0) if (joined or 0) >= MIN_PUBLIC_COUNT else None,
        "completed": int(completed or 0) if (completed or 0) >= MIN_PUBLIC_COUNT else None,
    }


def payload(db: Session, user: models.User, today: Optional[date] = None) -> dict:
    """The current month's challenge for the dashboard card."""
    today = today or datetime.utcnow().date()
    month = month_key(today)
    challenge = challenge_for(month)
    steps = progress(db, user.id, month)
    entry = get_entry(db, user.id, month)
    if entry is not None:
        try:
            record_completed(db, user, month, entry, steps)
        except Exception:
            db.rollback()  # The card never depends on it.
    edition = challenge.get("edition")
    return {
        "month": month,
        "label": month_label(month),
        "month_name": MONTH_NAMES[today.month - 1],
        "name": challenge["name"],
        "tagline": challenge["tagline"],
        "url": f"/challenges/{slug_for(month)}" if is_curated(month) else None,
        "edition_url": f"/discover/monthly/{edition}" if edition in published_editions() else None,
        "days_left": days_left(month, today),
        "joined": entry is not None,
        "steps": steps,
        "done_steps": sum(1 for step in steps if step["done"]),
        "complete": bool(steps) and all(step["done"] for step in steps),
        "completion": completion_payload(entry),
    }
