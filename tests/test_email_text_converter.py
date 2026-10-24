"""Readable mail alternatives, including malformed HTML that must stay bounded."""

import pytest

from app.email import html_to_text


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        (
            '<HEAD><title>Hidden</title><style>hidden</style></HEAD>'
            '<h1>Welcome &amp; enjoy</h1><p>First<br/>Second</p>',
            'Welcome & enjoy\nFirst\nSecond\n',
        ),
        (
            '<script>const markup = "<a href=\'broken";</script>'
            '<style>p::before { content: "<head>"; }</style><p>Visible</p>',
            'Visible\n',
        ),
        (
            '<head><style>hidden </head> still hidden</style>hidden</head><p>Visible</p>',
            'Visible\n',
        ),
        (
            '<!-- <head>comment</head> --><!DOCTYPE html><?ignored?><p>Visible</p>',
            'Visible\n',
        ),
        ('Before<!-- unclosed <a href="secret">hidden', 'Before\n'),
        ('<p>2 < 3 &amp; 5 &gt; 4; &#169; &#x1F680; &unknown;</p>',
         '2 < 3 & 5 > 4; © 🚀 &unknown;\n'),
        ('<p>Before < unfinished &amp; tail', 'Before < unfinished & tail\n'),
        (
            '<A CLASS="test" HREF=\'https://example.test/?a=1&amp;b=2\'>'
            ' Read <strong>this</strong> </A>',
            'Read this (https://example.test/?a=1&b=2)\n',
        ),
        ('<a href="https://example.test/?a=>&amp;b=<">Read</a>',
         'Read (https://example.test/?a=>&b=<)\n'),
        ('<a href="https://example.test/">Unclosed label',
         'Unclosed label (https://example.test/)\n'),
        ('<a href="first">One<a href="second">Two</a>', 'One (first)Two (second)\n'),
        ('<a href="url"></a><a href="">Label</a><a>No href</a>', 'urlLabelNo href\n'),
        ('<a href="url"/>After', 'urlAfter\n'),
        ('<a ="" href="u">t</a>', 't (u)\n'),
        ('<a href>t</a>', 't\n'),
        ('<a href="u" href>t</a>', 't\n'),
        ('<head/><script/><style/><p>Visible</p>', 'Visible\n'),
        ('<a href="url">Before<script>hidden</script> after</a>', 'Before after (url)\n'),
        ('<p>First</p><div><p>Second</p></div><p>Third</p>', 'First\nSecond\n\nThird\n'),
    ],
    ids=[
        'headings-breaks', 'raw-text-tags', 'head-containing-raw-text',
        'comments-declarations', 'unfinished-comment', 'entities-literal-angle',
        'unfinished-tag', 'link-attributes', 'quoted-angle-attributes',
        'unfinished-link', 'nested-link', 'empty-link', 'self-closing-link',
        'malformed-empty-attribute', 'valueless-href', 'last-valueless-href',
        'self-closing-skipped-tags', 'script-in-link', 'blank-lines',
    ],
)
def test_text_alternative_preserves_readable_content(html, expected):
    assert html_to_text(html) == expected


@pytest.mark.parametrize('tag', ['<head', '<a ', '<a href="!"'],
                         ids=['unfinished-head', 'unfinished-link', 'unfinished-href'])
def test_malformed_tag_sequence_recovers_later_visible_content(tag):
    # The malformed prefix is linear to scan and does not consume a later good tag.
    text = html_to_text(tag * 50_000 + '<h2>End of message</h2>')
    assert text.endswith('End of message\n')
    assert '<h2>' not in text


def test_large_valid_email_is_not_silently_truncated():
    label = 'Read this ' * 30_000
    url = 'https://example.test/?key=' + 'a' * 200_000
    text = html_to_text(f'<h2>Heading</h2><a href="{url}">{label}</a><p>Final line</p>')
    assert text == f'Heading\n{label.strip()} ({url})Final line\n'


@pytest.mark.parametrize('attack', [
    '<a href="' * 50_000,
    "<a href='" * 50_000,
    '<a data-value="' + '<\"\'&amp;' * 50_000,
], ids=['unfinished-double-quotes', 'unfinished-single-quotes', 'mixed-quotes-entities'])
def test_quote_heavy_unfinished_html_stays_fast_and_keeps_tail(attack):
    import time

    started = time.perf_counter()
    text = html_to_text(attack + 'Final marker')
    assert time.perf_counter() - started < 2
    assert text.endswith('Final marker\n')


@pytest.mark.parametrize('kind', ['digest', 'announcement'])
def test_generated_campaign_mail_keeps_its_text_alternative(kind, monkeypatch):
    from app import announcements, digest
    from app.email import html_message

    base = 'https://example.test'
    monkeypatch.setattr(digest, 'app_url', lambda: base)
    monkeypatch.setattr(announcements, 'app_url', lambda: base)
    unsubscribe = base + '/email/unsubscribe?token=a&source=email'
    card = {'title': 'Show & <more>', 'label': 'TV', 'date': '2026-10-10',
            'url': '/release-radar/tv#item-1', 'reason': 'In your library'}
    if kind == 'digest':
        subject, html, _ = digest.build_digest('neo & friends', {'matches': [card], 'popular': []}, unsubscribe)
        expected_heading = 'From your library'
        expected_button = 'Open Release Radar (' + base + '/release-radar)'
    else:
        subject, html, _ = announcements.build_email('neo & friends', 3, [card], unsubscribe,
                                                     weekly_url=base + '/email/weekly?token=a&source=email')
        expected_heading = 'Coming up from your library'
        expected_button = 'Email me weekly (' + base + '/email/weekly?token=a&source=email)'
    message = html_message(subject, ['nobody@example.com'], html)
    assert message.alternative_body == html
    assert message.subtype.value == 'plain'
    assert 'Hi neo & friends' in message.body
    assert 'Show & <more> (' in message.body
    assert expected_heading + '\n' in message.body
    assert expected_button in message.body
    assert unsubscribe + ')' in message.body
    assert '&amp;' not in message.body
