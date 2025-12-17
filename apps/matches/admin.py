from django.contrib import admin
from .models import (
    Turf, Match, MatchJoinRequest, MatchPlayer,
    Transaction, Club, Bowler, NetMateBooking
)


@admin.register(Turf)
class TurfAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'address', 'price_per_hour', 'is_available_instant', 'created_at']
    list_filter = ['is_available_instant', 'created_at']
    search_fields = ['name', 'address', 'owner__name', 'owner__phone']
    ordering = ['-created_at']


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'captain', 'turf', 'match_date', 'start_time', 
        'format', 'total_spots', 'spots_filled', 'status', 'created_at'
    ]
    list_filter = ['status', 'format', 'required_skill_level', 'match_date', 'created_at']
    search_fields = ['captain__name', 'captain__phone', 'turf__name']
    ordering = ['-match_date', '-start_time']
    readonly_fields = ['spots_filled', 'created_at', 'updated_at']


@admin.register(MatchJoinRequest)
class MatchJoinRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'match', 'player', 'status', 'deposit_paid', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['player__name', 'player__phone', 'match__id']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(MatchPlayer)
class MatchPlayerAdmin(admin.ModelAdmin):
    list_display = ['id', 'match', 'player', 'final_amount_paid', 'has_checked_in', 'created_at']
    list_filter = ['has_checked_in', 'created_at']
    search_fields = ['player__name', 'player__phone', 'match__id']
    ordering = ['-created_at']
    readonly_fields = ['created_at']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'match', 'amount', 'type', 'is_successful', 'created_at']
    list_filter = ['type', 'is_successful', 'created_at']
    search_fields = ['user__name', 'user__phone', 'razorpay_payment_id']
    ordering = ['-created_at']
    readonly_fields = ['created_at']


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ['name', 'captain', 'home_turf', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'captain__name']
    filter_horizontal = ['members']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Bowler)
class BowlerAdmin(admin.ModelAdmin):
    list_display = ['user', 'bowling_style', 'rate_30min', 'rate_60min', 'rating', 'is_available', 'created_at']
    list_filter = ['bowling_style', 'is_available', 'created_at']
    search_fields = ['user__name', 'user__phone']
    ordering = ['-rating']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(NetMateBooking)
class NetMateBookingAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'batsman', 'bowler', 'date', 'start_time', 
        'duration', 'total_amount', 'status', 'created_at'
    ]
    list_filter = ['status', 'duration', 'date', 'created_at']
    search_fields = ['batsman__name', 'bowler__user__name', 'society_address']
    ordering = ['-date', '-start_time']
    readonly_fields = ['created_at', 'updated_at']

