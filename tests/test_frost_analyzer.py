# test_frost_analyzer.py
"""
Tester för advanced_frost_analyzer modulen.
Kör med: python -m pytest test_frost_analyzer.py -v
"""
import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# FIXAT: Importera från advanced_frost_analyzer istället
from advanced_frost_analyzer import (
    calculate_advanced_frost_risk, 
    analyze_dataframe_advanced,
    calculate_rolling_mean_temperature,
    calculate_cloud_impact_factor
)


class TestCalculateFrostRisk(unittest.TestCase):
    """Tester för calculate_advanced_frost_risk funktionen"""
    
    def test_high_risk_scenarios(self):
        """Testa scenarier som ska ge hög risk"""
        # Temperatur <= 0°C oavsett vind
        risk, level, _ = calculate_advanced_frost_risk(-1.0, 0.5, 50.0)
        self.assertEqual(risk, "hög")
        self.assertEqual(level, 3)
        
        risk, level, _ = calculate_advanced_frost_risk(0.0, 10.0, 50.0)
        self.assertEqual(risk, "hög")
        self.assertEqual(level, 3)
    
    def test_medium_risk_scenarios(self):
        """Testa scenarier som ska ge medel risk"""
        # Temp <= 2°C och vindstilla med halvklart väder
        risk, level, _ = calculate_advanced_frost_risk(1.5, 2.0, 40.0)
        self.assertIn(risk, ["medel", "låg"])
        self.assertGreaterEqual(level, 1)
    
    def test_no_risk_scenarios(self):
        """Testa scenarier som inte ska ge någon risk"""
        # Varm temperatur
        risk, level, _ = calculate_advanced_frost_risk(10.0, 1.0, 50.0)
        self.assertEqual(risk, "ingen")
        self.assertEqual(level, 0)
    
    def test_missing_values(self):
        """Testa med saknade värden (NaN)"""
        risk, level, _ = calculate_advanced_frost_risk(np.nan, 2.0, 50.0)
        self.assertEqual(risk, "okänd")
        self.assertEqual(level, 0)


class TestAnalyzeDataframe(unittest.TestCase):
    """Tester för analyze_dataframe_advanced funktionen"""
    
    def setUp(self):
        """Skapa testdata som körs före varje test"""
        self.test_data = pd.DataFrame({
            'valid_time': pd.date_range('2025-01-01', periods=5, freq='h'),
            'temperature_2m': [-1.0, 1.0, 2.0, 10.0, 0.0],
            'wind_speed_10m': [2.0, 3.0, 1.5, 5.0, 0.5],
            'cloud_cover': [20.0, 50.0, 80.0, 90.0, 10.0],
            'dataset': ['forecast'] * 5
        })
    
    def test_analyze_normal_dataframe(self):
        """Testa analys av normal DataFrame"""
        result = analyze_dataframe_advanced(self.test_data)
        
        # Kontrollera att nya kolumner skapats
        expected_cols = ['frost_risk_level', 'frost_risk_numeric', 'frost_warning', 'temp_rolling_mean']
        for col in expected_cols:
            self.assertIn(col, result.columns, f"Kolumn {col} saknas")
        
        # Kontrollera att vi har rätt antal rader
        self.assertEqual(len(result), 5)
    
    def test_analyze_empty_dataframe(self):
        """Testa med tom DataFrame"""
        empty_df = pd.DataFrame()
        result = analyze_dataframe_advanced(empty_df)
        self.assertTrue(result.empty)
    
    def test_frost_warning_boolean(self):
        """Testa att frost_warning kolumnen är korrekt"""
        result = analyze_dataframe_advanced(self.test_data)
        
        # Kontrollera att vi får varningar för minusgrader
        minus_rows = result[result['temperature_2m'] <= 0]
        if not minus_rows.empty:
            self.assertTrue(minus_rows['frost_warning'].any(), 
                          "Minusgrader borde ge åtminstone en varning")


class TestHelperFunctions(unittest.TestCase):
    """Tester för hjälpfunktioner"""
    
    def test_rolling_mean_calculation(self):
        """Testa rullande medeltemperatur"""
        test_df = pd.DataFrame({
            'temperature_2m': [5.0, 3.0, 1.0, -1.0],
            'valid_time': pd.date_range('2025-01-01', periods=4, freq='h')
        })
        
        result = calculate_rolling_mean_temperature(test_df, hours=2)
        self.assertIn('temp_rolling_mean', result.columns)
        self.assertFalse(result['temp_rolling_mean'].isna().all())
    
    def test_cloud_impact_factor(self):
        """Testa molnpåverkansfaktor"""
        # Klart väder = högre faktor
        clear_factor = calculate_cloud_impact_factor(10.0)
        self.assertGreater(clear_factor, 1.0)
        
        # Mulet = lägre faktor
        cloudy_factor = calculate_cloud_impact_factor(90.0)
        self.assertLess(cloudy_factor, 1.0)


def run_simple_tests():
    """Enkla tester som kan köras utan pytest"""
    print("🧪 Kör enkla frost-tester...")
    
    # Test 1: Basic frost risk calculation
    risk, level, _ = calculate_advanced_frost_risk(-1.0, 2.0, 50.0)
    assert risk == "hög" and level == 3, f"Fel: förväntade hög/3, fick {risk}/{level}"
    print("✅ Test 1 OK: Hög risk vid -1°C")
    
    # Test 2: DataFrame analysis
    test_df = pd.DataFrame({
        'temperature_2m': [-1.0, 5.0],
        'wind_speed_10m': [1.0, 10.0],
        'cloud_cover': [20.0, 80.0]
    })
    result = analyze_dataframe_advanced(test_df)
    assert 'frost_risk_level' in result.columns, "Saknar frost_risk_level kolumn"
    assert result.iloc[0]['frost_warning'] == True, "Första raden borde ha varning"
    print("✅ Test 2 OK: DataFrame analys fungerar")
    
    print("🎉 Alla enkla tester klarade!")
    return True


if __name__ == "__main__":
    print("Välj testmetod:")
    print("1. Enkla tester (snabbt)")
    print("2. Fullständiga unittest")
    print("3. Pytest (kräver: pip install pytest)")
    
    choice = input("Val (1-3): ").strip()
    
    if choice == "1":
        run_simple_tests()
    elif choice == "2":
        print("\nKör unittest...")
        unittest.main(argv=[''], exit=False, verbosity=2)
    elif choice == "3":
        print("\nKör: python -m pytest test_frost_analyzer.py -v")
    else:
        print("Okänt val, kör enkla tester...")
        run_simple_tests()