import polars as pl

from ffm.experiments import fit_through_origin, lagged_residual_feature


def test_lagged_residual_uses_only_prior_games():
    frame = pl.DataFrame({
        "season": [2025] * 4, "week": [1, 2, 3, 4], "sleeper_id": ["p"] * 4,
        "proj_pts": [10.0] * 4, "act_pts": [11.0, 12.0, 13.0, 20.0],
    })
    result = lagged_residual_feature(frame)
    assert result.get_column("residual_last3").to_list() == [None, 1.0, 1.5, 2.0]


def test_fit_through_origin_recovers_coefficient():
    assert fit_through_origin([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]) == 2.0
