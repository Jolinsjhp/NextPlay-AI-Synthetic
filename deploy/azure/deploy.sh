#!/bin/sh
# Requires an existing resource group and active subscription. Defaults to what-if.
set -eu
if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
  echo 'Usage: sh deploy/azure/deploy.sh EXISTING_RESOURCE_GROUP UNIQUE_APP_NAME ZIP_PATH [--apply]' >&2
  exit 2
fi
resource_group="$1"
app_name="$2"
package_path="$3"
mode="${4:---plan}"
command -v az >/dev/null || { echo 'Install Microsoft Azure CLI or use Azure Cloud Shell.' >&2; exit 2; }
[ -f "$package_path" ] || { echo 'Build the sanitized ZIP package first.' >&2; exit 2; }
az account show --query '{subscription:name,state:state}' --output table
az group show --name "$resource_group" --query '{name:name,location:location}' --output table
# No paid fallback: unsupported F1 plans/regions must fail.
if [ "$mode" != '--apply' ]; then
  az deployment group what-if --resource-group "$resource_group" --template-file deploy/azure/main.json --parameters "appName=$app_name"
  echo 'Preview only. No application was deployed. Review the plan before using --apply.'
  exit 0
fi
az deployment group create --resource-group "$resource_group" --template-file deploy/azure/main.json --parameters "appName=$app_name" --query properties.outputs --output json
az webapp deploy --resource-group "$resource_group" --name "$app_name" --src-path "$package_path" --type zip --output none
host_name="$(az webapp show --resource-group "$resource_group" --name "$app_name" --query defaultHostName --output tsv)"
printf 'Deployment command finished. Verify https://%s/healthz and the three cases before claiming success.\n' "$host_name"
printf 'Model calls are disabled. Configure Foundry privately and set a call limit after checking your credits.\n'
