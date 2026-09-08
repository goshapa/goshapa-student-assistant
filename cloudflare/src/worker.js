import {handleUpdate} from './ui.js';
import {chunks} from './domain.js';
import {enqueue,scheduleJobs,stillRelevant,syncStep} from './jobs.js';

export async function telegram(env,method,payload){
  const response=await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/${method}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:AbortSignal.timeout(5000)});
  const result=await response.json();
  if(!result.ok){const error=new Error(`Telegram ${result.error_code||response.status}`);error.retryAfter=result.parameters?.retry_after;throw error;}
  return result.result;
}

async function send(env,s,item){
  const c=s.courses.find(c=>c.id===item.course_id);
  const base={chat_id:Number(env.OWNER_TELEGRAM_ID),reply_markup:item.markup||undefined};
  if(c&&(c.banner_file_id||c.image_path)&&item.text.length<=1024){
    const photo=c.banner_file_id||(env.PUBLIC_URL&&`${env.PUBLIC_URL}/${c.image_path.replace(/^assets\//,'')}`);
    if(photo)try {
      const result=await telegram(env,'sendPhoto',{...base,photo,caption:item.text});
      if(result.photo?.length)c.banner_file_id=result.photo.at(-1).file_id;
      return;
    }catch(error){
      // Only media rejection is safe to retry as text; timeouts may already have delivered.
      if(error.message!=='Telegram 400')throw error;
    }
  }
  await telegram(env,'sendMessage',{...base,text:item.text,link_preview_options:{is_disabled:true}});
}

async function locked(env,action){
  const owner=crypto.randomUUID(),now=Date.now();
  const claimed=await env.DB.prepare('UPDATE bot_lock SET owner=?,until_ms=? WHERE id=1 AND until_ms<? RETURNING id').bind(owner,now+120000,now).first();
  if(!claimed)return false;
  try{
    const row=await env.DB.prepare('SELECT data FROM bot_state WHERE id=1').first();
    if(!row)throw new Error('State not initialized');
    const s=JSON.parse(row.data);
    s.outbox??=[];s.sent??={};s.updates??=[];s.sync??={};
    const save=async()=>{
      const saved=await env.DB.prepare('UPDATE bot_state SET data=? WHERE id=1 AND EXISTS(SELECT 1 FROM bot_lock WHERE id=1 AND owner=? AND until_ms>?)').bind(JSON.stringify(s),owner,Date.now()).run();
      if(!saved.meta.changes)throw new Error('State lease expired');
    };
    await action(s,save);
    await save();
    // Persist before dispatch; retain failures for the next cron tick.
    for(const item of [...s.outbox].slice(0,3)){
      if(!stillRelevant(s,item,Date.now())){s.outbox=s.outbox.filter(x=>x.key!==item.key);await save();continue;}
      if(item.retryAt>Date.now())continue;
      try{
        await send(env,s,item);s.sent[item.key]=Date.now();s.outbox=s.outbox.filter(x=>x.key!==item.key);
      }catch(error){item.attempts++;item.retryAt=Date.now()+Math.max(error.retryAfter||0,Math.min(3600,30*2**Math.min(item.attempts,7)))*1000;console.warn('Notification delivery deferred');}
      await save();
    }
    return true;
  }finally{await env.DB.prepare('UPDATE bot_lock SET owner=NULL,until_ms=0 WHERE id=1 AND owner=?').bind(owner).run();}
}

export default {
  async fetch(request,env){
    const url=new URL(request.url);
    if(request.method==='GET'&&url.pathname==='/health')return Response.json({ok:true,enabled:env.ENABLED==='true'});
    if(request.method!=='POST'||url.pathname!=='/telegram')return new Response('Not found',{status:404});
    if(!env.WEBHOOK_SECRET||request.headers.get('X-Telegram-Bot-Api-Secret-Token')!==env.WEBHOOK_SECRET)return new Response('Forbidden',{status:403});
    if(env.ENABLED!=='true')return new Response('Temporarily disabled',{status:503});
    let update;try{update=await request.json();}catch{return new Response('Bad request',{status:400});}
    const event=update.callback_query||update.message;
    const chat=update.callback_query?.message?.chat||update.message?.chat;
    if(!event||String(event.from?.id)!==String(env.OWNER_TELEGRAM_ID)||String(chat?.id)!==String(env.OWNER_TELEGRAM_ID))return new Response('OK');
    try{
      const done=await locked(env,async(s)=>{
        if(s.updates.includes(update.update_id))return;
        if(update.callback_query)try{await telegram(env,'answerCallbackQuery',{callback_query_id:update.callback_query.id});}catch{}
        const messages=handleUpdate(s,update);
        let i=0;
        for(const message of messages)for(const text of chunks(message.text,3500))enqueue(s,`update:${update.update_id}:${i++}`,{...message,text});
        s.updates.push(update.update_id);s.updates=s.updates.slice(-200);
      });
      return new Response(done?'OK':'Busy',{status:done?200:503});
    }catch{console.error('Webhook processing failed');return new Response('Retry',{status:503});}
  },
  async scheduled(event,env,ctx){
    if(env.ENABLED!=='true')return;
    ctx.waitUntil(locked(env,async(s)=>{
      const now=Date.now();
      try{await syncStep(s,env,now);}catch{
        s.sync.error='Не удалось обновить Canvas. Сохранённые данные доступны.';
        s.sync.errorSince??=now;
        enqueue(s,`sync-error:${s.sync.errorSince}`,{text:'⚠️ Canvas временно не обновляется. Расписание и сохранённые задания доступны. Повторю автоматически.'});
      }
      scheduleJobs(s,now);
      // Update replies no longer need permanent notification history after the dedup window.
      for(const [key,sent] of Object.entries(s.sent))if(key.startsWith('update:')&&now-sent>86400000)delete s.sent[key];
    }).catch(()=>console.error('Scheduled processing failed')));
  }
};
