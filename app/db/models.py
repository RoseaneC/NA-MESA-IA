from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from .base import Base


class UserRole(str, Enum):
    DONOR = "donor"
    ORG = "org"
    SEEKER = "seeker"
    VOLUNTEER = "volunteer"
    UNKNOWN = "unknown"


class DonationStatus(str, Enum):
    PENDING = "pending"
    MATCHED = "matched"
    COLLECTED = "collected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class DistributionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class MatchStatus(str, Enum):
    SUGGESTED = "suggested"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True, nullable=False)
    role = Column(String, nullable=False, default=UserRole.UNKNOWN)
    name = Column(String, nullable=True)
    neighborhood = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    organizations = relationship("Organization", back_populates="user")


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    phone = Column(String, unique=True, index=True, nullable=False)
    coverage_area = Column(Text, nullable=True)
    can_pickup = Column(Boolean, default=False)
    hours = Column(Text, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="organizations")
    matches = relationship("Match", back_populates="organization")


class Donation(Base):
    __tablename__ = "donations"

    id = Column(Integer, primary_key=True, index=True)
    donor_phone = Column(String, nullable=False)
    food_type = Column(Text, nullable=False)
    qty = Column(Text, nullable=False)
    expires_at = Column(Text, nullable=False)
    location = Column(Text, nullable=False)
    status = Column(String, nullable=False, default=DonationStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    matches = relationship("Match", back_populates="donation")


class ActiveDistribution(Base):
    __tablename__ = "active_distributions"

    id = Column(Integer, primary_key=True, index=True)
    volunteer_phone = Column(String, nullable=False)
    food_type = Column(Text, nullable=False)
    qty = Column(Text, nullable=False)
    location = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    status = Column(String, nullable=False, default=DistributionStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.utcnow)


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    donation_id = Column(Integer, ForeignKey("donations.id"), nullable=False)
    org_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    status = Column(String, nullable=False, default=MatchStatus.SUGGESTED)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    donation = relationship("Donation", back_populates="matches")
    organization = relationship("Organization", back_populates="matches")


class ConversationState(Base):
    __tablename__ = "conversation_state"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, index=True, nullable=False)
    # Estado legado
    state = Column(String, nullable=False)
    temp_json = Column(JSON, nullable=True)
    # Novo formato
    current_flow = Column(String, nullable=False, default="MENU")
    current_step = Column(String, nullable=False, default="MENU")
    payload = Column(JSON, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ProcessedMessage(Base):
    __tablename__ = "processed_messages"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)