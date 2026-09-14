import { useEffect, useMemo, useReducer, useState } from "react";
import { ActivityIndicator, Pressable, SafeAreaView, StyleSheet, Text, TextInput, View } from "react-native";
import { StatusBar } from "expo-status-bar";

import { loadPublicConfig, resolveApiOrigin } from "./src/api/public-config";
import { createAuthClient } from "./src/api/auth-client";
import { authReducer, initialAuthState } from "./src/auth/auth-state";
import { secureTokenStore } from "./src/auth/secure-token-store";
import { initialLaunchState, launchReducer } from "./src/screens/launch-state";

const colors = {
  ink: "#17140f",
  paper: "#f4efe5",
  surface: "#fffaf0",
  gold: "#9a6b21",
  muted: "#6e6558",
  line: "#d8cbb7",
};

function AuthPanel({ brandName }: { brandName: string }) {
  const origin = resolveApiOrigin(process.env.EXPO_PUBLIC_API_URL);
  const client = useMemo(() => createAuthClient(origin, secureTokenStore), [origin]);
  const [state, dispatch] = useReducer(authReducer, initialAuthState);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    let active = true;
    client.restore()
      .then((user) => active && dispatch({ type: "restored", user }))
      .catch(() => active && dispatch({ type: "failed", message: "Sitzung konnte nicht geprüft werden." }));
    return () => { active = false; };
  }, [client]);

  const signIn = async () => {
    dispatch({ type: "signingIn" });
    try {
      const user = await client.login(email.trim(), password);
      setPassword("");
      dispatch({ type: "signedIn", user });
    } catch (error) {
      dispatch({
        type: "failed",
        message: error instanceof Error && error.message === "INVALID_CREDENTIALS"
          ? "E-Mail oder Passwort falsch."
          : "Anmeldung derzeit nicht möglich.",
      });
    }
  };

  const signOut = async () => {
    try { await client.logout(); } catch { /* local credential is cleared in finally */ }
    dispatch({ type: "signedOut" });
  };

  if (state.status === "restoring") return <><ActivityIndicator color={colors.gold} /><Text style={styles.body}>Sitzung wird geprüft …</Text></>;
  if (state.status === "signedIn") return <>
    <Text style={styles.marker}>ANGEMELDET</Text>
    <Text style={styles.cardTitle}>Willkommen bei {brandName}</Text>
    <Text style={styles.body}>{state.user.email}</Text>
    <Pressable accessibilityRole="button" onPress={signOut} style={styles.secondaryButton}><Text style={styles.secondaryButtonLabel}>Abmelden</Text></Pressable>
  </>;

  return <>
    <Text style={styles.marker}>SICHERE ANMELDUNG</Text>
    <Text style={styles.cardTitle}>{brandName}</Text>
    <TextInput accessibilityLabel="E-Mail" autoCapitalize="none" autoComplete="email" keyboardType="email-address" onChangeText={setEmail} placeholder="E-Mail" style={styles.input} value={email} />
    <TextInput accessibilityLabel="Passwort" autoComplete="current-password" onChangeText={setPassword} onSubmitEditing={signIn} placeholder="Passwort" secureTextEntry style={styles.input} value={password} />
    {state.status === "signedOut" && state.error && <Text accessibilityRole="alert" style={styles.error}>{state.error}</Text>}
    <Pressable accessibilityRole="button" disabled={state.status === "signingIn" || !email.trim() || !password} onPress={signIn} style={styles.button}>
      <Text style={styles.buttonLabel}>{state.status === "signingIn" ? "Anmeldung …" : "Anmelden"}</Text>
    </Pressable>
  </>;
}

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
          <AuthPanel brandName={state.config.brandName} />
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
  secondaryButton: { borderColor: colors.ink, borderWidth: 1, borderRadius: 999, paddingHorizontal: 22, paddingVertical: 13, marginTop: 22 },
  secondaryButtonLabel: { color: colors.ink, fontSize: 15, fontWeight: "700" },
  input: { alignSelf: "stretch", borderColor: colors.line, borderWidth: 1, borderRadius: 12, color: colors.ink, fontSize: 16, marginTop: 12, paddingHorizontal: 14, paddingVertical: 12 },
  error: { color: "#9d2d20", fontSize: 14, marginTop: 10 },
});
