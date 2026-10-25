// 프로필 "크게 / 작게" — 실제 동작하는 폰트 스케일 (배리어프리 핵심)
import React, { createContext, useContext, useMemo, useState } from 'react';

export type TextScale = 'small' | 'normal' | 'large';
const SCALE_MAP: Record<TextScale, number> = { small: 0.9, normal: 1.0, large: 1.25 };

type A11yCtx = {
  profile: 'manual' | 'power' | 'stroller' | 'crutch';
  setProfile: (p: 'manual' | 'power' | 'stroller' | 'crutch') => void;
  textScale: TextScale;
  scaleFactor: number;
  setTextScale: (s: TextScale) => void;
  fs: (size: number) => number; // font-size helper
};
const Ctx = createContext<A11yCtx>({
  profile: 'manual', setProfile: () => {}, textScale: 'normal', scaleFactor: 1, setTextScale: () => {}, fs: (s) => s,
});

export function AccessibilityProvider({ children }: { children: React.ReactNode }) {
  const [textScale, setTextScale] = useState<TextScale>('normal');
  const [profile,setProfile] = useState<A11yCtx['profile']>('manual');
  const scaleFactor = SCALE_MAP[textScale];
  const value = useMemo<A11yCtx>(
    () => ({ profile, setProfile, textScale, scaleFactor, setTextScale, fs: (s) => Math.round(s * scaleFactor) }),
    [profile, textScale, scaleFactor],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
export const useA11y = () => useContext(Ctx);
