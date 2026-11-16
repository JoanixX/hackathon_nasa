// Bounded WebGL2 additions inside MapLibre's existing context. No second scene engine or context.
import { mercator, localMatrix, geometryLines, usableGeometry, distanceM } from "./territory-geo.js";

const TREE_VS = `#version 300 es
precision highp float;
layout(location=0) in vec3 a_pos; layout(location=1) in vec3 a_normal; layout(location=2) in float a_part;
layout(location=3) in vec3 a_site; layout(location=4) in vec3 a_size;
uniform mat4 u_matrix; uniform vec3 u_sun; out vec3 v_color;
void main(){
  vec3 size=vec3(a_size.x,a_size.x,a_size.y);
  gl_Position=u_matrix*vec4(a_site+a_pos*size,1.0);
  float light=.42+.58*max(0.0,dot(normalize(a_normal/size),normalize(u_sun)));
  vec3 leaf=mix(vec3(.22,.36,.17),vec3(.39,.49,.23),a_size.z);
  v_color=mix(leaf,vec3(.34,.24,.15),a_part)*light;
}`;
const TREE_FS = `#version 300 es
precision highp float; in vec3 v_color; out vec4 color;
void main(){color=vec4(v_color,1.0);}`;
const WATER_VS = `#version 300 es
precision highp float; layout(location=0) in vec3 a_pos; layout(location=1) in vec3 a_uv;
uniform mat4 u_matrix; out vec3 v_uv;
void main(){v_uv=a_uv;gl_Position=u_matrix*vec4(a_pos,1.0);}`;
const WATER_FS = `#version 300 es
precision highp float; in vec3 v_uv; uniform float u_time; out vec4 color;
void main(){
  float wave=pow(.5+.5*sin(v_uv.x*.9-u_time*2.4*v_uv.z+sin(v_uv.y*4.0)),10.0);
  float alpha=(.18+wave*.36)*(1.0-smoothstep(.65,1.0,abs(v_uv.y)));
  color=vec4(mix(vec3(.20,.49,.66),vec3(.74,.88,.91),wave)*alpha,alpha);
}`;
const WEATHER_VS = `#version 300 es
precision highp float; out vec2 v_uv;
void main(){vec2 p=vec2(float((gl_VertexID<<1)&2),float(gl_VertexID&2));v_uv=p;gl_Position=vec4(p*2.0-1.0,0.0,1.0);}`;
const WEATHER_FS = `#version 300 es
precision highp float; in vec2 v_uv; uniform float u_time; uniform float u_rain; out vec4 color;
float hash(float p){return fract(sin(p*127.1)*43758.5453);}
void main(){
  float x=v_uv.x+v_uv.y*.10, col=floor(x*180.0), fall=fract(v_uv.y*5.0+u_time*(1.6+hash(col)) + hash(col)*7.0);
  float streak=(1.0-smoothstep(.03,.10,abs(fract(x*180.0)-.5)))*(1.0-smoothstep(.05,.25,fall));
  float alpha=min(.18,streak*.18*u_rain);
  color=vec4(vec3(.72,.82,.86)*alpha,alpha);
}`;
function program(gl, vs, fs) {
  const shaders = [], p = gl.createProgram();
  try {
    for (const [type, source] of [[gl.VERTEX_SHADER, vs], [gl.FRAGMENT_SHADER, fs]]) {
      const s = gl.createShader(type); shaders.push(s); gl.shaderSource(s, source); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      gl.attachShader(p, s);
    }
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
    return p;
  } catch (error) { gl.deleteProgram(p); throw error; }
  finally { for (const s of shaders) gl.deleteShader(s); }
}
function treeMesh() {
  const out = [];
  function tri(a, b, c, part) {
    const u = b.map((v, i) => v - a[i]), v = c.map((v, i) => v - a[i]);
    const n = [u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]], length = Math.hypot(...n) || 1;
    for (const p of [a, b, c]) out.push(...p, ...n.map(x => x / length), part);
  }
  const p = (a, z, r) => [Math.cos(a) * r, Math.sin(a) * r, z];
  for (let i = 0; i < 8; i++) {
    const a = i * Math.PI / 4, b = (i + 1) * Math.PI / 4;
    tri(p(a,0,.10),p(b,0,.10),p(a,.6,.075),1); tri(p(a,.6,.075),p(b,0,.10),p(b,.6,.075),1);
    for (let j = 0; j < 5; j++) {
      const t = -Math.PI/2 + j*Math.PI/5, u = t+Math.PI/5;
      const point=(angle,phi)=>p(angle,.69+Math.sin(phi)*.31,Math.cos(phi));
      tri(point(a,t),point(b,t),point(a,u),0); tri(point(a,u),point(b,t),point(b,u),0);
    }
  }
  return new Float32Array(out);
}

