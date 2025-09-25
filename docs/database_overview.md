# Frostvakt - Databasöversikt

**Databas:** `data/weather_history_forcast.db`

Denna SQLite-databas innehåller alla väderdata och frost-analyser för Frostvakt-systemet.
Den består av **7 tabeller** som tillsammans utgör ett komplett system för:

- **Realtidsövervakning** (`weather_hourly`, `frost_warnings`)
- **Historiska jämförelser** (`weather_historical`, `historical_reference`)
- **Systemövervakning** (`heartbeat`)
- **Optimerade vyer** (`daily_temperature_reference`)

---

## Tabellstruktur och Syfte

### 1. weather_hourly

**Skapad av:** `main.py` (funktionen `create_database_tables()`)  
**Uppdaterad av:** `main.py` (körs var 4:e timme via cron/scheduler)  
**Syfte:** Lagrar aktuell prognosdata från Open-Meteo API för realtidsövervakning.

#### Struktur:
| Kolumn | Typ | Beskrivning |
|--------|-----|-------------|
| `id` | INTEGER PRIMARY KEY | Primärnyckel (AUTO_INCREMENT) |
| `valid_time` | TEXT NOT NULL | Prognostid |
| `temperature_2m` | REAL | Temperatur vid 2m höjd |
| `relative_humidity_2m` | REAL | Relativ luftfuktighet |
| `precipitation` | REAL | Nederbörd |
| `wind_speed_10m` | REAL | Vindhastighet vid 10m höjd |
| `precipitation_probability` | INTEGER | Nederbördssannolikhet |
| `cloud_cover` | REAL | Molntäcke i procent |
| `dataset` | TEXT NOT NULL | Datakälla - "forecast" |
| `forecast_issue_time` | TEXT | När prognosen skapades |
| `horizon_hours` | REAL | Prognoshorisont i timmar |
| `run_id` | TEXT NOT NULL | Unik körnings-ID |
| `created_at` | TIMESTAMP | Skapad tidpunkt (DEFAULT CURRENT_TIMESTAMP) |

**Unik begränsning:** `(valid_time, dataset)` - Förhindrar dubletter

**Användning:** Realtidsövervakning, aktuella prognoser, kort-term frost-varningar

---

### 2. frost_warnings

**Skapad av:** `main.py` (funktionen `create_database_tables()`)  
**Uppdaterad av:** `main.py` (automatiskt när frost upptäcks av `advanced_frost_analyzer.py`)  
**Syfte:** Lagrar specifika frost-varningar genererade av den avancerade frost-analysalgoritmen.

#### Struktur:
| Kolumn | Typ | Beskrivning |
|--------|-----|-------------|
| `id` | INTEGER PRIMARY KEY | Primärnyckel (AUTO_INCREMENT) |
| `valid_time` | TEXT NOT NULL | När frost-risk förväntas |
| `temperature_2m` | REAL | Prognostiserad temperatur |
| `wind_speed_10m` | REAL | Prognostiserad vindhastighet |
| `cloud_cover` | REAL | Molntäcke vid varning (NY KOLUMN) |
| `frost_risk_level` | TEXT NOT NULL | Risknivå: "låg", "medel", "hög" |
| `frost_risk_numeric` | INTEGER NOT NULL | Numerisk risknivå 1-3 |
| `dataset` | TEXT NOT NULL | Datakälla |
| `forecast_issue_time` | TEXT | Prognostidpunkt |
| `horizon_hours` | REAL | Prognoshorisont |
| `run_id` | TEXT NOT NULL | Körnings-ID |
| `created_at` | TEXT NOT NULL | Skapad tidpunkt |

**Unik begränsning:** `(valid_time, dataset)` - Förhindrar dubletter

**Användning:** Email-notifikationer, SMS-varningar, frost-varningar i dashboard, historisk frost-statistik

---

### 3. weather_historical

**Skapad av:** `historical_data_fetcher.py` (funktionen `create_table()`)  
**Uppdaterad av:** `historical_data_fetcher.py` (körs manuellt för historisk data)  
**Syfte:** Lagrar 10 års historisk väderdata (2015-2024) för september-oktober månader för maskininlärning och historiska jämförelser.

