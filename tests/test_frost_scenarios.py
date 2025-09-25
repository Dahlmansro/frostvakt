# test_frost_scenarios.py
"""
Testa frost-varningssystemet med realistiska väderscenarier.
Simulerar olika typer av frostväder för att validera att varningarna fungerar korrekt.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Any

# FIXAT: Importera från advanced_frost_analyzer
from advanced_frost_analyzer import analyze_dataframe_advanced
from main import get_engine, load_frost_warnings
from email_notifier import EmailNotifier, send_frost_notification
import yaml
import os

def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Hittar inte config.yaml på: {os.path.abspath(path)}")
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg

# Konfigurera loggning
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("frost_test")


def create_realistic_frost_scenario(
    scenario_name: str,
    hours: int = 48,
    start_temp: float = 8.0,
    end_temp: float = -3.0,
    base_wind: float = 2.0,
    wind_variation: float = 1.5,
    humidity: float = 75.0
) -> pd.DataFrame:
    """
    Skapa realistiskt väderscenario med gradvis temperaturförändring.
    """
    
    # Skapa tidsserie
    start_time = datetime.now().replace(hour=18, minute=0, second=0, microsecond=0)
    times = [start_time + timedelta(hours=i) for i in range(hours)]
    
    # Gradvis temperaturminskning med realistisk dygnsvariation
    temp_trend = np.linspace(start_temp, end_temp, hours)
    
    # Lägg till dygnsvariation
    daily_variation = []
    for i, time in enumerate(times):
        hour = time.hour
        if 22 <= hour or hour <= 8:
            variation = -2.0 * np.sin(np.pi * (hour + 2) / 12) if hour <= 8 else -1.5
        else:
            variation = 1.0 * np.sin(np.pi * hour / 12)
        daily_variation.append(variation)
    
    temperatures = temp_trend + np.array(daily_variation)
    
    # Realistisk vindvariation
    wind_speeds = []
    for time in times:
        hour = time.hour
        if 0 <= hour <= 6:
            night_factor = 0.3
        elif 6 <= hour <= 10:
            night_factor = 0.6
        elif 10 <= hour <= 16:
            night_factor = 1.2
        elif 16 <= hour <= 20:
            night_factor = 0.9
        else:
            night_factor = 0.5
            
        wind = max(0.1, base_wind * night_factor + np.random.normal(0, wind_variation))
        wind_speeds.append(round(wind, 1))
    
    # Skapa DataFrame
    df = pd.DataFrame({
        'valid_time': times,
        'temperature_2m': [round(temp, 1) for temp in temperatures],
        'wind_speed_10m': wind_speeds,
        'relative_humidity_2m': [humidity + np.random.normal(0, 5) for _ in range(hours)],
        'cloud_cover': [20.0 + np.random.normal(0, 10) for _ in range(hours)],  # LAGT TILL
        'precipitation': [0.0] * hours,
        'precipitation_probability': [10] * hours,
        'dataset': 'test_scenario',
        'forecast_issue_time': pd.NaT,
        'horizon_hours': pd.NA,
        'run_id': f'frost_test_{scenario_name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    })
    
    logger.info(f"Scenario '{scenario_name}': {len(df)} timmar, temp {start_temp:.1f}°C → {end_temp:.1f}°C")
    return df


def create_test_scenarios() -> Dict[str, pd.DataFrame]:
    """Skapa olika realistiska frostscenarier för testning."""
    
    scenarios = {}
    
    # 1. KLASSISK STRÅLNINGSFROST
    scenarios["strålningsfrost"] = create_realistic_frost_scenario(
        scenario_name="strålningsfrost",
        hours=36,
        start_temp=4.0,
        end_temp=-1.5,
        base_wind=0.8,
        wind_variation=0.3,
        humidity=85
    )
    
    # 2. KRAFTIG VINTERKYLA
    scenarios["vinterkyla"] = create_realistic_frost_scenario(
        scenario_name="vinterkyla", 
        hours=48,
        start_temp=2.0,
        end_temp=-8.0,
        base_wind=3.5,
        wind_variation=2.0,
        humidity=70
    )
    
    # 3. GRÄNSFALL
    scenarios["gränsfall"] = create_realistic_frost_scenario(
        scenario_name="gränsfall",
        hours=24,
        start_temp=3.5,
        end_temp=-1.0,
        base_wind=2.5,
        wind_variation=2.5,
        humidity=80
    )
    
    return scenarios


def analyze_scenario(scenario_name: str, df: pd.DataFrame) -> Dict[str, Any]:
    """Analysera ett frostscenario och returnera resultat."""
    
    logger.info(f"\n{'='*60}")
    logger.info(f"ANALYSERAR SCENARIO: {scenario_name.upper()}")
    logger.info(f"{'='*60}")
    
    # Visa grundinfo
    temp_min = df['temperature_2m'].min()
    temp_max = df['temperature_2m'].max()
    
    logger.info(f"Scenario-info:")
    logger.info(f"  Temperaturspann: {temp_min:.1f}°C till {temp_max:.1f}°C")
    logger.info(f"  Total tid: {len(df)} timmar")
    
    # FIXAT: Använd analyze_dataframe_advanced
    df_analyzed = analyze_dataframe_advanced(df)
    
    # Sammanställ resultat
    warning_count = sum(df_analyzed['frost_warning']) if 'frost_warning' in df_analyzed.columns else 0
    
    if warning_count == 0:
        logger.info("Inga frostvarningar genererade")
        return {"scenario": scenario_name, "warnings": 0, "summary": {}, "dataframe": df_analyzed}
    
    logger.warning(f"FROSTVARNING: {warning_count} timmar med frostvarning!")
    
    # Skapa enkel sammanfattning
    risk_levels = df_analyzed[df_analyzed['frost_warning']]['frost_risk_level'].value_counts().to_dict()
    logger.warning(f"Riskfördelning: {risk_levels}")
    
    # Visa högriskvarningar
    high_risk = df_analyzed[df_analyzed['frost_risk_level'] == 'hög']
    if not high_risk.empty:
        logger.error(f"HOG FROSTRISK ({len(high_risk)} timmar):")
        for _, row in high_risk.head(3).iterrows():
            time_str = pd.to_datetime(row['valid_time']).strftime("%m-%d %H:%M")
            logger.error(f"    {time_str}: {row['temperature_2m']:.1f}°C, {row['wind_speed_10m']:.1f}m/s")
    
    return {
        "scenario": scenario_name,
        "warnings": warning_count,
        "summary": {"risk_levels": risk_levels},
        "dataframe": df_analyzed
    }


def save_test_results_to_database(results: List[Dict[str, Any]], sqlite_path: str = "data/weather_history_forcast.db"):
    """Spara testresultat till databasen."""
    
    logger.info(f"\nSparar testresultat till databas...")
    
    engine = get_engine(sqlite_path)
    
    total_saved = 0
    for result in results:
        if result['warnings'] > 0:
            df = result['dataframe']
            run_id = df.iloc[0]['run_id']
            saved = load_frost_warnings(df, engine, run_id)
            total_saved += saved
            logger.info(f"  {result['scenario']}: {saved} varningar sparade")
    
    logger.info(f"Totalt {total_saved} test-varningar sparade i databas")


def main():
    """Huvudfunktion för att köra alla testscenarier."""
    
    logger.info("STARTAR FROST-SCENARIO TESTNING")
    logger.info("="*70)
    
    # Skapa testscenarier
    scenarios = create_test_scenarios()
    
    # Analysera varje scenario
    results = []
    for name, df in scenarios.items():
        result = analyze_scenario(name, df)
        results.append(result)
    
    # Sammanfattning
    logger.info(f"\n{'='*70}")
    logger.info("TESTSAMMANFATTNING")
    logger.info(f"{'='*70}")
    
    total_warnings = sum(r['warnings'] for r in results)
    
    logger.info(f"Testade scenarier: {len(results)}")
    logger.info(f"Totala varningar: {total_warnings}")
    
    # Detaljerad sammanfattning
    logger.info(f"\nResultat per scenario:")
    for result in results:
        status = "VARNING" if result['warnings'] > 0 else "OK"
        logger.info(f"  [{status}] {result['scenario']:<15}: {result['warnings']:>3} varningar")
    
    # Spara till databas
    save_test_results_to_database(results)
    
    logger.info(f"\nTestning klar!")


if __name__ == "__main__":
    main()