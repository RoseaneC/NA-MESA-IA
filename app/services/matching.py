from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from ..db import models
from ..core.logging import logger
from .whatsapp import whatsapp_service
from .normalization import normalize_neighborhood


class MatchingService:
    def __init__(self, db: Session):
        self.db = db

    def match_donation(self, donation: models.Donation) -> Optional[models.Match]:
        """Find the best organization match for a donation."""
        # Get active organizations
        organizations = self.db.query(models.Organization).filter(
            models.Organization.active == True
        ).all()

        if not organizations:
            logger.info("No active organizations found for matching")
            return None

        # Score organizations based on criteria
        scored_orgs = []
        donation_neighborhood = normalize_neighborhood(donation.location)

        for org in organizations:
            score = 0

            # Coverage area match (highest priority)
            if org.coverage_area:
                org_areas = [normalize_neighborhood(area.strip())
                           for area in org.coverage_area.split(',')]
                if donation_neighborhood in org_areas:
                    score += 10

            # Can pickup (medium priority)
            if org.can_pickup:
                score += 5

            # Has operating hours
            if org.hours:
                score += 2

            scored_orgs.append((org, score))

        # Sort by score descending
        scored_orgs.sort(key=lambda x: x[1], reverse=True)

        # Get top match
        if scored_orgs and scored_orgs[0][1] > 0:
            best_org, score = scored_orgs[0]

            # Create match
            match = models.Match(
                donation_id=donation.id,
                org_id=best_org.id,
                status=models.MatchStatus.SUGGESTED
            )

            self.db.add(match)
            self.db.commit()
            self.db.refresh(match)

            # Notify organization
            self._notify_organization(best_org, donation)

            logger.info(f"Created match: donation {donation.id} -> org {best_org.id} (score: {score})")
            return match

        logger.info(f"No suitable match found for donation {donation.id}")
        return None

    def find_best_recipients(self, donation: models.Donation, limit: int = 3) -> List[models.Organization]:
        """Return top-N candidate organizations for a donation without creating matches."""
        organizations = self.db.query(models.Organization).filter(
            models.Organization.active == True
        ).all()

        if not organizations:
            return []

        scored_orgs = []
        donation_neighborhood = normalize_neighborhood(donation.location)

        for org in organizations:
            score = 0

            if org.coverage_area:
                org_areas = [normalize_neighborhood(area.strip())
                           for area in org.coverage_area.split(',')]
                if donation_neighborhood in org_areas:
                    score += 10

            if org.can_pickup:
                score += 5

            if org.hours:
                score += 2

            scored_orgs.append((org, score))

        scored_orgs.sort(key=lambda x: x[1], reverse=True)
        top_orgs = [org for org, score in scored_orgs if score > 0]
        return top_orgs[:limit]

    def _notify_organization(self, org: models.Organization, donation: models.Donation) -> None:
        """Send WhatsApp notification to organization about suggested match."""
        message = f"""🍽️ NOVA DOAÇÃO DISPONÍVEL!

📍 Comida: {donation.food_type}
📦 Quantidade: {donation.qty}
🏠 Local: {donation.location}
⏰ Válido até: {donation.expires_at}

Responda com:
✅ ACEITAR - para confirmar a coleta
❌ RECUSAR - para rejeitar esta doação

Ou ignore para decidir depois."""

        whatsapp_service.send_message(org.phone, message)

    def process_org_response(self, org_phone: str, response: str) -> bool:
        """Process organization's response to a match suggestion."""
        response_lower = response.lower().strip()

        # Find pending match for this organization
        match = self.db.query(models.Match).join(models.Organization).filter(
            models.Organization.phone == org_phone,
            models.Match.status == models.MatchStatus.SUGGESTED
        ).first()

        if not match:
            return False

        if "aceitar" in response_lower or "✅" in response:
            # Accept match
            match.status = models.MatchStatus.ACCEPTED
            match.donation.status = models.DonationStatus.MATCHED

            # Notify donor
            self._notify_donor_acceptance(match)

            logger.info(f"Match accepted: {match.id}")
            self.db.commit()
            return True

        elif "recusar" in response_lower or "❌" in response:
            # Reject match
            match.status = models.MatchStatus.REJECTED

            # Try to find another match
            self.match_donation(match.donation)

            logger.info(f"Match rejected: {match.id}")
            self.db.commit()
            return True

        return False

    def _notify_donor_acceptance(self, match: models.Match) -> None:
        """Notify donor that their donation was accepted."""
        org = match.organization
        donation = match.donation

        message = f"""🎉 SUA DOAÇÃO FOI ACEITA!

🏢 Organização: {org.name}
📞 Contato: {org.phone}
📍 Local de coleta: {donation.location}

A organização entrará em contato em breve para combinar os detalhes."""

        whatsapp_service.send_message(donation.donor_phone, message)

    def get_active_distributions(self, neighborhood: Optional[str] = None) -> List[models.ActiveDistribution]:
        """Get active food distributions, optionally filtered by neighborhood."""
        query = self.db.query(models.ActiveDistribution).filter(
            models.ActiveDistribution.status == models.DistributionStatus.ACTIVE,
            models.ActiveDistribution.expires_at > datetime.utcnow()
        )

        if neighborhood:
            normalized_neighborhood = normalize_neighborhood(neighborhood)
            # Simple location matching - could be improved
            query = query.filter(
                models.ActiveDistribution.location.ilike(f"%{normalized_neighborhood}%")
            )

        return query.all()


