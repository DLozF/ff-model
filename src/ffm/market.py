import csv
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl
import requests

FANTASYCALC_URL = (
    "https://api.fantasycalc.com/values/current?"
    "isDynasty=false&numQbs=1&numTeams=12&ppr=1"
)


def cache_fantasycalc(cache: str | Path, now: datetime | None = None) -> Path:
    """Cache the current FantasyCalc redraft market once per Central day."""
    cache = Path(cache)
    local_now = now or datetime.now(ZoneInfo("America/Chicago"))
    path = cache / f"fantasycalc_values_{local_now.date().isoformat()}.parquet"
    if path.exists():
        return path
    response = requests.get(FANTASYCALC_URL, timeout=60)
    response.raise_for_status()
    payload = response.json()
    fetched_at = datetime.now(timezone.utc)
    records = []
    for row in payload:
        player = row.get("player") or {}
        records.append({
            "fetched_at": fetched_at,
            "redraftValue": row.get("redraftValue"),
            "trend30Day": row.get("trend30Day"),
            "overallRank": row.get("overallRank"),
            "positionRank": row.get("positionRank"),
            "player_sleeperId": player.get("sleeperId"),
            "player_name": player.get("name"),
            "player_position": player.get("position"),
            "player_team": player.get("maybeTeam"),
        })
    cache.mkdir(parents=True, exist_ok=True)
    pl.from_dicts(records, infer_schema_length=None).write_parquet(path)
    return path


def load_market(cache: str | Path, now: datetime | None = None) -> pl.DataFrame:
    """Load normalized FantasyCalc values from the daily cache."""
    frame = pl.read_parquet(cache_fantasycalc(cache, now))
    team_column = "player_team" if "player_team" in frame.columns else "player_maybeTeam"
    return frame.select(
        pl.col("fetched_at"),
        pl.col("player_sleeperId").cast(pl.String).alias("sleeper_id"),
        pl.col("player_name").alias("market_name"),
        pl.col("player_position").alias("market_position"),
        pl.col(team_column).alias("market_team"),
        pl.col("redraftValue").cast(pl.Float64).alias("market_value"),
        pl.col("trend30Day").cast(pl.Float64).alias("trend_30_day"),
        pl.col("overallRank").cast(pl.Int64).alias("market_overall_rank"),
        pl.col("positionRank").cast(pl.Int64).alias("market_position_rank"),
    )


def join_market(
    players: pl.DataFrame,
    market: pl.DataFrame,
    id_column: str,
    log_path: str | Path,
) -> pl.DataFrame:
    """Join market values by Sleeper ID and log every unmatched player."""
    joined = players.with_columns(pl.col(id_column).cast(pl.String)).join(
        market, left_on=id_column, right_on="sleeper_id", how="left",
    )
    name_column = "name" if "name" in joined.columns else id_column
    unmatched = joined.filter(pl.col("market_value").is_null()).select(id_column, name_column)
    lines = [
        f"{row[id_column]}\t{row[name_column]}"
        for row in unmatched.iter_rows(named=True)
    ]
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    Path(log_path).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return joined.with_columns(pl.col("market_value").fill_null(0.0))


def package_value(values) -> float:
    """Value a package as its best asset plus half of every other asset."""
    values = [float(value) for value in values]
    if not values:
        return 0.0
    best = max(values)
    return best + 0.5 * (sum(values) - best)


def market_ratio(receives: float, gives: float) -> float:
    """Return the value received divided by the value given."""
    if gives <= 0:
        return float("inf") if receives > 0 else float("nan")
    return float(receives / gives)


DEFAULT_ACCEPTANCE_CUTOFFS = {"likely": 1.0, "possible": 0.9}


def acceptance_cutoffs(path: str | Path) -> dict:
    """Load fitted trade-acceptance cutoffs when at least 20 outcomes are resolved."""
    path = Path(path)
    if not path.exists():
        return {**DEFAULT_ACCEPTANCE_CUTOFFS, "resolved": 0, "calibrated": False}
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    resolved = [
        row for row in rows
        if row.get("outcome") in {"accepted", "rejected", "countered"}
    ]
    result = {
        **DEFAULT_ACCEPTANCE_CUTOFFS,
        "resolved": len(resolved),
        "calibrated": False,
    }
    if len(resolved) < 20:
        return result
    labels = np.array([1 if row["outcome"] == "accepted" else 0 for row in resolved])
    if np.unique(labels).size < 2:
        result["reason"] = "resolved outcomes contain only one class"
        return result
    from sklearn.linear_model import LogisticRegression

    ratios = np.array([[float(row["r"])] for row in resolved])
    model = LogisticRegression(random_state=2026).fit(ratios, labels)
    coefficient = float(model.coef_[0, 0])
    intercept = float(model.intercept_[0])
    if coefficient <= 0:
        result["reason"] = "fitted acceptance slope is not positive"
        return result

    def ratio_at(probability: float) -> float:
        logit = np.log(probability / (1.0 - probability))
        return max(0.0, float((logit - intercept) / coefficient))

    result.update({
        "likely": ratio_at(0.50),
        "possible": ratio_at(0.25),
        "calibrated": True,
        "coefficient": coefficient,
        "intercept": intercept,
    })
    return result


