# tests/test_notifications.py
"""
Tester för notifikationssystemet.
Kör detta för att testa att både email och SMS fungerar.
"""
import sys
import os
import yaml
import pandas as pd
import pytest
from datetime import datetime
import unittest
from typing import Dict, Any

# Lägg till src-mappen i path för att kunna importera moduler
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from notification_manager import NotificationManager, create_notification_manager
# FIXAT: Ändrat från create_test_sms till create_frost_sms_message
from sms_notifier import create_frost_sms_message
from email_notifier import EmailNotifier


def load_test_config() -> Dict[str, Any]:
    """Ladda konfiguration för tester."""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Hittar inte config.yaml på: {config_path}")
        return {}


def create_fake_frost_warnings() -> pd.DataFrame:
    """Skapa fake frostvarningar för testning."""
    return pd.DataFrame({
        'valid_time': [
            datetime.now().replace(hour=23, minute=0),
            datetime.now().replace(hour=0, minute=0),
            datetime.now().replace(hour=6, minute=0)
        ],
        'temperature_2m': [-1.5, -2.0, -0.5],
        'wind_speed_10m': [0.8, 1.2, 0.5],
        'frost_risk_level': ['hög', 'hög', 'medel'],
        'frost_risk_numeric': [3, 3, 2],
        'frost_warning': [True, True, True]
    })


class TestNotificationManager(unittest.TestCase):
    """Unit tests för NotificationManager."""
    
    def setUp(self):
        """Sätt upp test-miljö."""
        self.config = load_test_config()
        if not self.config:
            self.skipTest("Ingen config tillgänglig")
    
    def test_manager_creation(self):
        """Testa att manager kan skapas."""
        manager = NotificationManager(self.config)
        self.assertIsNotNone(manager)
    
    def test_notifier_status(self):
        """Testa att status-check fungerar."""
        manager = NotificationManager(self.config)
        status = manager.get_notifier_status()
        
        self.assertIsInstance(status, dict)
        self.assertIn('email', status)
        self.assertIn('sms', status)
    
    def test_recipients_extraction(self):
        """Testa att mottagare extraheras korrekt."""
        manager = NotificationManager(self.config)
        
        email_recipients = manager.get_email_recipients()
        sms_recipients = manager.get_sms_recipients()
        
        self.assertIsInstance(email_recipients, list)
        self.assertIsInstance(sms_recipients, list)


def test_sms_connection():
    """Testa SMS-anslutning."""
    print("TESTAR SMS-ANSLUTNING")
    print("=" * 50)
    
    config = load_test_config()
    if not config:
        print("Ingen konfiguration")
        return False
    
    manager = NotificationManager(config)
    
    if not manager.sms_notifier:
        print("SMS-notifier inte konfigurerad")
        return False
    
    # Testa anslutning
    if manager.sms_notifier.test_connection():
        print("SMS-anslutning fungerar!")
        return True
    else:
        print("SMS-anslutning misslyckades")
        return False


def test_email_connection():
    """Testa email-anslutning."""
    print("\nTESTAR EMAIL-ANSLUTNING")
    print("=" * 50)
    
    config = load_test_config()
    if not config:
        print("Ingen konfiguration")
        return False
    
    manager = NotificationManager(config)
    
    if not manager.email_notifier:
        print("Email-notifier inte konfigurerad")
        return False
    
    # Testa anslutning
    if manager.email_notifier.test_connection():
        print("Email-anslutning fungerar!")
        return True
    else:
        print("Email-anslutning misslyckades")
        return False


