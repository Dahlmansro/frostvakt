

```markdown
# ❄️ Frostvakt - Automatisk Frostövervakning

Ett system för att övervaka väder och upptäcka frostrisk med automatiska notifikationer via email och SMS.  
Systemet är utvecklat som ett proof-of-concept men kan enkelt anpassas för praktisk användning inom trädgård, jordbruk eller forskning.

---

## Vad gör Frostvakt?

Frostvakt hämtar väderdata från Open-Meteo API, analyserar frostrisk baserat på temperatur, vind, molntäcke och luftfuktighet, och skickar automatiska varningar via email och SMS när frost upptäcks. Systemet inkluderar även en interaktiv dashboard för att visualisera data och jämföra med 10 års historiska väderdata.

---

## Dataflöde

```

1. REALTID (var 4\:e timme):
   main.py → Open-Meteo API → weather\_hourly
   ↓
   advanced\_frost\_analyzer.py → frost\_warnings (vid frost-risk)
   ↓
   notification\_manager.py → Email + SMS-notifikationer
   ↓
   main.py → heartbeat (systemstatus)

2. HISTORISK DATA (manuellt):
   historical\_data\_fetcher.py → Open-Meteo Archive API → weather\_historical
   ↓
   historical\_analysis.py → historical\_reference + daily\_temperature\_reference

3. DASHBOARD:
   dashboard\_enhanced.py → Läser alla tabeller → Visar realtid + historiska jämförelser

````

---

## Huvudmål

### 1. **Tidig Varning**
- Upptäck frostrisk 24-48 timmar i förväg
- Ge användare tid att förbereda skyddsåtgärder

### 2. **Algoritmvalidering**
- Algoritmen tar hänsyn till temperatur, vind, molntäcke och luftfuktighet och validerades mot historisk data (F1-score 0.85).

### 3. **Data**
- Realtidsprognoser från Open-Meteo API  
- Jämförelse med YR (Meteorologiska Institutet)  
- 10 års historisk väderdata (2015-2024) för referens  

### 4. **Kommunikation**
- Email-notifikationer med detaljerade prognoser  
- SMS-varningar för akuta situationer (Twilio SMS-integration)  
- Dashboard för visuell övervakning  

### 5. **Visualisering**
- Streamlit dashboard med interaktiva grafer  
- Historiska min/max-kurvor för jämförelse  
- Frostmönster och trendanalys  

---

## Köra systemet

### Förutsättningar
```bash
Python 3.8+
pip (Python package manager)
````

### Installation

1. **Klona repository**

```bash
git clone https://github.com/ditt-användarnamn/frostvakt.git
cd frostvakt
```

2. **Installera dependencies**

```bash
pip install -r requirements.txt
```

3. **Konfigurera system**

```bash
# Kopiera exempel-konfiguration
copy config.yaml.example config.yaml

# Redigera config.yaml med dina inställningar:
# - Koordinater för din plats
# - Email-inställningar (SMTP)
# - SMS-inställningar (Twilio, valfritt)
```

4. **Kör första gången**

```bash
# Hämta historisk data (valfritt)
python scripts/historical_data_fetcher.py
python scripts/historical_analysis.py

# Kör huvudsystem
python src/main.py
```

---

## ⚙️ Konfiguration

All konfiguration hanteras via `config.yaml`.
En komplett mall finns i projektet som `config.yaml.example`. Kopiera den och justera med dina egna värden.

### Minsta som behöver ändras

```yaml
api:
  params:
    latitude: 59.06709     # Din plats
    longitude: 15.75283    # Din plats

email:
  enabled: true
  sender_email: "din-email@gmail.com"
  sender_password: "ditt-app-lösenord"
  recipients:
    - "mottagare@example.com"
```

---

## Användning

### 1. Dashboard

```bash
# Från projektets rotmapp:
streamlit run scripts/dashboard_enhanced.py
```

Öppnar interaktiv dashboard på `http://localhost:8501` med:

* Realtidstemperatur med historiska jämförelser
* Frostrisknivåer och varningar
* Karta med stationsplacering
* Detaljerad statistik

### 2. Kommandorad

```bash
# Kör frost-analys med notifikationer
python src/main.py

# Eller använd Windows batch-skript:
batch\run_frostvakt.cmd

# Debug-läge med extra loggning
set FROSTVAKT_DEBUG=true
python src/main.py

# Hämta och analysera historisk data
python scripts/historical_data_fetcher.py
python scripts/historical_analysis.py
```

### 3. Automatisk körning (Cron/Task Scheduler)

```bash
# Skapa uppgift som kör batch-skriptet:
batch\run_frostvakt.cmd
# Schemalägg: Var 4:e timme
```

---

## 📁 Projektstruktur

