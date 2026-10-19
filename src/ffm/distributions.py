from dataclasses import dataclass
from pathlib import Path

import numpy as np
import polars as pl

LEVELS = np.arange(0.005, 1.0, 0.005)
POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")


@dataclass(frozen=True)
class QuantileTable:
    """Conditional quantile table for one position."""

    grid: np.ndarray
    quantiles: np.ndarray
    floor: float


@dataclass
class QuantileModel:
    """Projection-conditional empirical fantasy point distributions."""

    levels: np.ndarray
    tables: dict[str, QuantileTable]

    @classmethod
    def fit(
        cls,
        frame: pl.DataFrame,
        positions: list[str] | tuple[str, ...] = POSITIONS,
        k: int = 300,
        smooth: int = 5,
    ) -> "QuantileModel":
        """Fit nearest-projection residual quantile tables."""
        tables = {}
        played = frame.filter(pl.col("played")) if "played" in frame.columns else frame
        for position in positions:
            rows = played.filter(pl.col("pos") == position)
            projections = rows.get_column("proj_pts").to_numpy()
            actual = rows.get_column("act_pts").to_numpy()
            if projections.size == 0:
                continue
            residuals = actual - projections
            maximum = max(0.25, np.quantile(projections, 0.995))
            grid = np.arange(0, maximum + 0.125, 0.25)
            floor = float(np.quantile(actual, 0.001))
            count = min(k, projections.size)
            quantiles = np.empty((grid.size, LEVELS.size), dtype=np.float64)
            for index, value in enumerate(grid):
                nearest = np.argpartition(np.abs(projections - value), count - 1)[:count]
                quantiles[index] = np.maximum(
                    floor, value + np.quantile(residuals[nearest], LEVELS)
                )
            quantiles = np.maximum.accumulate(quantiles, axis=1)
            quantiles = _rolling_mean(quantiles, smooth)
            quantiles = np.maximum(floor, quantiles)
            quantiles = np.maximum.accumulate(quantiles, axis=1)
            tables[position] = QuantileTable(
                grid.astype(np.float32), quantiles.astype(np.float32), floor
            )
        return cls(LEVELS.copy(), tables)

    def ppf(self, position: str, projection: np.ndarray, u: np.ndarray) -> np.ndarray:
        """Interpolate fantasy points for projections and uniform quantiles."""
        table = self.tables[position]
        projections, uniforms = np.broadcast_arrays(
            np.asarray(projection, dtype=float), np.asarray(u, dtype=float)
        )
        shape = projections.shape
        p = projections.ravel()
        q = np.clip(uniforms.ravel(), self.levels[0], self.levels[-1])
        upper_p = np.searchsorted(table.grid, p, side="right")
        upper_p = np.clip(upper_p, 1, table.grid.size - 1)
        lower_p = upper_p - 1
        p0 = table.grid[lower_p]
        p1 = table.grid[upper_p]
        weight_p = np.divide(p - p0, p1 - p0, out=np.zeros_like(p), where=p1 != p0)
        lower_values = _interp_levels(table.quantiles[lower_p], self.levels, q)
        upper_values = _interp_levels(table.quantiles[upper_p], self.levels, q)
        values = lower_values + weight_p * (upper_values - lower_values)
        above = p > table.grid[-1]
        if np.any(above):
            top = _interp_levels(
                np.broadcast_to(table.quantiles[-1], (above.sum(), self.levels.size)),
                self.levels,
                q[above],
            )
            maximum = float(table.grid[-1])
            values[above] = p[above] + (top - maximum) * p[above] / maximum
        return np.maximum(table.floor, values).reshape(shape)

    def quantile_matrix(self, position: str, projection: np.ndarray) -> np.ndarray:
        """Return all modeled quantiles for each projection."""
        projections = np.asarray(projection, dtype=float).reshape(-1, 1)
        return self.ppf(position, projections, self.levels.reshape(1, -1))

    def save(self, path: str | Path) -> None:
        """Save model tables to a compressed NumPy archive."""
        arrays = {"levels": self.levels, "positions": np.array(list(self.tables))}
        for position, table in self.tables.items():
            arrays[f"{position}_grid"] = table.grid
            arrays[f"{position}_quantiles"] = table.quantiles
            arrays[f"{position}_floor"] = np.array(table.floor)
        np.savez_compressed(path, **arrays)

    @classmethod
    def load(cls, path: str | Path) -> "QuantileModel":
        """Load model tables from a NumPy archive."""
        archive = np.load(path)
        tables = {
            str(position): QuantileTable(
                archive[f"{position}_grid"], archive[f"{position}_quantiles"],
                float(archive[f"{position}_floor"]),
            )
            for position in archive["positions"]
        }
        return cls(archive["levels"], tables)


def _rolling_mean(values: np.ndarray, width: int) -> np.ndarray:
    pad_left = width // 2
    pad_right = width - 1 - pad_left
    padded = np.pad(values, ((pad_left, pad_right), (0, 0)), mode="edge")
    cumulative = np.vstack([np.zeros((1, values.shape[1])), np.cumsum(padded, axis=0)])
    return (cumulative[width:] - cumulative[:-width]) / width


def _interp_levels(rows: np.ndarray, levels: np.ndarray, u: np.ndarray) -> np.ndarray:
    rows = np.asarray(rows)
    if rows.ndim == 1:
        rows = np.broadcast_to(rows, (u.size, rows.size))
    upper = np.searchsorted(levels, u, side="right")
    upper = np.clip(upper, 1, levels.size - 1)
    lower = upper - 1
    row_index = np.arange(u.size)
    weight = (u - levels[lower]) / (levels[upper] - levels[lower])
    return rows[row_index, lower] + weight * (rows[row_index, upper] - rows[row_index, lower])
