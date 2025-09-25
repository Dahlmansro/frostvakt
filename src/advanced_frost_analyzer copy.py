# src/advanced_frost_analyzer.py
"""
Frostanalys med validerad algoritm
===================================
Använder den algoritm som visade bäst resultat i utvärderingen 

Funktioner:
- Dagtidsfilter (08-17) vid temperatur över 3 grader
- Dynamiska tröskelvärden baserat på molntäcke
- Luftfuktighet för extra precision
"""
import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any
import logging

logger = logging.getLogger("frostvakt.advanced_frost_analyzer")


def calculate_rolling_mean_temperature(df: pd.DataFrame, hours: int = 3) -> pd.DataFrame:
    """
    Beräkna rullande medeltemperatur över de senaste X timmarna.
    Ger stabilare temperaturmått än enskilda värden.
    
    Args:
        df: DataFrame med temperaturdata
        hours: Antal timmar för rullande medelvärde (default: 3)
        
    Returns:
        DataFrame med tillagd 'temp_rolling_mean' kolumn
    """
    if df.empty or 'temperature_2m' not in df.columns:
        return df
    
    df_copy = df.copy()
    
    if 'valid_time' in df_copy.columns:
        df_copy = df_copy.sort_values('valid_time')
    
    df_copy['temp_rolling_mean'] = df_copy['temperature_2m'].rolling(
        window=hours, 
        min_periods=1
    ).mean().round(2)
    
    return df_copy


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


def calculate_advanced_frost_risk(temp_rolling: float, wind_speed: float, 
                                cloud_cover: float, humidity: float = None, 
                                hour_of_day: int = None) -> Tuple[str, int, Dict[str, Any]]:
    """
    Beräkna frostrisk med validerad algoritm (F1=0.852).
    
    Algoritm:
    1. Dagtidsfilter: Ingen varning 08-17 vid plusgrader
    2. Grundrisk: temp ≤ 0°C → HÖG risk
    3. Dynamiska trösklar baserat på molntäcke:
       - Klart (faktor ≥1.4): temp ≤ 3°C + vindstilla → varning
       - Halvklart (faktor ≥1.1): temp ≤ 2°C + vindstilla → varning  
       - Mulet: temp ≤ 1°C + vindstilla → varning
    4. Extra check: temp ≤ 2°C + vind < 3 m/s + fuktighet > 85% → varning
    
    Args:
        temp_rolling: Rullande medeltemperatur i Celsius
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
    if pd.isna(temp_rolling) or pd.isna(wind_speed):
        return "okänd", 0, {"reason": "Saknade temperatur- eller vinddata"}
    
    # DAGTIDSFILTER: Skippa frost på dagtid (08-17) vid plusgrader
    if hour_of_day is not None and 8 <= hour_of_day <= 17:
        if temp_rolling > 0:
            return "ingen", 0, {
                "reason": f"Dagtid (kl {hour_of_day:02d}) med plusgrader ({temp_rolling:.1f}°C)",
                "note": "Solstrålning förhindrar frost",
                "daytime_filter": True
            }
    
    # ========== VALIDERAD ALGORITM (F1=0.852) ==========
    
    # 1. GRUNDRISK: Temperatur under fryspunkten
    if temp_rolling <= 0:
        return "hög", 3, {
            "reason": f"Temperatur {temp_rolling:.1f}°C ≤ 0°C",
            "algorithm": "comprehensive",
            "temp": temp_rolling,
            "wind": wind_speed,
            "cloud_cover": cloud_cover,
            "humidity": humidity
        }
    
    # 2. MOLNPÅVERKAN: Dynamiska tröskelvärden
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
    
    if temp_rolling <= temp_limit and wind_speed < 4:
        return risk_level, risk_numeric, {
            "reason": f"Temperatur {temp_rolling:.1f}°C ≤ {temp_limit}°C + vindstilla ({wind_speed:.1f} m/s)",
            "cloud_factor": cloud_factor,
            "cloud_condition": "klart" if cloud_factor >= 1.4 else "halvklart" if cloud_factor >= 1.1 else "mulet",
            "algorithm": "comprehensive",
            "temp": temp_rolling,
            "wind": wind_speed,
            "cloud_cover": cloud_cover,
            "humidity": humidity
        }
    
    # 3. Luftfuktighet
    if not pd.isna(humidity) and temp_rolling <= 2 and wind_speed < 3 and humidity > 85:
        return "medel", 2, {
            "reason": f"Temperatur {temp_rolling:.1f}°C + låg vind ({wind_speed:.1f} m/s) + hög fuktighet ({humidity:.0f}%)",
            "note": "Kondensrisk vid hög luftfuktighet",
            "algorithm": "comprehensive",
            "temp": temp_rolling,
            "wind": wind_speed,
            "cloud_cover": cloud_cover,
            "humidity": humidity
        }
    
    # Ingen risk
    return "ingen", 0, {
        "reason": f"Temperatur {temp_rolling:.1f}°C för hög eller för mycket vind ({wind_speed:.1f} m/s)",
        "algorithm": "comprehensive",
        "temp": temp_rolling,
        "wind": wind_speed,
        "cloud_cover": cloud_cover,
        "humidity": humidity
    }


def analyze_dataframe_advanced(df: pd.DataFrame, rolling_hours: int = 3) -> pd.DataFrame:
    """
    Analysera DataFrame med validerad frostalgoritm.
    
    Args:
        df: DataFrame med kolumner 'temperature_2m', 'wind_speed_10m', 'cloud_cover'
        rolling_hours: Antal timmar för rullande medelvärde (default: 3)
        
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
    
    # Beräkna rullande medeltemperatur
    result_df = calculate_rolling_mean_temperature(result_df, rolling_hours)
    
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
        
        risk_text, risk_numeric, details = calculate_advanced_frost_risk(
            row['temp_rolling_mean'],
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
        explanation.append(f"Temperatur (3h medel): {frost_details['temp']:.1f}°C")
    
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
