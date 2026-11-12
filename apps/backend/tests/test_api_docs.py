"""8.9: docs/api.md lists every route the app has (generated, so it can't drift)."""

from scripts import api_docs


def test_the_api_docs_list_every_route():
    current = api_docs.DOC.read_text()
    assert api_docs.render(current) == current, "docs/api.md is out of date: run `python -m scripts.api_docs` in apps/backend"
