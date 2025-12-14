import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime, timedelta

from ..db.session import get_db
from ..db import models


router = APIRouter()


@router.get("/donations")
async def get_donations(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Get all donations."""
    donations = db.query(models.Donation).order_by(models.Donation.created_at.desc()).all()

    result = []
    for donation in donations:
        result.append({
            "id": donation.id,
            "donor_phone": donation.donor_phone,
            "food_type": donation.food_type,
            "qty": donation.qty,
            "expires_at": donation.expires_at,
            "location": donation.location,
            "status": donation.status,
            "created_at": donation.created_at.isoformat() if donation.created_at else None
        })

    return result


@router.get("/organizations")
async def get_organizations(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Get all organizations."""
    organizations = db.query(models.Organization).order_by(models.Organization.created_at.desc()).all()

    result = []
    for org in organizations:
        result.append({
            "id": org.id,
            "name": org.name,
            "phone": org.phone,
            "coverage_area": org.coverage_area,
            "can_pickup": org.can_pickup,
            "hours": org.hours,
            "active": org.active,
            "created_at": org.created_at.isoformat() if org.created_at else None
        })

    return result


@router.get("/active-distributions")
async def get_active_distributions(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Get active food distributions."""
    # Get distributions that haven't expired
    active_distributions = db.query(models.ActiveDistribution).filter(
        models.ActiveDistribution.status == models.DistributionStatus.ACTIVE,
        models.ActiveDistribution.expires_at > datetime.utcnow()
    ).order_by(models.ActiveDistribution.created_at.desc()).all()

    result = []
    for dist in active_distributions:
        result.append({
            "id": dist.id,
            "volunteer_phone": dist.volunteer_phone,
            "food_type": dist.food_type,
            "qty": dist.qty,
            "location": dist.location,
            "expires_at": dist.expires_at.isoformat() if dist.expires_at else None,
            "status": dist.status,
            "created_at": dist.created_at.isoformat() if dist.created_at else None
        })

    return result


@router.get("/matches")
async def get_matches(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Get all matches."""
    matches = db.query(models.Match).join(
        models.Donation, models.Match.donation_id == models.Donation.id
    ).join(
        models.Organization, models.Match.org_id == models.Organization.id
    ).order_by(models.Match.created_at.desc()).all()

    result = []
    for match in matches:
        result.append({
            "id": match.id,
            "donation": {
                "id": match.donation.id,
                "food_type": match.donation.food_type,
                "location": match.donation.location,
                "status": match.donation.status
            },
            "organization": {
                "id": match.organization.id,
                "name": match.organization.name,
                "phone": match.organization.phone
            },
            "status": match.status,
            "created_at": match.created_at.isoformat() if match.created_at else None
        })

    return result


@router.get("/metrics")
async def get_metrics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get system metrics."""
    # Total donations
    total_donations = db.query(models.Donation).count()

    # Active distributions
    total_active_distributions = db.query(models.ActiveDistribution).filter(
        models.ActiveDistribution.status == models.DistributionStatus.ACTIVE,
        models.ActiveDistribution.expires_at > datetime.utcnow()
    ).count()

    # Total organizations
    total_organizations = db.query(models.Organization).filter(
        models.Organization.active == True
    ).count()

    # Estimate meals served (rough calculation)
    # Assume average 2 meals per donation and 5 meals per active distribution
    meals_from_donations = total_donations * 2
    meals_from_distributions = total_active_distributions * 5
    estimated_meals = meals_from_donations + meals_from_distributions

    # Estimate food waste prevented (rough calculation in kg)
    # Assume average 2kg per donation
    waste_prevented_kg = total_donations * 2

    # Recent activity (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_donations = db.query(models.Donation).filter(
        models.Donation.created_at > week_ago
    ).count()

    recent_distributions = db.query(models.ActiveDistribution).filter(
        models.ActiveDistribution.created_at > week_ago
    ).count()

    return {
        "total_donations": total_donations,
        "total_active_distributions": total_active_distributions,
        "total_organizations": total_organizations,
        "estimated_meals_served": estimated_meals,
        "estimated_waste_prevented_kg": waste_prevented_kg,
        "recent_donations_7d": recent_donations,
        "recent_distributions_7d": recent_distributions,
        "generated_at": datetime.utcnow().isoformat()
    }


@router.get("/conversation-state/{phone}")
async def get_conversation_state(phone: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Debug: get conversation state and temp_json for a phone."""
    state = db.query(models.ConversationState).filter(models.ConversationState.phone == phone).first()
    if not state:
        raise HTTPException(status_code=404, detail="Not found")

    raw_temp = state.temp_json
    temp: Dict[str, Any] = {}
    if isinstance(raw_temp, str):
        try:
            loaded = json.loads(raw_temp)
            temp = loaded if isinstance(loaded, dict) else {}
        except Exception:
            temp = {}
    elif isinstance(raw_temp, dict):
        temp = dict(raw_temp)

    return {
        "phone": state.phone,
        "state": state.state,
        "temp_json": temp,
        "updated_at": state.updated_at,
    }