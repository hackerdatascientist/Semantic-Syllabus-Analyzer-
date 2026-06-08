from fastapi import FastAPI,UploadFile,File

app=FastAPI()

@app.post("/upload")

async def upload_file(file:UploadFile = File(...)):
    content = await file.read()

    return
    {
        "filename":file.filename,
        "content_type":file.content_type,
        "size":len(content)
    }