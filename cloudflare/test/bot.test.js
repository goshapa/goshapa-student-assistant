import test from 'node:test';
import assert from 'node:assert/strict';
import {occurrences,localDay,clock,utc,descriptionText,validDate,chunks} from '../src/domain.js';
import {handleUpdate} from '../src/ui.js';
import {applyAssignments,scheduleJobs,stillRelevant,syncStep,enqueue,dueKey} from '../src/jobs.js';
import worker from '../src/worker.js';

function state(){return {courses:[{id:1,title:'Math',course_code:'COSC-1570-3T',canvas_course_id:10}],
  lessons:[{id:1,course_id:1,title:'Math',weekday:0,start_time:'16:30:00',end_time:'18:50:00',building:'North',room:'305',start_date:'2026-08-24',end_date:'2026-12-18',is_active:1}],
  exceptions:[],assignments:[],settings:{lesson_reminder_1h:1,lesson_reminder_15m:1,assignment_reminder_3d:1,assignment_reminder_24h:1,assignment_reminder_6h:1,assignment_reminder_1h:1,morning_briefing_enabled:1,evening_briefing_enabled:1,morning_briefing_time:'09:00',evening_briefing_time:'21:00'},
  sent:{},outbox:[],updates:[],sync:{next:0},fsm:null};}
