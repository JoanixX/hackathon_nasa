// Contract-derived properties: metre scale, geographic round trips, holes, exclusion envelopes,
// deterministic bounded detail and hostile GeoJSON. Seed/replay printed by fast-check on failure.
import { test } from "node:test";
import assert from "node:assert/strict";
const module = await import(process.env.FAST_CHECK_MODULE || "fast-check"), fc = module.default ?? module;
import { mercator, fromMercator, distanceM, contains, clearOf, vegetationSamples, usableGeometry, localMatrix, solarPosition, renderPolicy } from "../../app/territory-geo.js";
const runs = (numRuns, seed = 20261115) => ({ numRuns, seed, verbose: true });
const coord = fc.tuple(fc.double({min:-81.32,max:-79.22,noNaN:true}),fc.double({min:-6.37,max:-4.08,noNaN:true}));
const rectangle = (x,y,w,h) => ({type:"Polygon",coordinates:[[[x,y],[x+w,y],[x+w,y+h],[x,y+h],[x,y]]]});
test("hidden/reduced-motion views never schedule effects; software profiles stay bounded",()=>{
  fc.assert(fc.property(fc.boolean(),fc.boolean(),fc.boolean(),fc.boolean(),fc.double({min:.25,max:4,noNaN:true}),fc.constantFrom(.5,.75,1,null),(software,reduced,visible,animate,ratio,quality)=>{
    const p=renderPolicy({software,reduced,visible,animate,ratio,quality});
    assert.ok(p.pixelRatio>=ratio*.5&&p.pixelRatio<=ratio);
    if(reduced||!visible||!animate)assert.equal(p.fps,0);
    else assert.ok(p.fps>0&&p.fps<=(software?1:24));
    if(quality===null&&software)assert.equal(p.pixelRatio,ratio*.5);
  }),runs(2000,15));
});

test("geographic/mercator round trips preserve Piura coordinates and altitude", () => {
  fc.assert(fc.property(coord,fc.double({min:-100,max:9000,noNaN:true}),(p,h)=>{
    const m=mercator(p,h),back=fromMercator(m.x,m.y);
    assert.ok(Math.abs(back[0]-p[0])<1e-11&&Math.abs(back[1]-p[1])<1e-11);
    assert.ok(Math.abs(m.z/m.unit-h)<1e-9);
    assert.ok(Math.abs(distanceM(p,back))<1e-6);
  }),runs(3000));
});
test("a one metre horizontal offset and a one metre vertical object use the same local scale",()=>{
  fc.assert(fc.property(coord,fc.double({min:.01,max:100,noNaN:true}),(p,metres)=>{
    const m=mercator(p,metres),offset=fromMercator(m.x+metres*m.unit,m.y);
    assert.ok(Math.abs(distanceM(p,offset)-metres)<2e-6);
    assert.ok(Math.abs(m.z-metres*m.unit)<1e-16);
  }),runs(3000,42));
});
test("polygon holes exclude interiors independently of winding and multipolygon order",()=>{
  fc.assert(fc.property(coord,fc.double({min:.002,max:.02,noNaN:true}),(p,size)=>{
    const outer=rectangle(p[0]-size,p[1]-size,2*size,2*size).coordinates[0];
    const hole=rectangle(p[0]-size/3,p[1]-size/3,2*size/3,2*size/3).coordinates[0];
    for(const rings of [[outer,hole],[outer.toReversed(),hole.toReversed()]]){
      assert.equal(contains(p,{type:"Polygon",coordinates:rings}),false);
      assert.equal(contains([p[0]+size*.8,p[1]],{type:"Polygon",coordinates:rings}),true);
      assert.equal(contains(p,{type:"MultiPolygon",coordinates:[rings]}),false);
    }
  }),runs(1800));
});
test("tree detail stays in mapped cover, outside water/building holes and full clearance envelopes",()=>{
  fc.assert(fc.property(coord,fc.integer({min:0,max:40}),(p,limit)=>{
    const forest=rectangle(p[0]-.006,p[1]-.006,.012,.012),lake=rectangle(p[0]-.001,p[1]-.001,.002,.002);
    const road={type:"LineString",coordinates:[[p[0]-.01,p[1]],[p[0]+.01,p[1]]]};
    const features=[{geometry:forest,properties:{class:"wood"}}],blocked=[{geometry:lake},{geometry:road}];
    const samples=vegetationSamples(features,blocked,p,15,limit);
    assert.ok(samples.length<=limit);
    assert.deepEqual(samples,vegetationSamples(features,blocked,p,15,limit));
    for(const s of samples){const q=[s.lon,s.lat];assert.ok(contains(q,forest));assert.ok(!contains(q,lake));assert.ok(clearOf(q,[road,lake],12));assert.equal(s.evidence,"illustrative");}
    assert.deepEqual(vegetationSamples(features,blocked,p,12,limit),[]);
    assert.deepEqual(vegetationSamples(features,Array(257).fill({geometry:lake}),p,15,limit),[]);
  }),runs(500));
});
test("metric-frame matrix agrees with independent homogeneous world-coordinate evaluation",()=>{
  fc.assert(fc.property(coord,fc.array(fc.double({min:-10,max:10,noNaN:true}),{minLength:16,maxLength:16}),fc.tuple(fc.integer({min:-1000,max:1000}),fc.integer({min:-1000,max:1000}),fc.integer({min:0,max:5000})),(p,m,v)=>{
    const o=mercator(p),out=localMatrix(m,o),world=[o.x+v[0]*o.unit,o.y+v[1]*o.unit,v[2]*o.unit,1];
    for(let row=0;row<4;row++){
      const expected=world.reduce((sum,a,j)=>sum+a*m[j*4+row],0),actual=[...v,1].reduce((sum,a,j)=>sum+a*out[j*4+row],0);
      assert.ok(Math.abs(expected-actual)<3e-6);
    }
  }),runs(2000));
});
test("small camera translations preserve the world positions of the same forest's trees",()=>{
  fc.assert(fc.property(coord,p=>{
    const forest=rectangle(p[0]-.001,p[1]-.001,.002,.002),features=[{geometry:forest,properties:{class:"forest"}}];
    const a=vegetationSamples(features,[],p,15,700),b=vegetationSamples(features,[],[p[0],p[1]+.00001],15,700);
    const keys=s=>s.map(t=>[t.lon,t.lat,t.height].join(',')).sort();
    assert.deepEqual(keys(a),keys(b));
  }),runs(700,100));
});
test("solar direction remains finite and bounded for real dates and longitudes",()=>{
  fc.assert(fc.property(coord,fc.integer({min:Date.UTC(2020,0,1),max:Date.UTC(2035,11,31)}),(p,ms)=>{
    const s=solarPosition(new Date(ms),...p);
    assert.ok(s.altitude>=-90&&s.altitude<=90&&s.azimuth>=0&&s.azimuth<360&&s.direction.every(Number.isFinite));
  }),runs(2000));
});
test("malformed/oversized coordinates are rejected before GPU preparation",()=>{
  fc.assert(fc.property(fc.jsonValue(),value=>{assert.equal(typeof usableGeometry(value),"boolean");}),runs(3000));
  assert.equal(usableGeometry({type:"Polygon",coordinates:[Array(12001).fill([0,0])]}),false);
  assert.equal(usableGeometry({type:"Polygon",coordinates:[[null,[1,2]]]}),false);
  assert.throws(()=>mercator([NaN,0]),RangeError);
});
