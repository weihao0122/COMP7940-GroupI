from azure.identity import DefaultAzureCredential, ManagedIdentityCredential, ClientSecretCredential
from azure.keyvault.secrets import SecretClient
import os

class ConfigManager:
    def __init__(self):
        # Key Vault URL
        self.vault_url = "https://comp7940-groupi-key.vault.azure.net/"
        
        try:
            credential = ManagedIdentityCredential()
            self.client = SecretClient(vault_url=self.vault_url, credential=credential)
            self.client.get_secret('TELEGRAM-ACCESS-TOKEN')
            print("Using Managed Identity for authentication")
        except Exception as e:
            print(f"Managed Identity failed: {str(e)}")
            try:
                credential = ClientSecretCredential(
                    tenant_id=os.getenv('AZURE_TENANT_ID'),
                    client_id=os.getenv('AZURE_CLIENT_ID'),
                    client_secret=os.getenv('AZURE_CLIENT_SECRET')
                )
                self.client = SecretClient(vault_url=self.vault_url, credential=credential)
                print("Using Service Principal for authentication")
            except Exception as e:
                print(f"Service Principal failed: {str(e)}")
                credential = DefaultAzureCredential()
                self.client = SecretClient(vault_url=self.vault_url, credential=credential)
                print("Using Default Azure Credential")
        
    def get_config(self):
        """Get all configuration from Azure Key Vault"""
        try:
            config = {
                'TELEGRAM': {
                    'ACCESS_TOKEN': self.client.get_secret('TELEGRAM-ACCESS-TOKEN').value
                },
                'CHATGPT': {
                    'BASICURL': self.client.get_secret('CHATGPT-BASICURL').value,
                    'MODELNAME': self.client.get_secret('CHATGPT-MODELNAME').value,
                    'APIVERSION': self.client.get_secret('CHATGPT-APIVERSION').value,
                    'ACCESS_TOKEN': self.client.get_secret('CHATGPT-ACCESS-TOKEN').value
                },
                'DATABASE': {
                    'MONGODB_URI': self.client.get_secret('DATABASE-MONGODB-URI').value
                }
            }
            return config
        except Exception as e:
            print(f"Error getting configuration from Key Vault: {str(e)}")
            raise 