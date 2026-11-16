// Rendering or switching focus areas must not submit analyses without the user's load action.
import {test} from "node:test";
import assert from "node:assert/strict";
const module=await import(process.env.FAST_CHECK_MODULE||"fast-check"),fc=module.default??module;
class FakeNode {
  children=[];textContent="";
  append(...nodes){this.children.push(...nodes);}
  setAttribute(){} addEventListener(){}
}
globalThis.Node=FakeNode;
globalThis.document={createElement:()=>new FakeNode(),createTextNode:text=>{const n=new FakeNode();n.textContent=text;return n;}};
globalThis.window={RaizCore:{createVersionGuard:()=>({})},matchMedia:()=>({matches:false})};
globalThis.location=new URL('http://local/');globalThis.addEventListener=()=>{};
let requests=0;globalThis.fetch=()=>{requests++;throw new Error('Unexpected automatic external work');};
const interval=globalThis.setInterval;globalThis.setInterval=()=>0;
const {overviewBlock}=await import('../../app/overview.js');
const {state}=await import('../../app/state.js');
globalThis.setInterval=interval;
const text=n=>n.textContent+(n.children||[]).map(c=>typeof c==='string'?c:text(c)).join('');
test('overview rendering preserves state and never performs analysis I/O across changing focus keys',()=>{
  fc.assert(fc.property(fc.array(fc.tuple(fc.string({maxLength:50}),fc.boolean()),{minLength:1,maxLength:20}),actions=>{
    for(const[name,cached]of actions){
      state.focusArea={name};
      state.overview=cached?{key:name,landscape:null,nisar:{status:'running'}}:null;
      const previous=state.overview;
      const output=text(overviewBlock(()=>{}));
      assert.equal(requests,0);assert.equal(state.overview,previous);
      assert.equal(output.includes('Load area overview'),!cached);
    }
  }),{numRuns:2000,seed:20261115,verbose:true});
});
