#version 330
uniform vec2 u_res;
uniform float u_time;
uniform int u_scene;
uniform vec3 u_phone;
uniform vec3 u_phone_rot;
uniform float u_ps;
uniform vec3 u_agent;
uniform float u_as;
uniform vec3 u_human;
uniform float u_hs;
uniform vec3 u_docs[3];
uniform float u_ds[3];
uniform vec3 u_boxes[4];
uniform float u_bs[4];
uniform vec3 u_camera;
uniform float u_scan;
uniform float u_focus;
uniform sampler2D u_screen;
uniform sampler2D u_prev_screen;
uniform float u_ui_mix;
uniform sampler2D u_doc;
uniform sampler2D u_modules;
out vec4 fragColor;
const vec3 teal=vec3(.16,.86,.75);
const vec3 gold=vec3(1.,.58,.23);
mat3 rx(float a){float c=cos(a),s=sin(a);return mat3(1,0,0,0,c,s,0,-s,c);}
mat3 ry(float a){float c=cos(a),s=sin(a);return mat3(c,0,-s,0,1,0,s,0,c);}
mat3 rz(float a){float c=cos(a),s=sin(a);return mat3(c,s,0,-s,c,0,0,0,1);}
float rounded2(vec2 p,vec2 b,float r){vec2 q=abs(p)-b+r;return length(max(q,0.))+min(max(q.x,q.y),0.)-r;}
float slab(vec3 p,vec3 b,float r,float bevel){vec2 q=vec2(rounded2(p.xy,b.xy,r),abs(p.z)-b.z);return length(max(q,0.))+min(max(q.x,q.y),0.)-bevel;}
float box(vec3 p,vec3 b,float r){vec3 q=abs(p)-b+r;return length(max(q,0.))+min(max(q.x,max(q.y,q.z)),0.)-r;}
float torus(vec3 p,vec2 tr){return length(vec2(length(p.xz)-tr.x,p.y))-tr.y;}
float capsule(vec3 p,vec3 a,vec3 b,float r){vec3 pa=p-a,ba=b-a;return length(pa-ba*clamp(dot(pa,ba)/dot(ba,ba),0.,1.))-r;}
vec2 un(vec2 a,vec2 b){return a.x<b.x?a:b;}
vec3 phonePoint(vec3 p){return transpose(ry(u_phone_rot.y)*rx(u_phone_rot.x)*rz(u_phone_rot.z))*(p-u_phone)/u_ps;}
vec3 docPoint(vec3 p,int i){float a=.07*sin(u_time*.65+float(i)*1.9);return transpose(ry(-.15+float(i)*.13+a)*rz(.04*sin(u_time*.5+float(i))))*(p-u_docs[i])/max(u_ds[i],.001);}
vec3 modPoint(vec3 p,int i){return transpose(ry(.17+sin(u_time*.45+float(i))*.12)*rx(-.09))*(p-u_boxes[i])/max(u_bs[i],.001);}
vec2 map(vec3 p){
 vec2 d=vec2(p.y+2.35,5.);
 vec3 q=phonePoint(p);
 d=un(d,vec2(slab(q,vec3(.86,1.57,.11),.18,.025)*u_ps,1.));
 d=un(d,vec2(slab(q-vec3(0,0,.142),vec3(.795,1.49,.01),.15,.008)*u_ps,2.));
 d=un(d,vec2(slab(q-vec3(0,1.345,.163),vec3(.175,.046,.013),.04,.008)*u_ps,1.));
 d=un(d,vec2(slab(q-vec3(.89,.47,0),vec3(.014,.21,.024),.012,.004)*u_ps,1.));
 if(u_as>.02){
  vec3 a=(p-u_agent)/u_as;
  d=un(d,vec2((length(a)-.49)*u_as,3.));
  d=un(d,vec2(torus(rx(.85)*rz(u_time*.22)*a,vec2(.68,.017))*u_as,4.));
  d=un(d,vec2(torus(rx(-.50)*ry(u_time*.3)*a,vec2(.77,.011))*u_as,4.));
 }
 if(u_hs>.02){
  vec3 h=(p-u_human)/u_hs;
  d=un(d,vec2(slab(h,vec3(.45,.55,.065),.30,.024)*u_hs,6.));
  d=un(d,vec2((length(h-vec3(0,.15,.085))-.145)*u_hs,7.));
  d=un(d,vec2(slab(h-vec3(0,-.17,.084),vec3(.21,.13,.055),.11,.025)*u_hs,7.));
 }
 for(int i=0;i<3;i++){if(u_ds[i]>.02){q=docPoint(p,i);d=un(d,vec2(slab(q,vec3(.47,.61,.026),.055,.012)*u_ds[i],10.+float(i)));}}
 for(int i=0;i<4;i++){if(u_bs[i]>.02){q=modPoint(p,i);d=un(d,vec2(box(q,vec3(.40,.40,.20),.08)*u_bs[i],20.+float(i)));}}
 return d;
}
vec3 normal(vec3 p){vec2 e=vec2(.001,0);return normalize(vec3(map(p+e.xyy).x-map(p-e.xyy).x,map(p+e.yxy).x-map(p-e.yxy).x,map(p+e.yyx).x-map(p-e.yyx).x));}
float shadow(vec3 p,vec3 rd){float t=.05,k=1.;for(int i=0;i<18;i++){float h=map(p+rd*t).x;k=min(k,10.*h/t);t+=clamp(h,.06,.5);if(h<.001||t>6.)break;}return clamp(k,.12,1.);}
float ao(vec3 p,vec3 n){float v=0.;for(int i=1;i<=3;i++){float h=float(i)*.08;v+=(h-map(p+n*h).x)/float(i);}return clamp(1.-v*1.5,.35,1.);}
vec3 env(vec3 r){
 vec3 c=mix(vec3(.012,.025,.04),vec3(.12,.19,.25),smoothstep(-.4,1.,r.y));
 c+=vec3(.9,1.,1.1)*pow(max(dot(r,normalize(vec3(-.7,.9,1.5))),0.),24.)*3.;
 c+=teal*pow(max(dot(r,normalize(vec3(1.,.4,.4))),0.),20.)*1.25;
 c+=gold*pow(max(dot(r,normalize(vec3(-1.,.15,-.5))),0.),28.)*.9;
 float strip=pow(max(1.-abs(r.x*.6+r.z*.2+.06),0.),110.)*smoothstep(.15,.55,r.y);
 c+=vec3(1.,.96,.85)*strip*1.5;return c;
}
vec3 light(vec3 p,vec3 n,vec3 v,vec3 base,float metal,float rough,vec3 lp,vec3 lc){
 vec3 l=normalize(lp-p),h=normalize(v+l);float nl=max(dot(n,l),0.),nv=max(dot(n,v),.001),nh=max(dot(n,h),0.),vh=max(dot(v,h),0.);
 float a=rough*rough,a2=a*a;float den=nh*nh*(a2-1.)+1.;float D=a2/max(3.14159*den*den,.00001);
 float k=(rough+1.)*(rough+1.)/8.;float G=nl/(nl*(1.-k)+k)*nv/(nv*(1.-k)+k);
 vec3 F0=mix(vec3(.04),base,metal);vec3 F=F0+(1.-F0)*pow(1.-vh,5.);
 return ((1.-F)*(1.-metal)*base/3.14159+D*G*F/max(4.*nv*max(nl,.001),.001))*lc*nl;
}
vec3 shade(vec3 p,vec3 n,vec3 rd,float id){
 vec3 v=-rd,base=vec3(.25),em=vec3(0);float metal=.6,rough=.28;
 if(id<1.5){base=vec3(.22,.29,.34);metal=.9;rough=.26;}
 else if(id<2.5){
  vec3 q=phonePoint(p);vec2 uv=vec2(q.x/1.59+.5,q.y/2.98+.5);
  vec3 tx=mix(texture(u_prev_screen,clamp(uv,0.,1.)).rgb,texture(u_screen,clamp(uv,0.,1.)).rgb,u_ui_mix);
  base=tx*.10;metal=.18;rough=.18;em=pow(tx,vec3(2.2))*1.35;
  float scan=exp(-pow((q.y-u_scan)*18.,2.));if(u_scene==6)em+=teal*scan*.9;
 }
 else if(id<3.5){
  vec3 a=normalize(p-u_agent);float longitude=atan(a.z,a.x),latitude=acos(clamp(a.y,-1.,1.));
  float net=pow(max(cos(longitude*8.+u_time*.55),0.),40.)+pow(max(cos(latitude*10.-u_time*.25),0.),40.);
  base=vec3(.025,.15,.13);metal=.8;rough=.23;
  em=teal*(net*.9+pow(1.-max(dot(n,v),0.),3.)*.35);
  if(u_scene==5)em=mix(em,gold*(net+.15),.65);
 }
 else if(id<4.5){base=teal;metal=.4;rough=.22;em=teal*3.2;}
 else if(id<5.5){base=vec3(.010,.023,.032);metal=.35;rough=.58;}
 else if(id<6.5){base=vec3(.63,.32,.11);metal=.85;rough=.29;}
 else if(id<7.5){base=vec3(.94,.70,.36);metal=.8;rough=.22;em=gold*.07;}
 else if(id<15.){
  int i=int(id)-10;vec3 q=docPoint(p,i);vec2 uv=vec2(q.x/.94+.5,q.y/1.22+.5);
  vec3 tx=texture(u_doc,vec2((clamp(uv.x,0.,1.)+float(i))/3.,clamp(uv.y,0.,1.))).rgb;
  base=vec3(.73,.8,.77);metal=.15;rough=.23;
  if(q.z>.016){base=pow(tx,vec3(2.2))*.85;em=pow(tx,vec3(2.2))*.10;}
 }
 else {
  int i=int(id)-20;vec3 q=modPoint(p,i);vec2 uv=vec2(q.x/.8+.5,q.y/.8+.5);
  base=mix(vec3(.08,.24,.25),vec3(.38,.21,.10),float(i==0));metal=.75;rough=.23;
  if(q.z>.12){vec3 tx=texture(u_modules,vec2((clamp(uv.x,0.,1.)+float(i))/4.,clamp(uv.y,0.,1.))).rgb;base=pow(tx,vec3(2.2))*.35;em=pow(tx,vec3(2.2))*.7;}
 }
 vec3 col=base*.18;
 col+=light(p,n,v,base,metal,rough,vec3(-3,5,5),vec3(7.,7.6,8.));
 col+=light(p,n,v,base,metal,rough,vec3(3,1,3),teal*2.);
 col+=light(p,n,v,base,metal,rough,vec3(-4,1,-2),gold*3.5);
 vec3 f0=mix(vec3(.04),base,metal);float nv=max(dot(n,v),0.);
 col+=env(reflect(rd,n))*(f0+(1.-f0)*pow(1.-nv,5.))*.7;
 col*=ao(p,n);
 if(abs(id-5.)<.1){
  vec2 delta=p.xz-u_phone.xz-vec2(.18,.35);float sh=1.-.44*exp(-pow(delta.x/1.20,2.)-pow(delta.y/.62,2.));col*=sh;
  vec2 c=(p.xz-u_agent.xz);col+=teal*exp(-dot(c,c)*1.5)*.10*u_as;
  vec2 a=(p.xz-u_phone.xz);col+=vec3(.025,.035,.04)*exp(-dot(a,a)*.5);
 }
 return col+em;
}
vec2 project(vec3 p,vec3 ro,vec3 f,vec3 right,vec3 up){vec3 q=p-ro;float z=max(dot(q,f),.01);return vec2(dot(q,right),dot(q,up))*.94/z;}
float segdist(vec2 p,vec2 a,vec2 b){vec2 ab=b-a;return length(p-a-ab*clamp(dot(p-a,ab)/max(dot(ab,ab),.000001),0.,1.));}
void main(){
 vec2 uv=(gl_FragCoord.xy-vec2(u_res.x*.5,u_res.y*.505))/u_res.y;
 vec3 ro=u_camera;vec3 f=normalize(vec3(0,-.02,0)-ro),right=normalize(cross(f,vec3(0,1,0))),up=cross(right,f);
 vec3 rd=normalize(f*.94+right*uv.x+up*uv.y);
 float vign=1.-.35*length(uv);vec3 col=mix(vec3(.006,.014,.024),vec3(.011,.030,.040),.5+.5*uv.y)*vign;
 col+=teal*.014*exp(-length(uv-vec2(.20,.03))*5.);
 col+=gold*.012*exp(-length(uv-vec2(-.25,-.05))*5.);
 float t=.1;vec2 hit;bool found=false;
 for(int i=0;i<76;i++){vec3 p=ro+rd*t;hit=map(p);if(hit.x<.0012){found=true;break;}t+=hit.x*.85;if(t>17.)break;}
 if(found){vec3 p=ro+rd*t;vec3 n=normal(p);col=shade(p,n,rd,hit.y);float fog=1.-exp(-t*t*.0013);col=mix(col,vec3(.008,.02,.03),fog);}
 // Authored connection paths: light particles carry the handoff, not simulated evidence.
 if(u_scene>=2&&u_scene<=6){
  vec3 a=u_phone+vec3(.42,-.15,.30),b=u_agent;vec3 bend=(a+b)*.5+vec3(0,.75,.15);
  vec3 ac=(u_scene==5)?gold:teal;
  vec2 prev=project(a,ro,f,right,up);float dist=10.;
  for(int j=1;j<=18;j++){float k=float(j)/18.;vec3 pt=mix(mix(a,bend,k),mix(bend,b,k),k);vec2 q=project(pt,ro,f,right,up);dist=min(dist,segdist(uv,prev,q));prev=q;}
  col+=ac*(.045*exp(-dist*100.)+.12*exp(-dist*550.));
  for(int j=0;j<5;j++){float k=fract(u_time*.16+float(j)*.21);if(u_scene==5)k=1.-k;vec3 pt=mix(mix(a,bend,k),mix(bend,b,k),k);float z=length(uv-project(pt,ro,f,right,up));col+=ac*exp(-z*z*180000.)*1.5;}
 }
 fragColor=vec4(col,1.);
}
