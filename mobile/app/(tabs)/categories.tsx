import React from "react";
import { FlatList, Pressable, StyleSheet, View } from "react-native";
import { useRouter } from "expo-router";
import { Feather } from "@expo/vector-icons";
import { Screen } from "@/components/Screen";
import { Text } from "@/components/Text";
import { Skeleton } from "@/components/Skeleton";
import { useCategories } from "@/features/catalog/useCatalog";
import { colors, radius, spacing } from "@/theme";

export default function CategoriesScreen() {
  const router = useRouter();
  const { data: categories, isLoading } = useCategories();

  return (
    <Screen edges={["top"]}>
      <View style={styles.header}>
        <Text variant="h1">Categories</Text>
      </View>
      {isLoading ? (
        <View style={styles.list}>
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} height={64} borderRadius={radius.lg} style={{ marginBottom: spacing.md }} />
          ))}
        </View>
      ) : (
        <FlatList
          data={categories ?? []}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <Pressable style={styles.row} onPress={() => router.push(`/category/${item.id}`)}>
              <View style={styles.iconCircle}>
                <Text variant="h3" color={colors.primary}>
                  {item.name.charAt(0).toUpperCase()}
                </Text>
              </View>
              <Text variant="bodyLarge" style={styles.name}>
                {item.name}
              </Text>
              <Feather name="chevron-right" size={18} color={colors.textMuted} />
            </Pressable>
          )}
        />
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { paddingHorizontal: spacing.base, paddingTop: spacing.md, paddingBottom: spacing.sm },
  list: { padding: spacing.base },
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  iconCircle: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.primaryLight,
    alignItems: "center",
    justifyContent: "center",
    marginRight: spacing.md,
  },
  name: { flex: 1 },
});
