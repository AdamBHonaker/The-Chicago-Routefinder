import { HOUSE_AD_ENABLED, HOUSE_AD_URL, HOUSE_AD_TEXT } from "../constants.js";

// House ad slot (Feature Monetization, Chunk 1). Renders only when
// VITE_HOUSE_AD_ENABLED=true and both URL+TEXT env vars are set. Mounted
// at the bottom of the results column and hidden during an active trip.
// FTC: rel="sponsored" + visible "SPONSORED" kicker. The body copy is
// intentionally not translated — affiliate links are typically en-US.
export default function AdSlot({ kicker }) {
  if (!HOUSE_AD_ENABLED || !HOUSE_AD_URL || !HOUSE_AD_TEXT) return null;
  return (
    <a
      className="ad-slot"
      href={HOUSE_AD_URL}
      target="_blank"
      rel="sponsored noopener noreferrer"
    >
      <span className="ad-slot__kicker">{kicker}</span>
      <span className="ad-slot__body">{HOUSE_AD_TEXT}</span>
    </a>
  );
}
