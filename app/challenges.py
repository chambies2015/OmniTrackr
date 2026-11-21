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
import re
import secrets
import unicodedata
from calendar import monthrange
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import backlog_draw, diary, models, title_origins, title_pages, year_in_review
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
#   pair        finish ``count`` titles whose other version, in another format, the member has also finished, then
#               or any time before: matched by name, or by an edition pick's "other" version (a book and an
#               audiobook of the same name are the same words, so they never pair)
#   maker       finish ``count`` titles by someone (a director, author, band, host, TV creator or game studio) whose
#               other work the member has also finished, then or any time before: going by the creator field,
#               the maker credit in a title's cached public facts, or an edition pick's maker and "shadow" (their
#               best-known work); another copy of the same story is not other work
#   report      write ``words`` words or more about each of ``count`` titles finished this month: the takeaway on
#               the finish screen, the note on a journal finish and the title's review, added together
#   draw        finish ``count`` titles this month that the member kept from the backlog draw on the home screen
#               (the "Draw from your backlog" card), whenever they kept it and whatever happened to the card after
#   tell        recommend ``count`` titles to someone this month with Recommend to a friend: sent to a friend's inbox
#               on OmniTrackr, or as a share link for someone who isn't on it yet (the step counts the sending, not
#               whether anyone opened it)
#   decades     finish titles released in ``count`` different decades this month, going by the year saved on each
#               title (1987 and 1989 are the same decade, 1989 and 1990 are not)
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
    "2027-07": {
        "name": "Told twice",
        "tagline": "Finish one of July's nine stories that exist in two formats, finish the other version of something you know and say which one you'd hand a friend first.",
        "published": "2027-07-01",
        # The July edition (out July 1) has nine picks, one per format, each naming its version in another format.
        "edition": "july-2027",
        "intro": [
            "July is when the big summer adaptations open, and when somebody always says the book was better. This challenge, and the July edition it pairs with, are about stories told twice, in two different formats. Jaws was a bestselling novel before it was a film, and Spielberg's mechanical shark broke down so often that he left most of it to your imagination. The film of Akira had to invent an ending because the manga still had two years to run. The Last of Us went from a game to a television series, Homecoming from a podcast to one, and Tommy from a double album to a film that changes who dies. The edition has nine picks, one in each format, and each names its other version. The challenge asks you to finish one of the nine, to finish the other version of something you already know, and to write down which version you would hand a friend first.",
            "The middle step counts a July finish whose other version you have finished in a different format, whenever that was: the film of a book you read years ago, or the manga of an anime you watched last week. It goes by the names in your library, so two titles with the same name in different formats pair up on their own, and the challenge card on your home screen lists a few titles already in your library that would make a pair. For the edition's nine, the other versions it names count under their own names too. A book and its own audiobook don't count, since they are the same words. Anything you finish in July counts, whenever you joined.",
        ],
        "steps": [
            {"kind": "edition", "edition": "july-2027",
             "label": "Finish one pick from the July edition",
             "detail": "The July edition has nine picks, one in each format OmniTrackr tracks, and each has another version in a different format that is worth finishing too. Tommy is about 75 minutes and The Girl Who Leapt Through Time 98, so either fits an evening, and Jaws is a little over two hours. Akira is six volumes and more than 2,000 pages, so start that one early. Finish any one of the nine in July and this step is done."},
            {"kind": "pair", "count": 1,
             "label": "Finish the other version of something",
             "detail": "Any title you finish in July counts if you have also finished a version of it in another format, this month or any time before: the novel and the film, the manga and the anime, the game and the series. The step goes by the names in your library, so check that both are saved under the same title. For the edition's picks, the other version it names counts under its own name, so 80 Days pairs with Around the World in Eighty Days. A book and its audiobook are the same words, so they don't pair. If you finish one of the edition's picks in July and have already finished its other version, this step and the first are both done."},
            {"kind": "reflect", "count": 1,
             "label": "Say which you'd hand a friend first",
             "detail": "Rate one of this month's finishes or add a line about it when you mark it finished. If you have finished both versions of something, write down which you would give a friend first and why: the quicker one, the one that keeps a surprise, or the one that does something the other can't. Takeaways stay private unless you publish a review."},
        ],
        "reflection": "Which version of a story you love did you meet first, and do you think that decided which one you prefer?",
    },
    "2027-08": {
        "name": "Eclipsed",
        "tagline": "Finish one of August's nine works eclipsed by their maker's most famous one, finish something else by a creator you already know and say whether the shadow was deserved.",
        "published": "2027-08-01",
        # The August edition (out August 1) has nine picks, one per format, each naming its maker's best-known work.
        "edition": "august-2027",
        "intro": [
            "On Monday, August 2, the Moon passes in front of the Sun for up to six minutes and 23 seconds. The shadow crosses southern Spain, Gibraltar and North Africa, then Luxor, Jeddah and Mecca, and most of Europe, Africa and the Middle East will see at least part of it. A longer total eclipse won't cross easily reached land until 2114. This challenge, and the August edition it pairs with, are about another kind of eclipse: the work that disappears behind its maker's most famous one. Francis Ford Coppola made The Conversation between the two Godfather films, and it lost the Oscar for Best Picture to the second of them. Fleetwood Mac followed Rumours with Tusk, a double album that cost more than any rock record before it and sold about four million copies, against more than forty million for Rumours. Toni Morrison wrote Sula fourteen years before Beloved. The edition has nine of these, one in each format, and each names the famous work standing in front of it. The challenge asks you to finish one of the nine, to finish something else by someone whose work you have already finished, and to write down whether the shadow was deserved.",
            "The middle step counts an August finish by a director, author, band, host, TV creator or game studio whose other work you have finished, this month or any time before. It goes by the creator saved on each title in your library and by the director, creator or developer that a title's page lists, when it lists one. For the edition's nine, the famous work each one names counts too, so The Conversation counts for anyone who has seen The Godfather. Another copy of the same work doesn't count: the audiobook of a book you have read, or another season or volume of a series you have finished, is more of the same thing. The challenge card on your home screen lists a few titles already in your library that would count. Anything you finish in August counts, whenever you joined.",
        ],
        "steps": [
            {"kind": "edition", "edition": "august-2027",
             "label": "Finish one pick from the August edition",
             "detail": "The August edition has nine picks, one in each format OmniTrackr tracks, and each lives in the shadow of the best-known work by the same people. The Conversation is 113 minutes and Tusk about 74, so either fits an evening, and Sula is under six hours on audio. The Leftovers is 28 episodes and Silver Spoon fifteen volumes, so start those early. Finish any one of the nine in August and this step is done."},
            {"kind": "maker", "count": 1,
             "label": "Finish something else by a creator you already know",
             "detail": "Any title you finish in August counts if you have also finished other work by the same director, author, band, podcast host, TV creator or game studio, this month or any time before: a second film by a director you like, another album by a band, a novel by the author of a book you loved. The step goes by the creator saved on each title in your library, so check those are filled in, and by the director, creator or developer a title's page lists, which is how TV, anime and games can count. For the edition's picks, the famous work it names counts too, so finishing Tusk counts if you have heard Rumours. The audiobook of a book you have read, or another season or volume of the same series, is the same work, so it doesn't count. The challenge card lists a few titles in your library that qualify."},
            {"kind": "reflect", "count": 1,
             "label": "Say whether the shadow was deserved",
             "detail": "Rate one of this month's finishes or add a line about it when you mark it finished. If you went from someone's famous work to a lesser-known one, write down which you would hand a friend first, and whether the famous one earned its place in front. Takeaways stay private unless you publish a review."},
        ],
        "reflection": "Which of this month's finishes deserved more attention than it got, and what do you think kept it in the shadow?",
    },
    "2027-09": {
        "name": "Required reading",
        "tagline": "Finish one of September's nine set texts, finish something from your summer reading list and hand in a fifty-word report.",
        "published": "2027-09-01",
        # The September edition (out September 1) has nine picks, one per format, each saying where it has been taught.
        "edition": "september-2027",
        "intro": [
            "In much of the world September is when school starts again, and on September 8 UNESCO marks International Literacy Day. This challenge, and the September edition it pairs with, are about the works classrooms teach: nine of them, one in each format, from a jury-room drama that British secondary schools screen more than almost any other film to a game three student teachers wrote for an eighth-grade history class in 1971. This month they are on nobody's syllabus but yours. The challenge asks you to finish one of them, to finish something from your own summer reading list, meaning anything that was already in your library before September 1, and to hand in a short report on something you finished.",
            "The report is the new part. Write fifty words or more about one of your September finishes: in the takeaway box when you mark it finished, in a note on the finish in your journal, or in a review on the title. Fifty words is four or five sentences. The step adds up everything you wrote about that one title, so a line now and a few more later count together, and it stays private unless you choose to publish a review. The challenge card on your home screen keeps count as you write. Anything you finish in September counts, whenever you joined.",
        ],
        "steps": [
            {"kind": "edition", "edition": "september-2027",
             "label": "Finish one of September's nine set texts",
             "detail": "The September edition has nine works that schools and universities teach, one in each format OmniTrackr tracks, and each says where it has been taught. 12 Angry Men is 96 minutes and To Pimp a Butterfly about 79, so either fits an evening, and a run of The Oregon Trail takes an hour or two. The Wire is 60 episodes and Barefoot Gen ten volumes, so start those early. Finish any one of the nine in September and this step is done."},
            {"kind": "waiting", "count": 1,
             "label": "Finish your summer reading",
             "detail": "Anything that was already in your library before September 1 counts, whether you saved it in June meaning to get to it over the summer or three years ago. Most libraries have a summer reading list that never got read. Pick one title from it and finish it. A title you add and finish in September counts toward the other two steps, just not this one, and if one of the edition's picks was already waiting in your library, it can do both."},
            {"kind": "report", "count": 1, "words": 50,
             "label": "Hand in a fifty-word report",
             "detail": "Write fifty words or more about one title you finish in September. The takeaway you write when you mark it finished counts, and so do a note on the finish in your journal and the review on the title, all added together, so you can write a line tonight and finish the report at the weekend. Four or five sentences will do it: what it is, what worked, what didn't and who you would give it to. Nobody grades it. A takeaway stays private, and a review is public only if you choose to publish it. The challenge card keeps count and can open the finish screen for your latest finish."},
        ],
        "reflection": "Which of this month's finishes would you put on a syllabus, and what would you want a class to argue about?",
    },
    "2027-10": {
        "name": "At a price",
        "tagline": "Finish one of October's nine bargains, take the deal the backlog draw offers you and make all three wishes.",
        "published": "2027-10-01",
        # The October edition (out October 1) has nine picks, one per format, each a story about a wish granted at a price.
        "edition": "october-2027",
        "intro": [
            "October is the month for stories about the dark, and one of the oldest is the bargain: a wish granted by a devil, a witch or a stranger at a crossroads, and a price that turns out to be more than anyone meant to pay. This challenge, and the October edition it pairs with, are about those deals: nine of them, one in each format, from a potion that keeps two rivals young whether they like it or not to a lamb brought back from the dead on the condition that it starts a cult. The challenge asks you to finish one of them, to take a deal of your own from the backlog draw on your home screen, and to make all three wishes, meaning three finishes in October.",
            "The deal is the new part. The Draw from your backlog card on your home screen deals you three face-down cards from titles you saved and never started. Keep one, finish it in October, and the step is done. You don't choose what's on the cards, which is the point: the bargain is that you watch, play, read or listen to whatever you're dealt. Anything you finish in October counts, whenever you joined.",
        ],
        "steps": [
            {"kind": "edition", "edition": "october-2027",
             "label": "Finish one of October's nine bargains",
             "detail": "The October edition has nine stories about a wish granted at a price, one in each format OmniTrackr tracks, and each says who the deal is with. Death Becomes Her is 104 minutes and Robert Johnson's King of the Delta Blues Singers about 43, so either fits an evening, and Something Wicked This Way Comes is a weekend's reading. Chainsaw Man is twelve episodes and xxxHolic nineteen volumes, so start those early. Finish any one of the nine in October and this step is done."},
            {"kind": "draw", "count": 1,
             "label": "Take the deal",
             "detail": "On your home screen, the Draw from your backlog card deals you three face-down cards from titles you saved and never started. Turn them over, keep one, pick a night for it if you like, and finish it in October. A card you kept before October counts too, and so does one you put back and then finished anyway. The draw needs at least three titles waiting in your library (podcasts aren't dealt, since they rarely end), so if the card isn't there, save a few first. If you don't like the first three, you can deal again, but the spirit of the thing is to take what you're given."},
            {"kind": "total", "count": 3,
             "label": "Make all three wishes",
             "detail": "Wishes come in threes in the old stories, from The Monkey's Paw to the genie in the bottle, and the third is usually the one that puts things right. Finish three titles in October, in any format. The edition pick and the card you were dealt both count toward the three, so a single extra finish can do it. Nobody is keeping score but you."},
        ],
        "reflection": "Which of this month's finishes cost you more than you expected, in time, nerve or sleep, and was it worth the price?",
    },
    "2027-11": {
        "name": "Tell me a story",
        "tagline": "Finish one of November's nine storytellers, tell someone about a title you loved and hear stories told two different ways.",
        "published": "2027-11-01",
        # The November edition (out November 1) has nine picks, one per format, each saying who tells its story.
        "edition": "november-2027",
        "intro": [
            "November is the month of long evenings and, in America, of the Thanksgiving table, where the same stories come out every year and somebody always tells them better than everyone else. This challenge, and the November edition it pairs with, are about storytellers: nine of them, one in each format, from a grandfather reading a fairy tale to a boy home sick from school to a folk singer who spends eighteen minutes explaining how he was arrested for littering on Thanksgiving Day in 1965. The challenge asks you to finish one of them, to tell somebody about a title you loved, and to finish stories in two different formats.",
            "The telling is the new part. In April the challenge counted titles somebody recommended to you; this month it is your turn. Choose Recommend on any title in your library, or on a title's page, and send it to a friend on OmniTrackr or make a share link for someone who isn't on it yet. Either one counts, and the step counts the telling, not whether they get round to it. The challenge card on your home screen offers your latest finish to start with. Anything you finish in November counts, whenever you joined.",
        ],
        "steps": [
            {"kind": "edition", "edition": "november-2027",
             "label": "Finish one of November's nine storytellers",
             "detail": "The November edition has nine stories about telling stories, one in each format OmniTrackr tracks, and each says who is telling it. The Princess Bride is 98 minutes and the title song of Alice's Restaurant eighteen and a half, so either fits an evening, and an episode of The Storyteller is about 22 minutes. The Thirteenth Tale is a long novel and Showa Genroku Rakugo Shinju 25 episodes, so start those early. Finish any one of the nine in November and this step is done."},
            {"kind": "tell", "count": 1,
             "label": "Tell someone about one",
             "detail": "Choose Recommend on a title in your library, or on its title page, and either send it to a friend on OmniTrackr with a line about why, or make a share link and send it to someone who isn't on OmniTrackr yet, by text, email or however you usually talk. Any title counts, whether you finished it this month or years ago, and the step counts the telling, not whether they listen. A share link opens a page with the title and your note, and if they join from it, you'll be friends. A recommendation shares only public facts about a title, never your rating, review or notes. The challenge card offers your latest finish to start with."},
            {"kind": "formats", "count": 2,
             "label": "Hear it told two ways",
             "detail": "Finish titles in two different formats in November: a film and a book, an album and a podcast, a manga and a game. A story told aloud, drawn or played is a different thing from one you read, and the edition has a storyteller in every format if you want ideas. The edition pick counts toward this step, so one more finish in another format will do it."},
        ],
        "reflection": "Which story from this month would you tell at the dinner table, and what would you leave out to make it better?",
        "links": [
            ("The Thanksgiving weekend guide", "/holidays/thanksgiving"),
        ],
    },
    "2027-12": {
        "name": "Between the years",
        "tagline": "Finish one of December's nine time machines, visit three decades and leave a note for next December.",
        "published": "2027-12-01",
        # The December edition (out December 1) has nine picks, one per format, each naming its time machine.
        # Christmas, the best-of lists and Year in Review have pages of their own, linked rather than repeated.
        "edition": "december-2027",
        "intro": [
            "December is when the year looks back at itself. Your Year in Review fills in, the best-of lists come out and the holiday guides fill the evenings, and then comes the odd, quiet week between Christmas and New Year that Germans call zwischen den Jahren, between the years. This challenge, and the December edition it pairs with, are about time travel: nine stories, one in each format, from a man who goes back to fix his love life by clenching his fists in a dark cupboard to a teacher who steps out of a diner's pantry into 1958 to stop the assassination of a president. The challenge asks you to finish one of them, to finish titles from three different decades, and to leave a note for the person you will be next December.",
            "The decades are the new part. Each of your December finishes counts for the decade it was released in, going by the year saved on the title in your library, so a film from 1987 and an album from 1989 are one decade and a book from 1990 is another. Three decades will do. The challenge card on your home screen keeps track of the decades you have visited and lists a few unfinished titles in your library from the ones you haven't. Anything you finish in December counts, whenever you joined.",
        ],
        "steps": [
            {"kind": "edition", "edition": "december-2027",
             "label": "Finish one of December's nine time machines",
             "detail": "The December edition has nine time-travel stories, one in each format OmniTrackr tracks, and each names its time machine. About Time is 123 minutes and Electric Light Orchestra's Time about 44, so either fits an evening, and Kindred is a weekend's reading. Steins;Gate is 24 episodes, Chrono Trigger twenty hours or more and 11/22/63 over thirty hours on audio, so save those for the long break. Finish any one of the nine in December and this step is done."},
            {"kind": "decades", "count": 3,
             "label": "Visit three decades",
             "detail": "Finish titles released in three different decades in December: a film from the 1980s, an album from the 1960s and a game from last year would do it. Each title counts for its decade, going by the year saved on it in your library, so check that it is filled in; for a game it is the release date. 1987 and 1989 are the same decade, and 1989 and 1990 are not. The edition's nine come from four decades, from Kindred in 1979 to You're Dead to Me in 2019, so three of them can do this step on their own, and the challenge card lists a few titles in your library from decades you haven't visited yet."},
            {"kind": "reflect", "count": 1,
             "label": "Leave a note for next December",
             "detail": "Rate one of this month's finishes or add a line about it when you mark it finished. Write it for the person who will read it a year from now: what it was like to meet it now, where you were and who you watched, read, played or heard it with. It will be waiting in your journal. Takeaways stay private unless you publish a review."},
        ],
        "reflection": "If you could go back and meet a story for the first time again, which would it be, and what would you tell yourself before you started?",
        "links": [
            ("The holiday guides", "/holidays"),
            ("The Christmas guide", "/holidays/christmas"),
            ("Your Year in Review", "/year-in-review"),
            ("The best of the year", "/best-of"),
        ],
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
    for row, item_id, reflected, note in (
        *((entry, entry.item_id, entry.rating is not None or bool((entry.note or "").strip()), entry.note)
          for entry in entries),
        *((moment, moment.item_id, moment.rating is not None or bool((moment.takeaway or "").strip()), moment.takeaway)
          for moment in moments),
    ):
        if row.category not in FORMAT_NOUNS:
            continue
        key = year_in_review._title_key(row.category, item_id, row.title)
        found = finished.setdefault(key, {"category": row.category, "item_id": item_id,
                                          "title": row.title or "", "reflected": False, "at": None, "times": [],
                                          "notes": []})
        found["reflected"] = found["reflected"] or reflected
        if (note or "").strip():
            found["notes"].append(note)
        when = getattr(row, "occurred_at", None) or getattr(row, "completed_at", None)
        if when is not None:
            found["times"].append(when)
            if found["at"] is None or when > found["at"]:
                found["at"] = when
        if found["item_id"] is None:
            found["item_id"] = item_id
    removed = {key: (row["times"], row["notes"]) for key, row in finished.items() if isinstance(key[1], str)}
    folded = year_in_review.fold_deleted_copies(finished)
    # A removed copy folded into the live one keeps its finish times (day steps read every one) and its notes
    # (report steps add them up).
    for key, (times, notes) in removed.items():
        if key in folded:
            continue
        for live_key, row in folded.items():
            if not isinstance(live_key[1], str) and (row["category"], year_in_review._plain_title(row["title"])) == key:
                row["times"].extend(times)
                row["notes"].extend(notes)
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


# ---------------------------------------------------------------- pair steps

# Formats whose titles of the same name are the same words read or heard, so they never make a pair.
SAME_WORDS = frozenset({"books", "audiobooks"})
# Words for each format in the card's "Other versions in your library" line.
PAIR_NOUNS = {
    "movies": "film", "tv-shows": "TV", "anime": "anime", "video-games": "game", "music": "album",
    "books": "book", "manga": "manga", "podcasts": "podcast", "audiobooks": "audiobook",
}
# How many unfinished titles the card names under a pair step.
PAIR_WAITING_LIMIT = 3
# Rows read per format: enough for any real library, and a bound on the card's cost for a huge import.
PAIR_LIBRARY_CAP = 5000

_NUMBER = r"(?:\d+|[ivx]+|one|two|three|four|five|six|seven|eight|nine|ten)"
# "Akira, Vol. 1", "24: Season 1", "The Last of Us Part I", "Dune: Part Two", "... The Final Season".
_PART = re.compile(r"[\s,:;.\-\u2013\u2014]+(?:(?:season|series|part|volume|vol|book|chapter|episode)\.?\s*" + _NUMBER
                   + r"|(?:the\s+)?(?:complete|final|first)\s+(?:season|series|collection|edition))$")
_BRACKETS = re.compile(r"\s*[(\[][^()\[\]]*[)\]]$")
_ARTICLE = re.compile(r"^(?:the|a|an)\s+")


# Characters of a title read for its story key. Library titles have no length limit, and the cache below
# keeps every title it is given, so a long one is cut first; the longest real titles are well under this.
STORY_KEY_CHARS = 300
# Punctuation that only separates words. A run of it is folded to one space before the suffixes are cut, so
# _PART never rescans a long run (40,000 commas and spaces used to take half a minute).
_SEPARATORS = re.compile(r"[\s,:;.\-\u2013\u2014]+")


def story_key(title: str) -> str:
    """A title reduced to the name its versions share: "The Last of Us Part I" and "The Last of Us: Season 1"
    are both "last of us". Trailing brackets, season/part/volume numbers and a leading article go; accents
    and punctuation are folded. Titles with no Latin letters keep their own script. "" when nothing is left.
    Only the first STORY_KEY_CHARS characters are read.
    """
    return _story_key(str(title or "")[:STORY_KEY_CHARS])


@lru_cache(maxsize=16384)
def _story_key(title: str) -> str:
    text = unicodedata.normalize("NFKD", title)
    folded = text.encode("ascii", "ignore").decode("ascii")
    text = (folded if re.search(r"[A-Za-z0-9]", folded) else text).casefold().replace("&", " and ")
    text = text.replace("'", "").replace("\u2019", "")
    text = _SEPARATORS.sub(" ", text).strip()
    previous = None
    while previous != text:
        previous = text
        text = _PART.sub("", _BRACKETS.sub("", text)).strip()
    text = " ".join(re.sub(r"[\W_]+", " ", text).split())
    return _ARTICLE.sub("", text) or text


def _edition_versions() -> tuple[dict, dict]:
    """Edition picks that name an "other" version: (category, name) of the pick -> its keys, and
    name of the other version -> [(pick category, key)]. The other version counts in any format but the pick's."""
    picks: dict[tuple[str, str], set[str]] = {}
    others: dict[str, list[tuple[str, str]]] = {}
    for slug, edition in MONTHLY_EDITIONS.items():
        for item in edition.get("items", []):
            other = item.get("other")
            if not other:
                continue
            key = f"{slug}/{item['key']}"
            for name in (item["title"], *item.get("aliases", ())):
                picks.setdefault((item["category"], title_pages.normalize(name)), set()).add(key)
            for name in (other["title"], *other.get("aliases", ())):
                others.setdefault(title_pages.normalize(name), []).append((item["category"], key))
    return picks, others


def _story_keys(category: str, title: str, versions: tuple[dict, dict]) -> list[str]:
    picks, others = versions
    keys = set(picks.get((category, title_pages.normalize(title)), ()))
    keys.update(key for pick_category, key in others.get(title_pages.normalize(title), ()) if pick_category != category)
    plain = story_key(title or "")
    if plain:
        keys.add("name:" + plain)
    return sorted(keys)


def _pairs_with(category: str, other: str) -> bool:
    return category != other and {category, other} != SAME_WORDS


def _library_rows(db: Session, user_id: int) -> list[dict]:
    """The member's library across the nine formats: title, finished or not, newest saves first."""
    rows = []
    for kind, (model, _, category, _, _) in title_pages.KINDS.items():
        done = getattr(model, title_pages.COMPLETE_FIELD[kind])
        for item_id, title, finished, added_at in db.query(model.id, model.title, done, model.added_at).filter(
                model.user_id == user_id).order_by(model.id.desc()).limit(PAIR_LIBRARY_CAP):
            if (title or "").strip():
                rows.append({"category": category, "id": item_id, "title": title.strip(),
                             "finished": bool(finished), "added": added_at or datetime.min})
    rows.sort(key=lambda row: (row["added"], row["id"]), reverse=True)
    return rows


def pair_progress(finishes: list[dict], library: list[dict], limit: int = PAIR_WAITING_LIMIT) -> dict:
    """Stories finished in two formats, counting only those with a finish this month, and up to ``limit``
    unfinished library titles that would make a pair.

    The other version can have been finished at any time: a library title marked finished counts, and so
    does any of this month's finishes, including a title since removed. Each story counts once, whether
    one or both of its versions were finished this month. "waiting" names the member's own titles, so only
    their card gets it.
    """
    versions = _edition_versions()
    finished: dict[str, set[str]] = {}
    for row in (*(row for row in library if row["finished"]), *finishes):
        for key in _story_keys(row["category"], row["title"], versions):
            finished.setdefault(key, set()).add(row["category"])

    def partner(category: str, keys: list[str]) -> Optional[tuple[str, str]]:
        for key in keys:
            match = next((other for other in sorted(finished.get(key, ())) if _pairs_with(category, other)), None)
            if match:
                return key, match
        return None

    stories = set()
    for finish in finishes:
        found = partner(finish["category"], _story_keys(finish["category"], finish["title"], versions))
        if found:
            stories.add(found[0])
    waiting, seen = [], set()
    for row in library:
        if len(waiting) >= limit:
            break
        if row["finished"] or (row["category"], title_pages.normalize(row["title"])) in seen:
            continue
        found = partner(row["category"], _story_keys(row["category"], row["title"], versions))
        if found:
            seen.add((row["category"], title_pages.normalize(row["title"])))
            waiting.append({"title": row["title"], "format": PAIR_NOUNS[row["category"]],
                            "with": PAIR_NOUNS[found[1]]})
    return {"count": len(stories), "waiting": waiting}


# ---------------------------------------------------------------- maker steps

# The credit in a title's public facts that names who made it (people_pages.FACT_ROLES roles). Cast,
# writers, studios of anime, publishers and networks are left out: they lump unrelated work together.
MAKER_CREDITS = {"movie": ("Director",), "tv": ("Creator",), "anime": ("Director",), "game": ("Developer",),
                 "album": ("Artist",), "book": ("Author",), "manga": ("Mangaka",), "podcast": ("Host",),
                 "audiobook": ("Author",)}
# How the creator field members type is split: a band's name keeps its commas.
MAKER_FIELD_ROLES = {"movie": "Director", "album": "Artist", "book": "Author", "manga": "Mangaka",
                     "podcast": "Host", "audiobook": "Author"}
# How many unfinished titles the card names under a maker step.
MAKER_WAITING_LIMIT = 3
# Rows read per format, like PAIR_LIBRARY_CAP: a bound on the card's cost for a huge import.
MAKER_LIBRARY_CAP = 5000
# Cached-facts keys read for maker credits (four queries). Titles past it still count by creator field.
MAKER_CREDIT_KEYS = 2000
_MORE_NAMES = re.compile(r"\s+(?:&|and)\s+|\s*;\s*|\s+/\s+")


def maker_key(name: str) -> str:
    """A maker's name reduced for matching: "The Velvet Underground" and "Velvet Underground" are one band,
    "Shinichirō Watanabe" and "Shinichiro Watanabe" one person. "" for a placeholder such as "Various"."""
    from . import people_pages

    name = " ".join((name or "").split())
    if not people_pages.is_real_name(name):
        return ""
    slug = people_pages.name_slug(name)
    slug = slug[4:] if slug.startswith("the-") and len(slug) > 4 else slug
    return slug if len(slug) >= 2 else ""


def maker_names(kind: str, value: str) -> list[str]:
    """The people in a creator field: "Joseph Fink, Jeffrey Cranor" and "Phil Lord & Christopher Miller" are two
    each, while a band such as "Earth, Wind & Fire" stays one name."""
    from . import people_pages

    role = MAKER_FIELD_ROLES.get(kind)
    if not role or not (value or "").strip():
        return []
    names = []
    for part in people_pages.split_names(value, role):
        names.extend([part] if role in people_pages.UNSPLIT_ROLES else _MORE_NAMES.split(part))
    return [name.strip() for name in names if name and name.strip()]


def _edition_makers() -> tuple[dict, dict]:
    """Edition picks that name a "shadow" (their maker's best-known work): (category, story key) of the pick, and
    of the shadow in each format it counts in, -> (maker key, maker's name)."""
    picks: dict[tuple[str, str], tuple[str, str]] = {}
    shadows: dict[tuple[str, str], tuple[str, str]] = {}
    for edition in MONTHLY_EDITIONS.values():
        for item in edition.get("items", []):
            shadow, maker = item.get("shadow"), item.get("maker")
            key = maker_key(maker or "")
            if not shadow or not key:
                continue
            for name in (item["title"], *item.get("aliases", ())):
                picks[(item["category"], story_key(name))] = (key, maker)
            for category in (shadow["category"], *shadow.get("also", ())):
                for name in (shadow["title"], *shadow.get("aliases", ())):
                    shadows[(category, story_key(name))] = (key, maker)
    return picks, shadows


def _maker_rows(db: Session, user_id: int) -> list[dict]:
    """The member's library across the nine formats with each title's creator field and year, newest saves first."""
    rows = []
    for kind, (model, _, category, _, creator) in title_pages.KINDS.items():
        done = getattr(model, title_pages.COMPLETE_FIELD[kind])
        columns = [model.id, model.title, done, model.added_at, title_pages._year_column(kind, model)]
        if creator:
            columns.append(getattr(model, creator))
        for found in db.query(*columns).filter(model.user_id == user_id).order_by(model.id.desc()).limit(MAKER_LIBRARY_CAP):
            item_id, title, finished, added_at, year = found[:5]
            if (title or "").strip():
                rows.append({"category": category, "kind": kind, "id": item_id, "title": title.strip(),
                             "finished": bool(finished), "added": added_at or datetime.min,
                             "year": title_pages._row_year(kind, year), "creator": found[5] if creator else None})
    rows.sort(key=lambda row: (row["added"], row["id"]), reverse=True)
    return rows


def _credit_keys(kind: str, title: str, year: Optional[int]) -> tuple[str, ...]:
    from . import title_metadata

    normalized = title_pages.normalize(title)
    keys = [title_metadata.cache_key(kind, normalized, year)]
    if year:
        keys.append(title_metadata.cache_key(kind, normalized, None))
    return tuple(keys)


def _credited_makers(db: Session, wanted: dict[str, str]) -> dict[str, list[tuple[str, str]]]:
    """The makers in cached public facts for each metadata key: key -> [(maker key, name)], 500 keys a query.

    ``wanted`` maps each key to its title kind, since only that kind's maker credit counts (a film's director,
    not its cast)."""
    found: dict[str, list[tuple[str, str]]] = {}
    keys = sorted(wanted)
    roles = sorted({role for kind in set(wanted.values()) for role in MAKER_CREDITS.get(kind, ())})
    if not keys or not roles:
        return found
    for first in range(0, len(keys), 500):
        for metadata_key, role, name in db.query(
            models.TitleCredit.metadata_key, models.TitleCredit.role, models.TitleCredit.name,
        ).filter(models.TitleCredit.metadata_key.in_(keys[first:first + 500]), models.TitleCredit.role.in_(roles)):
            if role in MAKER_CREDITS.get(wanted.get(metadata_key), ()):
                key = maker_key(name)
                if key:
                    found.setdefault(metadata_key, []).append((key, name))
    return found


def maker_progress(db: Session, finishes: list[dict], rows: list[dict], target: int = 1,
                   limit: int = MAKER_WAITING_LIMIT) -> dict:
    """This month's finishes by someone whose other work the member has finished, and, while the step isn't
    done, up to ``limit`` unfinished library titles that would count.

    A title's makers are the names in its creator field, its maker credit in cached public facts (director,
    TV creator, developer...) and, for an edition pick or the famous work it names, the edition's maker. The
    other work can have been finished at any time: a library title marked finished counts, and so does any of
    this month's finishes, including a title since removed. Another copy of the same story (the audiobook of a
    book, another season) is not other work. "waiting" names the member's own titles, so only their card gets it.
    """
    picks, shadows = _edition_makers()
    by_id = {(row["category"], row["id"]): row for row in rows}

    def row_for(finish: dict) -> Optional[dict]:
        return by_id.get((finish["category"], finish["item_id"])) if finish["item_id"] is not None else None

    # Credits are looked up for this month's finishes first, then the newest saves, up to MAKER_CREDIT_KEYS keys.
    wanted: dict[str, str] = {}
    for category, title, row in (*((finish["category"], finish["title"], row_for(finish)) for finish in finishes),
                                 *((row["category"], row["title"], row) for row in rows)):
        kind = title_pages.LIBRARY_TO_KIND.get(category)
        if kind and len(wanted) < MAKER_CREDIT_KEYS:
            for key in _credit_keys(kind, title, row["year"] if row else None):
                wanted[key] = kind
    try:
        credited = _credited_makers(db, wanted)
    except Exception:
        db.rollback()  # The step still counts creator fields and edition picks.
        credited = {}

    memo: dict[tuple, dict[str, str]] = {}

    def makers(category: str, title: str, row: Optional[dict]) -> dict[str, str]:
        """Maker key -> the maker's name as first found."""
        cache_key = (category, title, row["id"] if row else None)
        if cache_key in memo:
            return memo[cache_key]
        kind = title_pages.LIBRARY_TO_KIND.get(category)
        found: dict[str, str] = {}
        for name in maker_names(kind, row["creator"] if row else ""):
            key = maker_key(name)
            if key:
                found.setdefault(key, name)
        if kind:
            for metadata_key in _credit_keys(kind, title, row["year"] if row else None):
                for key, name in credited.get(metadata_key, ()):
                    found.setdefault(key, name)
        story = story_key(title)
        for mapping in (picks, shadows):
            if (category, story) in mapping:
                key, name = mapping[(category, story)]
                found.setdefault(key, name)
        memo[cache_key] = found
        return found

    # Every finished work, by maker: maker key -> story keys.
    finished: dict[str, set[str]] = {}
    done_entries = [(row["category"], row["title"], row) for row in rows if row["finished"]]
    done_entries += [(finish["category"], finish["title"], row_for(finish)) for finish in finishes]
    for category, title, row in done_entries:
        for key in makers(category, title, row):
            finished.setdefault(key, set()).add(story_key(title))

    def known_maker(title: str, found: dict[str, str]) -> Optional[str]:
        """The name of a maker of ``title`` with other finished work, or None."""
        story = story_key(title)
        for key in sorted(found):
            if finished.get(key, set()) - {story}:
                return found[key]
        return None

    counted = {story_key(finish["title"]) for finish in finishes
               if known_maker(finish["title"], makers(finish["category"], finish["title"], row_for(finish)))}
    waiting, seen = [], set()
    if len(counted) < target:
        for row in rows:
            if len(waiting) >= limit:
                break
            name = (row["category"], title_pages.normalize(row["title"]))
            if row["finished"] or name in seen:
                continue
            maker = known_maker(row["title"], makers(row["category"], row["title"], row))
            if maker:
                seen.add(name)
                waiting.append({"title": row["title"], "maker": maker})
    return {"count": len(counted), "waiting": waiting}


# ---------------------------------------------------------------- report steps

# Words in a report: letters and digits, with an apostrophe or hyphen inside a word ("don't", "well-made").
REPORT_WORD = re.compile(r"[^\W_]+(?:['’-][^\W_]+)*")
# Japanese and Chinese are written without spaces, so two of their characters count as one word.
_WIDE_CHARS = re.compile("[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff66-\uff9f]")


def report_words(text: Optional[str]) -> int:
    """How many words a takeaway, note or review has, for a report step."""
    text = str(text or "")
    wide = len(_WIDE_CHARS.findall(text))
    return len(REPORT_WORD.findall(_WIDE_CHARS.sub(" ", text))) + (wide + 1) // 2


# Characters of each review, takeaway or note read for a report. Fifty words fit many times over, and a
# library review has no length limit, so the card never reads (or counts through) more than this.
REPORT_TEXT_CHARS = 20000


def _reviews(db: Session, user_id: int, finishes: list[dict]) -> dict[tuple[str, int], list[str]]:
    """What the member wrote on each finished title still in their library, besides this month's journal notes:
    the title's review and the takeaway on its finish screen, whenever either was saved. One query per format
    for reviews and one for takeaways, reading only the member's own rows.

    A takeaway saved in an earlier month counts as well as the review does: "Keep writing" on the card opens
    the title's one finish screen, which may date from an earlier finish, and what is added there must count.
    """
    wanted: dict[str, set[int]] = {}
    for finish in finishes:
        kind = title_pages.LIBRARY_TO_KIND.get(finish["category"])
        if kind is not None and finish["item_id"] is not None and finish["item_id"] > 0:
            wanted.setdefault(kind, set()).add(finish["item_id"])
    written: dict[tuple[str, int], list[str]] = {}
    for kind, ids in wanted.items():
        model = title_pages.KINDS[kind][0]
        ordered = sorted(ids)
        for first in range(0, len(ordered), 500):
            for item_id, review in db.query(model.id, func.substr(model.review, 1, REPORT_TEXT_CHARS)).filter(
                model.user_id == user_id, model.id.in_(ordered[first:first + 500]), model.review.isnot(None),
            ):
                if (review or "").strip():
                    written.setdefault((kind, item_id), []).append(review)
    ids = sorted({item_id for found in wanted.values() for item_id in found})
    for first in range(0, len(ids), 500):
        for category, item_id, takeaway in db.query(
            models.CompletionMoment.category, models.CompletionMoment.item_id,
            func.substr(models.CompletionMoment.takeaway, 1, REPORT_TEXT_CHARS),
        ).filter(
            models.CompletionMoment.user_id == user_id, models.CompletionMoment.item_id.in_(ids[first:first + 500]),
            models.CompletionMoment.takeaway.isnot(None),
        ):
            kind = title_pages.LIBRARY_TO_KIND.get(category)
            if kind is not None and item_id in wanted.get(kind, ()) and (takeaway or "").strip():
                written.setdefault((kind, item_id), []).append(takeaway)
    return written


def report_progress(finishes: list[dict], reviews: dict[tuple[str, int], list[str]], words: int = 50,
                    target: int = 1) -> dict:
    """This month's finishes with at least ``words`` words written about them, and the one to write more about.

    A finish's words are its takeaway on the finish screen, the notes on its journal finishes and the title's
    review (``reviews``, from _reviews), added together; the same text saved in two places counts once. While the step isn't done, "best"
    is the finish with the most words so far (the latest finish if none has any), so the card can show the
    count and open the finish screen for it. It names the member's own title, so only their card gets it.
    """
    counted, written = 0, []
    for finish in finishes:
        texts: dict[str, str] = {}
        saved = reviews.get((title_pages.LIBRARY_TO_KIND.get(finish["category"]), finish["item_id"])) or ()
        for text in (*finish.get("notes", ()), *((saved,) if isinstance(saved, str) else saved)):
            plain = " ".join(str(text or "")[:REPORT_TEXT_CHARS].split())
            if plain:
                texts.setdefault(plain.casefold(), plain)
        total = sum(report_words(text) for text in texts.values())
        if total >= words:
            counted += 1
        written.append((total, finish["at"] or datetime.min, finish))
    best = None
    if counted < target and written:
        total, _, finish = max(written, key=lambda found: (found[0], found[1]))
        best = {"title": finish["title"], "category": finish["category"], "id": finish["item_id"],
                "words": total}
    return {"count": counted, "best": best}


# ---------------------------------------------------------------- draw steps

def _kept_cards(db: Session, user_id: int, before: datetime) -> set[tuple[str, int]]:
    """Every title the member has kept from the backlog draw before ``before``, whatever happened to the card.

    ``created_at`` rather than ``picked_at``, which "Not tonight" moves forward to ask again later.
    """
    return {(category, item_id) for category, item_id in db.query(
        models.BacklogDraw.category, models.BacklogDraw.item_id,
    ).filter(models.BacklogDraw.user_id == user_id, models.BacklogDraw.created_at < before).distinct()}


def draw_progress(db: Session, user: models.User, finishes: list[dict], month: str, target: int = 1) -> dict:
    """This month's finishes that the member kept from the backlog draw, and where their draw stands.

    A kept card counts once its title is finished this month, whenever it was kept (before the month ended) and
    whatever happened to the card afterwards: a member who put it back and finished it anyway still took the deal.
    While the step isn't done, "card" is the title on the member's card now ({title, category, night}) and
    "ready" says whether the draw has enough unstarted titles to deal. Both describe the member's own library,
    so only their card gets them.
    """
    _, end = month_bounds(month)
    kept = _kept_cards(db, user.id, end)
    counted = sum(1 for finish in finishes
                  if finish["item_id"] is not None and (finish["category"], finish["item_id"]) in kept)
    card, ready = None, False
    if counted < target:
        draw = backlog_draw.active(db, user.id)
        row = backlog_draw._item(db, user.id, draw.category, draw.item_id) if draw is not None else None
        if row is not None and (row.title or "").strip():
            card = {"title": row.title.strip(), "category": draw.category,
                    "night": draw.night.isoformat() if draw.night else None}
        else:
            ready = backlog_draw.backlog_count(db, user) >= backlog_draw.MIN_BACKLOG
    return {"count": counted, "card": card, "ready": ready}


# ---------------------------------------------------------------- tell steps

def tell_count(db: Session, user_id: int, month: str) -> int:
    """Titles the member recommended this month with Recommend to a friend: to a friend's inbox or as a share link.

    The copy a share link leaves in someone's inbox when they open it (``source_id`` set) is the reader's, not
    another recommendation, and sending one title to three friends is still one title told.
    """
    start, end = month_bounds(month)
    told = db.query(models.FriendRecommendation.category, func.lower(func.trim(models.FriendRecommendation.title))).filter(
        models.FriendRecommendation.sender_id == user_id,
        models.FriendRecommendation.source_id.is_(None),
        models.FriendRecommendation.created_at >= start,
        models.FriendRecommendation.created_at < end,
    ).distinct().limit(1000).all()
    return len(told)


def tell_suggestion(db: Session, user_id: int, finishes: list[dict]) -> Optional[dict]:
    """The finish the card offers to recommend: this month's latest, rated or noted ones first, while it is
    still in the library (the recommend dialog sends a library title). Private, like every other "best"."""
    ordered = sorted((finish for finish in finishes if finish["item_id"] is not None),
                     key=lambda finish: (finish["reflected"], finish["at"] or datetime.min), reverse=True)
    for finish in ordered[:20]:
        kind = title_pages.LIBRARY_TO_KIND.get(finish["category"])
        if kind is None:
            continue
        model = title_pages.KINDS[kind][0]
        title = db.query(model.title).filter(model.id == finish["item_id"], model.user_id == user_id).scalar()
        if (title or "").strip():
            return {"title": title.strip(), "category": finish["category"], "id": finish["item_id"]}
    return None


# ---------------------------------------------------------------- decade steps

DECADE_WAITING_LIMIT = 3
DECADE_LIBRARY_CAP = 500
# A year outside this range is a typo or a placeholder, not a decade anyone can visit.
FIRST_YEAR, LAST_YEAR = 1000, 2100


def decade_of(year) -> Optional[int]:
    """1987 -> 1980; None for a missing or implausible year."""
    if not isinstance(year, int) or isinstance(year, bool) or not FIRST_YEAR <= year <= LAST_YEAR:
        return None
    return year - year % 10


def _decade_waiting(db: Session, user_id: int, visited: set[int], limit: int = DECADE_WAITING_LIMIT) -> list[dict]:
    """Up to ``limit`` unfinished library titles from decades this month hasn't visited yet, one per decade,
    newest saves first. Each names the member's own title, so only their card gets them."""
    rows = []
    for kind, (model, _, category, _, _) in title_pages.KINDS.items():
        column = model.release_date if kind == "game" else model.year
        done = getattr(model, title_pages.COMPLETE_FIELD[kind])
        query = db.query(model.id, model.title, column, model.added_at).filter(
            model.user_id == user_id, column.isnot(None), or_(done.is_(None), done == False),  # noqa: E712
        ).order_by(model.id.desc()).limit(DECADE_LIBRARY_CAP)
        for item_id, title, value, added_at in query:
            year = value.year if kind == "game" and value is not None else value
            decade = decade_of(year)
            if decade is not None and decade not in visited and (title or "").strip():
                rows.append({"title": title.strip(), "category": category, "decade": decade,
                             "added": added_at or datetime.min, "id": item_id})
    rows.sort(key=lambda row: (row["added"], row["id"]), reverse=True)
    waiting, seen = [], set()
    for row in rows:
        if row["decade"] in seen:
            continue
        seen.add(row["decade"])
        waiting.append({"title": row["title"], "category": row["category"], "decade": row["decade"]})
        if len(waiting) >= limit:
            break
    return waiting


def decade_progress(db: Session, user_id: int, finishes: list[dict], target: int = 3) -> dict:
    """The decades this month's finishes were released in, going by the year saved on each title, and while
    the step isn't done, a few unfinished library titles from decades still to visit."""
    years = _release_years(db, finishes)
    visited = set()
    for finish in finishes:
        decade = decade_of(years.get((title_pages.LIBRARY_TO_KIND.get(finish["category"]), finish["item_id"])))
        if decade is not None:
            visited.add(decade)
    waiting = _decade_waiting(db, user_id, visited) if len(visited) < target else []
    return {"count": len(visited), "decades": sorted(visited), "waiting": waiting}


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
        elif step["kind"] == "pair":
            target = step.get("count", 1)
            found = pair_progress(finishes, _library_rows(db, user_id))
            count = found["count"]
            # "waiting" names the member's own titles, like "turning", so only their card has it.
            extra = {"waiting": [] if count >= target else found["waiting"]}
        elif step["kind"] == "maker":
            target = step.get("count", 1)
            found = maker_progress(db, finishes, _maker_rows(db, user_id), target)
            count = found["count"]
            # "waiting" names the member's own titles and the people behind them, so only their card has it.
            extra = {"waiting": found["waiting"]}
        elif step["kind"] == "report":
            target, words = step.get("count", 1), step.get("words", 50)
            found = report_progress(finishes, _reviews(db, user_id, finishes), words, target)
            count = found["count"]
            # "best" names one of the member's own finishes, like "waiting", so only their card has it.
            extra = {"words": words, "best": found["best"]}
        elif step["kind"] == "tell":
            target = step.get("count", 1)
            count = tell_count(db, user_id, month)
            # "suggest" names one of the member's own finishes, like "best", so only their card has it.
            extra = {"suggest": tell_suggestion(db, user_id, finishes) if count < target else None}
        elif step["kind"] == "decades":
            target = step.get("count", 3)
            found = decade_progress(db, user_id, finishes, target)
            count = found["count"]
            # "decades" and "waiting" describe the member's own titles, so only their card has them.
            extra = {"decades": found["decades"], "waiting": found["waiting"]}
        elif step["kind"] == "draw":
            target = step.get("count", 1)
            user = db.get(models.User, user_id)
            found = (draw_progress(db, user, finishes, month, target) if user is not None
                     else {"count": 0, "card": None, "ready": False})
            count = found["count"]
            # "card" names the member's own kept title, like "best", so only their card has it.
            extra = {"card": found["card"], "ready": found["ready"]}
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
