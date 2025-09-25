# src/notification_manager.py
"""
Central hantering av alla notifikationer för frostvakt-systemet.
Koordinerar email och SMS
"""
import pandas as pd
from typing import Dict, Any, List
import logging
from datetime import datetime

from email_notifier import EmailNotifier, send_frost_notification
from sms_notifier import create_twilio_notifier, send_frost_sms_notification

logger = logging.getLogger("frostvakt.notification_manager")


class NotificationManager:
    """Central hantering av alla notifikationer."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initiera notification manager med konfiguration.
        
        Args:
            config: Komplett konfiguration från config.yaml
        """
        self.config = config
        self.email_notifier = None
        self.sms_notifier = None
        
        self._setup_email_notifier()
        self._setup_sms_notifier()
        
        logger.debug("NotificationManager initierad")
    
    def _setup_email_notifier(self) -> None:
        """Sätt upp email-notifier om aktiverat."""
        email_config = self.config.get('email', {})
        
        if not email_config.get('enabled', False):
            logger.debug("Email-notifikationer inaktiverade")
            return
        
        try:
            self.email_notifier = EmailNotifier(
                smtp_server=email_config['smtp_server'],
                smtp_port=email_config['smtp_port'],
                sender_email=email_config['sender_email'],
                sender_password=email_config['sender_password']
            )
            
            if self.email_notifier.test_connection():
                logger.debug("Email-notifier konfigurerad och testad")
            else:
                logger.error("Email-notifier anslutning misslyckades")
                self.email_notifier = None
                
        except KeyError as e:
            logger.error(f"Email konfigurationfel - saknar: {e}")
        except Exception as e:
            logger.error(f"Email setup fel: {e}")
    
    def _setup_sms_notifier(self) -> None:
        """Sätt upp SMS-notifier om aktiverat."""
        sms_config = self.config.get('sms', {})
        
        if not sms_config.get('enabled', False):
            logger.debug("SMS-notifikationer inaktiverade")
            return
        
        try:
            twilio_config = sms_config['twilio']
            self.sms_notifier = create_twilio_notifier(
                account_sid=twilio_config['account_sid'],
                auth_token=twilio_config['auth_token'],
                from_number=twilio_config['from_number']
            )
            
            if self.sms_notifier.test_connection():
                logger.debug("SMS-notifier konfigurerad och testad")
            else:
                logger.error("SMS-notifier anslutning misslyckades")
                self.sms_notifier = None
                
        except KeyError as e:
            logger.error(f"SMS konfigurationfel - saknar: {e}")
        except Exception as e:
            logger.error(f"SMS setup fel: {e}")
    
    def get_email_recipients(self) -> List[str]:
        """Hämta email-mottagare från config."""
        email_config = self.config.get('email', {})
        return email_config.get('recipients', [])
    
    def get_sms_recipients(self) -> List[str]:
        """Hämta aktiverade SMS-mottagare från config."""
        sms_config = self.config.get('sms', {})
        recipients = sms_config.get('recipients', [])
        
        active_numbers = []
        for recipient in recipients:
            if recipient.get('enabled', False):
                active_numbers.append(recipient['number'])
        
        logger.debug(f"{len(active_numbers)} SMS-mottagare aktiverade")
        return active_numbers
    
    def get_location_name(self) -> str:
        """Hämta platsnamn för notifikationer."""
        return (self.config.get('email', {})
                .get('notifications', {})
                .get('location_name', 'Din trakt'))
    
    def is_any_notifier_active(self) -> bool:
        """Kontrollera om någon notifier är aktiv."""
        return self.email_notifier is not None or self.sms_notifier is not None
    
    def get_notifier_status(self) -> Dict[str, bool]:
        """Få status för alla notifiers."""
        return {
            'email': self.email_notifier is not None,
            'sms': self.sms_notifier is not None
        }
    
    def send_email_notifications(self, warnings_df: pd.DataFrame) -> bool:
        """
        Skicka email-notifikationer.
        
        Args:
            warnings_df: DataFrame med frostvarningar
            
        Returns:
            True om email skickades framgångsrikt
        """
        if not self.email_notifier:
            logger.debug("Email-notifier inte tillgänglig")
            return False
        
        recipients = self.get_email_recipients()
        if not recipients:
            logger.debug("Inga email-mottagare konfigurerade")
            return False
        
        try:
            location = self.get_location_name()
            success = send_frost_notification(warnings_df, self.email_notifier, recipients, location)
            
            if success:
                logger.debug(f"Email skickat till {len(recipients)} mottagare")
            else:
                logger.error("Email-sändning misslyckades")
            
            return success
            
        except Exception as e:
            logger.error(f"Email-notifikation fel: {e}")
            return False
    
    def send_sms_notifications(self, warnings_df: pd.DataFrame) -> bool:
        """
        Skicka SMS-notifikationer.
        
        Args:
            warnings_df: DataFrame med frostvarningar
            
        Returns:
            True om SMS skickades framgångsrikt
        """
        if not self.sms_notifier:
            logger.debug("SMS-notifier inte tillgänglig")
            return False
        
        recipients = self.get_sms_recipients()
        if not recipients:
            logger.debug("Inga SMS-mottagare aktiverade")
            return False
        
        try:
            location = self.get_location_name()
            success = send_frost_sms_notification(warnings_df, self.sms_notifier, recipients, location)
            
            if success:
                logger.debug(f"SMS skickat till {len(recipients)} mottagare")
            else:
                logger.error("SMS-sändning misslyckades")
            
            return success
            
        except Exception as e:
            logger.error(f"SMS-notifikation fel: {e}")
            return False
    
    def send_all_notifications(self, warnings_df: pd.DataFrame) -> Dict[str, bool]:
        """
        Skicka alla typer av notifikationer.
        
        Args:
            warnings_df: DataFrame med frostvarningar
            
        Returns:
            Dictionary med resultat: {'email': bool, 'sms': bool, 'any_sent': bool}
        """
        if warnings_df.empty:
            logger.debug("Inga frostvarningar att skicka")
            return {'email': False, 'sms': False, 'any_sent': False}
        
        logger.debug(f"Skickar notifikationer för {len(warnings_df)} frostvarningar")
        
        email_success = self.send_email_notifications(warnings_df)
        sms_success = self.send_sms_notifications(warnings_df)
        
        any_sent = email_success or sms_success
        
        results = {
            'email': email_success,
            'sms': sms_success, 
            'any_sent': any_sent
        }
        
        if any_sent:
            logger.debug(f"Notifikationer skickade - Email: {email_success}, SMS: {sms_success}")
        else:
            logger.warning("Inga notifikationer kunde skickas")
        
        return results


def create_notification_manager(config: Dict[str, Any]) -> NotificationManager:
    """
    Skapa och konfigurera NotificationManager.
    
    Args:
        config: Komplett konfiguration
        
    Returns:
        Konfigurerad NotificationManager instans
    """
    return NotificationManager(config)