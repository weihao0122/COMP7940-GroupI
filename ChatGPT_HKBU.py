import configparser
import requests
from colorama import init, Fore, Back, Style

# Initialize colorama
init()

# Define custom symbols
SUCCESS = "[ OK ]"
ERROR = "[FAIL]"
INFO = "[INFO]"
BULLET = "*"

class HKBU_ChatGPT():
    def __init__(self, config):
        """Initialize ChatGPT client"""
        if isinstance(config, dict):
            print(f"{INFO} Using provided config dictionary")
            self.config = config
        else:
            print(f"{INFO} Loading config from file: {config}")
            self.config = configparser.ConfigParser()
            self.config.read(config)
        print(f"{SUCCESS} ChatGPT client initialized")

    def submit(self, message):
        """Submit a message to ChatGPT and get response"""
        try:
            conversation = [{"role": "user", "content": message}]
            
            # Build URL
            url = (self.config['CHATGPT']['BASICURL'] + 
                   "/deployments/" + self.config['CHATGPT']['MODELNAME'] + 
                   "/chat/completions/?api-version=" + 
                   self.config['CHATGPT']['APIVERSION'])
            
            headers = { 'Content-Type': 'application/json', 
                        'api-key': self.config['CHATGPT']['ACCESS_TOKEN'] }
            payload = { 'messages': conversation }
            
            print(f"{INFO} Sending request to ChatGPT")
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                print(f"{SUCCESS} Received response from ChatGPT")
                return data['choices'][0]['message']['content']
            else:
                print(f"{ERROR} Request failed with status code: {response.status_code}")
                return f'Error: {response.status_code}'
        except Exception as e:
            print(f"{ERROR} Exception occurred: {str(e)}")
            return f'Error: {str(e)}'

if __name__ == '__main__':
    ChatGPT_test = HKBU_ChatGPT()
    while True:
        user_input = input("Typing anything to ChatGPT:\t")
        response = ChatGPT_test.submit(user_input)
        print(response)
