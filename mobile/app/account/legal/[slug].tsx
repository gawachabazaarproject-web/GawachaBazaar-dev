import React from "react";
import { ScrollView, StyleSheet, View } from "react-native";
import { Stack, useLocalSearchParams } from "expo-router";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { getPolicy } from "@/features/legal/content";
import { colors, spacing } from "@/theme";

export default function PolicyScreen() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const policy = getPolicy(slug);

  return (
    <Screen edges={["bottom"]}>
      <Stack.Screen options={{ headerShown: true, title: policy?.menuLabel ?? "Policy" }} />
      <ScrollView contentContainerStyle={styles.content}>
        {!policy ? (
          <Text variant="body" color={colors.textSecondary}>
            This page could not be found.
          </Text>
        ) : (
          <>
            <Text variant="displayM" color={colors.primary} style={styles.title}>
              {policy.title}
            </Text>
            {policy.intro ? (
              <Text variant="body" color={colors.textSecondary} style={styles.para}>
                {policy.intro}
              </Text>
            ) : null}
            {policy.sections.map((section, i) => (
              <View key={i} style={styles.section}>
                {section.heading ? (
                  <Text variant="bodyMedium" style={styles.heading}>
                    {section.heading}
                  </Text>
                ) : null}
                {section.paragraphs?.map((p, j) => (
                  <Text key={`p${j}`} variant="body" color={colors.textSecondary} style={styles.para}>
                    {p}
                  </Text>
                ))}
                {section.bullets?.map((b, j) => (
                  <View key={`b${j}`} style={styles.bulletRow}>
                    <Text variant="body" color={colors.textSecondary} style={styles.dot}>
                      •
                    </Text>
                    <Text variant="body" color={colors.textSecondary} style={styles.bulletText}>
                      {b}
                    </Text>
                  </View>
                ))}
              </View>
            ))}
            <Text variant="caption" color={colors.textMuted} style={styles.footer}>
              © 2026 GAWACHA BAAZAAR. All Rights Reserved.
            </Text>
          </>
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.xl, paddingBottom: spacing.xl * 2 },
  title: { marginBottom: spacing.md },
  section: { marginTop: spacing.lg },
  heading: { marginBottom: spacing.sm },
  para: { marginBottom: spacing.sm },
  bulletRow: { flexDirection: "row", marginBottom: spacing.xs },
  dot: { width: 16 },
  bulletText: { flex: 1 },
  footer: { marginTop: spacing.xl },
});
