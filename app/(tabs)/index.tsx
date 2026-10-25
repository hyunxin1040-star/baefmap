import { useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, TextInput, Pressable, ScrollView, StyleSheet, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Search, Plus, WandSparkles, X, Moon, Sun, Type, Bus, Footprints } from 'lucide-react-native';
import { useTheme } from '@/theme/ThemeContext';
import { useA11y, TextScale } from '@/accessibility/AccessibilityContext';
import MapView from '@/components/MapView';
import { PLACES, PLACE_MAP, ORIGIN } from '@/data/mockPlaces';
import { Stop } from '@/types';
import { computeRoutes, ComputedRoute, RoutingOptions } from '@/features/routing';

let seq = 6;

export default function PlannerScreen() {
  const { palette, isDark, toggle } = useTheme();
  const { fs, textScale, setTextScale, profile } = useA11y();
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<'all' | Stop['role'] | string>('all');
  const [activeRoute, setActiveRoute] = useState<'short' | 'safe' | 'balance'>('balance');
  const [stops,setStops] = useState<Stop[]>([
    {sid:1,role:'start',placeId:'gwanghwamun',name:'광화문광장'},
    {sid:2,role:'via',placeId:'gyeongbok',name:'경복궁'},
    {sid:3,role:'end',placeId:'insadong',name:'인사동길'},
  ]);
  const [computedRoute, setComputedRoute] = useState<ComputedRoute | null>(null);
  const [isOptimizing, setIsOptimizing] = useState(false);
  const [optimizeError, setOptimizeError] = useState<string | null>(null);

  const [avoidSteep,setAvoidSteep] = useState(false);
  const requestSeq=useRef(0);
  useEffect(()=>{requestSeq.current++;setComputedRoute(null);setOptimizeError(null);},[stops,activeRoute,profile,avoidSteep]);
  const handleOptimize = async () => {
    const ticket=++requestSeq.current;
    setIsOptimizing(true);
    setOptimizeError(null);
    setComputedRoute(null);
    try {
      const opts: RoutingOptions = {
        routeMode: activeRoute === 'short' ? 'shortest' : activeRoute === 'safe' ? 'wheelchair' : 'balanced',
        excludeStairs: activeRoute !== 'short',
        excludeSteepSlope: avoidSteep,
        preferElevator: false,
        preferIndoor: false,
        profile,
      };
      const results = await computeRoutes(stops, opts);
      if(ticket!==requestSeq.current) return;
      if (results.length > 0) {
        setComputedRoute(results[0]);
      } else {
        setOptimizeError('접근 가능한 경로를 찾지 못했어요.');
      }
    } catch (error) {
      setOptimizeError(error instanceof Error ? error.message : '경로 계산 중 오류가 발생했어요.');
    } finally {
      setIsOptimizing(false);
    }
  };

  const inRoute = (id: string) => stops.some((s) => s.placeId === id);
  const filtered = useMemo(
    () => [ORIGIN,...PLACES].filter((p) =>
      (filter === 'all' || p.category === filter) &&
      (!query || p.name.includes(query) || p.keywords.includes(query))),
    [query, filter],
  );

  const addPlace = (id: string) => {
    if (inRoute(id) || stops.length >= 10) return;
    const p = PLACE_MAP[id];
    setStops((prev) => {
      const endIdx = prev.findIndex((s) => s.role === 'end');
      const next = [...prev];
      next.splice(endIdx < 0 ? next.length : endIdx, 0,
        { sid: seq++, role: 'via', placeId: id, name: p.name });
      return next;
    });
  };
  const delStop = (sid: number) => setStops((p) => p.filter((s) => s.sid !== sid));

  return (
    <SafeAreaView style={[s.safe, { backgroundColor: palette.bg }]} edges={['top']}>
      {/* App bar */}
      <View style={[s.appbar, { backgroundColor: palette.surface, borderBottomColor: palette.border }]}>
        <View style={s.brand}>
          <View style={[s.logo, { backgroundColor: palette.accent }]}>
            <Text style={{ color: '#fff', fontWeight: '800' }}>배</Text>
          </View>
          <View>
            <Text style={{ color: palette.text, fontWeight: '800', fontSize: fs(15) }}>배프맵</Text>
            <Text style={{ color: palette.text3, fontSize: fs(10) }}>종로·중구 MVP</Text>
          </View>
        </View>
        <View style={{ flexDirection: 'row', gap: 6 }}>
          {/* 접근성 프로필: 크게/작게 — 동작함 */}
          <Pressable accessibilityLabel="글자 크기 전환" onPress={() => cycleScale(textScale, setTextScale)} style={[s.iconBtn, { borderColor: palette.border }]}>
            <Type color={palette.text2} size={18} />
          </Pressable>
          <Pressable accessibilityLabel="화면 테마 전환" onPress={toggle} style={[s.iconBtn, { borderColor: palette.border }]}>
            {isDark ? <Sun color={palette.text2} size={18} /> : <Moon color={palette.text2} size={18} />}
          </Pressable>
        </View>
      </View>

      {/* Map (상단 고정) */}
      <View style={s.mapBox}><MapView places={stops.map(st=>PLACE_MAP[st.placeId])} segments={computedRoute?.segmentsCoordinates ?? []} /></View>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 24 }}>
        {/* 검색 */}
        <View style={s.sec}>
          <View style={[s.search, { backgroundColor: palette.surface2, borderColor: palette.border }]}>
            <Search color={palette.text3} size={17} />
            <TextInput
              value={query} onChangeText={setQuery}
              placeholder="관광지, 호텔, 카페 검색" placeholderTextColor={palette.text3}
              style={{ flex: 1, color: palette.text, fontSize: fs(13) }} />
          </View>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 10 }}>
            {[['all', '전체'], ['sight', '관광지'], ['hotel', '호텔'], ['cafe', '카페'], ['food', '식당']].map(([c, l]) => (
              <Pressable key={c} onPress={() => setFilter(c)}
                style={[s.fchip, { backgroundColor: filter === c ? palette.accent : palette.surface2, borderColor: palette.border }]}>
                <Text style={{ color: filter === c ? '#fff' : palette.text2, fontWeight: '600', fontSize: fs(11.5) }}>{l}</Text>
              </Pressable>
            ))}
          </ScrollView>
        </View>

        {/* 추천 장소 리스트 */}
        <Text style={[s.secTitle, { color: palette.text3, fontSize: fs(11) }]}>추천 장소 {filtered.length}</Text>
        <View style={{ paddingHorizontal: 12, gap: 6 }}>
          {filtered.map((p) => {
            const added = inRoute(p.id);
            return (
              <View key={p.id} style={[s.poi, { backgroundColor: palette.surface, borderColor: palette.border }]}>
                <View style={{ flex: 1 }}>
                  <Text style={{ color: palette.text, fontWeight: '700', fontSize: fs(13) }}>{p.name}</Text>
                  <Text style={{ color: p.accLevel === 'ok' ? palette.safe : palette.warn, fontSize: fs(10.5), fontWeight: '600', marginTop: 2 }}>
                    시설 접근성 미확인
                  </Text>
                </View>
                <Pressable accessibilityLabel={p.name + ' 경유지 추가'} disabled={added || isOptimizing || stops.length >= 10} onPress={() => addPlace(p.id)}
                  style={[s.addBtn, { backgroundColor: added ? palette.safeSoft : palette.accentSoft }]}>
                  <Plus color={added ? palette.safe : palette.accentInk} size={17} />
                </Pressable>
              </View>
            );
          })}
        </View>

        <View style={{padding:16,gap:10}}><Text style={{color:palette.text,fontSize:fs(13),fontWeight:'700'}}>경로 모드</Text><View style={{flexDirection:'row',gap:8}}>{([['short','최단'],['safe','접근성 우선'],['balance','균형']] as const).map(([key,label])=><Pressable key={key} disabled={isOptimizing} accessibilityRole="button" accessibilityState={{selected:activeRoute===key}} onPress={()=>setActiveRoute(key)} style={{backgroundColor:activeRoute===key?palette.accent:palette.surface2,padding:12,borderRadius:10}}><Text style={{color:activeRoute===key?'#fff':palette.text}}>{label}</Text></Pressable>)}</View><Pressable disabled={isOptimizing || activeRoute==='short'} accessibilityRole="checkbox" accessibilityState={{checked:avoidSteep}} onPress={()=>setAvoidSteep(v=>!v)}><Text style={{color:palette.text}}> {avoidSteep?'☑':'☐'} 8% 초과 확인된 급경사 제외</Text></Pressable><Text style={{color:palette.text3,fontSize:fs(11)}}>접근성 우선·균형은 계단과 wheelchair=no를 제외합니다. 최단은 계단을 포함할 수 있습니다. 무료 서버는 첫 요청에 1~2분 걸릴 수 있습니다.</Text></View>
        {/* 선택한 동선 */}
        <Text style={[s.secTitle, { color: palette.text3, fontSize: fs(11) }]}>선택한 동선</Text>
        <View style={{ paddingHorizontal: 16, gap: 6 }}>
          {stops.map((st) => (
            <View key={st.sid} style={[s.stop, { backgroundColor: palette.surface, borderColor: palette.border }]}>
              <View style={[s.dot, { backgroundColor: st.role === 'start' ? palette.accent : st.role === 'end' ? palette.danger : 'transparent', borderColor: st.role === 'via' ? palette.text3 : 'transparent' }]} />
              <Text style={{ flex: 1, color: palette.text, fontSize: fs(12.5), fontWeight: '500' }}>{st.name}</Text>
              <Pressable disabled={isOptimizing} accessibilityLabel={st.name + ' 출발지 지정'} onPress={()=>setStops(prev=>prev.map(p=>({...p,role:p.sid===st.sid?'start':p.role==='start'?'via':p.role})))}><Text style={{color:palette.accent,fontSize:fs(11)}}>출발</Text></Pressable>
              <Pressable disabled={isOptimizing} accessibilityLabel={st.name + ' 도착지 지정'} onPress={()=>setStops(prev=>prev.map(p=>({...p,role:p.sid===st.sid?'end':p.role==='end'?'via':p.role})))}><Text style={{color:palette.accent,fontSize:fs(11)}}>도착</Text></Pressable>
              {(
                <Pressable disabled={isOptimizing} accessibilityLabel={st.name + ' 삭제'} onPress={() => delStop(st.sid)}><X color={palette.text3} size={15} /></Pressable>
              )}
            </View>
          ))}
          <Pressable
            style={[s.optimize, { backgroundColor: palette.accentSoft, opacity: isOptimizing ? 0.6 : 1 }]}
            onPress={handleOptimize}
            disabled={isOptimizing || stops.length < 2}
          >
            {isOptimizing
              ? <ActivityIndicator size="small" color={palette.accentInk} />
              : <WandSparkles color={palette.accentInk} size={15} />}
            <Text style={{ color: palette.accentInk, fontWeight: '700', fontSize: fs(12) }}>
              {isOptimizing ? '계산 중… (실제 지도 데이터 조회, 최대 1~2분)' : '실제 보행 경로 계산'}
            </Text>
          </Pressable>

          {optimizeError && (
            <Text style={{ color: palette.danger, fontSize: fs(11.5) }}>{optimizeError}</Text>
          )}

          {computedRoute && (
            <View style={[s.resultBox, { backgroundColor: palette.surface, borderColor: palette.border }]}>
              <Text style={{ color: palette.text, fontWeight: '700', fontSize: fs(13) }}>
                {computedRoute.order.map((st) => st.name).join(' → ')}
              </Text>
              <Text style={{ color: palette.text2, fontSize: fs(11.5), marginTop: 4 }}>
                총 {Math.round(computedRoute.estimatedMinutes)}분 · 도보 {(computedRoute.distanceM / 1000).toFixed(2)}km
                {computedRoute.warningCount > 0 ? ` · 주의구간 ${computedRoute.warningCount}곳` : ''}
              </Text>
              <Text style={{color:palette.text2,fontSize:fs(12),marginTop:8}}>접근성 태그 확인률 {computedRoute.informationRate.toFixed(1)}% · 통행 가능 보장이 아닙니다.</Text>
              {computedRoute.warningDetails.map((w,i)=><Text key={i} style={{color:palette.warn,fontSize:fs(11),marginTop:5}}>· {w}</Text>)}
              <View style={{ gap: 6, marginTop: 8 }}>
                {computedRoute.legs.map((leg, index) => (
                  <View key={index} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    {leg.mode === 'transit'
                      ? <Bus color={palette.accentInk} size={13} />
                      : <Footprints color={palette.text3} size={13} />}
                    <Text style={{ color: palette.text2, fontSize: fs(11) }}>
                      {leg.fromPlace} → {leg.toPlace} · {Math.round(leg.minutes)}분
                      {leg.mode === 'transit' && leg.transit
                        ? ` (대중교통, ${leg.transit.fareWon ?? '-'}원)`
                        : ' (도보)'}
                    </Text>
                  </View>
                ))}
              </View>
            </View>
          )}
        </View>

        {/* 데이터 출처 */}
        <Text style={{padding:16,color:palette.text3,fontSize:fs(11)}}>도로망: © OpenStreetMap contributors · 장소 좌표는 대표 위치입니다. 시설 접근성·입구 연결은 미확인입니다. 현장 상황을 확인하세요.</Text>
      </ScrollView>
    </SafeAreaView>
  );
}

