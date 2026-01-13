from xml.etree.ElementTree import tostring

from fastapi import FastAPI
from datetime import datetime
from zoneinfo import ZoneInfo

app = FastAPI()


@app.get("/")
async def root():
    message = "Hello World"
    log(message)
    return {"message": message}

def main():
    print("Hello from emspprojectv1!")

def log(string):
    now_utc = datetime.now(ZoneInfo("UTC"))
    logger = now_utc.strftime("%Y-%m-%d %H:%M:%S") + ":  Sending API Response:  " + string
    print(logger)

if __name__ == "__main__":
    main()
