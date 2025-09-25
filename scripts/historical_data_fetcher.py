# historical_data_fetcher.py

    """
    Hämtar historisk data, 2015-2024från OPEN-METEO
    """

import os
import sqlite3
import time
from datetime import datetime
import openmeteo_requests
import requests_cache
from retry_requests import retry
import pandas as pd
import yaml

def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def create_table(db_path):
    """Skapa tabellen om den inte finns"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weather_historical (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            valid_time TEXT NOT NULL UNIQUE,
            temperature_2m REAL,
            relative_humidity_2m REAL,
            dew_point_2m REAL,
            wind_speed_10m REAL,
            cloud_cover REAL,
            pressure_msl REAL,
            rain REAL,
            year INTEGER,
            month INTEGER,
            day INTEGER,
            hour INTEGER,
            day_of_year INTEGER,
            created_at TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    print("Tabell skapad/kontrollerad")

def check_database(db_path):
    """Kontrollera vad som finns i databasen"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM weather_historical")
    count = cursor.fetchone()[0]
    
    cursor.execute("SELECT DISTINCT year FROM weather_historical ORDER BY year")
    years = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    
    print(f"Befintliga poster: {count}")
    print(f"Befintliga år: {years}")
    
    return count, years

def fetch_year_data(cfg, year):
    """Hämta data för ett år"""
    print(f"Hämtar data för {year}...")
    
    # Setup API
    cache_session = requests_cache.CachedSession('.cache', expire_after=-1)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)
    
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": cfg["api"]["params"]["latitude"],
        "longitude": cfg["api"]["params"]["longitude"],
        "start_date": f"{year}-09-01",
        "end_date": f"{year}-10-31",
        "hourly": ["temperature_2m", "relative_humidity_2m", "dew_point_2m", 
                  "wind_speed_10m", "cloud_cover", "pressure_msl", "rain"]
    }
    
    # API-anrop
    responses = openmeteo.weather_api(url, params=params)
    response = responses[0]
    hourly = response.Hourly()
    
    # Bygg DataFrame
    hourly_data = {
        "valid_time": pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left"
        )
    }
    
    # Lägg till data
    hourly_data["temperature_2m"] = hourly.Variables(0).ValuesAsNumpy()
    hourly_data["relative_humidity_2m"] = hourly.Variables(1).ValuesAsNumpy()
    hourly_data["dew_point_2m"] = hourly.Variables(2).ValuesAsNumpy()
    hourly_data["wind_speed_10m"] = hourly.Variables(3).ValuesAsNumpy()
    hourly_data["cloud_cover"] = hourly.Variables(4).ValuesAsNumpy()
    hourly_data["pressure_msl"] = hourly.Variables(5).ValuesAsNumpy()
    hourly_data["rain"] = hourly.Variables(6).ValuesAsNumpy()
    
    df = pd.DataFrame(data=hourly_data)
    
    # Konvertera tid
    df["valid_time"] = df["valid_time"].dt.tz_convert("Europe/Stockholm").dt.tz_localize(None)
    df["year"] = df["valid_time"].dt.year
    df["month"] = df["valid_time"].dt.month
    df["day"] = df["valid_time"].dt.day
    df["hour"] = df["valid_time"].dt.hour
    df["day_of_year"] = df["valid_time"].dt.dayofyear
    
    # Förbered för databas
    df["valid_time"] = df["valid_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"  {len(df)} poster hämtade")
    
    return df

def save_data(df, db_path):
    """Spara data till databas"""
    conn = sqlite3.connect(db_path)
    
    saved_count = 0
    for _, row in df.iterrows():
        try:
            conn.execute("""
                INSERT INTO weather_historical (
                    valid_time, temperature_2m, relative_humidity_2m, dew_point_2m,
                    wind_speed_10m, cloud_cover, pressure_msl, rain,
                    year, month, day, hour, day_of_year, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['valid_time'], row['temperature_2m'], row['relative_humidity_2m'], 
                row['dew_point_2m'], row['wind_speed_10m'], row['cloud_cover'], 
                row['pressure_msl'], row['rain'],
                row['year'], row['month'], row['day'], row['hour'], 
                row['day_of_year'], row['created_at']
            ))
            saved_count += 1
        except sqlite3.IntegrityError:
            # Hoppa över dubbletter (valid_time redan finns)
            continue
    
    conn.commit()
    conn.close()
    
    print(f"  {saved_count} poster sparade")
    return saved_count

def main():
    """Huvudfunktion"""
    print("ENKEL HISTORICAL FETCHER")
    print("=" * 40)
    
    # Ladda config
    cfg = load_config()
    db_path = cfg["storage"]["sqlite_path"]
    
    # Skapa tabell
    create_table(db_path)
    
    # Kontrollera befintlig data
    count, years = check_database(db_path)
    
    # Definiera år att hämta
    current_year = datetime.now().year
    all_years = list(range(current_year - 10, current_year))
    
    if count == 0:
        years_to_fetch = all_years
        print(f"Databasen är tom - hämtar alla år: {years_to_fetch}")
    else:
        missing_years = [y for y in all_years if y not in years]
        if missing_years:
            years_to_fetch = missing_years
            print(f"Hämtar saknade år: {years_to_fetch}")
        else:
            print("All data finns redan - inget att hämta")
            return
    
    # Hämta data
    total_saved = 0
    successful_years = []
    
    for i, year in enumerate(years_to_fetch, 1):
        try:
            print(f"\n[{i}/{len(years_to_fetch)}] År {year}")
            df = fetch_year_data(cfg, year)
            saved = save_data(df, db_path)
            total_saved += saved
            successful_years.append(year)
            
            if i < len(years_to_fetch):
                time.sleep(1)
                
        except Exception as e:
            print(f"  FEL: {e}")
            continue
    
    # Sammanfattning
    print(f"\n" + "=" * 40)
    print("SAMMANFATTNING")
    print("=" * 40)
    print(f"Framgångsrika år: {successful_years}")
    print(f"Totalt sparade poster: {total_saved:,}")
    
    # Slutkontroll
    final_count, final_years = check_database(db_path)
    print(f"\nSlutstatus:")
    print(f"  Totalt poster i databas: {final_count:,}")
    print(f"  År med data: {final_years}")
    
    if total_saved > 0:
        print(f"\nFRAMGÅNG! Data hämtad och sparad")
    else:
        print(f"\nIngen ny data hämtad")

if __name__ == "__main__":
    main()