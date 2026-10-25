import { View, Text, Pressable, StyleSheet } from 'react-native';
import { ShieldCheck, Zap, Scale } from 'lucide-react-native';
import { useTheme } from '@/theme/ThemeContext';
import { useA11y } from '@/accessibility/AccessibilityContext';
import { RouteOption } from '@/types';

const ICONS = { short: Zap, safe: ShieldCheck, balance: Scale };

export default function RouteCard({ route, active, onPress }: {
  route: RouteOption; active: boolean; onPress: () => void;
}) {
  const { palette } = useTheme();
  const { fs } = useA11y();
  const Icon = ICONS[route.kind];
  const good = route.danger === 0;
  return (
    <Pressable onPress={onPress}
      style={[styles.card, { backgroundColor: palette.surface, borderColor: active ? palette.accent : palette.border, borderWidth: active ? 2 : 1 }]}>
      <View style={styles.top}>
        <View style={[styles.tag, { backgroundColor: palette.accentSoft }]}>
          <Icon color={palette.accentInk} size={13} />
          <Text style={[styles.tagT, { color: palette.accentInk, fontSize: fs(11) }]}>{route.label}</Text>
        </View>
        <Text style={[styles.time, { color: palette.text, fontSize: fs(19) }]}>
          {route.time}<Text style={{ fontSize: fs(11), color: palette.text3 }}> 분 · {route.dist}</Text>
        </Text>
      </View>
      <View style={[styles.metrics, { backgroundColor: palette.border }]}>
        <Metric label="접근성" value={String(route.acc)} color={good ? palette.safe : palette.warn} bg={palette.surface2} fs={fs} />
        <Metric label="위험구간" value={String(route.danger)} color={good ? palette.safe : palette.warn} bg={palette.surface2} fs={fs} />
        <Metric label="엘리베이터" value={String(route.ev)} color={palette.text} bg={palette.surface2} fs={fs} />
      </View>
    </Pressable>
  );
}
function Metric({ label, value, color, bg, fs }: any) {
  const { palette } = useTheme();
  return (
    <View style={[styles.metric, { backgroundColor: bg }]}>
      <Text style={{ color, fontWeight: '800', fontSize: fs(15) }}>{value}</Text>
      <Text style={{ color: palette.text3, fontSize: fs(9.5), marginTop: 1 }}>{label}</Text>
    </View>
  );
}
const styles = StyleSheet.create({
  card: { borderRadius: 13, padding: 13, gap: 9 },
  top: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  tag: { flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 9, paddingVertical: 4, borderRadius: 7 },
  tagT: { fontWeight: '700' },
  time: { fontWeight: '800' },
  metrics: { flexDirection: 'row', borderRadius: 9, overflow: 'hidden', gap: 1 },
  metric: { flex: 1, paddingVertical: 8, alignItems: 'center' },
});
