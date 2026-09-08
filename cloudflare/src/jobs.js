import {utc,localDay,clock,addDays,startAt,occurrences,lessonText,scheduleText,dateLabel,courseFor,assignmentOrder,button,keyboard} from './domain.js';

export function enqueue(s,key,message,guard=null) {
  if(s.sent[key] || s.outbox.some(x=>x.key===key))return;
  s.outbox.push({key,...message,guard,attempts:0,retryAt:0});
}
export const lessonKey = (o,kind) => `lesson:${o.id}:${o.original_date}:${o.date}:${o.start_time.slice(0,5)}:${kind}`;
export const dueKey = (a,kind) => `assignment:${a.id}:${utc(a.due_at)}:${kind}`;
const WINDOWS=[[4320,'assignment_reminder_3d','3_days'],[1440,'assignment_reminder_24h','24_hours'],[360,'assignment_reminder_6h','6_hours'],[60,'assignment_reminder_1h','1_hour']];

export function scheduleJobs(s,now) {
  const today=localDay(now);
  // A bounded catch-up window handles delayed cron runs without replaying a day's reminders.
  const previous=Math.max(s.lastTick||now-60000,now-300000);
  for(const day of [today,addDays(today,1)])for(const o of occurrences(s,day)) {
    const start=startAt(o.date,o.start_time);
    for(const [minutes,field,kind] of [[60,'lesson_reminder_1h','1h'],[15,'lesson_reminder_15m','15m']]){
      const trigger=start-minutes*60000;
      if(s.settings[field]&&previous<trigger&&trigger<=now&&now<start)
        enqueue(s,lessonKey(o,kind),{text:`⏰ Через ${Math.ceil((start-now)/60000)} мин. пара!\n\n${lessonText(o)}`,course_id:o.course_id},
          {type:'lesson',id:o.id,date:o.date,original:o.original_date,start,field,expires:start});
    }
  }
  for(const a of s.assignments.filter(a=>a.is_active&&!a.is_submitted&&a.due_at)) {
    const due=utc(a.due_at), course=courseFor(s,a);
    if(due<=now) {
      enqueue(s,dueKey(a,'missed'),{text:`💀 Пропущен дедлайн\n\n${a.name}\n${course?.title||'Canvas'}\n📅 ${dateLabel(a.due_at)}\n❌ Не сдано`,course_id:course?.id},
        {type:'assignment',id:a.id,due,missed:true});
      continue;
    }
    for(const [minutes,field,kind] of WINDOWS){
      const trigger=due-minutes*60000;
      if(s.settings[field]&&previous<trigger&&trigger<=now)
        enqueue(s,dueKey(a,kind),{text:`🚨 Напоминание о задании\n\n${a.name}\n${course?.title||'Canvas'}\n📅 ${dateLabel(a.due_at)}\n⏳ Осталось ${Math.max(1,Math.ceil((due-now)/3600000))} ч.\n❌ Не сдано`,course_id:course?.id,markup:keyboard([[button('📄 Что нужно сделать',`assignment:${a.id}:0:0:0:active`)]])},
          {type:'assignment',id:a.id,due,field,expires:due});
    }
  }
  const active=s.assignments.filter(a=>a.is_active&&!a.is_submitted);
  const upcoming=active.filter(a=>a.due_at&&utc(a.due_at)>now).sort(assignmentOrder);
  for(const section of ['morning','evening']){
    const field=section+'_briefing_enabled',time=s.settings[section+'_briefing_time'];
    const trigger=startAt(today,time);
    if(s.settings[field]&&previous<trigger&&trigger<=now){
      const target=section==='morning'?today:addDays(today,1),os=occurrences(s,target);
      const dueToday=active.filter(a=>a.due_at&&localDay(utc(a.due_at))===today).length;
      let text=`${section==='morning'?'☀️ Доброе утро!':'🌙 Расписание на завтра'}\n\n${scheduleText(s,target)}\n\n📚 Активных заданий: ${active.length}`;
      if(section==='morning')text+=`\n🚨 Дедлайнов сегодня: ${dueToday}${upcoming[0]?`\nБлижайший: ${upcoming[0].name}\n${dateLabel(upcoming[0].due_at)}`:''}`;
      if(section==='evening'&&os[0]?.start_time<'09:00')text+='\n⚠️ Завтра ранняя пара — поставь будильник.';
      enqueue(s,`briefing:${section}:${today}`,{text},{field,expires:trigger+3600000});
    }
  }
  s.lastTick=now;
}

export function stillRelevant(s,item,now) {
  const g=item.guard;if(!g)return true;
  if(g.expires&&now>=g.expires)return false;
  if(g.field&&!s.settings[g.field])return false;
  if(g.type==='assignment'){
    const a=s.assignments.find(a=>a.id===g.id);
    return !!a&&a.is_active&&!a.is_submitted&&utc(a.due_at)===g.due;
  }
  if(g.type==='lesson')return occurrences(s,g.date).some(o=>o.id===g.id&&o.original_date===g.original&&startAt(o.date,o.start_time)===g.start);
  return true;
}

