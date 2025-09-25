# src/advanced_frost_analyzer.py
"""
Frostanalys med validerad algoritm
===================================
Använder den algoritm som visade bäst resultat i utvärderingen (F1=0.852)

funktioner:
- temperatur
- dagtidsfilter (08-17) vid plusgrader
- dynamiska tröskelvärden baserat på molntäcke
- luftfuktighet
"""
import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any
import logging

logger = logging.getLogger("frostvakt.advanced_frost_analyzer")


def calculate_cloud_impact_factor(cloud_cover: float) -> float:
    """
    Beräkna molnpåverkansfaktor för frostrisk.
    
    Klar himmel (lågt molntäcke) ökar frostrisk genom strålningsförlust.
    Mulet väder (högt molntäcke) minskar frostrisk genom isolering.
    
    Args:
        cloud_cover: Molntäcke i procent (0-100)
        
    Returns:
        Faktor mellan 0.7 (mulet) och 1.5 (klart)
    """
    if pd.isna(cloud_cover):
        return 1.0
    
    if cloud_cover <= 20:
        return 1.5  # Klar himmel - stor strålningsförlust
    elif cloud_cover <= 50:
        return 1.2  # Halvklart - viss strålningsförlust
    elif cloud_cover <= 80:
        return 1.0  # Mestadels mulet - neutral
    else:
        return 0.7  # Mulet - molntäcke isolerar


def calculate_advanced_frost_risk(temperature: float, wind_speed: float, 
                                cloud_cover: float, humidity: float = None, 
                                hour_of_day: int = None) -> Tuple[str, int, Dict[str, Any]]:
    """
    Beräkna frostrisk
    
    algoritm:
    1. dagtidsfilter: ingen varning 08-17 vid plusgrader
    2. grundrisk: temp ≤ 0°C → hög risk
    3. dynamiska trösklar baserat på molntäcke:
       - klart (faktor ≥1.4): temp ≤ 3°C + vindstilla → varning
       - halvklart (faktor ≥1.1): temp ≤ 2°C + vindstilla → varning  
       - mulet: temp ≤ 1°C + vindstilla → varning
    4. extra check: temp ≤ 2°C + vind < 3 m/s + fuktighet > 85% → varning
    
    Args:
        temperature: Direkttemperatur i Celsius
        wind_speed: Vindhastighet i m/s
        cloud_cover: Molntäcke i procent
        humidity: Relativ luftfuktighet i procent (optional)
        hour_of_day: Timme på dygnet 0-23 (optional, för dagtidsfilter)
        
    Returns:
        Tuple med (risk_level_text, risk_level_numeric, details_dict)
        - risk_level_text: "ingen", "låg", "medel", "hög"
        - risk_level_numeric: 0-3
        - details_dict: Detaljerad information om bedömningen
    """
    # Hantera saknade värden
    if pd.isna(temperature) or pd.isna(wind_speed):
        return "okänd", 0, {"reason": "Saknade temperatur- eller vinddata"}
    
    # dagtidsfilter: skippa frost på dagtid (08-17) vid plusgrader
    if hour_of_day is not None and 8 <= hour_of_day <= 17:
        if temperature > 0:
            return "ingen", 0, {
                "reason": f"Dagtid (kl {hour_of_day:02d}) med plusgrader ({temperature:.1f}°C)",
                "note": "Solstrålning förhindrar frost",
                "daytime_filter": True,
                "algorithm": "komplett"
            }


    # 1. grundrisk: temperatur under fryspunkten
    if temperature <= 0:
        return "hög", 3, {
            "reason": f"Temperatur {temperature:.1f}°C ≤ 0°C",
            "algorithm": "komplett",
            "temp": temperature,
            "wind": wind_speed,
            "cloud_cover": cloud_cover,
            "humidity": humidity
        }
    
    # 2. molnpåverkan: dynamiska tröskelvärden
    cloud_factor = calculate_cloud_impact_factor(cloud_cover)
    
    # Bestäm temperaturtröskel baserat på molnförhållanden
    if cloud_factor >= 1.4:  # Klar himmel
        temp_limit = 3.0
        risk_level = "låg"
        risk_numeric = 1
    elif cloud_factor >= 1.1:  # Halvklart
        temp_limit = 2.0
        risk_level = "medel"
        risk_numeric = 2
    else:  # Mulet
        temp_limit = 1.0
        risk_level = "medel"
        risk_numeric = 2
    
    if temperature <= temp_limit and wind_speed < 4:
        return risk_level, risk_numeric, {
            "reason": f"Temperatur {temperature:.1f}°C ≤ {temp_limit}°C + vindstilla ({wind_speed:.1f} m/s)",
            "cloud_factor": cloud_factor,
            "cloud_condition": "klart" if cloud_factor >= 1.4 else "halvklart" if cloud_factor >= 1.1 else "mulet",
            "algorithm": "komplett",
            "temp": temperature,
            "wind": wind_speed,
            "cloud_cover": cloud_cover,
            "humidity": humidity
        }
    
    # 3. extra check: luftfuktighet
    if not pd.isna(humidity) and temperature <= 2 and wind_speed < 3 and humidity > 85:
        return "medel", 2, {
            "reason": f"Temperatur {temperature:.1f}°C + låg vind ({wind_speed:.1f} m/s) + hög fuktighet ({humidity:.0f}%)",
            "note": "Kondensrisk vid hög luftfuktighet",
            "algorithm": "komplett",
            "temp": temperature,
            "wind": wind_speed,
            "cloud_cover": cloud_cover,
            "humidity": humidity
        }
    
    # Ingen risk
    return "ingen", 0, {
        "reason": f"Temperatur {temperature:.1f}°C för hög eller för mycket vind ({wind_speed:.1f} m/s)",
        "algorithm": "komplett",
        "temp": temperature,
        "wind": wind_speed,
        "cloud_cover": cloud_cover,
        "humidity": humidity
    }


