from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import UserProfileOut
from app.core.database import get_db
from app.models.user_profile import UserProfile

router = APIRouter(prefix="/profile", tags=["profile"])

@router.get("", response_model=UserProfileOut)
def get_profile(db: Session = Depends(get_db)):
    profile = db.query(UserProfile).first()
    if not profile:
        profile = UserProfile()
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile
