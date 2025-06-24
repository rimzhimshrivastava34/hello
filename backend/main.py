from fastapi import FastAPI, Depends
from fastapi.responses import StreamingResponse
import asyncio
import os
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from google.generativeai import GenerativeModel, configure
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, validator

load_dotenv()
# Initialize FastAPI
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("MONGO_URI is not set in .env file")
client = AsyncIOMotorClient(MONGO_URI, tls=True, tlsAllowInvalidCertificates=True)
db = client.convo_history  # Database
collection = db.chats  # Collection to store conversations

class ChatRequest(BaseModel):
    user_id: str
    message: str

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBjYD7zaVZ8hG3k7fk1wVwCCm2JckzdKcc")
configure(api_key=GEMINI_API_KEY)
model = GenerativeModel("gemini-1.5-flash")

# Prompt
QUIZ_PROMPT = """
You are a quiz tutor. Based on the given topic, generate a quiz question, a broad hint, a more specific hint, and check the user’s answer.

You are a friendly and knowledgeable math and science tutor. Your goal is to provide clear, concise, and step-by-step explanations without directly giving answers. Follow these steps:
- Begin with: 'Hey there! What topic would you like to study?'
- After the user specifies a topic, ask a multiple-choice question related to it, offering four options.
- When the user selects an option, provide hints to guide their understanding without revealing the answer.
- If the user answers incorrectly, continue providing hints, moving from broad to more specific, until they arrive at the correct answer.
- The user cannot switch to a different question until they answer the current one correctly.
- Once they get the right answer, congratulate them and ask: 'Would you like to proceed with the next question?'
- Keep responses short, to the point, and focused on fostering the student’s learning.

Response Format Example:
1. Initial greeting: 'Hey there! What topic would you like to study?'
2. User response: 'Algebra'
3. Tutor question: 'What’s the value of x in 2x + 3 = 7? A) 1, B) 2, C) 3, D) 4'
4. User response: 'A'
5. Tutor hint: 'Try substituting x = 1 into the equation. Does 2(1) + 3 equal 7? Let’s rethink the steps!'
6. User response: 'C'
7. Tutor hint: 'Let’s break it down: Subtract 3 from both sides first, then divide by 2. Try again!'
8. User response: 'B'
9. Tutor confirmation: 'Great job! 2(2) + 3 = 7, so x = 2 is correct. Would you like to proceed with the next question?'
"""


# Pydantic models
class HistoryItem(BaseModel):
    role: str
    content: str
    
    @validator("role")
    def role_must_be_valid(cls, v):
        if v not in ["user", "assistant"]:
            raise ValueError("Role must be 'user' or 'assistant'")
        return v



# Helper function to stream responses
async def stream_response(response_text: str):
    print(f"streaming response: {response_text}")
    for char in response_text:
        yield char
        await asyncio.sleep(0.01)

# Function to get conversation history from MongoDB
async def get_history(user_id: str):
    user_data = await collection.find_one({"user_id": user_id})
    return user_data["history"] if user_data else []

# Function to update conversation history
async def update_history(user_id: str, role: str, content: str):
    print(f"Updating history for user {user_id}: {role}: {content}")
    await collection.update_one(
        {"user_id": user_id},
        {"$push": {"history": {"role": role, "content": content}}},
        upsert=True
    )

# Gemini AI response function
async def gemini_response(user_id: str, message: str):
    print(f"Processing Gemini response for user {user_id}: {message}")
    try:
        history = await get_history(user_id)
        await update_history(user_id, "user", message)  # Store user message
        
        # Case 1: First message (ask topic)
        if not history:
            response = "Hey there! What topic would you like to study?"
            await update_history(user_id, "assistant", response)
            async for char in stream_response(response):
                yield char
            return
        
        # Case 2: Topic selection (Generate quiz question)
        if len(history) == 1:
            prompt = f"{QUIZ_PROMPT}\nUser topic: {message}"
            gemini_output = model.generate_content(prompt).text
            response = f"Great choice! Here’s your first question: {gemini_output}"
            await update_history(user_id, "assistant", response)
            async for char in stream_response(response):
                yield char
            return
        
        # Case 3: Check user's answer and provide hints
        prompt = f"{QUIZ_PROMPT}\nUser question: {history[-1]['content']}\nUser answer: {message}"
        gemini_output = model.generate_content(prompt).text
        await update_history(user_id, "assistant", gemini_output)
        
        async for char in stream_response(gemini_output):
            yield char
    
    except Exception as e:
        yield f"Error: {str(e)}"

# API Endpoint
@app.post("/ask")
async def ask_question(request: ChatRequest):
    print(f"Received request: {request}")
    return StreamingResponse(gemini_response(request.user_id, request.message), media_type="text/plain")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

