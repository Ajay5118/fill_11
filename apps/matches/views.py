# apps/matches/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import math

from .models import Match, Vacancy, Venue, GroundCheckin, EscrowTransaction
from .serializers import (
    MatchSerializer,
    MatchListSerializer,
    VacancySerializer,
    VenueSerializer,
    GroundCheckinSerializer,
    EscrowTransactionSerializer,
    JoinVacancySerializer,
    GPSCheckinSerializer,
    AddVacancySerializer,
)


# ==================== UTILITY FUNCTIONS ====================

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees).
    Returns distance in meters.

    Formula:
    a = sin²(Δφ/2) + cos φ1 ⋅ cos φ2 ⋅ sin²(Δλ/2)
    c = 2 ⋅ atan2(√a, √(1−a))
    d = R ⋅ c

    where φ is latitude, λ is longitude, R is earth's radius (6371 km)
    """
    # Radius of the Earth in meters
    R = 6371000

    # Convert decimal degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c

    return distance


# ==================== PERMISSIONS ====================

class IsMatchCaptain(IsAuthenticated):
    """
    Custom permission to only allow captains of a match to edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any authenticated user
        if request.method in ['GET', 'HEAD', 'OPTIONS']:
            return True

        # Write permissions are only allowed to the captain
        return obj.host_team.captain == request.user


# ==================== VENUE VIEWSET ====================

class VenueViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Venue CRUD operations
    """
    queryset = Venue.objects.all()
    serializer_class = VenueSerializer

    def get_permissions(self):
        """
        Allow anyone to view venues, but only authenticated users to create
        """
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def nearby(self, request):
        """
        Get venues near a specific location
        Query params: lat, long, radius (in km, default 5)
        """
        try:
            user_lat = float(request.query_params.get('lat'))
            user_long = float(request.query_params.get('long'))
            radius_km = float(request.query_params.get('radius', 5))
        except (TypeError, ValueError):
            return Response(
                {"error": "Invalid lat, long, or radius parameters"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get all venues and calculate distances
        venues = Venue.objects.all()
        nearby_venues = []

        for venue in venues:
            distance = calculate_haversine_distance(
                user_lat, user_long,
                venue.gps_lat, venue.gps_long
            )

            if distance <= radius_km * 1000:  # Convert km to meters
                venue_data = VenueSerializer(venue).data
                venue_data['distance_meters'] = round(distance, 2)
                nearby_venues.append(venue_data)

        # Sort by distance
        nearby_venues.sort(key=lambda x: x['distance_meters'])

        return Response(nearby_venues)


# ==================== VACANCY VIEWSET ====================

class VacancyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Vacancy CRUD operations
    """
    queryset = Vacancy.objects.select_related('match', 'match__venue').all()
    serializer_class = VacancySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Filter vacancies based on query parameters
        """
        queryset = super().get_queryset()

        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Filter by match
        match_id = self.request.query_params.get('match_id')
        if match_id:
            queryset = queryset.filter(match__match_id=match_id)

        # Only open vacancies
        only_open = self.request.query_params.get('only_open')
        if only_open and only_open.lower() == 'true':
            queryset = queryset.filter(status='OPEN')

        return queryset.order_by('-created_at')


# ==================== MATCH VIEWSET ====================

class MatchViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Match CRUD operations with custom actions
    """
    queryset = Match.objects.select_related(
        'host_team', 'host_team__captain', 'visitor_team', 'venue'
    ).prefetch_related('vacancies').all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """Use different serializers for list and detail views"""
        if self.action == 'list':
            return MatchListSerializer
        return MatchSerializer

    def get_permissions(self):
        """
        Allow anyone to view matches, but only authenticated users for other actions
        """
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """
        Filter matches based on query parameters
        """
        queryset = super().get_queryset()

        # Filter upcoming matches
        upcoming = self.request.query_params.get('upcoming')
        if upcoming and upcoming.lower() == 'true':
            queryset = queryset.filter(
                start_time__gt=timezone.now(),
                is_cancelled=False
            )

        # Filter by ground status
        ground_status = self.request.query_params.get('ground_status')
        if ground_status:
            queryset = queryset.filter(ground_status=ground_status)

        # Filter by venue
        venue_id = self.request.query_params.get('venue_id')
        if venue_id:
            queryset = queryset.filter(venue__venue_id=venue_id)

        return queryset.order_by('-start_time')

    def perform_create(self, serializer):
        """
        Override to set the host team captain to the current user
        """
        serializer.save()

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def add_vacancy(self, request, pk=None):
        """
        Add a vacancy to a match. Only the captain can perform this action.

        POST /api/matches/{match_id}/add_vacancy/
        Body: {
            "looking_for_role": "BATSMAN",
            "count_needed": 2,
            "cost_per_head": 200
        }
        """
        match = self.get_object()

        # Check if the user is the captain of the host team
        if match.host_team.captain != request.user:
            return Response(
                {"error": "Only the match captain can add vacancies"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Validate input
        serializer = AddVacancySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Create vacancy
        vacancy = Vacancy.objects.create(
            match=match,
            looking_for_role=serializer.validated_data['looking_for_role'],
            count_needed=serializer.validated_data['count_needed'],
            cost_per_head=serializer.validated_data['cost_per_head'],
            status='OPEN'
        )

        vacancy_serializer = VacancySerializer(vacancy)
        return Response(
            {
                "message": "Vacancy added successfully",
                "vacancy": vacancy_serializer.data
            },
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def join_vacancy(self, request, pk=None):
        """
        Join a vacancy by creating an escrow transaction.

        POST /api/matches/{match_id}/join_vacancy/
        Body: {
            "vacancy_id": "uuid-here"
        }
        """
        match = self.get_object()

        # Validate input
        serializer = JoinVacancySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        vacancy_id = serializer.validated_data['vacancy_id']

        try:
            with transaction.atomic():
                # Get the vacancy with row-level locking to prevent race conditions
                vacancy = Vacancy.objects.select_for_update().get(
                    vacancy_id=vacancy_id,
                    match=match
                )

                # Check if vacancy is still open and has slots
                if vacancy.status != 'OPEN':
                    return Response(
                        {"error": "This vacancy is not open"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                if vacancy.filled_count >= vacancy.count_needed:
                    return Response(
                        {"error": "This vacancy is already full"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Check if user already joined this vacancy
                existing_transaction = EscrowTransaction.objects.filter(
                    match=match,
                    payer=request.user,
                    status='HELD'
                ).first()

                if existing_transaction:
                    return Response(
                        {"error": "You have already joined this match"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Create escrow transaction
                escrow = EscrowTransaction.objects.create(
                    match=match,
                    payer=request.user,
                    amount=Decimal(vacancy.cost_per_head),
                    status='HELD',
                    release_condition=f"Match completion or captain approval"
                )

                # Decrement count_needed and increment filled_count
                vacancy.filled_count += 1

                # Mark as filled if all slots are taken
                if vacancy.filled_count >= vacancy.count_needed:
                    vacancy.status = 'FILLED'

                vacancy.save()

                # Serialize response
                escrow_serializer = EscrowTransactionSerializer(escrow)
                vacancy_serializer = VacancySerializer(vacancy)

                return Response(
                    {
                        "message": "Successfully joined the vacancy",
                        "escrow_transaction": escrow_serializer.data,
                        "vacancy": vacancy_serializer.data,
                        "slots_remaining": max(0, vacancy.count_needed - vacancy.filled_count)
                    },
                    status=status.HTTP_201_CREATED
                )

        except Vacancy.DoesNotExist:
            return Response(
                {"error": "Vacancy not found for this match"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def gps_checkin(self, request, pk=None):
        """
        Perform GPS check-in to verify physical presence at venue.
        Uses Haversine formula to calculate distance.

        POST /api/matches/{match_id}/gps_checkin/
        Body: {
            "user_lat": 17.4485,
            "user_long": 78.3908
        }
        """
        match = self.get_object()

        # Validate input
        serializer = GPSCheckinSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_lat = serializer.validated_data['user_lat']
        user_long = serializer.validated_data['user_long']

        # Get venue coordinates
        venue = match.venue
        venue_lat = venue.gps_lat
        venue_long = venue.gps_long

        # Calculate distance using Haversine formula
        distance = calculate_haversine_distance(
            user_lat, user_long,
            venue_lat, venue_long
        )

        # Check if user is within 50 meters
        is_successful = distance < 50

        # Create check-in record
        checkin = GroundCheckin.objects.create(
            match=match,
            user=request.user,
            user_lat=user_lat,
            user_long=user_long,
            is_successful=is_successful,
            distance_from_venue=distance
        )

        # If successful, update match ground status to SECURED
        if is_successful:
            match.ground_status = 'SECURED'
            match.save()

            checkin_serializer = GroundCheckinSerializer(checkin)
            return Response(
                {
                    "message": "Check-in successful! Ground status updated to SECURED.",
                    "distance_meters": round(distance, 2),
                    "check_in": checkin_serializer.data
                },
                status=status.HTTP_200_OK
            )
        else:
            # Calculate how far they need to move
            distance_needed = distance - 50

            checkin_serializer = GroundCheckinSerializer(checkin)
            return Response(
                {
                    "error": "Check-in failed. You are too far from the venue.",
                    "distance_meters": round(distance, 2),
                    "distance_needed": round(distance_needed, 2),
                    "message": f"You need to be within 50 meters. You are {round(distance, 2)} meters away.",
                    "check_in": checkin_serializer.data
                },
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def my_participation(self, request, pk=None):
        """
        Check if the current user has joined this match

        GET /api/matches/{match_id}/my_participation/
        """
        match = self.get_object()

        # Check for escrow transaction
        escrow = EscrowTransaction.objects.filter(
            match=match,
            payer=request.user
        ).first()

        # Check for check-in
        checkin = GroundCheckin.objects.filter(
            match=match,
            user=request.user
        ).first()

        data = {
            "is_participant": escrow is not None,
            "has_checked_in": checkin is not None and checkin.is_successful,
            "escrow_status": escrow.status if escrow else None,
            "amount_held": float(escrow.amount) if escrow else 0
        }

        return Response(data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def cancel_match(self, request, pk=None):
        """
        Cancel a match (only captain can do this)
        Refunds all escrow transactions

        POST /api/matches/{match_id}/cancel_match/
        """
        match = self.get_object()

        # Check if user is the captain
        if match.host_team.captain != request.user:
            return Response(
                {"error": "Only the match captain can cancel the match"},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if match has already started
        if match.start_time <= timezone.now():
            return Response(
                {"error": "Cannot cancel a match that has already started"},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            # Mark match as cancelled
            match.is_cancelled = True
            match.save()

            # Refund all escrow transactions
            escrows = EscrowTransaction.objects.filter(
                match=match,
                status='HELD'
            )

            refund_count = 0
            for escrow in escrows:
                escrow.refund_payment()
                refund_count += 1

            # Mark all vacancies as expired
            match.vacancies.update(status='EXPIRED')

        return Response(
            {
                "message": "Match cancelled successfully",
                "refunds_processed": refund_count
            },
            status=status.HTTP_200_OK
        )


# ==================== ESCROW VIEWSET ====================

class EscrowTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing escrow transactions (read-only)
    """
    queryset = EscrowTransaction.objects.select_related(
        'match', 'payer', 'match__venue'
    ).all()
    serializer_class = EscrowTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Users can only see their own transactions
        """
        return super().get_queryset().filter(payer=self.request.user)