export class TerritoryLayer {
  id = "territory-detail"; type = "custom"; renderingMode = "3d";
  trees = []; waterways = []; origin = mercator([-80.63, -5.19]); sun = [-.5,-.5,.8];
  active = true; moving = true; rain = 0;
  stats = { trees: 0, waterSegments: 0, drawCalls: 0, gpuBytes: 0, renders: 0, cpuMs: 0 };
  constructor(onError) { this.onError = onError; }
  onAdd(map, gl) {
    this.map = map; this.gl = gl;
    if (!gl.createVertexArray || !gl.drawArraysInstanced) { this.onError("3D detail needs WebGL2; terrain and mapped layers remain available."); return; }
    try { this.allocate(); } catch (error) { this.release(); this.onError("3D detail could not start: " + error.message); }
  }
  allocate() {
    const g = this.gl;
    this.tp = program(g,TREE_VS,TREE_FS); this.wp = program(g,WATER_VS,WATER_FS); this.rp = program(g,WEATHER_VS,WEATHER_FS);
    this.tv = g.createVertexArray(); this.wv = g.createVertexArray(); this.rv = g.createVertexArray();
    this.mesh = g.createBuffer(); this.instances = g.createBuffer(); this.water = g.createBuffer();
    g.bindVertexArray(this.tv); g.bindBuffer(g.ARRAY_BUFFER,this.mesh);
    const mesh = treeMesh(); this.vertexCount = mesh.length/7; g.bufferData(g.ARRAY_BUFFER,mesh,g.STATIC_DRAW);
    for (const [i,n,offset] of [[0,3,0],[1,3,12],[2,1,24]]) { g.enableVertexAttribArray(i);g.vertexAttribPointer(i,n,g.FLOAT,false,28,offset); }
    g.bindBuffer(g.ARRAY_BUFFER,this.instances);
    for (const [i,offset] of [[3,0],[4,12]]) {g.enableVertexAttribArray(i);g.vertexAttribPointer(i,3,g.FLOAT,false,24,offset);g.vertexAttribDivisor(i,1);}
    g.bindVertexArray(this.wv);g.bindBuffer(g.ARRAY_BUFFER,this.water);
    for(const [i,offset] of [[0,0],[1,12]]) {g.enableVertexAttribArray(i);g.vertexAttribPointer(i,3,g.FLOAT,false,24,offset);}
    g.bindVertexArray(null);
    this.baseBytes=mesh.byteLength;this.ready=true;this.upload();
  }
  setData(trees, waterways, center) {
    this.trees=trees.slice(0,700);this.waterways=waterways.slice(0,128);this.origin=mercator(center);
    if(this.ready)this.upload();
  }
  upload() {
    const g=this.gl, o=this.origin, sample=p=>this.map.queryTerrainElevation(p);
    if(g.isContextLost())return;
    const instances=[];
    for(const t of this.trees) {
      const h=sample([t.lon,t.lat]);if(!Number.isFinite(h))continue;
      const m=mercator([t.lon,t.lat],h), ratio=m.unit/o.unit;
      instances.push((m.x-o.x)/o.unit,(m.y-o.y)/o.unit,m.z/o.unit,t.radius*ratio,t.height*ratio,t.shade);
    }
    const water=[];let segments=0;
    for(const f of this.waterways) {
      if(!usableGeometry(f.geometry))continue;
      const props=f.properties||{};
      if(!["river","canal"].includes(props.class)||[1,"1",true,"yes"].includes(props.intermittent))continue;
      for(const line of geometryLines(f.geometry))for(let i=1;i<line.length&&segments<192;i++) {
        let a=line[i-1],b=line[i],length=distanceM(a,b);
        if(length<1||length>600)continue;
        let ah=sample(a),bh=sample(b);if(!Number.isFinite(ah)||!Number.isFinite(bh))continue;
        if(ah<bh){[a,b]=[b,a];[ah,bh]=[bh,ah];}
        const A=mercator(a,ah+.2),B=mercator(b,bh+.2),dx=(B.x-A.x)/o.unit,dy=(B.y-A.y)/o.unit,l=Math.hypot(dx,dy);
        const half=Math.max(1,Math.min(8,Number(props.width)||4))/2, nx=-dy/l*half,ny=dx/l*half;
        const base=[(A.x-o.x)/o.unit,(A.y-o.y)/o.unit,A.z/o.unit],end=[(B.x-o.x)/o.unit,(B.y-o.y)/o.unit,B.z/o.unit];
        const speed=ah-bh>.5?1:0;
        const v=(p,side,u)=>[p[0]+nx*side,p[1]+ny*side,p[2],u,side,speed];
        water.push(...v(base,-1,0),...v(base,1,0),...v(end,-1,length),...v(end,-1,length),...v(base,1,0),...v(end,1,length));segments++;
      }
    }
    g.bindBuffer(g.ARRAY_BUFFER,this.instances);g.bufferData(g.ARRAY_BUFFER,new Float32Array(instances),g.DYNAMIC_DRAW);
    g.bindBuffer(g.ARRAY_BUFFER,this.water);g.bufferData(g.ARRAY_BUFFER,new Float32Array(water),g.DYNAMIC_DRAW);
    this.waterCount=water.length/6;
    Object.assign(this.stats,{trees:instances.length/6,waterSegments:segments,gpuBytes:this.baseBytes+(instances.length+water.length)*4});
    this.map.triggerRepaint();
  }
  render(gl, args) {
    if(!this.ready||!this.active)return;
    const started=performance.now();this.stats.drawCalls=0;
    if(!this.stats.trees&&!this.waterCount&&!this.rain){this.stats.renders++;this.stats.cpuMs=0;return;}
    const projection=args.defaultProjectionData;
    const worldMatrix=projection?.mainMatrix||projection?.projectionMatrix||args.modelViewProjectionMatrix;
    if(!worldMatrix||worldMatrix.length!==16){if(!this.warnedProjection){this.warnedProjection=true;this.onError("The map did not provide a compatible 3D projection matrix.");}return;}
    const matrix=localMatrix(worldMatrix,this.origin),time=this.moving?performance.now()/1000:0;
    gl.enable(gl.DEPTH_TEST);gl.depthMask(true);gl.disable(gl.CULL_FACE);gl.enable(gl.BLEND);gl.blendFunc(gl.ONE,gl.ONE_MINUS_SRC_ALPHA);
    if(this.stats.trees) {
      gl.useProgram(this.tp);gl.bindVertexArray(this.tv);gl.uniformMatrix4fv(gl.getUniformLocation(this.tp,"u_matrix"),false,matrix);
      gl.uniform3fv(gl.getUniformLocation(this.tp,"u_sun"),this.sun);gl.drawArraysInstanced(gl.TRIANGLES,0,this.vertexCount,this.stats.trees);this.stats.drawCalls++;
    }
    if(this.waterCount) {
      gl.depthMask(false);gl.useProgram(this.wp);gl.bindVertexArray(this.wv);gl.uniformMatrix4fv(gl.getUniformLocation(this.wp,"u_matrix"),false,matrix);
      gl.uniform1f(gl.getUniformLocation(this.wp,"u_time"),time);gl.drawArrays(gl.TRIANGLES,0,this.waterCount);this.stats.drawCalls++;
    }
    if(this.rain) {
      gl.disable(gl.DEPTH_TEST);gl.depthMask(false);gl.useProgram(this.rp);gl.bindVertexArray(this.rv);
      gl.uniform1f(gl.getUniformLocation(this.rp,"u_time"),time);gl.uniform1f(gl.getUniformLocation(this.rp,"u_rain"),this.rain);gl.drawArrays(gl.TRIANGLES,0,3);this.stats.drawCalls++;
    }
    gl.bindVertexArray(null);gl.depthMask(true);this.stats.renders++;this.stats.cpuMs=performance.now()-started;
  }
  release() {
    const g=this.gl;if(!g)return;
    for(const name of ["mesh","instances","water"]) {if(this[name])g.deleteBuffer(this[name]);this[name]=null;}
    for(const name of ["tp","wp","rp"]) {if(this[name])g.deleteProgram(this[name]);this[name]=null;}
    for(const name of ["tv","wv","rv"]) {if(this[name])g.deleteVertexArray(this[name]);this[name]=null;}
    this.ready=false;this.stats.gpuBytes=0;
  }
  onRemove() { this.release();this.trees=[];this.waterways=[]; }
}
