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
const ids=['workspace-form','id_code','id_question','run-test','ask-assistant','clear-chat','editor-error','id_run_custom','id_custom_input','id_custom_expected','code-count','stale-result','result-freshness','chat-history','test-results','verified-revision','apply-revision','undo-revision','revision-status','revision-controls'];
const nodes=Object.fromEntries(ids.map(id=>[id,new Element()]));
const form=nodes['workspace-form'], question=nodes.id_question, code=nodes.id_code;
code.value='int main(){}'; question.value='not submitted';
const revisedCode='int main(){\r\nreturn 0;\r\n}';
nodes['verified-revision'].textContent=JSON.stringify({base_code:code.value,candidate_code:revisedCode});
nodes['run-test'].value='test'; nodes['ask-assistant'].value='ask';
form.dataset={initialTab:'code',testUrl:'/test/',clearUrl:'/clear/',practiceUrl:'/problem/1/'};
const fields={action:new Element(),parent_submission:new Element(),submission_id:new Element('token'),csrfmiddlewaretoken:new Element('csrf'),question,code};
form.elements={namedItem:name=>fields[name]};
const wait=new Element(); form.querySelector=selector=>selector==='[data-wait]'?wait:fields.action;
const submissions=[]; form.requestSubmit=button=>submissions.push(button.value);
class FakeFormData {
  constructor(source) { this.values=new Map(source?Object.entries(fields).map(([name,field])=>[name,field.value]):[]); }
  delete(key) { this.values.delete(key); } set(key,value) { this.values.set(key,value); }
  get(key) { return this.values.get(key); }
}
const requests=[], locations=[];
const browser=new Element(); browser.confirm=()=>true; browser.alert=message=>{throw Error(message);}; browser.history={replaceState:(_,__,url)=>locations.push(url)};
const context={document:{getElementById:id=>nodes[id]||null,querySelectorAll:()=>[],querySelector:()=>null,createElement:()=>new Element(),documentElement:new Element()},window:browser,
  FormData:FakeFormData,Event:class {constructor(type){this.type=type;}},crypto:{randomUUID:()=> 'retry-token'},
  fetch:async(url,options)=>{requests.push({url,options}); return {ok:true,json:async()=>url==='/clear/'?{parent:4,next_token:'clear-token',url:'/submission/4/'}:{html:'results',record:4,token:'test-token',next_token:'new-token',url:'/submission/4/',code:code.value,custom_test:{enabled:false}}};}};
vm.runInNewContext(fs.readFileSync('static/coach/workbench.js','utf8'),context);
(async()=>{
  code.value='independent edit';
  await nodes['apply-revision'].emit('click'); assert.equal(code.value,'independent edit','stale suggestions cannot overwrite later edits');
  code.value='int main(){}'; nodes.id_run_custom.checked=true;
  await nodes['apply-revision'].emit('click'); assert.equal(code.value,'int main(){}','changed tests invalidate verification');
  nodes.id_run_custom.checked=false;
  await nodes['apply-revision'].emit('click'); assert.equal(code.value,revisedCode);
  assert.equal(nodes['undo-revision'].disabled,false);
  code.value='later edits'; await nodes['undo-revision'].emit('click'); assert.equal(code.value,'later edits','undo must preserve later edits');
  code.value=revisedCode.replace(/\r\n/g,'\n'); await nodes['undo-revision'].emit('click'); assert.equal(code.value,'int main(){}','CRLF/LF normalization must not prevent safe undo');
  form.setAttribute('aria-busy','true'); await nodes['apply-revision'].emit('click'); assert.equal(code.value,'int main(){}'); form.removeAttribute('aria-busy');
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
  await form.emit('submit',{submitter:nodes['ask-assistant']});
  const sentData = new FakeFormData(form);
  await form.emit('formdata',{formData:sentData});
  assert.equal(question.value,'','sending chat clears the visible composer');
  assert.equal(sentData.get('question'),'not submitted','the actual message must remain in the outgoing request');
  await browser.emit('pageshow');
  await nodes['clear-chat'].emit('click');
  assert.equal(requests[1].url,'/clear/'); assert.equal(question.value,''); assert.equal(code.value,'int main(){}');
  assert.equal(nodes['chat-history'].children.length,1); assert.equal(fields.submission_id.value,'clear-token');
  assert.equal(nodes['revision-controls'].hidden,true);
  await nodes['apply-revision'].emit('click'); assert.equal(code.value,'int main(){}','cleared chat cannot apply a deleted suggestion');
  // Exercise the new asynchronous path instead of only the native fallback.
  form.dataset.askUrl='/ask/';
  context.AbortSignal={timeout:()=>undefined}; context.setTimeout=fn=>fn();
  browser.location={assign:url=>locations.push(url)};
  browser.sessionStorage={setItem(){},removeItem(){},getItem(){return null;}};
  let polls=0, asks=0;
  context.fetch=async(url,options)=>{
    if (url==='/ask/') {
      asks++; assert.equal(options.body.get('question'),'新的問題');
      return {ok:true,json:async()=>({record:5,status_url:'/submission/5/progress/',url:'/submission/5/'})};
    }
    polls++;
    return {ok:true,json:async()=>polls===1 ? {status:'running',phase:'generation',label:'正在生成回覆',generated_chars:30,elapsed_seconds:2} : {status:'done',url:'/submission/5/'}};
  };
  question.value='新的問題';
  const flight=form.emit('submit',{submitter:nodes['ask-assistant']});
  const repeated=await form.emit('submit',{submitter:nodes['ask-assistant']});
  assert.equal(repeated.defaultPrevented,true);
  await flight;
  assert.equal(asks,1,'busy UI must not send a second chat');
  assert.equal(polls,2); assert.equal(question.value,'');
  assert.equal(locations.at(-1),'/submission/5/');
  context.fetch=async()=>({ok:false,json:async()=>({error:'目前忙碌，尚未送出'})});
  question.value='不能丟失的訊息';
  await form.emit('submit',{submitter:nodes['ask-assistant']});
  assert.equal(question.value,'不能丟失的訊息');
  assert.equal(wait.hidden,false,'failed acknowledgements must stay visible');
  assert.match(wait.textContent,/忙碌/);
  console.log('Enter/IME, independent testing, and chat clearing checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
