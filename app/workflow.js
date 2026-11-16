// Bounded workflow pages and explicit detail dialogs. No scrolling is required inside a step.
import {el} from "./dom.js";
let dialog=null;
const positions=new Map();
export function partitionCards(heights,budget) {
  if(!Number.isFinite(budget)||budget<48)throw new RangeError("A page needs at least 48 pixels.");
  const pages=[];let page=[],used=0;
  heights.forEach((height,index)=>{
    const h=Number.isFinite(height)&&height>=0?Math.min(height,budget):48;
    if(page.length&&used+h>budget){pages.push(page);page=[];used=0;}
    page.push(index);used+=h;
  });
  if(page.length)pages.push(page);
  return pages;
}
export function closeDialog(){dialog?.close();}
export function showDialog(title,content){
  closeDialog();const previous=document.activeElement;
  const d=dialog=el("dialog",{class:"detail-dialog","aria-label":title});
  const body=el("div",{class:"detail-body"},...([content].flat()));
  d.append(el("div",{class:"detail-head"},el("h2",{},title),el("button",{type:"button",class:"btn",onclick:()=>d.close()},"Close")),body);
  d.addEventListener("click",e=>{if(e.target===d)d.close();});
  d.addEventListener("close",()=>{d.remove();if(dialog===d)dialog=null;if(previous?.isConnected)previous.focus();});
  document.body.append(d);d.showModal();
  requestAnimationFrame(()=>window.dispatchEvent(new Event("resize")));
  return d;
}
export function mountPanel(host,content,key){
  host._panelDispose?.();closeDialog();
  const view=el("div",{class:"panel-viewport"}),nav=el("div",{class:"panel-pages","aria-label":"Step pages"});
  host.replaceChildren(view,nav);let pages=[],cards=[],scheduled=null,disposed=false;
  const mutation=new MutationObserver(()=>schedule());
  const resize=new ResizeObserver(()=>schedule());
  const measure=()=>{
    if(disposed||host.clientHeight<100)return;
    mutation.disconnect();
    const budget=Math.max(48,host.clientHeight-58);
    const stage=el("div",{class:"panel-measure"});host.append(stage);
    let expanded=null;
    cards=content.map((node,i)=>{
      const wasExpanded=view.contains(node)&&(node.matches?.("details[open]")||node.querySelector?.("details[open]"));
      stage.append(node);const h=node.getBoundingClientRect().height+18;
      if(h<=budget)return{node,height:h};
      const heading=node.querySelector?.("h2,h3")?.textContent?.trim()||({explore:"Map options",zones:"Zone details",plan:"Planting settings",future:"Future view",report:"Full report"}[key]||"Details");
      const title=`Open ${heading.toLowerCase()}`;
      if(wasExpanded)expanded={heading,node};
      const button=el("button",{class:"btn detail-launch",type:"button","aria-label":title,onclick:()=>showDialog(heading,node)},title);
      return{node:button,height:58};
    });
    stage.remove();pages=partitionCards(cards.map(c=>c.height),budget);render();
    if(expanded)showDialog(expanded.heading,expanded.node);
  };
  function render(){
    mutation.disconnect();const index=Math.min(positions.get(key)||0,Math.max(0,pages.length-1));positions.set(key,index);
    view.replaceChildren(...(pages[index]||[]).map(i=>cards[i].node));
    nav.replaceChildren();
    if(pages.length>1)nav.append(
      el("button",{class:"btn quiet",type:"button",disabled:index===0,onclick:()=>{positions.set(key,index-1);render();}},"Previous"),
      el("span",{class:"note",role:"status"},`${index+1} / ${pages.length}`),
      el("button",{class:"btn",type:"button",disabled:index===pages.length-1,onclick:()=>{positions.set(key,index+1);render();}},"Next"));
    mutation.observe(view,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:["open","hidden"]});
  }
  function schedule(){if(!scheduled&&!disposed)scheduled=requestAnimationFrame(()=>{scheduled=null;measure();});}
  resize.observe(host);schedule();
  host._panelDispose=()=>{disposed=true;resize.disconnect();mutation.disconnect();if(scheduled)cancelAnimationFrame(scheduled);};
}
export function compactKey(host,items,entries){
  host.replaceChildren(...entries.slice(0,4).map(([label,color])=>el("span",{class:"key-chip"},el("i",{style:`background:${color}`,"aria-hidden":"true"}),label)),
    el("button",{class:"key-chip key-more",type:"button",onclick:()=>showDialog("Map key and sources",el("div",{class:"source-key"},...items))},"Key & sources"));
}
