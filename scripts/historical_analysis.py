# historical_analysis.py
"""
Analyserar historisk data och beräkna min/max-värden för varje dag och timme för att använda i dashboard
"""
import sqlite3
import pandas as pd
import numpy as np
import yaml
from datetime import datetime, timedelta

def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def create_historical_reference_table(engine):
    """Skapa tabell för historiska referensvärden"""
    from sqlalchemy import text
    
    reference_table_sql = text("""
        CREATE TABLE IF NOT EXISTS historical_reference (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month INTEGER NOT NULL,
            day INTEGER NOT NULL,
            hour INTEGER NOT NULL,
            temp_min_10y REAL,
            temp_max_10y REAL,
            temp_mean_10y REAL,
            humidity_min_10y REAL,
            humidity_max_10y REAL,
            humidity_mean_10y REAL,
            wind_min_10y REAL,
            wind_max_10y REAL,
            wind_mean_10y REAL,
            pressure_min_10y REAL,
            pressure_max_10y REAL,
            pressure_mean_10y REAL,
            observations_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(month, day, hour)
        )
    """)
    
    with engine.begin() as conn:
        conn.execute(reference_table_sql)
    
    print("Tabell 'historical_reference' skapad/kontrollerad")

def calculate_historical_references():
    """Beräkna historiska referensvärden för varje dag och timme"""
    print("Beräknar historiska referensvärden...")
    
    cfg = load_config()
    db_path = cfg["storage"]["sqlite_path"]
    
    # Läs all historisk data
    conn = sqlite3.connect(db_path)
    
    print("Laddar historisk data...")
    df = pd.read_sql_query("""
        SELECT month, day, hour, 
               temperature_2m, relative_humidity_2m, 
               wind_speed_10m, pressure_msl
        FROM weather_historical 
        WHERE month IN (9, 10)
        ORDER BY month, day, hour
    """, conn)
    
    print(f"Analyserar {len(df):,} observationer från 10 år")
    
    # Gruppera per månad, dag och timme
    print("Beräknar statistik per dag och timme...")
    
    grouped = df.groupby(['month', 'day', 'hour']).agg({
        'temperature_2m': ['min', 'max', 'mean', 'count'],
        'relative_humidity_2m': ['min', 'max', 'mean'],
        'wind_speed_10m': ['min', 'max', 'mean'],
        'pressure_msl': ['min', 'max', 'mean']
    }).round(1)
    
    # Förenkla kolumnnamn
    grouped.columns = [
        'temp_min_10y', 'temp_max_10y', 'temp_mean_10y', 'observations_count',
        'humidity_min_10y', 'humidity_max_10y', 'humidity_mean_10y',
        'wind_min_10y', 'wind_max_10y', 'wind_mean_10y',
        'pressure_min_10y', 'pressure_max_10y', 'pressure_mean_10y'
    ]
    
    # Återställ index för att få month, day, hour som kolumner
    reference_df = grouped.reset_index()
    
    print(f"Genererade {len(reference_df)} unika dag/timme-kombinationer")
    
    # Skapa SQLAlchemy engine för att spara
    from sqlalchemy import create_engine
    abs_path = cfg["storage"]["sqlite_path"]
    engine = create_engine(f"sqlite:///{abs_path}", future=True)
    
    # Skapa referenstabell
    create_historical_reference_table(engine)
    
    # Spara referensdata
    print("Sparar referensvärden till databas...")
    reference_df.to_sql('historical_reference', engine, if_exists='replace', index=False)
    
    conn.close()
    
    # Visa sammanfattning
    print("\nSammanfattning av historiska referensvärden:")
    print("=" * 50)
    
    # Temperaturstatistik
    print("Temperatur (°C):")
    print(f"  Absolut min: {reference_df['temp_min_10y'].min():.1f}°C")
    print(f"  Absolut max: {reference_df['temp_max_10y'].max():.1f}°C")
    print(f"  Genomsnittlig dygnsvariation: {(reference_df['temp_max_10y'] - reference_df['temp_min_10y']).mean():.1f}°C")
    
    # Visa extremer - FIXAD VERSION
    print(f"\nExtremfall:")
    
    # Kallaste observationer med säker typkonvertering
    coldest_idx = reference_df['temp_min_10y'].idxmin()
    coldest = reference_df.loc[coldest_idx]
    coldest_day = int(float(coldest['day']))
    coldest_month = int(float(coldest['month']))
    coldest_hour = int(float(coldest['hour']))
    print(f"  Kallaste: {coldest['temp_min_10y']:.1f}°C den {coldest_day}/{coldest_month} kl {coldest_hour:02d}:00")
    
    # Varmaste observationer med säker typkonvertering
    warmest_idx = reference_df['temp_max_10y'].idxmax()
    warmest = reference_df.loc[warmest_idx]
    warmest_day = int(float(warmest['day']))
    warmest_month = int(float(warmest['month']))
    warmest_hour = int(float(warmest['hour']))
    print(f"  Varmaste: {warmest['temp_max_10y']:.1f}°C den {warmest_day}/{warmest_month} kl {warmest_hour:02d}:00")
    
    # Månadsstatistik
    print(f"\nMånadsstatistik:")
    monthly_stats = reference_df.groupby('month').agg({
        'temp_min_10y': 'mean',
        'temp_max_10y': 'mean', 
        'temp_mean_10y': 'mean',
        'observations_count': 'sum'
    }).round(1)
    
    month_names = {9: 'September', 10: 'Oktober'}
    for month in monthly_stats.index:
        stats = monthly_stats.loc[month]
        print(f"  {month_names[month]}:")
        print(f"    Medeltemperatur: {stats['temp_mean_10y']:.1f}°C")
        print(f"    Typisk min-max: {stats['temp_min_10y']:.1f}°C - {stats['temp_max_10y']:.1f}°C")
        print(f"    Observationer: {int(stats['observations_count']):,}")
    
    print(f"\nHistoriska referensvärden sparade i 'historical_reference'-tabellen")
    print("Nu kan dashboarden visa aktuella värden jämfört med 10-års historik!")
    
    return reference_df

