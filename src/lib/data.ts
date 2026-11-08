import catalog from '../../content/catalog.json';
import settings from '../../content/albums.json';
import config from '../../site.json';
export const kind = config.kind;
export const publishing = process.env.PUBLISH === '1';
export const photos = catalog.filter((p:any) => publishing ? (p.included ?? p.approved) : p.included !== false);
if (publishing && !photos.length) throw new Error('影集没有入选照片，停止发布。');
export const mediaBase = (process.env.MEDIA_BASE || config.mediaBase).replace(/\/$/, '');
export function imageUrl(p:any, size=1600, format='jpg') {
  const sizes=p.variants.map((v:any)=>v.bound).sort((a:number,b:number)=>a-b);
  const bound=sizes.find((b:number)=>b>=size) || sizes.at(-1);
  const ext=p.formats && !p.formats.includes(format) ? p.formats[0] : format;
  return `${mediaBase}/${p.key}/${bound}.${ext}`;
}
export const albums = [...new Set(photos.map(p=>p.album))].map(id => {
  const meta=(settings as any)[id] || {};
  let items=photos.filter(p=>p.album===id);
  if(meta.photoIds) items.sort((a,b)=>{const rank=(p:any)=>{const n=meta.photoIds.indexOf(p.id);return n<0?999:n;};return rank(a)-rank(b);});
  const title=meta.title || (items[0].event==='杂' ? `日常 · ${items[0].date.slice(5).replace('-','.')}` : items[0].event);
  const cover=items.find(p=>p.id===meta.coverId)||items[0];
  return {id,title,description:meta.description||'',subtitle:meta.subtitle||items[0].date.replaceAll('-',' / '),color:meta.color||'#766653',photos:items,cover,date:items[0].date};
});
export const featured=kind==='photo' ? [...albums].sort((a,b)=>b.date.localeCompare(a.date)) : albums.sort((a,b)=>Object.keys(settings).indexOf(a.id)-Object.keys(settings).indexOf(b.id));
export const hero=photos[0];
