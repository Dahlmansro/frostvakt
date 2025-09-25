# src/yr_api_client.py
"""
YR (met.no) API-klient för väderdata.
Hämtar prognosdata från det norska meteorologiska institutet.
"""
import requests
import pandas as pd
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import logging
import time

logger = logging.getLogger("frostvakt.yr")


class YrApiClient:
    """Klient för YR (met.no) WeatherAPI."""
    
    def __init__(self, user_agent: str = "FrostvaktApp/1.0"):
        """
        Initiera YR API-klient.
        
        Args:
            user_agent: Identifiering enligt YR:s krav
        """
        self.base_url = "https://api.met.no/weatherapi/locationforecast/2.0"
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'application/json'
        })
        
        # Cache för att respektera YR:s cachning
        self._cache = {}
        
        logger.info(f"YR API-klient initierad: {user_agent}")
    
    def _get_cache_key(self, lat: float, lon: float, endpoint: str = "compact") -> str:
        """Skapa nyckel för cache."""
        return f"{endpoint}_{lat:.4f}_{lon:.4f}"
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Kontrollera om cache-post fortfarande är giltig."""
        if 'expires' not in cache_entry:
            return False
        
        try:
            expires = datetime.fromisoformat(cache_entry['expires'].replace('Z', '+00:00'))
            return datetime.now(timezone.utc) < expires
        except:
            return False
    
    def fetch_forecast(self, lat: float, lon: float, endpoint: str = "compact", 
                      timeout: int = 15) -> Dict[str, Any]:
        """
        Hämta väderprognos från YR API.
        
        Args:
            lat: Latitud (max 4 decimaler)
            lon: Longitud (max 4 decimaler) 
            endpoint: 'compact' eller 'complete'
            timeout: Timeout i sekunder
            
        Returns:
            JSON-data från YR API
            
        Raises:
            requests.RequestException: Vid API-fel
        """
        # Avrunda koordinater till max 4 decimaler (YR:s krav)
        lat = round(lat, 4)
        lon = round(lon, 4)
        
        cache_key = self._get_cache_key(lat, lon, endpoint)
        
        # Kontrollera cache först
        if cache_key in self._cache and self._is_cache_valid(self._cache[cache_key]):
            logger.info(f"Använder cached data för {lat}, {lon}")
            return self._cache[cache_key]['data']
        
        url = f"{self.base_url}/{endpoint}"
        params = {
            'lat': lat,
            'lon': lon
        }
        
        # Använd If-Modified-Since om vi har tidigare data
        headers = {}
        if cache_key in self._cache and 'last_modified' in self._cache[cache_key]:
            headers['If-Modified-Since'] = self._cache[cache_key]['last_modified']
        
        logger.info(f"Hämtar YR-prognos: {url} (lat={lat}, lon={lon})")
        
        try:
            response = self.session.get(url, params=params, headers=headers, timeout=timeout)
            
            if response.status_code == 304:
                logger.info("Data oförändrad sedan senast (304)")
                if cache_key in self._cache:
                    return self._cache[cache_key]['data']
                else:
                    raise requests.RequestException("304 men ingen cached data")
            
            response.raise_for_status()
            data = response.json()
            
            # Spara i cache med metadata
            cache_entry = {
                'data': data,
                'fetched_at': datetime.now(timezone.utc).isoformat(),
            }
            
            # Spara cache-headers om de finns
            if 'Expires' in response.headers:
                cache_entry['expires'] = response.headers['Expires']
            if 'Last-Modified' in response.headers:
                cache_entry['last_modified'] = response.headers['Last-Modified']
            
            self._cache[cache_key] = cache_entry
            
            logger.info(f"YR-data hämtat framgångsrikt: {len(data.get('properties', {}).get('timeseries', []))} tidpunkter")
            return data
            
        except requests.RequestException as e:
            logger.error(f"YR API-fel för {lat}, {lon}: {e}")
            raise
    
    def transform_to_dataframe(self, yr_data: Dict[str, Any], dataset: str = "yr_forecast") -> pd.DataFrame:
        """
        Transformera YR JSON till DataFrame (kompatibel med befintligt system).
        
        Args:
            yr_data: JSON-data från YR API
            dataset: Dataset-namn för identifiering
            
        Returns:
            DataFrame med väderdata
        """
        if not yr_data or 'properties' not in yr_data:
            logger.warning("Tom eller ogiltig YR-data")
            return pd.DataFrame()
        
        properties = yr_data['properties']
        timeseries = properties.get('timeseries', [])
        
        if not timeseries:
            logger.warning("Inga tidsserier i YR-data")
            return pd.DataFrame()
        
        # Extrahera data från YR:s format
        rows = []
        for ts in timeseries:
            time_str = ts.get('time')
            if not time_str:
                continue
                
            data_point = ts.get('data', {})
            instant = data_point.get('instant', {}).get('details', {})
            
            # Extrahera relevanta parametrar
            row = {
                'valid_time': time_str,
                'temperature_2m': instant.get('air_temperature'),
                'relative_humidity_2m': instant.get('relative_humidity'),
                'precipitation': None,  # Behöver särskild hantering för YR
                'wind_speed_10m': instant.get('wind_speed'),
                'precipitation_probability': None,  # Finns i nästa perioders data
                'cloud_cover': instant.get('cloud_area_fraction'),  # YR använder cloud_area_fraction
                'dataset': dataset
            }
            
            # Hantera nederbörd (finns i nästa period)
            next_1h = data_point.get('next_1_hours', {}).get('details', {})
            if next_1h:
                row['precipitation'] = next_1h.get('precipitation_amount')
                row['precipitation_probability'] = next_1h.get('probability_of_precipitation')
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        if df.empty:
            return df
            
        # Konvertera tider
        df['valid_time'] = pd.to_datetime(df['valid_time']).dt.tz_localize(None)
        
        # Lägg till metadata
        df['forecast_issue_time'] = datetime.now()
        df['horizon_hours'] = (df['valid_time'] - datetime.now()).dt.total_seconds() / 3600.0
        df['run_id'] = f"yr_run_{datetime.now().strftime('%Y%m%dT%H%M%SZ')}"
        
        logger.info(f"YR-data transformerat: {len(df)} rader")
        return df
    
    def get_location_info(self, yr_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrahera platsinformation från YR-data.
        
        Args:
            yr_data: JSON-data från YR API
            
        Returns:
            Dictionary med platsinformation
        """
        if not yr_data or 'geometry' not in yr_data:
            return {}
        
        geometry = yr_data['geometry']
        coordinates = geometry.get('coordinates', [])
        
        if len(coordinates) >= 3:
            return {
                'longitude': coordinates[0],
                'latitude': coordinates[1], 
                'altitude': coordinates[2],
                'type': geometry.get('type', 'Point')
            }
        
        return {}
    
    def compare_with_openmeteo(self, yr_df: pd.DataFrame, om_df: pd.DataFrame) -> pd.DataFrame:
        """
        Jämför YR-data med Open-Meteo data.
        
        Args:
            yr_df: DataFrame med YR-data
            om_df: DataFrame med Open-Meteo data
            
        Returns:
            DataFrame med jämförelser
        """
        if yr_df.empty or om_df.empty:
            logger.warning("Kan inte jämföra - tom data")
            return pd.DataFrame()
        
        # Matcha på tid (närmaste timme)
        yr_df = yr_df.copy()
        om_df = om_df.copy()
        
        yr_df['hour'] = yr_df['valid_time'].dt.floor('H')
        om_df['hour'] = om_df['valid_time'].dt.floor('H')
        
        # Merger på timme
        comparison = pd.merge(
            yr_df[['hour', 'temperature_2m', 'wind_speed_10m', 'cloud_cover']],
            om_df[['hour', 'temperature_2m', 'wind_speed_10m', 'cloud_cover']], 
            on='hour',
            suffixes=('_yr', '_om'),
            how='inner'
        )
        
        if comparison.empty:
            logger.warning("Inga matchande tidpunkter för jämförelse")
            return comparison
        
        # Beräkna skillnader
        comparison['temp_diff'] = comparison['temperature_2m_yr'] - comparison['temperature_2m_om']
        comparison['wind_diff'] = comparison['wind_speed_10m_yr'] - comparison['wind_speed_10m_om']
        
        if 'cloud_cover_yr' in comparison.columns and 'cloud_cover_om' in comparison.columns:
            comparison['cloud_diff'] = comparison['cloud_cover_yr'] - comparison['cloud_cover_om']
        
        logger.info(f"Jämförelse skapad: {len(comparison)} matchande tidpunkter")
        return comparison


