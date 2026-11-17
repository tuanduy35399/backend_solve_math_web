import json
import os
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase
from ai_service.providers import ProviderUnavailable
from integrations.research import create_report
from integrations.research_worker import failure_code,ResearchFailure


class ResearchErrorTests(SimpleTestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'OPENAI_API_KEY':'not-real','OPENAI_BASE_URL':'http://127.0.0.1/mock','OPENAI_MODEL':'mock','TAVILY_API_KEY':'not-real'})
        self.env.start();self.addCleanup(self.env.stop)
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        root=Path(self.folder.name);(root/'ai_agent_game_maker_plan').mkdir();(root/'ai_agent_game_maker_plan/tools.py').touch()
        self.root=patch('integrations.research.ROOT',root);self.root.start();self.addCleanup(self.root.stop)
        self.material=SimpleNamespace(title='Hình vuông',topic='Hình học')

    def test_connection_failure_names_gateway_without_raw_provider_details(self):
        def worker(*args,**kwargs):
            (Path(kwargs['cwd'])/'error.json').write_text(json.dumps({'code':'model_connection'}))
            return SimpleNamespace(returncode=1,stderr='PRIVATE_SECRET_SENTINEL')
        with patch('integrations.research.subprocess.run',side_effect=worker):
            with self.assertRaises(ProviderUnavailable) as caught:create_report(self.material)
        self.assertIn('OPENAI_BASE_URL',str(caught.exception))
        self.assertNotIn('PRIVATE_SECRET_SENTINEL',str(caught.exception))

    def test_timeout_is_explicit(self):
        with patch('integrations.research.subprocess.run',side_effect=subprocess.TimeoutExpired('worker',180)):
            with self.assertRaisesMessage(ProviderUnavailable,'3 phút'):create_report(self.material)

    def test_worker_classifies_failures_without_exception_text(self):
        connection_error=type('OpenAIConnectionError',(Exception,),{})('private endpoint')
        self.assertEqual(failure_code(connection_error),'model_connection')
        self.assertEqual(failure_code(ResearchFailure('search_failed')),'search_failed')
        self.assertEqual(failure_code(ValueError('private data')),'agent_failed')
