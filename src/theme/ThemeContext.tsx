import React, { createContext, useContext, useMemo, useState } from 'react';
import { useColorScheme } from 'react-native';
import { light, dark, Palette } from './tokens';

type ThemeCtx = { palette: Palette; isDark: boolean; toggle: () => void };
const Ctx = createContext<ThemeCtx>({ palette: light, isDark: false, toggle: () => {} });

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const system = useColorScheme();
  const [override, setOverride] = useState<boolean | null>(null);
  const isDark = override ?? system === 'dark';
  const value = useMemo<ThemeCtx>(
    () => ({ palette: isDark ? dark : light, isDark, toggle: () => setOverride((v) => !(v ?? isDark)) }),
    [isDark],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
export const useTheme = () => useContext(Ctx);
