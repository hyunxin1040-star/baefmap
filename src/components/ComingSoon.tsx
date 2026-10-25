import { View, Text, StyleSheet } from 'react-native';
import { LucideIcon } from 'lucide-react-native';
import { useTheme } from '@/theme/ThemeContext';
import { useA11y } from '@/accessibility/AccessibilityContext';

type Props = { icon: LucideIcon; title: string; desc: string; bullets?: string[] };

export default function ComingSoon({ icon: Icon, title, desc, bullets = [] }: Props) {
  const { palette } = useTheme();
  const { fs } = useA11y();
  return (
    <View style={[styles.wrap, { backgroundColor: palette.bg }]}>
      <View style={[styles.badge, { backgroundColor: palette.accentSoft }]}>
        <Icon color={palette.accentInk} size={28} />
      </View>
      <Text style={[styles.title, { color: palette.text, fontSize: fs(20) }]}>{title}</Text>
      <Text style={[styles.desc, { color: palette.text3, fontSize: fs(13) }]}>{desc}</Text>
      <View style={[styles.tag, { borderColor: palette.border }]}>
        <Text style={{ color: palette.text3, fontSize: fs(11), fontWeight: '700' }}>구현 예정 · 자리 확보됨</Text>
      </View>
      {bullets.map((b) => (
        <Text key={b} style={[styles.bullet, { color: palette.text2, fontSize: fs(12.5) }]}>· {b}</Text>
      ))}
    </View>
  );
}
const styles = StyleSheet.create({
  wrap: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 28, gap: 10 },
  badge: { width: 60, height: 60, borderRadius: 16, alignItems: 'center', justifyContent: 'center', marginBottom: 4 },
  title: { fontWeight: '800' },
  desc: { textAlign: 'center', lineHeight: 20 },
  tag: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 8, borderWidth: 1, marginVertical: 6 },
  bullet: { textAlign: 'center' },
});
