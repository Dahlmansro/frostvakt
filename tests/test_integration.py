# tests/test_integration.py
"""
Integrationstester för Frostvakt-systemet.
Testar att systemet fungerar som helhet och att konfiguration/loggning fungerar.
"""
import os
import sys
from pathlib import Path
from datetime import datetime
import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# FIXAT: Importera från advanced_frost_analyzer
from advanced_frost_analyzer import analyze_dataframe_advanced
import pandas as pd


class TestConfiguration:
    """Tester för konfigurationsfiler och inställningar."""
    
    def test_config_file_exists(self):
        """Kontrollera att config.yaml finns."""
        config_path = Path("config.yaml")
        assert config_path.exists(), "config.yaml saknas"
    
    def test_config_file_valid_yaml(self):
        """Kontrollera att config.yaml är giltig YAML."""
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        assert isinstance(config, dict), "config.yaml måste innehålla ett dictionary"
    
    def test_config_has_required_sections(self):
        """Kontrollera att alla nödvändiga konfigurationssektioner finns."""
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        required_sections = ["api", "storage", "run", "email"]
        
        for section in required_sections:
            assert section in config, f"Konfigurationssektion '{section}' saknas"
    
    def test_api_config_complete(self):
        """Kontrollera att API-konfiguration är komplett."""
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        api_config = config["api"]
        required_api_fields = ["base_url", "params"]
        
        for field in required_api_fields:
            assert field in api_config, f"API-fält '{field}' saknas"
        
        params = api_config["params"]
        required_params = ["latitude", "longitude", "hourly"]
        
        for param in required_params:
            assert param in params, f"API-parameter '{param}' saknas"
    
    def test_email_config_structure(self):
        """Kontrollera email-konfigurationens struktur."""
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        email_config = config["email"]
        
        # Kontrollera att enabled finns och är boolean
        assert "enabled" in email_config
        assert isinstance(email_config["enabled"], bool)
        
        # Om email är aktiverat, kontrollera nödvändiga fält
        if email_config["enabled"]:
            required_fields = ["smtp_server", "smtp_port", "sender_email", "recipients"]
            for field in required_fields:
                assert field in email_config, f"Email-fält '{field}' saknas"


class TestLogging:
    """Tester för loggning och filhantering."""
    
    def test_log_directory_creation(self):
        """Testa att logg-mapp kan skapas."""
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        log_file = config["run"]["log_file"]
        log_dir = os.path.dirname(log_file)
            
        # Skapa mappen
        os.makedirs(log_dir, exist_ok=True)
        
        # Kontrollera att mappen skapades
        assert os.path.exists(log_dir), "Kunde inte skapa logg-mapp"
    
    def test_log_file_writable(self):
        """Testa att vi kan skriva till logg-filen."""
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        log_file = config["run"]["log_file"]
        log_dir = os.path.dirname(log_file)
        
        # Skapa mappen om den inte finns
        os.makedirs(log_dir, exist_ok=True)
        
        # Testa att skriva till filen
        test_content = f"Integration test {datetime.now()}\n"
        
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(test_content)
        
        # Kontrollera att filen finns och innehåller vår text
        assert os.path.exists(log_file), "Logg-fil skapades inte"
        
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert test_content in content, "Kunde inte skriva till logg-fil"


class TestSystemIntegration:
    """Tester för systemintegration och helhetsflöden."""
    
    def test_frost_analyzer_integration(self):
        """Testa att frost-analys fungerar med realistisk data."""
        # Skapa testdata som liknar verklig väderdata
        test_data = pd.DataFrame({
            'temperature_2m': [5.0, 2.0, -1.0, 0.5, 3.5],
            'wind_speed_10m': [1.0, 3.0, 2.0, 1.5, 0.8],
            'cloud_cover': [20.0, 50.0, 80.0, 30.0, 10.0],
            'valid_time': [
                '2025-01-01 06:00:00',
                '2025-01-01 07:00:00', 
                '2025-01-01 08:00:00',
                '2025-01-01 09:00:00',
                '2025-01-01 10:00:00'
            ]
        })
        
        # FIXAT: Använd analyze_dataframe_advanced
        result = analyze_dataframe_advanced(test_data)
        
        # Kontrollera att alla nödvändiga kolumner finns
        expected_columns = ['frost_risk_level', 'frost_risk_numeric', 'frost_warning']
        for col in expected_columns:
            assert col in result.columns, f"Kolumn '{col}' saknas i frost-analys resultat"
        
        # Kontrollera att vi har rätt antal rader
        assert len(result) == len(test_data), "Frost-analys ändrade antal rader"
        
        # Kontrollera grundläggande funktionalitet
        assert len(result) == len(test_data), "Analys påverkade antal rader"
        assert not result.empty, "Analysen returnerade tom DataFrame"

        # Kontrollera att kolumnerna finns och har rätt datatyper
        for col in ['frost_risk_level', 'frost_risk_numeric', 'frost_warning']:
            assert col in result.columns, f"Kolumn '{col}' saknas"
            
        assert result['frost_risk_numeric'].dtype in ['int64', 'int32'], "frost_risk_numeric ska vara heltal"
        assert result['frost_warning'].dtype == bool, "frost_warning ska vara boolean"
       
    def test_data_pipeline_structure(self):
        """Testa att datapipeline-strukturen är korrekt."""
        # Kontrollera att viktiga moduler kan importeras
        try:
            from main import load_config, transform_hourly_json
            from email_notifier import EmailNotifier
            from advanced_frost_analyzer import calculate_advanced_frost_risk
        except ImportError as e:
            pytest.fail(f"Kunde inte importera nödvändiga moduler: {e}")
    
    def test_configuration_integration(self):
        """Testa att konfiguration fungerar med systemet."""
        # Ladda konfiguration
        with open("config.yaml", "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        # Kontrollera att databas-sökväg är rimlig
        db_path = config["storage"]["sqlite_path"]
        db_dir = os.path.dirname(db_path)
        
        # Testa att databas-mappen kan skapas
        os.makedirs(db_dir, exist_ok=True)
        assert os.path.exists(db_dir), "Kunde inte skapa databas-mapp"


if __name__ == "__main__":
    # Kör tester direkt om filen körs
    pytest.main([__file__, "-v"])