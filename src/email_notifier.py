# src/email_notifier.py
"""
Email-notifikationssystem för frostvarningar.
Skickar email via SMTP när frost upptäcks i prognoser.
"""
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
import logging

logger = logging.getLogger("frostvakt.email_notifier")


class EmailNotifier:
    """Hanterar email-notifikationer för frostvarningar."""
    
    def __init__(self, smtp_server: str, smtp_port: int, sender_email: str, sender_password: str):
        """
        Initiera email-notifier.
        
        Args:
            smtp_server: SMTP server (t.ex. smtp.gmail.com)
            smtp_port: Port (587 för TLS)
            sender_email: Avsändar email
            sender_password: App-lösenord eller vanligt lösenord
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        
        logger.debug(f"Email-notifier konfigurerad: {sender_email} via {smtp_server}:{smtp_port}")
    
    def test_connection(self) -> bool:
        """Testa email-anslutning utan att skicka meddelande."""
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.sender_email, self.sender_password)
            
            logger.debug("Email-anslutning testad framgångsrikt")
            return True
            
        except Exception as e:
            logger.error(f"Email-anslutning misslyckades: {e}")
            return False
    
    def send_email(self, recipients: List[str], subject: str, body_html: str, body_text: str = None) -> bool:
        """
        Skicka email till mottagare.
        
        Args:
            recipients: Lista med email-adresser
            subject: Email-rubrik
            body_html: HTML-formaterat meddelande
            body_text: Text-version (optional)
            
        Returns:
            True om framgångsrikt skickat
        """
        try:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.sender_email
            message["To"] = ", ".join(recipients)
            
            if body_text is None:
                import re
                body_text = re.sub('<[^<]+?>', '', body_html)
                body_text = body_text.replace('&nbsp;', ' ').strip()
            
            text_part = MIMEText(body_text, "plain", "utf-8")
            html_part = MIMEText(body_html, "html", "utf-8")
            
            message.attach(text_part)
            message.attach(html_part)
            
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, recipients, message.as_string())
            
            logger.debug(f"Email skickat till {len(recipients)} mottagare: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Fel vid email-sändning: {e}")
            return False


def get_friendly_date(date_time: datetime) -> str:
    """Konvertera datetime till vänligt format."""
    now = datetime.now()
    today = now.date()
    target_date = date_time.date()
    
    if target_date == today:
        return f"Idag {target_date.strftime('%Y-%m-%d')}"
    elif target_date == today + timedelta(days=1):
        return f"I morgon {target_date.strftime('%Y-%m-%d')}"
    elif target_date == today + timedelta(days=2):
        return f"I övermorgon {target_date.strftime('%Y-%m-%d')}"
    else:
        weekdays = ["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag", "Lördag", "Söndag"]
        weekday = weekdays[target_date.weekday()]
        return f"{weekday} {target_date.strftime('%Y-%m-%d')}"


def create_enhanced_time_blocks(warnings_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Gruppera frostvarningar i 2-timmarsblock."""
    if warnings_df.empty:
        return []
    
    df = warnings_df.copy()
    df['valid_time'] = pd.to_datetime(df['valid_time'])
    df = df.sort_values('valid_time')
    
    blocks = []
    current_block = None
    
    for _, row in df.iterrows():
        hour = row['valid_time'].hour
        block_start = (hour // 2) * 2
        block_key = f"{row['valid_time'].date()}_{block_start:02d}"
        
        if current_block is None or current_block['key'] != block_key:
            if current_block is not None:
                blocks.append(current_block)
            
            current_block = {
                'key': block_key,
                'date': row['valid_time'].date(),
                'start_hour': block_start,
                'end_hour': block_start + 2,
                'friendly_date': get_friendly_date(row['valid_time']),
                'warnings': [],
                'max_risk_level': row['frost_risk_level'],
                'max_risk_numeric': row['frost_risk_numeric'],
                'min_temp': row.get('temp_rolling_mean', row['temperature_2m']),
                'max_temp': row.get('temp_rolling_mean', row['temperature_2m']),
                'avg_cloud_cover': row.get('cloud_cover', 50),
                'cloud_count': 1 if not pd.isna(row.get('cloud_cover')) else 0
            }
        
        warning_data = {
            'time': row['valid_time'],
            'temp': row['temperature_2m'],
            'temp_rolling': row.get('temp_rolling_mean', row['temperature_2m']),
            'wind': row['wind_speed_10m'],
            'cloud_cover': row.get('cloud_cover'),
            'risk': row['frost_risk_level']
        }
        current_block['warnings'].append(warning_data)
        
        if row['frost_risk_numeric'] > current_block['max_risk_numeric']:
            current_block['max_risk_level'] = row['frost_risk_level']
            current_block['max_risk_numeric'] = row['frost_risk_numeric']
        
        temp_value = row.get('temp_rolling_mean', row['temperature_2m'])
        current_block['min_temp'] = min(current_block['min_temp'], temp_value)
        current_block['max_temp'] = max(current_block['max_temp'], temp_value)
        
        if not pd.isna(row.get('cloud_cover')):
            total_cloud = current_block['avg_cloud_cover'] * current_block['cloud_count']
            current_block['cloud_count'] += 1
            current_block['avg_cloud_cover'] = (total_cloud + row['cloud_cover']) / current_block['cloud_count']
    
    if current_block is not None:
        blocks.append(current_block)
    
    return blocks


def get_cloud_cover_description(cloud_cover: float) -> str:
    """Konvertera molntäcke till beskrivande text."""
    if pd.isna(cloud_cover):
        return "okänt"
    elif cloud_cover <= 20:
        return "klar himmel ⭐"
    elif cloud_cover <= 50:
        return "lätt molnigt ⛅"
    elif cloud_cover <= 80:
        return "molnigt ☁️"
    else:
        return "mulet 🌫️"


def get_highest_risk_next_24h(warnings_df: pd.DataFrame) -> str:
    """Hitta högsta frostrisknivå för närmaste 24 timmarna."""
    if warnings_df.empty:
        return "ingen"
    
    now = datetime.now()
    next_24h = now + timedelta(hours=24)
    
    df = warnings_df.copy()
    df['valid_time'] = pd.to_datetime(df['valid_time'])
    next_24h_warnings = df[
        (df['valid_time'] >= now) & 
        (df['valid_time'] <= next_24h)
    ]
    
    if next_24h_warnings.empty:
        return "ingen"
    
    max_risk = next_24h_warnings['frost_risk_numeric'].max()
    
    if max_risk >= 3:
        return "hög"
    elif max_risk >= 2:
        return "medel"
    elif max_risk >= 1:
        return "låg"
    else:
        return "ingen"


def format_frost_warning_email(warnings_df: pd.DataFrame, location: str = "Väderstation") -> tuple[str, str]:
    """Formatera frostvarning som HTML-email."""
    if warnings_df.empty:
        return "Inga frostvarningar", "<p>Inga frostvarningar för tillfället.</p>"
    
    highest_risk = get_highest_risk_next_24h(warnings_df)
    
    if highest_risk == 'hög':
        risk_emoji = "🚨"
        risk_text = "HÖG FROSTRISK"
        color = "#ff4444"
    elif highest_risk == 'medel':
        risk_emoji = "⚠️"
        risk_text = "MEDEL FROSTRISK"  
        color = "#ff8800"
    else:
        risk_emoji = "❄️"
        risk_text = "LÅG FROSTRISK"
        color = "#4488ff"
    
    subject = f"{risk_emoji} FROSTVARNING {location} - {risk_text}"
    
    time_blocks = create_enhanced_time_blocks(warnings_df)[:8]
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .header {{ background-color: {color}; color: white; padding: 20px; text-align: center; }}
            .content {{ padding: 20px; }}
            .summary {{ background-color: #e8f4f8; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            .time-block {{ margin: 15px 0; padding: 15px; border-radius: 5px; }}
            .high-risk {{ background-color: #ffe6e6; border-left: 5px solid #ff4444; }}
            .medium-risk {{ background-color: #fff3e6; border-left: 5px solid #ff8800; }}
            .low-risk {{ background-color: #e6f3ff; border-left: 5px solid #4488ff; }}
            .block-header {{ font-weight: bold; margin-bottom: 8px; }}
            .weather-details {{ font-size: 0.9em; color: #666; margin-top: 5px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>{risk_emoji} FROSTVARNING - {location.upper()}</h1>
            <p>{datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        </div>
        
        <div class="content">
            <div class="summary">
                <h2>📊 Sammanfattning närmaste 24h</h2>
                <p><strong>Frostrisknivå:</strong> <span style="color: {color}; font-weight: bold;">{highest_risk.upper()} RISK</span></p>
            </div>
    """
    
    if time_blocks:
        html_body += """
            <h2>🕐 Detaljerade frostvarningar</h2>
            <p>Visas som 2-timmarsblock:</p>
        """
        
        for block in time_blocks:
            risk = block['max_risk_level']
            css_class = "high-risk" if risk == 'hög' else "medium-risk" if risk == 'medel' else "low-risk"
            
            time_range = f"{block['start_hour']:02d}:00-{block['end_hour']:02d}:00"
            
            if block['min_temp'] == block['max_temp']:
                temp_text = f"{block['min_temp']:.1f}°C"
            else:
                temp_text = f"{block['min_temp']:.1f} till {block['max_temp']:.1f}°C"
            
            cloud_desc = get_cloud_cover_description(block['avg_cloud_cover'])
            cloud_impact = ""
            if block['avg_cloud_cover'] <= 20:
                cloud_impact = " (ökar frostrisk)"
            elif block['avg_cloud_cover'] >= 80:
                cloud_impact = " (minskar frostrisk)"
            
            html_body += f"""
                <div class="time-block {css_class}">
                    <div class="block-header">
                        {block['friendly_date']} kl {time_range} - {risk.upper()} RISK
                    </div>
                    <div class="weather-details">
                        🌡️ Temperatur: {temp_text}<br>
                        ☁️ Molntäcke: {block['avg_cloud_cover']:.0f}% ({cloud_desc}){cloud_impact}<br>
                    </div>
                </div>
            """
    
    html_body += f"""
        <h2>💡 Rekommendationer</h2>
        <div style="background-color: #f0f8ff; padding: 15px; border-radius: 5px; border-left: 5px solid {color};">
    """
    
    if highest_risk == 'hög':
        html_body += """
            <strong>🚨 HÖG FROSTRISK - Akuta åtgärder:</strong>
            <ul>
                <li>🛡️ Täck känsliga växter med duk eller plast omedelbart</li>
                <li>💧 Vattna jorden runt växter (fuktig jord håller värme bättre)</li>
                <li>🚗 Förbered för bilskrapning på morgonen</li>
                <li>⚠️ Extra försiktighet på vägarna - risk för halka</li>
            </ul>
        """
    elif highest_risk == 'medel':
        html_body += """
            <strong>⚠️ MEDEL FROSTRISK - Förberedelser:</strong>
            <ul>
                <li>🌱 Förbered skydd för känsliga växter</li>
                <li>🚗 Kontrollera så bilrutan är ren</li>
                <li>👀 Håll utkik efter frost på morgonen</li>
            </ul>
        """
    else:
        html_body += """
            <strong>❄️ LÅG FROSTRISK - Övervaka läget:</strong>
            <ul>
                <li>👁️ Håll koll på temperaturutvecklingen</li>
                <li>🌿 Robusta växter klarar sig troligen bra</li>
                <li>⏰ Ny prognos kommer snart</li>
            </ul>
        """
    
    html_body += """
            </div>
        </div>
        
        <div style="background-color: #f5f5f5; padding: 15px; text-align: center; font-size: 0.9em; color: #666;">
            <p>📡 Baserat på väderdata från Open-Meteo API</p>
        </div>
    </body>
    </html>
    """
    
    return subject, html_body


def send_frost_notification(warnings_df: pd.DataFrame, notifier: EmailNotifier, 
                          recipients: List[str], location: str = "Din väderstation") -> bool:
    """
    Skicka frostvarning via email.
    
    Args:
        warnings_df: DataFrame med frostvarningar
        notifier: EmailNotifier instans
        recipients: Lista med email-mottagare
        location: Platsnamn
        
    Returns:
        True om meddelande skickades framgångsrikt
    """
    if warnings_df.empty:
        logger.debug("Inga frostvarningar att skicka")
        return False
    
    subject, html_body = format_frost_warning_email(warnings_df, location)
    
    success = notifier.send_email(recipients, subject, html_body)
    
    if success:
        logger.debug(f"Frostvarning skickad till {len(recipients)} mottagare")
    else:
        logger.error("Kunde inte skicka frostvarning")
    
    return success