# api_comparison.py
"""
Jämförelse-verktyg för väder-API:er (YR vs Open-Meteo).
"""
import pandas as pd
import requests
import yaml
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional
import logging

# Importera befintliga moduler
from yr_api_client import YrApiClient

# Konfigurera loggning för jämförelser
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | COMPARE | %(levelname)s | %(message)s"
)
logger = logging.getLogger("api_comparison")


def load_config_simple(path: str = "config.yaml") -> Dict[str, Any]:
    """Enkel config-laddning."""
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


def fetch_openmeteo_simple() -> pd.DataFrame:
    """Hämta Open-Meteo data direkt."""
    print("Hämtar Open-Meteo data...")
    
    # Ladda config
    config = load_config_simple()
    api_config = config["api"]
    base_url = api_config["base_url"]
    params = api_config["params"].copy()
    
    # Anpassa för jämförelse - 14 dagar för mer relevant data
    params["forecast_days"] = 14
    params["past_days"] = 0
    
    print(f"PARAMS SKICKAS: {params}")
    print(f"HOURLY PARAMETER: '{params.get('hourly')}'")
    
    # API-anrop
    response = requests.get(base_url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    
    # Analysera svar
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    
    print(f"API returnerade {len(hourly)} parametrar:")
    for key, values in hourly.items():
        print(f"  {key}: {len(values)} värden")
    
    # Skapa DataFrame
    df = pd.DataFrame({"valid_time": pd.to_datetime(times)})
    
    # Lägg till alla parametrar som finns
    for param_name in ["temperature_2m", "relative_humidity_2m", "precipitation", 
                      "wind_speed_10m", "precipitation_probability", "cloud_cover"]:
        param_values = hourly.get(param_name, [])
        
        if len(param_values) == len(times):
            if param_name == "wind_speed_10m":
                df[param_name] = [w/3.6 if w is not None else None for w in param_values]
            else:
                df[param_name] = param_values
        else:
            print(f"WARNING: {param_name} har {len(param_values)} värden, förväntat {len(times)}")
            df[param_name] = [None] * len(times)
    
    df["api"] = "open_meteo"
    print(f"Open-Meteo DataFrame: {len(df)} rader")
    return df


def fetch_yr_simple() -> pd.DataFrame:
    """Hämta YR data direkt."""
    print("Hämtar YR data...")
    
    # Ladda config
    config = load_config_simple()
    yr_config = config.get("yr_api", {})
    user_agent = yr_config.get("user_agent", "FrostvaktApp/1.0 test@example.com")
    
    # Koordinater
    params = yr_config.get("params", config["api"]["params"])
    lat = params["latitude"]
    lon = params["longitude"]
    
    # YR-klient
    yr_client = YrApiClient(user_agent)
    yr_json = yr_client.fetch_forecast(lat, lon)
    df = yr_client.transform_to_dataframe(yr_json, "yr_forecast")
    
    if not df.empty:
        # Begränsa till 14 dagar för mer relevant jämförelse
        cutoff_time = datetime.now() + pd.Timedelta(days=14)
        df = df[df["valid_time"] <= cutoff_time].copy()
        df["api"] = "yr"
    
    print(f"YR DataFrame: {len(df)} rader")
    return df


def add_simple_summary(comparison_df):
    """Enkel och tydlig sammanfattning - lagom för små dataset."""
    
    if comparison_df.empty:
        print("\n📋 SLUTLIG SAMMANFATTNING:")
        print("Ingen data att sammanfatta")
        return
    
    # Beräkna grundläggande statistik
    num_comparisons = len(comparison_df)
    mean_temp_diff = comparison_df['temp_diff'].mean()
    mean_wind_diff = comparison_df['wind_diff'].mean()
    
    # God överensstämmelse = mindre än 0.5°C temperaturskillnad
    good_agreement = (comparison_df['temp_diff'].abs() < 0.5).mean() * 100
    
    # Extremvärden
    max_temp_diff = comparison_df['temp_diff'].abs().max()
    max_wind_diff = comparison_df['wind_diff'].abs().max()
    
    # Molntäcke om tillgängligt
    cloud_stats = ""
    if 'cloud_diff' in comparison_df.columns and not comparison_df['cloud_diff'].isna().all():
        mean_cloud_diff = comparison_df['cloud_diff'].mean()
        cloud_stats = f"\n Medelskillnad molntäcke: {mean_cloud_diff:.1f}%"
    
    # Vem som oftast är varmare/kallare
    yr_warmer_count = (comparison_df['temp_diff'] > 0).sum()
    yr_warmer_pct = (yr_warmer_count / num_comparisons) * 100
    
    # Tidsperiod
    time_start = comparison_df['hour'].min().strftime('%Y-%m-%d %H:%M')
    time_end = comparison_df['hour'].max().strftime('%Y-%m-%d %H:%M')
    
    # Sammanfattning
    print("=" * 60)
    print("GRUNDLÄGGANDE SAMMANFATTNING: YR vs Open-Meteo")
    print("=" * 60)
    
    print(f"Dataset: {num_comparisons} jämförelser mellan YR och Open-Meteo")
    print(f"Tidsperiod: {time_start} → {time_end}")
    print(f"Medelskillnad temperatur: {mean_temp_diff:+.2f}°C (YR - Open-Meteo)")
    print(f"Medelskillnad vind: {mean_wind_diff:+.2f} m/s (YR - Open-Meteo)")
    if cloud_stats:
        print(cloud_stats.strip())
    
    print(f"\nExtremvärden:")
    print(f"• Största temperaturskillnad: {max_temp_diff:.2f}°C")
    print(f"• Största vindskillnad: {max_wind_diff:.2f} m/s")
    
    print(f"\n Överensstämmelse:")
    print(f"• God överensstämmelse: {good_agreement:.1f}% av mätningarna (<0.5°C)")
    print(f"• YR varmare: {yr_warmer_pct:.1f}% av tiden")
    print(f"• YR kallare: {100-yr_warmer_pct:.1f}% av tiden")
    

def compare_simple():
    """Enkel jämförelse med 14 dagars data."""
    print("=== FÖRENKLAD API-JÄMFÖRELSE (14 dagar) ===")
    
    # Hämta data
    try:
        df_om = fetch_openmeteo_simple()
    except Exception as e:
        print(f"Open-Meteo fel: {e}")
        df_om = pd.DataFrame()
    
    try:
        df_yr = fetch_yr_simple()
    except Exception as e:
        print(f"YR fel: {e}")
        df_yr = pd.DataFrame()
    
    if df_om.empty:
        print("Open-Meteo data misslyckades")
        return
    
    if df_yr.empty:
        print("YR data misslyckades")
        return
    
    # FIXA TIDSJUSTERING - Ta bara framtida prognoser från båda
    now = datetime.now()
    print(f"\nFiltrerar data från: {now}")
    
    df_om_future = df_om[df_om['valid_time'] >= now].copy()
    df_yr_future = df_yr[df_yr['valid_time'] >= now].copy()
    
    print(f"Efter tidsfiltrering:")
    print(f"Open-Meteo: {len(df_om_future)} rader (från {df_om_future['valid_time'].min() if not df_om_future.empty else 'N/A'})")
    print(f"YR: {len(df_yr_future)} rader (från {df_yr_future['valid_time'].min() if not df_yr_future.empty else 'N/A'})")
    
    if df_om_future.empty or df_yr_future.empty:
        print("Ingen framtida data att jämföra")
        return
    
    # JÄMFÖR FÖRSTA MATCHANDE TIDPUNKTER
    print(f"\nJÄMFÖRELSE AV MATCHANDE TIDPUNKTER:")
    
    # Hitta gemensamma tidpunkter (avrunda till närmaste timme)
    df_om_future['hour'] = df_om_future['valid_time'].dt.floor('H')
    df_yr_future['hour'] = df_yr_future['valid_time'].dt.floor('H')
    
    # Merge på timme
    comparison = pd.merge(
        df_om_future[['hour', 'temperature_2m', 'wind_speed_10m', 'cloud_cover']],
        df_yr_future[['hour', 'temperature_2m', 'wind_speed_10m', 'cloud_cover']], 
        on='hour',
        suffixes=('_openmeteo', '_yr'),
        how='inner'
    )
    
    if comparison.empty:
        print("Inga matchande tidpunkter hittades")
        return
    
    print(f"Hittade {len(comparison)} matchande tidpunkter")
    
    # Beräkna skillnader
    comparison['temp_diff'] = comparison['temperature_2m_yr'] - comparison['temperature_2m_openmeteo']
    comparison['wind_diff'] = comparison['wind_speed_10m_yr'] - comparison['wind_speed_10m_openmeteo']
    comparison['cloud_diff'] = comparison['cloud_cover_yr'] - comparison['cloud_cover_openmeteo']
    
    # Visa första 5 jämförelserna
    print(f"\nFörsta 5 jämförelser:")
    print("Tid                 | OM Temp | YR Temp | Diff  | OM Vind | YR Vind | Diff  ")
    print("-" * 75)
    
    for i, row in comparison.head(5).iterrows():
        time_str = row['hour'].strftime('%Y-%m-%d %H:%M')
        print(f"{time_str} | {row['temperature_2m_openmeteo']:7.1f} | {row['temperature_2m_yr']:7.1f} | {row['temp_diff']:5.1f} | {row['wind_speed_10m_openmeteo']:7.1f} | {row['wind_speed_10m_yr']:7.1f} | {row['wind_diff']:5.1f}")
    
    # Spara jämförelse
    comparison.to_csv("api_comparison_results.csv", index=False)
    print(f"\nJämförelse sparad till: api_comparison_results.csv")
    
    # Visa enkel slutsammanfattning
    add_simple_summary(comparison)
    
    return df_om_future, df_yr_future, comparison


if __name__ == "__main__":
    compare_simple()