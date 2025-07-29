from flask import Flask, render_template, url_for, request, redirect, flash, session
from datetime import datetime
from pytz import timezone, UTC
from babel.numbers import format_currency
from sqlalchemy import func
from models import db, User, Lot, Spot, Reserve
from flask_login import LoginManager, login_user, login_required, logout_user, current_user

app = Flask(__name__)
db_name = 'ParkingLotLatest.db'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_name}?check_same_thread=False'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '8b15fe3d465f7a5550d1ca63460601f6'
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

with app.app_context():
    db.create_all()
    admin_user = User.query.filter_by(email='admin@gmail.com').first()
    if not admin_user:
        admin_user = User(username='admin', email='admin@gmail.com', is_admin=True,)
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()
        print('Admin user created')
    else:
        print('Admin user already exist')

@app.context_processor
def inject_user():
    return dict(current_user=current_user)

# @app.before_request
# def make_session_non_permanent():
#     session.permanent = False

# @app.before_request
# def clear_session_on_restart():
#     session.clear()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        logout_user()
        flash("You were logged out because you accessed the login page directly.", "info")
        return redirect(url_for('login'))  # reload login page after logout

    if request.method == 'POST':
        uemail = request.form['uemail']
        upassword = request.form['upassword']

        user = User.query.filter_by(email=uemail).first()
        if user and user.check_password(upassword):
            login_user(user)
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('user_dashboard'))
        else:
            session.pop('_flashes', None)
            flash('Invalid credentials','danger')
            return redirect(url_for('login'))

    return render_template('Auth/LoginPage.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        uemail = request.form['uemail']
        username = request.form['username']
        upassword = request.form['upassword']


        existing_user = User.query.filter_by(email=uemail).first()
        if existing_user:
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))

        # Basic validations
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, uemail):
            flash("Invalid email format.", "danger")
            return redirect(url_for('register'))

        # if len(upassword) < 6:
        #     flash("Password must be at least 6 characters.", "danger")
        #     return redirect(url_for('register'))

        # if len(upassword) > 10:
        #     flash("Password should not be greater than 10 characters.", "danger")
        #     return redirect(url_for('register'))

        new_user = User(is_admin=False, username=username, email=uemail,)
        new_user.set_password(upassword)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful!', 'success')
        return redirect(url_for('login'))

    return render_template('Auth/RegisterPage.html')


@app.route("/admin/dashboard")
@login_required
def admin_dashboard():
    session.pop('_flashes', None)
    users = User.query.filter_by(is_admin=False)
    lots = Lot.query.all()

    total_revenue = (
        db.session.query(func.sum(Reserve.cost))
        .filter(Reserve.leaving_ts != None)
        .scalar()
    ) or 0

    formatted_revenue = format_currency(total_revenue, 'INR', locale='en_IN')

    labels = []
    occupied = []
    available = []
    for lot in lots:
        total = len(lot.booking_lot)
        occ = len([s for s in lot.booking_lot if s.status])
        labels.append(lot.locationName)
        occupied.append(occ)
        available.append(total - occ)

    return render_template('Admin/AdminDashboard.html', users=users, lots=lots, labels=labels, occupied=occupied, available=available, total_revenue=formatted_revenue)


