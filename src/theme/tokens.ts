// 디자인 토큰 — HTML 데모의 teal 팔레트를 앱으로 이식
export const light = {
  bg: '#eef1f2', surface: '#ffffff', surface2: '#f4f6f7', surface3: '#eaeeef',
  border: '#e0e6e6', borderStrong: '#cdd6d5',
  text: '#111f1d', text2: '#41514d', text3: '#7c8a86',
  accent: '#0d9488', accent600: '#0b7d73', accentSoft: '#d5f2ee', accentInk: '#0a5a52',
  danger: '#dc2626', dangerSoft: '#fde3e3', warn: '#c2760a', warnSoft: '#fbeccf',
  safe: '#0f9d63', safeSoft: '#d9f4e6', info: '#2563eb', infoSoft: '#dde8fe',
};

export const dark: typeof light = {
  bg: '#0c1413', surface: '#121c1b', surface2: '#172322', surface3: '#1d2b29',
  border: '#25332f', borderStrong: '#33443f',
  text: '#eaf1ef', text2: '#a9b9b4', text3: '#71827d',
  accent: '#2dd4bf', accent600: '#14b8a6', accentSoft: '#123a36', accentInk: '#7defdf',
  danger: '#f87171', dangerSoft: '#3a1c1c', warn: '#f0b755', warnSoft: '#3a2e14',
  safe: '#34d399', safeSoft: '#123626', info: '#60a5fa', infoSoft: '#16273f',
};

export type Palette = typeof light;
export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 };
export const radius = { sm: 8, md: 12, lg: 16, pill: 999 };