@pytest.mark.skip(reason="Interaktiv test - kör manuellt")
def test_send_test_sms():
    """Skicka test-SMS."""
    print("\nSKICKAR TEST-SMS")
    print("=" * 50)
    
    config = load_test_config()
    manager = NotificationManager(config)
    
    if not manager.sms_notifier:
        print("SMS inte konfigurerat")
        return False
    
    recipients = manager.get_sms_recipients()
    if not recipients:
        print("Inga SMS-mottagare")
        return False
    
    # Fråga användaren
    print(f"Skicka test-SMS till {recipients}?")
    answer = input("Skriv 'ja' för att fortsätta: ").lower().strip()
    
    if answer not in ['ja', 'j', 'yes', 'y']:
        print("Test avbrutet")
        return True
    
    # FIXAT: Skapa test-SMS med create_frost_sms_message
    try:
        # Skapa fake frostvarningar för test-SMS
        test_warnings = pd.DataFrame({
            'valid_time': [datetime.now()],
            'temperature_2m': [-2.0],
            'wind_speed_10m': [1.0],
            'frost_risk_level': ['hög'],
            'frost_risk_numeric': [3]
        })
        
        test_message = create_frost_sms_message(test_warnings, "Test-plats")
        success = manager.sms_notifier.send_sms(recipients[0], test_message)
        
        if success:
            print("Test-SMS skickat! Kolla din telefon.")
            return True
        else:
            print("Test-SMS misslyckades")
            return False
    except Exception as e:
        print(f"Fel: {e}")
        return False


@pytest.mark.skip(reason="Interaktiv test - kör manuellt")
def test_send_frost_notifications():
    """Testa att skicka riktiga frostvarningar."""
    print("\nTESTAR FROSTVARNINGAR")
    print("=" * 50)
    
    config = load_test_config()
    manager = NotificationManager(config)
    
    # Skapa fake frostvarningar
    fake_warnings = create_fake_frost_warnings()
    
    print(f"Skapad fake frostvarning med {len(fake_warnings)} timmar")
    print("Kommer skicka till:")
    
    if manager.email_notifier:
        email_recipients = manager.get_email_recipients()
        print(f"  Email: {len(email_recipients)} mottagare")
    
    if manager.sms_notifier:
        sms_recipients = manager.get_sms_recipients()
        print(f"  SMS: {len(sms_recipients)} mottagare")
    
    # Fråga användaren
    answer = input("\nSkicka test-frostvarningar? (ja/nej): ").lower().strip()
    
    if answer not in ['ja', 'j', 'yes', 'y']:
        print("Test avbrutet")
        return True
    
    # Skicka notifikationer
    results = manager.send_all_notifications(fake_warnings)
    
    print(f"\nRESULTAT:")
    print(f"  Email: {'OK' if results['email'] else 'MISSLYCKADES'}")
    print(f"  SMS: {'OK' if results['sms'] else 'MISSLYCKADES'}")
    print(f"  Något skickat: {'JA' if results['any_sent'] else 'NEJ'}")
    
    if results['any_sent']:
        print("\nTest lyckades! Kolla din telefon och email.")
    
    return results['any_sent']


def run_interactive_tests():
    """Kör interaktiva tester där användaren kan välja."""
    print("FROSTVAKT NOTIFIKATIONS-TESTER")
    print("=" * 60)
    
    config = load_test_config()
    if not config:
        print("Kunde inte ladda konfiguration")
        return
    
    # Visa status
    manager = NotificationManager(config)
    status = manager.get_notifier_status()
    
    print(f"SYSTEM STATUS:")
    print(f"  Email: {'Aktivt' if status['email'] else 'Inaktivt'}")
    print(f"  SMS: {'Aktivt' if status['sms'] else 'Inaktivt'}")
    
    if not manager.is_any_notifier_active():
        print("\nInga notifiers är aktiva. Kontrollera config.yaml")
        return
    
    while True:
        print(f"\n{'='*60}")
        print("VALJ TEST:")
        print("1. Testa anslutningar")
        print("2. Skicka test-SMS")
        print("3. Skicka test-frostvarningar")
        print("4. Kor alla tester")
        print("0. Avsluta")
        
        choice = input("\nValj (0-4): ").strip()
        
        if choice == '0':
            print("Avslutar tester")
            break
        elif choice == '1':
            test_sms_connection()
            test_email_connection()
        elif choice == '2':
            test_send_test_sms()
        elif choice == '3':
            test_send_frost_notifications()
        elif choice == '4':
            test_sms_connection()
            test_email_connection()
            test_send_test_sms()
            test_send_frost_notifications()
        else:
            print("Ogiltigt val")


if __name__ == "__main__":
    # Kör interaktiva tester
    run_interactive_tests()