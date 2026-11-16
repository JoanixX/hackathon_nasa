// Actual map/water/3D/video browser checks with an explicitly labelled fixture scene, without AI calls.
// First: python tools/build_visual_fixture.py in the configured project environment.
import { readFile, writeFile, stat } from "node:fs/promises";
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const fixture=JSON.parse(await readFile(".local/qa/performance/fixture.json","utf8"));
const BASE=process.argv[2]||"http://localhost:8765", OUT=".local/qa/performance";
const browser=await chromium.launch({args:["--enable-unsafe-swiftshader","--ignore-gpu-blocklist","--use-gl=angle","--use-angle=swiftshader"]});
const page=await browser.newPage({viewport:{width:1280,height:800},acceptDownloads:true});
const result={checks:[],errors:[]};const check=(name,ok,detail)=>{result.checks.push({name,ok:!!ok,detail});console.log(ok?"PASS":"FAIL",name,detail||"");};
page.on("pageerror",e=>result.errors.push(String(e)));
await page.addInitScript(()=>localStorage.setItem("raiz-tour","done"));
try {
  await page.goto(BASE);await page.waitForFunction(()=>window.raiz?.state.scenario);
  await page.screenshot({ path: OUT + "/default-map-current.png" });
  check("default_legend_has_no_hidden_relief",!(await page.locator("#legend").innerText()).includes("Hillshade"));
  const block=page.locator("#panel-body h3").filter({hasText:"Surface water and ponding"}).locator("..");
  await block.getByRole("button",{name:"Load available dates",exact:true}).click();
  await page.waitForFunction(()=>window.raiz.state.dates.dswx?.length||window.raiz.state.layerErrors.dswx,null,{timeout:90000});
  const dates=await page.evaluate(()=>window.raiz.state.dates.dswx||[]);
  check("water_dates_available",dates.length>0,dates.length);
  if(dates.length){
    await page.getByLabel("Surface water and ponding (DSWx-HLS) date").selectOption(dates.includes("2026-02-27")?"2026-02-27":dates.at(-1));
    check("water_palette_opaque_and_dated",await page.evaluate(()=>import("/app/map.js").then(M=>M.getMap().getPaintProperty("img-dswx","raster-opacity")===1)));
    check("water_legend_visible",(await page.locator("#legend").innerText()).includes("Partial water, ponding"));
    await page.getByLabel("Surface water and ponding (DSWx-HLS) date").selectOption("");
    check("water_layer_removed",await page.evaluate(()=>import("/app/map.js").then(M=>!M.getMap().getSource("img-dswx"))));
  }
  await page.evaluate(f=>{const s=window.raiz.state;s.scenario=f.scenario;s.scenarioId=f.scenario.summary.scenario_id;s.dataset={sectors:f.scenario.sectors,dataset_version:f.scenario.summary.dataset_version};s.datasetKind="demo";s.plan=f.plan;s.scene=f.scene;window.raiz.drawZones();window.raiz.go("future");},fixture);
  check("fixture_label_preserved",(await page.locator("#panel-body").innerText()).includes("FIXTURE")||await page.evaluate(()=>window.raiz.state.scene.inference.mode==="fixture"));
  const views = [["before","twin-water"],["after","twin-trees"],["huayco_trees","twin-mud"],["huayco_none","twin-mud"]];
  if (process.env.RAIZ_VISUAL_QUICK) views.splice(2);
  for(const [view,source] of views){
    const info=await page.evaluate(async view=>{const P=await import("/app/panels.js");let status="";await P.showView(view,{set:message=>{status=message;}});const T=await import("/app/twin.js");const map=(await import("/app/map.js")).getMap();return {counts:{...T.counts},status,path:window.raiz.state.flowPath,center:map.getCenter().toArray(),pitch:map.getPitch()};},view);
    check("view_"+view,info.counts[source]>0,info.status);
    if(view==="before"||view==="after") { check("pitched_3d_"+view,info.pitch>=45,info.pitch); const box=fixture.scene.frame.bbox_lonlat;check("camera_on_scene_"+view,info.center[0]>=box[0]-.02&&info.center[0]<=box[2]+.02&&info.center[1]>=box[1]-.02&&info.center[1]<=box[3]+.02,info.center); }
    if(view==="huayco_trees")result.pathWithTrees=JSON.stringify(info.path?.geometry);
    if(view==="huayco_none")check("same_terrain_path_for_both_views",JSON.stringify(info.path?.geometry)===result.pathWithTrees);
    await page.waitForFunction(source => import("/app/map.js").then(M => M.getMap().isSourceLoaded(source)), source, { timeout: 15000 });
    await page.waitForTimeout(300);
    await page.screenshot({path:OUT+"/view-"+view+".png",timeout:45000});
  }
  if (!process.env.RAIZ_VISUAL_SKIP_VIDEO) {
  const downloadEvent=page.waitForEvent("download",{timeout:30000}).catch(() => null);
  await page.evaluate(()=>import("/app/panels.js").then(P=>P.showView("after",{set(){}},{record:true})));
  const download=await downloadEvent;
  if (download) await download.saveAs(OUT+"/after-fixture.webm");
  check("webm_download",download && (await stat(OUT+"/after-fixture.webm")).size>1000);
  }
  await page.getByRole("button", { name: "12 months", exact: true }).click();
  check("timeline_exits_twin_comparison", await page.evaluate(() => window.raiz.state.twinView === null));
  await page.evaluate(()=>window.raiz.go("compare"));
  check("twin_stopped_when_leaving_future",await page.evaluate(()=>import("/app/twin.js").then(T=>Object.values(T.counts).every(n=>n===0))));
  await page.waitForFunction(()=>window.Chart&&Object.keys(Chart.instances).length>0,null,{timeout:90000});
  for(let i=0;i<8;i++)await page.evaluate(()=>import("/app/panels.js").then(P=>P.setLayer("imerg",null)));
  check("charts_do_not_accumulate",await page.evaluate(()=>Object.keys(Chart.instances).length<=1));
  check("no_javascript_errors",result.errors.length===0,result.errors);
} finally {await writeFile(OUT+(process.env.RAIZ_VISUAL_SKIP_VIDEO?"/visual-views.json":process.env.RAIZ_VISUAL_QUICK?"/visual-check-quick.json":"/visual-check.json"),JSON.stringify(result,null,2));await browser.close();}
if(result.checks.some(c=>!c.ok))process.exitCode=1;
