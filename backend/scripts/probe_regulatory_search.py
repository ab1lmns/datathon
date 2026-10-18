"""Bounded, synthetic text-fact test. NOT video accuracy or a production endpoint."""
import json, time, resource
from pathlib import Path
from service.regulatory_search import LegalSearch

CASES = [
 ('count_absent', ['Кассир продолжает приём переданных клиентом наличных денег и пересчитывает именно эти деньги.', 'Клиент ушёл из полностью наблюдаемой зоны обслуживания; через стекло и рядом его также нет.', 'Операция приёма ещё не завершена, это не внутренняя обработка уже принятых денег.']),
 ('count_present', ['Кассир принимает наличные деньги и пересчитывает их в присутствии клиента.', 'Клиент остаётся у рабочего стола до завершения пересчёта.']),
 ('cup_only', ['На рабочем столе видна чашка; кассир пьёт из неё. Принадлежность чашки и наличие разрешения неизвестны.']),
 ('door_passage', ['Посетитель проходит через открытую дверь, затем дверь закрывается. Кассовое помещение отделено стенами и отдельным запираемым входом.']),
 ('bag_uncertain', ['Человек передаёт непрозрачную сумку кассиру и уходит. Назначение сумки, её содержимое и проверка пломб не видны.']),
 ('cash_between', ['На рабочем столе находятся ранее принятые наличные деньги первого клиента; операция с ним завершена.', 'Следующий клиент начинает обслуживание, деньги предыдущей операции всё ещё на столе вне запираемого устройства.']),
]

def main():
 import torch
 from transformers import AutoProcessor, AutoModelForImageTextToText
 free,total=torch.cuda.mem_get_info()
 if free < 11*1024**3: raise RuntimeError('Insufficient free VRAM; production untouched')
 torch.cuda.set_per_process_memory_fraction(0.39)
 search=LegalSearch(); start=time.monotonic()
 model_id='Qwen/Qwen3-VL-4B-Instruct'
 proc=AutoProcessor.from_pretrained(model_id,local_files_only=True)
 model=AutoModelForImageTextToText.from_pretrained(model_id,dtype=torch.bfloat16,local_files_only=True).to('cuda').eval()
 results=[]
 for name,texts in CASES:
  facts=[dict(id=f'F{i+1}',text=t,pts_sec=[float(i)],certainty='clear') for i,t in enumerate(texts)]
  candidates=search.retrieve(facts)
  prompt=search.prompt(facts,candidates)
  inp=proc.apply_chat_template([{'role':'user','content':[{'type':'text','text':prompt}]}],tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors='pt').to('cuda')
  t0=time.monotonic()
  def ask(inputs, limit):
   with torch.inference_mode(): output=model.generate(**inputs,max_new_tokens=limit,do_sample=False)
   toks=output[0,inputs['input_ids'].shape[1]:]
   eos=model.generation_config.eos_token_id; eos=eos if isinstance(eos,list) else [eos]
   return proc.decode(toks,skip_special_tokens=True),len(toks),'eos' if toks[-1].item() in eos else 'length'
  raw,count,finish=ask(inp,640)
  stages=[dict(raw=raw,output_tokens=count,finish_reason=finish)]
  try:
   selected=json.loads(raw)['rule_id']
   rule=next((r for r in candidates if r['rule_id']==selected),None)
   if rule and finish=='eos':
    rows=[]
    for condition in rule['required_conditions']+rule['abstention_conditions']:
     cp=search.condition_prompt(facts,condition)
     ci=proc.apply_chat_template([{'role':'user','content':[{'type':'text','text':cp}]}],tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors='pt').to('cuda')
     cr,ct,cf=ask(ci,160); count+=ct
     stages.append(dict(condition_id=condition['condition_id'],raw=cr,output_tokens=ct,finish_reason=cf))
     if cf!='eos': finish=cf
     row=json.loads(cr); row['id']=condition['condition_id']; rows.append(row)
    raw=json.dumps(dict(rule_id=selected,conditions=rows,reason='Проверка каждого условия по фактам; объяснения приведены отдельно.'),ensure_ascii=False)
  except (ValueError,KeyError,TypeError): finish='invalid_stage'
  result=dict(case=name,synthetic=True,facts=facts,candidate_ids=[r['rule_id'] for r in candidates],raw=raw,
    output_tokens=count,stages=stages,finish_reason=finish,seconds=round(time.monotonic()-t0,3),
    validated=search.validate(raw,facts,candidates,finish))
  results.append(result); print(json.dumps({'case':name,'assessment':result['validated']['assessment'],'tokens':count},ensure_ascii=False),flush=True)
  Path('probe_results.json').write_text(json.dumps(dict(model=model_id,results=results,
    peak_vram_mib=torch.cuda.max_memory_allocated()/1024**2,wall_sec=time.monotonic()-start,
    rss_peak_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),ensure_ascii=False,indent=2))
if __name__=='__main__': main()
