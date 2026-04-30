import { useTranslation } from "react-i18next";

const PRECIP_KEYS = {
  rain:          "precip_rain",
  snow:          "precip_snow",
  sleet:         "precip_sleet",
  freezing_rain: "precip_freezing_rain",
};

export default function WeatherStrip({ weather }) {
  const { t } = useTranslation();
  if (!weather) return null;

  const {
    temperature_f,
    feels_like_f,
    short_forecast = "",
    precipitation_type,
    precipitation_intensity,
    wind_gust_mph,
    alerts,
  } = weather;

  const showPrecip = precipitation_type && precipitation_type !== "none";
  const precipBase = showPrecip
    ? (PRECIP_KEYS[precipitation_type] ? t(PRECIP_KEYS[precipitation_type]) : precipitation_type)
    : null;
  const precipLabel = precipBase && precipitation_intensity
    ? `${precipBase} (${precipitation_intensity})`
    : precipBase;

  const showWind = wind_gust_mph != null && wind_gust_mph >= 15;
  const alertText = alerts && alerts.length > 0 ? String(alerts[0]).slice(0, 80) : null;

  const parts = [short_forecast];
  if (showPrecip && precipLabel) parts.push(precipLabel);
  if (showWind) parts.push(t("weather_gusts", { mph: Math.round(wind_gust_mph) }));
  const conditionText = parts.filter(Boolean).join(" · ");

  const hasTemp = Number.isFinite(temperature_f);
  const hasFeelsLike = Number.isFinite(feels_like_f);
  const showFeelsLike = hasFeelsLike && Math.abs(Math.round(feels_like_f) - Math.round(temperature_f)) >= 2;

  return (
    <div className="weather-strip">
      <div className="weather-strip__main">
        {hasTemp && (
          <span className="weather-strip__temp">
            {Math.round(temperature_f)}°
            {showFeelsLike && <span className="weather-strip__feels"> / {t("weather_feels_like", { temp: Math.round(feels_like_f) })}</span>}
          </span>
        )}
        <span className="weather-strip__condition">{conditionText}</span>
        <span className="weather-strip__label">{t("weather_label")}</span>
      </div>
      {alertText && (
        <p className="weather-strip__alert">⚠ {alertText}</p>
      )}
    </div>
  );
}
