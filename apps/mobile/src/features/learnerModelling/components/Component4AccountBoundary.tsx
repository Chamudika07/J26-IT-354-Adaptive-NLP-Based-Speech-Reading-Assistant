import { nativeRememberStore, validateLoginSettings, type LoginSettings, type RememberStore } from "../data/rememberedAccount";
import { Pp1ConnectionContext } from "../preview/Pp1Connection";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { AccountError, createAccountSession, type AccountIdentity, type AccountSession, type AuthorizedLearner } from "../data/accountSession";
import type { LiveConnection } from "../data/component4Client";
import { LearnerProgressScreen } from "../screens/LearnerProgressScreen";
import { GuardianSummaryScreen } from "../screens/GuardianSummaryScreen";
import { EducatorAnalyticsScreen } from "../screens/EducatorAnalyticsScreen";
import type { PreviewRole, ReportingPeriodDays } from "../types";
import { palette, radii, spacing } from "../theme";
import { PeriodSelector } from "./PeriodSelector";

const COPY = {
  storage_unavailable: "Saved sign-in is unavailable. Unlock your device and try again.",
  sign_in_required: "Please check your sign-in details or sign in again.",
  invalid_response: "We could not verify the account information.",
  unavailable: "We could not reach the server. Please try again.",
  invalid_address: "Enter a trusted HTTPS server address ending in /api/v1.",
  rate_limited: "Too many attempts. Please wait before trying again.",
};
function Button({ text, onPress }: { text: string; onPress(): void }) {
  return <Pressable accessibilityRole="button" onPress={onPress} style={styles.button}><Text style={styles.buttonText}>{text}</Text></Pressable>;
}
/** Minimal host for existing live screens. Auth credentials remain in memory only. */
export function Component4AccountBoundary({ children, periodDays, onSelectDays, rememberStore, compactHome = false }: { compactHome?: boolean; children: ReactNode; periodDays: ReportingPeriodDays; onSelectDays?: (days: ReportingPeriodDays) => void; rememberStore?: RememberStore }) {
  const [savedLogin] = useState(() => rememberStore ?? nativeRememberStore());
  const [remember, setRemember] = useState(true);
  const remembered = useRef<LoginSettings | undefined>(undefined);
  const [pp1, setPp1] = useState(false);
  const [phase, setPhase] = useState<"demo" | "login" | "busy" | "account">("demo");
  const [address, setAddress] = useState("");
  const [handle, setHandle] = useState("");
  const [password, setPassword] = useState("");
  const [identity, setIdentity] = useState<AccountIdentity>();
  const [learners, setLearners] = useState<AuthorizedLearner[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [selected, setSelected] = useState<AuthorizedLearner>();
  const [role, setRole] = useState<PreviewRole>("learner");
  const [message, setMessage] = useState("");
  const [listLoading, setListLoading] = useState(false);
  const manager = useRef<AccountSession | undefined>(undefined);
  const operation = useRef(0);
  useEffect(() => () => { operation.current++; manager.current?.dispose(); }, []);
  useEffect(() => {
    let active = true;
    const attempt = operation.current;
    void (async () => {
      try {
        const saved = await savedLogin.load();
        if (!active || operation.current !== attempt || !saved) return;
        remembered.current = saved; setAddress(saved.baseUrl); setHandle(saved.handle); setRemember(saved.remember);
        if (!saved.remember || !saved.autoSignIn) return;
        setPhase("busy");
        const client = createAccountSession(saved.baseUrl, expired, fetch, savedLogin.persistence(saved));
        manager.current = client;
        const me = await client.restore();
        if (!active || operation.current !== attempt) return;
        if (!me || me.login_handle.trim().toLowerCase() !== saved.handle.trim().toLowerCase()) throw new AccountError("sign_in_required");
        setIdentity(me); setRole(me.roles.includes("learner") ? "learner" : me.roles.includes("guardian") ? "guardian" : "educator");
        setPhase("account"); await loadLearners(client, attempt);
      } catch {
        if (!active || operation.current !== attempt) return;
        manager.current?.dispose(); manager.current = undefined;
        if (remembered.current) { await savedLogin.signOut(remembered.current).catch(() => undefined); setPhase("login"); }
        setMessage("Please sign in again. Your password has not been saved.");
      }
    })();
    return () => { active = false; };
    // Restore once for this mounted account host; subsequent operations use the generation guard.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [savedLogin]);
  const roles = useMemo(() => identity?.roles.filter((r): r is PreviewRole => r === "learner" || r === "guardian" || r === "educator") ?? [], [identity]);
  const currentManager = manager.current;
  const connection = useMemo<LiveConnection | undefined>(() => selected && currentManager && roles.includes(role) ? {
    baseUrl: currentManager.baseUrl, learnerId: selected.id, role, session: currentManager.session,
  } : undefined, [selected, currentManager, role, roles]);
  const pp1Connection = useMemo(() => currentManager ? { baseUrl: currentManager.baseUrl, session: currentManager.session } : undefined, [currentManager]);
  function clearView() { setPp1(false); setIdentity(undefined); setLearners([]); setCursor(null); setSelected(undefined); setPassword(""); setListLoading(false); }
  function expired() {
    operation.current++; clearView();
    if (remembered.current) void savedLogin.signOut(remembered.current).catch(() => undefined);
    setPhase("login"); setMessage("Your session ended. Please sign in again.");
  }
  async function login() {
    if (phase === "busy") return;
    const attempt = ++operation.current;
    setPassword(""); setMessage(""); clearView(); setPhase("busy");
    manager.current?.dispose();
    let client: AccountSession;
    try {
      const settings = validateLoginSettings({ version: 1, baseUrl: address.trim(), handle: handle.trim(), remember, autoSignIn: remember });
      remembered.current = settings;
      try {
        await savedLogin.saveSettings(settings);
        if (!remember) await savedLogin.signOut(settings);
      } catch { throw new AccountError("storage_unavailable"); }
      client = createAccountSession(settings.baseUrl, expired, fetch, remember ? savedLogin.persistence(settings) : undefined);
      manager.current = client;
      const me = await client.login(handle, password);
      if (attempt !== operation.current) return;
      setIdentity(me);
      const available = me.roles.filter((r): r is PreviewRole => ["learner", "guardian", "educator"].includes(r));
      setRole(available[0] ?? "learner");
      setPhase("account");
      await loadLearners(client, attempt);
    } catch (error) {
      if (attempt !== operation.current) return;
      manager.current?.dispose(); clearView(); setPhase("login");
      setMessage(COPY[error instanceof AccountError ? error.code : "unavailable"]);
    }
  }
  async function loadLearners(client = manager.current, attempt = operation.current, next?: string) {
    if (!client) return;
    if (!next) { setSelected(undefined); setLearners([]); setCursor(null); }
    setListLoading(true); setMessage("");
    try {
      const page = await client.learners(next);
      if (attempt !== operation.current) return;
      if (page.next_cursor && page.next_cursor === next) throw new AccountError("invalid_response");
      setLearners(old => next ? [...old, ...page.items.filter(item => !old.some(v => v.id === item.id))] : page.items);
      setCursor(page.next_cursor);
    } catch (error) {
      if (attempt === operation.current) setMessage(COPY[error instanceof AccountError ? error.code : "unavailable"]);
    } finally { if (attempt === operation.current) setListLoading(false); }
  }
  async function leave(to: "login" | "demo") {
    const attempt = ++operation.current;
    const client = manager.current; manager.current = undefined;
    clearView(); setPhase(to); setMessage("");
    if (remembered.current) {
      try { await savedLogin.signOut(remembered.current); }
      catch { if (attempt === operation.current) setMessage("Local saved sign-out could not be confirmed. Please clear saved login before reusing this device."); }
    }
    if (client) {
      const revoked = await client.logout();
      if (!revoked && attempt === operation.current) setMessage("Signed out on this device. Server sign-out could not be confirmed.");
    }
  }
  if (phase === "demo") return <View style={styles.root}><View style={[styles.controls, compactHome && { paddingVertical: 2, paddingHorizontal: 16 }]}><Pressable accessibilityRole="button" onPress={() => { operation.current++; setPhase("login"); setMessage(""); }} style={[styles.button, compactHome && { alignSelf: "flex-end", backgroundColor: palette.primarySoft, paddingHorizontal: 12 }]}><Text style={[styles.buttonText, compactHome && { color: palette.primaryDark }]}>Sign In for Live Mode</Text></Pressable>{message ? <Text accessibilityRole="alert">{message}</Text> : null}</View>{children}</View>;
  if (phase === "login" || phase === "busy") return <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.form}>
    <Text accessibilityRole="header" style={styles.title}>Sign in to ReadBuddy</Text>
    <Text>Your password is never saved. Remember Me keeps a secure sign-in on this device.</Text>
    {phase === "busy" ? <ActivityIndicator accessibilityLabel="Signing in" /> : <>
      <TextInput accessibilityLabel="HTTPS server address" autoCapitalize="none" autoCorrect={false} placeholder="HTTPS server address ending in /api/v1" value={address} onChangeText={setAddress} style={styles.input} />
      <TextInput accessibilityLabel="Login handle" autoCapitalize="none" autoCorrect={false} value={handle} onChangeText={setHandle} placeholder="Login handle" style={styles.input} />
      <TextInput accessibilityLabel="Password" secureTextEntry autoCapitalize="none" autoCorrect={false} value={password} onChangeText={setPassword} placeholder="Password" style={styles.input} />
      <Pressable accessibilityRole="checkbox" accessibilityLabel="Remember Me" accessibilityState={{ checked: remember }} onPress={() => setRemember(value => !value)} style={styles.button}><Text style={styles.buttonText}>Remember Me: {remember ? "On" : "Off"}</Text></Pressable>
      <Button text="Sign In" onPress={() => void login()} />
    </>}
    {message ? <Text accessibilityRole="alert">{message}</Text> : null}
    <Button text="Return to Demo Mode" onPress={() => void leave("demo")} />
  </ScrollView>;
  if (__DEV__ && pp1 && roles.includes("learner") && pp1Connection) return <View style={styles.root}>
    <Button text="Back to signed-in reports" onPress={() => setPp1(false)} />
    <Pp1ConnectionContext.Provider value={pp1Connection} key={pp1Connection.session.scopeKey}>
      <LearnerProgressScreen periodDays={periodDays} />
    </Pp1ConnectionContext.Provider>
  </View>;
  return <View style={styles.root}>
    <View style={styles.controls}>
      <Text style={styles.title}>Signed-in reading reports</Text>
      {__DEV__ && roles.includes("learner") ? <Button text="Open PP1 Sample Journey" onPress={() => setPp1(true)} /> : null}
      <Text>Sign-in does not replace learning-support consent.</Text>
      {onSelectDays ? <PeriodSelector selectedDays={periodDays} onSelectDays={onSelectDays} /> : null}
      <View style={styles.row}><Button text="Sign Out" onPress={() => void leave("login")} /><Button text="Return to Demo Mode" onPress={() => void leave("demo")} /></View>
      {roles.length ? <View style={styles.row}>{roles.map(r => <Button key={r} text={r === "learner" ? "Learner Reports" : r === "guardian" ? "Guardian Reports" : "Educator Reports"} onPress={() => { setRole(r); setSelected(undefined); }} />)}</View> : <Text>This account has no supported reading-report role.</Text>}
      {selected ? <><Text>{selected.display_name}</Text><Button text="Choose Another Learner" onPress={() => { setSelected(undefined); }} /></> : null}
    </View>
    {!selected ? <ScrollView contentContainerStyle={styles.form}>
      <Text accessibilityRole="header" style={styles.title}>Choose a learner</Text>
      <Text>Only learners available to your account are listed. Each report checks your access again.</Text>
      {listLoading ? <ActivityIndicator accessibilityLabel="Loading authorized learners" /> : null}
      {!listLoading && !message && learners.length === 0 ? <Text>No authorized learners are available to this account.</Text> : null}
      {learners.map(l => <Button key={l.id} text={l.display_name} onPress={() => setSelected(l)} />)}
      {message ? <Text accessibilityRole="alert">{message}</Text> : null}
      {!listLoading ? <><Button text="Refresh Learner List" onPress={() => void loadLearners()} />{cursor ? <Button text="More Learners" onPress={() => void loadLearners(manager.current, operation.current, cursor)} /> : null}</> : null}
    </ScrollView> : connection ? <View style={styles.root} key={`${connection.session.scopeKey}:${selected.id}:${role}`}>
      {role === "learner" ? <LearnerProgressScreen periodDays={periodDays} liveConnection={connection} initialMode="live" /> : role === "guardian" ? <GuardianSummaryScreen periodDays={periodDays} liveConnection={connection} initialMode="live" /> : <EducatorAnalyticsScreen periodDays={periodDays} liveConnection={connection} initialMode="live" />}
    </View> : <Text accessibilityRole="alert">This account cannot open that report.</Text>}
  </View>;
}
const styles = StyleSheet.create({ root: { flex: 1 }, controls: { padding: spacing.sm, gap: spacing.sm, backgroundColor: palette.surface }, form: { padding: spacing.lg, gap: spacing.md }, row: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm }, title: { fontSize: 18, fontWeight: "800", color: palette.ink }, input: { borderWidth: 1, borderColor: palette.outline, borderRadius: radii.small, padding: spacing.md, minHeight: 48, color: palette.ink }, button: { backgroundColor: palette.primary, padding: spacing.sm, minHeight: 44, justifyContent: "center", borderRadius: radii.small }, buttonText: { color: "white", fontSize: 14, fontWeight: "700" } });
