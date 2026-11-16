// Bounded mutation fuzzing of the viewer's GeoJSON boundary (not coverage guided).
// No network or external API. Run under: node --max-old-space-size=128 tests/js/territory_fuzz.mjs
import assert from "node:assert/strict";
import {mkdir,writeFile} from "node:fs/promises";
import {usableGeometry} from "../../app/territory-geo.js";
let seed=20261115;const random=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return(seed>>>0)/4294967296;};
const corpus=['null','{}','{"type":"Polygon","coordinates":null}','{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,0]]]}','{"type":"MultiPolygon","coordinates":[null]}','{"type":"LineString","coordinates":[[NaN,1],[2,3]]}'];
const dict=['null','[]','{}','"coordinates"',':',',','1e309','-0','"💧"','[[[[',']]]]', '"__proto__"'];
const start=performance.now();let total=0,parsed=0,accepted=0;
for(;total<10000&&performance.now()-start<60000;total++){
  let input=corpus[Math.floor(random()*corpus.length)];
  const at=Math.floor(random()*(input.length+1)),token=dict[Math.floor(random()*dict.length)];
  input=random()<.5?input.slice(0,at)+token+input.slice(at):input.slice(0,at)+input.slice(at+Math.floor(random()*8));
  assert.ok(input.length<=8192);
  let value;try{value=JSON.parse(input);parsed++;}catch(e){if(e instanceof SyntaxError)continue;throw e;}
  try{const result=usableGeometry(value);assert.equal(typeof result,'boolean');if(result)accepted++;}
  catch(error){await mkdir('.local/fuzz/territory',{recursive:true});await writeFile('.local/fuzz/territory/failure.json',JSON.stringify({input,total,seed,error:String(error)},null,2));throw error;}
}
const result={kind:'bounded mutation, not coverage guided',initialSeed:20261115,total,parsed,accepted,rejected:parsed-accepted,parseRejected:total-parsed,ms:performance.now()-start,maxInputBytes:8192,findings:0};
await mkdir('.local/fuzz/territory',{recursive:true});await writeFile('.local/fuzz/territory/result.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
