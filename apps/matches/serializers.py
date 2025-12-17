from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import (
    Turf, Match, MatchJoinRequest, MatchPlayer, 
    Transaction, Club, Bowler, NetMateBooking,
    Vacancy, EscrowTransaction, GroundCheckin,
    MatchScorecard, PlayerMatchStat
)

User = get_user_model()


class TurfSerializer(serializers.ModelSerializer):
    """Serializer for Turf model"""
    owner_name = serializers.CharField(source='owner.name', read_only=True)
    
    class Meta:
        model = Turf
        fields = [
            'id', 'name', 'owner', 'owner_name', 'address', 
            'location', 'price_per_hour', 'images', 
            'is_available_instant', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class MatchSerializer(serializers.ModelSerializer):
    """Serializer for Match model"""
    captain_name = serializers.CharField(source='captain.name', read_only=True)
    turf_name = serializers.CharField(source='turf.name', read_only=True)
    turf_address = serializers.CharField(source='turf.address', read_only=True)
    spots_remaining = serializers.SerializerMethodField()
    can_join = serializers.SerializerMethodField()
    join_requests_count = serializers.SerializerMethodField()
    vacancies = serializers.SerializerMethodField()
    
    class Meta:
        model = Match
        fields = [
            'id', 'captain', 'captain_name', 'turf', 'turf_name', 'turf_address',
            'host_team', 'visitor_team', 'match_type',
            'match_date', 'start_time', 'end_time', 'format', 'total_spots',
            'spots_filled', 'max_join_allowed', 'required_skill_level',
            'price_per_player', 'status', 'ground_status', 'spots_remaining', 'can_join',
            'join_requests_count', 'vacancies', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'spots_filled', 'status', 'ground_status', 'created_at', 'updated_at']
    
    def get_spots_remaining(self, obj):
        return max(0, obj.total_spots - obj.spots_filled)
    
    def get_can_join(self, obj):
        return obj.can_accept_more_players()
    
    def get_join_requests_count(self, obj):
        return obj.join_requests.filter(status='PENDING').count()

    def get_vacancies(self, obj):
        from .serializers import VacancySerializer  # local import to avoid circular
        qs = obj.vacancies.all().order_by('-created_at')
        return VacancySerializer(qs, many=True).data
    
    def validate(self, attrs):
        """Validate match data"""
        if 'match_date' in attrs and 'start_time' in attrs:
            match_datetime = timezone.datetime.combine(
                attrs['match_date'],
                attrs['start_time']
            )
            if match_datetime < timezone.now():
                raise serializers.ValidationError("Match date and time must be in the future")
        
        if 'start_time' in attrs and 'end_time' in attrs:
            if attrs['end_time'] <= attrs['start_time']:
                raise serializers.ValidationError("End time must be after start time")
        
        return attrs


class MatchJoinRequestSerializer(serializers.ModelSerializer):
    """Serializer for MatchJoinRequest"""
    player_name = serializers.CharField(source='player.name', read_only=True)
    player_phone = serializers.CharField(source='player.phone.as_e164', read_only=True)
    match_details = MatchSerializer(source='match', read_only=True)
    
    class Meta:
        model = MatchJoinRequest
        fields = [
            'id', 'match', 'match_details', 'player', 'player_name', 
            'player_phone', 'status', 'deposit_paid', 'razorpay_order_id',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']


class MatchPlayerSerializer(serializers.ModelSerializer):
    """Serializer for MatchPlayer"""
    player_name = serializers.CharField(source='player.name', read_only=True)
    player_phone = serializers.CharField(source='player.phone.as_e164', read_only=True)
    
    class Meta:
        model = MatchPlayer
        fields = [
            'id', 'match', 'player', 'player_name', 'player_phone',
            'final_amount_paid', 'has_checked_in', 'check_in_location', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for Transaction"""
    user_name = serializers.CharField(source='user.name', read_only=True)
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'user', 'user_name', 'match', 'amount', 'type',
            'razorpay_payment_id', 'is_successful', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ClubSerializer(serializers.ModelSerializer):
    """Serializer for Club"""
    captain_name = serializers.CharField(source='captain.name', read_only=True)
    members_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Club
        fields = [
            'id', 'name', 'captain', 'captain_name', 'members',
            'logo', 'home_turf', 'members_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_members_count(self, obj):
        return obj.members.count()


class VacancySerializer(serializers.ModelSerializer):
    """Serializer for Vacancy/job post"""

    class Meta:
        model = Vacancy
        fields = [
            'id', 'match', 'role_needed', 'count_needed',
            'cost_per_head', 'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'match', 'status', 'created_at', 'updated_at']


class EscrowTransactionSerializer(serializers.ModelSerializer):
    """Serializer for EscrowTransaction"""
    payer_name = serializers.CharField(source='payer.name', read_only=True)

    class Meta:
        model = EscrowTransaction
        fields = [
            'id', 'match', 'payer', 'payer_name', 'amount',
            'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']


class GroundCheckinSerializer(serializers.ModelSerializer):
    """Serializer for GroundCheckin"""
    user_name = serializers.CharField(source='user.name', read_only=True)

    class Meta:
        model = GroundCheckin
        fields = [
            'id', 'match', 'user', 'user_name', 'user_lat', 'user_long',
            'distance_meters', 'is_successful', 'created_at'
        ]
        read_only_fields = ['id', 'distance_meters', 'is_successful', 'created_at']


class MatchScorecardSerializer(serializers.ModelSerializer):
    """Serializer for MatchScorecard"""

    class Meta:
        model = MatchScorecard
        fields = [
            'id', 'match', 'winning_team_name', 'summary_text',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PlayerMatchStatSerializer(serializers.ModelSerializer):
    """Serializer for PlayerMatchStat"""
    user_name = serializers.CharField(source='user.name', read_only=True)

    class Meta:
        model = PlayerMatchStat
        fields = [
            'id', 'match', 'user', 'user_name', 'runs', 'wickets', 'catches',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class BowlerSerializer(serializers.ModelSerializer):
    """Serializer for Bowler"""
    user_name = serializers.CharField(source='user.name', read_only=True)
    user_phone = serializers.CharField(source='user.phone.as_e164', read_only=True)

    class Meta:
        model = Bowler
        fields = [
            'id', 'user', 'user_name', 'user_phone', 'bowling_style',
            'rate_30min', 'rate_60min', 'available_areas', 'rating',
            'is_available', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'rating', 'created_at', 'updated_at']


class NetMateBookingSerializer(serializers.ModelSerializer):
    """Serializer for NetMateBooking"""
    batsman_name = serializers.CharField(source='batsman.name', read_only=True)
    bowler_name = serializers.CharField(source='bowler.user.name', read_only=True)
    bowler_details = BowlerSerializer(source='bowler', read_only=True)

    class Meta:
        model = NetMateBooking
        fields = [
            'id', 'batsman', 'batsman_name', 'bowler', 'bowler_name', 'bowler_details',
            'date', 'start_time', 'duration', 'society_address', 'location',
            'total_amount', 'deposit_paid', 'status', 'razorpay_order_id',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']

    def validate(self, attrs):
        """Validate booking data"""
        if 'date' in attrs and 'start_time' in attrs:
            booking_datetime = timezone.datetime.combine(
                attrs['date'],
                attrs['start_time']
            )
            if booking_datetime < timezone.now():
                raise serializers.ValidationError("Booking date and time must be in the future")

        return attrs

