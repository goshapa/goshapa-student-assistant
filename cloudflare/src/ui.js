import {MAIN,DAYS,button as b,keyboard as kb,utc,localDay,clock,addDays,weekday,startAt,occurrences,lessonText,scheduleText,validDate,validTime,chunks,assignmentText,assignmentOrder,dateLabel,status,courseFor} from './domain.js';

const back=[b('⬅️ Настройки','settings:root')];
const cancel=kb([[b('✖️ Отмена','cancel')]]);
const nextID=items=>Math.max(0,...items.map(x=>x.id))+1;
const SLOT_FIELDS=['weekday','start_time','end_time','building','room','start_date','end_date'];
const PROMPTS={title:'Название предмета:',course_code:'Код курса, например COSC-1570-3T:',weekday:'День недели (1 — понедельник, 7 — воскресенье):',start_time:'Время начала (ЧЧ:ММ):',end_time:'Время окончания (ЧЧ:ММ):',building:'Корпус:',room:'Аудитория:',start_date:'Дата начала курса (ДД.ММ.ГГГГ):',end_date:'Дата окончания курса (ДД.ММ.ГГГГ):',date:'Дата занятия (ДД.ММ.ГГГГ):',new_date:'Новая дата (ДД.ММ.ГГГГ):',new_start_time:'Новое время начала (ЧЧ:ММ):',new_end_time:'Новое время окончания (ЧЧ:ММ):',new_building:'Новый корпус:',new_room:'Новая аудитория:',briefing_time:'Время сводки (ЧЧ:ММ):'};
const TOGGLES={lesson_reminder_1h:['За час','lesson'],lesson_reminder_15m:['За 15 минут','lesson'],assignment_reminder_3d:['За 3 дня','assignment'],assignment_reminder_24h:['За сутки','assignment'],assignment_reminder_6h:['За 6 часов','assignment'],assignment_reminder_1h:['За час','assignment'],morning_briefing_enabled:['Включена','morning'],evening_briefing_enabled:['Включена','evening']};