```
frostvakt/
├── src/                          
│   ├── main.py                   # Huvudprogram - ETL-pipeline och datainhämtning
│   ├── advanced_frost_analyzer.py # Validerad frostalgoritm (F1=0.852)
│   ├── email_notifier.py         # Email-notifikationssystem med HTML-formatering
│   ├── sms_notifier.py           # SMS via Twilio
│   ├── notification_manager.py   # Central hantering av alla notifikationer
│   ├── yr_api_client.py          # YR API-klient för jämförelsedata
│   └── __init__.py               # Python-paket init
│
├── scripts/                     
│   ├── dashboard_enhanced.py     # Streamlit dashboard med historiska jämförelser
│   ├── api_comparison.py         # Jämför YR vs Open-Meteo prognoser
│   ├── historical_data_fetcher.py # Hämta 10 års historisk data från Open-Meteo
│   ├── historical_analysis.py    # Beräkna min/max-värden och frostmönster
│   ├── frost_model_eval.py       # ML-validering i Google Colab
│   └── tune_frost_algorithm.py   # Utvärdera och jämföra olika algoritmer
│
├── tests/                        # Testsvit - Komplett testtäckning
│   ├── test_frost_analyzer.py    # Algoritm-tester med olika scenarier
│   ├── test_data_pipeline.py     # API-anrop och databas-tester
│   ├── test_email_notifier.py    # Email-funktionalitet och formatering
│   ├── test_notifications.py     # Integration av email och SMS
│   ├── test_frost_scenarios.py   # Realistiska väderscenarier
│   ├── test_integration.py       # Systemintegration end-to-end
│   ├── test_smoke.py             # Snabba rök-tester för deployment
│   ├── test_logic.py             # Logik-validering
│   └── __init__.py               # Test-paket init
│
├── batch/                        
│   ├── run_frostvakt.cmd         # Kör huvudsystem med error handling
│   └── run_dashboard.cmd         # Starta dashboard i webbläsare
│
├── data/                         
│   ├── weather_history_forcast.db # SQLite - prognoser + historik
│   └── .gitkeep                  # Håller mappen i Git
│
├── logs/                         
│   ├── etl.log                   # Systemlogg med alla händelser
│   └── .gitkeep                  # Håller mappen i Git
│
├── docs/                         # Dokumentation
│   └── database_overview.md      # Databas-schema 
│
├── .gitignore                    
├── config.yaml.example           # Exempel-konfiguration för nya användare
├── requirements.txt              # Python dependencies
├── setup.py                      # Package installation setup
├── pytest.ini                    # Pytest-konfiguration
└── README.md                     # Denna fil
```

---

## Validering & Testning

Projektet innehåller en komplett testsuite och verktyg för att utvärdera algoritmer.

### Köra tester

```bash
# Alla tester
pytest tests/ -v

# Specifika tester
pytest tests/test_frost_analyzer.py -v
python tests/test_notifications.py
```

### Algoritmvalidering

```bash
# Jämför olika frostalgoritmer mot historiska data
python scripts/tune_frost_algorithm.py
```

### API-Jämförelse

```bash
# Jämför Open-Meteo mot YR
python scripts/api_comparison.py
```

---

## 📢 Notifikationer

### Email-Exempel

**Rubrik:** `🚨 FROSTVARNING Din trakt - HÖG FROSTRISK`

**Innehåll:**

* 📊 Sammanfattning av högsta risk (24h)
* 🕐 Detaljerade 2-timmarsblock med väderinfo
* 💡 Rekommendationer baserat på risknivå
* ☁️ Molntäcke och dess påverkan

### SMS-Exempel

```
🚨 FROST HÖG RISK imorgon. Temp -2°C, svag vind. 
Täck växter NU! 
```

---

## 📋 Loggning och Felsökning

Frostvakt har två loggnivåer:

**Normal läge (INFO)** – Standard

* Visar viktiga händelser: datainhämtning, frostvarningar, notifikationer
* Rekommenderas för daglig användning

**Debug-läge (DEBUG)** – För felsökning

* Visar all detaljerad information om systemets funktion
* Aktiveras genom att sätta miljövariabel: `FROSTVAKT_DEBUG=true`

### Aktivera Debug-läge

**Windows (PowerShell):**

```powershell
$env:FROSTVAKT_DEBUG="true"
python src/main.py
```

**Windows (CMD):**

```cmd
set FROSTVAKT_DEBUG=true
python src/main.py
```

### Loggfiler

Loggar sparas i `logs/etl.log` och innehåller tidsstämplar, API-anrop, frostanalys och eventuella fel.

---

**Observera:** Prestanda kan variera beroende på geografisk plats och lokala väderförhållanden.

---

## Historisk Analys

Systemet kan kompletteras med historiska data (2015–2024) för att jämföra prognoser med tidigare mönster.

```bash
# Hämta historisk data
python scripts/historical_data_fetcher.py

# Analysera och skapa referenser
python scripts/historical_analysis.py
```

---

## Databastabeller

Se filen `docs/database_overview.md`.

---

## Möjliga förbättringar

* Integrera fler väderkällor (t.ex. SMHI)
* Logga faktiska frostnätter för lokal anpassning
* Mobilapp eller API-integration för externa system
* Långsiktig analys av klimattrender

---

## Licens

Privat användning. Väderdata från Open-Meteo (CC BY 4.0).

---

## Kontakt

**Projektägare:** Camilla Dahlman
**E-post:** [camilla.dahlman@utb.ecutbildning.se](mailto:camilla.dahlman@utb.ecutbildning.se)
**GitHub:** [Dahlmansro](https://github.com/Dahlmansro)

---

<div align="center">

**Skydda dina växter. Få varningar i tid. Använd data.** 🌱❄️

</div>
```
