// Integrated real-data browser checks plus explicitly labelled renderer fixtures.
// No model inference, no Earthdata download. Default Chromium software renderer, unthrottled network.
import {mkdir,writeFile} from "node:fs/promises";
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||"playwright");
const HARDWARE=process.env.TERRITORY_RENDERER==='hardware';
const BASE=process.argv[2]||"http://127.0.0.1:8765",OUT=HARDWARE?".local/qa/territory/hardware":".local/qa/territory";
await mkdir(OUT,{recursive:true});
const result={startedUtc:new Date().toISOString(),base:BASE,checks:[],errors:[],networkFailures:[],measurements:{},scope:`${HARDWARE?'D3D11 hardware':'SwiftShader software'} Chromium; real mapping/DEM checks and separately labelled GPU fixtures. No scientific or sustained-session certification.`};
const check=(name,ok,detail)=>{result.checks.push({name,ok:!!ok,detail});console.log(ok?"PASS":"FAIL",name,detail??"");};
const browser=await chromium.launch({args:HARDWARE?["--ignore-gpu-blocklist","--use-gl=angle","--use-angle=d3d11"]:["--enable-unsafe-swiftshader","--ignore-gpu-blocklist","--use-gl=angle","--use-angle=swiftshader"]});
const page=await browser.newPage({viewport:{width:1100,height:720}}),requests=[];
// A separately edited eager overview appeared during this task. Preserve it in the application;
// an optional isolated run tests the territorial viewer without launching those unrelated analysis jobs.
result.overviewIsolated=process.env.TERRITORY_ISOLATE_OVERVIEW==='1';
if(result.overviewIsolated)await page.route('**/app/overview.js',route=>route.fulfill({contentType:'text/javascript',body:`
export function overviewBlock(){const p=document.createElement('p');p.textContent='QA isolation: independent background hazard/water analysis withheld.';return p;}
export function loadOverview(){}
`}));
page.on("pageerror",e=>result.errors.push(e.stack||String(e)));
page.on("request",r=>requests.push(r.url()));
page.on("requestfailed",r=>{if(r.failure()?.errorText!=="net::ERR_ABORTED")result.networkFailures.push({url:r.url(),error:r.failure()?.errorText});});
await page.addInitScript(()=>localStorage.setItem("raiz-tour","done"));
async function stableTerrain() {
  let consecutive=0,last=null;const started=Date.now();
  while(Date.now()-started<90000){
    last=await page.evaluate(async()=>{const m=(await import('/app/map.js')).getMap(),c=m.getCenter();return{enabled:!!m.getTerrain(),loaded:m.isSourceLoaded('dem'),moving:m.isMoving(),zoom:m.getZoom(),pitch:m.getPitch(),elevation:m.queryTerrainElevation(c),tiles:m.areTilesLoaded()};});
    if(last.enabled&&last.loaded&&!last.moving&&last.tiles&&Number.isFinite(last.elevation)&&last.elevation>300)consecutive++;else consecutive=0;
    if(consecutive>=5)return{ok:true,ms:Date.now()-started,last};
    await page.waitForTimeout(500);
  }
  return{ok:false,ms:Date.now()-started,last};
}
async function mapCapture(path){
  const url=await page.evaluate(async()=>{
    const m=(await import('/app/map.js')).getMap();
    return new Promise(resolve=>{m.once('render',()=>resolve(m.getCanvas().toDataURL('image/png')));m.triggerRepaint();});
  });
  await writeFile(path,Buffer.from(url.split(',')[1],'base64'));
}
try{
  await page.goto(BASE,{waitUntil:"domcontentloaded"});
  await page.waitForFunction(()=>window.raiz?.state.scenario,null,{timeout:60000});
  await page.waitForTimeout(1200);
  check("no eager DEM or territory module",!requests.some(u=>/\/api\/terrain\/|\/app\/territory/.test(u)),requests.filter(u=>/\/api\/terrain\/|\/app\/territory/.test(u)));
  result.measurements.initial=await page.evaluate(()=>({marks:window.raiz.perf,hardwareConcurrency:navigator.hardwareConcurrency,devicePixelRatio,ua:navigator.userAgent}));
  await page.evaluate(async()=>{const m=(await import('/app/map.js')).getMap();m.jumpTo({center:[-79.62,-5.38],zoom:11.4,bearing:-30});});
  await page.click('#btn-3d');await page.waitForFunction(()=>window.raiz?.territory,null,{timeout:45000}).catch(async error=>{
    result.activation=await page.evaluate(()=>({toast:document.querySelector('#toast')?.textContent,state3d:window.raiz?.state.terrain3d}));throw error;
  });
  const ready=await stableTerrain();result.measurements.realTerrain=ready;check("stable real mountain terrain",ready.ok,ready);
  result.measurements.regionalCadence=await page.evaluate(async()=>{
    const m=(await import('/app/map.js')).getMap(),g=m.getCanvas().getContext('webgl2'),ext=g.getExtension('WEBGL_debug_renderer_info');
    const times=[];let last=null,renders=0;const count=()=>renders++;m.on('render',count);
    const bearing=m.getBearing();m.easeTo({bearing:bearing+12,duration:2000});
    await new Promise(resolve=>{const start=performance.now();const step=t=>{if(last!==null)times.push(t-last);last=t;if(performance.now()-start>=3000)return resolve();m.triggerRepaint();requestAnimationFrame(step);};requestAnimationFrame(step);});
    m.off('render',count);m.jumpTo({bearing});times.sort((a,b)=>a-b);
    return{samples:times.length,renderCallbacks:renders,medianFrameMs:times[Math.floor(times.length/2)],p95FrameMs:times[Math.floor(times.length*.95)],renderer:ext?g.getParameter(ext.UNMASKED_RENDERER_WEBGL):g.getParameter(g.RENDERER),pixelRatio:m.getCanvas().width/m.getContainer().clientWidth,heapUsedBytes:performance.memory?.usedJSHeapSize??null,scope:'Three-second regional camera turn; rAF cadence, not GPU completion timing or sustained-session certification.'};
  });
  check("default true vertical scale and preserved regional zoom",await page.evaluate(async()=>{const m=(await import('/app/map.js')).getMap();return m.getTerrain().exaggeration===1&&Math.abs(m.getZoom()-11.4)<.15;}));
  await mapCapture(OUT+'/mountains.png');
  const point=await page.request.get(BASE+'/api/terrain/point?lon=-79.62&lat=-5.38');
  const sample=await point.json();check("real source height with EGM2008 provenance",point.ok()&&sample.elevation_m>300&&sample.vertical_crs==='EPSG:3855',sample);
  const before=await page.evaluate(()=>window.raiz.territory.options.trees);
  await page.locator('[data-territory=trees]').uncheck();check("layer toggle",before&&!await page.evaluate(()=>window.raiz.territory.options.trees));
  await page.locator('[data-territory=trees]').check();
  await page.selectOption('#territory-weather','heavy');
  const effectsAvailable=await page.locator('[data-territory=animate]').isEnabled();
  if(effectsAvailable)await page.locator('[data-territory=animate]').check();
  await page.waitForTimeout(500);
  check("weather shader renders",await page.evaluate(()=>window.raiz.territory.stats.drawCalls>=1));
  if(effectsAvailable)await page.locator('[data-territory=animate]').uncheck();
  else check('software graphics keeps continuous effects off',!await page.locator('[data-territory=animate]').isChecked());
  await page.selectOption('#territory-weather','clear');
  await page.locator('[data-territory=inspect]').check();await page.mouse.click(650,430);
  await page.waitForFunction(()=>document.querySelector('#territory-inspect').textContent.includes('DSM elevation:')||document.querySelector('#territory-inspect').textContent.includes('Source elevation unknown'),null,{timeout:12000});
  check("coordinate inspection completes",await page.locator('#territory-inspect').innerText());
  await page.click('#btn-3d');
  check("return to 2D",await page.evaluate(async()=>!(await import('/app/map.js')).getMap().getTerrain()));
  await page.locator('#steps button').filter({hasText:'Zones'}).click();
  await page.evaluate(()=>window.raiz.ensureDraw());
  await page.selectOption('#vertex-count','4');await page.getByRole('button',{name:'Place the vertices',exact:true}).click();
  await page.evaluate(async()=>{const d=await import('/app/draw.js');d.placeVertices([[-80.632,-5.195],[-80.628,-5.195],[-80.628,-5.191],[-80.632,-5.191]]);});
  check("geographic polygon preserved",await page.evaluate(()=>window.raiz.state.drawn.at(-1)?.geometry.coordinates[0][0][0]===-80.632));
  for(const width of [1440,1024,768,390]){await page.setViewportSize({width,height:width===390?844:800});check('no overflow '+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
  check("no uncaught JavaScript errors",result.errors.length===0,result.errors);
  await page.close();
  const {checkRenderer}=await import('./territory_renderer_check.mjs');
  result.measurements.renderer=await checkRenderer(browser,BASE,OUT);
  check('synthetic renderer pixels and cleanup',result.measurements.renderer.ok,result.measurements.renderer);
}catch(error){result.failure=error.stack||String(error);check('browser flow completed',false,result.failure);}
finally{result.finishedUtc=new Date().toISOString();await writeFile(OUT+'/session.json',JSON.stringify(result,null,2));await browser.close();}
if(result.checks.some(c=>!c.ok))process.exitCode=1;