#### Struktur:
| Kolumn | Typ | Beskrivning |
|--------|-----|-------------|
| `id` | INTEGER PRIMARY KEY | Primärnyckel (AUTO_INCREMENT) |
| `valid_time` | TEXT NOT NULL UNIQUE | Observationstid |
| `temperature_2m` | REAL | Historisk temperatur |
| `relative_humidity_2m` | REAL | Historisk luftfuktighet |
| `dew_point_2m` | REAL | Daggpunkt |
| `wind_speed_10m` | REAL | Vindhastighet |
| `cloud_cover` | REAL | Molntäcke i procent |
| `pressure_msl` | REAL | Lufttryck vid havsytan |
| `rain` | REAL | Nederbörd |
| `soil_temperature_0_to_7cm` | REAL | Marktemperatur 0-7cm djup (NY KOLUMN) |
| `year` | INTEGER | År för analys |
| `month` | INTEGER | Månad för analys |
| `day` | INTEGER | Dag för analys |
| `hour` | INTEGER | Timme för analys |
| `day_of_year` | INTEGER | Dag i året 1-365 |
| `created_at` | TEXT | Skapad tidpunkt |

**Användning:** Maskininlärning, historiska jämförelser, beräkning av normala värden, avancerad frost-analys

---

### 4. historical_reference

**Skapad av:** `historical_analysis.py` (funktionen `create_historical_reference_table()`)  
**Uppdaterad av:** `historical_analysis.py` (körs efter historisk datainsamling)  
**Syfte:** Statistik (min/max/medel) för varje dag och timme baserat på 10 års historisk data.

#### Struktur:
| Kolumn | Typ | Beskrivning |
|--------|-----|-------------|
| `month` | BIGINT | Månad |
| `day` | BIGINT | Dag |
| `hour` | BIGINT | Timme |
| `temp_min_10y` | FLOAT | Lägsta temperatur observerad denna tid |
| `temp_max_10y` | FLOAT | Högsta temperatur observerad denna tid |
| `temp_mean_10y` | FLOAT | Medeltemperatur för denna tid |
| `observations_count` | BIGINT | Antal observationer som ligger till grund för statistiken |
| `humidity_min_10y` | FLOAT | Minimum luftfuktighet |
| `humidity_max_10y` | FLOAT | Maximum luftfuktighet |
| `humidity_mean_10y` | FLOAT | Medel luftfuktighet |
| `wind_min_10y` | FLOAT | Minimum vindhastighet |
| `wind_max_10y` | FLOAT | Maximum vindhastighet |
| `wind_mean_10y` | FLOAT | Medel vindhastighet |
| `pressure_min_10y` | FLOAT | Minimum lufttryck |
| `pressure_max_10y` | FLOAT | Maximum lufttryck |
| `pressure_mean_10y` | FLOAT | Medel lufttryck |

**Användning:** Dashboard för att visa "ovanligt varmt/kallt för årstiden", snabb jämförelse av aktuella värden

---

### 5. daily_temperature_reference

**Skapad av:** `historical_analysis.py` (funktionen `create_daily_summary()`)  
**Uppdaterad av:** `historical_analysis.py` (körs efter historisk analys)  
**Syfte:** Förenklad daglig sammanfattning av temperaturstatistik för snabbare dashboard-renderingar.

#### Struktur:
| Kolumn | Typ | Beskrivning |
|--------|-----|-------------|
| `month` | INTEGER | Månad |
| `day` | INTEGER | Dag |
| `daily_temp_min` | REAL | Lägsta temperatur någon gång denna dag |
| `daily_temp_max` | REAL | Högsta temperatur någon gång denna dag |
| `daily_temp_mean` | REAL | Medeltemperatur för hela dagen |
| `hours_available` | INTEGER | Antal timmar med data |

**Användning:** Dagliga temperaturspann i dashboard, snabb översikt av historiska extremer

---

### 6. heartbeat

**Skapad av:** `main.py` (funktionen `create_database_tables()`)  
**Uppdaterad av:** `main.py` (vid varje körning)  
**Syfte:** Systemhälsoövervakning - spårar när systemet senast kördes och om det kördes framgångsrikt.

#### Struktur:
| Kolumn | Typ | Beskrivning |
|--------|-----|-------------|
| `id` | INTEGER PRIMARY KEY | Primärnyckel (AUTO_INCREMENT) |
| `run_id` | TEXT NOT NULL | Körnings-ID |
| `status` | TEXT NOT NULL | Körningsstatus: "ok" eller "fail" |
| `timestamp` | TEXT NOT NULL | När körningen skedde |

**Användning:** Övervaka systemhälsa, upptäcka om automatiska körningar slutat fungera, felsökning

---

### 7. sqlite_sequence

**Skapad av:** SQLite automatiskt  
**Uppdaterad av:** SQLite automatiskt  
**Syfte:** Intern SQLite-tabell som håller reda på AUTO_INCREMENT-sekvenser för alla tabeller.

#### Struktur:
| Kolumn | Typ | Beskrivning |
|--------|-----|-------------|
| `name` | TEXT | Tabellnamn |
| `seq` | INTEGER | Senaste använda AUTO_INCREMENT-värde |

**Användning:** Endast för SQLites interna användning

