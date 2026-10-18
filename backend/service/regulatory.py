"""Link model events to reference norms, without inferring missing legal conditions."""
import json
from pathlib import Path
from cashguard.registry import REGISTRY, refs

DATA = json.loads((Path(__file__).resolve().parents[1] / 'regulatory/regulatory_rules.json').read_text())
RULES = {r['rule_id']: r for r in DATA['rules']}
# References for review, NOT automatic equivalence or confirmed legal findings.
MAPPING = {
    'A_unattended_valuables': (['CASH_006','CASH_008'], 'Проверить, что это ранее принятые банкноты или незавершённый приём. Сумка или папка сами по себе этих условий не подтверждают.'),
    'B_safe_open': (['CASH_007'], 'Связанная норма о запираемом устройстве. Открытая дверца не доказывает, что устройство не закрывается на ключ.'),
    'C_cash_on_desk_next_client': (['CASH_006'], 'Нужно подтвердить, что на столе остаются деньги предыдущей операции, а не нового клиента.'),
    'D_no_authenticity_check': (['CASH_018'], 'Нужна проверка типа операции, возможностей оборудования и полной последовательности действий.'),
    'E_unauthorized_person': (['CASH_047'], 'Связанная норма об изоляции помещения. По внешности человека нельзя установить его полномочия или отсутствие допуска.'),
    'F_bag_no_check': (['CASH_035'], 'Нужно подтвердить передачу именно инкассаторской сумки и наблюдаемость всей обязательной проверки. Уход человека сам по себе не доказывает пропуск проверки.'),
    'G_personal_items': (['CASH_001'], 'Нужно подтвердить личный характер вещи, хранение и отсутствие исключений. Наличие чашки или питьё само по себе не подтверждает нарушение пункта 12.'),
    'H_door_open': (['CASH_047','CASH_048'], 'Связанные требования к устройству кассы. Открытая дверь в конкретный момент сама по себе не доказывает отсутствие изоляции или отдельного запираемого входа.'),
    'I_no_client_id': (['CASH_059'], 'Отсутствие видимого документа не доказывает отсутствие идентификации, включая цифровую.'),
    'J_count_without_client': (['CASH_005'], 'Проверить, что пересчитываются принимаемые деньги данного клиента после его ухода из места обслуживания.'),
}


def reference_for(code):
    if code not in MAPPING:
        sources = refs(code) if code else []
        return {
            'document': sources[0]['doc'] if sources else 'Нормативное соответствие не установлено',
            'section': sources[0]['label'] if sources else None,
            'url': sources[0]['url'] if sources else None,
            'assessment': 'NEEDS_REVIEW', 'rule_ids': [], 'sources': [],
            'reason': 'Соответствующего правила в присланном модуле нет. Прежняя ссылка приведена только для ручной проверки; её применимость не подтверждена.',
            'unknown_conditions': [], 'checked_at': None,
        }
    ids, reason = MAPPING[code]
    rules = [RULES[i] for i in ids if RULES[i]['legal_status']=='VERIFIED']
    sources, unknown = [], []
    for rule in rules:
        doc = rule['legal_document']
        for clause in doc.get('clause_refs', []):
            source = {'document':doc['title'], 'section':clause['clause'], 'url':clause['url']}
            if source not in sources: sources.append(source)
        unknown.extend({'id':c['condition_id'], 'text':c['description'], 'value':'UNKNOWN'} for c in rule['required_conditions'])
    first = sources[0] if sources else {'document':'Нормативное соответствие не установлено'}
    return {**first, 'assessment':'NEEDS_REVIEW', 'rule_ids':[r['rule_id'] for r in rules],
            'reason':reason, 'sources':sources, 'unknown_conditions':unknown,
            'checked_at':DATA['checked_at'],
            'verification_note':'Дата и VERIFIED — сведения поставленного нормативного пакета. Условия события моделью не подтверждены.'}


def enrich(payload):
    if not isinstance(payload,dict) or payload.get('status')!='done': return payload
    lookup={v['name']:k for k,v in REGISTRY.items()}
    for event in payload.get('violations',[]):
        event['rule']=reference_for(lookup.get(event.get('type')))
    return payload
