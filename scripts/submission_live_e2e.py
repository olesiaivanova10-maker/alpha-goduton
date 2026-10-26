"""Explicit opt-in: two company analyses and chats consume organizer API budget."""
import argparse, json, time, urllib.request, urllib.error
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:28081');p.add_argument('--output',type=Path,required=True);p.add_argument('--title-contains',default='');p.add_argument('--allow-live',action='store_true');a=p.parse_args()
if not a.allow_live:raise SystemExit('Refusing external model calls without --allow-live')
def request(path, data=None):
 req=urllib.request.Request(a.base+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'},method='POST' if data is not None else 'GET')
 with urllib.request.urlopen(req,timeout=100) as f:return json.load(f)
def wait(job):
 deadline=time.monotonic()+900;previous=None
 while time.monotonic()<deadline:
  state=request('/api/feed/jobs/'+job)
  stage=state.get('detail',{}).get('stage') or state['status']
  if stage!=previous:print(job[:8],stage,flush=True);previous=stage
  if state['status'] in {'completed','failed'}:return state
  time.sleep(3)
 raise TimeoutError('Job still running after 15 minutes')
# RSS are fetched by the actual worker, no canned article or card is inserted.
rss=request('/api/news/refresh',{});rss_result=wait(rss['job_id'])
news=request('/api/news?limit=100')['items']
import re
candidate=next((n for n in news if a.title_contains.lower() in n['title'].lower() and len(n.get('body','')) >= 100 and re.search(r'\b(?:ключев.{0,12}ставк|инфляц|нефт|топлив|кредит|ставк)',n['title'].lower())),None)
if not candidate:raise SystemExit('No suitable current news: cannot claim a successful live test')
report={'rss':rss_result,'article':{'news_id':candidate['news_id'],'title':candidate['title'],'source_name':candidate['source_name'],'source_url':candidate['source_url']},'companies':[]}
a.output.parent.mkdir(parents=True,exist_ok=True)
for company in ['U_14366','U_26030']:
 print(company,'new RSS article:',candidate['title'],flush=True)
 task=request('/api/insights/analyze',{'company_id':company,'news_title':candidate['title'],'news_body':candidate['body'],'source_name':candidate['source_name'],'source_url':candidate['source_url'],'published_at':candidate.get('published_at')})
 state=wait(task['job_id'])
 feed=request('/api/feed?company_id='+company)
 row={'company_id':company,'job':state,'events':feed['events']}
 if feed['events']:
  card=feed['events'][0]
  row['chat']=request('/chat',{'card_id':card['card_id'],'question':'Какие условия кредитного договора и данные нужно уточнить перед действием? Не выдумывай размер долга.'})
  row['feedback']=request('/feedback',{'insight_id':card['card_id'],'company_id':company,'rating':3,'comment':'Технический E2E-прогон; не экспертная оценка полезности'})
 report['companies'].append(row)
 a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
print('Saved live results. Published counts:',[len(r['events']) for r in report['companies']],flush=True)
raise SystemExit(0 if any(r['events'] for r in report['companies']) and all(r['job']['status']=='completed' for r in report['companies']) else 2)
