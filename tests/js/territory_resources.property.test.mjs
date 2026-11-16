import {test} from "node:test";
import assert from "node:assert/strict";
const module=await import(process.env.FAST_CHECK_MODULE||"fast-check"),fc=module.default??module;
import {TerritoryLayer} from "../../app/territory-gl.js";
const identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
function graphics(failAt=Infinity) {
  const live=new Set(),counts={draw:0,created:0},gl={};
  for(const kind of ['Buffer','Program','Shader','VertexArray']){
    gl['create'+kind]=()=>{const h={kind,id:++counts.created};live.add(h);return h;};
    gl['delete'+kind]=h=>{assert.ok(live.delete(h),'GPU handle must be released exactly once');};
  }
  for(const name of ['shaderSource','compileShader','attachShader','linkProgram','bindVertexArray','bindBuffer','bufferData','enableVertexAttribArray','vertexAttribPointer','vertexAttribDivisor','triggerRepaint','enable','disable','depthMask','blendFunc','useProgram','uniformMatrix4fv','uniform3fv','uniform1f'])gl[name]=()=>{};
  gl.getShaderParameter=()=>counts.created<failAt;gl.getShaderInfoLog=()=>"Injected shader compilation failure";gl.getProgramParameter=()=>true;
  gl.getUniformLocation=()=>0;gl.drawArrays=gl.drawArraysInstanced=()=>counts.draw++;
  gl.isContextLost=()=>false;
  return {gl,live,counts};
}
test("GPU handles are bounded and released over changing data and repeated lifecycle operations",()=>{
  fc.assert(fc.property(fc.array(fc.tuple(fc.integer({min:0,max:20}),fc.boolean()),{minLength:1,maxLength:12}),actions=>{
    const{gl,live,counts}=graphics(),errors=[];
    const map={queryTerrainElevation:()=>125,triggerRepaint(){}};
    const layer=new TerritoryLayer(e=>errors.push(e));layer.onAdd(map,gl);
    assert.equal(live.size,9);
    for(const[n,motion]of actions){
      layer.moving=motion;
      layer.setData(Array.from({length:n},(_,i)=>({lon:-80.6+i*.0001,lat:-5.2,height:6,radius:3,shade:.5})),[],[-80.6,-5.2]);
      layer.render(gl,{defaultProjectionData:{mainMatrix:identity}});
      assert.equal(layer.stats.trees,n);assert.ok(layer.stats.gpuBytes<20000);assert.ok(layer.stats.drawCalls<=1);assert.equal(live.size,9);
    }
    assert.deepEqual(errors,[]);layer.onRemove();assert.equal(live.size,0);layer.onRemove();assert.equal(live.size,0);
    assert.ok(counts.draw<=actions.length);
  }),{numRuns:1200,seed:20261115,verbose:true});
});
test("failed shader startup cleans all handles; unsupported projection reports once without drawing",()=>{
  const failed=graphics(2),errors=[],layer=new TerritoryLayer(e=>errors.push(e));
  layer.onAdd({queryTerrainElevation:()=>0,triggerRepaint(){}},failed.gl);
  assert.equal(failed.live.size,0);assert.equal(errors.length,1);
  const g=graphics(),l=new TerritoryLayer(e=>errors.push(e));l.onAdd({queryTerrainElevation:()=>0,triggerRepaint(){}},g.gl);
  l.setData([{lon:-80.6,lat:-5.2,height:6,radius:3,shade:.5}],[],[-80.6,-5.2]);
  l.setData([{lon:-80.6,lat:-5.2,height:6,radius:3,shade:.5}],[],[-80.6,-5.2]);
  l.render(g.gl,{});l.render(g.gl,{});assert.equal(errors.length,2);assert.equal(g.counts.draw,0);l.onRemove();assert.equal(g.live.size,0);
});
