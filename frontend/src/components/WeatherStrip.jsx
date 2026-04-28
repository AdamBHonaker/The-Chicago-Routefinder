import { useTranslation } from "react-i18next";

const PRECIP_LABELS = {
  rain:          "Rain",
  snow:          "Snow",
  sleet:         "Sleet",
  freezing_rain: "Freezing rain",
};

export default function WeatherStrip({ weather }) {
  const { t } = useTranslation();
  if (!weather) return null;

  const {
    temperature_f,
    feels_like_f,
    short_forecast,
    precipitation_type,
    precipitation_intensity,
    wind_gust_mph,
    alerts,
  } = weather;

  const showPrecip = precipitation_type && precipitation_type !== "none";
  const precipLabel = showPrecip
    ? (precipitation_intensity
        ? `${PRECIP_LABELS[precipitation_type] ?? precipitation_type} (${precipitation_intensity})`
        : (PRECIP_LABELS[precipitation_type] ?? precipitation_type))
    : null;

  const showWind = wind_gust_mph != null && wind_gust_mph >= 15;
  const alertText = alerts && alerts.length > 0 ? String(alerts[0]).slice(0, 80) : null;

  return (
    <div className="weather-strip">
      <div className="weather-strip__main">
        {Math.round(temperature_f)}°F
        {" "}({t("weather_feels_like", { temp: Math.round(feels_like_f) })})
        {" · "}{short_forecast}
        {showPrecip && (
          <span className="weather-strip__badge">{precipLabel}</span>
        )}
        {showWind && (
          <span className="weather-strip__wind">
            {" · "}Gusts {Math.round(wind_gust_mph)} mph
          </span>
        )}
      </div>
      {alertText && (
        <div className="weather-strip__alert">
          ⚠ {t("weather_nws_alert", { headline: alertText })}
        </div>
      )}
    </div>
  );
}
