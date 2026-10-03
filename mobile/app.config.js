/**
 * Extends app.json with the Firebase native config files.
 *
 * google-services.json (Android) / GoogleService-Info.plist (iOS) come from
 * Firebase Console -> Project settings -> Your apps. They are gitignored and
 * provided per build:
 *   - locally: drop them next to this file, or
 *   - EAS: upload as file secrets and expose their paths as
 *     GOOGLE_SERVICES_JSON / GOOGLE_SERVICE_INFO_PLIST.
 * Only set when the file exists, so a build without Firebase still runs
 * (it shows the "sign-in unavailable" screen instead of crashing).
 */
const fs = require("fs");
const path = require("path");

function existing(envVar, fallback) {
  const file = process.env[envVar] || fallback;
  return fs.existsSync(path.resolve(__dirname, file)) ? file : undefined;
}

module.exports = ({ config }) => {
  const androidFile = existing("GOOGLE_SERVICES_JSON", "./google-services.json");
  const iosFile = existing("GOOGLE_SERVICE_INFO_PLIST", "./GoogleService-Info.plist");
  return {
    ...config,
    android: { ...config.android, ...(androidFile ? { googleServicesFile: androidFile } : {}) },
    ios: { ...config.ios, ...(iosFile ? { googleServicesFile: iosFile } : {}) },
  };
};