export async function canvasList(env,path) {
  const origin=new URL(env.CANVAS_BASE_URL).origin;
  let url=new URL(path,origin).href; const result=[];
  for(let page=0;url;page++){
    if(page>=8)throw new Error('Canvas pagination limit');
    if(new URL(url).origin!==origin)throw new Error('Unexpected Canvas origin');
    const response=await fetch(url,{headers:{Authorization:`Bearer ${env.CANVAS_ACCESS_TOKEN}`},redirect:'error',signal:AbortSignal.timeout(5000)});
    if(!response.ok){await response.body?.cancel();throw new Error(`Canvas HTTP ${response.status}`);}
    const data=await response.json();if(!Array.isArray(data))throw new Error('Invalid Canvas response');
    result.push(...data);
    url=(response.headers.get('Link')||'').match(/<([^>]+)>;\s*rel="next"/)?.[1]||null;
  }
  return result;
}

export function applyAssignments(s,cid,rows,now) {
  const seen=new Set();
  let nextID=Math.max(0,...s.assignments.map(a=>a.id))+1;
  for(const raw of rows){
    seen.add(raw.id);
    let a=s.assignments.find(a=>a.canvas_assignment_id===raw.id);
    const isNew=!a,oldDue=a?utc(a.due_at):null,wasSubmitted=!!a?.is_submitted;
    if(!a){a={id:nextID++,canvas_assignment_id:raw.id,canvas_course_id:cid,is_submitted:false};s.assignments.push(a);}
    for(const key of ['name','description','due_at','unlock_at','lock_at','html_url','points_possible'])a[key]=raw[key]??null;
    a.name ||= 'Без названия';a.is_active=1;a.submission_types=(raw.submission_types||[]).join(',');
    const sub=raw.submission;
    if(sub){
      a.is_submitted=!!sub.submitted_at||['submitted','graded','pending_review'].includes(sub.workflow_state);
      a.is_missing=!!sub.missing&&!a.is_submitted;a.is_late=!!sub.late;a.is_graded=sub.workflow_state==='graded';
      a.submitted_at=sub.submitted_at;
    }
    a.updated_at=new Date(now).toISOString();
    const course=courseFor(s,a),markup=keyboard([[button('📄 Что нужно сделать',`assignment:${a.id}:0:0:0:active`)]]);
    if(isNew)enqueue(s,`new:${a.id}`,{text:`🆕 Новое задание\n\n${a.name}\n${course?.title||'Canvas'}\n📅 ${dateLabel(a.due_at)}${a.due_at?'':'\nПреподаватель не указал срок.'}`,course_id:course?.id,markup});
    else if(oldDue!==utc(a.due_at))enqueue(s,`changed:${a.id}:${oldDue}:${utc(a.due_at)}:${now}`,{text:`⚠️ Дедлайн изменён\n\n${a.name}\nБыло: ${oldDue?dateLabel(new Date(oldDue).toISOString()):'не указан'}\nСтало: ${dateLabel(a.due_at)}`,markup});
    if(!isNew&&!wasSubmitted&&a.is_submitted)enqueue(s,`submitted:${a.id}:${a.submitted_at||now}`,{text:`✅ Задание сдано\n\n${a.name}\nНапоминания отключены.`});
  }
  // Only reached after every page for this course loaded successfully.
  for(const a of s.assignments)if(a.canvas_course_id===cid&&!seen.has(a.canvas_assignment_id))a.is_active=0;
}

export async function syncStep(s,env,now) {
  if(!s.sync.queue?.length) {
    if(!s.sync.requested&&now<(s.sync.next||0))return;
    const courses=await canvasList(env,'/api/v1/courses?enrollment_state=active&per_page=100');
    for(const raw of courses){
      const code=(raw.course_code||'').toUpperCase().split(/[\s-]+/).slice(0,3).join('-');
      const normalized=x=>(x||'').toLowerCase().replace(/[^a-z0-9]/g,'');
      const match=s.courses.find(c=>c.course_code===raw.course_code)||s.courses.find(c=>c.canvas_course_id===raw.id)||s.courses.find(c=>normalized(c.title)===normalized(raw.name))||s.courses.find(c=>c.course_code===code);
      if(match)match.canvas_course_id=raw.id;
    }
    s.sync.queue=courses.map(c=>c.id);s.sync.manual=!!s.sync.requested;s.sync.requested=false;s.sync.next=now+15*60000;
  }
  const cid=s.sync.queue[0];
  if(cid){
    const rows=await canvasList(env,`/api/v1/courses/${cid}/assignments?include%5B%5D=submission&per_page=100`);
    if(rows.some(a=>!a.submission))throw new Error('Canvas submission data unavailable');
    applyAssignments(s,cid,rows,now);s.sync.queue.shift();
  }
  s.sync.error=null;s.sync.errorSince=null;
  if(!s.sync.queue.length){
    s.sync.lastComplete=new Date(now).toISOString();
    if(s.sync.manual)enqueue(s,`sync:${now}`,{text:`✅ Canvas синхронизирован\nАктивных заданий: ${s.assignments.filter(a=>a.is_active&&!a.is_submitted).length}\nСдано: ${s.assignments.filter(a=>a.is_active&&a.is_submitted).length}\nВремя: ${clock(now)}`});
    s.sync.manual=false;
  }
}
