"""Shared public API branding and key instructions; contains no credentials."""
TITLE = 'Forte API'
DESCRIPTION = """Интерфейс интеграции Forte: передача видеозаписи, получение состояния обработки и результатов проверки.

Для защищённых методов подключите выданный ключ через поле «Подключить ключ API» на странице документации
или кнопку Authorize в совместимом OpenAPI-клиенте. Передаётся только значение ключа, без Bearer,
в заголовке X-API-Key. Ответ 401 означает отсутствие или отклонение ключа.

Порядок работы: отправьте MOV → сохраните job_id → запрашивайте результат до done или failed.
"""


def present_schema(schema):
    """Documentation-only names and explanations; wire fields and routes stay intact."""
    schema.get('paths', {}).pop('/api/v1/jobs/{job_id}/review', None)
    schema.setdefault('info', {}).update(title=TITLE, description=DESCRIPTION)
    schema['tags'] = [{'name':'Проверка видео','description':'Отправка записи и получение результатов анализа.'},
                      {'name':'Доступность','description':'Состояние сервиса перед отправкой записи.'}]
    operations = {
        '/api/v1/analyze': ('submitVideo', 'Проверка видео', 'Отправить запись на проверку',
            'Передайте MOV-файл в поле file. Сервер вернёт job_id — идентификатор, по которому запрашивается результат. Ответ на загрузку ещё не является результатом анализа.', 'Запись принята; возвращён идентификатор задания.'),
        '/api/v1/jobs/{job_id}': ('readAnalysis', 'Проверка видео', 'Забрать результат проверки',
            'Укажите job_id, полученный после загрузки. processing означает, что проверка продолжается; done содержит результат; failed сообщает об ошибке обработки.', 'Текущее состояние задания и доступный результат.'),
        '/api/v1/health': ('readServiceStatus', 'Доступность', 'Узнать состояние сервиса',
            'Проверка доступности сервиса и состояния обработчика. Ключ для этого запроса не требуется.', 'Состояние сервиса, обработчика и очереди.'),
    }
    for path, (opid, tag, summary, description, success) in operations.items():
        for method, operation in schema.get('paths', {}).get(path, {}).items():
            if method not in ('get','post'): continue
            operation.update(operationId=opid, tags=[tag], summary=summary, description=description)
            for param in operation.get('parameters', []):
                if param.get('name')=='job_id':
                    param['description']='Идентификатор из ответа на отправку видео. Вставьте значение целиком.'
                    param.setdefault('schema', {})['title']='Идентификатор задания'
            for status,response in operation.get('responses', {}).items():
                response['description'] = {'200':success,'422':'Поля запроса не соответствуют ожидаемому формату.'}.get(status,response.get('description','Ответ сервера'))
    components=schema.setdefault('components', {})
    schemas=components.setdefault('schemas', {})
    rename={key:'VideoSubmission' for key in schemas if key.startswith('Body_analyze_')}
    rename.update({key:value for key,value in {'HTTPValidationError':'RequestValidationReport','ValidationError':'InvalidRequestField'}.items() if key in schemas})
    for old,new in rename.items(): schemas[new]=schemas.pop(old)
    titles={'VideoSubmission':'Отправка видеозаписи','RequestValidationReport':'Ошибки заполнения запроса','InvalidRequestField':'Поле с ошибкой'}
    for key,model in schemas.items():
        if key in titles:model['title']=titles[key]
        for name,prop in model.get('properties', {}).items():
            prop['title']={'file':'Видеозапись MOV','detail':'Список ошибок','loc':'Расположение поля','msg':'Причина ошибки','type':'Код ошибки','input':'Переданное значение','ctx':'Дополнительные сведения'}.get(name,prop.get('title',name))
            if name=='file':prop['description']='Выберите исходную видеозапись в формате .mov.'
    def rewrite(node):
        if isinstance(node,dict):
            ref=node.get('$ref')
            if isinstance(ref,str) and ref.startswith('#/components/schemas/'):
                old=ref.rsplit('/',1)[-1]
                if old in rename:node['$ref']='#/components/schemas/'+rename[old]
            for value in node.values(): rewrite(value)
        elif isinstance(node,list):
            for value in node:rewrite(value)
    rewrite(schema)
    return schema
