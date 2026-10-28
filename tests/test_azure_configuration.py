import io
import json
import os
import unittest
from unittest.mock import patch
from model_service import narrate
from decision_analysis.agents import configuration

class AzureConfigurationTests(unittest.TestCase):
    def test_summary_uses_azure_deployment_endpoint_and_api_key_header(self):
        reply={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(dict(summary='Summary',first_half='First',second_half='Second'))}]}]}
        with patch('model_service.urlopen',return_value=io.StringIO(json.dumps(reply))) as call:
            narrate({'periods':[{},{}],'agent':{}},'existing-deployment','test-only','https://example.openai.azure.com/openai/v1')
        req=call.call_args.args[0]
        self.assertEqual(req.full_url,'https://example.openai.azure.com/openai/v1/responses')
        headers={k.lower():v for k,v in req.header_items()}
        self.assertEqual(headers['api-key'],'test-only')
        self.assertNotIn('authorization',headers)
        self.assertEqual(json.loads(req.data)['model'],'existing-deployment')

    def test_existing_teammate_environment_is_reused(self):
        with patch.dict(os.environ,{'ITG_MODEL_BASE_URL':'https://example.openai.azure.com/openai/v1','ITG_MODEL_NAME':'existing-deployment','ITG_MODEL_API_KEY':'test-only'},clear=True):
            cfg=configuration()
        self.assertEqual(cfg['model'],'existing-deployment')
        self.assertTrue(cfg['api_key'])

    def test_project_configuration_takes_precedence(self):
        with patch.dict(os.environ,{'NEXTPLAY_MODEL':'new-deployment','ITG_MODEL_NAME':'old-deployment'},clear=True):
            self.assertEqual(configuration()['model'],'new-deployment')

    def test_saved_settings_override_legacy_defaults(self):
        with patch.dict(os.environ,{'ITG_MODEL_NAME':'legacy-default'},clear=True):
            self.assertEqual(configuration({'model':'saved-deployment'})['model'],'saved-deployment')
