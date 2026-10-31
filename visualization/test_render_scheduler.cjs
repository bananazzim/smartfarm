const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname,'../static/js/render-scheduler.js'),'utf8').replace('export function','function');
const context = vm.createContext({});
vm.runInContext(source, context);
const frames = new Map();
let sequence = 0;
let draws = 0;
const scheduler = context.createRenderScheduler({
  draw() {draws++;},
  requestFrame(callback) {const id=++sequence;frames.set(id,callback);return id;},
  cancelFrame(id) {frames.delete(id);},
});
function flush() {
  const batch=[...frames.values()];frames.clear();batch.forEach(callback=>callback());
}
scheduler.invalidate();scheduler.invalidate();scheduler.invalidate();
assert.equal(frames.size,1,'multiple changes coalesce into one frame');
flush();assert.equal(draws,1);assert.equal(frames.size,0,'idle scene schedules no frames');
for(let i=0;i<600;i++) flush();
assert.equal(draws,1,'no idle rendering over 600 simulated ticks');
scheduler.invalidate();scheduler.setActive(false);
assert.equal(frames.size,0,'hidden scene cancels pending work');
scheduler.invalidate();assert.equal(frames.size,0);
scheduler.setActive(true);assert.equal(frames.size,1);
flush();assert.equal(draws,2);
scheduler.invalidate();scheduler.dispose();assert.equal(frames.size,0);
scheduler.invalidate();scheduler.setActive(true);assert.equal(frames.size,0);
console.log('PASS: coalesced frames, idle zero frames, hidden pause, resume, disposal');
