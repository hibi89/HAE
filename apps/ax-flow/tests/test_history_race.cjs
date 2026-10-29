const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

class Element {
  constructor(selector = "") { this.selector=selector; this.children=[]; this.listeners={}; this.value=""; this.disabled=false; this.hidden=false; this.className=""; this._text=""; }
  get firstChild(){return this.children[0]||null;}
  get textContent(){return this._text;}
  set textContent(value){this._text=String(value);this.children=[];}
  addEventListener(name,fn){this.listeners[name]=fn;}
  appendChild(child){this.children.push(child);return child;}
  removeChild(child){this.children.splice(this.children.indexOf(child),1);return child;}
}
const tick=(ms=0)=>new Promise(resolve=>setTimeout(resolve,ms));
function ok(body){return {ok:true,status:200,json:async()=>body};}

async function main(){
  const elements=new Map();
  const document={querySelector(s){if(!elements.has(s))elements.set(s,new Element(s));return elements.get(s);},createElement(s){return new Element(s);}};
  const runA="Guiaaaaaaaaaaaa", runB="Guibbbbbbbbbbbb";
  let releaseA;
  const delayedA=new Promise(resolve=>{releaseA=resolve;});
  const fetch=async(url)=>{
    if(url==="/")return ok({});
    if(url==="/api/dbvora")return ok({available:false,error_code:"NOT_CONFIGURED"});
    if(url==="/api/runs?limit=10")return ok({runs:[
      {run_id:runA,status:"completed",created_at:"2026-10-29T02:00:00.000Z",steps_recorded:1,step_outcomes:{completed:1}},
      {run_id:runB,status:"completed",created_at:"2026-10-29T02:01:00.000Z",steps_recorded:1,step_outcomes:{completed:1}},
    ]});
    if(url===`/api/status?run_id=${runA}`) return delayedA;
    if(url.startsWith("/api/status?run_id=")){
      const id=url.slice(url.indexOf("=")+1);
      return ok({run_id:id,status:"completed",steps_recorded:1,step_outcomes:{completed:1},
        result_summary:{kind:"saved",count:2,duplicate_count:0},
        integration:{workflow_status:"completed",dbvora:{available:false,error_code:"NOT_CONFIGURED"}}});
    }
    if(url.startsWith("/api/audit?run_id="))return ok({available:true,
      review:{schema_version:"sovia.plan_observation_review.v1"},
      execution:{executed_steps:[{}],failed_steps:[],unverifiable_steps:[],policy_findings:[]}});
    throw new Error("Unexpected request: "+url);
  };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,"..","axflow","static","app.js"),"utf8"),{document,fetch,localStorage:{getItem(){return null;},setItem(){}}});
  await tick(10);
  const buttons=elements.get("#recent-runs-list").children.map(li=>li.children[0]);
  assert.equal(buttons.length,2);
  buttons[0].listeners.click();
  await tick();
  buttons[1].listeners.click();
  await tick(10);
  assert.equal(elements.get("#run-id").textContent,runB,"latest selection should load first");
  releaseA(ok({run_id:runA,status:"completed",steps_recorded:1,step_outcomes:{completed:1},
    result_summary:{kind:"saved",count:1,duplicate_count:0},integration:{workflow_status:"completed"}}));
  await tick(20);
  assert.equal(elements.get("#history-run-id").value,runB);
  assert.equal(elements.get("#run-id").textContent,runB,"late response for the old selection must not replace the latest result");
  assert.match(elements.get("#history-state").textContent,/불러왔습니다/);
  process.stdout.write("PASS: late history responses cannot overwrite the most recently selected run\n");
}
main().catch(error=>{process.stderr.write(error.stack+"\n");process.exitCode=1;});
