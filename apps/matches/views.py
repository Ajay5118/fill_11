from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta, datetime
from django.conf import settings
from django.contrib.auth import get_user_model
import math
try:
    import razorpay
except ImportError:
    razorpay = None

from .models import (
    Turf, Match, MatchJoinRequest, MatchPlayer,
    Transaction, Club, Bowler, NetMateBooking,
    Vacancy, EscrowTransaction, GroundCheckin,
    MatchScorecard, PlayerMatchStat
)
from .serializers import (
    TurfSerializer, MatchSerializer, MatchJoinRequestSerializer,
    MatchPlayerSerializer, TransactionSerializer, ClubSerializer,
    VacancySerializer, EscrowTransactionSerializer, GroundCheckinSerializer,
    MatchScorecardSerializer, PlayerMatchStatSerializer,
    BowlerSerializer, NetMateBookingSerializer
)

User = get_user_model()


def _haversine_distance_m(lat1, lon1, lat2, lon2):
    """Return distance in meters between two GPS points."""
    # convert decimal degrees to radians
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = rlon2 - rlon1
    dlat = rlat2 - rlat1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371000  # Radius of earth in meters
    return r * c


class TurfViewSet(viewsets.ModelViewSet):
    """ViewSet for Turf management"""
    queryset = Turf.objects.all()
    serializer_class = TurfSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter turfs by location if provided"""
        queryset = super().get_queryset()
        lat = self.request.query_params.get('lat')
        lng = self.request.query_params.get('lng')
        
        # TODO: Implement distance-based filtering
        # For now, return all turfs
        
        return queryset


class MatchViewSet(viewsets.ModelViewSet):
    """ViewSet for Match management"""
    queryset = Match.objects.all()
    serializer_class = MatchSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter matches based on query parameters"""
        queryset = super().get_queryset()
        
        # Filter by status
        status_filter = self.request.query_params.get('status', 'PENDING')
        queryset = queryset.filter(status=status_filter)
        
        # Filter by date (upcoming matches)
        queryset = queryset.filter(match_date__gte=timezone.now().date())
        
        # Filter by location (if turf location provided)
        lat = self.request.query_params.get('lat')
        lng = self.request.query_params.get('lng')
        # TODO: Implement distance-based filtering
        
        # Filter by format
        format_filter = self.request.query_params.get('format')
        if format_filter:
            queryset = queryset.filter(format=format_filter)
        
        # Filter by skill level
        skill_level = self.request.query_params.get('skill_level')
        if skill_level:
            queryset = queryset.filter(required_skill_level=skill_level)
        
        return queryset.order_by('match_date', 'start_time')
    
    def perform_create(self, serializer):
        """Create match - only captain can create"""
        serializer.save(captain=self.request.user)
    
    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        """
        Player sends join request and pays deposit
        POST /api/matches/<id>/join/
        """
        match = self.get_object()
        user = request.user
        
        # Check if match can accept more players
        if not match.can_accept_more_players():
            return Response(
                {'error': 'Match is full. Maximum join requests reached.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user already sent a request
        existing_request = MatchJoinRequest.objects.filter(
            match=match,
            player=user
        ).first()
        
        if existing_request:
            if existing_request.status == 'PENDING':
                return Response(
                    {'error': 'You already have a pending request for this match.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif existing_request.status == 'APPROVED':
                return Response(
                    {'error': 'You are already approved for this match.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Check if user is the captain
        if match.captain == user:
            return Response(
                {'error': 'Captain cannot join their own match.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create Razorpay order for deposit (₹250)
        deposit_amount = 250.00
        
        # Initialize Razorpay client (you'll need to add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to settings)
        razorpay_order_id = None
        if razorpay:
            try:
                client = razorpay.Client(auth=(
                    getattr(settings, 'RAZORPAY_KEY_ID', ''),
                    getattr(settings, 'RAZORPAY_KEY_SECRET', '')
                ))
                
                order_data = {
                    'amount': int(deposit_amount * 100),  # Amount in paise
                    'currency': 'INR',
                    'receipt': f'match_{match.id}_deposit_{user.user_id}',
                    'notes': {
                        'match_id': str(match.id),
                        'user_id': str(user.user_id),
                        'type': 'deposit'
                    }
                }
                
                razorpay_order = client.order.create(data=order_data)
                razorpay_order_id = razorpay_order['id']
                
            except Exception as e:
                # If Razorpay is not configured, create order ID manually for testing
                razorpay_order_id = f'test_order_{match.id}_{user.user_id}'
        else:
            # If Razorpay is not installed, create order ID manually for testing
            razorpay_order_id = f'test_order_{match.id}_{user.user_id}'
        
        # Create join request
        join_request = MatchJoinRequest.objects.create(
            match=match,
            player=user,
            deposit_paid=deposit_amount,
            razorpay_order_id=razorpay_order_id,
            status='PENDING'
        )
        
        serializer = MatchJoinRequestSerializer(join_request)
        
        return Response({
            'message': 'Join request submitted successfully. Please complete the payment.',
            'join_request': serializer.data,
            'razorpay_order_id': razorpay_order_id,
            'amount': deposit_amount
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def add_vacancy(self, request, pk=None):
        """Captain posts a vacancy/job for this match.

        POST /api/matches/matches/{id}/add_vacancy/
        Body: {"role_needed": "BATSMAN", "count_needed": 2, "cost_per_head": 500.0}
        """
        match = self.get_object()

        if match.captain != request.user:
            return Response(
                {'error': 'Only captain can add vacancies.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = VacancySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        vacancy = serializer.save(match=match, status='OPEN')
        return Response(
            {
                'message': 'Vacancy created successfully.',
                'vacancy': VacancySerializer(vacancy).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def join_vacancy(self, request, pk=None):
        """Player pays and joins a posted vacancy.

        POST /api/matches/matches/{id}/join_vacancy/
        Body: {"vacancy_id": "..."}
        """
        match = self.get_object()
        user = request.user

        vacancy_id = request.data.get('vacancy_id')
        if not vacancy_id:
            return Response({'error': 'vacancy_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            vacancy = Vacancy.objects.get(id=vacancy_id, match=match)
        except Vacancy.DoesNotExist:
            return Response({'error': 'Vacancy not found for this match.'}, status=status.HTTP_404_NOT_FOUND)

        if vacancy.status != 'OPEN' or vacancy.count_needed <= 0:
            return Response({'error': 'Vacancy is already filled.'}, status=status.HTTP_400_BAD_REQUEST)

        # Create escrow record (payment is assumed handled by client/payment gateway)
        escrow = EscrowTransaction.objects.create(
            match=match,
            payer=user,
            amount=vacancy.cost_per_head,
            status='HELD',
        )

        # Attach player to match if not already
        match_player, created = MatchPlayer.objects.get_or_create(
            match=match,
            player=user,
            defaults={'final_amount_paid': vacancy.cost_per_head},
        )

        if created:
            match.spots_filled += 1
            match.save(update_fields=['spots_filled'])

        vacancy.count_needed -= 1
        if vacancy.count_needed <= 0:
            vacancy.status = 'FILLED'
        vacancy.save(update_fields=['count_needed', 'status'])

        return Response(
            {
                'message': 'Joined vacancy successfully. Payment held in escrow.',
                'vacancy': VacancySerializer(vacancy).data,
                'escrow': EscrowTransactionSerializer(escrow).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'])
    def gps_checkin(self, request, pk=None):
        """GPS verification for venue (King of the Hill).

        POST /api/matches/matches/{id}/gps_checkin/
        Body: {"lat": 17.3850, "lng": 78.4867}
        """
        match = self.get_object()
        user = request.user

        lat = request.data.get('lat')
        lng = request.data.get('lng')
        if lat is None or lng is None:
            return Response({'error': 'lat and lng are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            return Response({'error': 'lat and lng must be numeric.'}, status=status.HTTP_400_BAD_REQUEST)

        venue = match.turf
        venue_lat = venue.gps_lat
        venue_lng = venue.gps_long

        # Fallback to JSON location if explicit GPS not set
        if venue_lat is None or venue_lng is None:
            loc = venue.location or {}
            venue_lat = loc.get('lat') or loc.get('latitude')
            venue_lng = loc.get('lng') or loc.get('long') or loc.get('longitude')

        if venue_lat is None or venue_lng is None:
            return Response(
                {'error': 'Venue coordinates not configured.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        distance_m = _haversine_distance_m(lat, lng, float(venue_lat), float(venue_lng))
        is_success = distance_m <= 50.0

        checkin = GroundCheckin.objects.create(
            match=match,
            user=user,
            user_lat=lat,
            user_long=lng,
            distance_meters=distance_m,
            is_successful=is_success,
        )

        # Update player check-in flag if they are part of the match
        MatchPlayer.objects.filter(match=match, player=user).update(
            has_checked_in=is_success,
            check_in_location={'lat': lat, 'lng': lng},
        )

        if is_success and match.ground_status != 'SECURED':
            match.ground_status = 'SECURED'
            match.save(update_fields=['ground_status'])

        serializer = GroundCheckinSerializer(checkin)
        status_code = status.HTTP_200_OK if is_success else status.HTTP_400_BAD_REQUEST
        return Response(serializer.data, status=status_code)

    @action(detail=True, methods=['post'])
    def submit_scorecard(self, request, pk=None):
        """Captain submits scorecard and player stats.

        POST /api/matches/matches/{id}/submit_scorecard/
        Body: {
          "winning_team_name": "Team A",
          "summary_text": "Match summary...",
          "players": [
            {"user_id": "...", "runs": 30, "wickets": 2, "catches": 1},
            ...
          ]
        }
        """
        match = self.get_object()

        if match.captain != request.user:
            return Response(
                {'error': 'Only captain can submit scorecard.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        winning_team_name = request.data.get('winning_team_name', '')
        summary_text = request.data.get('summary_text', '')

        scorecard, _ = MatchScorecard.objects.update_or_create(
            match=match,
            defaults={
                'winning_team_name': winning_team_name,
                'summary_text': summary_text,
            },
        )

        players_payload = request.data.get('players', []) or []
        player_stats = []

        for item in players_payload:
            user_id = item.get('user_id')
            if not user_id:
                continue
            try:
                user = User.objects.get(user_id=user_id)
            except User.DoesNotExist:
                continue

            runs = int(item.get('runs', 0) or 0)
            wickets = int(item.get('wickets', 0) or 0)
            catches = int(item.get('catches', 0) or 0)

            stat, created = PlayerMatchStat.objects.update_or_create(
                match=match,
                user=user,
                defaults={
                    'runs': runs,
                    'wickets': wickets,
                    'catches': catches,
                },
            )
            player_stats.append(stat)

            # Update aggregate stats on user
            user.total_runs += runs
            user.total_wickets += wickets
            if created:
                user.matches_played += 1
            user.save(update_fields=['total_runs', 'total_wickets', 'matches_played'])

        # Mark match as completed
        if match.status != 'COMPLETED':
            match.status = 'COMPLETED'
            match.save(update_fields=['status'])

        # Release all held escrows for this match
        EscrowTransaction.objects.filter(match=match, status='HELD').update(status='RELEASED')

        return Response(
            {
                'message': 'Scorecard submitted successfully.',
                'scorecard': MatchScorecardSerializer(scorecard).data,
                'player_stats': PlayerMatchStatSerializer(player_stats, many=True).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['get'])
    def join_requests(self, request, pk=None):
        """Get all join requests for a match (captain only)."""
        match = self.get_object()

        if match.captain != request.user:
            return Response(
                {'error': 'Only captain can view join requests.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        join_requests = match.join_requests.all()
        serializer = MatchJoinRequestSerializer(join_requests, many=True)
        return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_join_request(request, request_id):
    """
    Captain approves a join request
    POST /api/join-requests/<id>/approve/
    """
    try:
        join_request = MatchJoinRequest.objects.get(id=request_id)
    except MatchJoinRequest.DoesNotExist:
        return Response(
            {'error': 'Join request not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check if user is the captain
    if join_request.match.captain != request.user:
        return Response(
            {'error': 'Only captain can approve join requests.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Check if request is pending
    if join_request.status != 'PENDING':
        return Response(
            {'error': f'Join request is already {join_request.status.lower()}.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if match can accept more players
    if not join_request.match.can_accept_more_players():
        return Response(
            {'error': 'Match is full. Cannot approve more players.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Approve the request
    join_request.status = 'APPROVED'
    join_request.save()
    
    # Update match spots_filled
    match = join_request.match
    match.spots_filled += 1
    match.save()
    
    # Create MatchPlayer record
    final_amount = match.price_per_player - join_request.deposit_paid
    MatchPlayer.objects.create(
        match=match,
        player=join_request.player,
        final_amount_paid=final_amount
    )
    
    # Create transaction record for deposit
    Transaction.objects.create(
        user=join_request.player,
        match=match,
        amount=join_request.deposit_paid,
        type='DEPOSIT',
        is_successful=True
    )
    
    serializer = MatchJoinRequestSerializer(join_request)
    
    return Response({
        'message': 'Join request approved successfully.',
        'join_request': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_join_request(request, request_id):
    """
    Captain rejects a join request
    POST /api/join-requests/<id>/reject/
    """
    try:
        join_request = MatchJoinRequest.objects.get(id=request_id)
    except MatchJoinRequest.DoesNotExist:
        return Response(
            {'error': 'Join request not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Check if user is the captain
    if join_request.match.captain != request.user:
        return Response(
            {'error': 'Only captain can reject join requests.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Reject the request
    join_request.status = 'REJECTED'
    join_request.save()
    
    # Refund deposit (create refund transaction)
    Transaction.objects.create(
        user=join_request.player,
        match=join_request.match,
        amount=join_request.deposit_paid,
        type='REFUND',
        is_successful=True
    )
    
    # Update user wallet
    join_request.player.wallet_balance += join_request.deposit_paid
    join_request.player.save()
    
    serializer = MatchJoinRequestSerializer(join_request)
    
    return Response({
        'message': 'Join request rejected. Deposit refunded.',
        'join_request': serializer.data
    }, status=status.HTTP_200_OK)


class NetMateBowlerListView(generics.ListAPIView):
    """List available bowlers for NetMate"""
    serializer_class = BowlerSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter bowlers by availability and location"""
        queryset = Bowler.objects.filter(is_available=True)
        
        # Filter by area if provided
        area = self.request.query_params.get('area')
        if area:
            # Filter by available_areas JSON field
            queryset = queryset.filter(available_areas__contains=[area])
        
        return queryset.order_by('-rating')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def book_netmate(request):
    """
    Book a bowler for net practice
    POST /api/netmate/book/
    Body: {
        "bowler_id": "...",
        "date": "2024-01-15",
        "start_time": "18:00:00",
        "duration": 30,
        "society_address": "...",
        "location": {"lat": 17.3850, "lng": 78.4867}
    }
    """
    serializer = NetMateBookingSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    bowler_id = serializer.validated_data['bowler'].id
    duration = serializer.validated_data['duration']
    
    try:
        bowler = Bowler.objects.get(id=bowler_id, is_available=True)
    except Bowler.DoesNotExist:
        return Response(
            {'error': 'Bowler not found or not available.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Calculate total amount
    if duration == 30:
        total_amount = bowler.rate_30min
    else:
        total_amount = bowler.rate_60min
    
    # Create Razorpay order (100% upfront payment)
    razorpay_order_id = None
    if razorpay:
        try:
            client = razorpay.Client(auth=(
                getattr(settings, 'RAZORPAY_KEY_ID', ''),
                getattr(settings, 'RAZORPAY_KEY_SECRET', '')
            ))
            
            order_data = {
                'amount': int(total_amount * 100),  # Amount in paise
                'currency': 'INR',
                'receipt': f'netmate_{bowler.id}_{request.user.user_id}',
                'notes': {
                    'bowler_id': str(bowler.id),
                    'user_id': str(request.user.user_id),
                    'type': 'netmate_booking'
                }
            }
            
            razorpay_order = client.order.create(data=order_data)
            razorpay_order_id = razorpay_order['id']
            
        except Exception as e:
            razorpay_order_id = f'test_order_netmate_{bowler.id}_{request.user.user_id}'
    else:
        razorpay_order_id = f'test_order_netmate_{bowler.id}_{request.user.user_id}'
    
    # Create booking
    booking = NetMateBooking.objects.create(
        batsman=request.user,
        bowler=bowler,
        date=serializer.validated_data['date'],
        start_time=serializer.validated_data['start_time'],
        duration=duration,
        society_address=serializer.validated_data['society_address'],
        location=serializer.validated_data['location'],
        total_amount=total_amount,
        deposit_paid=total_amount,  # 100% upfront
        razorpay_order_id=razorpay_order_id,
        status='PENDING'
    )
    
    serializer = NetMateBookingSerializer(booking)
    
    return Response({
        'message': 'Booking created successfully. Please complete the payment.',
        'booking': serializer.data,
        'razorpay_order_id': razorpay_order_id,
        'amount': total_amount
    }, status=status.HTTP_201_CREATED)