def acceptance_status(cutoffs: dict) -> str:
    """Describe whether reports use guessed or outcome-calibrated thresholds."""
    if cutoffs.get("calibrated"):
        return (
            f"Trade acceptance thresholds fitted on {cutoffs['resolved']} resolved offers: "
            f"LIKELY r>={cutoffs['likely']:.3f}, POSSIBLE r>={cutoffs['possible']:.3f}."
        )
    reason = f" ({cutoffs['reason']})" if cutoffs.get("reason") else ""
    return (
        f"Trade acceptance thresholds remain defaults (LIKELY r>=1.000, "
        f"POSSIBLE r>=0.900): {cutoffs.get('resolved', 0)}/20 resolved offers{reason}."
    )


def acceptance_label(ratio: float, cutoffs: dict | None = None) -> str:
    """Classify acceptance from the other team's market ratio."""
    cutoffs = cutoffs or DEFAULT_ACCEPTANCE_CUTOFFS
    if ratio >= cutoffs["likely"]:
        return "LIKELY"
    if ratio >= cutoffs["possible"]:
        return "POSSIBLE"
    return "UNLIKELY"


def healthy_market_fallers(market: pl.DataFrame, sleeper_players: pl.DataFrame) -> pl.DataFrame:
    """List healthy players whose 30-day trend is below negative 25% of value."""
    health = sleeper_players.select(
        pl.col("player_id").cast(pl.String).alias("sleeper_id"),
        "injury_status", "status", "active",
    )
    return (
        market.join(health, on="sleeper_id", how="inner")
        .filter(
            (pl.col("trend_30_day") < -0.25 * pl.col("market_value"))
            & (pl.col("injury_status").is_null() | (pl.col("injury_status") == ""))
            & (pl.col("active") == True)
        )
        .with_columns(
            (100 * pl.col("trend_30_day") / pl.col("market_value")).alias("trend_pct")
        )
        .sort("trend_pct")
    )


def news_lines(news: pl.DataFrame) -> list[str]:
    """Render the market faller section shared by trade and waiver reports."""
    lines = ["## News check: healthy market fallers", ""]
    if news.is_empty():
        return lines + ["- None.", ""]
    lines.extend(
        f"- {row['market_name']} ({row['market_position']}): "
        f"V {row['market_value']:.0f}, 30-day {row['trend_30_day']:+.0f} "
        f"({row['trend_pct']:+.1f}%)."
        for row in news.iter_rows(named=True)
    )
    return lines + [""]


def write_model_vs_market(players: pl.DataFrame, market: pl.DataFrame, path: str | Path) -> None:
    """Write the largest within-position rank gaps for the market top 150."""
    model = players.select(
        pl.col("player_id").cast(pl.String).alias("sleeper_id"),
        pl.col("name"), pl.col("position"), pl.col("ros_points"),
    ).with_columns(
        pl.col("ros_points").rank("ordinal", descending=True).over("position").alias("model_rank")
    )
    compared = (
        market.sort("market_value", descending=True).head(150)
        .join(model, on="sleeper_id", how="inner")
        .with_columns((pl.col("model_rank") - pl.col("market_position_rank")).alias("rank_gap"))
    )

    def table(title: str, rows: pl.DataFrame) -> list[str]:
        output = [title, "", "| Player | Pos | V | Model rank | Market rank | Gap |", "|---|---|---:|---:|---:|---:|"]
        for row in rows.iter_rows(named=True):
            output.append(
                f"| {row['name']} | {row['position']} | {row['market_value']:.0f} | "
                f"{row['model_rank']} | {row['market_position_rank']} | {row['rank_gap']:+d} |"
            )
        return output + [""]

    path = Path(path)
    forward_section = ""
    start = "<!-- forward-test:start -->"
    end = "<!-- forward-test:end -->"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if start in existing and end in existing:
            body = existing.split(start, 1)[1].split(end, 1)[0]
            forward_section = f"{start}{body}{end}"
    lines = ["# Model vs market", "", "Top 150 players by FantasyCalc redraft value.", ""]
    lines += table("## Market ranks higher than model", compared.sort("rank_gap", descending=True).head(15))
    lines += table("## Model ranks higher than market", compared.sort("rank_gap").head(15))
    content = "\n".join(lines).rstrip() + "\n"
    if forward_section:
        content += "\n" + forward_section + "\n"
    path.write_text(content, encoding="utf-8")
