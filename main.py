from fastapi import FastAPI, Body, Request, HTTPException, Depends
from pydantic import BaseModel, Field, ValidationError
from fastapi import Header
import os
import json
from typing import List, Optional
import uvicorn
import logging
from service_page_agent import AzureOpenAiClient
from config import PAGES_API
from utils.redis_handler import RedisSessionManager

redis_manager = RedisSessionManager()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
    ,encoding="utf-8"
)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="Redirect - Agent",
    description="This is a sample API for Redirect page agent\n"
                "Usage:\n"
                "- If the 'query' parameter is string, a text card is returned.\n"
                "- If it contains json dictionary, a JSON card response is returned.\n"
                "- If it contains json dictionary with 'error_message' key, an error card is returned."
)

# ---------------------------------------------------------
# Azure openAI API wrapper
# ---------------------------------------------------------
chat_agent = AzureOpenAiClient()


# ---------------------------------------------------------
# Pydentic Models
# ---------------------------------------------------------
class CardList(BaseModel):
    total_pages: int = Field(default=1, description="Total number of pages available")
    current_page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=1, description="Number of items per page")
    json_content: str = Field(default=None, description="")


class Json_card(BaseModel):
    text: str = Field(default="...", description="Text description")
    content: str = Field(default=json.dumps({}), description="Contains content object")

    class Config:
        arbitrary_types_allowed = True


class RequestMSG(BaseModel):
    request_id: str = Field(example="1", description="Unique request identifier")
    source_system: int = Field(example=46, description="System code (46=Website, 65=Apps)")
    session_id: str = Field(example="xyz-456", description="Session identifier")
    query: str = Field(example="Find nearest hospital", description="User input query")


class Text_card(BaseModel):
    text: str = Field(example="some text", description="response to user")


class Options_card(BaseModel):
    text: str = Field(example="some text", description="response to user")
    options: List[str] = Field(example=["Hospital A", "Hospital B", "Hospital C"], description="List of options")


class Error_card(BaseModel):
    text: str = Field(
        default="אני מצטער, אך בקשתך אינה נמצאת בתחום הטיפול שלי. אני יכול לעזור לך במידע רפואי, קביעת תורים, ומציאת",
        description="Bot response shown to the user when the request is out of scope – fixed message"
        )
    code_error: int = Field(default=PAGES_API["OUT_OF_SCOPE_ERROR_CODE"],
                            description="Error code in the example indicating the request is out of the bot's handling scope"
                            )
    error_msg: str = Field(default="failed to pass Agent Rail Guard -> out of scope",
                           description="Internal error message or reason, optionally shown for logging or advanced handling"
                           )


class RequestHeaders(BaseModel):
    login_mask_id: str = Header(None, example="masked-123", description="Masked login identifier")
    login_gender: str = Header(None, example="M", description="Gender of logged-in user (M/F/U)")
    cust_mask_id: str = Header(None, example="masked-456", description="Masked customer identifier")
    cust_gender: str = Header(None, example="F", description="Customer gender (M/F)")
    cust_age: int = Header(None, example=30, description="Customer age")
    dr_license: str = Header(None, description="personal doctor liscence")
    pass


class ResponseMSG(BaseModel):
    request_id: str = Field(example="1", description="Unique request identifier")
    source_system: int = Field(example=46, description="System code (46=Website, 65=Apps)")
    session_id: str = Field(example="xyz-456", description="Session identifier")
    next_agent: str = Field(example="classifier/redirect/searchService...", description="the next agent to address")
    card_type: str = Field(example="text/options/json/error", description="Type of card being returned")
    card_sub_type: str = Field(default="none", example="none/poi/redirect/shaban...",
                               description="Subtype when card_type is json")

    text_card: Optional[Text_card] = Field(default=None, description="Text response to the user")
    options_card: Optional[Options_card] = Field(default=None, description="Options list for the user")
    json_card: Optional[Json_card] = Field(default=None, description="JSON structured data")
    error_card: Optional[Error_card] = Field(default=None, description="Error structured data")

    # Validators to ensure proper card setup based on card_type
    def __init__(self, **data):
        super().__init__(**data)
        if self.card_type == "text":
            if self.text_card is None:
                self.text_card = Text_card(text="")
            self.options_card = None
            self.json_card = None
            self.card_sub_type = "redirect"
        elif self.card_type == "options":
            if self.options_card is None:
                self.options_card = Options_card(text="", options=[])
            self.text_card = None
            self.json_card = None
            self.card_sub_type = "redirect"
        elif self.card_type == "json":
            if self.json_card is None:
                self.json_card = Json_card(text="", content={}) #content=json.dumps({}))
            self.text_card = None
            self.options_card = None
            self.card_sub_type = "redirect"
        elif self.card_type == "error":
            self.card_sub_type = "redirect"
            if self.error_card is None:
                self.error_card = Error_card()
            self.text_card = None
            self.options_card = None
            self.json_card = None


