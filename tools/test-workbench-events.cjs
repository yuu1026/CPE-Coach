const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
class Element {
  constructor(value='') { this.value=value; this.checked=false; this.dataset={}; this.attributes={}; this.listeners={}; this.classList={add(){},toggle(){}}; this.children=[]; }
  addEventListener(name,fn) { (this.listeners[name] ||= []).push(fn); }
  async emit(type,props={}) { const event={type,defaultPrevented:false,preventDefault(){this.defaultPrevented=true;},...props}; for (const fn of this.listeners[type]||[]) await fn(event); return event; }
  dispatchEvent(event) { for (const fn of this.listeners[event.type]||[]) fn(event); }
  setAttribute(name,value) { this.attributes[name]=value; }
  getAttribute(name) { return this.attributes[name]; }
  removeAttribute(name) { delete this.attributes[name]; }
  replaceChildren() { this.children=[]; }
  append(child) { this.children.push(child); }
  focus() {}
}
const ids=['workspace-form','id_code','id_question','run-test','ask-assistant','clear-chat','editor-error','id_run_custom','id_custom_input','id_custom_expected','code-count','stale-result','result-freshness','chat-history','test-results'];
const nodes=Object.fromEntries(ids.map(id=>[id,new Element()]));
const form=nodes['workspace-form'], question=nodes.id_question, code=nodes.id_code;
code.value='int main(){}'; question.value='not submitted';
nodes['run-test'].value='test'; nodes['ask-assistant'].value='ask';
form.dataset={initialTab:'code',testUrl:'/test/',clearUrl:'/clear/',practiceUrl:'/problem/1/'};
const fields={action:new Element(),parent_submission:new Element(),submission_id:new Element('token'),csrfmiddlewaretoken:new Element('csrf'),question,code};
form.elements={namedItem:name=>fields[name]};
const wait=new Element(); form.querySelector=selector=>selector==='[data-wait]'?wait:fields.action;
const submissions=[]; form.requestSubmit=button=>submissions.push(button.value);
class FakeFormData {
  constructor(source) { this.values=new Map(source?Object.entries(fields).map(([name,field])=>[name,field.value]):[]); }
  delete(key) { this.values.delete(key); } set(key,value) { this.values.set(key,value); }
}
const requests=[], locations=[];
const browser=new Element(); browser.confirm=()=>true; browser.alert=message=>{throw Error(message);}; browser.history={replaceState:(_,__,url)=>locations.push(url)};
const context={document:{getElementById:id=>nodes[id]||null,querySelectorAll:()=>[],querySelector:()=>null,createElement:()=>new Element(),documentElement:new Element()},window:browser,
  FormData:FakeFormData,Event:class {constructor(type){this.type=type;}},crypto:{randomUUID:()=> 'retry-token'},
  fetch:async(url,options)=>{requests.push({url,options}); return {ok:true,json:async()=>url==='/clear/'?{parent:4,next_token:'clear-token',url:'/submission/4/'}:{html:'results',record:4,token:'test-token',next_token:'new-token',url:'/submission/4/',code:code.value,custom_test:{enabled:false}}};}};
vm.runInNewContext(fs.readFileSync('static/coach/workbench.js','utf8'),context);
(async()=>{
  await question.emit('keydown',{key:'Enter'}); assert.deepEqual(submissions,['ask']);
  for (const props of [{shiftKey:true},{isComposing:true},{keyCode:229},{repeat:true}]) await question.emit('keydown',{key:'Enter',...props});
  assert.equal(submissions.length,1,'newline, IME confirmation, and held keys must not send');
  const tested=await form.emit('submit',{submitter:nodes['run-test']});
  assert.equal(tested.defaultPrevented,true);
  assert.equal(requests.length,1); assert.equal(requests[0].url,'/test/');
  assert.equal(requests[0].options.body.values.has('question'),false);
  assert.equal(question.value,'not submitted'); assert.equal(nodes['chat-history'].children.length,0);
  assert.equal(fields.parent_submission.value,4); assert.equal(fields.submission_id.value,'new-token');
  assert.equal(nodes['ask-assistant'].disabled,false);
  await nodes['clear-chat'].emit('click');
  assert.equal(requests[1].url,'/clear/'); assert.equal(question.value,''); assert.equal(code.value,'int main(){}');
  assert.equal(nodes['chat-history'].children.length,1); assert.equal(fields.submission_id.value,'clear-token');
  console.log('Enter/IME, independent testing, and chat clearing checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
