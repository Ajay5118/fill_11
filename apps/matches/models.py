from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from phonenumber_field.modelfields import PhoneNumberField
import uuid

User = get_user_model()


class Turf(models.Model):
    """Turf/Venue model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_turfs')
    address = models.TextField()
    # Explicit GPS fields for distance calculations
    gps_lat = models.FloatField(null=True, blank=True)
    gps_long = models.FloatField(null=True, blank=True)
    location = models.JSONField(default=dict, help_text='{"lat": 17.3850, "lng": 78.4867}')
    VENUE_TYPE_CHOICES = [
        ('BOX', 'Box'),
        ('OPEN', 'Open Ground'),
    ]
    venue_type = models.CharField(max_length=20, choices=VENUE_TYPE_CHOICES, default='BOX')
    BOOKING_MODE_CHOICES = [
        ('INSTANT', 'Instant Booking'),
        ('REQUEST', 'Captain Request'),
    ]
    booking_mode = models.CharField(max_length=20, choices=BOOKING_MODE_CHOICES, default='REQUEST')
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2)
    images = models.JSONField(default=list, help_text='List of image URLs')
    is_available_instant = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.address}"


class Club(models.Model):
    """Micro-clubs to stop WhatsApp leakage"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    captain = models.ForeignKey(User, on_delete=models.CASCADE, related_name='captained_clubs')
    members = models.ManyToManyField(User, related_name='clubs', blank=True)
    logo = models.ImageField(upload_to='club_logos/', blank=True, null=True)
    home_turf = models.ForeignKey(Turf, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} (Captain: {self.captain.name})"


