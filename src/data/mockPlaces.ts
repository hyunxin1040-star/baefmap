import { Place } from '@/types';
// Curated landmark reference coordinates, not verified accessible entrances.
const make = (id:string,name:string,latitude:number,longitude:number,category:Place['category']='sight'):Place => ({id,name,category,keywords:name,accLevel:'na',coord:{latitude,longitude},demoXY:{x:0,y:0},access:{entry:'na',toilet:'na',elevator:'na',slope:'미확인',width:'미확인'},congestion:[],bestVisit:'시설 접근성과 출입구는 현장 확인이 필요합니다.'});
export const ORIGIN=make('seoulstation','서울역',37.5547,126.9707,'transport');
export const PLACES:Place[]=[["gyeongbok","경복궁",37.5762,126.9769],["bukchon","북촌한옥마을",37.5826,126.9831],["cheonggye","청계광장",37.5691,126.9777],["gwanghwamun","광화문광장",37.572,126.9769],["insadong","인사동길",37.574,126.985],["gwcafe","세종문화회관",37.5722,126.9754],["myeongfood","명동성당",37.5633,126.9873],["euljironopo","서울시립미술관",37.5641,126.9738],["euljirohotel","덕수궁 대한문",37.5659,126.9751],["cityhotel","서울광장",37.5655,126.978],["jongrohotel","종묘",37.5711,126.993]].map(p=>make(p[0] as string,p[1] as string,p[2] as number,p[3] as number));
export const PLACE_MAP:Record<string,Place>=Object.fromEntries([ORIGIN,...PLACES].map(p=>[p.id,p]));
export const DEMO_ROUTES=[];
