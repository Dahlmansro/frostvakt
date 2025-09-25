# dashboard_enhanced.py
"""
Frostvakt Dashboard, körs med Streamlit
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from datetime import datetime, timedelta
import sqlite3
import os
import yaml
from typing import Dict, Any

# Sida-konfiguration
st.set_page_config(
    page_title="Frostvakt",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
.frost-warning {
    background-color: #ffe6e6;
    padding: 1rem;
    border-radius: 0.5rem;
    border-left: 5px solid #ff4444;
}
.frost-ok {
    background-color: #e6ffe6;
    padding: 1rem;
    border-radius: 0.5rem;
    border-left: 5px solid #44ff44;
}
.historical-context {
    background-color: #f0f8ff;
    padding: 1rem;
    border-radius: 0.5rem;
    border-left: 5px solid #4488ff;
}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_config() -> Dict[str, Any]:
    """Ladda konfiguration från config.yaml"""
    try:
        with open("config.yaml", "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        st.error(f"Kunde inte ladda config.yaml: {e}")
        return {}


def safe_datetime_convert(series: pd.Series) -> pd.Series:
    """Säker konvertering till datetime"""
    try:
        if series.dtype == 'object':
            return pd.to_datetime(series, format='%Y-%m-%d %H:%M:%S', errors='coerce')
        elif pd.api.types.is_datetime64_any_dtype(series):
            return series
        else:
            return pd.to_datetime(series, errors='coerce')
    except:
        return pd.to_datetime(series, errors='coerce')


@st.cache_data(ttl=300)
def load_weather_data(days_ahead: int = 7) -> pd.DataFrame:
    """Ladda väderdata från SQLite-databasen (framtida prognoser)"""
    cfg = load_config()
    db_path = cfg.get("storage", {}).get("sqlite_path", "data/weather_history_forcast.db")
    
    if not os.path.exists(db_path):
        return pd.DataFrame()
    
    # Hämta data från nu och framåt
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    future_cutoff = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d %H:%M:%S")
    
    query = f"""
    SELECT * FROM weather_hourly 
    WHERE valid_time >= '{current_time}' AND valid_time <= '{future_cutoff}'
    ORDER BY valid_time ASC
    """
    
    try:
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query(query, conn)
            if not df.empty and 'valid_time' in df.columns:
                df['valid_time'] = safe_datetime_convert(df['valid_time'])
            return df
    except Exception as e:
        st.error(f"Fel vid laddning av väderdata: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_frost_warnings(days_ahead: int = 7) -> pd.DataFrame:
    """Ladda frostvarningar från databasen (framtida varningar)"""
    cfg = load_config()
    db_path = cfg.get("storage", {}).get("sqlite_path", "data/weather_history_forcast.db")
    
    if not os.path.exists(db_path):
        return pd.DataFrame()
    
    # FIXAD: Hämta alla framtida varningar (inte bara dagens datum)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    future_cutoff = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d %H:%M:%S")
    
    query = f"""
    SELECT * FROM frost_warnings 
    WHERE valid_time >= '{current_time}' AND valid_time <= '{future_cutoff}'
    ORDER BY valid_time ASC
    """
    
    try:
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query(query, conn)
            if not df.empty:
                if 'valid_time' in df.columns:
                    df['valid_time'] = safe_datetime_convert(df['valid_time'])
                if 'created_at' in df.columns:
                    df['created_at'] = safe_datetime_convert(df['created_at'])
            return df
    except Exception as e:
        st.error(f"Fel vid laddning av frostvarningar: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def load_historical_reference() -> pd.DataFrame:
    """Ladda historiska referensvärden"""
    cfg = load_config()
    db_path = cfg.get("storage", {}).get("sqlite_path", "data/weather_history_forcast.db")
    
    if not os.path.exists(db_path):
        return pd.DataFrame()
    
    query = """
    SELECT month, day, hour, 
           temp_min_10y, temp_max_10y, temp_mean_10y,
           humidity_min_10y, humidity_max_10y, humidity_mean_10y,
           wind_min_10y, wind_max_10y, wind_mean_10y,
           observations_count
    FROM historical_reference
    ORDER BY month, day, hour
    """
    
    try:
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query(query, conn)
            return df
    except Exception as e:
        st.error(f"Fel vid laddning av historiska referenser: {e}")
        return pd.DataFrame()


def get_historical_context(current_temp: float, current_time: datetime, historical_ref: pd.DataFrame) -> Dict[str, Any]:
    """Jämför aktuell temperatur med historiska värden"""
    if historical_ref.empty:
        return {"available": False}
    
    month = current_time.month
    day = current_time.day
    hour = current_time.hour
    
    # Hitta matchande historisk referens
    match = historical_ref[
        (historical_ref['month'] == month) & 
        (historical_ref['day'] == day) & 
        (historical_ref['hour'] == hour)
    ]
    
    if match.empty:
        return {"available": False}
    
    ref = match.iloc[0]
    
    # Beräkna percentil ungefär
    temp_range = ref['temp_max_10y'] - ref['temp_min_10y']
    if temp_range > 0:
        percentile = ((current_temp - ref['temp_min_10y']) / temp_range) * 100
        percentile = max(0, min(100, percentile))
    else:
        percentile = 50
    
    # Klassificera temperaturen
    if current_temp < ref['temp_min_10y']:
        classification = "Extremt kallt"
        color = "#0066cc"
    elif current_temp > ref['temp_max_10y']:
        classification = "Extremt varmt"
        color = "#cc6600"
    elif percentile < 25:
        classification = "Kallt för årstiden"
        color = "#4488ff"
    elif percentile > 75:
        classification = "Varmt för årstiden"
        color = "#ff8844"
    else:
        classification = "Normalt för årstiden"
        color = "#44aa44"
    
    return {
        "available": True,
        "historical_min": ref['temp_min_10y'],
        "historical_max": ref['temp_max_10y'],
        "historical_mean": ref['temp_mean_10y'],
        "percentile": percentile,
        "classification": classification,
        "color": color,
        "observations": ref['observations_count']
    }

def create_enhanced_temperature_chart(df: pd.DataFrame, historical_ref: pd.DataFrame) -> go.Figure:
    """Skapa förbättrat temperatur-diagram med historiska min/max"""
    if df.empty:
        return go.Figure().add_annotation(text="Ingen data tillgänglig", 
                                        xref="paper", yref="paper", x=0.5, y=0.5)
    
    fig = go.Figure()
    
    # Förbered data för historiska kurvor
    if not historical_ref.empty:
        df_with_hist = df.copy()
        df_with_hist['month'] = df_with_hist['valid_time'].dt.month
        df_with_hist['day'] = df_with_hist['valid_time'].dt.day
        df_with_hist['hour'] = df_with_hist['valid_time'].dt.hour
        
        df_merged = df_with_hist.merge(
            historical_ref[['month', 'day', 'hour', 'temp_min_10y', 'temp_max_10y', 'temp_mean_10y']], 
            on=['month', 'day', 'hour'], 
            how='left'
        )
        
        fig.add_trace(go.Scatter(
            x=df_merged['valid_time'],
            y=df_merged['temp_max_10y'],
            mode='lines',
            name='10-års maximum',
            line=dict(color='rgba(255,100,100,0.6)', width=1, dash='dot'),
            hovertemplate='Max 10 år: %{y:.1f}°C<extra></extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=df_merged['valid_time'],
            y=df_merged['temp_min_10y'],
            mode='lines',
            name='10-års minimum',
            line=dict(color='rgba(100,100,255,0.6)', width=1, dash='dot'),
            fill='tonexty',
            fillcolor='rgba(200,200,200,0.2)',
            hovertemplate='Min 10 år: %{y:.1f}°C<extra></extra>'
        ))
        
        fig.add_trace(go.Scatter(
            x=df_merged['valid_time'],
            y=df_merged['temp_mean_10y'],
            mode='lines',
            name='10-års medel',
            line=dict(color='rgba(100,100,100,0.8)', width=1, dash='dash'),
            hovertemplate='Medel 10 år: %{y:.1f}°C<extra></extra>'
        ))
    
    # Lägg till aktuell temperaturkurva
    fig.add_trace(go.Scatter(
        x=df['valid_time'], 
        y=df['temperature_2m'],
        mode='lines+markers',
        name='Prognos temperatur',
        line=dict(color='#1f77b4', width=3),
        marker=dict(size=6),
        hovertemplate='Temperatur: %{y:.1f}°C<br>Tid: %{x}<extra></extra>'
    ))
    
    # Frostlinjer
    fig.add_hline(y=0, line_dash="solid", line_color="red", line_width=2,
                  annotation_text="Fryspunkt (0°C)")
    fig.add_hline(y=3, line_dash="dash", line_color="orange", 
                  annotation_text="Frost-risk (3°C)")
    
    fig.update_layout(
        title="Temperaturprognos med historiska referenser (10 år)",
        xaxis_title="Tid",
        yaxis_title="Temperatur (°C)",
        hovermode='x unified',
        height=500,
        legend=dict(x=0.02, y=0.98),
        xaxis=dict(
            tickmode='linear',
            dtick=6*60*60*1000,
            tickformat='%d/%m %H:%M'
        )
    )
    
    return fig

def safe_count_warnings_period(frost_df: pd.DataFrame, hours: int = 24) -> int:
    """FIXAD: Räkna frostvarningar för kommande X timmar (inte bara idag)"""
    if frost_df.empty or 'valid_time' not in frost_df.columns:
        return 0
    
    try:
        if frost_df['valid_time'].dtype != 'datetime64[ns]':
            frost_df = frost_df.copy()
            frost_df['valid_time'] = safe_datetime_convert(frost_df['valid_time'])
        
        now = datetime.now()
        future = now + timedelta(hours=hours)
        
        warnings_in_period = frost_df[
            (frost_df['valid_time'] >= now) & 
            (frost_df['valid_time'] <= future)
        ]
        return len(warnings_in_period)
    except:
        return 0

def safe_filter_next_24h(frost_df: pd.DataFrame) -> pd.DataFrame:
    """Säkert filtrera frostvarningar för närmaste 24h"""
    if frost_df.empty or 'valid_time' not in frost_df.columns:
        return pd.DataFrame()
    
    try:
        df_copy = frost_df.copy()
        if df_copy['valid_time'].dtype != 'datetime64[ns]':
            df_copy['valid_time'] = safe_datetime_convert(df_copy['valid_time'])
        
        now = datetime.now()
        future_24h = now + timedelta(hours=24)
        
        filtered = df_copy[
            (df_copy['valid_time'] > now) & 
            (df_copy['valid_time'] <= future_24h)
        ]
        return filtered
    except:
        return pd.DataFrame()

def create_location_map(cfg: Dict[str, Any]) -> folium.Map:
    """Skapa karta med väderstation-plats"""
    lat = cfg.get("api", {}).get("params", {}).get("latitude", 59.06709)
    lon = cfg.get("api", {}).get("params", {}).get("longitude", 15.75283)
    location_name = cfg.get("email", {}).get("notifications", {}).get("location_name", "Väderstation")
    
    m = folium.Map(location=[lat, lon], zoom_start=10)
    
    folium.Marker(
        [lat, lon],
        popup=f"🌡️ {location_name}",
        tooltip="Klicka för mer info",
        icon=folium.Icon(color='blue', icon='thermometer-half', prefix='fa')
    ).add_to(m)
    
    return m

def main():
    """Huvudfunktion för förbättrad dashboard"""
    
    st.title("❄️ Frostvakt")
    st.markdown("*Realtidsövervakning med 10 års historiska jämförelser*")
    
    # Sidebar
    st.sidebar.header("⚙️ Inställningar")
    days_ahead = st.sidebar.selectbox(
        "Visa prognos för kommande:",
        [3, 5, 7, 10, 14],
        index=2,
        format_func=lambda x: f"{x} dag{'ar' if x > 1 else ''}"
    )
    
    show_historical = st.sidebar.checkbox("Visa historiska referenser", value=True)
    
    # Ladda data
    with st.spinner("Laddar väderdata och historiska referenser..."):
        weather_df = load_weather_data(days_ahead)
        frost_df = load_frost_warnings(days_ahead)
        historical_ref = load_historical_reference() if show_historical else pd.DataFrame()
        cfg = load_config()
    
    if weather_df.empty:
        st.warning("⚠️ Ingen väderdata hittades. Kontrollera att systemet har kört och samlat data.")
        return
    
    # Huvudstatistik
    col1, col2, col3, col4 = st.columns(4)
    
    latest = weather_df.iloc[0] if not weather_df.empty else None
    
    with col1:
        if latest is not None:
            current_temp = latest['temperature_2m']
            st.metric("🌡️ Aktuell temperatur", f"{current_temp:.1f}°C")
            
            # Visa historisk kontext om tillgänglig
            if not historical_ref.empty:
                context = get_historical_context(current_temp, latest['valid_time'], historical_ref)
                if context["available"]:
                    st.markdown(f"""
                    <div class="historical-context">
                        <small>{context['classification']}<br>
                        10-års spann: {context['historical_min']:.1f}°C - {context['historical_max']:.1f}°C</small>
                    </div>
                    """, unsafe_allow_html=True)
    
    with col2:
        if latest is not None:
            st.metric("💨 Vindhastighet", f"{latest['wind_speed_10m']:.1f} m/s")
    
    with col3:
        # FIXAD: Visa varningar för närmaste 24h istället för "idag"
        frost_count_24h = safe_count_warnings_period(frost_df, hours=24)
        st.metric("❄️ Frostvarningar 24h", frost_count_24h)
    
    # Frost-status
    st.subheader("🚨 Aktuell frost-status")
    
    next_24h_warnings = safe_filter_next_24h(frost_df)
    
    if not next_24h_warnings.empty:
        highest_risk = next_24h_warnings['frost_risk_numeric'].max()
        if highest_risk >= 3:
            risk_text = "HÖG FROSTRISK"
            risk_color = "🚨"
        elif highest_risk >= 2:
            risk_text = "MEDEL FROSTRISK"
            risk_color = "⚠️"
        else:
            risk_text = "LÅG FROSTRISK"
            risk_color = "❄️"
        
        next_time = next_24h_warnings.iloc[0]['valid_time']
        if pd.api.types.is_datetime64_any_dtype(next_time):
            next_warning_time = next_time.strftime('%Y-%m-%d %H:%M')
        else:
            next_warning_time = str(next_time)
        
        st.markdown(f"""
        <div class="frost-warning">
            <h3>{risk_color} {risk_text} - Närmaste 24h</h3>
            <p>🕐 {len(next_24h_warnings)} frosttimmar prognostiserade</p>
            <p>📅 Närmaste varning: {next_warning_time}</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="frost-ok">
            <h3>✅ INGEN FROSTRISK - Närmaste 24h</h3>
            <p>Inga frostvarningar prognostiserade för de kommande 24 timmarna.</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Grafer i tabbar
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🌡️ Temperatur Enhanced", "💨 Vind", "❄️ Frostrisk", "📍 Plats", "📊 Statistik"])
    
    with tab1:
        if show_historical and not historical_ref.empty:
            st.plotly_chart(create_enhanced_temperature_chart(weather_df, historical_ref), use_container_width=True)
        else:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=weather_df['valid_time'], 
                y=weather_df['temperature_2m'],
                mode='lines+markers',
                name='Temperatur',
                line=dict(color='#1f77b4', width=2),
                marker=dict(size=4)
            ))
            
            fig.add_hline(y=0, line_dash="dash", line_color="red", 
                          annotation_text="Fryspunkt (0°C)")
            fig.add_hline(y=3, line_dash="dot", line_color="orange", 
                          annotation_text="Frost-risk (3°C)")
            
            fig.update_layout(
                title="Temperaturprognos",
                xaxis_title="Tid",
                yaxis_title="Temperatur (°C)",
                hovermode='x unified',
                height=400,
                xaxis=dict(
                    tickmode='linear',
                    dtick=6*60*60*1000,
                    tickformat='%d/%m %H:%M'
                )
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=weather_df['valid_time'], 
            y=weather_df['wind_speed_10m'],
            fill='tonexty',
            mode='lines',
            name='Vindhastighet',
            line=dict(color='#2ca02c', width=2)
        ))
        
        fig.add_hline(y=2, line_dash="dash", line_color="orange", 
                      annotation_text="Kritisk vindgräns (2 m/s)")
        
        fig.update_layout(
            title="Vindhastighetsprognos",
            xaxis_title="Tid",
            yaxis_title="Vindhastighet (m/s)",
            hovermode='x unified',
            height=400,
            xaxis=dict(
                tickmode='linear',
                dtick=6*60*60*1000,
                tickformat='%d/%m %H:%M'
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        if not frost_df.empty:
            st.subheader("📋 Detaljerade frostvarningar")
            if 'valid_time' in frost_df.columns:
                display_df = frost_df[['valid_time', 'temperature_2m', 'wind_speed_10m', 'frost_risk_level', 'dataset']].copy()
                display_df.columns = ['Tid', 'Temperatur (°C)', 'Vind (m/s)', 'Risknivå', 'Typ']
                st.dataframe(display_df, use_container_width=True)
        else:
            st.info("Inga frostvarningar att visa för vald tidsperiod.")
    
    with tab4:
        if cfg:
            location_name = cfg.get("email", {}).get("notifications", {}).get("location_name", "Väderstation")
            st.subheader(f"📍 Plats: {location_name}")
            map_obj = create_location_map(cfg)
            st_folium(map_obj, width=700, height=500)
    
    with tab5:
        st.subheader("📊 Datastatistik")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Prognosdata:**")
            st.write(f"• Totala prognoser: {len(weather_df)}")
            if not weather_df.empty and 'valid_time' in weather_df.columns:
                try:
                    min_time = weather_df['valid_time'].min()
                    max_time = weather_df['valid_time'].max()
                    if pd.api.types.is_datetime64_any_dtype(min_time):
                        st.write(f"• Från: {min_time.strftime('%Y-%m-%d %H:%M')}")
                        st.write(f"• Till: {max_time.strftime('%Y-%m-%d %H:%M')}")
                except:
                    pass
                    
                if 'temperature_2m' in weather_df.columns:
                    st.write(f"• Min temperatur: {weather_df['temperature_2m'].min():.1f}°C")
                    st.write(f"• Max temperatur: {weather_df['temperature_2m'].max():.1f}°C")
        
        with col2:
            st.markdown("**Frostvarningar:**")
            st.write(f"• Totala varningar: {len(frost_df)}")
            if not frost_df.empty and 'frost_risk_level' in frost_df.columns:
                risk_counts = frost_df['frost_risk_level'].value_counts()
                for risk, count in risk_counts.items():
                    st.write(f"• {risk.capitalize()} risk: {count}")
            
            if show_historical and not historical_ref.empty:
                st.markdown("**Historiska referenser:**")
                st.write(f"• Referenspunkter: {len(historical_ref):,}")
                st.write(f"• Tidsperiod: 10 år (2015-2024)")
                st.write(f"• Månader: September-Oktober")
    
    # Footer
    st.markdown("---")
    if latest is not None and 'valid_time' in weather_df.columns:
        try:
            last_update_time = weather_df.iloc[0]['valid_time']
            if pd.api.types.is_datetime64_any_dtype(last_update_time):
                last_update = last_update_time.strftime('%Y-%m-%d %H:%M')
                st.caption(f"📅 Prognos från: {last_update} | 🔄 Nästa uppdatering inom 4 timmar")
        except:
            pass
    
    if show_historical and not historical_ref.empty:
        st.caption("📈 Historiska jämförelser baserade på 10 års väderdata från Open-Meteo Archive")
    
    if st.button("🔄 Uppdatera data"):
        st.cache_data.clear()
        st.rerun()

if __name__ == "__main__":
    main()