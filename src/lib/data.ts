import catalog from '../../content/catalog.json';
import config from '../../site.json';
export const kind = config.kind;
export const publishing = process.env.PUBLISH === '1';
export const photos = catalog.filter(p => !publishing || p.approved);
if (publishing && !photos.length) throw new Error('没有确认的照片。请先在选片页确认并导入清单。');
export const mediaBase = (process.env.MEDIA_BASE || config.mediaBase).replace(/\/$/, '');
export const imageUrl = (p: typeof photos[number], size = 1600, format = 'webp') => `${mediaBase}/${p.key}/${size}.${format}`;
const series: Record<string, {title: string, description: string}> = {
  land: {title:'草木之间', description:'花开、树影，以及远处的田野。'},
  water: {title:'沿着水走', description:'从湖岸到海边，留住片刻的平静。'},
  city: {title:'街巷片刻', description:'在熟悉与陌生的街道之间停一停。'},
};
export const albums = [...new Set(photos.map(p=>p.album))].map(id => {
  const items = photos.filter(p=>p.album === id);
  const title = kind === 'frame' ? series[id]?.title || id : (items[0].event === '杂' ? `${items[0].date.slice(5).replace('-', ' 月 ')} 日的日常` : items[0].event);
  return {id, title, description: kind === 'frame' ? series[id]?.description || '' : items[0].date.replaceAll('-', ' / '), photos:items, cover:kind === 'frame' && id === 'land' ? items[1] || items[0] : items[0]};
});
export const featured = kind === 'photo' ? [...albums].sort((a,b)=> (b.id === '20241228' ? 1 : a.id === '20241228' ? -1 : b.id.localeCompare(a.id))) : albums;
export const hero = kind === 'frame' ? photos[0] : photos.find(p=>p.title==='餐桌前的相聚') || photos[0];
