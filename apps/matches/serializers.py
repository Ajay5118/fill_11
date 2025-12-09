# apps/matches/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Match, Vacancy, Venue, GroundCheckin, EscrowTransaction
from apps.users.models import Team

User = get_user_model()


# ==================== USER SERIALIZERS ====================

class BasicUserSerializer(serializers.ModelSerializer):
    """Basic user info for nested representations"""

    class Meta:
        model = User
        fields = ['user_id', 'full_name', 'phone_number', 'skill_level',
                  'primary_role', 'reliability_score']
        read_only_fields = fields


# ==================== VENUE SERIALIZERS ====================

class VenueSerializer(serializers.ModelSerializer):
    """Venue serializer with GPS coordinates"""

    class Meta:
        model = Venue
        fields = ['venue_id', 'name', 'venue_type', 'booking_mode',
                  'is_verified', 'gps_lat', 'gps_long',
                  'avg_cost_per_hour', 'address', 'created_at', 'updated_at']
        read_only_fields = ['venue_id', 'is_verified', 'created_at', 'updated_at']

    def validate(self, data):
        """Validate GPS coordinates"""
        if not (-90 <= data.get('gps_lat', 0) <= 90):
            raise serializers.ValidationError({"gps_lat": "Invalid latitude value"})
        if not (-180 <= data.get('gps_long', 0) <= 180):
            raise serializers.ValidationError({"gps_long": "Invalid longitude value"})
        return data


class VenueListSerializer(serializers.ModelSerializer):
    """Minimal venue info for list views"""

    class Meta:
        model = Venue
        fields = ['venue_id', 'name', 'venue_type', 'avg_cost_per_hour']


# ==================== TEAM SERIALIZERS ====================

class TeamSerializer(serializers.ModelSerializer):
    """Team serializer with captain details"""
    captain = BasicUserSerializer(read_only=True)
    captain_id = serializers.UUIDField(write_only=True, required=False)

    class Meta:
        model = Team
        fields = ['id', 'captain', 'captain_id', 'team_name', 'temp_player_count']
        read_only_fields = ['id']

    def create(self, validated_data):
        """Create team with captain from context if not provided"""
        if 'captain_id' not in validated_data:
            validated_data['captain_id'] = self.context['request'].user.user_id
        return super().create(validated_data)


# ==================== VACANCY SERIALIZERS ====================

class VacancySerializer(serializers.ModelSerializer):
    """Full vacancy serializer for CRUD operations"""
    match_details = serializers.SerializerMethodField(read_only=True)
    slots_remaining = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Vacancy
        fields = ['vacancy_id', 'match', 'looking_for_role', 'count_needed',
                  'cost_per_head', 'status', 'filled_count', 'slots_remaining',
                  'match_details', 'created_at', 'updated_at']
        read_only_fields = ['vacancy_id', 'filled_count', 'status', 'created_at', 'updated_at']

    def get_slots_remaining(self, obj):
        """Calculate remaining slots"""
        return max(0, obj.count_needed - obj.filled_count)

    def get_match_details(self, obj):
        """Return minimal match info"""
        return {
            'match_id': str(obj.match.match_id),
            'start_time': obj.match.start_time,
            'venue_name': obj.match.venue.name
        }

    def validate_count_needed(self, value):
        """Validate count needed is positive"""
        if value < 1:
            raise serializers.ValidationError("Count needed must be at least 1")
        return value

    def validate_cost_per_head(self, value):
        """Validate cost is non-negative"""
        if value < 0:
            raise serializers.ValidationError("Cost per head cannot be negative")
        return value


class VacancyNestedSerializer(serializers.ModelSerializer):
    """Nested vacancy serializer for match details"""
    slots_remaining = serializers.SerializerMethodField()

    class Meta:
        model = Vacancy
        fields = ['vacancy_id', 'looking_for_role', 'count_needed',
                  'filled_count', 'slots_remaining', 'cost_per_head', 'status']

    def get_slots_remaining(self, obj):
        return max(0, obj.count_needed - obj.filled_count)


# ==================== MATCH SERIALIZERS ====================

class MatchSerializer(serializers.ModelSerializer):
    """Full match serializer with nested relationships"""
    host_team = TeamSerializer(read_only=True)
    visitor_team = TeamSerializer(read_only=True)
    venue = VenueSerializer(read_only=True)
    vacancies = VacancyNestedSerializer(many=True, read_only=True)

    # Write-only fields for creation
    host_team_id = serializers.UUIDField(write_only=True, required=False)
    visitor_team_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    venue_id = serializers.UUIDField(write_only=True)

    is_upcoming = serializers.BooleanField(read_only=True)
    total_vacancies = serializers.SerializerMethodField()
    total_filled = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = ['match_id', 'host_team', 'host_team_id', 'visitor_team',
                  'visitor_team_id', 'venue', 'venue_id', 'match_type',
                  'ground_status', 'start_time', 'total_slots', 'is_cancelled',
                  'vacancies', 'is_upcoming', 'total_vacancies', 'total_filled',
                  'created_at', 'updated_at']
        read_only_fields = ['match_id', 'is_cancelled', 'created_at', 'updated_at']

    def get_total_vacancies(self, obj):
        """Calculate total vacancy slots"""
        return sum(v.count_needed for v in obj.vacancies.all())

    def get_total_filled(self, obj):
        """Calculate total filled slots"""
        return sum(v.filled_count for v in obj.vacancies.all())

    def validate_start_time(self, value):
        """Ensure start time is in the future"""
        from django.utils import timezone
        if value < timezone.now():
            raise serializers.ValidationError("Match start time must be in the future")
        return value

    def validate_total_slots(self, value):
        """Validate total slots range"""
        if not (1 <= value <= 22):
            raise serializers.ValidationError("Total slots must be between 1 and 22")
        return value

    def validate(self, data):
        """Cross-field validation"""
        # Ensure venue exists
        if 'venue_id' in data:
            if not Venue.objects.filter(venue_id=data['venue_id']).exists():
                raise serializers.ValidationError({"venue_id": "Venue does not exist"})

        # Auto-assign host_team from request user if not provided
        if 'host_team_id' not in data and self.context.get('request'):
            user = self.context['request'].user
            # Try to get or create a team for this user
            team, created = Team.objects.get_or_create(
                captain=user,
                defaults={'team_name': f"{user.full_name}'s Team"}
            )
            data['host_team_id'] = team.id  # Changed from team_id to id

        return data


class MatchListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views"""
    venue_name = serializers.CharField(source='venue.name', read_only=True)
    host_captain = serializers.CharField(source='host_team.captain.full_name', read_only=True)
    open_slots = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = ['match_id', 'venue_name', 'host_captain', 'match_type',
                  'ground_status', 'start_time', 'open_slots', 'is_upcoming']

    def get_open_slots(self, obj):
        """Calculate total open slots"""
        return sum(max(0, v.count_needed - v.filled_count)
                   for v in obj.vacancies.filter(status='OPEN'))


# ==================== CHECKIN SERIALIZERS ====================

class GroundCheckinSerializer(serializers.ModelSerializer):
    """Ground check-in serializer"""
    user = BasicUserSerializer(read_only=True)
    match_details = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = GroundCheckin
        fields = ['checkin_id', 'match', 'user', 'checkin_time', 'user_lat',
                  'user_long', 'is_successful', 'distance_from_venue', 'match_details']
        read_only_fields = ['checkin_id', 'checkin_time', 'is_successful',
                            'distance_from_venue']

    def get_match_details(self, obj):
        return {
            'match_id': str(obj.match.match_id),
            'venue_name': obj.match.venue.name,
            'start_time': obj.match.start_time
        }

    def validate(self, data):
        """Validate GPS coordinates"""
        if not (-90 <= data.get('user_lat', 0) <= 90):
            raise serializers.ValidationError({"user_lat": "Invalid latitude value"})
        if not (-180 <= data.get('user_long', 0) <= 180):
            raise serializers.ValidationError({"user_long": "Invalid longitude value"})
        return data


# ==================== ESCROW SERIALIZERS ====================

class EscrowTransactionSerializer(serializers.ModelSerializer):
    """Escrow transaction serializer"""
    payer = BasicUserSerializer(read_only=True)
    match_details = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = EscrowTransaction
        fields = ['escrow_id', 'match', 'payer', 'amount', 'status',
                  'release_condition', 'released_at', 'refunded_at',
                  'match_details', 'created_at']
        read_only_fields = ['escrow_id', 'status', 'released_at',
                            'refunded_at', 'created_at']

    def get_match_details(self, obj):
        return {
            'match_id': str(obj.match.match_id),
            'venue_name': obj.match.venue.name,
            'start_time': obj.match.start_time
        }


# ==================== ACTION SERIALIZERS ====================

class JoinVacancySerializer(serializers.Serializer):
    """Serializer for join_vacancy action"""
    vacancy_id = serializers.UUIDField(required=True)

    def validate_vacancy_id(self, value):
        """Validate vacancy exists and is open"""
        try:
            vacancy = Vacancy.objects.get(vacancy_id=value)
        except Vacancy.DoesNotExist:
            raise serializers.ValidationError("Vacancy does not exist")

        if vacancy.status != 'OPEN':
            raise serializers.ValidationError("This vacancy is not open")

        if vacancy.filled_count >= vacancy.count_needed:
            raise serializers.ValidationError("This vacancy is already full")

        return value


class GPSCheckinSerializer(serializers.Serializer):
    """Serializer for GPS check-in action"""
    user_lat = serializers.FloatField(required=True, min_value=-90, max_value=90)
    user_long = serializers.FloatField(required=True, min_value=-180, max_value=180)

    def validate(self, data):
        """Additional validation for GPS coordinates"""
        if data['user_lat'] == 0 and data['user_long'] == 0:
            raise serializers.ValidationError(
                "Invalid GPS coordinates. Please enable location services."
            )
        return data


class AddVacancySerializer(serializers.Serializer):
    """Serializer for add_vacancy action"""
    looking_for_role = serializers.ChoiceField(
        choices=['BATSMAN', 'BOWLER', 'ALL_ROUNDER', 'WICKET_KEEPER', 'ANY']
    )
    count_needed = serializers.IntegerField(min_value=1, max_value=11)
    cost_per_head = serializers.IntegerField(min_value=0)

    def validate(self, data):
        """Validate vacancy data"""
        if data['cost_per_head'] > 10000:
            raise serializers.ValidationError(
                {"cost_per_head": "Cost per head seems unusually high"}
            )
        return data