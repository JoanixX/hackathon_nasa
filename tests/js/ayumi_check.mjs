// Real map/UI checks; planning inputs are explicitly synthetic, with no model or Earthdata calls.
import {mkdir,writeFile} from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const hardware=process.env.TERRITORY_RENDERER==='hardware';
const base=process.argv[2]||'http://127.0.0.1:8765';
const out=`.local/qa/ayumi/${hardware?'hardware':'software'}`;
await mkdir(out,{recursive:true});
const result={startedUtc:new Date().toISOString(),renderer:hardware?'D3D11 hardware':'SwiftShader software',checks:[],errors:[],timings:{},scope:'Real map and DEM; synthetic planning fixture. No scientific, physical-AR or paid inference acceptance.'};
const check=(name,ok,detail)=>{result.checks.push({name,ok:!!ok,detail});console.log(ok?'PASS':'FAIL',name,detail??'');};
const browser=await chromium.launch({args:hardware?['--ignore-gpu-blocklist','--use-gl=angle','--use-angle=d3d11']:['--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--use-gl=angle','--use-angle=swiftshader']});
const page=await browser.newPage({viewport:{width:1440,height:900}});
page.on('pageerror',e=>result.errors.push(e.stack||String(e)));
await page.addInitScript(()=>localStorage.setItem('raiz-tour','done'));
async function findPanelButton(name){
  await page.waitForTimeout(250);
  for(let i=0;i<40;i++){
    const button=page.locator('#panel-body').getByRole('button',{name,exact:true});
    if(await button.count()&&await button.isVisible())return button;
    const next=page.locator('.panel-pages').getByRole('button',{name:'Next',exact:true});
    if(!await next.count()) {await page.waitForTimeout(50);continue;}
    if(await next.isDisabled())break;
    await next.click();await page.waitForTimeout(40);
  }
  throw new Error(`No visible panel action: ${name}`);
}
async function checkPages(step){
  await page.evaluate(s=>window.raiz.go(s),step);await page.waitForTimeout(150);
  let count=0;
  while(count++<40){
    const fit=await page.evaluate(()=>{
      const v=document.querySelector('.panel-viewport');
      return {height:v.clientHeight,scroll:v.scrollHeight,document:document.documentElement.scrollWidth<=innerWidth+1,
        text:document.querySelector('#panel-body').textContent.includes('could not be shown')};
    });
    check(`${step} page ${count} fits`,fit.height>=100&&fit.scroll<=fit.height+2&&fit.document&&!fit.text,fit);
    const next=page.locator('.panel-pages').getByRole('button',{name:'Next',exact:true});
    if(!await next.count()||await next.isDisabled())break;
    await next.click();await page.waitForTimeout(40);
  }
  return count;
}
try{
  const start=Date.now();await page.goto(base,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>window.raiz?.state.scenario&&document.querySelector('.panel-viewport')?.children.length,null,{timeout:90000});
  result.timings.interfaceReadyMs=Date.now()-start;
  check('Ayumi title and brand',(await page.title()).startsWith('Ayumi')&&(await page.locator('.brand-name').textContent())==='Ayumi');
  check('no persistent territorial settings',!await page.locator('.territory-controls').count()&&await page.locator('#btn-territory').isHidden());
  check('compact transparent key',await page.locator('#legend .key-chip').count()<=5&&await page.evaluate(()=>getComputedStyle(document.querySelector('#legend')).backgroundColor==='rgba(0, 0, 0, 0)'));
  await page.locator('#legend button').click();check('source key opens explicitly',await page.locator('dialog').isVisible());await page.getByRole('button',{name:'Close',exact:true}).click();
  await page.click('#btn-texture');check('images can be disabled',await page.locator('#btn-texture').getAttribute('aria-pressed')==='false');
  // Load a local fixture through the real API; manual mode is explicit and never a real NISAR result.
  const fixture=await page.evaluate(async()=>{
    const s=window.raiz.state.scenario,t=performance.now();
    const response=await fetch('/api/plans',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario_id:s.summary.scenario_id,dataset_version:s.summary.dataset_version,evidence_mode:'manual',budget_pen:18457})});
    if(!response.ok)throw new Error(await response.text());
    const plan=await response.json();Object.assign(window.raiz.state,{dataset:s,datasetKind:'demo',plan});
    return{ms:performance.now()-t,plan:plan.plan_version};
  });result.timings.fixturePlan=fixture;
  for(const step of ['explore','zones','evidence','compare','plan','future','report'])await checkPages(step);
  await page.evaluate(()=>window.raiz.go('report'));await page.waitForTimeout(100);
  await (await findPanelButton('Generate the draft')).click();
  await page.waitForFunction(()=>!!window.raiz.state.report,null,{timeout:10000});
  await page.waitForSelector('#panel-body .detail-launch',{timeout:10000});
  await (await findPanelButton('Open complete report')).click();
  const reportText=await page.locator('dialog').innerText();
  check('complete municipal report shown',['Coverage','Resources','Budget items','Plant benefits','Implementation','Risk register','Unpriced resources','Sources','Σ'].every(t=>reportText.includes(t)));
  check('official source links preserved',await page.locator('dialog a[href^="https://"]').count()>=7);
  await page.screenshot({path:out+'/municipal-report.png'});
  await page.getByRole('button',{name:'Close',exact:true}).click();
  await page.evaluate(()=>window.raiz.go('explore'));await page.waitForTimeout(100);
  await page.click('#btn-3d');await page.waitForFunction(()=>window.raiz.territory,null,{timeout:45000});
  check('3D controls remain outside steps',!await page.locator('.panel-body .territory-controls').count());
  await page.click('#btn-territory');
  check('3D controls open only on request',await page.locator('dialog .territory-controls').isVisible());
  check('no full-region destinations',!await page.getByRole('button',{name:'All Piura',exact:true}).count());
  await page.getByRole('button',{name:'Close',exact:true}).click();
  await page.waitForFunction(async()=>{const m=(await import('/app/map.js')).getMap(),h=m.queryTerrainElevation(m.getCenter());return m.isSourceLoaded('dem')&&m.areTilesLoaded()&&!m.isMoving()&&h>100&&Math.abs(m.getCenterElevation()-h)<50;},null,{timeout:90000});
  result.timings.terrain=await page.evaluate(async()=>{const m=(await import('/app/map.js')).getMap(),c=m.getCenter(),gl=m.getCanvas().getContext('webgl2'),e=gl.getExtension('WEBGL_debug_renderer_info');return{zoom:m.getZoom(),elevation:m.queryTerrainElevation(c),ratio:m.getPixelRatio(),renderer:e?gl.getParameter(e.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER)};});
  check('true vertical scale',await page.evaluate(async()=>((await import('/app/map.js')).getMap().getTerrain().exaggeration===1)));
  await page.screenshot({path:out+'/site-3d.png'});
  await page.click('#btn-3d');
  for(const width of [1024,768,390]){
    await page.setViewportSize({width,height:width===390?844:800});
    await checkPages('explore');
    await page.screenshot({path:out+`/explore-${width}.png`});
  }
  check('no uncaught JavaScript errors',result.errors.length===0,result.errors);
}catch(e){result.failure=e.stack||String(e);result.debug=await page.locator('#panel-body').innerText().catch(()=>null);await page.screenshot({path:out+'/failure.png'}).catch(()=>{});check('flow completed',false,[result.failure,result.debug]);}
finally{await writeFile(out+'/session.json',JSON.stringify(result,null,2));await browser.close();}
if(result.checks.some(c=>!c.ok))process.exitCode=1;
