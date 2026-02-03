from pathlib import Path

def test_has_example_config():
    assert Path(config.example.yaml).exists()