def analyze_dataframe_advanced(df: pd.DataFrame) -> pd.DataFrame:
    """
    Analysera DataFrame med validerad "komplett" frostalgoritm.
    
    Använder direkttemperatur för bästa prestanda (F1=0.852).
    
    Args:
        df: DataFrame med kolumner 'temperature_2m', 'wind_speed_10m', 'cloud_cover'
        
    Returns:
        DataFrame med frostkolumner:
        - frost_risk_level: Text (ingen/låg/medel/hög)
        - frost_risk_numeric: Numerisk (0-3)
        - frost_warning: Boolean (True om risk > 0)
        - frost_details: Dictionary med detaljer
    """
    if df.empty:
        logger.warning("Tom DataFrame skickad till frost-analys")
        return df
    
    required_cols = ['temperature_2m', 'wind_speed_10m']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        logger.error(f"Saknar kolumner för frost-analys: {missing_cols}")
        return df
    
    result_df = df.copy()
    
    # Sätt default för molntäcke om det saknas
    if 'cloud_cover' not in result_df.columns:
        result_df['cloud_cover'] = 50.0
    
    has_humidity = 'relative_humidity_2m' in result_df.columns and not result_df['relative_humidity_2m'].isna().all()
    
    frost_results = []
    frost_details = []
    
    for _, row in result_df.iterrows():
        humidity = row.get('relative_humidity_2m') if has_humidity else None
        
        # Extrahera timme för dagtidsfilter
        hour_of_day = None
        if 'valid_time' in row.index and pd.notna(row['valid_time']):
            try:
                if hasattr(row['valid_time'], 'hour'):
                    hour_of_day = row['valid_time'].hour
                else:
                    hour_of_day = pd.to_datetime(row['valid_time']).hour
            except:
                pass
        
        # Kör frostanalys med direkttemperatur
        risk_text, risk_numeric, details = calculate_advanced_frost_risk(
            row['temperature_2m'],   # Direkttemperatur
            row['wind_speed_10m'], 
            row.get('cloud_cover', 50.0),
            humidity,
            hour_of_day
        )
        frost_results.append((risk_text, risk_numeric))
        frost_details.append(details)
    
    result_df['frost_risk_level'] = [result[0] for result in frost_results]
    result_df['frost_risk_numeric'] = [result[1] for result in frost_results]
    result_df['frost_warning'] = result_df['frost_risk_numeric'] > 0
    result_df['frost_details'] = frost_details
    
    warning_count = sum(result_df['frost_warning'])
    
    if warning_count > 0:
        logger.info(f"Frostanalys: {warning_count}/{len(result_df)} timmar har risk")
    
    return result_df


def get_frost_explanation(frost_details: Dict[str, Any]) -> str:
    """
    Skapa lättläst förklaring av frostanalys för email/logg.
    
    Args:
        frost_details: Details dictionary från calculate_advanced_frost_risk
        
    Returns:
        Formaterad textsträng med förklaring
    """
    if not frost_details:
        return "Ingen detaljerad information tillgänglig"
    
    explanation = []
    
    # Huvudorsak
    if 'reason' in frost_details:
        explanation.append(f"Orsak: {frost_details['reason']}")
    
    # Detaljerad väderinfo
    if 'temp' in frost_details:
        explanation.append(f"Temperatur: {frost_details['temp']:.1f}°C")
    
    if 'wind' in frost_details:
        explanation.append(f"Vindhastighet: {frost_details['wind']:.1f} m/s")
    
    if 'cloud_cover' in frost_details and not pd.isna(frost_details['cloud_cover']):
        explanation.append(f"Molntäcke: {frost_details['cloud_cover']:.0f}%")
        if 'cloud_condition' in frost_details:
            explanation.append(f"Molnförhållande: {frost_details['cloud_condition']}")
    
    if 'humidity' in frost_details and not pd.isna(frost_details['humidity']):
        explanation.append(f"Luftfuktighet: {frost_details['humidity']:.0f}%")
    
    # Extra noteringar
    if 'note' in frost_details:
        explanation.append(f"OBS: {frost_details['note']}")
    
    # Algoritm-info (för debugging)
    if 'algorithm' in frost_details:
        explanation.append(f"Algoritm: {frost_details['algorithm']}")
    
    return "\n".join(explanation)
