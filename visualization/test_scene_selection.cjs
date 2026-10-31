// Run with: node visualization/test_scene_selection.cjs (no browser/dependencies).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

function element(dataset = {}) {
  const classes = new Set();
  return {
    dataset, attributes: {}, handlers: {},
    classList: {toggle(name, on) {on ? classes.add(name) : classes.delete(name);}, contains(name) {return classes.has(name);}},
    setAttribute(name, value) {this.attributes[name] = value;},
    addEventListener(name, handler) {this.handlers[name] = handler;},
    querySelector() {return this.button;},
    click() {this.handlers.click();},
  };
}
// Include punctuation in an ID to catch accidental string-splitting of sensor IDs.
const ids = ['S01, east', 'S02', 'S03', 'S04'];
const rows = [element({combination:'1'}), element({combination:'2'})];
rows.forEach(row => {row.button = element();});
const buttons = ids.map(sensor => element({sensor}));
const status = element();
const nodes = {
  'location-data': {textContent: JSON.stringify({selected: ids.slice(0,3), combinations:{'1':ids.slice(0,3),'2':ids.slice(1)}})},
  'location-scene': element(), 'location-loading': status,
};
const context = vm.createContext({
  document: {
    getElementById(id) {return nodes[id];},
    querySelectorAll(selector) {return selector === '[data-combination]' ? rows : buttons;},
  },
});
const source = fs.readFileSync(path.join(__dirname,'../static/js/greenhouse-scene.js'),'utf8');
vm.runInContext(source, context, {importModuleDynamically() {return Promise.reject(new Error('WebGL not used in selection unit test'));}});
assert.equal(rows[0].classList.contains('comparison-selected'),true);
assert.equal(rows[1].classList.contains('comparison-selected'),false);
assert.equal(buttons[0].attributes['aria-pressed'],'true');
rows[1].click();
assert.equal(rows[0].classList.contains('comparison-selected'),false);
assert.equal(rows[1].button.attributes['aria-pressed'],'true');
assert.equal(buttons[0].attributes['aria-pressed'],'false');
assert.equal(buttons[3].attributes['aria-pressed'],'true');
buttons[0].click();
assert.equal(rows[1].classList.contains('comparison-selected'),true,'inspecting coordinates preserves recommendation');
assert.equal(buttons[0].attributes['aria-pressed'],'false');
assert.equal(buttons.slice(1).every(button => button.attributes['aria-pressed']==='true'),true);
console.log('PASS: default recommendation, row change, exclusive selection, coordinate-list selection, IDs preserved');
