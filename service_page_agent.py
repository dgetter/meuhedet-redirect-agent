import logging
from dotenv import load_dotenv
from openai import AzureOpenAI
from collections import deque
from config import PAGES_MODEL
import os
import json


class AzureOpenAiClient:
    def __init__(self) -> None:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

        load_dotenv()

        env = os.getenv("APP_ENV", "DEV").upper()

        self.api_key = os.getenv(f"AZURE_OPENAI_API_KEY_{env.upper()}")
        self.azure_endpoint = os.getenv(f"AZURE_OPENAI_ENDPOINT_{env.upper()}")
        self.max_retries = os.getenv(f"AZURE_OPENAI_RETRIES_{env.upper()}")
        self.api_version = os.getenv(f"AZURE_OPENAI_VERSION_{env.upper()}")

        # self.logger.info(f"ENV: {env} {self.azure_endpoint}")

        if not all([self.api_key, self.azure_endpoint, self.max_retries, self.api_version]):
            self.logger.error("Missing API key or endpoint. Please set environment variables correctly.")
            raise ValueError("Missing API key or endpoint!")

        self.client = AzureOpenAI(
            api_key=self.api_key,
            azure_endpoint=self.azure_endpoint,
            max_retries=int(self.max_retries),
            api_version=self.api_version
        )

        self.logger.info("AzureOpenAiClient initialized with API key and endpoint.")
        self._load_services_info()

    def invoke(self, user_input: str, history: list = []) -> tuple:
        messages = self._construct_prompt(user_input, history)
        self.logger.debug(f"Prompt constructed with messages: {messages}")

        try:
            response = self.client.chat.completions.create(
                messages=messages,
                model=PAGES_MODEL['MODEL'],
                max_tokens=PAGES_MODEL['MAX_TOKENS'],
                temperature=PAGES_MODEL['TEMPERATURE'],
                top_p=PAGES_MODEL['TOP_P'],
                stream=PAGES_MODEL['STREAM'],
                seed = PAGES_MODEL['SEED']
            )
            self.logger.info("Received response from Azure OpenAI.")
        except Exception as e:
            self.logger.error(f"Error while getting response from Azure OpenAI: {e}")
            self.logger.error(f"Error details: {e.args}")
            raise

        self.logger.debug(f"Response: {response}")

        response_content = response.choices[0].message.content
        self.logger.debug(f"Response content: {response_content}")

        if history is None:
            history = []
        elif isinstance(history, str):
            history = [history]

        self.logger.info(f"response_content: {response_content}")

        history.extend([
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": response_content}
        ])
        self.logger.info(f"History: {history}")
        self.logger.debug(f"Updated history length: {len(history)}")

        history = self.memory_window(history)

        self.logger.info("Memory window updated.")
        return response_content, history

    def _load_services_info(self) -> None:
        try:
            with open(PAGES_MODEL["FILE_PATH"], 'r', encoding='utf-8') as file:
                self.file = file.read()
            self.logger.info("Services file loaded successfully.")
        except Exception as e:
            self.logger.error(f"Error loading services file: {e}")
            raise

    def memory_window(self, history: list) -> list:
        hist = deque(history, maxlen=(PAGES_MODEL["MEMORY_K"] * 2))
        return list(hist)

    def _construct_prompt(self, user_input: str, history: list) -> list:
        system_message = (
            """You are an expert Hebrew classification algorithm specialized in identifying the correct service/s based on user input. Your task is to analyze the user’s query, along with the provided chat history and a file describing the available services, to determine the most relevant service/s. Follow these steps carefully:

            1. Consider Chat History for Context:

            * If the chat history contains relevant messages (e.g., follow-up questions, clarifications), use them as context to enhance your understanding of the current user input.

            2. Determine If the Input + Context Is Sufficient:

            * If the combined information is enough to confidently determine the correct service, **meaning there is only one service that could be relevant**, return the relevant service in the format:
            {"code": "<service_code>", "name": "<service_name>"} 

            * If the information is insufficient or ambiguous, **meaning more than one service could be relevant**, list the most relevant services options in descending order of relevance and ask a targeted clarification question. The format should be:
            {
            "options": [
                {"code": "<service_code>", "name": "<service_name>"},
                {"code": "<service_code>", "name": "<service_name>"},
                ... (more options if needed)
            ],
            "clarification_question": "<specific question to refine user intent>"
            }
            * The clarification question must be directly related to the listed service options and the user's input. 

            3. Handle Non-Relevant Queries.

            * If the user input is not relevant to any of the services or to your mission to find relevant services, explain it politely in the following format:
            {"error_message": "<your message to the user>"}

            4. Handle Greetings and General Inquiries:

            * If the user input is a general greeting (e.g., "How are you?", "Good morning", "Hello"), respond politely and explain your purpose.

            * If the user asks what you can help with (e.g., "What can you do?", "How can you assist me?"), respond politely and explain your purpose.


            **Context Information:**\n"""
            f"* Available services: {self.file}"
            f"* Chat history: {history}"

            "**Important Notes:**"

            "* Do not return a clarification question without listing relevant service options."
            "* Keep responses concise, structured, and informative. Avoid unnecessary explanations."
            "* Do not return the answer wrap inside: ```json...```"
        )

        self.logger.debug(f"Constructing system message.")

        return [
            {
                "role": "developer",
                "content": system_message
            },
            {
                "role": "user",
                "content": user_input
            }
        ]