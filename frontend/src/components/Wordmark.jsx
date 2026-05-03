import { useTranslation } from "react-i18next";

/**
 * Two-line stacked wordmark — italic Fraunces "The Chicago" over roman
 * Fraunces "Routefinder" with a rust-colored period at the end. Per the D2
 * design system this is the canonical brand mark; the literal text is fixed
 * (it's an editorial lockup, not a label) but `aria-label` localizes for
 * screen readers via the `app_title` key.
 *
 * `size`: "md" (38px, default — home masthead) or "lg" (64px — cover hero,
 * 404, future onboarding/landing screens).
 *
 * Render at the home masthead and anywhere else the brand identity needs to
 * appear visually. The desktop side-rail uses a different mark (vertical
 * caps, no rust period) and stays inline in `SideRail.jsx`.
 */
export default function Wordmark({ size = "md" }) {
  const { t } = useTranslation();
  const className =
    size === "lg" ? "masthead-title masthead-title--lg" : "masthead-title";
  return (
    <h1 className={className} aria-label={t("app_title")}>
      <span className="masthead-title-italic">The Chicago</span>
      <span className="masthead-title-roman">
        Routefinder<span className="masthead-period">.</span>
      </span>
    </h1>
  );
}
