import assert from 'node:assert/strict';
import {fromRecords,parseTime,roofAt,sensorKey} from '../static/js/fps-data.js';
import {pointBlocked,clearSegment,planRoute} from '../static/js/fps-navigation.js';

const record=(id='S01',timestamp='2026-10-31 09:00',x=1,type='measured')=>({sensor_id:id,timestamp,x,y:2,z:1.5,positionType:type});
for(const count of [0,1,2,3,6,10]) {
  const input=Array.from({length:count},(_,i)=>record('S'+i));
  assert.equal(fromRecords(input).sensors.length,count);
}
assert.equal(fromRecords([record(),record(),record('S01','2026-10-31 09:05')]).sensors.length,1);
const conflict=fromRecords([record(),record('S01','2026-10-31 09:00',4),record('S02')]);
assert.deepEqual(conflict.sensors.map(s=>s.id),['S02']);
assert.equal(conflict.issues[0].code,'POSITION_CONFLICT');
const invalid=fromRecords([record('S01','broken'),record('S02')]);
assert.equal(invalid.issues[0].code,'INVALID_TIMESTAMP');
assert.deepEqual(invalid.sensors.map(s=>s.id),['S02']);
assert.equal(parseTime('2026-10-31 09:00'),parseTime('2026-10-31T00:00:00Z'));
assert.equal(parseTime('2026-10-31T09:00:00+09:00'),parseTime('2026-10-31T00:00:00Z'));
for(const value of ['2026-02-30 09:00','2026-13-01 09:00','2026-10-31 25:00','',null,true])assert(Number.isNaN(parseTime(value)));
const moves=[record(),record('S01','2026-10-31 10:00',8)];
assert.equal(fromRecords(moves).sensors.length,0);
assert.equal(fromRecords(moves,{at:'2026-10-31 09:30'}).sensors[0].x,1);
assert.equal(fromRecords(moves,{at:'2026-10-31 10:00'}).sensors[0].x,8);
assert.equal(fromRecords(moves,{at:'2026-10-31 08:00'}).sensors.length,0);
assert.equal(fromRecords(moves,{at:'2026-10-31 11:00'}).sensors.length,0);
assert.equal(fromRecords(moves,{at:'bad'}).sensors.length,0);
assert.equal(fromRecords([record(),record('S01','2026-10-31 09:00',2,'recommended')]).sensors.length,2);
assert.notEqual(sensorKey({id:'same',positionType:'measured'}),sensorKey({id:'same',positionType:'recommended'}));
assert.equal(fromRecords([record('__proto__')]).sensors[0].id,'__proto__');
assert.equal(fromRecords([record('<img src=x onerror=alert(1)>')]).sensors[0].id,'<img src=x onerror=alert(1)>');
assert.equal(fromRecords([{...record(),x:null}]).sensors.length,0);
for(const cfg of [{length:30,width:7,height:4},{length:50,width:9,height:4.5},{length:12,width:6,height:3.5}]) {
  assert.equal(roofAt(cfg.width/2,cfg),cfg.height);
  assert(Math.abs(roofAt(0,cfg)-cfg.height*.45)<1e-10);
}
const world={length:12,width:6,rects:[[2,1,7,2]],npcs:[]};
assert(pointBlocked(0,3,world));assert(pointBlocked(4,1.5,world));
assert(!clearSegment({x:1,z:1.5},{x:9,z:1.5},world));
const route=planRoute({x:1,z:1.5},{x:9,z:1.5},world);
assert(route && route.length>1);
let previous={x:1,z:1.5};for(const point of route){assert(clearSegment(previous,point,world));previous=point;}
assert.equal(pointBlocked(5,3,{...world,npcs:[{x:5,z:3}]}),false);
assert.deepEqual(planRoute({x:1,z:3},{x:5,z:3},{...world,npcs:[{x:5,z:3}]}),[{x:5,z:3}]);
assert(clearSegment({x:1,z:3},{x:9,z:3},{...world,npcs:[{x:5,z:3}]}));
assert(pointBlocked(.1,3,world));
assert(pointBlocked(4,1.5,world));
assert.equal(planRoute({x:1,z:3},{x:10,z:3},{...world,rects:[[5,0,6,6]]}),null);
console.log('PASS: dynamic counts, duplicate/conflict/time/movement/type/XSS data, roof shapes, collision-safe routes');

assert.equal(fromRecords([{...record(),isRecommended:true}]).sensors[0].isRecommended,true);
assert.equal(fromRecords([record()]).sensors[0].isRecommended,false);
