import { Plus } from './Icons';

export function SidebarFaq(){
 return <section className="sidebar-faq" aria-labelledby="sidebar-faq-title"><span className="sidebar-faq-label">НУЖНА ПОДСКАЗКА?</span><h2 id="sidebar-faq-title">Вопросы и ответы</h2>{[
  ['Как загрузить видео?','Нажмите «Загрузить видео» в шапке. Принимаются MOV до 200 МБ.'],
  ['Сколько ждать результат?','До 5 минут, включая загрузку. Статус обновляется автоматически.'],
  ['Где смотреть результат?','В «Видеоотчётах»: выберите запись, чтобы увидеть события, таймкоды и кадры.'],
 ].map(([question,answer])=><details key={question} name="sidebar-faq"><summary>{question}<Plus size={13} aria-hidden="true"/></summary><p>{answer}</p></details>)}</section>;
}
