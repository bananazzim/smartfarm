// No DOM/Three dependency. Naive Korean timestamps always mean Asia/Seoul.
export const toNum = value => value == null || typeof value === 'boolean' || String(value).trim()==='' ? NaN : Number(value);
export const sensorKey = sensor => JSON.stringify([sensor.positionType === 'recommended' ? 'recommended' : 'measured', String(sensor.id)]);
export function parseTime(value) {
  if (value instanceof Date) return Number.isFinite(+value) ? +value : NaN;
  if (typeof value === 'number') return Number.isFinite(+new Date(value)) ? value : NaN;
  if (typeof value !== 'string') return NaN;
  const text=value.trim();
  const match=text.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(\.\d{1,6})?)?(Z|[+-]\d{2}:\d{2})?$/);
  if (!match) return NaN;
  const [,year,month,day,hour,minute,second='0',fraction='',offset] = match;
  if (+year<1000 || +month<1 || +month>12 || +day<1 || +day>new Date(Date.UTC(+year,+month,0)).getUTCDate() || +hour>23 || +minute>59 || +second>59) return NaN;
  return Date.parse(`${year}-${month}-${day}T${hour}:${minute}:${second.padStart(2,'0')}${fraction}${offset || '+09:00'}`);
}
export function roofAt(y, config) {
  // Match the prototype's 24 straight film panels, including their chord heights.
  const theta=Math.acos(Math.max(-1,Math.min(1,1-2*y/config.width)));
  const i=Math.min(23,Math.floor(theta/Math.PI*24));
  const a=Math.PI*i/24,b=Math.PI*(i+1)/24;
  const x0=config.width/2*(1-Math.cos(a)),x1=config.width/2*(1-Math.cos(b));
  const fraction=Math.max(0,Math.min(1,(y-x0)/(x1-x0)));
  return config.height*.45+config.height*.55*(Math.sin(a)+(Math.sin(b)-Math.sin(a))*fraction);
}
export function fromRecords(records, options={}) {
  const groups=new Map(), issues=[], times=new Set();
  const result={sensors:[],histories:Object.create(null),moved:[],times:[],issues};
  const hasAt=options.at!=null && options.at!=='';
  const at=hasAt ? parseTime(options.at) : NaN;
  if(hasAt && !Number.isFinite(at)) issues.push({code:'INVALID_TIMESTAMP',message:'선택한 측정 시각이 유효하지 않습니다.'});
  for(const [index,record] of (Array.isArray(records)?records:[]).entries()) {
    const id=String(record?.sensor_id ?? record?.sensorId ?? record?.id ?? '').trim();
    const type=(record?.positionType ?? record?.position_type)==='recommended'?'recommended':'measured';
    if(!id) {issues.push({row:index+1,code:'MISSING_ID',message:'센서 ID가 없습니다.'});continue;}
    const stamp=parseTime(record.timestamp ?? record.time);
    if(!Number.isFinite(stamp)) {issues.push({id,row:index+1,code:'INVALID_TIMESTAMP',message:'유효하지 않은 측정 시각의 기록을 제외했습니다.'});continue;}
    const p=['x','y','z'].map(axis=>toNum(record[axis]));
    if(!p.every(Number.isFinite)) {issues.push({id,row:index+1,code:'BAD_COORD',message:'설치 좌표가 없거나 유효하지 않습니다.'});continue;}
    const key=sensorKey({id,positionType:type});
    if(!groups.has(key)) groups.set(key,{id,type,isRecommended:record.isRecommended===true,stamps:new Map(),conflict:false});
    const group=groups.get(key), previous=group.stamps.get(stamp);
    if(previous && previous.some((v,i)=>Math.abs(v-p[i])>1e-6)) {
      group.conflict=true;
      issues.push({id,timestamp:new Date(stamp).toISOString(),code:'POSITION_CONFLICT',message:`${new Date(stamp).toISOString()}에 서로 다른 좌표가 있어 이 센서를 표시하지 않습니다.`});
    } else group.stamps.set(stamp,p);
  }
  for(const [key,group] of groups) {
    const entries=[...group.stamps].sort((a,b)=>a[0]-b[0]);
    const runs=[];
    for(const [stamp,p] of entries) {
      const last=runs[runs.length-1];
      if(last && last.p.every((v,i)=>Math.abs(v-p[i])<=1e-6)) {last.to=stamp;last.count++;}
      else runs.push({p,from:stamp,to:stamp,count:1});
    }
    result.histories[key]=runs.map(run=>({x:run.p[0],y:run.p[1],z:run.p[2],from:new Date(run.from).toISOString(),to:new Date(run.to).toISOString(),count:run.count}));
    if(group.conflict) continue;
    if(runs.length>1) {result.moved.push(group.id);runs.forEach(run=>times.add(new Date(run.from).toISOString()));}
    if(hasAt && !Number.isFinite(at)) continue;
    if(hasAt && at>entries[entries.length-1][0]) {issues.push({id:group.id,code:'OUTSIDE_RECORD_RANGE',message:'선택 시점까지 확인된 위치 기록이 없어 표시하지 않습니다.'});continue;}
    if(!hasAt && runs.length>1) {issues.push({id:group.id,code:'MOVED_NEEDS_TIME',message:'설치 위치 변경 이력이 있습니다. 측정 시점을 선택하세요.'});continue;}
    const chosen=hasAt ? entries.filter(entry=>entry[0]<=at).pop() : entries[entries.length-1];
    if(!chosen) {issues.push({id:group.id,code:'NOT_INSTALLED_YET',message:'선택한 시점 이전에 위치 기록이 없습니다.'});continue;}
    result.sensors.push({id:group.id,x:chosen[1][0],y:chosen[1][1],z:chosen[1][2],positionType:group.type,isRecommended:group.isRecommended});
  }
  result.times=[...times].sort();
  return result;
}
