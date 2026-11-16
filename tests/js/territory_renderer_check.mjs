// Pixel/graphics check on an explicitly synthetic flat ground plane. This isolates custom-layer
// cost from native terrain, vector parsing and independent analytical jobs; no regional FPS claim.
import {writeFile} from "node:fs/promises";
export async function checkRenderer(browser, base, out) {
  const page=await browser.newPage({viewport:{width:1100,height:720}}),errors=[];
  page.on('pageerror',e=>errors.push(e.stack||String(e)));
  await page.route(base+'/',route=>route.fulfill({contentType:'text/html',body:`<!doctype html><html lang="en"><head>
  <script src="https://cdn.jsdelivr.net/npm/maplibre-gl@5.24.1/dist/maplibre-gl.js"></script>
  <style>body{margin:0}#map{position:fixed;inset:0}p{position:fixed;top:0;left:0;z-index:5;background:#111;color:white;padding:12px;font:14px sans-serif}</style></head>
  <body><div id="map"></div><p>SYNTHETIC GPU FIXTURE — flat ground; illustrative trees and water; no real inventory or hydraulic model</p></body></html>`}));
  try {
    await page.goto(base+'/',{waitUntil:'load'});
    await page.evaluate(async()=>{
      const {TerritoryLayer}=await import('/app/territory-gl.js');
      const map=window.qaMap=new maplibregl.Map({container:'map',style:{version:8,sources:{},layers:[{id:'bg',type:'background',paint:{'background-color':'#d2c3a4'}}]},center:[-80.63,-5.19],zoom:18,pitch:55,bearing:0,attributionControl:false});
      await new Promise(resolve=>map.on('load',resolve));
      const layer=window.qaLayer=new TerritoryLayer(e=>{throw new Error(e);});map.addLayer(layer);
      layer.map={queryTerrainElevation:()=>0,triggerRepaint:()=>map.triggerRepaint()};
      layer.setData(Array.from({length:20},(_,i)=>({lon:-80.63+(i%5-2)*.00012,lat:-5.19+(Math.floor(i/5)-2)*.00012,height:8,radius:4,shade:(i%5)/5})),[
        {type:'Feature',properties:{class:'river'},geometry:{type:'LineString',coordinates:[[-80.6304,-5.1904],[-80.6296,-5.1896]]}}
      ],[-80.63,-5.19]);
    });
    const capture=()=>page.evaluate(()=>new Promise(resolve=>{window.qaMap.once('render',()=>{
      const source=window.qaMap.getCanvas(),c=document.createElement('canvas');c.width=source.width;c.height=source.height;
      const ctx=c.getContext('2d');ctx.drawImage(source,0,0);const d=ctx.getImageData(0,0,c.width,c.height).data;
      let green=0;for(let i=0;i<d.length;i+=4)if(d[i+1]>d[i]+10&&d[i+1]>d[i+2]+10)green++;
      resolve({url:source.toDataURL('image/png'),green,stats:{...window.qaLayer.stats}});
    });window.qaMap.triggerRepaint();}));
    const on=await capture();
    await writeFile(out+'/renderer-fixture.png',Buffer.from(on.url.split(',')[1],'base64'));
    await page.evaluate(()=>{window.qaLayer.active=false;});const off=await capture();
    await page.evaluate(()=>{window.qaLayer.active=true;});
    const timing=await page.evaluate(async()=>{
      const frames=[];let last=null;await new Promise(resolve=>{const start=performance.now();const step=t=>{if(last!==null)frames.push(t-last);last=t;if(performance.now()-start>=2000)return resolve();window.qaMap.triggerRepaint();requestAnimationFrame(step);};requestAnimationFrame(step);});
      frames.sort((a,b)=>a-b);return{samples:frames.length,medianFrameMs:frames[Math.floor(frames.length/2)],p95FrameMs:frames[Math.floor(frames.length*.95)]};
    });
    await page.evaluate(()=>window.qaMap.removeLayer('territory-detail'));
    const released=await page.evaluate(()=>window.qaLayer.stats.gpuBytes===0);
    return{ok:on.green>250&&off.green===0&&on.stats.trees===20&&on.stats.drawCalls===2&&released&&errors.length===0,
      pixels:{onGreen:on.green,offGreen:off.green},stats:on.stats,timing,released,errors,scope:'Synthetic flat-ground pixel and GPU cost check only. Real regional terrain performance is separate.'};
  }finally{await page.close();}
}