@app.route("/admin/parking-lots/add", methods=['GET', 'POST'])
@login_required
def add_parking_lot():
    if request.method == 'POST':
        locationName = request.form['locationName']
        price = request.form['price']
        address = request.form['address']
        pincode = request.form['pincode']
        maxSpots = request.form['maxSpots']

        existing_lot = Lot.query.filter_by(locationName=locationName).first()
        if existing_lot:
            flash('Lot already exist', 'danger')
            return redirect(url_for('add_parking_lot'))

        new_lot = Lot(locationName=locationName, price=price, address=address, pincode=pincode, maxSpots=maxSpots,)
        db.session.add(new_lot)
        db.session.flush()

        lot_id = new_lot.id
        db.session.commit()

        for i in range(int(maxSpots)):
            spot = Spot(lot_id=lot_id)
            db.session.add(spot)

        db.session.commit()

        flash('Lot added successful!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('Admin/CreateLotPage.html')


@app.route('/admin/parking-lots/<int:lot_id>/edit', methods=['GET', 'POST'])
@login_required  # Optional: Admin only
def edit_lot(lot_id):
    lot = Lot.query.get_or_404(lot_id)

    if request.method == 'POST':
        try:
            lot.locationName = request.form['locationName']
            lot.price = request.form['price']
            lot.address = request.form['address']
            lot.pincode = request.form['pincode']
            new_max_spots = int(request.form['maxSpots'])
            original_max_spots = lot.maxSpots

            if new_max_spots < 0:
                flash("Invalid value. Spot count must be 0 or more.", "warning")
                return redirect(url_for('edit_parking_lot', lot_id=lot.id))

            # Case 1: Increase → Add new Spot rows
            if new_max_spots > original_max_spots:
                # Add new spots
                for _ in range(new_max_spots - original_max_spots):
                    new_spot = Spot(lot_id=lot.id)
                    db.session.add(new_spot)

            elif new_max_spots < original_max_spots:
                # Remove unreserved spots if safe
                removable_spots = Spot.query.filter_by(lot_id=lot.id, reserve_id=None)\
                                            .order_by(Spot.id.desc())\
                                            .limit(original_max_spots - new_max_spots).all()

                if len(removable_spots) < (original_max_spots - new_max_spots):
                    flash("Not enough unreserved spots to reduce maxSpots.", "warning")
                    return redirect(url_for('edit_lot', lot_id=lot.id))

                for spot in removable_spots:
                    db.session.delete(spot)

            lot.maxSpots = new_max_spots
            db.session.commit()
            flash("Lot and spots updated successfully.", "success")
            return redirect(url_for('admin_dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f"Error updating lot: {str(e)}", "danger")

    return render_template('Admin/EditLotPage.html', lot=lot)


@app.route('/admin/parking-lots/<int:lot_id>/delete', methods=['POST'])
@login_required  # Optional: Admin only
def delete_lot(lot_id):
    lot = Lot.query.get_or_404(lot_id)

    # Get all related spots for the lot
    spots = Spot.query.filter_by(lot_id=lot.id).all()

    # Check if any spot has a non-null reserve_id
    has_reservation = any(spot.reserve_id is not None for spot in spots)

    if has_reservation:
        print("Flash should appear now")
        flash("Cannot delete lot. It contains reserved parking spots.", "warning")
        return redirect(url_for("admin_dashboard"))

    # If all spots are unreserved, delete the lot (and optionally its spots)
    try:
        # Delete all related spots first if cascade is not set
        for spot in spots:
            db.session.delete(spot)

        db.session.delete(lot)
        db.session.commit()
        flash("Lot and unreserved spots deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting lot: {str(e)}", "danger")

    return redirect(url_for("admin_dashboard"))



@app.route('/user/book-spot')
@login_required
def book_spot():
    available_lots = Lot.query.join(Spot)\
        .filter(Spot.reserve_id == None)\
        .distinct(Lot.id)\
        .all()

    return render_template('User/BookParking.html', lots=available_lots)


@app.route('/user/book-spot', methods=['POST'])
@login_required
def confirm_booking():
    if request.method == 'POST':
        lot_id = request.form['lot']
        vehicle_no = request.form['vehicleNo']

        spot = Spot.query.filter(Spot.lot_id==lot_id, Spot.status==False).first()
        spot_id = spot.id

        if spot.status:
            flash("Spot already booked!", "danger")
            return redirect(url_for('user_dashboard'))


        # Create reservation
        reservation = Reserve(
            spot_id=spot.id,
            user_id=current_user.id,
            vehicleNo=vehicle_no
        )
        db.session.add(reservation)
        db.session.flush()  # to get reservation.id before commit

        # Update spot status
        spot.status = True
        spot.reserve_id = reservation.id
        spot.user_id = current_user.id

        db.session.commit()
        return redirect(url_for('user_dashboard'))


@app.route('/user/release/<int:release_id>')
@login_required
def release_parking(release_id):
    reservation = Reserve.query.get_or_404(release_id)
    if reservation.user_id != current_user.id:
        flash("Unauthorized release!", "danger")
        return redirect(url_for('user_dashboard'))

    # Current time in IST
    ist = timezone('Asia/Kolkata')
    leaving_ts = datetime.utcnow().replace(tzinfo=UTC).astimezone(ist)
    reservation.leaving_ts = leaving_ts

    # # Compute cost
    now = datetime.now()
    duration_hours = (now - reservation.parking_ts).total_seconds() / 3600
    duration_hours = max(1, round(duration_hours))  # minimum 1 hour
    price = reservation.spot_reserved.lot_booked.price
    reservation.cost = duration_hours * price

    # Free the spot
    spot = Spot.query.get(reservation.spot_id)
    spot.status = False
    spot.reserve_id = None
    spot.user_id = None

    db.session.commit()
    return redirect(url_for('user_dashboard'))

@app.route("/admin/parking-lots/<int:lot_id>/spots")
@login_required
def spots(lot_id):
    print(lot_id)
    spots = Spot.query.filter_by(lot_id=lot_id)
    lot = Lot.query.get_or_404(lot_id)
    return render_template('Admin/SpotPage.html', spots=spots, lot=lot)

@app.route("/user/dashboard")
@login_required
def user_dashboard():
    booked_spots = Reserve.query.filter_by(user_id=current_user.id)
    lots = Lot.query.all()
    lot_stats = []
    for lot in lots:
        total_spots = len(lot.booking_lot)
        occupied_spots = len([spot for spot in lot.booking_lot if spot.status])
        available_spots = total_spots - occupied_spots
        if int(total_spots) - int(occupied_spots) == 0:
            status = False
        else:
            status = True

        lot_stats.append({
            'lot': lot,
            'total': total_spots,
            'occupied': occupied_spots,
            'available': available_spots,
            'status': status
        })

    return render_template('User/UserDashboard.html', booked_spots=booked_spots, lot_stats=lot_stats)


if __name__ =="__main__":
    app.run(debug=True)