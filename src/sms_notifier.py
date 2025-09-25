# src/sms_notifier.py
"""
SMS-notifikationssystem för frostvarningar.
Skickar SMS via Twilio när frost upptäcks i prognoser.
"""
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta
import pandas as pd

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger("frostvakt.sms_notifier")


class SmsNotifier:
    """Hanterar SMS-notifikationer för frostvarningar."""
    
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        """
        Initiera SMS-notifier med Twilio.
        
        Args:
            account_sid: Twilio Account SID
            auth_token: Twilio Auth Token
            from_number: Twilio telefonnummer att skicka från
        """
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number
        
        logger.debug(f"SMS-notifier konfigurerad med nummer: {from_number}")
    
    def test_connection(self) -> bool:
        """Testa Twilio-anslutning."""
        try:
            account = self.client.api.accounts(self.client.account_sid).fetch()
            logger.debug(f"Twilio-anslutning OK: {account.friendly_name}")
            return True
        except TwilioRestException as e:
            logger.error(f"Twilio-anslutning misslyckades: {e}")
            return False
    
    def send_sms(self, to_number: str, message: str) -> bool:
        """
        Skicka SMS till ett telefonnummer.
        
        Args:
            to_number: Mottagarens telefonnummer (internationellt format)
            message: Meddelande att skicka (max 160 tecken rekommenderat)
            
        Returns:
            True om framgångsrikt skickat
        """
        try:
            msg = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number
            )
            logger.debug(f"SMS skickat till {to_number}: {msg.sid}")
            return True
            
        except TwilioRestException as e:
            logger.error(f"SMS till {to_number} misslyckades: {e}")
            return False
    
    def send_bulk_sms(self, recipients: List[str], message: str) -> Dict[str, bool]:
        """
        Skicka samma SMS till flera mottagare.
        
        Args:
            recipients: Lista med telefonnummer
            message: Meddelande att skicka
            
        Returns:
            Dictionary med resultat per mottagare
        """
        results = {}
        
        for number in recipients:
            success = self.send_sms(number, message)
            results[number] = success
        
        successful = sum(results.values())
        if successful < len(recipients):
            logger.warning(f"SMS delvis misslyckades: {successful}/{len(recipients)} lyckades")
        
        return results


def create_frost_sms_message(warnings_df: pd.DataFrame, location: str = "Din trakt") -> str:
    """
    Skapa kort SMS-meddelande för frostvarning.
    
    Args:
        warnings_df: DataFrame med frostvarningar
        location: Platsnamn
        
    Returns:
        SMS-meddelande (max 160 tecken rekommenderat)
    """
    if warnings_df.empty:
        return ""
    
    max_risk = warnings_df['frost_risk_numeric'].max()
    warning_count = len(warnings_df)
    
    now = datetime.now()
    first_warning_time = pd.to_datetime(warnings_df.iloc[0]['valid_time'])
    
    if first_warning_time.date() == now.date():
        time_text = "idag"
    elif first_warning_time.date() == (now + timedelta(days=1)).date():
        time_text = "imorgon"
    else:
        time_text = first_warning_time.strftime("%d/%m")
    
    if max_risk >= 3:
        risk_text = "HÖG RISK"
        emoji = "🚨"
    elif max_risk >= 2:
        risk_text = "MEDEL RISK"
        emoji = "⚠️"
    else:
        risk_text = "LÅG RISK"
        emoji = "❄️"
    
    min_temp = warnings_df['temperature_2m'].min()
    avg_wind = warnings_df['wind_speed_10m'].mean()
    
    if warning_count == 1:
        duration_text = "1 timme"
    elif warning_count <= 6:
        duration_text = f"{warning_count} timmar"
    else:
        duration_text = "flera timmar"
    
    if avg_wind < 2:
        wind_text = "svag vind"
    elif avg_wind < 4:
        wind_text = "måttlig vind"
    else:
        wind_text = "kraftig vind"
    
    if max_risk >= 3:
        action = "Täck växter NU!"
    elif max_risk >= 2:
        action = "Förbered skydd!"
    else:
        action = "Håll koll!"
    
    if warning_count == 1:
        message = f"{emoji} FROST {risk_text} {time_text}. Temp {min_temp:.0f}°C, {wind_text}. {action} MVH {location}"
    else:
        message = f"{emoji} FROST {risk_text} {duration_text}. Temp {min_temp:.0f}°C, {wind_text}. {action} MVH {location}"
    
    if len(message) > 160:
        message = f"{emoji} FROST {risk_text}. Temp {min_temp:.0f}°C. {action} MVH {location}"
    
    return message


def send_frost_sms_notification(warnings_df: pd.DataFrame, notifier: SmsNotifier, 
                                recipients: List[str], location: str = "Grannfrostvakt") -> bool:
    """
    Skicka frostvarning via SMS.
    
    Args:
        warnings_df: DataFrame med frostvarningar
        notifier: SmsNotifier instans
        recipients: Lista med telefonnummer
        location: Platsnamn för signatur
        
    Returns:
        True om minst ett SMS skickades framgångsrikt
    """
    if warnings_df.empty:
        logger.debug("Inga frostvarningar att skicka")
        return False
    
    if not recipients:
        logger.debug("Inga SMS-mottagare konfigurerade")
        return False
    
    message = create_frost_sms_message(warnings_df, location)
    
    if not message:
        logger.error("Kunde inte skapa SMS-meddelande")
        return False
    
    logger.debug(f"SMS-meddelande skapat: {message}")
    logger.debug(f"Längd: {len(message)} tecken")
    
    results = notifier.send_bulk_sms(recipients, message)
    
    successful = sum(results.values())
    
    if successful > 0:
        logger.debug(f"SMS frostvarning skickad till {successful}/{len(recipients)} mottagare")
        return True
    else:
        logger.error("Alla SMS misslyckades")
        return False


def create_twilio_notifier(account_sid: str, auth_token: str, from_number: str) -> SmsNotifier:
    """
    Convenience-funktion för att skapa SmsNotifier.
    
    Args:
        account_sid: Twilio Account SID
        auth_token: Twilio Auth Token
        from_number: Twilio telefonnummer
        
    Returns:
        Konfigurerad SmsNotifier instans
    """
    return SmsNotifier(account_sid, auth_token, from_number)