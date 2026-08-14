from datetime import datetime, timezone

import pytest

from services.cron import matches, next_run, parse_cron


def t(y=2026, mo=1, d=1, h=0, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


def test_matches_every_minute():
    assert matches("* * * * *", t(2026, 1, 1, 10, 30))


def test_matches_hourly():
    c = "0 * * * *"
    assert matches(c, t(2026, 1, 1, 10, 0))
    assert not matches(c, t(2026, 1, 1, 10, 5))


def test_matches_weekday():
    c = "0 9 * * 1-5"  # 周一至周五 09:00
    # 2026-01-01 是周四 (isoweekday=4)
    assert matches(c, t(2026, 1, 1, 9, 0))
    # 2026-01-03 是周六 (isoweekday=6)
    assert not matches(c, t(2026, 1, 3, 9, 0))


def test_matches_step():
    c = "*/15 * * * *"
    assert matches(c, t(2026, 1, 1, 10, 0))
    assert matches(c, t(2026, 1, 1, 10, 15))
    assert not matches(c, t(2026, 1, 1, 10, 10))


def test_matches_list():
    c = "10,20,30 * * * *"
    assert matches(c, t(2026, 1, 1, 10, 20))
    assert not matches(c, t(2026, 1, 1, 10, 25))


def test_invalid_cron():
    with pytest.raises(ValueError):
        parse_cron("0 9 * *")  # 只有 4 段
    with pytest.raises(ValueError):
        parse_cron("a * * * *")  # 非法值


def test_next_run_basic():
    assert next_run("0 9 * * *", t(2026, 1, 1, 8, 30)) == t(2026, 1, 1, 9, 0)


def test_next_run_next_day():
    assert next_run("0 9 * * *", t(2026, 1, 1, 10, 0)) == t(2026, 1, 2, 9, 0)


def test_next_run_minute_step():
    assert next_run("*/15 * * * *", t(2026, 1, 1, 10, 20)) == t(2026, 1, 1, 10, 30)


def test_next_run_weekday_skip_weekend():
    # 2026-01-02 是周五，下一次工作日是 01-05（周一）
    assert next_run("0 9 * * 1-5", t(2026, 1, 2, 10, 0)) == t(2026, 1, 5, 9, 0)
