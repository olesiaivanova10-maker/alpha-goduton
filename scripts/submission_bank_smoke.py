"""Opt-in positive scenario from case materials, explicitly not an unseen-news benchmark."""
import argparse, json, time, urllib.request
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--allow-live',action='store_true');p.add_argument('--base',default='http://127.0.0.1:28081');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
if not a.allow_live:raise SystemExit('Use --allow-live to spend organizer API budget')
def call(path,data=None):
 req=urllib.request.Request(a.base+path,method='POST' if data is not None else 'GET',data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=30) as f:return json.load(f)
task=call('/api/insights/analyze',{'company_id':'U_14366','news_title':'Банк России сохранил ключевую ставку на уровне 14%','news_body':'Событие из материалов кейса: 11 сентября 2026 года совет директоров Банка России сохранил ключевую ставку на уровне 14% годовых. Это первая пауза после десяти последовательных снижений ставки, начавшихся в июне 2025 года. Данные об остатке долга, ставке конкретного кредита и инвестициях клиента в новости отсутствуют.','source_name':'Материалы кейса: положительный проверочный сценарий'})
previous=None
for _ in range(300):
 state=call('/api/feed/jobs/'+task['job_id'])
 stage=state['detail'].get('stage',state['status'])
 if stage!=previous:print(stage,flush=True);previous=stage
 if state['status'] in {'completed','failed'}:break
 time.sleep(3)
feed=call('/api/feed?company_id=U_14366')
report={'scenario':'Known case-material macro event; not a held-out quality test','job':state,'events':feed['events']}
a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
passed=any(e['six_questions']['q3_bank_evaluation']['has_report'] and e['six_questions']['q3_bank_evaluation'].get('bank_excerpts') and e['audit']['is_valid'] for e in feed['events'])
print('PASS bank PDF -> synthesis -> personalized insight -> audit -> published:',bool(passed),flush=True)
raise SystemExit(0 if passed else 2)
