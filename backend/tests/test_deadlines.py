import tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from service.jobs import JobStore,Dispatcher,QueueFull

class Deadlines(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=JobStore(Path(self.tmp.name));self.disp=Dispatcher(self.store,'unused',300,False)
    def add(self,jid,age=0):
        p=Path(self.tmp.name)/f'{jid}.mov';p.write_bytes(b'test')
        return self.store.add(jid,'api','submission.mov',p,4,created_at=time.time()-age,max_active=2)
    def test_capacity_rejects_without_storing(self):
        self.add('a');self.add('b')
        with self.assertRaises(QueueFull):self.add('c')
        self.assertIsNone(self.store.get('c'))
    def test_pending_expiry_and_deletion(self):
        self.add('old',301);self.add('fresh');self.disp.pending.extend(['old','fresh'])
        self.disp._expire_pending()
        self.assertEqual(list(self.disp.pending),['fresh'])
        self.assertEqual(self.store.get('old')['status'],'failed')
        self.assertFalse(Path(self.store.get('old')['video']).exists())
    def test_dispatch_does_not_restart_deadline(self):
        self.add('old',301);self.disp._dispatch('old')
        self.assertIsNone(self.disp.current)
        self.assertEqual(self.store.get('old')['attempts'],0)
    def test_late_success_is_not_success_and_terminal_is_immutable(self):
        self.add('old',301);self.disp._finish('old','done',{'verdict':'no_violation','violations':[]})
        self.assertEqual(self.store.get('old')['status'],'failed')
        self.disp._finish('old','done',{'verdict':'violation','violations':[]})
        self.assertIsNone(self.store.get('old')['result'])
    def test_deadline_includes_waiting(self):
        j=self.add('a',295)
        self.disp.current_started=time.time()
        with patch('service.jobs.time.time',return_value=j['created_at']+301):
            self.assertTrue(self.disp._expired('a'))
