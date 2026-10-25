import { View, Text } from 'react-native';
import { Place } from '@/types';
export type MapProps = { places?: Place[]; segments?: number[][][] };
export default function MapView(_: MapProps) { return <View><Text>웹 버전에서 지도를 확인할 수 있습니다.</Text></View>; }
