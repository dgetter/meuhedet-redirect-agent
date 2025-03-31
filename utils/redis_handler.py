import redis
import json
import os
import logging
from dotenv import load_dotenv


class RedisSessionManager:
    def __init__(self):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

        load_dotenv()

        env = os.getenv("APP_ENV", "DEV").lower()

        self.host = os.getenv(f"REDIS_HOST_{env.upper()}")
        self.port = os.getenv(f"REDIS_PORT_{env.upper()}")
        self.db = os.getenv(f"REDIS_DB_{env.upper()}")
        self.password = os.getenv(f"REDIS_PASSWORD_{env.upper()}")

        self.logger.info(f"ENV: {env} {self.host} {self.port} {self.db}")

        if not all([self.host, self.port, self.db, self.password]):
            self.logger.error(f"Missing required environment variables for Redis connection: {env}")
            raise ValueError("Missing required Redis environment variables")

        self.redis_client = redis.Redis(
            host=self.host,
            port=self.port,
            db=self.db,
            decode_responses=True,
            ssl=True,
            password=self.password
        )

    def save_session(self, session_id, data):
        try:
            json_data = json.dumps(data, ensure_ascii=False)
            self.redis_client.set(session_id, json_data)
            self.logger.info(f"Data written to Redis for session {session_id}")
        except Exception as e:
            self.logger.error(f"Error writing to Redis: {e}")

    def get_session(self, session_id):
        try:
            data = self.redis_client.get(session_id)
            self.logger.info(f"Data read from Redis for session {session_id}")
            if data:
                self.logger.info(f"data: {json.loads(data)}")
                return json.loads(data)
            return None
        except Exception as e:
            self.logger.error(f"Error reading from Redis: {e}")
            return None

    def append_to_session(self, session_id, new_data):
        try:
            existing_data = self.get_session(session_id)

            if not isinstance(existing_data, list):
                existing_data = [existing_data] if existing_data else []

            existing_data.append(new_data)
            self.save_session(session_id, existing_data)
            self.logger.info(f"Session {session_id} updated with new data")
        except Exception as e:
            self.logger.error(f"Error appending data to session {session_id}: {e}")

    def delete_session(self, session_id):
        try:
            self.redis_client.delete(session_id)
            self.logger.info(f"Session {session_id} deleted from Redis")
        except Exception as e:
            self.logger.error(f"Error deleting session {session_id} from Redis: {e}")

    def close_connection(self):
        try:
            self.redis_client.close()
            self.logger.info("Redis connection closed")
        except Exception as e:
            self.logger.error(f"Error closing Redis connection: {e}")

# if __name__ == "__main__":
#     redis_manager = RedisSessionManager()
#     redis_manager.delete_session('"xyz-456')
#     session_data = {"user_id": 123, "name": "John Doe", "status": "active"}
#     redis_manager.save_session('2', session_data)
#     response_content = redis_manager.get_session('2')
#     print(response_content)