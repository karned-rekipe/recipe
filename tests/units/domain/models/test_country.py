from domain.models.country import Country, normalize_country_code


PREVIOUSLY_MISSING_ISO_CODES = {
    "AI", "AQ", "AS", "AW", "AX", "BL", "BM", "BQ", "BV", "CC", "CK",
    "CW", "CX", "EH", "FK", "FO", "GF", "GG", "GI", "GL", "GP", "GS",
    "GU", "HK", "HM", "IM", "IO", "JE", "KY", "MF", "MO", "MP", "MQ",
    "MS", "NC", "NF", "NU", "PF", "PM", "PN", "PR", "PS", "RE", "SH",
    "SJ", "SX", "TC", "TF", "TK", "UM", "VA", "VG", "VI", "WF", "YT",
}


def test_country_contains_every_iso_3166_1_alpha_2_code():
    country_codes = {country.value for country in Country}

    assert len(country_codes) == 249
    assert PREVIOUSLY_MISSING_ISO_CODES <= country_codes


def test_normalize_country_code_accepts_aliases_and_ignores_unknown_values():
    assert normalize_country_code("fr") is Country.FR
    assert normalize_country_code(" UK ") is Country.GB
    assert normalize_country_code("GP") is Country.GP
    assert normalize_country_code("XK") is None
    assert normalize_country_code(None) is None
