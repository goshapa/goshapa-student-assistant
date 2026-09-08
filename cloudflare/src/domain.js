export const DAYS = ['Понедельник','Вторник','Среда','Четверг','Пятница','Суббота','Воскресенье'];
export const MAIN = {keyboard:[['📅 Сегодня','➡️ Завтра'],['🗓 Неделя','📚 Assignments'],['⏰ Deadlines','✅ Submitted'],['⚙️ Настройки','🔄 Sync Canvas'],['🎓 Мои предметы']].map(r=>r.map(text=>({text}))),resize_keyboard:true};
export const button = (text, callback_data) => ({text, callback_data});
export const keyboard = rows => ({inline_keyboard: rows});
export const utc = value => value ? Date.parse(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : value.replace(' ','T')+'Z') : null;
export const localDay = (now=Date.now()) => new Date(now+5*3600000).toISOString().slice(0,10);
export const clock = (now=Date.now()) => new Date(now+5*3600000).toISOString().slice(11,16);
export const addDays = (date, days) => new Date(Date.parse(date+'T00:00:00Z')+days*86400000).toISOString().slice(0,10);
export const weekday = date => (new Date(date+'T12:00:00Z').getUTCDay()+6)%7;
export const startAt = (date,time) => Date.parse(`${date}T${time.slice(0,5)}:00+05:00`);
export const dateLabel = value => value ? `${localDay(utc(value)).split('-').reverse().join('.')} ${clock(utc(value))}` : 'Не указан';
export const status = a => a.is_late ? '⚠️ Сдано поздно' : a.is_submitted ? '✅ Сдано' : a.is_missing ? '🚨 Пропущено' : '❌ Не сдано';
export const courseFor = (s,a) => s.courses.find(c=>c.canvas_course_id===a.canvas_course_id);
export function occurrences(s,date) {
  const result=[];
  for(const lesson of s.lessons) {
    if(!lesson.is_active || date<lesson.start_date || date>lesson.end_date) continue;
    const exceptions=s.exceptions.filter(e=>e.lesson_id===lesson.id);
    const original=exceptions.find(e=>e.date===date);
    const sources=exceptions.filter(e=>e.type==='rescheduled' && (e.new_date||e.date)===date && e.date>=lesson.start_date && e.date<=lesson.end_date);
    if(weekday(date)===lesson.weekday && !original) sources.push(null);
    for(const e of sources) result.push({...lesson,date,original_date:e?.date||date,
      start_time:e?.new_start_time||lesson.start_time,end_time:e?.new_end_time||lesson.end_time,
      building:e?.new_building||lesson.building,room:e?.new_room||lesson.room,
      course:s.courses.find(c=>c.id===lesson.course_id)});
  }
  return result.sort((a,b)=>a.start_time.localeCompare(b.start_time));
}
export function lessonText(o) { return `📚 ${o.course?.title||o.title}\n🕒 ${o.start_time.slice(0,5)}–${o.end_time.slice(0,5)}\n📍 ${o.building} — ${o.room}`; }
export function scheduleText(s,date) {
  const items=occurrences(s,date);
  return `📅 ${DAYS[weekday(date)]}, ${date.split('-').reverse().join('.')}\n\n${items.length?items.map(lessonText).join('\n\n'):'😎 Занятий нет.'}`;
}
export function validDate(text) {
  const m=/^(\d{2})\.(\d{2})\.(\d{4})$/.exec(text);
  if(!m) return null;
  const date=`${m[3]}-${m[2]}-${m[1]}`;
  const ms=Date.parse(date+'T00:00:00Z');
  return Number.isFinite(ms)&&new Date(ms).toISOString().slice(0,10)===date?date:null;
}
export const validTime = text => /^([01]\d|2[0-3]):[0-5]\d$/.test(text);
export function chunks(text,size=850) {
  const result=[]; let page='';
  for(const char of text) {if(page.length+char.length>size){result.push(page);page='';} page+=char;}
  if(page) result.push(page);
  return result.length?result:[''];
}
export function descriptionText(html='',base='') {
  let source=html.replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi,'');
  const links=[];
  source=source.replace(/<a\b[^>]*href=["']([^"']+)["'][^>]*>/gi,(_,link)=>{try {const url=new URL(link,base);if(['http:','https:'].includes(url.protocol))links.push(url.href);}catch{} return '';});
  source=source.replace(/<(img|iframe|audio|video)\b[^>]*>/gi,'\n[Медиа — открой в Canvas]\n')
    .replace(/<li\b[^>]*>/gi,'\n• ').replace(/<\/?(p|div|br|ul|ol|h[1-6]|tr)\b[^>]*>/gi,'\n')
    .replace(/<[^>]*>/g,'');
  source=source.replace(/&(#x[0-9a-f]+|#\d+|amp|lt|gt|quot|apos|nbsp);/gi,(all,key)=>{
    if(key[0]==='#'){const n=key[1].toLowerCase()==='x'?parseInt(key.slice(2),16):Number(key.slice(1));return n>0&&n<=0x10ffff?String.fromCodePoint(n):all;}
    return {amp:'&',lt:'<',gt:'>',quot:'"',apos:"'",nbsp:' '}[key.toLowerCase()];
  }).replace(/[ \t]+/g,' ').replace(/\n\s*\n+/g,'\n\n').trim();
  return source+(links.length?'\n\nМатериалы:\n'+[...new Set(links)].join('\n'):'');
}
export function assignmentText(s,a) {
  const formats={online_upload:'загрузить файл',online_text_entry:'ввести текст',online_url:'отправить ссылку',discussion_topic:'ответить в обсуждении',online_quiz:'пройти тест',on_paper:'сдать вне Canvas',none:'отправка в Canvas не предусмотрена',external_tool:'через внешний сервис',media_recording:'аудио/видео',student_annotation:'аннотировать документ'};
  return `📄 ${a.name}\n📚 ${courseFor(s,a)?.title||'Canvas'}\n📅 ${dateLabel(a.due_at)} (Ташкент)\n${status(a)}\n\n📤 Как сдать: ${(a.submission_types||'').split(',').filter(Boolean).map(k=>formats[k]||k).join(', ')||'не указано'}\n\n📝 Что нужно сделать:\n${descriptionText(a.description||'',a.html_url)||'Преподаватель не добавил описание. Проверь материалы в Canvas.'}\n\nИсходные инструкции без перевода. Вложения не разобраны.`;
}
export const assignmentOrder = (a,b) => (utc(a.due_at)??Infinity)-(utc(b.due_at)??Infinity);