const message=text=>({message:{text}});
const callback=data=>({callback_query:{data}});
test('SQLite UTC and Tashkent dates are consistent',()=>{
  assert.equal(utc('2026-09-15 18:59:00.000000'),utc('2026-09-15T23:59:00+05:00'));
  assert.equal(localDay(utc('2026-09-15T21:00:00Z')),'2026-09-16');
  assert.equal(clock(utc('2026-09-15T18:59:00Z')),'23:59');
});
test('date validation rejects impossible dates',()=>{assert.equal(validDate('31.02.2026'),null);assert.equal(validDate('14.09.2026'),'2026-09-14');});
test('move removes original, adds destination, cancellation suppresses both',()=>{
  const s=state();s.exceptions.push({lesson_id:1,date:'2026-09-14',new_date:'2026-09-16',type:'rescheduled',new_start_time:'11:00'});
  assert.equal(occurrences(s,'2026-09-14').length,0);
  assert.equal(occurrences(s,'2026-09-16')[0].start_time,'11:00');
  assert.equal(occurrences(s,'2026-09-21').length,1);
  assert.equal(occurrences(s,'2026-12-21').length,0);
  s.exceptions[0].type='cancelled';assert.equal(occurrences(s,'2026-09-16').length,0);
});
test('description preserves instructions and safe materials',()=>{
  const text=descriptionText('<p>A &amp; B</p><li>PDF</li><a href="/files/42">Rubric</a><script>evil()</script>','https://example.com');
  assert.match(text,/A & B/);assert.match(text,/• PDF/);assert.match(text,/https:\/\/example.com\/files\/42/);assert.doesNotMatch(text,/evil/);
  const long='😀'.repeat(5000);assert.equal(chunks(long).join(''),long);assert.ok(chunks(long).every(p=>p.length<=850));
});
test('assignment update preserves submission on unknown data and soft deletes only its course',()=>{
  const s=state();s.assignments=[{id:1,canvas_assignment_id:20,canvas_course_id:10,is_submitted:true,is_active:1,due_at:'2026-09-15 18:59:00'}, {id:2,canvas_assignment_id:21,canvas_course_id:11,is_active:1}];
  applyAssignments(s,10,[{id:20,name:'Essay',due_at:'2026-09-15T18:59:00Z'}],1);
  assert.equal(s.assignments[0].is_submitted,true);assert.equal(s.outbox.length,0);assert.equal(s.assignments[1].is_active,1);
  applyAssignments(s,10,[],2);assert.equal(s.assignments[0].is_active,0);assert.equal(s.assignments[1].is_active,1);
});
test('failed Canvas page leaves assignments unchanged',async()=>{
  const s=state();s.sync.queue=[10];s.assignments=[{id:1,is_active:1,canvas_course_id:10}];
  const original=globalThis.fetch;globalThis.fetch=async()=>new Response('unavailable',{status:503});
  try{await assert.rejects(syncStep(s,{CANVAS_BASE_URL:'https://example.com',CANVAS_ACCESS_TOKEN:'test'},1));assert.equal(s.assignments[0].is_active,1);assert.deepEqual(s.sync.queue,[10]);}finally{globalThis.fetch=original;}
});
test('deadline revision permits new reminders and cancels pending obsolete ones',()=>{
  const s=state(),a={id:1,is_active:1,is_submitted:false,due_at:'2026-09-15T18:59:00Z'};s.assignments=[a];
  const now=utc(a.due_at)-3600000;s.lastTick=now-60000;scheduleJobs(s,now);
  const item=s.outbox.find(i=>i.key===dueKey(a,'1_hour'));assert.ok(item);assert.equal(stillRelevant(s,item,now),true);
  a.is_submitted=true;assert.equal(stillRelevant(s,item,now),false);a.is_submitted=false;
  a.due_at='2026-09-16T18:59:00Z';assert.equal(stillRelevant(s,item,now),false);
  s.lastTick=utc(a.due_at)-3660000;scheduleJobs(s,utc(a.due_at)-3600000);assert.ok(s.outbox.some(i=>i.key===dueKey(a,'1_hour')));
});
test('outbox deduplicates repeated scheduling and setting toggles invalidate jobs',()=>{
  const s=state();const now=utc('2026-09-14T10:30:00Z');s.lastTick=now-60000;
  scheduleJobs(s,now);const count=s.outbox.length;scheduleJobs(s,now);assert.equal(s.outbox.length,count);
  const item=s.outbox.find(i=>i.guard?.type==='lesson');assert.ok(item);s.settings.lesson_reminder_1h=0;assert.equal(stillRelevant(s,item,now),false);
});
test('menus paginate and course filter does not leak other courses',()=>{
  const s=state();s.assignments=Array.from({length:17},(_,i)=>({id:i+1,name:'Essay '+i,is_active:1,canvas_course_id:i<8?10:11}));
  const all=handleUpdate(s,message('📚 Assignments'))[0];assert.match(all.text,/17/);assert.equal(all.markup.inline_keyboard.length,7);
  const only=handleUpdate(s,callback('list:active:1:0'))[0];assert.match(only.text,/задания: 8/);
});
test('add wizard validates time range and persists a new slot only after confirmation',()=>{
  const s=state();handleUpdate(s,callback('manage:add'));
  for(const text of ['New','TEST-1','2','14:00','13:00'])handleUpdate(s,message(text));
  assert.equal(s.fsm.step,4);assert.equal(s.lessons.length,1);
  for(const text of ['15:00','West','202','01.09.2026','01.12.2026'])handleUpdate(s,message(text));
  assert.equal(s.fsm.confirm,true);handleUpdate(s,callback('confirm:yes'));assert.equal(s.lessons.length,2);assert.equal(s.lessons[1].weekday,1);
});
test('move wizard stores new date and can cancel from actual destination',()=>{
  const s=state();handleUpdate(s,callback('slot:move:1'));
  for(const text of ['14.09.2026','16.09.2026','11:00','12:00','West','202'])handleUpdate(s,message(text));
  handleUpdate(s,callback('confirm:yes'));assert.equal(occurrences(s,'2026-09-16').length,1);
  handleUpdate(s,callback('slot:cancel:1'));handleUpdate(s,message('16.09.2026'));handleUpdate(s,callback('confirm:yes'));
  assert.equal(occurrences(s,'2026-09-16').length,0);
});
test('webhook rejects forged requests before database access',async()=>{
  const env={WEBHOOK_SECRET:'test',ENABLED:'true',OWNER_TELEGRAM_ID:'1'};
  const request=new Request('https://example.com/telegram',{method:'POST',body:'{}'});
  assert.equal((await worker.fetch(request,env)).status,403);
  const outsider=new Request('https://example.com/telegram',{method:'POST',headers:{'X-Telegram-Bot-Api-Secret-Token':'test'},body:JSON.stringify({message:{from:{id:2},chat:{id:2},text:'/today'}})});
  assert.equal((await worker.fetch(outsider,env)).status,200);
});
