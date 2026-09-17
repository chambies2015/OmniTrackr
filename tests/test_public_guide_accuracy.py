def test_how_to_guide_explains_actual_controls(client):
    response = client.get('/guides')
    assert response.status_code == 200
    content = response.text
    assert '0–10 scale' in content
    assert 'zero is an actual score' in content
    assert 'Public Review checkbox belongs to each item' in content
    assert 'Hiding a tab is a layout preference, not a privacy setting' in content
    assert 'subject to the site' in content
    assert 'previewing a file does not save titles' in content
    assert 'out of 5 or 10' not in content
    assert 'enable public reviews in your account settings' not in content
    assert 'mark items as watched, in progress, or plan-to-watch' not in content.lower()

