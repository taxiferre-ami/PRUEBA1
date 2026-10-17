from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
import bcrypt
import jwt
from datetime import datetime, timedelta
import secrets
import re
import os

from models import init_db, SessionLocal, User, Event, EventParticipant, Exclusion, Assignment, StatusEnum
from draw import exists_valid, generate_assignment

app = FastAPI(title="Amigo Invisible Fácil v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("SECRET_KEY", "cambia-esto-en-produccion-2026")
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_pw(p: str) -> str:
    return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def verify_pw(p: str, h: str) -> bool:
    return bcrypt.checkpw(p.encode(), h.encode())

def create_token(data: dict):
    to_encode = data.copy()
    to_encode.update({"exp": datetime.utcnow() + timedelta(days=30)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        phone = payload.get("sub")
        if not phone:
            raise HTTPException(401, "Token inválido")
    except:
        raise HTTPException(401, "Token inválido")
    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        raise HTTPException(401, "Usuario no encontrado")
    return user

def generate_event_code() -> str:
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        code = "".join(secrets.choice(chars) for _ in range(8))
        if any(c.isalpha() for c in code) and any(c.isdigit() for c in code):
            return code

class RegisterIn(BaseModel):
    full_name: str
    phone: str
    password: str

class ProfileUpdate(BaseModel):
    alias: str = Field(..., min_length=1, max_length=50)
    needs: Optional[str] = Field(None, max_length=250)

class EventCreate(BaseModel):
    name: str

class JoinEvent(BaseModel):
    code: str

class ExclusionIn(BaseModel):
    giver_id: int
    receiver_id: int
    mutual: bool = False

@app.on_event("startup")
def startup():
    init_db()

@app.post("/register")
def register(data: RegisterIn, db: Session = Depends(get_db)):
    phone = re.sub(r"\D", "", data.phone)
    if db.query(User).filter(User.phone == phone).first():
        raise HTTPException(400, "Este teléfono ya está registrado")
    user = User(full_name=data.full_name.strip(), phone=phone, password_hash=hash_pw(data.password))
    db.add(user)
    db.commit()
    return {"message": "Registrado correctamente"}

@app.post("/token")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    phone = re.sub(r"\D", "", form.username)
    user = db.query(User).filter(User.phone == phone).first()
    if not user or not verify_pw(form.password, user.password_hash):
        raise HTTPException(400, "Teléfono o contraseña incorrectos")
    token = create_token({"sub": user.phone})
    return {"access_token": token, "token_type": "bearer"}

@app.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "full_name": user.full_name,
        "phone": user.phone,
        "alias": user.alias,
        "needs": user.needs
    }

@app.put("/me")
def update_me(data: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.alias = data.alias.strip()
    user.needs = (data.needs or "").strip()[:250]
    db.commit()
    return {"message": "Perfil actualizado"}

@app.post("/events")
def create_event(data: EventCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.alias:
        raise HTTPException(400, "Debes poner un Alias en tu perfil antes de crear un evento")
    code = generate_event_code()
    while db.query(Event).filter(Event.code == code).first():
        code = generate_event_code()
    ev = Event(name=data.name.strip(), code=code, creator_id=user.id)
    db.add(ev)
    db.commit()
    db.refresh(ev)
    db.add(EventParticipant(event_id=ev.id, user_id=user.id))
    db.commit()
    return {"id": ev.id, "name": ev.name, "code": ev.code}

@app.post("/events/join")
def join_event(data: JoinEvent, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.alias:
        raise HTTPException(400, "Debes poner un Alias en tu perfil antes de unirte")
    code = data.code.strip().upper()
    ev = db.query(Event).filter(Event.code == code).first()
    if not ev:
        raise HTTPException(404, "Código de evento no válido")
    if db.query(EventParticipant).filter_by(event_id=ev.id, user_id=user.id).first():
        return {"message": "Ya estás en este evento", "event_id": ev.id}
    db.add(EventParticipant(event_id=ev.id, user_id=user.id))
    db.commit()
    return {"message": "Te has unido al evento", "event_id": ev.id}

@app.get("/events")
def my_events(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    parts = db.query(EventParticipant).filter_by(user_id=user.id).all()
    result = []
    for p in parts:
        ev = p.event
        result.append({
            "id": ev.id,
            "name": ev.name,
            "code": ev.code,
            "status": ev.status.value,
            "is_creator": ev.creator_id == user.id,
            "participants_count": len(ev.participants)
        })
    return result

@app.get("/events/{event_id}")
def get_event(event_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    part = db.query(EventParticipant).filter_by(event_id=event_id, user_id=user.id).first()
    if not part:
        raise HTTPException(403, "No perteneces a este evento")
    ev = part.event
    participants = []
    for ep in ev.participants:
        u = ep.user
        participants.append({
            "id": u.id,
            "alias": u.alias or u.full_name,
            "full_name": u.full_name,
            "needs": u.needs or "",
            "phone": u.phone if ev.creator_id == user.id else None
        })
    return {
        "id": ev.id,
        "name": ev.name,
        "code": ev.code,
        "status": ev.status.value,
        "is_creator": ev.creator_id == user.id,
        "participants": participants,
        "exclusions": [{"id": e.id, "giver_id": e.giver_id, "receiver_id": e.receiver_id, "mutual": e.mutual} for e in ev.exclusions]
    }

@app.post("/events/{event_id}/exclusions")
def add_exclusion(event_id: int, data: ExclusionIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ev = db.query(Event).filter_by(id=event_id, creator_id=user.id).first()
    if not ev or ev.status != StatusEnum.preparing:
        raise HTTPException(400, "Solo el creador puede modificar exclusiones mientras está en preparación")
    db.add(Exclusion(event_id=event_id, giver_id=data.giver_id, receiver_id=data.receiver_id, mutual=data.mutual))
    db.commit()
    return {"message": "Exclusión añadida"}

@app.post("/events/{event_id}/validate")
def validate(event_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ev = db.query(Event).filter_by(id=event_id).first()
    if not ev or not db.query(EventParticipant).filter_by(event_id=event_id, user_id=user.id).first():
        raise HTTPException(403)
    user_ids = [ep.user_id for ep in ev.participants]
    ok, msg = exists_valid(user_ids, ev.exclusions)
    return {"valid": ok, "message": msg}

@app.post("/events/{event_id}/draw")
def draw(event_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ev = db.query(Event).filter_by(id=event_id, creator_id=user.id).first()
    if not ev or ev.status != StatusEnum.preparing:
        raise HTTPException(400, "No se puede sortear")
    user_ids = [ep.user_id for ep in ev.participants]
    ok, msg = exists_valid(user_ids, ev.exclusions)
    if not ok:
        raise HTTPException(400, msg)
    assignment = generate_assignment(user_ids, ev.exclusions)
    if not assignment:
        raise HTTPException(500, "Error al generar asignación")
    db.query(Assignment).filter_by(event_id=event_id).delete()
    for giver, receiver in assignment.items():
        code = secrets.token_urlsafe(8).upper()[:8]
        db.add(Assignment(event_id=event_id, giver_id=giver, receiver_id=receiver, private_code=code))
    ev.status = StatusEnum.drawn
    db.commit()
    return {"message": "Sorteo realizado"}

@app.get("/events/{event_id}/my-assignment")
def my_assignment(event_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ass = db.query(Assignment).filter_by(event_id=event_id, giver_id=user.id).first()
    if not ass:
        raise HTTPException(404, "Aún no hay asignación o no participas")
    receiver = db.query(User).get(ass.receiver_id)
    return {
        "receiver_alias": receiver.alias or receiver.full_name,
        "private_code": ass.private_code
    }

@app.get("/result/{code}")
def public_result(code: str, db: Session = Depends(get_db)):
    ass = db.query(Assignment).filter_by(private_code=code.upper()).first()
    if not ass:
        raise HTTPException(404, "Código no válido")
    giver = db.query(User).get(ass.giver_id)
    receiver = db.query(User).get(ass.receiver_id)
    ev = ass.event
    return {
        "your_alias": giver.alias or giver.full_name,
        "receiver_alias": receiver.alias or receiver.full_name,
        "event_name": ev.name
    }

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/{full_path:path}")
def spa(full_path: str):
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