function cycleScale(cur: TextScale, set: (s: TextScale) => void) {
  const order: TextScale[] = ['small', 'normal', 'large'];
  set(order[(order.indexOf(cur) + 1) % order.length]);
}

const s = StyleSheet.create({
  safe: { flex: 1 },
  appbar: { height: 56, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 14, borderBottomWidth: 1 },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 9 },
  logo: { width: 32, height: 32, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  iconBtn: { width: 38, height: 38, borderRadius: 10, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  mapBox: { height: 240 },
  sec: { paddingHorizontal: 16, paddingTop: 14 },
  search: { flexDirection: 'row', alignItems: 'center', gap: 8, borderWidth: 1, borderRadius: 10, paddingHorizontal: 11, height: 42 },
  fchip: { paddingHorizontal: 13, paddingVertical: 7, borderRadius: 16, borderWidth: 1, marginRight: 6 },
  secTitle: { fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.3, paddingHorizontal: 16, marginTop: 18, marginBottom: 8 },
  poi: { flexDirection: 'row', alignItems: 'center', gap: 11, padding: 11, borderRadius: 11, borderWidth: 1 },
  addBtn: { width: 32, height: 32, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  stop: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 11, borderRadius: 9, borderWidth: 1 },
  dot: { width: 11, height: 11, borderRadius: 6, borderWidth: 2.5 },
  optimize: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, padding: 11, borderRadius: 9, marginTop: 4 },
  resultBox: { marginTop: 4, padding: 12, borderRadius: 11, borderWidth: 1 },
});
