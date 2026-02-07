from cryptocosmo.config import load_config
from main import run


def test_simulation_runs_20_ticks():
    cfg = load_config('config.yaml')
    cfg.mode = 'simulation'
    cfg.max_ticks = 20
    cfg.tick_seconds = 0
    run(cfg)
