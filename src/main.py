# src/main.py
"""
Huvudfil frostvakt-system
Hanterar datahämtning, frostanalys och notifikationer.
"""
import os
import sys
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import traceback

import requests
import pandas as pd
import yaml
from sqlalchemy import create_engine, text

from advanced_frost_analyzer import analyze_dataframe_advanced
from notification_manager import create_notification_manager

# Loggkonfiguration

DEBUG_MODE = os.getenv('FROSTVAKT_DEBUG', 'false').lower() == 'true'

if DEBUG_MODE:
    log_level = logging.DEBUG
    log_format = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    print("🔧 DEBUG-läge aktiverat - Detaljerad loggning")
else:
    log_level = logging.INFO
    log_format = "%(asctime)s | %(levelname)-7s | %(message)s"

logging.basicConfig(
    level=log_level,
    format=log_format,
    handlers=[
        logging.FileHandler("logs/etl.log", mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("frostvakt.main")

if not DEBUG_MODE:
    logging.getLogger("frostvakt.notification_manager").setLevel(logging.WARNING)
    logging.getLogger("frostvakt.email_notifier").setLevel(logging.WARNING)
    logging.getLogger("frostvakt.sms_notifier").setLevel(logging.WARNING)
    logging.getLogger("frostvakt.advanced_frost_analyzer").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    logging.getLogger("requests").setLevel(logging.ERROR)
    logging.getLogger("twilio").setLevel(logging.ERROR)

# Loggfunktioner

def log_run_start(run_id: str):
    """Logga körningens start."""
    logger.info(f"▶️  Frostvakt startar (Run ID: {run_id})")

def log_data_fetched(hours: int, source: str = "Open-Meteo"):
    """Logga datahämtning."""
    logger.info(f"🌡️  Hämtade {hours}h prognos från {source}")

def log_frost_analysis(total: int, warnings: int):
    """Logga frostanalys resultat."""
    if warnings > 0:
        logger.warning(f"❄️  FROSTVARNING: {warnings} av {total} timmar har frostrisk")
    else:
        logger.info(f"✅ Ingen frostrisk: {total} timmar analyserade")

def log_notifications_sent(email_sent: bool, sms_sent: bool):
    """Logga notifikationer."""
    if email_sent or sms_sent:
        methods = []
        if email_sent: methods.append("email")
        if sms_sent: methods.append("SMS")
        logger.info(f"🔔 Notifikationer skickade via: {', '.join(methods)}")

def log_run_complete(duration: str, rows: int, warnings: int):
    """Logga körningens slut."""
    logger.info(f"✅ Körning slutförd ({duration}) - {rows} rader, {warnings} varningar")

def debug_log(message: str):
    """Logga debug-meddelande (visas bara i debug-läge)."""
    if DEBUG_MODE:
        logger.debug(f"🔍 {message}")

def debug_frost_details(details: dict):
    """Logga detaljerad frostanalys (bara debug)."""
    if DEBUG_MODE:
        logger.debug(f"Frost-detaljer: {details}")

# Konfig och API

def load_config(path: str = "config.yaml") -> Dict[str, Any]:
    """Ladda konfiguration från YAML-fil."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Hittar inte config.yaml på: {os.path.abspath(path)}")
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


def fetch_with_retry(url: str, params: dict, timeout: int, max_retries: int = 3, backoff: int = 2) -> Dict[str, Any]:
    """Hämta data med retry-logik för robusthet."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            debug_log(f"API-anrop misslyckades (försök {attempt + 1}/{max_retries}): {e}")
            
            if attempt < max_retries - 1:
                sleep_time = backoff * (attempt + 1)
                import time
                time.sleep(sleep_time)
            else:
                raise


def fetch_forecast(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Hämta prognosdata från Open-Meteo."""
    base_url = cfg["api"]["base_url"]
    params = cfg["api"]["params"].copy()
    params["forecast_days"] = cfg["api"]["params"].get("forecast_days", 7)
    
    debug_log("Hämtar prognos från Open-Meteo")
    
    result = fetch_with_retry(
        base_url, 
        params, 
        timeout=cfg["run"]["timeout_seconds"],
        max_retries=cfg["run"].get("max_retries", 3),
        backoff=cfg["run"].get("backoff_seconds", 2)
    )
       
    return result

# Datatransformering

WANTED_COLS = [
    "temperature_2m",
    "relative_humidity_2m", 
    "precipitation",
    "wind_speed_10m",
    "precipitation_probability",
    "cloud_cover",
]

def transform_hourly_json(
    json_data: Dict[str, Any],
    dataset: str,
    forecast_issue_time: Optional[pd.Timestamp],
    run_id: str,
    tz: str = "Europe/Stockholm",
) -> pd.DataFrame:
    """Transformera Open-Meteo JSON till DataFrame."""
    hourly = json_data.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        logger.warning("Inga tider i API-svar")
        return pd.DataFrame()

    df = pd.DataFrame({"valid_time": times})
    df["valid_time"] = pd.to_datetime(df["valid_time"]).dt.tz_localize(None)

    for col in WANTED_COLS:
        values = hourly.get(col, [None] * len(df))
        df[col] = values
    
    if 'wind_speed_10m' in df.columns:
        df['wind_speed_10m'] = df['wind_speed_10m'] / 3.6

    df["dataset"] = dataset

    if forecast_issue_time is not None:
        fit = pd.to_datetime(forecast_issue_time).tz_localize(None)
        df["forecast_issue_time"] = fit
        df["horizon_hours"] = (df["valid_time"] - fit).dt.total_seconds() / 3600.0
        df["horizon_hours"] = df["horizon_hours"].round(1)
    else:
        df["forecast_issue_time"] = pd.NaT
        df["horizon_hours"] = pd.NA

    df["run_id"] = run_id

    return df[[
        "valid_time", "temperature_2m", "relative_humidity_2m", "precipitation",
        "wind_speed_10m", "precipitation_probability", "cloud_cover", "dataset",
        "forecast_issue_time", "horizon_hours", "run_id",
    ]]


# Databasfunktioner

def get_engine(sqlite_path: str):
    """Skapa databasanslutning."""
    abs_path = os.path.abspath(sqlite_path)
    dir_path = os.path.dirname(abs_path)
    os.makedirs(dir_path, exist_ok=True)
    return create_engine(f"sqlite:///{abs_path}", future=True)

def create_database_tables(engine):
    """Skapa alla nödvändiga tabeller om de inte finns."""
    weather_table_sql = text("""
        CREATE TABLE IF NOT EXISTS weather_hourly (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            valid_time TEXT NOT NULL,
            temperature_2m REAL,
            relative_humidity_2m REAL,
            precipitation REAL,
            wind_speed_10m REAL,
            precipitation_probability INTEGER,
            cloud_cover REAL,                     
            dataset TEXT NOT NULL,
            forecast_issue_time TEXT,
            horizon_hours REAL,
            run_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(valid_time, dataset)
        )
    """)

    frost_table_sql = text("""
        CREATE TABLE IF NOT EXISTS frost_warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            valid_time TEXT NOT NULL,
            temperature_2m REAL,
            wind_speed_10m REAL,
            frost_risk_level TEXT NOT NULL,
            frost_risk_numeric INTEGER NOT NULL,
            dataset TEXT NOT NULL,
            forecast_issue_time TEXT,
            horizon_hours REAL,
            run_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(valid_time, dataset)
        )
    """)

    heartbeat_sql = text("""
        CREATE TABLE IF NOT EXISTS heartbeat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            status TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    
    with engine.begin() as conn:
        conn.execute(weather_table_sql)
        conn.execute(frost_table_sql)
        conn.execute(heartbeat_sql) 

INSERT_WEATHER_SQL = text("""
    INSERT OR REPLACE INTO weather_hourly (
        valid_time, temperature_2m, relative_humidity_2m, precipitation,
        wind_speed_10m, precipitation_probability, cloud_cover, dataset,
        forecast_issue_time, horizon_hours, run_id
    ) VALUES (
        :valid_time, :temperature_2m, :relative_humidity_2m, :precipitation,
        :wind_speed_10m, :precipitation_probability, :cloud_cover, :dataset,
        :forecast_issue_time, :horizon_hours, :run_id
    )
""")

INSERT_FROST_WARNING_SQL = text("""
    INSERT OR REPLACE INTO frost_warnings (
        valid_time, temperature_2m, wind_speed_10m, cloud_cover, frost_risk_level,
        frost_risk_numeric, dataset, forecast_issue_time, horizon_hours,
        run_id, created_at
    ) VALUES (
        :valid_time, :temperature_2m, :wind_speed_10m, :cloud_cover, :frost_risk_level,
        :frost_risk_numeric, :dataset, :forecast_issue_time, :horizon_hours,
        :run_id, :created_at
    )
""")

def load_weather_data(df: pd.DataFrame, engine) -> int:
    """Spara väderdata till databas."""
    if df.empty:
        return 0

    df = df.copy()
    for col in ["valid_time", "forecast_issue_time"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: None if pd.isna(x) else pd.to_datetime(x).strftime("%Y-%m-%d %H:%M:%S"))

    if 'forecast_issue_time' in df.columns and not df['forecast_issue_time'].isna().all():
        df['forecast_issue_datetime'] = pd.to_datetime(df['forecast_issue_time'])
        df = df.sort_values(['valid_time', 'forecast_issue_datetime'], ascending=[True, False])
        df = df.groupby('valid_time').first().reset_index()
        df = df.drop('forecast_issue_datetime', axis=1)
        debug_log(f"Filtrerat till {len(df)} unika prognostidpunkter")

    records: List[Dict[str, Any]] = df.to_dict(orient="records")

    with engine.begin() as conn:
        for rec in records:
            try:
                conn.execute(INSERT_WEATHER_SQL, rec)
            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    continue
                else:
                    raise e

    debug_log(f"Sparade {len(records)} prognosrader")
    return len(records)


def load_frost_warnings(df: pd.DataFrame, engine, run_id: str) -> int:
    """Spara frost-varningar till databas."""
    if df.empty:
        return 0

    warnings_df = df[df['frost_warning'] == True].copy()
    
    if warnings_df.empty:
        return 0

    warnings_df['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for col in ["valid_time", "forecast_issue_time"]:
        if col in warnings_df.columns:
            warnings_df[col] = warnings_df[col].apply(
                lambda x: None if pd.isna(x) else pd.to_datetime(x).strftime("%Y-%m-%d %H:%M:%S")
            )

    if 'forecast_issue_time' in warnings_df.columns:
        warnings_df['forecast_issue_datetime'] = pd.to_datetime(warnings_df['forecast_issue_time'])
        warnings_df = warnings_df.sort_values(['valid_time', 'forecast_issue_datetime'], ascending=[True, False])
        warnings_df = warnings_df.groupby('valid_time').first().reset_index()
        warnings_df = warnings_df.drop('forecast_issue_datetime', axis=1, errors='ignore')

    warning_cols = [
        'valid_time', 'temperature_2m', 'wind_speed_10m', 'cloud_cover',
        'frost_risk_level', 'frost_risk_numeric', 'dataset',
        'forecast_issue_time', 'horizon_hours', 'run_id', 'created_at'
    ]

    if 'cloud_cover' not in warnings_df.columns:
        warnings_df['cloud_cover'] = None
    
    records = warnings_df[warning_cols].to_dict(orient="records")

    with engine.begin() as conn:
        for rec in records:
            try:
                conn.execute(INSERT_FROST_WARNING_SQL, rec)
            except Exception as e:
                if "UNIQUE constraint failed" in str(e):
                    continue
                else:
                    raise e

    debug_log(f"Sparade {len(records)} frostvarningar")
    return len(records)


# Frostanalys

def perform_frost_analysis(df: pd.DataFrame, dataset_name: str, run_id: str) -> pd.DataFrame:
    """Utför förbättrad frost-analys på weather DataFrame."""
    if df.empty:
        return df
    
    df_with_frost = analyze_dataframe_advanced(df)
    
    if 'frost_warning' in df_with_frost.columns:
        warning_count = sum(df_with_frost['frost_warning'])
        
        debug_log(f"Frostanalys: {warning_count} av {len(df)} timmar har risk")
        
        if warning_count > 0 and DEBUG_MODE:
            first_warning = df_with_frost[df_with_frost['frost_warning']].iloc[0]
            if 'frost_details' in first_warning:
                debug_frost_details(first_warning['frost_details'])
    
    return df_with_frost


# Huvudflöde

def main():
    """Huvudfunktion för Frostvakt-systemet."""
    
    try:
        cfg = load_config("config.yaml")
    except Exception as e:
        print(f"KRITISKT FEL: Kan inte ladda konfiguration: {e}")
        sys.exit(1)
    
    run_id_prefix = cfg["run"].get("batch_id_prefix", "etl_run")
    now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{run_id_prefix}_{now_utc}"
    
    print("🚀 Frostvakt kör...")
    log_run_start(run_id)
    
    try:
        from smoke_test import run_smoke_tests
        if not run_smoke_tests():
            logger.error("Smoke tests misslyckades")
            print("❌ Systemtest misslyckades")
            sys.exit(1)
    except ImportError:
        pass
    except Exception as e:
        debug_log(f"Smoke test fel: {e}")
    
    sqlite_path = cfg["storage"]["sqlite_path"]
    
    try:
        engine = get_engine(sqlite_path)
        create_database_tables(engine)
        debug_log("Databas förberedd")
    except Exception as e:
        logger.error(f"Databasfel: {e}")
        print("Databasfel")
        sys.exit(1)
    
    notification_manager = create_notification_manager(cfg)
    debug_log(f"Notifiers status: {notification_manager.get_notifier_status()}")
    
    stats = {
        'start_time': datetime.now(),
        'forecast_rows': 0,
        'forecast_warnings': 0,
        'notifications_sent': False,
        'errors': []
    }
    
    df_fc = pd.DataFrame()
    
    try:
        fc_json = fetch_forecast(cfg)
        issue_time_local = pd.Timestamp.now(tz=cfg["api"]["params"].get("timezone", "Europe/Stockholm"))
        df_fc = transform_hourly_json(
            fc_json, "forecast", issue_time_local, run_id,
            cfg["api"]["params"].get("timezone", "Europe/Stockholm")
        )
        stats['forecast_rows'] = len(df_fc)
        
        log_data_fetched(len(df_fc))
        
        df_fc = perform_frost_analysis(df_fc, "forecast", run_id)
        
        warnings_only = df_fc[df_fc.get('frost_warning', False) == True] if not df_fc.empty else pd.DataFrame()
        
        log_frost_analysis(len(df_fc), len(warnings_only))
        
        if not warnings_only.empty:
            print(f"❄️ FROSTVARNING: {len(warnings_only)} timmar med frostrisk!")
            
            try:
                notification_results = notification_manager.send_all_notifications(warnings_only)
                
                if notification_results['any_sent']:
                    stats['notifications_sent'] = True
                    
                    log_notifications_sent(
                        notification_results['email'],
                        notification_results['sms']
                    )
                    
                    if notification_results['email']:
                        print("📧 Frostvarning skickad via email")
                    if notification_results['sms']:
                        print("📱 Frostvarning skickad via SMS")
                    
            except Exception as e:
                error_msg = f"Notifikationsfel: {e}"
                logger.error(error_msg)
                stats['errors'].append(error_msg)
        
    except Exception as e:
        error_msg = f"Prognos misslyckades: {e}"
        logger.error(error_msg)
        print("Fel vid väderdata-hämtning")
        stats['errors'].append(error_msg)
        df_fc = pd.DataFrame()
    
    try:
        if not df_fc.empty:
            load_weather_data(df_fc, engine)
            stats['forecast_warnings'] = load_frost_warnings(df_fc, engine, run_id)
            debug_log("Data sparat i databas")
    except Exception as e:
        error_msg = f"Databas-sparning misslyckades: {e}"
        logger.error(error_msg)
        stats['errors'].append(error_msg)
    
    stats['end_time'] = datetime.now()
    stats['duration'] = stats['end_time'] - stats['start_time']
    
    log_run_complete(
        str(stats['duration']).split('.')[0],
        stats['forecast_rows'],
        stats['forecast_warnings']
    )
    
    try:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO heartbeat (run_id, status, timestamp) VALUES (:run_id, :status, :ts)"),
                {
                    "run_id": run_id,
                    "status": "ok" if not stats['errors'] else "fail",
                    "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            )
        debug_log("Heartbeat uppdaterad")
    except Exception as e:
        logger.error(f"Misslyckades skriva heartbeat: {e}")

    if stats['errors']:
        logger.error(f"Fel under körning: {'; '.join(stats['errors'])}")
        print("⚠️ Körning slutförd med fel (se logg)")
        if any('kritiskt' in error.lower() or 'databas' in error.lower() for error in stats['errors']):
            sys.exit(1)
    else:
        print("✅ Frostvakt slutförd")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAvbruten av användare")
        sys.exit(130)
    except Exception as e:
        print(f"\n💥 KRITISKT FEL: {e}")
        traceback.print_exc()
        sys.exit(1)
        