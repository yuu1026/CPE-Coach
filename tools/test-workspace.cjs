// Browser-independent checks for draft navigation and filtering behavior.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(value = '') { this.value = value; this.hidden = false; this.checked = false; this.dataset = {}; this.listeners = {}; this.style = {}; this.classes = new Set(); this.classList = {toggle:(name,on) => on ? this.classes.add(name) : this.classes.delete(name)}; }
  addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); }
  dispatchEvent(event) { for (const fn of this.listeners[event.type] || []) fn(event); }
  setAttribute() {}
  after(element) { this.afterElement = element; }
}
const source = fs.readFileSync('static/coach/workspace-preferences.js', 'utf8');
function workspace({stored, dataset = {}, error = false} = {}) {
  const fields = Object.fromEntries(['code','question','hint_level','run_custom','custom_input','custom_expected','submission_id','action'].map(name => [name, new Element()]));
  fields.hint_level.value = '1'; fields.submission_id.value = 'new-token'; fields.action.value = 'ask';
  const form = new Element(); form.dataset = {user:'7', problem:'100', record:'', token:'', ...dataset}; form.elements = {namedItem:name => fields[name]};
  const nodes = Object.fromEntries(['draft-status','restore-draft','clear-draft','reading-size','editor-size','reset-layout'].map(id => [id, new Element('15')]));
  nodes['reading-size'].options = nodes['editor-size'].options = ['14','15','16','18'].map(value => ({value}));
  const key = 'cpe:draft:v1:7:100'; const storage = new Map(stored ? [[key, JSON.stringify(stored)]] : []);
  const window = new Element(); let nextTimer = 0; const timers = new Map();
  const toggles = ['problem','chat'].map(name => { const element = new Element(); element.dataset.togglePane = name; return element; });
  const context = {document:{getElementById:id => id === 'workspace-form' ? form : nodes[id], querySelector:() => null, querySelectorAll:selector => selector === '[data-toggle-pane]' ? toggles : [], createElement:() => new Element(), documentElement:{style:{setProperty(){}}}}, window,
    localStorage:{getItem:key => storage.get(key) || null, setItem:(key,value) => { if (error) throw Error('unavailable'); storage.set(key,value); }, removeItem:key => storage.delete(key)},
    setTimeout:fn => { timers.set(++nextTimer, fn); return nextTimer; }, clearTimeout:id => timers.delete(id), Event:class {constructor(type) {this.type=type;}}};
  vm.runInNewContext(source, context);
  return {form, fields, nodes, storage, key, window, toggles, flush:() => { for (const fn of [...timers.values()]) fn(); }, saved:() => JSON.parse(storage.get(key))};
}
const draft = {code:'int main(){}', question:'hint?', hint_level:'2', run_custom:true, custom_input:'1', custom_expected:'2', record:''};
let page = workspace({stored:draft});
page.toggles[0].dispatchEvent({type:'click'}); page.toggles[1].dispatchEvent({type:'click'});
assert.ok(page.form.classes.has('is-problem-collapsed')); assert.ok(page.form.classes.has('is-chat-collapsed'));
assert.match(page.form.style.gridTemplateColumns,/^0px 0px/);
assert.equal(JSON.parse(page.storage.get('cpe:layout:v2:7')).collapsed.chat,true);
page.nodes['reset-layout'].dispatchEvent({type:'click'}); assert.equal(page.form.classes.size,0);
assert.match(page.form.style.gridTemplateColumns,/48fr/);
assert.equal(page.fields.code.value, draft.code); assert.equal(page.fields.run_custom.checked, true);
page.fields.question.value = 'new question'; page.form.dispatchEvent({type:'input'}); page.flush();
assert.equal(page.saved().question, 'new question');
page.nodes['clear-draft'].dispatchEvent({type:'click'}); page.window.dispatchEvent({type:'pagehide'});
assert.equal(page.storage.has(page.key), false, 'pagehide must not recreate cleared drafts');
assert.equal(page.fields.code.value, draft.code, 'clearing saved draft leaves editor intact');
page = workspace({stored:{...draft, record:'old'}, dataset:{record:'new'}});
assert.equal(page.fields.code.value, ''); assert.equal(page.nodes['restore-draft'].hidden, false);
page.nodes['restore-draft'].dispatchEvent({type:'click'}); assert.equal(page.fields.code.value, draft.code);
page = workspace({stored:{...draft, pending:{token:'posted',action:'ask',question:'hint?'}},dataset:{record:'1',token:'posted',status:'done'}});
assert.equal(page.fields.question.value, '', 'successful ask clears only the submitted question');
page = workspace({stored:{...draft, pending:{token:'posted',action:'ask',question:'hint?'}},dataset:{record:'1',token:'posted',status:'failed'}});
assert.equal(page.fields.question.value, 'hint?', 'failed ask preserves retry text');
page = workspace({stored:draft,dataset:{errors:'yes'}}); assert.equal(page.fields.code.value, '', 'server validation form wins over autosave');
page = workspace({error:true}); page.form.dispatchEvent({type:'input'}); page.flush(); assert.match(page.nodes['draft-status'].textContent, /無法保存/);
page = workspace(); page.fields.code.value = 'draft'; page.form.dispatchEvent({type:'submit', defaultPrevented:false}); assert.equal(page.saved().pending.token, 'new-token');
const search = new Element(), filter = new Element('all'), track = new Element(''), select = new Element('1'), matches = new Element(), button = new Element();
const options = [{value:'',textContent:'choose'},{value:'1',textContent:'UVa 100',dataset:{done:'yes',track:'simulation'}},{value:'2',textContent:'UVa 101',dataset:{done:'no',track:'numbers'}}];
select.options = [...options]; select.replaceChildren = (...children) => { select.options = children; };
const picker = new Element(); picker.querySelector = name => ({'[data-search]':search,'[data-filter]':filter,'[data-track-filter]':track,'[data-topics]':select,'[data-matches]':matches,button})[name];
vm.runInNewContext(fs.readFileSync('static/coach/problem-picker.js','utf8'), {document:{querySelectorAll:() => [picker]}});
filter.value = 'todo'; filter.dispatchEvent({type:'change'}); assert.equal(select.options.length,2); assert.equal(select.value,'');
search.value = 'missing'; search.dispatchEvent({type:'input'}); assert.equal(button.disabled,true);
search.value = ''; filter.value = 'all'; filter.dispatchEvent({type:'change'}); assert.equal(select.options.length,3, 'filtered options must return');
track.value = 'numbers'; track.dispatchEvent({type:'change'}); assert.equal(select.options.length,2); assert.equal(select.options[1].value,'2');
filter.value = 'done'; filter.dispatchEvent({type:'change'}); assert.equal(button.disabled,true, 'topic and completion filters intersect');
const noteStorage = new Map();
function notesPage(user, problem, blocked=false) {
  const note = new Element(), status = new Element();
  vm.runInNewContext(fs.readFileSync('static/coach/learning-tools.js','utf8'), {
    document:{getElementById:id => ({'workspace-form':{dataset:{user,problem}},'thinking-notes':note,'notes-status':status})[id]},
    localStorage:{getItem:key => noteStorage.get(key),setItem:(key,value) => { if (blocked) throw Error('storage blocked'); noteStorage.set(key,value); }}
  });
  return {note,status};
}
let notes = notesPage('7','100'); notes.note.value = 'my reasoning'; notes.note.dispatchEvent({type:'input'});
assert.equal(notesPage('7','100').note.value,'my reasoning');
assert.equal(notesPage('8','100').note.value,''); assert.equal(notesPage('7','101').note.value,'');
notes = notesPage('7','100',true); notes.note.dispatchEvent({type:'input'}); assert.match(notes.status.textContent,/無法保存/);
console.log('Workspace drafts, notes, and intersecting topic filters passed.');
