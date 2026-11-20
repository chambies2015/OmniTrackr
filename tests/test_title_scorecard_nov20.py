"""Title pages, Nov 20 2026: the member scorecard, a colour per format, stand-in covers, where-to-watch
tiles with Rent and Buy merged, a flat About, quick answers that fold, members' Share menu."""
from app import models, title_metadata
from app.routers import titles
from tests.test_title_chapters_nov15 import CAST, between
from tests.test_title_pages import SAMPLE, add_movie, member, seed_metadata

RENT_AND_BUY = {
    "v": 1, "kind": "movie", "region": "US", "justwatch": True, "fetched": "2026-11-17",
    "groups": [{"label": "Stream", "providers": [{"name": "Netflix"}]},
               {"label": "Rent", "providers": [{"name": "Apple TV"}, {"name": "Plex"}]},
               {"label": "Buy", "providers": [{"name": "Apple TV"}, {"name": "Vudu"}]}],
    "credits": [{"name": "JustWatch", "url": "https://www.justwatch.com/"}],
}


def page(client, db_session, ratings=(9,), data=SAMPLE, where=None, poster="https://img.example/member.jpg", path="/titles/movie/interstellar-2014"):
    for index, rating in enumerate(ratings):
        add_movie(db_session, member(db_session, f"fan{index}"), rating=rating, watched=index == 0, poster_url=poster)
    db_session.commit()
    if data is not None:
        seed_metadata(db_session, data)
    if where is not None:
        title_metadata.store(db_session, "where:movie:interstellar:2014", where, "ok")
    response = client.get(path)
    assert response.status_code == 200
    return response.text


def card(html):
    return between(html, 'class="title-scorecard', "</section>")


# ---------------------------------------------------------------- scorecard

def test_under_three_ratings_the_card_says_how_close_the_score_is(client, db_session):
    html = page(client, db_session, ratings=(9, None))
    early = card(html)
    assert "title-scorecard--early" in html
    assert "Early days for Interstellar." in early and "2 members tracking it so far, and 1 has watched it." in early
    assert "1 of 3 ratings in" in early and "1<small>/3</small>" in early
    # No empty tiles, no score, and nobody's single rating on show.
    assert "have watched it (" not in html and "0 have" not in html and "9.0" not in early
    assert "The member verdict" not in html


def test_nobody_finished_yet_leaves_the_count_out(client, db_session):
    add_movie(db_session, member(db_session, "solo"))
    db_session.commit()
    early = card(client.get("/titles/movie/interstellar-2014").text)
    assert "1 member tracking it so far." in early and "0 of 3 ratings in" in early and "have watched" not in early


def test_full_card_has_score_spread_numbers_and_verdict(client, db_session):
    html = page(client, db_session, ratings=(9.5, 9, 8, 7, 6))
    full = card(html)
    assert "title-scorecard--spread" in html and "title-scorecard--early" not in html
    assert "7.9<small>/10</small>" in full and "average member rating, from 5 ratings" in full
    assert 'href="/titles/movie#rank-1"' in full and "#1 of 1 movies" in full
    assert "How members rate Interstellar" in full and "From 5 member ratings out of 10" in full
    assert "<b>5</b> members tracking it" in full and "<b>20%</b> of them have watched it" in full
    assert "The member verdict" in full
    # The score is drawn from a custom property; the CSP step turns it into a class.
    assert "--score:79" in html


def test_guests_get_a_sign_up_and_members_a_rate_link(client, db_session):
    html = page(client, db_session, ratings=(9, 8, 7))
    assert 'href="/#signup" data-title-signup>Start your free library</a>' in card(html)
    client.cookies.set("omnitrackr_session", "anything")
    member_html = client.get("/titles/movie/interstellar-2014").text
    assert 'href="#write-review">Rate and review it</a>' in card(member_html)
    assert "Start your free library" not in member_html


def test_the_old_sidebar_and_stat_tiles_are_gone(client, db_session):
    html = page(client, db_session, ratings=(9, 8, 7))
    assert "title-glance" not in html and 'class="title-stats"' not in html


# ---------------------------------------------------------------- format colour, covers, chips

def test_body_carries_the_format_for_its_colour(client, db_session):
    html = page(client, db_session)
    body = html.split("<body", 1)[1].split(">", 1)[0]
    assert 'class="site title-page title-detail"' in body and 'data-title-kind="movie"' in body


def test_no_art_gets_a_stand_in_cover_with_the_name(client, db_session):
    html = page(client, db_session, data={**SAMPLE, "poster": None}, poster=None)
    hero = between(html, 'class="title-hero__art"', "</div>\n")
    assert 'title-hero__poster--empty title-cover' in hero and 'aria-hidden="true"' in hero
    assert "<img" not in hero
    assert '<span class="title-cover__kind">Movie</span>' in hero
    assert '<strong class="title-cover__name">Interstellar</strong>' in hero
    assert '<span class="title-cover__by">Christopher Nolan</span>' in hero
    assert f"--cover-hue:{titles._hue('Interstellar')}" in html


