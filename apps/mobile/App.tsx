import { useEffect, useReducer, useState } from "react";
import { ActivityIndicator, Pressable, SafeAreaView, StyleSheet, Text, View } from "react-native";
import { StatusBar } from "expo-status-bar";

import { loadPublicConfig, resolveApiOrigin } from "./src/api/public-config";
import { initialLaunchState, launchReducer } from "./src/screens/launch-state";

const colors = {
  ink: "#17140f",
  paper: "#f4efe5",
  surface: "#fffaf0",
  gold: "#9a6b21",
  muted: "#6e6558",
  line: "#d8cbb7",
};

export default function App() {
  const [state, dispatch] = useReducer(launchReducer, initialLaunchState);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    let origin: string;
    try {
      origin = resolveApiOrigin(process.env.EXPO_PUBLIC_API_URL);
    } catch (error) {
      dispatch({
        type: "misconfigured",
        message: error instanceof Error ? error.message : "Invalid API configuration",
      });
      return;
    }

    loadPublicConfig(origin)
      .then((config) => active && dispatch({ type: "ready", config }))
      .catch(() => active && dispatch({ type: "unavailable" }));

    return () => {
      active = false;
    };
  }, [attempt]);

  const retry = () => {
    dispatch({ type: "retry" });
    setAttempt((value) => value + 1);
  };

  return (
    <SafeAreaView style={styles.page}>
      <StatusBar style="dark" />
      <View style={styles.hero}>
        <Text style={styles.eyebrow}>PERSONAL & RELATIONSHIP DEVELOPMENT</Text>
        <Text accessibilityRole="header" style={styles.title}>
          AVENYTH
        </Text>
        <Text style={styles.subtitle}>Klarheit beginnt mit einer verlässlichen Verbindung.</Text>
      </View>

      <View style={styles.card} accessibilityLiveRegion="polite">
        {state.status === "loading" && (
          <>
            <ActivityIndicator color={colors.gold} size="large" />
            <Text style={styles.cardTitle}>Dienst wird geprüft</Text>
          </>
        )}

        {state.status === "ready" && (
          <>
            <Text style={styles.marker}>BEREIT</Text>
            <Text style={styles.cardTitle}>{state.config.brandName} ist erreichbar</Text>
            <Text style={styles.body}>Die mobile Grundlage ist verbunden. Die sichere Anmeldung folgt im nächsten Increment.</Text>
          </>
        )}

        {state.status === "misconfigured" && (
          <>
            <Text style={styles.marker}>KONFIGURATION</Text>
            <Text style={styles.cardTitle}>API-Adresse fehlt oder ist unsicher</Text>
            <Text style={styles.body}>{state.message}</Text>
          </>
        )}

        {state.status === "unavailable" && (
          <>
            <Text style={styles.marker}>NICHT ERREICHBAR</Text>
            <Text style={styles.cardTitle}>Verbindung nicht möglich</Text>
            <Text style={styles.body}>Prüfe Netzwerk und Dienststatus und versuche es erneut.</Text>
            <Pressable accessibilityRole="button" onPress={retry} style={styles.button}>
              <Text style={styles.buttonLabel}>Erneut prüfen</Text>
            </Pressable>
          </>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.paper, paddingHorizontal: 24, justifyContent: "center" },
  hero: { marginBottom: 36 },
  eyebrow: { color: colors.gold, fontSize: 11, letterSpacing: 1.8, fontWeight: "700" },
  title: { color: colors.ink, fontSize: 44, letterSpacing: 4, fontWeight: "300", marginTop: 10 },
  subtitle: { color: colors.muted, fontSize: 17, lineHeight: 25, marginTop: 12, maxWidth: 320 },
  card: { backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderRadius: 22, minHeight: 220, padding: 28, justifyContent: "center", alignItems: "flex-start" },
  marker: { color: colors.gold, fontSize: 11, letterSpacing: 1.5, fontWeight: "800" },
  cardTitle: { color: colors.ink, fontSize: 23, lineHeight: 29, fontWeight: "600", marginTop: 14 },
  body: { color: colors.muted, fontSize: 15, lineHeight: 22, marginTop: 10 },
  button: { backgroundColor: colors.ink, borderRadius: 999, paddingHorizontal: 22, paddingVertical: 13, marginTop: 22 },
  buttonLabel: { color: colors.surface, fontSize: 15, fontWeight: "700" },
});

