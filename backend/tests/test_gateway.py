"""Gateway contract; mocked upstream, no GPU."""
import unittest
import httpx
from fastapi.testclient import TestClient
from service.gateway import app, with_rule_sources
from cashguard.registry import REGISTRY

class GatewayTest(unittest.TestCase):
    def test_registry_preserves_model_fields(self):
        event = dict(type=REGISTRY['B_safe_open']['name'], timecode_sec=7.25,
                     description='observed', evidence_frames=[{'timestamp_sec':7.25,'image_base64':'jpeg'}])
        result = with_rule_sources({'status':'done', 'violations':[event.copy()]})
        for k, v in event.items():
            self.assertEqual(result['violations'][0][k], v)
        self.assertTrue(result['violations'][0]['rule']['url'].startswith('https://adilet.zan.kz/'))

    def test_proxy_auth_body_health(self):
        requests = []
        def handle(request):
            requests.append(request)
            if request.url.path == '/api/v1/health':
                return httpx.Response(200, json={'status':'ok','worker':'ready','queue':0,'busy':False})
            if request.headers.get('x-api-key') != 'test-only-key':
                return httpx.Response(401, json={'detail':'unauthorized'})
            return httpx.Response(200, json={'job_id':'mock-job'})
        with TestClient(app) as client:
            original = app.state.client
            app.state.client = httpx.AsyncClient(base_url='http://mock',transport=httpx.MockTransport(handle))
            try:
                self.assertEqual(client.get('/health').json()['worker'],'ready')
                self.assertEqual(client.post('/api/v1/analyze',files={'file':('x.mov',b'local-test')}).status_code,401)
                response=client.post('/api/v1/analyze',headers={'X-API-Key':'test-only-key'},files={'file':('x.mov',b'local-test')})
                self.assertEqual(response.json(),{'job_id':'mock-job'})
                self.assertIn(b'local-test', requests[-1].content)
                self.assertEqual(client.get('/ui/api/jobs/mock-job').status_code,404)
                self.assertEqual(client.get('/.env').status_code,404)
            finally:
                client.portal.call(app.state.client.aclose)
                app.state.client = original

if __name__ == '__main__':
    unittest.main()
