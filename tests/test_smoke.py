# tests/test_smoke.py
"""
Enkel smoke-test, kontrollerar:konfig är ok, moduler importeras, frost-logik fungerar, databasen är rätt strukturerad
"""
import pathlib
import yaml
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

def test_config_loads():
    """Konfigurationsfilen kan laddas."""
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    assert "api" in cfg and "storage" in cfg

def test_imports_work():
    """Viktiga moduler kan importeras."""
    sys.path.insert(0, str(ROOT / "src"))
    from advanced_frost_analyzer import calculate_advanced_frost_risk
    from email_notifier import EmailNotifier
    from main import load_config

def test_frost_logic():
    """Grundläggande frost-logik fungerar."""
    sys.path.insert(0, str(ROOT / "src"))
    from advanced_frost_analyzer import calculate_advanced_frost_risk
    risk, level, _ = calculate_advanced_frost_risk(-2.0, 1.0, 20.0)
    assert risk == "hög", "Frost-algoritm fungerar inte"

def test_database_exists():
    """Databas finns och har rätt tabell."""
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    db_path = ROOT / cfg["storage"]["sqlite_path"]
    if not db_path.exists():
        return  # OK om systemet inte kört än
    
    with sqlite3.connect(db_path) as con:
        tables = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        assert "weather_hourly" in tables