export function handleUpdate(s,update,now=Date.now()) {
  const outputs=[];
  const say=(text,markup=null,course=null)=>outputs.push({text,markup,course_id:course?.id||null});
  const today=localDay(now);
  const course=id=>s.courses.find(c=>c.id===Number(id));
  function courses(){say('🎓 Мои предметы',kb(s.courses.map(c=>[b(c.title,`course:${c.id}`)])));}
  function courseCard(id,next=false){
    const c=course(id); if(!c){say('Предмет не найден.');return;}
    const slots=s.lessons.filter(l=>l.course_id===c.id&&l.is_active);
    let nearest=null;
    for(let i=0;i<370&&!nearest;i++)nearest=occurrences(s,addDays(today,i)).find(o=>o.course_id===c.id&&startAt(o.date,o.start_time)>now);
    const text=`📚 ${c.title}\n🔖 ${c.course_code}\n\n${nearest?`Ближайшая пара: ${nearest.date}\n${lessonText(nearest)}`:'Нет предстоящих занятий.'}\n\n${slots.map(l=>`${DAYS[l.weekday]} ${l.start_time.slice(0,5)}–${l.end_time.slice(0,5)}\n📆 ${l.start_date} — ${l.end_date}`).join('\n')}`;
    say(text,kb([[b('📚 Assignments',`list:active:${id}:0`),b('⏰ Deadlines',`list:due:${id}:0`)],[b('🗓 Next lesson',`next:${id}`)],[b('⬅️ Предметы','courses')]]),c);
  }
  function list(mode='active',id=0,page=0){
    const c=course(id);
    let items=s.assignments.filter(a=>a.is_active&&(Number(id)===0||a.canvas_course_id===c?.canvas_course_id));
    items=items.filter(a=>mode==='submitted'?a.is_submitted:!a.is_submitted&&(mode!=='due'||a.due_at)).sort(assignmentOrder);
    if(mode==='submitted')items.reverse();
    page=Math.min(Math.max(0,Number(page)||0),Math.max(0,Math.ceil(items.length/6)-1));
    const selected=items.slice(page*6,page*6+6);
    const lines=[`${mode==='submitted'?'✅ Сданные задания':mode==='due'?'⏰ Дедлайны':'📚 Активные задания'}: ${items.length}`,`Страница ${page+1}/${Math.max(1,Math.ceil(items.length/6))}`,''];
    const rows=selected.map(a=>{
      lines.push(`${a.name.slice(0,140)}\n${dateLabel(a.due_at)}${a.due_at&&utc(a.due_at)<now?' · просрочено':''}`);
      return [b(a.name.slice(0,60),`assignment:${a.id}:0:${id}:${page}:${mode}`)];
    });
    const nav=[];
    if(page>0)nav.push(b('⬅️',`list:${mode}:${id}:${page-1}`));
    if((page+1)*6<items.length)nav.push(b('➡️',`list:${mode}:${id}:${page+1}`));
    if(nav.length)rows.push(nav);
    if(Number(id))rows.push([b('⬅️ Предмет',`course:${id}`)]);
    say(lines.join('\n\n'),kb(rows));
  }
  function assignment(id,page=0,cid=0,lp=0,mode='active'){
    const a=s.assignments.find(x=>x.id===Number(id)); if(!a){say('Задание не найдено.');return;}
    const pages=chunks(assignmentText(s,a)); page=Math.min(Math.max(0,Number(page)||0),pages.length-1);
    const nav=[];
    if(page)nav.push(b('⬅️',`assignment:${id}:${page-1}:${cid}:${lp}:${mode}`));
    if(page+1<pages.length)nav.push(b('Далее ➡️',`assignment:${id}:${page+1}:${cid}:${lp}:${mode}`));
    const rows=nav.length?[nav]:[];
    if(/^https?:\/\//.test(a.html_url||''))rows.push([{text:'🔗 Open Canvas',url:a.html_url}]);
    rows.push([b('⬅️ К списку',`list:${mode}:${cid}:${lp}`)]);
    say(`📄 ${page+1}/${pages.length}\n\n${pages[page]}`,kb(rows),page===0?courseFor(s,a):null);
  }
  function settings(section='root'){
    if(section==='root'){say('⚙️ Настройки',kb([['🔔 Пары','lesson'],['📚 Задания','assignment'],['☀️ Утренняя сводка','morning'],['🌙 Вечерняя сводка','evening'],['🎓 Canvas','canvas'],['📚 Управление расписанием','manage']].map(([label,key])=>[b(label,`settings:${key}`)])));return;}
    if(section==='manage'){say('📚 Управление расписанием',kb([[b('➕ Добавить пару','manage:add')],[b('✏️ Изменить пару','manage:edit')],[b('❌ Отменить пару','manage:cancel')],[b('🔄 Перенести пару','manage:move')],back]));return;}
    if(section==='canvas'){say(`🎓 Canvas\nПоследняя полная синхронизация: ${dateLabel(s.sync.lastComplete)}\n${s.sync.error?'⚠️ '+s.sync.error:'Подключён'}\nПроверка курсов — каждые 15 минут.`,kb([[b('🔄 Sync Canvas','sync')],back]));return;}
    const rows=Object.entries(TOGGLES).filter(([,v])=>v[1]===section).map(([key,[label]])=>[b(`${s.settings[key]?'✅':'⬜️'} ${label}`,`toggle:${key}`)]);
    let title=section==='lesson'?'🔔 Напоминания о парах':section==='assignment'?'📚 Напоминания о заданиях':`${section==='morning'?'☀️':'🌙'} Сводка: ${s.settings[section+'_briefing_time']}`;
    if(['morning','evening'].includes(section))rows.push([b('🕘 Изменить время',`time:${section}`)]);
    rows.push(back);say(title,kb(rows));
  }
  function prompt(){const f=s.fsm;if(f)say(PROMPTS[f.fields[f.step]],cancel);}
  function begin(action,lesson=null){
    const fields=action==='add'?['title','course_code',...SLOT_FIELDS]:action==='edit'?SLOT_FIELDS:action==='time'?['briefing_time']:['date',...(action==='move'?['new_date','new_start_time','new_end_time','new_building','new_room']:[])];
    s.fsm={action,lesson_id:lesson?.id,fields,step:0,data:{},expires:now+3600000};prompt();
  }
  function confirm(){
    const f=s.fsm;f.confirm=true;
    say(`Сохранить ${f.action==='cancel'?'отмену':f.action==='move'?'перенос':'изменения'}?\n\n${Object.entries(f.data).filter(([k])=>k!=='original_date').map(([k,v])=>`${PROMPTS[k]||k} ${v}`).join('\n')}`,kb([[b('✅ Да','confirm:yes'),b('❌ Нет','cancel')]]));
  }
  function finish(){
    const f=s.fsm;if(!f?.confirm){say('Этот диалог уже завершён.');return;}
    const d=f.data;
    if(f.action==='time')s.settings[f.section+'_briefing_time']=d.briefing_time;
    else if(f.action==='add'){
      let c=s.courses.find(c=>c.course_code===d.course_code);
      if(!c){c={id:nextID(s.courses),course_code:d.course_code,title:d.title};s.courses.push(c);}
      s.lessons.push({...d,id:nextID(s.lessons),course_id:c.id,is_active:1});
    }else if(f.action==='edit'){
      const l=s.lessons.find(l=>l.id===f.lesson_id);if(!l){say('Пара не найдена.');s.fsm=null;return;}Object.assign(l,d);
    }else{
      const l=s.lessons.find(l=>l.id===f.lesson_id);
      if(!l){say('Пара не найдена.');s.fsm=null;return;}
      const source=d.original_date||d.date;
      s.exceptions=s.exceptions.filter(e=>!(e.lesson_id===l.id&&e.date===source));
      s.exceptions.push({...d,id:nextID(s.exceptions),lesson_id:l.id,date:source,type:f.action==='cancel'?'cancelled':'rescheduled'});
    }
    s.fsm=null;say('✅ Сохранено.',MAIN);
  }
  function input(text){
    const f=s.fsm;if(!f)return;
    if(f.expires<now){s.fsm=null;say('Диалог истёк. Начни заново в настройках.');return;}
    if(f.confirm){say('Подтверди кнопкой «Да» или отмени.');return;}
    const key=f.fields[f.step];let value=text.trim();
    const lesson=s.lessons.find(l=>l.id===f.lesson_id);
    if(key.includes('date')){
      value=validDate(value);if(!value){say('Введите существующую дату как ДД.ММ.ГГГГ.');return;}
      if(key==='end_date'&&value<f.data.start_date){say('Окончание курса должно быть не раньше начала.');return;}
      if(key==='new_date'&&(!lesson||value<lesson.start_date||value>lesson.end_date)){say('Дата должна быть в пределах периода курса.');return;}
      if(key==='date'){
        const matched=occurrences(s,value).filter(o=>o.id===f.lesson_id);
        if(matched.length!==1){say(matched.length?'На эту дату несколько экземпляров пары. Выбери другую дату.':'На эту дату нет такой пары.');return;}
        f.data.original_date=matched[0].original_date;
      }
    }else if(key.includes('time')){
      if(!validTime(value)){say('Введите время в формате ЧЧ:ММ.');return;}
      if(key.endsWith('end_time')&&value<=(f.data.new_start_time||f.data.start_time)){say('Время окончания должно быть позже начала.');return;}
    }else if(key==='weekday'){
      if(!/^[1-7]$/.test(value)){say('Введи номер дня от 1 до 7.');return;}value=Number(value)-1;
    }else if(!value||value.length>200){say('Введите текст длиной от 1 до 200 символов.');return;}
    f.data[key]=value;f.step++;if(f.step===f.fields.length)confirm();else prompt();
  }
  const callback=update.callback_query;
  if(callback){
    let [action,...args]=(callback.data||'').split(':');
    if(action==='courses')courses();
    else if(action==='course')courseCard(args[0]);
    else if(action==='next')courseCard(args[0],true);
    else if(action==='list')list(...args);
    else if(action==='assignment')assignment(...args);
    else if(action==='settings')settings(args[0]);
    else if(action==='toggle'&&TOGGLES[args[0]]){s.settings[args[0]]=s.settings[args[0]]?0:1;settings(TOGGLES[args[0]][1]);}
    else if(action==='time'&&['morning','evening'].includes(args[0])){begin('time');s.fsm.section=args[0];}
    else if(action==='cancel'){s.fsm=null;say('Отменено.',MAIN);}
    else if(action==='confirm'&&args[0]==='yes')finish();
    else if(action==='manage'){
      if(args[0]==='add')begin('add');
      else if(['edit','cancel','move'].includes(args[0]))say('Выбери конкретную пару:',kb(s.lessons.filter(l=>l.is_active).map(l=>[b(`${l.title.slice(0,38)} · ${DAYS[l.weekday]} ${l.start_time.slice(0,5)}`,`slot:${args[0]}:${l.id}`)]).concat([back])));
    }else if(action==='slot'&&['edit','cancel','move'].includes(args[0])){
      const lesson=s.lessons.find(l=>l.id===Number(args[1]));if(lesson)begin(args[0],lesson);else say('Пара не найдена.');
    }else if(action==='sync'){s.sync.requested=true;say('🔄 Синхронизация запрошена. Результат придёт автоматически.');}
    else say('Эта кнопка устарела. Открой меню заново.',MAIN);
    return outputs;
  }
  const text=update.message?.text;
  if(!text){say('Отправь текст или выбери кнопку меню.');return outputs;}
  const command=text.split('@')[0];
  if(command==='/cancel'){s.fsm=null;say('Отменено.',MAIN);}
  else if(command==='/start'||command==='/help'){s.fsm=null;say('👋 Goshapa Student Assistant\n\nРасписание, Canvas и дедлайны.\n/today /tomorrow /week /assignments /deadlines /sync /settings\n/cancel — отменить ввод.',MAIN);}
  else if(['/today','📅 Сегодня','/tomorrow','➡️ Завтра'].includes(command)){
    const date=['/tomorrow','➡️ Завтра'].includes(command)?addDays(today,1):today;
    const os=occurrences(s,date);say(scheduleText(s,date),null,os.length===1?os[0].course:null);
  }else if(['/week','🗓 Неделя'].includes(command)){
    const monday=addDays(today,-weekday(today));
    for(const page of chunks(Array.from({length:7},(_,i)=>scheduleText(s,addDays(monday,i))).join('\n\n'),3500))say(page);
  }else if(['/assignments','📚 Assignments'].includes(command))list();
  else if(['/deadlines','⏰ Deadlines'].includes(command))list('due');
  else if(command==='✅ Submitted')list('submitted');
  else if(command==='🎓 Мои предметы')courses();
  else if(['/settings','⚙️ Настройки'].includes(command))settings();
  else if(['/sync','🔄 Sync Canvas'].includes(command)){s.sync.requested=true;say('🔄 Синхронизация запрошена. Результат придёт автоматически.');}
  else if(s.fsm)input(text);
  else say('Выбери действие в меню.',MAIN);
  return outputs;
}
