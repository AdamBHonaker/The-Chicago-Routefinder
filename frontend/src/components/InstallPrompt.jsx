import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocalStorage } from "../hooks/useLocalStorage.js";
import { track } from "../analytics.js";

/* InstallPrompt — first-visit "Add to Home Screen" suggestion for mobile users.
 *
 * Shown when ALL of these hold:
 *   - viewport is mobile-sized (matches the app's main mobile breakpoint)
 *   - app is NOT already running as an installed PWA (display-mode: standalone
 *     or iOS legacy navigator.standalone)
 *   - the user has not previously dismissed or installed (localStorage flag)
 *
 * Behavior splits on browser capability:
 *   - Chromium-based browsers fire `beforeinstallprompt`; we intercept it and
 *     render a single "Install" button that calls prompt() directly.
 *   - Everything else (notably iOS Safari, which has no programmatic install
 *     API) gets browser-specific text instructions for the Share-sheet path.
 *
 * Dismissal is sticky — once the user closes the prompt or completes install,
 * we never show it again on that device.
 */

const STORAGE_KEY = "crf:installPromptDismissed";
const MOBILE_QUERY = "(max-width: 800px)";

function detectBrowser(ua) {
  const isIOS = /iphone|ipad|ipod/i.test(ua);
  const isAndroid = /android/i.test(ua);
  if (!isIOS && !isAndroid) return { platform: "other" };

  if (isIOS) {
    if (/crios/i.test(ua))   return { platform: "ios", browser: "chrome-ios" };
    if (/fxios/i.test(ua))   return { platform: "ios", browser: "firefox-ios" };
    if (/edgios/i.test(ua))  return { platform: "ios", browser: "edge-ios" };
    return { platform: "ios", browser: "safari" };
  }

  // Android
  if (/samsungbrowser/i.test(ua))    return { platform: "android", browser: "samsung" };
  if (/firefox|fxios/i.test(ua))     return { platform: "android", browser: "firefox" };
  if (/edga|edg\//i.test(ua))        return { platform: "android", browser: "edge" };
  if (/opr\/|opera/i.test(ua))       return { platform: "android", browser: "opera" };
  return { platform: "android", browser: "chrome" };
}

function isStandalone() {
  if (typeof window === "undefined") return false;
  if (window.matchMedia?.("(display-mode: standalone)").matches) return true;
  if (window.navigator?.standalone === true) return true; // iOS legacy
  return false;
}

export default function InstallPrompt() {
  const { t } = useTranslation();
  const [dismissed, setDismissed] = useLocalStorage(STORAGE_KEY, false);
  const [visible, setVisible] = useState(false);
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [info, setInfo] = useState(null);

  useEffect(() => {
    if (dismissed) return;
    if (typeof window === "undefined") return;
    if (isStandalone()) return;
    if (!window.matchMedia?.(MOBILE_QUERY).matches) return;

    const browserInfo = detectBrowser(window.navigator.userAgent || "");
    if (browserInfo.platform === "other") return;

    setInfo(browserInfo);

    // Capture native install opportunity on Android Chromium so we can offer
    // a one-tap install rather than text instructions.
    const onBip = (e) => {
      e.preventDefault();
      setDeferredPrompt(e);
    };
    window.addEventListener("beforeinstallprompt", onBip);

    // Persist dismissal if the OS-level install completes outside our UI.
    const onInstalled = () => {
      setDismissed(true);
      setVisible(false);
      track("install_completed");
    };
    window.addEventListener("appinstalled", onInstalled);

    // Small delay so the prompt doesn't fight the first paint / map load.
    const id = setTimeout(() => {
      setVisible(true);
      track("install_prompt_shown");
    }, 2500);

    return () => {
      window.removeEventListener("beforeinstallprompt", onBip);
      window.removeEventListener("appinstalled", onInstalled);
      clearTimeout(id);
    };
  }, [dismissed, setDismissed]);

  if (!visible || !info) return null;

  const close = () => {
    setVisible(false);
    setDismissed(true);
    track("install_prompt_dismissed");
  };

  const onNativeInstall = async () => {
    if (!deferredPrompt) return;
    track("install_prompt_accepted");
    deferredPrompt.prompt();
    try {
      await deferredPrompt.userChoice;
    } catch { /* user-choice rejection isn't actionable */ }
    setDeferredPrompt(null);
    setVisible(false);
    setDismissed(true);
  };

  const instructionsKey = (() => {
    if (info.platform === "ios") {
      if (info.browser === "safari") return "install_ios_safari";
      return "install_ios_other"; // Chrome/Firefox/Edge on iOS can't install — direct to Safari
    }
    // Android
    switch (info.browser) {
      case "samsung":  return "install_android_samsung";
      case "firefox":  return "install_android_firefox";
      case "opera":    return "install_android_opera";
      default:         return "install_android_chrome";
    }
  })();

  const canNativeInstall = info.platform === "android" && !!deferredPrompt;

  return (
    <div className="install-prompt" role="dialog" aria-labelledby="install-prompt-title">
      <button
        type="button"
        className="install-prompt__close"
        onClick={close}
        aria-label={t("aria_dismiss")}
      >×</button>
      <span className="install-prompt__kicker">{t("install_kicker")}</span>
      <p id="install-prompt-title" className="install-prompt__title">
        {t("install_title")}
      </p>
      <p className="install-prompt__body">{t(instructionsKey)}</p>
      <div className="install-prompt__actions">
        {canNativeInstall && (
          <button
            type="button"
            className="install-prompt__install-btn"
            onClick={onNativeInstall}
          >
            {t("install_btn")}
          </button>
        )}
        <button
          type="button"
          className="install-prompt__later-btn"
          onClick={close}
        >
          {t("install_later")}
        </button>
      </div>
    </div>
  );
}
