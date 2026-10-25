import { Tabs } from 'expo-router';
import { Route, Building2, LocateFixed, UserRound } from 'lucide-react-native';
import { useTheme } from '@/theme/ThemeContext';

export default function TabsLayout() {
  const { palette } = useTheme();
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: palette.accent,
        tabBarInactiveTintColor: palette.text3,
        tabBarStyle: {
          backgroundColor: palette.surface,
          borderTopColor: palette.border,
          height: 62,
          paddingBottom: 8,
          paddingTop: 6,
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
      }}
    >
      <Tabs.Screen name="index"
        options={{ title: '경로', tabBarIcon: ({ color, size }) => <Route color={color} size={size} /> }} />
      <Tabs.Screen name="facilities"
        options={{ title: '시설', tabBarIcon: ({ color, size }) => <Building2 color={color} size={size} /> }} />
      <Tabs.Screen name="tracking"
        options={{ title: '트래킹', tabBarIcon: ({ color, size }) => <LocateFixed color={color} size={size} /> }} />
      <Tabs.Screen name="profile"
        options={{ title: '프로필', tabBarIcon: ({ color, size }) => <UserRound color={color} size={size} /> }} />
    </Tabs>
  );
}
