"""Link model events to reference norms, without inferring missing legal conditions."""
import json
from pathlib import Path
from forte.registry import REGISTRY, refs
from .event_wording import qualify_known_description

DATA = json.loads((Path(__file__).resolve().parents[1] / 'regulatory/regulatory_rules.json').read_text())
RULES = {r['rule_id']: r for r in DATA['rules']}
SOURCE_AUDIT_PATH = Path(__file__).resolve().parents[1] / 'regulatory/source_audit.json'
SOURCE_AUDIT = json.loads(SOURCE_AUDIT_PATH.read_text()) if SOURCE_AUDIT_PATH.exists() else {}
APPLICABILITY_SOURCES = json.loads((Path(__file__).resolve().parents[1] / 'regulatory/applicability_sources.json').read_text())
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
    if code == 'L_workstation_unlocked':
        return {'document':'Прямое нормативное основание не установлено',
                'section':None, 'url':None, 'assessment':'NEEDS_REVIEW', 'rule_ids':[], 'sources':[],
                'relation':'NO_DIRECT_BASIS',
                'reason':'Норма об автоматической блокировке после 30 минут не устанавливает нарушение при кратком уходе работника. Клиентский документ онлайн-банкинга не определяет обязанности кассира. Для вывода о нарушении необходимы применимые внутренние требования банка и подтверждение состояния сессии.',
                'unknown_conditions':[{'id':'workstation_policy','text':'Внутренние требования банка, длительность бездействия и состояние сессии','value':'UNKNOWN'}],
                'checked_at':None, 'source_verification':'NOT_APPLICABLE'}
    if code not in MAPPING:
        sources = []
        return {
            'document': sources[0]['doc'] if sources else 'Нормативное соответствие не установлено',
            'section': sources[0]['label'] if sources else None,
            'url': sources[0]['url'] if sources else None,
            'assessment': 'NEEDS_REVIEW', 'rule_ids': [], 'sources': [],
            'reason': 'Соответствующего правила в присланном модуле нет. Неподходящая ссылка не назначается.',
            'unknown_conditions': [], 'checked_at': None,
        }
    ids, reason = MAPPING[code]
    rules = [RULES[i] for i in ids if RULES[i]['legal_status']=='VERIFIED']
    sources, unknown = [], []
    for rule in rules:
        doc = rule['legal_document']
        audit = SOURCE_AUDIT.get('rules', {}).get(rule['rule_id'], {})
        for index, clause in enumerate(doc.get('clause_refs', [])):
            verified = audit.get('clauses', [])[index] if audit.get('text_verified') else {}
            source = {'document':doc['title'], 'section':clause['clause'],
                      'url':verified.get('url', clause['url'])}
            if verified:
                source['quote'] = verified['quote']
            if rule['rule_id'] not in APPLICABILITY_SOURCES and source not in sources: sources.append(source)
        for source in APPLICABILITY_SOURCES.get(rule['rule_id'], []):
            if source not in sources: sources.append(source)
        unknown.extend({'id':c['condition_id'], 'text':c['description'], 'value':'UNKNOWN'} for c in rule['required_conditions'])
    first = sources[0] if sources else {'document':'Нормативное соответствие не установлено'}
    return {**first, 'assessment':'NEEDS_REVIEW', 'rule_ids':[r['rule_id'] for r in rules],
            'relation':'RELATED_ONLY' if code in ('B_safe_open','E_unauthorized_person','H_door_open') else 'CONDITIONAL_BASIS',
            'reason':reason, 'sources':sources, 'unknown_conditions':unknown,
            'checked_at':SOURCE_AUDIT.get('fetched_at', DATA['checked_at']),
            'source_verification':('OFFICIAL_TEXT_VERIFIED' if rules and all(
                SOURCE_AUDIT.get('rules', {}).get(r['rule_id'], {}).get('text_verified') for r in rules)
                else 'PACKAGE_REFERENCE_NOT_REVERIFIED'),
            'verification_note':'Цитаты сверены с текстом официального источника. Применимость к конкретному событию оценивается отдельно.' if SOURCE_AUDIT else 'Сверка официального текста не выполнена.'}


def enrich(payload):
    if not isinstance(payload,dict) or payload.get('status')!='done': return payload
    lookup={v['name']:k for k,v in REGISTRY.items()}
    for event in payload.get('violations',[]):
        code=lookup.get(event.get('type'))
        event['rule']=reference_for(code)
        # Replace only the exact legacy normative suffix; never edit visual evidence or unknown text.
        description=qualify_known_description(code,event.get('description'))
        if isinstance(description,str): event['description']=description
        if code and isinstance(description,str):
            for lead in ('Возможное нарушение требования', 'Может не соответствовать требованию'):
                suffix=f"{lead}: {REGISTRY[code]['norm']}."
                if description.endswith(suffix):
                    event['description']=description[:-len(suffix)].rstrip() + ' Нормативная применимость не установлена автоматически. Точный пункт, официальный источник и условия применения приведены в разделе «Правило».'
                    break
    return payload
