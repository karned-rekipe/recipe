from domain.models.country import Country, normalize_country_code


def test_normalize_country_code_accepts_aliases_and_ignores_unknown_values():
    assert normalize_country_code("fr") is Country.FR
    assert normalize_country_code(" UK ") is Country.GB
    assert normalize_country_code("XK") is None
    assert normalize_country_code(None) is None
