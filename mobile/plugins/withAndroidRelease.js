/**
 * Android release-build configuration, applied on every `expo prebuild`
 * (android/ is generated and git-ignored - never hand-edit it).
 *
 * 1. Release signing. When the GAWACHA_UPLOAD_* Gradle properties exist -
 *    they belong in ~/.gradle/gradle.properties on the build machine, never
 *    in this repo - release builds are signed with that upload keystore.
 *    Without them a release build still works, signed with the debug key
 *    (fine for local testing, not for sharing or the Play Store).
 *
 * 2. UPI app visibility. Android 11+ hides other installed apps unless the
 *    manifest declares them in <queries>. Razorpay Checkout hands UPI
 *    payments to GPay/PhonePe/Paytm via upi:// links (see
 *    src/components/payment/RazorpayCheckout.tsx), so declare the scheme.
 *
 * 3. Gradle memory. The template's 512m Metaspace cap runs out during the
 *    release build (Kotlin classpath snapshots + lint) and fails it.
 *
 * 4. Compressed native libs (legacy packaging). The APK is shared directly
 *    (WhatsApp/Drive), so compressing the .so files makes the download much
 *    smaller. It also lets the APK run on x86 test emulators via ARM
 *    translation: uncompressed in-APK libs make SoLoader look for lib/x86_64
 *    and crash on launch.
 */
const { withAndroidManifest, withAppBuildGradle, withGradleProperties } = require("expo/config-plugins");

const GRADLE_JVM_ARGS = "-Xmx4096m -XX:MaxMetaspaceSize=1024m";

const RELEASE_SIGNING_CONFIG = `
        release {
            if (project.hasProperty('GAWACHA_UPLOAD_STORE_FILE')) {
                storeFile file(GAWACHA_UPLOAD_STORE_FILE)
                storePassword GAWACHA_UPLOAD_STORE_PASSWORD
                keyAlias GAWACHA_UPLOAD_KEY_ALIAS
                keyPassword GAWACHA_UPLOAD_KEY_PASSWORD
            }
        }`;

function withReleaseSigning(config) {
  return withAppBuildGradle(config, (cfg) => {
    let src = cfg.modResults.contents;
    if (src.includes("GAWACHA_UPLOAD_STORE_FILE")) return cfg;

    const withConfig = src.replace(/signingConfigs \{(\r?\n)/, (_m, nl) => `signingConfigs {${RELEASE_SIGNING_CONFIG}${nl}`);
    const withBuildType = withConfig.replace(
      /(release \{(?:\r?\n\s*\/\/[^\n]*)*\r?\n\s*)signingConfig signingConfigs\.debug/,
      "$1signingConfig project.hasProperty('GAWACHA_UPLOAD_STORE_FILE') ? signingConfigs.release : signingConfigs.debug",
    );
    if (withConfig === src || withBuildType === withConfig) {
      throw new Error("withAndroidRelease: build.gradle template changed - update the signing patch.");
    }
    cfg.modResults.contents = withBuildType;
    return cfg;
  });
}

function withUpiQueries(config) {
  return withAndroidManifest(config, (cfg) => {
    const manifest = cfg.modResults.manifest;
    manifest.queries = manifest.queries ?? [{}];
    const queries = manifest.queries[0];
    queries.intent = queries.intent ?? [];
    const declared = queries.intent.some((intent) =>
      (intent.data ?? []).some((d) => d.$?.["android:scheme"] === "upi"),
    );
    if (!declared) {
      queries.intent.push({
        action: [{ $: { "android:name": "android.intent.action.VIEW" } }],
        data: [{ $: { "android:scheme": "upi" } }],
      });
    }
    return cfg;
  });
}

function setGradleProperty(props, key, value) {
  const existing = props.find((p) => p.type === "property" && p.key === key);
  if (existing) existing.value = value;
  else props.push({ type: "property", key, value });
}

function withBuildProperties(config) {
  return withGradleProperties(config, (cfg) => {
    setGradleProperty(cfg.modResults, "org.gradle.jvmargs", GRADLE_JVM_ARGS);
    setGradleProperty(cfg.modResults, "expo.useLegacyPackaging", "true");
    return cfg;
  });
}

module.exports = (config) => withBuildProperties(withUpiQueries(withReleaseSigning(config)));
