import {test} from 'node:test';
import assert from 'node:assert/strict';
const m=await import(process.env.FAST_CHECK_MODULE||'fast-check'),fc=m.default??m;
import {partitionCards} from '../../app/workflow.js';
import {detailTier} from '../../app/territory-geo.js';
test('all cards occur once in order, bounded by the available page height',()=>{
  fc.assert(fc.property(fc.array(fc.integer({min:1,max:2000}),{maxLength:200}),fc.integer({min:48,max:1200}),(heights,budget)=>{
    const pages=partitionCards(heights,budget);
    assert.deepEqual(pages.flat(),heights.map((_,i)=>i));
    for(const page of pages)assert.ok(page.reduce((sum,i)=>sum+Math.min(heights[i],budget),0)<=budget);
  }),{numRuns:5000,seed:16012026});
});
test('detail hysteresis does not oscillate inside the transition bands',()=>{
  fc.assert(fc.property(fc.double({min:12.5,max:12.999999,noNaN:true}),fc.double({min:14.5,max:14.999999,noNaN:true}),(low,high)=>{
    assert.equal(detailTier(low,0),0);assert.equal(detailTier(low,1),1);
    assert.equal(detailTier(high,1),1);assert.equal(detailTier(high,2),2);
    assert.equal(detailTier(16,0),2);assert.equal(detailTier(10,2),0);
  }),{numRuns:5000,seed:16022026});
});
test('malformed sizes and zooms remain bounded',()=>{
  fc.assert(fc.property(fc.anything({maxDepth:3}),(value)=>{
    const tier=detailTier(value);assert.ok([0,1,2].includes(tier));
    if(!Number.isFinite(value)||value<48)assert.throws(()=>partitionCards([1],value),RangeError);
  }),{numRuns:2000,seed:16032026});
});