# ---------------------------------------------------------
# Helper functions for responses
# ---------------------------------------------------------
def create_json_response(req: RequestMSG, model_answer: dict) -> ResponseMSG:
    try:
        options = model_answer["options"]
        text = model_answer["clarification_question"]
    except:
        options = model_answer
        text = "זה מה שמצאתי:"
    json_card = Json_card(
        text=text,
        content= json.dumps(options, ensure_ascii=False)
    )

    return ResponseMSG(
        request_id=req.request_id,
        source_system=req.source_system,
        session_id=req.session_id,
        next_agent="redirect",
        card_type="json",
        json_card=json_card
    )


def create_text_response(req: RequestMSG, model_answer: str) -> ResponseMSG:
    return ResponseMSG(
        request_id=req.request_id,
        source_system=req.source_system,
        session_id=req.session_id,
        next_agent="redirect",
        card_type="text",
        text_card=Text_card(text=model_answer)
    )


def create_options_response(req: RequestMSG) -> ResponseMSG:
    return ResponseMSG(
        request_id=req.request_id,
        source_system=req.source_system,
        session_id=req.session_id,
        next_agent="redirect",
        card_type="options",
        options_card=Options_card(
            text="בחר אפשרות:",
            options=["אפשרות א'", "אפשרות ב'", "אפשרות ג'"]
        )
    )


def create_error_response(req: RequestMSG, model_answer: dict) -> ResponseMSG:
    return ResponseMSG(
        request_id=req.request_id,
        source_system=req.source_system,
        session_id=req.session_id,
        next_agent="redirect",
        card_type="error",
        error_card=Error_card(
            text=model_answer["error_message"],
        )
    )


def check_model_response_type(res: str) -> str:
    try:
        parsed = json.loads(res)

        if isinstance(parsed, dict) and "error_message" in parsed:
            return "error", parsed
        elif isinstance(parsed, dict):
            return "dict", parsed
        elif isinstance(parsed, list):
            return "list", parsed
        else:
            return "text", parsed
    except json.JSONDecodeError:
        return "text", res

    # ---------------------------------------------------------


# Combined /query endpoint
# ---------------------------------------------------------
@app.post("/query", response_model=ResponseMSG)
async def query_endpoint(
        req_body: RequestMSG = Body(...),
        login_mask_id: str = Header(..., alias="x-login-mask-id", example="masked-123",
                                    description="Masked login identifier"),
        login_gender: str = Header(..., alias="x-login-gender", example="M",
                                   description="Gender of logged-in user (M/F/U)"),
        cust_mask_id: str = Header(..., alias="x-cust-mask-id", example="masked-456",
                                   description="Masked customer identifier"),
        cust_gender: str = Header(..., alias="x-cust-gender", example="F", description="Customer gender (M/F)"),
        cust_age: int = Header(..., alias="x-cust-age", example=30, description="Customer age"),
        dr_license: str = Header(..., alias="x-dr-license", example="abcde-1245",
                                 description="personal doctor license"),
) -> ResponseMSG:
    try:
        # Convert request to Pydantic model
        request_msg = req_body
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Body validation error: {e}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")

    query = request_msg.query
    history = redis_manager.get_session(request_msg.session_id)
    if isinstance(history, bytes):
        history = history.decode('utf-8')
    logger.info(f"History: {history}")

    answer, updated_history = chat_agent.invoke(query, [history])
    response_type, parsed_ans = check_model_response_type(answer)
    logger.info(f"parsed_ans: {parsed_ans}")

    logger.info(f"History after: {updated_history}")
    logger.info(f"Answer: {answer}")
    if updated_history:
        redis_manager.append_to_session(request_msg.session_id, updated_history)
    else:
        redis_manager.save_session(request_msg.session_id, updated_history)

    if response_type == "text":
        response = create_text_response(request_msg, parsed_ans)
        return response
    elif response_type == "dict":
        response = create_json_response(request_msg, parsed_ans)
        return response
    elif response_type == "error":
        response = create_error_response(request_msg, parsed_ans)
        return response


# if __name__ == "__main__":
#     port = int(os.environ.get("PORT", 5000))
#     uvicorn.run(app, host="0.0.0.0", port=port)

