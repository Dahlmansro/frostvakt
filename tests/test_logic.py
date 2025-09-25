# test_frost_logic.py
"""
Testa frost-logiken med olika scenarier
"""
import pandas as pd
from datetime import datetime
from src.advanced_frost_analyzer import analyze_dataframe_advanced

# Testdata med olika scenarier
test_cases = [
    # Scenario 1: Natt, minusgrader (ska varna)
    {'valid_time': '2025-01-15 02:00:00', 'temperature_2m': -2.0, 'wind_speed_10m': 1.5, 'cloud_cover': 20},
    
    # Scenario 2: Dag, plusgrader (ska INTE varna - nytt filter)
    {'valid_time': '2025-01-15 14:00:00', 'temperature_2m': 2.0, 'wind_speed_10m': 1.5, 'cloud_cover': 20},
    
    # Scenario 3: Dag, minusgrader (ska varna - frost är frost!)
    {'valid_time': '2025-01-15 14:00:00', 'temperature_2m': -1.0, 'wind_speed_10m': 1.5, 'cloud_cover': 20},
    
    # Scenario 4: Natt, precis över noll (ska varna vid vindstilla)
    {'valid_time': '2025-01-15 23:00:00', 'temperature_2m': 1.0, 'wind_speed_10m': 1.0, 'cloud_cover': 10},
    
    # Scenario 5: Natt, kallare än 3°C men mycket vind (ska INTE varna)
    {'valid_time': '2025-01-15 23:00:00', 'temperature_2m': 2.5, 'wind_speed_10m': 5.0, 'cloud_cover': 30},
]

df_test = pd.DataFrame(test_cases)
df_test['valid_time'] = pd.to_datetime(df_test['valid_time'])
df_test['relative_humidity_2m'] = 85.0  # Lägg till fuktighetsvärde

print("TEST AV FROST-LOGIK")
print("=" * 80)

# Kör analys
result = analyze_dataframe_advanced(df_test, rolling_hours=1)

# Visa resultat
for idx, row in result.iterrows():
    hour = row['valid_time'].hour
    temp = row['temperature_2m']
    wind = row['wind_speed_10m']
    warning = row['frost_warning']
    risk = row['frost_risk_level']
    
    day_night = "DAG" if 8 <= hour <= 17 else "NATT"
    
    print(f"\nScenario {idx + 1}: {day_night} kl {hour:02d}:00")
    print(f"  Temp: {temp:.1f}°C, Vind: {wind:.1f} m/s")
    print(f"  Varning: {'JA' if warning else 'NEJ'} (Risk: {risk})")
    print(f"  Förväntat: ", end="")
    
    # Validera mot förväntningar
    if idx == 0:  # Natt, minusgrader
        print("JA - Kall natt")
        if not warning:
            print("  ❌ FEL! Skulle varna")
    elif idx == 1:  # Dag, plusgrader
        print("NEJ - Dagtid med plusgrader")
        if warning:
            print("  ❌ FEL! Skulle inte varna")
    elif idx == 2:  # Dag, minusgrader
        print("JA - Minusgrader även på dagen")
        if not warning:
            print("  ❌ FEL! Skulle varna")
    elif idx == 3:  # Natt, 1°C vindstilla
        print("JA - Risk vid vindstilla")
        if not warning:
            print("  ❌ FEL! Skulle varna")
    elif idx == 4:  # Natt, 2.5°C mycket vind
        print("NEJ - För varmt och blåsigt")
        if warning:
            print("  ❌ FEL! Skulle inte varna")

print("\n" + "=" * 80)