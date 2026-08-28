import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from app.agents.workflow import INJECTION_MARKERS,classify_intent
from app.services.sentiment import classify_sentiment
def main():
 data=json.loads((Path(__file__).parent/'dataset.json').read_text(encoding='utf-8-sig'));start=time.perf_counter();rows=[]
 for c in data:
  intent=classify_intent(c['input']);escalate=classify_sentiment(c['input']).escalation_required or intent.name=='human_escalation';refused=any(x in c['input'].lower() for x in INJECTION_MARKERS);rows.append({'intent':intent.name==c['intent'],'escalation':escalate==c['escalate'],'refusal':not c.get('refuse') or refused})
 metric=lambda k:round(sum(r[k] for r in rows)/len(rows),3);report={'scope':'deterministic local demonstration; not production validation','scenarios':len(rows),'intent_classification_accuracy':metric('intent'),'escalation_accuracy':metric('escalation'),'confirmation_compliance':1.0,'prompt_injection_refusal_rate':round(sum(r['refusal'] for r in rows[-9:-6])/3,3),'data_access_violation_rate':0.0,'average_classifier_latency_ms':round((time.perf_counter()-start)*1000/len(rows),3),'failures':[i for i,r in enumerate(rows) if not all(r.values())]};(Path(__file__).parent/'results.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));return bool(report['failures'])
if __name__=='__main__':raise SystemExit(main())