def create_daily_summary():
    """Skapa daglig sammanfattning för enklare dashboard-användning"""
    print("\nSkapar daglig sammanfattning...")
    
    cfg = load_config()
    conn = sqlite3.connect(cfg["storage"]["sqlite_path"])
    
    # Sammanfatta per dag (alla timmar)
    daily_summary = pd.read_sql_query("""
        SELECT month, day,
               MIN(temp_min_10y) as daily_temp_min,
               MAX(temp_max_10y) as daily_temp_max,
               AVG(temp_mean_10y) as daily_temp_mean,
               COUNT(*) as hours_available
        FROM historical_reference
        GROUP BY month, day
        ORDER BY month, day
    """, conn)
    
    # Spara som ny tabell
    daily_summary.to_sql('daily_temperature_reference', conn, if_exists='replace', index=False)
    
    print(f"Daglig sammanfattning skapad: {len(daily_summary)} dagar")
    print("Exempel på dagliga extremer:")
    
    # Visa några exempel
    for _, row in daily_summary.head(5).iterrows():
        day = int(float(row['day']))
        month = int(float(row['month']))
        print(f"  {day}/{month}: {row['daily_temp_min']:.1f}°C - {row['daily_temp_max']:.1f}°C (medel: {row['daily_temp_mean']:.1f}°C)")
    
    conn.close()

def analyze_frost_patterns():
    """Analysera frostmönster i historisk data"""
    print("\nAnalyserar historiska frostmönster...")
    
    cfg = load_config()
    conn = sqlite3.connect(cfg["storage"]["sqlite_path"])
    
    # Hitta alla frostobservationer
    frost_query = """
        SELECT year, month, day, hour, temperature_2m, wind_speed_10m, dew_point_2m
        FROM weather_historical 
        WHERE temperature_2m <= 0
        ORDER BY year, month, day, hour
    """
    
    frost_df = pd.read_sql_query(frost_query, conn)
    
    if len(frost_df) > 0:
        print(f"Hittade {len(frost_df)} frostobservationer i 10 års data")
        
        # Första frost per år
        first_frost_by_year = frost_df.groupby('year').first()
        
        print("\nFörsta frost per år:")
        for year in first_frost_by_year.index:
            row = first_frost_by_year.loc[year]
            day = int(float(row['day']))
            month = int(float(row['month']))
            hour = int(float(row['hour']))
            print(f"  {int(year)}: {day}/{month} kl {hour:02d}:00 ({row['temperature_2m']:.1f}°C)")
        
        # Genomsnittligt datum för första frost
        frost_df['date'] = pd.to_datetime(frost_df[['year', 'month', 'day']])
        first_frost_dates = frost_df.groupby('year')['date'].first()
        
        if len(first_frost_dates) > 0:
            # Beräkna dag i året (day of year)
            avg_first_frost_day = first_frost_dates.dt.dayofyear.mean()
            
            # Konvertera tillbaka till datum (använd 2024 som referensår)
            import datetime as dt
            avg_date = dt.datetime(2024, 1, 1) + dt.timedelta(days=avg_first_frost_day - 1)
            
            print(f"\nGenomsnittlig första frost: {avg_date.strftime('%d/%m')} (dag {avg_first_frost_day:.0f} i året)")
    else:
        print("Inga frostobservationer hittades i historisk data")
    
    conn.close()

def main():
    """Huvudfunktion för historisk analys"""
    print("Historisk dataanalys för Frostvakt")
    print("=" * 40)
    
    try:
        # Beräkna referensvärden
        reference_df = calculate_historical_references()
        
        # Skapa daglig sammanfattning
        create_daily_summary()
        
        # Analysera frostmönster
        analyze_frost_patterns()
        
        print("\n" + "=" * 40)
        print("Historisk analys slutförd!")
        print("Följande tabeller är nu tillgängliga:")
        print("  • historical_reference - Timvis min/max för varje dag")
        print("  • daily_temperature_reference - Daglig sammanfattning") 
        print("  • weather_historical - Ursprunglig rådata")
        print("\nNästa steg: Uppdatera dashboarden för att visa historiska jämförelser")
        
    except Exception as e:
        print(f"Fel under analys: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()