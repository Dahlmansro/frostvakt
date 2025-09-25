# frost_algorithm_evaluation.py
"""
Algoritm utvärdering och validering

Testar och jämför olika frostdetekteringsalgoritmer mot historiska data.

Syfte:
- Jämföra olika strategier (dagtidsfilter, molntäcke, luftfuktighet)
- Identifiera optimal algoritm 

"""
import sqlite3
import pandas as pd
import numpy as np
import yaml
from datetime import datetime
from typing import Tuple

# Konfiguration

def load_config():
    """Ladda konfiguration från config.yaml"""
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_historical_data():
    """Ladda historisk väderdata för validering"""
    cfg = load_config()
    db_path = cfg["storage"]["sqlite_path"]
    
    conn = sqlite3.connect(db_path)
    query = """
        SELECT valid_time, temperature_2m, wind_speed_10m, relative_humidity_2m,
               cloud_cover, year, month, day, hour
        FROM weather_historical 
        WHERE temperature_2m IS NOT NULL AND wind_speed_10m IS NOT NULL
        ORDER BY valid_time
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    df['valid_time'] = pd.to_datetime(df['valid_time'])
    df['actual_frost'] = df['temperature_2m'] <= 0
    df['is_daytime'] = df['hour'].between(8, 17)
    
    print(f"Dataset: {len(df):,} observationer")
    print(f"Faktiska frostfall: {df['actual_frost'].sum():,} ({df['actual_frost'].mean():.1%})")
    
    return df

# Hjälpfunktioner

def calculate_cloud_impact_factor(cloud_cover: float) -> float:
    """Beräkna molnpåverkansfaktor (1.5 = klar himmel ökar risk, 0.7 = mulet minskar)"""
    if pd.isna(cloud_cover):
        return 1.0
    if cloud_cover <= 20:
        return 1.5
    elif cloud_cover <= 50:
        return 1.2
    elif cloud_cover <= 80:
        return 1.0
    else:
        return 0.7

def calculate_dew_point_impact(temp: float, humidity: float) -> Tuple[float, float]:
    """Beräkna daggpunkt och påverkansfaktor"""
    if pd.isna(temp) or pd.isna(humidity):
        return None, 1.0
    
    a, b = 17.27, 237.7
    alpha = ((a * temp) / (b + temp)) + np.log(humidity / 100.0)
    dew_point = (b * alpha) / (a - alpha)
    dew_point_depression = temp - dew_point
    
    if dew_point_depression < 2:
        return dew_point, 1.3
    elif dew_point_depression < 4:
        return dew_point, 1.1
    else:
        return dew_point, 1.0

def calculate_rolling_mean(df: pd.DataFrame, hours: int = 3) -> pd.DataFrame:
    """Beräkna rullande medeltemperatur"""
    df_copy = df.copy().sort_values('valid_time')
    df_copy['temp_rolling_mean'] = df_copy['temperature_2m'].rolling(
        window=hours, min_periods=1
    ).mean().round(2)
    return df_copy


# Algoritmer

def algorithm_original(temp, wind):
    """Basalgoritm utan filter"""
    if pd.isna(temp) or pd.isna(wind):
        return False
    if temp <= 0:
        return True
    elif temp <= 1 and 2 <= wind <= 4:
        return True
    elif temp <= 3 and wind < 2:
        return True
    return False

def algorithm_with_daytime_filter(temp, wind, hour):
    """Algoritm med dagtidsfilter (ingen varning 08-17 vid plusgrader)"""
    if pd.isna(temp) or pd.isna(wind):
        return False
    if 8 <= hour <= 17 and temp > 0:
        return False
    if temp <= 0:
        return True
    elif temp <= 1 and 2 <= wind <= 4:
        return True
    elif temp <= 3 and wind < 2:
        return True
    return False

def algorithm_with_clouds_and_daytime(temp, wind, cloud_cover, hour):
    """Algoritm med molntäcke och dagtidsfilter"""
    if pd.isna(temp) or pd.isna(wind):
        return False
    if 8 <= hour <= 17 and temp > 0:
        return False
    if temp <= 0:
        return True
    elif temp <= 1 and 2 <= wind <= 4:
        return True
    elif temp <= 3 and wind < 2:
        return True
    
    cloud_factor = calculate_cloud_impact_factor(cloud_cover)
    if cloud_factor >= 1.4 and temp <= 2 and wind < 3:
        return True
    return False

def algorithm_comprehensive(temp, wind, cloud_cover, humidity, hour):
    """
    Komplett algoritm med dynamiska tröskelvärden
    - Dagtidsfilter (08-17)
    - Molnpåverkan justerar temperaturtrösklar
    - Luftfuktighet för extra precision
    """
    if pd.isna(temp) or pd.isna(wind):
        return False
    
    # Dagtidsfilter
    if 8 <= hour <= 17 and temp > 0:
        return False
    
    # Grundrisk
    if temp <= 0:
        return True
    
    # Dynamisk tröskel baserad på molntäcke
    cloud_factor = calculate_cloud_impact_factor(cloud_cover)
    if cloud_factor >= 1.4:
        temp_limit = 3.0
    elif cloud_factor >= 1.1:
        temp_limit = 2.0
    else:
        temp_limit = 1.0
    
    if temp <= temp_limit and wind < 4:
        return True
    
    # Extra check med luftfuktighet
    if not pd.isna(humidity) and temp <= 2 and wind < 3 and humidity > 85:
        return True
    
    return False

def algorithm_advanced_with_risk_levels(temp_rolling, wind, cloud_cover, humidity, hour):
    """Algoritm med rullande medel och riskjustering"""
    if pd.isna(temp_rolling) or pd.isna(wind):
        return False
    
    if hour is not None and 8 <= hour <= 17 and temp_rolling > 0:
        return False
    
    base_risk = 0
    if temp_rolling <= 0:
        base_risk = 3
    elif temp_rolling <= 1 and 2 <= wind <= 4:
        base_risk = 2
    elif temp_rolling <= 3 and wind < 2:
        base_risk = 1
    else:
        return False
    
    # Justera risk med moln och luftfuktighet
    cloud_factor = calculate_cloud_impact_factor(cloud_cover)
    _, humidity_factor = calculate_dew_point_impact(temp_rolling, humidity) if not pd.isna(humidity) else (None, 1.0)
    
    adjusted_risk = base_risk
    if not pd.isna(cloud_cover):
        if cloud_factor >= 1.3 and base_risk >= 1:
            adjusted_risk = min(3, base_risk + 1)
        elif cloud_factor <= 0.8 and base_risk >= 2:
            adjusted_risk = max(1, base_risk - 1)
    
    if humidity_factor >= 1.2 and adjusted_risk >= 1 and adjusted_risk < 3:
        adjusted_risk = min(3, adjusted_risk + 1)
    
    return adjusted_risk > 0

# Utvärdering

def evaluate_algorithm(df, algorithm_func, param_names, use_rolling_mean=False):
    """Utvärdera algoritmprestanda"""
    df_eval = df.copy()
    if use_rolling_mean:
        df_eval = calculate_rolling_mean(df_eval, hours=3)
        temp_col = 'temp_rolling_mean'
    else:
        temp_col = 'temperature_2m'
    
    predictions = []
    for _, row in df_eval.iterrows():
        params = [row[temp_col], row['wind_speed_10m']] + [row[p] for p in param_names]
        try:
            predictions.append(algorithm_func(*params))
        except:
            predictions.append(False)
    
    predictions = pd.Series(predictions)
    actual = df['actual_frost']
    
    tp = ((actual) & (predictions)).sum()
    fp = ((~actual) & (predictions)).sum()
    fn = ((actual) & (~predictions)).sum()
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    return {
        'recall': recall,
        'precision': precision,
        'f1_score': f1,
        'true_positives': int(tp),
        'false_positives': int(fp),
        'false_negatives': int(fn)
    }

# Rapportering

def analyze_daytime_impact(df):
    """Analysera dagtidsfilterets säkerhet"""
    print("\n" + "="*70)
    print("DAGTIDSFILTER - SÄKERHETSANALYS")
    print("="*70)
    
    daytime_frost = df[df['is_daytime'] & df['actual_frost']]
    daytime_frost_plus = daytime_frost[daytime_frost['temperature_2m'] > 0]
    
    print(f"Frostfall på dagtid (08-17): {len(daytime_frost)}")
    print(f"Därav med plusgrader: {len(daytime_frost_plus)}")
    
    if len(daytime_frost_plus) == 0:
        print("✅ SÄKERT: Dagtidsfilter missar inga faktiska frostfall")
    else:
        print(f" VARNING: {len(daytime_frost_plus)} frostfall med plusgrader på dagtid")
        for _, row in daytime_frost_plus.head(3).iterrows():
            print(f"   {row['year']}-{row['month']:02d}-{row['day']:02d} {row['hour']:02d}:00 - "
                  f"Temp: {row['temperature_2m']:.1f}°C")

def compare_algorithms(df):
    """Jämför alla algoritmer"""
    algorithms = [
        ('Original', algorithm_original, [], False),
        ('+ Dagtidsfilter', algorithm_with_daytime_filter, ['hour'], False),
        ('+ Moln & Dagtid', algorithm_with_clouds_and_daytime, ['cloud_cover', 'hour'], False),
        ('+ Komplett', algorithm_comprehensive, ['cloud_cover', 'relative_humidity_2m', 'hour'], False),
        ('+ Advanced (Rullande)', algorithm_advanced_with_risk_levels, ['cloud_cover', 'relative_humidity_2m', 'hour'], True)
    ]
    
    print("\n" + "="*70)
    print("ALGORITM-JÄMFÖRELSE")
    print("="*70)
    print(f"\n{'Algoritm':<30} {'Recall':>9} {'Precision':>10} {'F1':>8} {'Missade':>8} {'Falska':>8}")
    print("-" * 70)
    
    results = []
    for name, func, params, use_rolling in algorithms:
        metrics = evaluate_algorithm(df, func, params, use_rolling)
        results.append((name, metrics))
        print(f"{name:<30} {metrics['recall']:>8.1%} {metrics['precision']:>9.1%} "
              f"{metrics['f1_score']:>8.3f} {metrics['false_negatives']:>8} {metrics['false_positives']:>8}")
    
    print("-" * 70)
    
    # Identifiera bästa
    best = max(results, key=lambda x: x[1]['f1_score'])
    print(f"\n🏆 BÄST: {best[0]} (F1={best[1]['f1_score']:.3f})")
    
    return results

# Huvudprogram

def main():
    """Utvärdera frost-algoritmer"""
    print("="*70)
    print("FROST-ALGORITM UTVÄRDERING")
    print(f"Körning: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    df = load_historical_data()
    
    if df['actual_frost'].sum() < 10:
        print(f"\n❌ FEL: För få frostfall ({df['actual_frost'].sum()}) för validering")
        return
    
    analyze_daytime_impact(df)
    results = compare_algorithms(df)
    
    print("\n" + "="*70)
    print("  • Använder dagtidsfilter, molntäcke och luftfuktighet")
    print("\nImplementerad i: src/advanced_frost_analyzer.py")
    print("="*70)

if __name__ == "__main__":
    main()
