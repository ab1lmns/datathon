document.getElementById('forte-auth').addEventListener('submit', function(event) {
 event.preventDefault();
 const field=document.getElementById('forte-key');
 const status=document.getElementById('forte-key-status');
 if(!window.ui || !window.ui.preauthorizeApiKey){status.textContent='Документация ещё загружается. Повторите через несколько секунд.';return;}
 const key=field.value.trim();
 if(!key){status.textContent='Введите ключ доступа.';return;}
 window.ui.preauthorizeApiKey('APIKeyHeader',key);
 field.value='';
 status.textContent='Ключ добавлен. Его действительность будет проверена сервером при запросе.';
});
document.getElementById('forte-clear').addEventListener('click',function(){
 if(window.ui)window.ui.authActions.logout(['APIKeyHeader']);
 document.getElementById('forte-key').value='';
 document.getElementById('forte-key-status').textContent='Ключ удалён из вкладки.';
});
