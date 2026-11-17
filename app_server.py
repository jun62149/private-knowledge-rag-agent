from fastapi import FastAPI 
from fastapi.middleware.cors import CORSMiddleware 
from chat.chat_routes import chat_router
from knowledgebase_server.kb_routes import kb_router 


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat_router)
app.include_router(kb_router)

if __name__=="__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=6605, log_level="info")