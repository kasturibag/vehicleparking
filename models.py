from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

import pytz
def get_ist_time():
    return datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Asia/Kolkata'))

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    user_bookings = db.relationship('Reserve', back_populates='booked_by', lazy=True)

    def is_authenticated(self):
        return True

    def get_id(self):
        return str(self.id)

    def get_username(self):
        return str(self.username)

    def is_active(self):
       return True

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)


class Lot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    locationName = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    pincode = db.Column(db.String(10), nullable=False)
    maxSpots = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)

    booking_lot = db.relationship('Spot', back_populates='lot_booked', lazy=True)


class Spot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('lot.id'), nullable=False)
    reserve_id = db.Column(db.Integer, db.ForeignKey('reserve.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    status = db.Column(db.Boolean, default=False)  # False = Available, True = Booked

    lot_booked = db.relationship('Lot', back_populates='booking_lot')
    reserve = db.relationship('Reserve', foreign_keys=[reserve_id], back_populates='reserved_booking')
    reserve_history = db.relationship('Reserve', back_populates='spot_reserved', foreign_keys='Reserve.spot_id')


class Reserve(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('spot.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    vehicleNo = db.Column(db.String(20), nullable=False)
    parking_ts = db.Column(db.DateTime, default=get_ist_time)
    leaving_ts = db.Column(db.DateTime, nullable=True)
    cost = db.Column(db.Float, default=0)
    location = db.Column(db.String(200), nullable=False)
    spotNo = db.Column(db.Integer, nullable=False)

    booked_by = db.relationship('User', back_populates='user_bookings')
    reserved_booking = db.relationship('Spot', foreign_keys='Spot.reserve_id', back_populates='reserve')
    spot_reserved = db.relationship('Spot', back_populates='reserve_history', foreign_keys=[spot_id])