class Match(models.Model):
    """Match model - Captain creates match"""
    FORMAT_CHOICES = [
        ('TENNIS', 'Tennis Ball'),
        ('LEATHER', 'Leather Ball'),
        ('BOX', 'Box Cricket'),
    ]
    MATCH_TYPE_CHOICES = [
        ('SOLO_MIX', 'Solo Mix'),
        ('TEAM_VS_TEAM', 'Team vs Team'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('ONGOING', 'Ongoing'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    GROUND_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SECURED', 'Secured'),
        ('BOOKED', 'Booked'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    captain = models.ForeignKey(User, on_delete=models.CASCADE, related_name='captained_matches')
    turf = models.ForeignKey(Turf, on_delete=models.CASCADE, related_name='matches')
    # Optional team vs team structure
    host_team = models.ForeignKey('Club', on_delete=models.SET_NULL, null=True, blank=True, related_name='hosted_matches')
    visitor_team = models.ForeignKey('Club', on_delete=models.SET_NULL, null=True, blank=True, related_name='visitor_matches')
    match_type = models.CharField(max_length=20, choices=MATCH_TYPE_CHOICES, default='SOLO_MIX')
    match_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    format = models.CharField(max_length=20, choices=FORMAT_CHOICES, default='TENNIS')
    total_spots = models.PositiveIntegerField(default=16)
    spots_filled = models.PositiveIntegerField(default=0)
    max_join_allowed = models.PositiveIntegerField(default=20, help_text='Overbooking allowed')
    required_skill_level = models.CharField(
        max_length=20, 
        choices=User.SKILL_LEVEL_CHOICES, 
        default='BEGINNER'
    )
    price_per_player = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    ground_status = models.CharField(max_length=20, choices=GROUND_STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.format} Match at {self.turf.name} on {self.match_date}"
    
    def can_accept_more_players(self):
        """Check if match can accept more join requests (overbooking)"""
        return self.spots_filled < self.max_join_allowed
    
    def is_full(self):
        """Check if match is at capacity"""
        return self.spots_filled >= self.total_spots


class MatchJoinRequest(models.Model):
    """Join request from player to match"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='join_requests')
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name='join_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    deposit_paid = models.DecimalField(max_digits=10, decimal_places=2, default=250.00)
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['match', 'player']  # One request per player per match
    
    def __str__(self):
        return f"{self.player.name} -> {self.match} ({self.status})"


class MatchPlayer(models.Model):
    """Confirmed players after approval"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='players')
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name='match_participations')
    final_amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    has_checked_in = models.BooleanField(default=False, help_text='GPS check-in at turf')
    check_in_location = models.JSONField(default=dict, blank=True, null=True, help_text='GPS coordinates')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['match', 'player']
    
    def __str__(self):
        return f"{self.player.name} in {self.match}"


class Transaction(models.Model):
    """Transaction model for payments"""
    TYPE_CHOICES = [
        ('DEPOSIT', 'Deposit'),
        ('BOOKING', 'Booking Fee'),
        ('REFUND', 'Refund'),
        ('BONUS', 'Bonus Credit'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    match = models.ForeignKey(Match, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    razorpay_payment_id = models.CharField(max_length=255, blank=True, null=True)
    is_successful = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.type} - ₹{self.amount} - {self.user.name}"


class Bowler(models.Model):
    """Bowler model for NetMate feature"""
    BOWLING_STYLE_CHOICES = [
        ('FAST', 'Fast'),
        ('MEDIUM', 'Medium'),
        ('SPIN', 'Spin'),
        ('ALL', 'All Styles'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='bowler_profile')
    bowling_style = models.CharField(max_length=20, choices=BOWLING_STYLE_CHOICES, default='ALL')
    rate_30min = models.DecimalField(max_digits=10, decimal_places=2)
    rate_60min = models.DecimalField(max_digits=10, decimal_places=2)
    available_areas = models.JSONField(default=list, help_text='List of areas where bowler is available')
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.00, validators=[MinValueValidator(1.00), MaxValueValidator(5.00)])
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-rating']
    
    def __str__(self):
        return f"{self.user.name} - {self.bowling_style} Bowler"


class NetMateBooking(models.Model):
    """NetMate booking - Book a bowler for net practice"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('ONGOING', 'Ongoing'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    DURATION_CHOICES = [
        (30, '30 minutes'),
        (60, '60 minutes'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batsman = models.ForeignKey(User, on_delete=models.CASCADE, related_name='netmate_bookings')
    bowler = models.ForeignKey(Bowler, on_delete=models.CASCADE, related_name='bookings')
    date = models.DateField()
    start_time = models.TimeField()
    duration = models.PositiveIntegerField(choices=DURATION_CHOICES, default=30)
    society_address = models.TextField()
    location = models.JSONField(default=dict, help_text='GPS coordinates')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    deposit_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    razorpay_order_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.batsman.name} booked {self.bowler.user.name} on {self.date}"


class Vacancy(models.Model):
    """Vacancy/job post for a match"""
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('FILLED', 'Filled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='vacancies')
    role_needed = models.CharField(max_length=20, choices=User.SKILL_ROLE_CHOICES, default='ANY')
    count_needed = models.PositiveIntegerField()
    cost_per_head = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Vacancy for {self.role_needed} in {self.match} ({self.status})"


class EscrowTransaction(models.Model):
    """Escrow to safely hold player payments"""
    STATUS_CHOICES = [
        ('HELD', 'Held'),
        ('RELEASED', 'Released'),
        ('REFUNDED', 'Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='escrow_transactions')
    payer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='escrow_transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='HELD')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Escrow {self.status} - ₹{self.amount} for {self.match}"


class GroundCheckin(models.Model):
    """GPS verification log at the venue"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='ground_checkins')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ground_checkins')
    user_lat = models.FloatField()
    user_long = models.FloatField()
    distance_meters = models.FloatField()
    is_successful = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        status = 'OK' if self.is_successful else 'FAILED'
        return f"{self.user} check-in for {self.match} ({status})"


class MatchScorecard(models.Model):
    """Summary scorecard for a match"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.OneToOneField(Match, on_delete=models.CASCADE, related_name='scorecard')
    winning_team_name = models.CharField(max_length=255, blank=True)
    summary_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Scorecard for {self.match}"


class PlayerMatchStat(models.Model):
    """Individual performance per match"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='player_stats')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='match_stats')
    runs = models.PositiveIntegerField(default=0)
    wickets = models.PositiveIntegerField(default=0)
    catches = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['match', 'user']

    def __str__(self):
        return f"Stats for {self.user} in {self.match}"

