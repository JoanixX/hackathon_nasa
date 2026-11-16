// Five cold-browser/warm-server sessions, plus actual HTTP operations and a 15-second camera trace.
// No AI request, Earthdata download, VM/DNS mutation or claim of scientific validation.
import {mkdir,writeFile} from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.argv[2]||'http://127.0.0.1:8765',hardware=process.env.TERRITORY_RENDERER==='hardware';
const out=`.local/qa/ayumi/perf-${hardware?'hardware':'software'}`;await mkdir(out,{recursive:true});
const results={date:new Date().toISOString(),conditions:'1440×900, fresh browser contexts, warm API/source disk cache, unthrottled network; local host. Synthetic plan; actual map/DEM/zone HTTP. No model calls.',sessions:[],operations:{},errors:[]};
const browser=await chromium.launch({args:hardware?['--ignore-gpu-blocklist','--use-gl=angle','--use-angle=d3d11']:['--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--use-gl=angle','--use-angle=swiftshader']});
const summarize=xs=>{const a=xs.slice().sort((a,b)=>a-b);return{n:a.length,median:a[Math.floor(a.length/2)],p95:a[Math.min(a.length-1,Math.ceil(a.length*.95)-1)],min:a[0],max:a.at(-1)};};
try{
  for(let run=0;run<5;run++){
    const context=await browser.newContext({viewport:{width:1440,height:900}}),page=await context.newPage();
    await page.addInitScript(()=>localStorage.setItem('raiz-tour','done'));
    page.on('pageerror',e=>results.errors.push(String(e)));
    const requests=[];page.on('request',r=>requests.push(r.url()));
    const start=Date.now();await page.goto(base,{waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>window.raiz?.state.scenario&&document.querySelector('.panel-viewport')?.children.length,null,{timeout:90000});
    const row={run:run+1,interfaceReadyMs:Date.now()-start};
    row.resources=await page.evaluate(()=>performance.getEntriesByType('resource').map(r=>({name:r.name.replace(location.origin,''),duration:r.duration,bytes:r.transferSize})).sort((a,b)=>b.duration-a.duration).slice(0,10));
    await page.waitForFunction(async()=>{const m=(await import('/app/map.js')).getMap();return m.areTilesLoaded()&&!m.isMoving();},null,{timeout:90000});
    row.mapSettledMs=Date.now()-start;row.defaultHeavyRequests=requests.filter(u=>/\/api\/(terrain|nisar|landscape)|\/app\/territory/.test(u)).length;
    if(run===0){
      results.operations=await page.evaluate(async()=>{
        const s=window.raiz.state.scenario,result={plans:[],reports:[],planReuse:[],navigation:[]};
        const call=async(path,body)=>{const t=performance.now(),r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const b=await r.json();if(!r.ok)throw new Error(JSON.stringify(b));return{ms:performance.now()-t,body:b};};
        let plan;
        for(let i=0;i<9;i++){
          const body={scenario_id:s.summary.scenario_id,dataset_version:s.summary.dataset_version,budget_pen:19000+i,evidence_mode:'manual'};
          const p=await call('/api/plans',body);plan=p.body;result.plans.push(p.ms);
          result.planReuse.push((await call('/api/plans',body)).ms);
          result.reports.push((await call('/api/reports/preview',{plan_version:plan.plan_version})).ms);
        }
        Object.assign(window.raiz.state,{dataset:s,datasetKind:'demo',plan});
        for(let i=0;i<21;i++){
          const step=['plan','future','report'][i%3],t=performance.now();window.raiz.go(step);
          await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
          result.navigation.push(performance.now()-t);
        }
        window.raiz.go('explore');return result;
      });
      await page.click('#btn-3d');const terrainStart=Date.now();
      await page.waitForFunction(async()=>{const m=(await import('/app/map.js')).getMap(),h=m.queryTerrainElevation(m.getCenter());return m.getTerrain()&&m.isSourceLoaded('dem')&&m.areTilesLoaded()&&!m.isMoving()&&h>100&&Math.abs(m.getCenterElevation()-h)<50;},null,{timeout:90000});
      row.terrainReadyMs=Date.now()-terrainStart;
      row.camera=await page.evaluate(async()=>{
        const m=(await import('/app/map.js')).getMap(),gl=m.getCanvas().getContext('webgl2'),e=gl.getExtension('WEBGL_debug_renderer_info'),times=[];
        const heapBefore=performance.memory?.usedJSHeapSize??null;
        let last=null,renders=0,lastRender=null;const renderIntervals=[];const onRender=()=>{const t=performance.now();if(lastRender!==null)renderIntervals.push(t-lastRender);lastRender=t;renders++;};m.on('render',onRender);
        const b=m.getBearing();m.easeTo({bearing:b+70,duration:15000});
        await new Promise(resolve=>{const start=performance.now();function tick(t){if(last!==null)times.push(t-last);last=t;if(t-start>=15000)return resolve();requestAnimationFrame(tick);}requestAnimationFrame(tick);});
        m.stop();m.off('render',onRender);m.jumpTo({bearing:b});
        return{frameIntervals:times,renderIntervals,renders,renderer:e?gl.getParameter(e.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),pixelRatio:m.getPixelRatio(),heapBefore,heapAfter:performance.memory?.usedJSHeapSize??null};
      });
    }
    results.sessions.push(row);console.log(JSON.stringify({...row,camera:row.camera?{renders:row.camera.renders,frames:row.camera.frameIntervals.length}:undefined}));
    await context.close();
  }
  results.summary={interfaceReadyMs:summarize(results.sessions.map(s=>s.interfaceReadyMs)),mapSettledMs:summarize(results.sessions.map(s=>s.mapSettledMs)),...Object.fromEntries(Object.entries(results.operations).map(([k,v])=>[k,summarize(v)]))};
  const camera=results.sessions.find(s=>s.camera)?.camera;if(camera)results.summary.cameraFrameMs=summarize(camera.frameIntervals);
  if(camera)results.summary.mapRenderMs=summarize(camera.renderIntervals);
}catch(e){results.failure=e.stack||String(e);process.exitCode=1;}
finally{await writeFile(out+'/session.json',JSON.stringify(results,null,2));await browser.close();console.log(JSON.stringify(results.summary??results.failure));}
