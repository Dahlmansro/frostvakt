# tests/test_data_pipeline.py
"""
Tester för datapipeline - API-anrop, databas och datatransformering.
"""
import os
import sys
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import pytest
import requests
import pandas as pd
import yaml
from sqlalchemy import create_engine, text

# Lägg till src-mappen i Python-sökvägen
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from main import (
    load_config, 
    transform_hourly_json, 
    get_engine, 
    create_database_tables,
    load_weather_data
)


class TestAPIConnection:
    """Tester för API-anslutning till Open-Meteo."""
    
    @pytest.fixture
    def config(self):
        """Ladda konfiguration för tester."""
        return load_config("config.yaml")
    
    def test_api_connection(self, config):
        """Testa grundläggande API-anslutning."""
        base_url = config["api"]["base_url"]
        params = {
            "latitude": config["api"]["params"]["latitude"],
            "longitude": config["api"]["params"]["longitude"],
            "hourly": "temperature_2m",  # Bara en parameter för snabb test
            "forecast_days": 1
        }
        
        try:
            response = requests.get(
                base_url, 
                params=params, 
                timeout=config["run"]["timeout_seconds"]
            )
            response.raise_for_status()
            
            data = response.json()
            assert "hourly" in data, "API returnerade ogiltigt format"
            assert data["hourly"].get("time"), "API returnerade inga tidsstämplar"
            
        except requests.RequestException as e:
            pytest.fail(f"API-anslutning misslyckades: {e}")
    
    def test_api_returns_expected_data(self, config):
        """Testa att API returnerar förväntad datastruktur."""
        base_url = config["api"]["base_url"]
        params = config["api"]["params"].copy()
        params["forecast_days"] = 1  # Begränsa för snabbare test
        
        response = requests.get(base_url, params=params, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        # Kontrollera att alla förväntade fält finns
        assert "hourly" in data
        hourly = data["hourly"]
        
        expected_fields = ["time", "temperature_2m", "wind_speed_10m"]
        for field in expected_fields:
            assert field in hourly, f"Fält '{field}' saknas i API-svar"
            assert isinstance(hourly[field], list), f"Fält '{field}' är inte en lista"
    
    def test_api_coordinates_valid(self, config):
        """Kontrollera att koordinaterna i config ger rimliga resultat."""
        params = config["api"]["params"]
        lat = params["latitude"]
        lon = params["longitude"]
        
        # Vingåker ska ha koordinater runt dessa värden
        assert 58 < lat < 60, f"Latitud {lat} verkar inte vara för Vingåker"
        assert 15 < lon < 17, f"Longitud {lon} verkar inte vara för Vingåker"


class TestDataTransformation:
    """Tester för datatransformering från API till DataFrame."""
    
    def test_transform_hourly_json(self):
        """Testa transformering av API JSON till DataFrame."""
        # Skapa mock API-data
        mock_json = {
            "hourly": {
                "time": [
                    "2025-01-01T00:00",
                    "2025-01-01T01:00",
                    "2025-01-01T02:00"
                ],
                "temperature_2m": [5.0, 4.2, 3.8],
                "wind_speed_10m": [7.2, 8.1, 6.5],  # km/h (kommer konverteras till m/s)
                "relative_humidity_2m": [80, 82, 85],
                "precipitation": [0.0, 0.1, 0.0]
            }
        }
        
        # Transformera data
        df = transform_hourly_json(
            mock_json, 
            "forecast", 
            pd.Timestamp.now(), 
            "test_run_123"
        )
        
        # Kontrollera resultat
        assert not df.empty, "DataFrame är tom efter transformering"
        assert len(df) == 3, "Fel antal rader efter transformering"
        
        # Kontrollera kolumner
        expected_cols = [
            "valid_time", "temperature_2m", "wind_speed_10m", 
            "dataset", "run_id"
        ]
        for col in expected_cols:
            assert col in df.columns, f"Kolumn '{col}' saknas"
        
        # Kontrollera vindkonvertering (km/h till m/s)
        expected_wind_ms = 7.2 / 3.6  # 7.2 km/h = 2.0 m/s
        assert abs(df.iloc[0]['wind_speed_10m'] - expected_wind_ms) < 0.1, \
            "Vindkonvertering från km/h till m/s fungerar inte"
    
    def test_transform_handles_missing_data(self):
        """Testa att transformering hanterar saknade värden."""
        mock_json = {
            "hourly": {
                "time": ["2025-01-01T00:00", "2025-01-01T01:00"],
                "temperature_2m": [5.0, None],
                "wind_speed_10m": [None, 8.1]
            }
        }
        
        df = transform_hourly_json(mock_json, "test", None, "test_run")
        
        assert not df.empty
        assert len(df) == 2
        assert pd.isna(df.iloc[1]['temperature_2m'])
        assert pd.isna(df.iloc[0]['wind_speed_10m'])


class TestDatabaseOperations:
    """Tester för databasoperationer."""
    
    @pytest.fixture
    def temp_db(self):
        """Skapa temporär databas för tester."""
        import time
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_path = f.name
        
        yield temp_path
        
        # Städa upp efter test (Windows-säkert)
        try:
            # Vänta lite för att säkerställa att alla anslutningar stängs
            time.sleep(0.1)
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except (PermissionError, OSError):
            # På Windows kan filer ibland vara låsta - ignorera detta
            pass
    
    def test_database_creation(self, temp_db):
        """Testa att databas och tabeller kan skapas."""
        engine = get_engine(temp_db)
        create_database_tables(engine)
        
        # Kontrollera att filen skapades
        assert os.path.exists(temp_db), "Databasfil skapades inte"
        
        # Kontrollera tabellstruktur
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='weather_hourly'
            """)
            tables = cursor.fetchall()
            assert len(tables) == 1, "weather_hourly tabellen skapades inte"
    
    def test_data_insertion(self, temp_db):
        """Testa att data kan sparas i databasen."""
        engine = get_engine(temp_db)
        create_database_tables(engine)
        
        # Skapa testdata
        test_data = pd.DataFrame({
            'valid_time': ['2025-01-01 12:00:00', '2025-01-01 13:00:00'],
            'temperature_2m': [5.0, 4.5],
            'wind_speed_10m': [2.0, 2.5],
            'cloud_cover': [50.0, 60.0], 
            'dataset': ['test', 'test'],
            'run_id': ['test_run_123', 'test_run_123'],
            'relative_humidity_2m': [80.0, 82.0],
            'precipitation': [0.0, 0.1],
            'wind_speed_10m': [2.0, 2.5],
            'precipitation_probability': [10, 20],
            'forecast_issue_time': [None, None],
            'horizon_hours': [None, None]
        })
        
        # Spara data
        rows_inserted = load_weather_data(test_data, engine)
        assert rows_inserted == 2, "Fel antal rader sparades"
        
        # Kontrollera att data finns i databasen
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM weather_hourly")
            count = cursor.fetchone()[0]
            assert count == 2, "Data sparades inte korrekt"
    
    def test_database_constraints(self, temp_db):
        """Testa databas-begränsningar och unika nycklar."""
        engine = get_engine(temp_db)
        create_database_tables(engine)
        
        # Skapa testdata
        test_data = pd.DataFrame({
            'valid_time': ['2025-01-01 12:00:00', '2025-01-01 13:00:00'],  # Olika tider
            'temperature_2m': [5.0, 6.0],
            'wind_speed_10m': [2.0, 2.5],
            'cloud_cover': [50.0, 60.0],
            'dataset': ['forecast', 'forecast'],
            'run_id': ['run_1', 'run_1'],
            'relative_humidity_2m': [80.0, 82.0],
            'precipitation': [0.0, 0.1],
            'precipitation_probability': [10, 20],
            'forecast_issue_time': [None, None],
            'horizon_hours': [None, None]
        })
        
        # Spara data första gången
        rows1 = load_weather_data(test_data, engine)
        assert rows1 == 2, "Första insättningen misslyckades"
        
        # Testa REPLACE-logik med samma data
        rows2 = load_weather_data(test_data, engine)
        assert rows2 == 2, "Andra insättningen misslyckades"
        
        # Kontrollera att vi fortfarande har 2 rader (inte 4)
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM weather_hourly")
            count = cursor.fetchone()[0]
            assert count == 2, f"REPLACE logik fungerar inte korrekt - förväntade 2, fick {count}"


class TestDataValidation:
    """Tester för datavalidering och kvalitet."""
    
    def test_temperature_ranges(self):
        """Testa att temperaturer är inom rimliga gränser."""
        # Skapa testdata med extrema temperaturer
        test_data = pd.DataFrame({
            'temperature_2m': [-50.0, 0.0, 25.0, 45.0],  # Extrema men möjliga värden
            'wind_speed_10m': [0.0, 5.0, 10.0, 30.0]
        })
        
        # Kontrollera att värdena är inom rimliga gränser för Sverige
        temps = test_data['temperature_2m']
        assert temps.min() >= -60, "Temperatur för låg för svenska förhållanden"
        assert temps.max() <= 50, "Temperatur för hög för svenska förhållanden"
    
    def test_wind_speed_validation(self):
        """Testa att vindhastigheter är rimliga."""
        test_data = pd.DataFrame({
            'wind_speed_10m': [0.0, 2.0, 15.0, 30.0]  # m/s
        })
        
        winds = test_data['wind_speed_10m']
        assert winds.min() >= 0, "Vindhastighet kan inte vara negativ"
        assert winds.max() <= 50, "Vindhastighet för hög (över 50 m/s = 180 km/h)"


if __name__ == "__main__":
    # Kör tester direkt om filen körs
    pytest.main([__file__, "-v"])