import os
from typing import List, Optional, Literal, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI(title="DevLearn Pro API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------ Helpers ------------

def oid_str(obj: Any) -> str:
    try:
        if isinstance(obj, ObjectId):
            return str(obj)
    except Exception:
        pass
    return str(obj)


def serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    d = {**doc}
    if d.get("_id"):
        d["id"] = oid_str(d.pop("_id"))
    # Convert datetime to isoformat strings
    for k, v in list(d.items()):
        try:
            import datetime as _dt
            if isinstance(v, (_dt.datetime, _dt.date)):
                d[k] = v.isoformat()
        except Exception:
            pass
    return d


# ------------ Schemas (lightweight request models) ------------

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    provider: Literal["email", "google"] = "email"


class LoginRequest(BaseModel):
    email: EmailStr


class AuthResponse(BaseModel):
    user_id: str
    name: str
    email: EmailStr


class NoteCreate(BaseModel):
    user_id: str
    title: str
    content: str = ""
    language: Optional[str] = None


class ProgressUpdate(BaseModel):
    user_id: str
    course: str
    lesson: str
    completed: bool = True


class MentorRequest(BaseModel):
    question: str
    language: Optional[str] = None
    level: Optional[Literal["beginner", "intermediate", "advanced"]] = "beginner"


class ConvertRequest(BaseModel):
    source_language: str
    target_language: str
    code: str


# ------------ Root & Health ------------

@app.get("/")
def read_root():
    return {"message": "DevLearn Pro Backend running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# ------------ Auth (minimal demo; replace with proper OAuth later) ------------

@app.post("/api/auth/signup", response_model=AuthResponse)
def signup(payload: SignupRequest):
    # Upsert by email
    existing = db["user"].find_one({"email": payload.email}) if db else None
    if existing:
        user_id = existing.get("_id")
        return AuthResponse(user_id=oid_str(user_id), name=existing.get("name", payload.name), email=payload.email)
    user_doc = {
        "name": payload.name,
        "email": str(payload.email),
        "provider": payload.provider,
        "created_at": __import__("datetime").datetime.utcnow(),
        "updated_at": __import__("datetime").datetime.utcnow(),
    }
    inserted = db["user"].insert_one(user_doc)
    return AuthResponse(user_id=oid_str(inserted.inserted_id), name=payload.name, email=payload.email)


@app.post("/api/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest):
    existing = db["user"].find_one({"email": str(payload.email)}) if db else None
    if not existing:
        raise HTTPException(status_code=404, detail="User not found. Please sign up.")
    return AuthResponse(user_id=oid_str(existing.get("_id")), name=existing.get("name", "User"), email=payload.email)


# ------------ Notes ------------

@app.get("/api/notes", response_model=List[Dict[str, Any]])
def list_notes(user_id: str):
    docs = get_documents("note", {"user_id": user_id}, limit=100)
    return [serialize_doc(d) for d in docs]


@app.post("/api/notes", response_model=Dict[str, Any])
def create_note(payload: NoteCreate):
    note = payload.model_dump()
    note_id = create_document("note", note)
    saved = db["note"].find_one({"_id": ObjectId(note_id)})
    return serialize_doc(saved)


# ------------ Progress & Ranks ------------

@app.get("/api/progress/{user_id}", response_model=Dict[str, Any])
def get_progress(user_id: str):
    items = get_documents("progress", {"user_id": user_id}, limit=500)
    total_completed = sum(1 for i in items if i.get("completed"))
    # Simple rank thresholds
    if total_completed >= 50:
        rank = "🏆 Platinum"
    elif total_completed >= 25:
        rank = "🥇 Gold"
    elif total_completed >= 10:
        rank = "🥈 Silver"
    elif total_completed >= 3:
        rank = "🥉 Bronze"
    else:
        rank = "🎓 Newbie"
    return {"items": [serialize_doc(i) for i in items], "completed": total_completed, "rank": rank}


@app.post("/api/progress", response_model=Dict[str, Any])
def update_progress(payload: ProgressUpdate):
    doc = payload.model_dump()
    _id = create_document("progress", doc)
    saved = db["progress"].find_one({"_id": ObjectId(_id)})
    return serialize_doc(saved)


# ------------ Curated YouTube content (no API key required) ------------

CURATED_CHANNELS = [
    {
        "name": "CodeWithHarry",
        "url": "https://www.youtube.com/@CodeWithHarry",
        "topics": ["C++", "JavaScript", "Python", "DSA", "React"],
        "videos": [
            {"title": "Python for Beginners (Hindi)", "videoId": "gfDE2a7MKjA"},
            {"title": "C++ Full Course", "videoId": "z9bZufPHFLU"},
            {"title": "React JS Tutorials", "videoId": "bMknfKXIFA8"}
        ]
    },
    {
        "name": "WsCube Tech",
        "url": "https://www.youtube.com/@wscubetechindia",
        "topics": ["Web Dev", "Java", "Python", "DSA"],
        "videos": [
            {"title": "Java Tutorial Series", "videoId": "xk4_1vDrzzo"},
            {"title": "HTML & CSS Crash Course", "videoId": "qz0aGYrrlhU"}
        ]
    },
    {
        "name": "Apna College",
        "url": "https://www.youtube.com/@ApnaCollegeOfficial",
        "topics": ["C++", "DSA", "Placements"],
        "videos": [
            {"title": "DSA One Shot", "videoId": "8hly31xKli0"},
            {"title": "C++ Placement Course", "videoId": "z9bZufPHFLU"}
        ]
    }
]


@app.get("/api/videos", response_model=Dict[str, Any])
def list_videos():
    # Returns curated channels and videos (embed via https://www.youtube.com/watch?v={id})
    return {"channels": CURATED_CHANNELS}


# ------------ AI Mentor (rule-based placeholder) ------------

@app.post("/api/ai/mentor", response_model=Dict[str, Any])
def ai_mentor(req: MentorRequest):
    lang = (req.language or "programming").title()
    level = req.level or "beginner"
    tips = {
        "beginner": [
            "Break problems into small steps and write pseudo-code first.",
            "Practice daily: tiny consistent sessions beat long rare ones.",
            "Read errors carefully; they often tell you exactly what to fix.",
        ],
        "intermediate": [
            "Write tests for edge cases before refactoring.",
            "Profile performance before optimizing.",
            "Learn your debugger and step through code.",
        ],
        "advanced": [
            "Design for maintainability; prefer clarity over cleverness.",
            "Document assumptions and invariants in code.",
            "Benchmark with realistic data and environments.",
        ],
    }
    answer = f"Here are some {level} tips for {lang}:\n- " + "\n- ".join(tips.get(level, tips["beginner"]))
    return {"answer": answer}


# ------------ Code Converter (very naive demo) ------------

@app.post("/api/ai/convert", response_model=Dict[str, Any])
def convert_code(req: ConvertRequest):
    src = req.source_language.lower()
    tgt = req.target_language.lower()
    code = req.code.strip()

    if src == tgt:
        return {"converted": code, "notes": "Source and target languages are the same."}

    # Very naive patterns just for demo purposes
    converted = code
    notes = []

    if src in ["javascript", "js"] and tgt in ["python"]:
        converted = converted.replace("console.log", "print")
        converted = converted.replace("===", "==").replace("!==", "!=")
        converted = converted.replace("true", "True").replace("false", "False")
        notes.append("Converted console.log to print and booleans to Python style.")
    elif src in ["python"] and tgt in ["javascript", "js"]:
        converted = converted.replace("print(", "console.log(")
        converted = converted.replace("True", "true").replace("False", "false")
        notes.append("Converted print to console.log and booleans to JS style.")
    else:
        notes.append("Generic transformation applied. Manual review recommended.")

    return {"converted": converted, "notes": " ".join(notes)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
