module.exports = function (api) {
  api.cache(true);
  return {
    presets: ["babel-preset-expo"],
    plugins: [
      // Must remain last in the plugin list - react-native-reanimated's
      // own installation requirement.
      "react-native-reanimated/plugin",
    ],
  };
};
