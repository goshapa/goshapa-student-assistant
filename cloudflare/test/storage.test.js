import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import worker from '../src/worker.js';

function database(){
  const sqlite=new DatabaseSync(':memory:');sqlite.exec(readFileSync(new URL('../schema.sql',import.meta.url),'utf8'));
  const state={courses:[],lessons:[],exceptions:[],assignments:[],settings:{},sent:{},outbox:[],updates:[],sync:{next:Date.now()+86400000}};
  sqlite.prepare('INSERT INTO bot_state VALUES(1,?)').run(JSON.stringify(state));
  const DB={prepare(sql){const q=sqlite.prepare(sql);let args=[];return {bind(...values){args=values;return this;},async first(){return q.get(...args)||null;},async run(){const r=q.run(...args);return {meta:{changes:r.changes}};}};}};
  return {sqlite,DB,read:()=>JSON.parse(sqlite.prepare('SELECT data FROM bot_state').get().data),write:s=>sqlite.prepare('UPDATE bot_state SET data=?').run(JSON.stringify(s))};
}
function request(id,text='/start'){return new Request('https://example.com/telegram',{method:'POST',headers:{'X-Telegram-Bot-Api-Secret-Token':'test'},body:JSON.stringify({update_id:id,message:{from:{id:1},chat:{id:1},text}})});}
const env=DB=>({DB,WEBHOOK_SECRET:'test',ENABLED:'true',OWNER_TELEGRAM_ID:'1',BOT_TOKEN:'test'});

test('webhook stores state, sends once and ignores Telegram redelivery',async()=>{
  const db=database(),old=globalThis.fetch;let sent=0;
  globalThis.fetch=async()=>{sent++;return Response.json({ok:true,result:{message_id:1}});};
  try{
    assert.equal((await worker.fetch(request(100),env(db.DB))).status,200);
    assert.equal(sent,1);assert.equal(db.read().outbox.length,0);
    assert.equal((await worker.fetch(request(100),env(db.DB))).status,200);
    assert.equal(sent,1);assert.deepEqual(db.read().updates,[100]);
  }finally{globalThis.fetch=old;db.sqlite.close();}
});
test('failed delivery stays pending and succeeds on retry',async()=>{
  const db=database(),old=globalThis.fetch;
  globalThis.fetch=async()=>Response.json({ok:false,error_code:429,parameters:{retry_after:1}});
  try{
    await worker.fetch(request(101),env(db.DB));let s=db.read();assert.equal(s.outbox.length,1);assert.equal(Object.keys(s.sent).length,0);
    s.outbox[0].retryAt=0;db.write(s);
    globalThis.fetch=async()=>Response.json({ok:true,result:{message_id:2}});
    await worker.fetch(request(101),env(db.DB));assert.equal(db.read().outbox.length,0);assert.ok(db.read().sent['update:101:0']);
  }finally{globalThis.fetch=old;db.sqlite.close();}
});
test('busy lease returns retry without consuming an update',async()=>{
  const db=database();db.sqlite.prepare('UPDATE bot_lock SET until_ms=?').run(Date.now()+120000);
  try{assert.equal((await worker.fetch(request(102),env(db.DB))).status,503);assert.deepEqual(db.read().updates,[]);}finally{db.sqlite.close();}
});
