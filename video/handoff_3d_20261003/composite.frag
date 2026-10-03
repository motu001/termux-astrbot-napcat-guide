#version 330
uniform sampler2D u_hdr;
uniform sampler2D u_overlay;
uniform vec2 u_res;
uniform float u_time;
uniform float u_sweep;
out vec4 fragColor;
vec3 aces(vec3 x){return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.,1.);}
void main(){
 vec2 uv=gl_FragCoord.xy/u_res;vec3 c=texture(u_hdr,uv).rgb;vec3 bloom=vec3(0);float wt=0.;
 for(int y=-2;y<=2;y++)for(int x=-2;x<=2;x++){float w=exp(-float(x*x+y*y)*.38);vec3 v=texture(u_hdr,uv+vec2(x,y)*4./u_res).rgb;bloom+=max(v-.65,0.)*w;wt+=w;}
 c+=bloom/wt*.24;
 float band=exp(-pow((uv.x+.15*uv.y-(u_sweep*1.8-.25))*8.,2.));
 if(u_sweep>0.&&u_sweep<1.)c+=vec3(.09,.17,.18)*band*sin(u_sweep*3.14159);
 c=pow(aces(c),vec3(1./2.2));
 vec4 o=texture(u_overlay,uv);c=mix(c,o.rgb,o.a);
 // Very fine deterministic dithering removes gradient banding without dirty texture.
 float n=fract(sin(dot(gl_FragCoord.xy,vec2(12.9898,78.233)))*43758.5453);
 c+=(n-.5)/800.;fragColor=vec4(c,1.);
}
