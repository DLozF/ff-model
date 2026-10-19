from ffm.ids import NFL_TEAMS, normalize_team


def test_team_mapping_covers_all_32_teams():
    assert len(NFL_TEAMS) == 32
    assert {normalize_team(team) for team in NFL_TEAMS} == NFL_TEAMS


def test_source_aliases_normalize():
    assert normalize_team("JAC") == "JAX"
    assert normalize_team("LA") == "LAR"
    assert normalize_team("WAS") == "WSH"