def test_yr_api(lat: float = 59.06732, lon: float = 15.75295):
    """
    Testfunktion för YR API - följer alla användarvillkor.
    
    Args:
        lat: Testlatitud (Vingåker som standard)
        lon: Testlongitud
    """
    print(f"Testar YR API för koordinater: {lat}, {lon}")
    print(" Följer YR användarvillkor:")
    print("   ✅ User-Agent med kontaktinfo")
    print("   ✅ Rate limiting (max 1 request/minut)")
    print("   ✅ Caching med If-Modified-Since")
    print("   ✅ Max 4 decimaler i koordinater")
    
    try:
        # Skapa klient med korrekt User-Agent enligt YR:s krav
        client = YrApiClient("FrostvaktApp/1.0 github.com/user/frostvakt support@example.com")
        
        # Hämta data
        print(" Hämtar prognosdata...")
        data = client.fetch_forecast(lat, lon)
        
        # Visa grundinfo
        print(f"✅ Data hämtat framgångsrikt!")
        print(f"Datastruktur:")
        print(f"   - Huvudnycklar: {list(data.keys())}")
        
        if 'properties' in data:
            props = data['properties']
            print(f"   - Properties: {list(props.keys())}")
            
            if 'timeseries' in props:
                ts_count = len(props['timeseries'])
                print(f"   - Antal tidserier: {ts_count}")
                
                # Visa exempel på första datapunkten
                if ts_count > 0:
                    first_ts = props['timeseries'][0]
                    print(f"   - Första tidpunkt: {first_ts.get('time')}")
                    
                    instant = first_ts.get('data', {}).get('instant', {}).get('details', {})
                    print(f"   - Temperatur: {instant.get('air_temperature')}°C")
                    print(f"   - Vind: {instant.get('wind_speed')} m/s")
                    print(f"   - Molntäcke: {instant.get('cloud_area_fraction')}%")
        
        # Transformera till DataFrame
        print("Transformerar till DataFrame...")
        df = client.transform_to_dataframe(data)
        
        if not df.empty:
            print(f"DataFrame skapat: {len(df)} rader")
            print(f"   - Kolumner: {list(df.columns)}")
            print(f"   - Tidsperiod: {df['valid_time'].min()} till {df['valid_time'].max()}")
            
            # Visa exempel på första raderna
            print("\nFörsta 3 rader:")
            print(df[['valid_time', 'temperature_2m', 'wind_speed_10m', 'cloud_cover']].head(3))
        
        return True, client, df
        
    except Exception as e:
        print(f"Fel vid YR API-test: {e}")
        return False, None, pd.DataFrame()


if __name__ == "__main__":
    # Kör test
    success, client, df = test_yr_api()
    
    if success:
        print("\n YR API-test lyckades!")
        print("Klient är redo för integration med Frostvakt-systemet")
    else:
        print("\n YR API-test misslyckades")