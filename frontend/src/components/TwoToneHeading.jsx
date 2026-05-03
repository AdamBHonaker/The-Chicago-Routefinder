import { useTranslation } from "react-i18next";

/**
 * D2 two-tone headline pattern: italic-serif opener + roman-serif continuation,
 * optional caps kicker above and a 2px ink rule below.
 *
 * Splits the resolved translation on the first whitespace by default — pass
 * `italicWords` to italicize more leading words. CJK locales without spaces
 * resolve to a single token and italicize the whole headline, which is the
 * intended graceful fallback.
 */
export default function TwoToneHeading({
  capsKey,
  headingKey,
  italicWords = 1,
  ruleAfter = true,
  className = "",
  id,
}) {
  const { t } = useTranslation();
  const heading = t(headingKey);
  const tokens = heading.split(/\s+/).filter(Boolean);
  const italicTokens = tokens.slice(0, italicWords);
  const restTokens = tokens.slice(italicWords);
  const italic = italicTokens.join(" ");
  const rest = restTokens.join(" ");

  return (
    <div className={`two-tone-heading ${className}`.trim()}>
      {capsKey && <div className="caps">{t(capsKey)}</div>}
      <h2 className="headline" id={id}>
        {italic && <span className="headline__italic">{italic}</span>}
        {rest && <> {rest}</>}
      </h2>
      {ruleAfter && <div className="rule-thick" aria-hidden="true" />}
    </div>
  );
}
