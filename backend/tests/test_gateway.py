"""Gateway contract; mocked upstream, no GPU."""
import unittest
import httpx
from fastapi.testclient import TestClient
from service.gateway import app, with_rule_sources
from forte.registry import REGISTRY

class GatewayTest(unittest.TestCase):
    def test_registry_preserves_model_fields(self):
        event = dict(type=REGISTRY['B_safe_open']['name'], timecode_sec=7.25,
                     description='observed', evidence_frames=[{'timestamp_sec':7.25,'image_base64':'jpeg'}])
        result = with_rule_sources({'status':'done', 'violations':[event.copy()]})
        for k, v in event.items():
            self.assertEqual(result['violations'][0][k], v)
        self.assertTrue(result['violations'][0]['rule']['url'].startswith('https://adilet.zan.kz/'))

    def test_swagger_branding_preserves_auth_contract(self):
        schema={'info':{'title':'old'},'components':{'securitySchemes':{'APIKeyHeader':{'type':'apiKey','in':'header','name':'X-API-Key'}}},'paths':{'/api/v1/analyze':{'post':{'security':[{'APIKeyHeader':[]}]}}}}
        with TestClient(app) as client:
            original=app.state.client
            app.state.client=httpx.AsyncClient(base_url='http://mock',transport=httpx.MockTransport(lambda req:httpx.Response(200,json=schema)))
            try:
                out=client.get('/openapi.json').json()
                self.assertEqual(out['info']['title'],'Forte API')
                self.assertIn('Authorize',out['info']['description'])
                self.assertEqual(out['components']['securitySchemes'],schema['components']['securitySchemes'])
                self.assertEqual(out['paths']['/api/v1/analyze']['post']['security'],schema['paths']['/api/v1/analyze']['post']['security'])
                self.assertEqual(set(out['paths']),set(schema['paths']))
                page=client.get('/docs').text
                self.assertIn('Forte API — документация',page)
                self.assertIn('"persistAuthorization": false',page)
            finally:
                client.portal.call(app.state.client.aclose)
                app.state.client=original

    def test_schema_references_preserve_upload_contract(self):
        from service.api_docs import present_schema
        old = 'Body_analyze_api_v1_analyze_post'
        schema = {'paths': {'/api/v1/analyze': {'post': {'requestBody': {
            'content': {'multipart/form-data': {'schema': {'$ref': '#/components/schemas/' + old}}}
        }}}}, 'components': {'schemas': {
            old: {'type': 'object', 'required': ['file'], 'properties': {'file': {'type': 'string', 'format': 'binary'}}},
            'HTTPValidationError': {'properties': {'detail': {'items': {'$ref': '#/components/schemas/ValidationError'}}}},
            'ValidationError': {'type': 'object'}
        }}}
        out = present_schema(schema)
        models = out['components']['schemas']
        self.assertEqual(models['VideoSubmission']['required'], ['file'])
        self.assertEqual(models['VideoSubmission']['properties']['file']['format'], 'binary')
        self.assertEqual(out['paths']['/api/v1/analyze']['post']['requestBody']['content']['multipart/form-data']['schema']['$ref'], '#/components/schemas/VideoSubmission')
        self.assertEqual(models['RequestValidationReport']['properties']['detail']['items']['$ref'], '#/components/schemas/InvalidRequestField')

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
                count = len(requests)
                self.assertEqual(client.get('/api/v1/jobs/mock-job/review').status_code,404)
                self.assertEqual(len(requests), count)
            finally:
                client.portal.call(app.state.client.aclose)
                app.state.client = original

if __name__ == '__main__':
    unittest.main()
