import { createRemoteJWKSet, jwtVerify } from 'jose';
import config from '../site.json';
import catalog from '../content/catalog.json';

type Env = { ASSETS: { fetch(request: Request): Promise<Response> }; PHOTOS: any; ACCESS_TEAM_DOMAIN?: string; ACCESS_AUD?: string };
const allowed = new Set(catalog.filter((p:any)=>p.included ?? p.approved).flatMap((p:any) => p.variants.flatMap((v:any) => (p.formats || ['jpg','webp']).map((format:string) => `${p.key}/${v.bound}.${format}`))));
const keysets = new Map<string, ReturnType<typeof createRemoteJWKSet>>();
const privateSite = config.kind === 'photo';

export async function authorized(request: Request, env: Env) {
  if (!env.ACCESS_TEAM_DOMAIN || !env.ACCESS_AUD || !/^[a-z0-9-]+\.cloudflareaccess\.com$/.test(env.ACCESS_TEAM_DOMAIN)) return false;
  const token = request.headers.get('Cf-Access-Jwt-Assertion');
  if (!token) return false;
  const issuer = `https://${env.ACCESS_TEAM_DOMAIN}`;
  let keys = keysets.get(issuer);
  if (!keys) { keys = createRemoteJWKSet(new URL(`${issuer}/cdn-cgi/access/certs`)); keysets.set(issuer,keys); }
  try {
    const {payload} = await jwtVerify(token,keys,{issuer,audience:env.ACCESS_AUD,algorithms:['RS256'],requiredClaims:['exp','iat','sub']});
    return typeof payload.email === 'string' && payload.email.length > 0;
  } catch { return false; }
}

function secure(response: Response) {
  const headers = new Headers(response.headers);
  headers.set('X-Content-Type-Options','nosniff');
  headers.set('Referrer-Policy','same-origin');
  headers.set('X-Frame-Options','DENY');
  headers.set('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'");
  if(privateSite) { headers.set('Cache-Control','private, no-store');headers.set('X-Robots-Tag','noindex, nofollow, noarchive'); }
  return new Response(response.body,{status:response.status,headers});
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if(privateSite && !(await authorized(request,env))) return secure(new Response('请通过家庭影集的登录入口访问。',{status:401}));
    if(!['GET','HEAD'].includes(request.method)) return secure(new Response('Method not allowed',{status:405,headers:{Allow:'GET, HEAD'}}));
    const url = new URL(request.url);
    if(['/review','/api/','/library-media/'].some(prefix=>url.pathname.startsWith(prefix))) return secure(new Response('Not found',{status:404}));
    if(url.pathname.startsWith('/media/')) {
      const key = url.pathname.slice(7);
      if(!allowed.has(key)) return secure(new Response('Not found',{status:404}));
      const object = request.method==='HEAD' ? await env.PHOTOS.head(key) : await env.PHOTOS.get(key);
      if(!object) return secure(new Response('Not found',{status:404}));
      const headers = new Headers();
      headers.set('Content-Type',key.endsWith('.webp')?'image/webp':'image/jpeg');
      headers.set('ETag',object.httpEtag);
      headers.set('Cache-Control',privateSite?'private, no-store':'public, max-age=31536000, immutable');
      if(request.headers.get('If-None-Match')===object.httpEtag) return secure(new Response(null,{status:304,headers}));
      headers.set('Content-Length',String(object.size));
      return secure(new Response(request.method==='HEAD'?null:object.body,{headers}));
    }
    return secure(await env.ASSETS.fetch(request));
  }
};
