# WeatherAPI Usage

The repo now supports WeatherAPI through `autonomous_betting_agent/weatherapi.py` and the Streamlit page `pages/2_Odds_Weather_Decision_Layer.py`.

## Environment key

Set:

```bash
WEATHERAPI_KEY=your_key_here
```

The app also allows the user to paste the WeatherAPI key directly into the page.

## Supported weather columns

The decision layer can read these columns from a CSV:

- `is_outdoor`
- `wind_mph`
- `wind_kph`
- `precip_mm`
- `weather_condition`

WeatherAPI output is converted into compatible fields, including:

- `weather_condition`
- `weather_wind_mph`
- `weather_wind_kph`
- `weather_precip_mm`
- `weather_temp_c`
- `weather_humidity`
- `weather_chance_of_rain`
- `weather_chance_of_snow`

## Current weather logic

Outdoor sports are weather-sensitive by default:

- Baseball
- American football
- Soccer
- Tennis
- AFL / NRL / Rugby

The decision layer flags wind, precipitation, storm, snow, ice, and sleet conditions.

Severe weather keeps the pick in `WATCH` until there is a weather-adjusted independent model probability.
