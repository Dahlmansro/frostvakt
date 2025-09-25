# tests/test_email_notifier.py
"""
Tester för email-notifikationssystem.
Testar email-konfiguration, meddelande-formatering och säker anslutning.
"""
import os
import sys
from datetime import datetime, timedelta
import pytest
import pandas as pd
import yaml
from unittest.mock import Mock, patch

# Lägg till src-mappen i Python-sökvägen
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# FIXAT: Använd rätt funktionsnamn
from email_notifier import (
    EmailNotifier, 
    format_frost_warning_email,
    send_frost_notification,
    get_friendly_date,
    create_enhanced_time_blocks,  # <-- ÄNDRAT från create_time_blocks
    get_highest_risk_next_24h
)


class TestEmailConfiguration:
    """Tester för email-konfiguration och validering."""
    
    @pytest.fixture
    def config(self):
        """Ladda konfiguration för tester."""
        with open("config.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    
    def test_email_config_structure(self, config):
        """Kontrollera att email-konfiguration har rätt struktur."""
        email_config = config.get("email", {})
        
        # Kontrollera att enabled finns och är boolean
        assert "enabled" in email_config
        assert isinstance(email_config["enabled"], bool)
    
    def test_email_config_when_enabled(self, config):
        """Testa email-konfiguration när den är aktiverad."""
        email_config = config.get("email", {})
        
        if email_config.get("enabled", False):
            required_fields = ["smtp_server", "smtp_port", "sender_email", "sender_password", "recipients"]
            
            for field in required_fields:
                assert field in email_config, f"Email-fält '{field}' saknas när email är aktiverat"
            
            # Kontrollera att recipients inte är tom
            assert email_config.get("recipients"), "Inga email-mottagare konfigurerade"
            assert isinstance(email_config["recipients"], list), "Recipients måste vara en lista"
    
    def test_smtp_settings_valid(self, config):
        """Kontrollera att SMTP-inställningar är rimliga."""
        email_config = config.get("email", {})
        
        if email_config.get("enabled", False):
            smtp_port = email_config.get("smtp_port")
            assert isinstance(smtp_port, int), "SMTP-port måste vara ett heltal"
            assert 1 <= smtp_port <= 65535, "SMTP-port måste vara mellan 1-65535"
            
            smtp_server = email_config.get("smtp_server")
            assert isinstance(smtp_server, str), "SMTP-server måste vara en sträng"
            assert "." in smtp_server, "SMTP-server måste vara en giltig domän"


class TestEmailNotifierClass:
    """Tester för EmailNotifier-klassen."""
    
    def test_email_notifier_creation(self):
        """Testa att EmailNotifier kan skapas med giltiga parametrar."""
        notifier = EmailNotifier(
            smtp_server="smtp.example.com",
            smtp_port=587,
            sender_email="test@example.com",
            sender_password="test_password"
        )
        
        assert notifier.smtp_server == "smtp.example.com"
        assert notifier.smtp_port == 587
        assert notifier.sender_email == "test@example.com"
        assert notifier.sender_password == "test_password"
    
    @patch('smtplib.SMTP')
    def test_email_connection_test_success(self, mock_smtp):
        """Testa framgångsrik email-anslutning."""
        # Mock SMTP-servern
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        
        notifier = EmailNotifier(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            sender_email="test@gmail.com",
            sender_password="test_password"
        )
        
        # Testa anslutning
        result = notifier.test_connection()
        
        assert result == True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test@gmail.com", "test_password")
    
    @patch('smtplib.SMTP')
    def test_email_connection_test_failure(self, mock_smtp):
        """Testa misslyckad email-anslutning."""
        # Mock SMTP-servern att kasta fel
        mock_smtp.side_effect = Exception("Anslutning misslyckades")
        
        notifier = EmailNotifier(
            smtp_server="invalid.server.com",
            smtp_port=587,
            sender_email="test@invalid.com",
            sender_password="wrong_password"
        )
        
        # Testa anslutning
        result = notifier.test_connection()
        
        assert result == False


class TestEmailFormatting:
    """Tester för email-formatering och innehåll."""
    
    @pytest.fixture
    def sample_warnings(self):
        """Skapa test-frostvarningar."""
        now = datetime.now()
        return pd.DataFrame({
            'valid_time': [
                now + timedelta(hours=2),
                now + timedelta(hours=3),
                now + timedelta(hours=4)
            ],
            'temperature_2m': [-1.0, 0.5, 2.0],
            'wind_speed_10m': [1.5, 2.0, 1.0],
            'cloud_cover': [20.0, 50.0, 80.0],
            'frost_risk_level': ['hög', 'medel', 'låg'],
            'frost_risk_numeric': [3, 2, 1],
            'dataset': ['forecast', 'forecast', 'forecast']
        })
    
    def test_get_friendly_date(self):
        """Testa vänlig datumformatering."""
        now = datetime.now()
        today = now.date()
        tomorrow = today + timedelta(days=1)
        
        # Testa olika datum
        today_result = get_friendly_date(now)
        assert "Idag" in today_result
        
        tomorrow_result = get_friendly_date(datetime.combine(tomorrow, datetime.min.time()))
        assert "I morgon" in tomorrow_result
    
    def test_get_highest_risk_next_24h(self, sample_warnings):
        """Testa identifiering av högsta risknivå."""
        risk = get_highest_risk_next_24h(sample_warnings)
        assert risk == "hög"  # Högsta risk i sample_warnings
    
    def test_get_highest_risk_empty_warnings(self):
        """Testa högsta risk med inga varningar."""
        empty_df = pd.DataFrame()
        risk = get_highest_risk_next_24h(empty_df)
        assert risk == "ingen"
    
    def test_create_time_blocks(self, sample_warnings):
        """Testa skapande av tidsblock."""
        blocks = create_enhanced_time_blocks(sample_warnings)
        
        assert len(blocks) > 0, "Inga tidsblock skapades"
        
        # Kontrollera struktur på första blocket
        first_block = blocks[0]
        required_keys = ['date', 'start_hour', 'end_hour', 'warnings', 'max_risk_level']
        
        for key in required_keys:
            assert key in first_block, f"Nyckel '{key}' saknas i tidsblock"
    
    def test_format_frost_warning_email(self, sample_warnings):
        """Testa formatering av frostvarnings-email."""
        subject, html_body = format_frost_warning_email(sample_warnings, "Test-plats")
        
        # Kontrollera subject
        assert "FROSTVARNING" in subject
        assert "Test-plats" in subject
        
        # Kontrollera HTML-innehåll
        assert "doctype html" in html_body.lower()
        assert "frostvarning" in html_body.lower()
        assert any(risk in html_body.lower() for risk in ["hög risk", "medel risk", "låg risk"])
    
    def test_format_email_empty_warnings(self):
        """Testa formatering med inga varningar."""
        empty_df = pd.DataFrame()
        subject, html_body = format_frost_warning_email(empty_df, "Test-plats")
        
        assert "Inga frostvarningar" in subject
        assert "Inga frostvarningar" in html_body


class TestEmailSafety:
    """Säkerhetstester för email-systemet."""
    
    def test_email_with_sensitive_data(self):
        """Testa att känslig data inte läcker i emails."""
        warnings_df = pd.DataFrame({
            'valid_time': [datetime.now()],
            'temperature_2m': [-1.0],
            'wind_speed_10m': [1.0],
            'frost_risk_level': ['hög'],
            'frost_risk_numeric': [3],
            'secret_field': ['HEMLIG_DATA']
        })
        
        subject, html_body = format_frost_warning_email(warnings_df, "Test")
        
        # Kontrollera att känslig data inte finns i email
        assert "HEMLIG_DATA" not in subject
        assert "HEMLIG_DATA" not in html_body
        assert "secret_field" not in html_body


if __name__ == "__main__":
    # Kör tester direkt om filen körs
    pytest.main([__file__, "-v"])