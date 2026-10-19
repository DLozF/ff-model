from itertools import combinations


def trade_candidates(my_roster: list[int], other_roster: list[int]):
    """Yield every 1-for-1, 2-for-1, and 1-for-2 trade."""
    for give in my_roster:
        for get in other_roster:
            yield (give,), (get,)
    for give in combinations(my_roster, 2):
        for get in other_roster:
            yield give, (get,)
    for give in my_roster:
        for get in combinations(other_roster, 2):
            yield (give,), get


def waiver_candidates(free_agents: list[int], droppable: list[int]):
    """Yield every drop/add waiver pair."""
    for free_agent in free_agents:
        for drop in droppable:
            yield drop, free_agent
