# Task 03 A2 rerun: FantasyCalc fallback values

## P7 sample trades

- Current imported league sample: Chalino Sánchez gives Tyler Warren to Team 8 for Christian McCaffrey.
- Result: ACCEPT / UNLIKELY, r=0.301; Tyler Warren V=2410 (`fantasycalc`), Christian McCaffrey V=8016 (`fantasycalc`).
- Report: `reports/trade_2026-10-20_team_8_tyler_warren_christian_mccaffrey.md`.
- The historical AJ Barner-for-Christian McCaffrey P7 sample cannot be rerun as a full roster trade against the current imported league: AJ Barner is now a free agent, not on Chalino Sánchez's roster. The evaluator correctly rejected that stale roster input instead of fabricating a result.

## AJ Barner for Christian McCaffrey: market change

- Before A2: AJ Barner was unmatched and treated as V=0; no source was exposed.
- After A2: AJ Barner is V=2 with `value_source=model_fallback`; Christian McCaffrey remains V=8016 with `value_source=fantasycalc`.
- Other-team market ratio for receiving AJ and giving McCaffrey: r=0.000249501, still UNLIKELY.
- The stale full P7 model verdict is not reported as a rerun because the current roster configuration cannot execute that trade.

## P8 rerun

- Candidates: 44,880.
- Passed market r >= 0.90: 24,184.
- Passed WELP: 260.
- Confirmed trades: 30.
- Confirmed waivers: 10.
- Runtime: 551.802 seconds.
- Trade and waiver reports now expose `value_source` for every listed asset.
- Example fallback waiver: Tyrone Tracy is V=2 (`model_fallback`).
