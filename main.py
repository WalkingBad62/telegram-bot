#!/usr/bin/env python
import os
from dotenv import load_dotenv

load_dotenv()

import uvicorn
from backend import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)