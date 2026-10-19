NFL_TEAMS = {
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
    "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WSH",
}

_ALIASES = {
    "ARZ": "ARI", "BLT": "BAL", "CLV": "CLE", "GBY": "GB",
    "HST": "HOU", "JAC": "JAX", "KAN": "KC", "LA": "LAR",
    "LVR": "LV", "NWE": "NE", "NOR": "NO", "OAK": "LV",
    "SD": "LAC", "SDG": "LAC", "STL": "LAR", "SFO": "SF",
    "TAM": "TB", "WAS": "WSH",
}


def normalize_team(team: str | None) -> str | None:
    """Normalize an NFL team abbreviation."""
    if team is None:
        return None
    value = team.upper()
    return _ALIASES.get(value, value)
