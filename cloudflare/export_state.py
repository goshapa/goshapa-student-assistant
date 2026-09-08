"""Export a consistent private SQLite snapshot for D1; never commit the output."""
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / 'private'
OUT.mkdir(exist_ok=True)

def millis(value):
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)

def export():
    with sqlite3.connect(f'file:{ROOT / "database/student.db"}?mode=ro', uri=True) as source:
        db = sqlite3.connect(':memory:')
        source.backup(db)
    db.row_factory = sqlite3.Row
    rows = lambda table: [dict(row) for row in db.execute(f'SELECT * FROM {table}')]
    state = dict(courses=rows('courses'), lessons=rows('lessons'), exceptions=rows('lesson_exceptions'),
                 assignments=rows('assignments'), settings=rows('settings')[0], sent={}, outbox=[], updates=[], fsm=None,
                 sync={'lastComplete': rows('settings')[0]['last_canvas_sync_at'], 'requested': False, 'next': 0},
                 lastTick=int(datetime.now(timezone.utc).timestamp()*1000))
    assignments = {a['id']: a for a in state['assignments']}
    lessons = {l['id']: l for l in state['lessons']}
    for h in rows('notification_history'):
        kind, key = h['notification_type'], None
        if h['assignment_id'] in assignments:
            a = assignments[h['assignment_id']]
            if kind == 'new_assignment': key = f"new:{a['id']}"
            elif kind in ['3_days','24_hours','6_hours','1_hour','missed']:
                key = f"assignment:{a['id']}:{millis(a['due_at'])}:{kind}"
        elif kind in ['morning_briefing','evening_briefing']:
            key = f"briefing:{kind.split('_')[0]}:{h['ref_date']}"
        elif kind in ['lesson_1h','lesson_15m'] and h['lesson_id'] in lessons:
            l=lessons[h['lesson_id']]
            exception=next((e for e in state['exceptions'] if e['lesson_id']==l['id'] and (e.get('new_date') or e['date'])==h['ref_date']),None)
            time=(exception or {}).get('new_start_time') or l['start_time']
            original=(exception or {}).get('date') or h['ref_date']
            key=f"lesson:{l['id']}:{original}:{h['ref_date']}:{time[:5]}:{kind.split('_')[1]}"
        if key: state['sent'][key]=millis(h['sent_at']) or 1
    db.close()
    text=json.dumps(state,ensure_ascii=False,separators=(',',':'))
    (OUT/'state.json').write_text(text,encoding='utf-8')
    # D1 limits each SQL statement to 100 KB. Stage chunks and publish the row last.
    sql = ["CREATE TABLE IF NOT EXISTS bot_import (id INTEGER PRIMARY KEY, data TEXT NOT NULL);",
           "INSERT INTO bot_import(id,data) VALUES(1,'') ON CONFLICT(id) DO UPDATE SET data='';"]
    for offset in range(0, len(text), 12000):
        chunk = text[offset:offset+12000].replace("'", "''")
        sql.append("UPDATE bot_import SET data=data||'"+chunk+"' WHERE id=1;")
    sql.append("INSERT INTO bot_state(id,data) SELECT id,data FROM bot_import WHERE id=1 ON CONFLICT(id) DO UPDATE SET data=excluded.data;")
    (OUT/'import.sql').write_text('\n'.join(sql)+'\n',encoding='utf-8')
    print(f"Private snapshot: {len(state['courses'])} courses, {len(state['assignments'])} assignments, {len(state['sent'])} notification records")

if __name__ == '__main__':
    export()
