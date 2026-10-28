# Reuse an existing Azure deployment

The Settings form already supplies the saved service configuration to both the
match summary and bounded agent tools. A new Azure resource is not required if
the team already owns a compatible deployment.

1. Copy the Azure OpenAI / Foundry **base URL**, for example
   `https://YOUR-RESOURCE.openai.azure.com/openai/v1`.
2. Enter the **deployment name**, not an arbitrary model family label.
3. Enter the API key privately in Settings, or configure the server environment.
4. Save, then verify a summary and an agent explanation. Endpoint compatibility
   and available quota still need a real provider call.

The runtime accepts `NEXTPLAY_MODEL_BASE_URL`, `NEXTPLAY_MODEL`,
`NEXTPLAY_MODEL_API_KEY`. It also accepts the teammate deployment names
`ITG_MODEL_BASE_URL`, `ITG_MODEL_NAME`, `ITG_MODEL_API_KEY`; the NEXTPLAY variables
take precedence. Secrets are not exposed by the settings GET endpoint.

The summary transport uses `api-key` for Azure hosts and bearer authorization
for other compatible hosts. No redirects are followed. A public Azure App
Service website URL is not a model inference endpoint.

The local services inspected on 28 October had no model name or saved key;
this release therefore does not claim a live Azure connection.

Reference: [Microsoft Responses v1 documentation](https://learn.microsoft.com/en-us/rest/api/aifoundry/azureopenai/responses).