def test_rail_cards_without_art_get_a_mini_cover(client, db_session):
    users = [member(db_session, f"m{index}") for index in range(2)]
    for user in users:
        add_movie(db_session, user, rating=9)
        add_movie(db_session, user, title="Tenet", year=2020)
    db_session.commit()
    html = client.get("/titles/movie/interstellar-2014").text
    rails = html.split('class="title-related-grid"', 1)[1]
    # The CSP step adds its own class after these two, so match the start of the attribute.
    assert '<span class="title-cover title-cover--mini' in rails and "<b>Tenet</b>" in rails
    assert 'data-kind="movie"' in rails


def test_genre_chips_drop_the_format_and_shelf_marks():
    metadata = {"genres": ["action anime and manga", "Dark fantasy anime and manga", "Dune (Imaginary place)",
                           "Fiction, science fiction, general", "roguelike deck-building game", "Seinen manga",
                           "drama anime and manga"]}
    assert titles._genre_chips(metadata) == ["Action", "Dark fantasy", "Roguelike deck-building", "Seinen"]
    # The facts row keeps the full labels.
    assert "Dark fantasy anime and manga" in titles._genres(metadata)


def test_hero_chips_use_the_short_labels(client, db_session):
    html = page(client, db_session, data={**SAMPLE, "genres": ["heist film", "science fiction action film"]})
    chips = between(html, 'class="title-hero__chips">', "</div>")
    assert chips == '<span class="site-chip">Heist</span><span class="site-chip">Science fiction action</span>'


# ---------------------------------------------------------------- where to watch

def test_rent_and_buy_merge_into_one_list_with_offers():
    groups = titles._where_groups(RENT_AND_BUY["groups"])
    assert [label for label, _ in groups] == ["Stream", "Rent or buy"]
    merged = {provider["name"]: offers for provider, offers in groups[1][1]}
    assert merged == {"Apple TV": ("Rent", "Buy"), "Plex": ("Rent",), "Vudu": ("Buy",)}


def test_rent_alone_is_left_as_it_is():
    groups = [{"label": "Rent", "providers": [{"name": "Apple TV"}]}, {"label": "Free", "providers": [{"name": "Tubi"}]}]
    assert titles._where_groups(groups) == [("Rent", [({"name": "Apple TV"}, ())]), ("Free", [({"name": "Tubi"}, ())])]


def test_where_section_lists_each_store_once(client, db_session):
    html = page(client, db_session, where=RENT_AND_BUY)
    where = between(html, 'id="where-title"', "</section>")
    assert "<h3>Rent or buy</h3>" in where and "<h3>Rent</h3>" not in where and "<h3>Buy</h3>" not in where
    assert where.count('<span class="title-where__name">Apple TV</span>') == 1
    assert '<span class="title-where__offers"><small>Rent</small><small>Buy</small></span>' in where
    # The quick answer still says it plainly.
    assert "rent it from Apple TV and Plex and buy it from Apple TV and Vudu" in html


def test_no_services_found_leaves_out_the_empty_list(client, db_session, monkeypatch):
    monkeypatch.delenv("AMAZON_ASSOCIATES_TAG", raising=False)
    user = member(db_session, "listener")
    db_session.add(models.Podcast(user_id=user.id, title="Hardcore History", host="Dan Carlin", year=2006))
    db_session.commit()
    title_metadata.store(db_session, "podcast:hardcore history:2006", {"links": [], "sources": []}, "ok")
    title_metadata.store(db_session, "where:podcast:hardcore history:2006", None, "miss")
    html = client.get("/titles/podcast/hardcore-history-2006").text
    where = between(html, 'id="where-title"', "</section>")
    assert "Search other services" in where and 'class="title-where__groups"' not in where


# ---------------------------------------------------------------- about, answers, share menu

def test_about_without_a_cast_lays_the_facts_out_flat(client, db_session):
    html = page(client, db_session)
    assert 'class="title-section title-about title-about--flat"' in html
    cast_html = page(client, db_session, data=CAST, ratings=())
    assert 'class="title-section title-about"' in cast_html and "title-cast--nested" in cast_html


def test_quick_answers_fold_after_the_first_two():
    faq = [(f"Question {n}?", f"Answer {n}.", f"Answer {n}.") for n in range(4)]
    html = titles._faq_html(type("Group", (), {"title": "Interstellar"})(), faq)
    assert html.count('<details class="title-faq__item" open>') == 2 and html.count("<details") == 4
    assert "<summary><h3>Question 3?</h3></summary><p>Answer 3.</p>" in html


def test_members_share_menu_holds_the_three_ways_to_pass_it_on(client, db_session):
    client.cookies.set("omnitrackr_session", "anything")
    html = page(client, db_session)
    menu = between(html, '<details class="title-more">', "</details>")
    assert '<summary class="site-btn site-btn--ghost">Share</summary>' in menu
    assert 'class="title-more__item" data-share' in menu and ">Copy or send the link</button>" in menu
    assert "data-friend-rec-open" in menu and "data-take-ask" in menu
    assert html.count("data-friend-rec-open") == 1 and html.count("data-take-ask") == 1


def test_guests_keep_a_plain_share_button(client, db_session):
    html = page(client, db_session)
    assert "title-more" not in html.split("<main>", 1)[1].split("</section>", 1)[0]
    assert '<button type="button" class="site-btn site-btn--ghost" data-share' in html
