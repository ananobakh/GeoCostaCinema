"""
Cinema Reservation System – VS Code Edition
Run this script to create the project and start the server.
"""

import os
import sys
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import random
import string
import bcrypt
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

# ----- Configuration -----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')

for dirname in [TEMPLATE_DIR, STATIC_DIR, INSTANCE_DIR]:
    os.makedirs(dirname, exist_ok=True)

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cinema.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ----- Models -----
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    registered_on = db.Column(db.DateTime, default=datetime.utcnow)
    bookings = db.relationship('Booking', backref='user', lazy=True)
    waiting_entries = db.relationship('WaitingEntry', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

class Movie(db.Model):
    __tablename__ = 'movies'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    genre = db.Column(db.String(100))
    duration_min = db.Column(db.Integer)
    description = db.Column(db.Text)
    release_year = db.Column(db.Integer)
    rating = db.Column(db.Float)
    showtimes = db.relationship('Showtime', backref='movie', lazy=True)

class Hall(db.Model):
    __tablename__ = 'halls'
    id = db.Column(db.Integer, primary_key=True)
    hall_name = db.Column(db.String(50), nullable=False)
    rows = db.Column(db.Integer, default=5)
    cols = db.Column(db.Integer, default=8)
    is_vip = db.Column(db.Boolean, default=False)
    showtimes = db.relationship('Showtime', backref='hall', lazy=True)

class Showtime(db.Model):
    __tablename__ = 'showtimes'
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    hall_id = db.Column(db.Integer, db.ForeignKey('halls.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    base_price = db.Column(db.Float, default=5000.0)
    bookings = db.relationship('Booking', backref='showtime', lazy=True)
    waiting_list = db.relationship('WaitingEntry', backref='showtime', lazy=True)

class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    showtime_id = db.Column(db.Integer, db.ForeignKey('showtimes.id'), nullable=False)
    booking_reference = db.Column(db.String(20), unique=True, nullable=False)
    num_seats = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    seat_numbers = db.Column(db.Text)
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')
    payment_deadline = db.Column(db.DateTime)

class WaitingEntry(db.Model):
    __tablename__ = 'waiting'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    showtime_id = db.Column(db.Integer, db.ForeignKey('showtimes.id'), nullable=False)
    num_seats = db.Column(db.Integer, nullable=False)
    desired_seats = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    notified = db.Column(db.Boolean, default=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def generate_booking_ref():
    while True:
        ref = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        if not Booking.query.filter_by(booking_reference=ref).first():
            return ref

def release_expired_pending_bookings():
    with app.app_context():
        now = datetime.utcnow()
        expired = Booking.query.filter(Booking.status == 'pending', Booking.payment_deadline < now).all()
        for booking in expired:
            booking.status = 'cancelled'
            db.session.commit()
            waiting = WaitingEntry.query.filter_by(showtime_id=booking.showtime_id, notified=False).order_by(WaitingEntry.timestamp).first()
            if waiting:
                waiting.notified = True
                db.session.commit()
        db.session.commit()

scheduler = BackgroundScheduler()
scheduler.add_job(func=release_expired_pending_bookings, trigger='interval', minutes=1)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# ----- Routes -----
@app.route('/')
def index():
    today = datetime.today()
    upcoming = Showtime.query.filter(Showtime.start_time >= today).order_by(Showtime.start_time).limit(12).all()
    movies = list(set([st.movie for st in upcoming]))
    return render_template('index.html', movies=movies, upcoming=upcoming)

@app.route('/register', methods=['GET','POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        confirm = request.form['confirm_password']
        if password != confirm:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')
        if User.query.filter_by(username=username).first():
            flash('Username taken', 'danger')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return render_template('register.html')
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash(f'Welcome {user.username}!', 'success')
            if user.is_admin:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('customer_dashboard'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out', 'info')
    return redirect(url_for('index'))

@app.route('/customer_dashboard')
@login_required
def customer_dashboard():
    if current_user.is_admin:
        return redirect(url_for('admin_dashboard'))
    upcoming = Booking.query.filter(
        Booking.user_id == current_user.id,
        Booking.status.in_(('confirmed', 'pending')),
        Booking.showtime.has(Showtime.start_time >= datetime.today())
    ).order_by(Booking.showtime.has(Showtime.start_time)).all()
    past = Booking.query.filter(
        Booking.user_id == current_user.id,
        Booking.status == 'confirmed',
        Booking.showtime.has(Showtime.start_time < datetime.today())
    ).order_by(Booking.showtime.has(Showtime.start_time).desc()).limit(5).all()
    waiting = WaitingEntry.query.filter_by(user_id=current_user.id, notified=False).order_by(WaitingEntry.timestamp.desc()).all()
    notified_waiting = WaitingEntry.query.filter_by(user_id=current_user.id, notified=True).order_by(WaitingEntry.timestamp.desc()).all()
    return render_template('customer_dashboard.html', upcoming=upcoming, past=past, waiting=waiting, notified_waiting=notified_waiting)

@app.route('/movies')
def movies():
    genre = request.args.get('genre', '')
    query = Movie.query
    if genre:
        query = query.filter(Movie.genre.ilike(f'%{genre}%'))
    movies = query.all()
    all_genres = [g[0] for g in db.session.query(Movie.genre).distinct() if g[0]]
    return render_template('movies.html', movies=movies, genres=all_genres, selected_genre=genre)

@app.route('/movie/<int:movie_id>')
def movie_detail(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    showtimes = Showtime.query.filter(
        Showtime.movie_id == movie_id,
        Showtime.start_time >= datetime.today()
    ).order_by(Showtime.start_time).all()
    return render_template('movie_detail.html', movie=movie, showtimes=showtimes)

@app.route('/book_seat/<int:showtime_id>', methods=['GET','POST'])
@login_required
def book_seat(showtime_id):
    showtime = Showtime.query.get_or_404(showtime_id)
    if showtime.start_time < datetime.today():
        flash('Showtime already passed', 'danger')
        return redirect(url_for('movies'))
    booked = []
    for b in showtime.bookings:
        if b.status in ('confirmed', 'pending') and b.seat_numbers:
            booked.extend(b.seat_numbers.split(','))
    if request.method == 'POST':
        selected = request.form.get('selected_seats', '')
        if not selected:
            flash('Select at least one seat', 'warning')
            return redirect(url_for('book_seat', showtime_id=showtime_id))
        seats = selected.split(',')
        conflict = [s for s in seats if s in booked]
        if conflict:
            flash(f'Seats {", ".join(conflict)} already taken', 'danger')
            return redirect(url_for('book_seat', showtime_id=showtime_id))
        num = len(seats)
        total = num * showtime.base_price
        ref = generate_booking_ref()
        deadline = datetime.utcnow() + timedelta(minutes=15)
        booking = Booking(
            user_id=current_user.id,
            showtime_id=showtime.id,
            booking_reference=ref,
            num_seats=num,
            total_price=total,
            seat_numbers=selected,
            status='pending',
            payment_deadline=deadline
        )
        db.session.add(booking)
        db.session.commit()
        flash(f'Booking reserved! Reference: {ref}. Total: ₡{total:,.0f}. Please confirm payment within 15 minutes.', 'success')
        return redirect(url_for('my_bookings'))
    hall = showtime.hall
    matrix = []
    for r in range(hall.rows):
        row_letter = chr(ord('A')+r)
        row = []
        for c in range(hall.cols):
            sid = f"{row_letter}{c+1}"
            row.append({'id': sid, 'booked': sid in booked})
        matrix.append(row)
    return render_template('book_seat.html', showtime=showtime, seat_matrix=matrix)

@app.route('/my_bookings')
@login_required
def my_bookings():
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.booking_date.desc()).all()
    return render_template('my_bookings.html', bookings=bookings)

@app.route('/confirm_booking/<int:booking_id>', methods=['POST'])
@login_required
def confirm_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('my_bookings'))
    if booking.status != 'pending':
        flash('This booking cannot be confirmed now.', 'warning')
        return redirect(url_for('my_bookings'))
    if booking.payment_deadline < datetime.utcnow():
        flash('Payment deadline has passed. Seat released.', 'danger')
        booking.status = 'cancelled'
        db.session.commit()
        waiting = WaitingEntry.query.filter_by(showtime_id=booking.showtime_id, notified=False).order_by(WaitingEntry.timestamp).first()
        if waiting:
            waiting.notified = True
            db.session.commit()
            flash('Seat became available for someone on waiting list.', 'info')
        return redirect(url_for('my_bookings'))
    booking.status = 'confirmed'
    db.session.commit()
    flash(f'Booking {booking.booking_reference} confirmed! Enjoy the movie.', 'success')
    return redirect(url_for('my_bookings'))

@app.route('/cancel_booking/<int:booking_id>', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id and not current_user.is_admin:
        flash('Unauthorized', 'danger')
        return redirect(url_for('my_bookings'))
    if booking.showtime.start_time < datetime.today() and booking.status == 'confirmed':
        flash('Cannot cancel past showings', 'warning')
    else:
        old_status = booking.status
        booking.status = 'cancelled'
        db.session.commit()
        if old_status == 'pending':
            waiting = WaitingEntry.query.filter_by(showtime_id=booking.showtime_id, notified=False).order_by(WaitingEntry.timestamp).first()
            if waiting:
                waiting.notified = True
                db.session.commit()
                flash('Seat became available for someone on waiting list.', 'info')
        flash(f'Booking {booking.booking_reference} cancelled', 'info')
    return redirect(url_for('my_bookings'))

@app.route('/join_waiting/<int:showtime_id>', methods=['POST'])
@login_required
def join_waiting(showtime_id):
    showtime = Showtime.query.get_or_404(showtime_id)
    if showtime.start_time < datetime.today():
        flash('Showtime already passed', 'danger')
        return redirect(url_for('movies'))
    num = int(request.form.get('num_seats', 1))
    if WaitingEntry.query.filter_by(user_id=current_user.id, showtime_id=showtime_id).first():
        flash('Already on waiting list', 'warning')
        return redirect(url_for('movie_detail', movie_id=showtime.movie.id))
    waiting = WaitingEntry(user_id=current_user.id, showtime_id=showtime_id, num_seats=num)
    db.session.add(waiting)
    db.session.commit()
    flash('Added to waiting list. You will be notified when seats become available.', 'info')
    return redirect(url_for('movie_detail', movie_id=showtime.movie.id))

# ----- Admin Routes -----
@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    total_users = User.query.count()
    total_movies = Movie.query.count()
    total_bookings = Booking.query.filter_by(status='confirmed').count()
    total_revenue = db.session.query(db.func.sum(Booking.total_price)).filter_by(status='confirmed').scalar() or 0
    recent = Booking.query.filter_by(status='confirmed').order_by(Booking.booking_date.desc()).limit(10).all()
    pending = Booking.query.filter_by(status='pending').count()
    waiting_count = WaitingEntry.query.filter_by(notified=False).count()
    return render_template('admin_dashboard.html', total_users=total_users, total_movies=total_movies,
                           total_bookings=total_bookings, total_revenue=total_revenue, recent=recent,
                           pending=pending, waiting_count=waiting_count)

@app.route('/admin/waiting_list')
@login_required
def admin_waiting_list():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    waiting_entries = WaitingEntry.query.order_by(WaitingEntry.timestamp).all()
    return render_template('admin_waiting_list.html', waiting=waiting_entries)

@app.route('/admin/movies')
@login_required
def admin_movies():
    if not current_user.is_admin: return redirect(url_for('index'))
    movies = Movie.query.order_by(Movie.title).all()
    return render_template('admin_movies.html', movies=movies)

@app.route('/admin/movies/add', methods=['GET','POST'])
@login_required
def add_movie():
    if not current_user.is_admin: return redirect(url_for('index'))
    if request.method == 'POST':
        movie = Movie(
            title=request.form['title'],
            genre=request.form['genre'],
            duration_min=int(request.form['duration']),
            description=request.form['description'],
            release_year=int(request.form['year']),
            rating=float(request.form.get('rating',0))
        )
        db.session.add(movie)
        db.session.commit()
        flash('Movie added', 'success')
        return redirect(url_for('admin_movies'))
    return render_template('add_movie.html')

@app.route('/admin/movies/delete/<int:movie_id>')
@login_required
def delete_movie(movie_id):
    if not current_user.is_admin: return redirect(url_for('index'))
    movie = Movie.query.get_or_404(movie_id)
    db.session.delete(movie)
    db.session.commit()
    flash('Movie deleted', 'warning')
    return redirect(url_for('admin_movies'))

@app.route('/admin/showtimes')
@login_required
def admin_showtimes():
    if not current_user.is_admin: return redirect(url_for('index'))
    showtimes = Showtime.query.order_by(Showtime.start_time).all()
    movies = Movie.query.all()
    halls = Hall.query.all()
    return render_template('admin_showtimes.html', showtimes=showtimes, movies=movies, halls=halls)

@app.route('/admin/showtimes/add', methods=['POST'])
@login_required
def add_showtime():
    if not current_user.is_admin: return redirect(url_for('index'))
    movie = Movie.query.get(request.form['movie_id'])
    start = datetime.strptime(request.form['start_time'], '%Y-%m-%dT%H:%M')
    end = start + timedelta(minutes=movie.duration_min)
    st = Showtime(
        movie_id=movie.id,
        hall_id=request.form['hall_id'],
        start_time=start,
        end_time=end,
        base_price=float(request.form['base_price'])
    )
    db.session.add(st)
    db.session.commit()
    flash('Showtime added', 'success')
    return redirect(url_for('admin_showtimes'))

@app.route('/admin/showtimes/delete/<int:showtime_id>')
@login_required
def delete_showtime(showtime_id):
    if not current_user.is_admin: return redirect(url_for('index'))
    st = Showtime.query.get_or_404(showtime_id)
    db.session.delete(st)
    db.session.commit()
    flash('Showtime deleted', 'info')
    return redirect(url_for('admin_showtimes'))

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin: return redirect(url_for('index'))
    users = User.query.all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/promote/<int:user_id>')
@login_required
def promote_user(user_id):
    if not current_user.is_admin: return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    if user.id != current_user.id:
        user.is_admin = True
        db.session.commit()
        flash(f'{user.username} is now admin', 'success')
    else:
        flash('Cannot promote yourself', 'warning')
    return redirect(url_for('admin_users'))

@app.route('/admin/users/delete/<int:user_id>')
@login_required
def delete_user(user_id):
    if not current_user.is_admin: return redirect(url_for('index'))
    user = User.query.get_or_404(user_id)
    if user.id != current_user.id:
        db.session.delete(user)
        db.session.commit()
        flash('User deleted', 'warning')
    else:
        flash('Cannot delete yourself', 'danger')
    return redirect(url_for('admin_users'))

def seed_data():
    with app.app_context():
        if Movie.query.count() == 0:
            m1 = Movie(title='Inception', genre='Sci-Fi', duration_min=148, description='Dream within a dream', release_year=2010, rating=8.8)
            m2 = Movie(title='The Dark Knight', genre='Action', duration_min=152, description='Batman vs Joker', release_year=2008, rating=9.0)
            m3 = Movie(title='Parasite', genre='Thriller', duration_min=132, description='Class satire', release_year=2019, rating=8.6)
            db.session.add_all([m1,m2,m3])
            h1 = Hall(hall_name='Main Hall', rows=5, cols=8, is_vip=False)
            h2 = Hall(hall_name='VIP Hall', rows=4, cols=6, is_vip=True)
            db.session.add_all([h1,h2])
            db.session.commit()
            today = datetime.today().replace(hour=10, minute=0, second=0, microsecond=0)
            for i in range(3):
                st1 = Showtime(movie_id=m1.id, hall_id=h1.id, start_time=today+timedelta(days=i), end_time=today+timedelta(days=i, minutes=148), base_price=5000)
                st2 = Showtime(movie_id=m2.id, hall_id=h2.id, start_time=today+timedelta(days=i, hours=15), end_time=today+timedelta(days=i, hours=15, minutes=152), base_price=7000)
                db.session.add_all([st1,st2])
            db.session.commit()
            admin = User(username='admin', email='admin@cinema.com', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()

# ----- Write Templates (auto-create all HTML files) -----
templates_content = {
    'base.html': '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎬 CineMagic</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
    <nav class="navbar">
        <div class="container">
            <a href="/" class="brand">🎬 CineMagic</a>
            <ul class="nav-links">
                <li><a href="{{ url_for('movies') }}">🎞️ Movies</a></li>
                {% if current_user.is_authenticated %}
                    {% if current_user.is_admin %}<li><a href="{{ url_for('admin_dashboard') }}">⚙️ Admin</a></li>{% endif %}
                    <li><a href="{{ url_for('my_bookings') }}">🎟️ My Bookings</a></li>
                    <li><a href="{{ url_for('logout') }}">🚪 Logout ({{ current_user.username }})</a></li>
                {% else %}
                    <li><a href="{{ url_for('login') }}">🔐 Login</a></li>
                    <li><a href="{{ url_for('register') }}">📝 Register</a></li>
                {% endif %}
            </ul>
        </div>
    </nav>
    <div class="container main-content">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}{% for cat, msg in messages %}<div class="alert alert-{{ cat }}">{{ msg }}</div>{% endfor %}{% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </div>
    <footer><div class="container"><p>✨ CineMagic – Smart Cinema Reservation ✨</p></div></footer>
    <script src="{{ url_for('static', filename='script.js') }}"></script>
</body>
</html>''',
    'index.html': '{% extends "base.html" %}{% block content %}<h1 style="color:white; text-shadow:2px 2px 4px rgba(0,0,0,0.3);">🎬 Now Showing</h1><div class="movie-grid">{% for movie in movies %}<div class="movie-card"><h3>{{ movie.title }}</h3><p>🎭 {{ movie.genre }} | 📅 {{ movie.release_year }}</p><p>⭐ {{ movie.rating }}/10</p><a href="{{ url_for("movie_detail", movie_id=movie.id) }}" class="btn">🎟️ Book now</a></div>{% endfor %}</div>{% endblock %}',
    'login.html': '{% extends "base.html" %}{% block content %}<div style="max-width:400px; margin:40px auto; background:white; padding:30px; border-radius:24px;"><h2>🔐 Login</h2><form method="POST"><input name="username" placeholder="Username" required><input type="password" name="password" placeholder="Password" required><button type="submit">Sign in</button></form><p style="margin-top:15px;">New user? <a href="{{ url_for("register") }}">Create account</a></p></div>{% endblock %}',
    'register.html': '{% extends "base.html" %}{% block content %}<div style="max-width:400px; margin:40px auto; background:white; padding:30px; border-radius:24px;"><h2>📝 Register</h2><form method="POST"><input name="username" placeholder="Username" required><input name="email" type="email" placeholder="Email" required><input type="password" name="password" placeholder="Password" required><input type="password" name="confirm_password" placeholder="Confirm Password" required><button type="submit">Sign up</button></form><p>Already have an account? <a href="{{ url_for("login") }}">Login</a></p></div>{% endblock %}',
    'movies.html': '{% extends "base.html" %}{% block content %}<h2 style="color:white;">🎞️ All Movies</h2><form method="GET" style="background:rgba(255,255,255,0.2); padding:15px; border-radius:20px; margin-bottom:20px;"><select name="genre"><option value="">All Genres</option>{% for g in genres %}<option value="{{ g }}" {% if selected_genre==g %}selected{% endif %}>{{ g }}</option>{% endfor %}</select><button type="submit">Filter</button></form><div class="movie-grid">{% for m in movies %}<div class="movie-card"><h3>{{ m.title }}</h3><p>{{ m.genre }} | {{ m.release_year }} | ⭐{{ m.rating }}</p><a href="{{ url_for("movie_detail", movie_id=m.id) }}" class="btn">Details</a></div>{% endfor %}</div>{% endblock %}',
    'movie_detail.html': '{% extends "base.html" %}{% block content %}<div style="background:white; border-radius:24px; padding:25px; margin-bottom:20px;"><h2>{{ movie.title }} ({{ movie.release_year }})</h2><p><strong>⭐ Rating:</strong> {{ movie.rating }}/10</p><p><strong>🎭 Genre:</strong> {{ movie.genre }}</p><p><strong>⏱️ Duration:</strong> {{ movie.duration_min }} min</p><p><strong>📖 Description:</strong> {{ movie.description }}</p></div><h3 style="color:white;">📅 Showtimes</h3>{% for st in showtimes %}<div style="background:white; border-radius:16px; padding:15px; margin:10px 0; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;"><div><strong>{{ st.start_time.strftime("%Y-%m-%d %H:%M") }}</strong> – Hall: {{ st.hall.hall_name }} – 💰 ₡{{ st.base_price }}</div><div><a href="{{ url_for("book_seat", showtime_id=st.id) }}" class="btn">🎫 Book</a><form method="POST" action="{{ url_for("join_waiting", showtime_id=st.id) }}" style="display:inline;"><input type="hidden" name="num_seats" value="1"><button style="background:#f39c12;">⏳ Join Waiting List</button></form></div></div>{% else %}<p style="color:white;">No upcoming showtimes.</p>{% endfor %}{% endblock %}',
    'book_seat.html': '{% extends "base.html" %}{% block content %}<div style="background:rgba(255,255,255,0.9); border-radius:24px; padding:20px;"><h2>🎭 Select Seats for {{ showtime.movie.title }}</h2><p><strong>{{ showtime.start_time.strftime("%Y-%m-%d %H:%M") }}</strong> – {{ showtime.hall.hall_name }}</p><form method="POST" id="seatForm"><div class="seat-map">{% for row in seat_matrix %}<div class="seat-row">{% for seat in row %}<div class="seat {% if seat.booked %}booked{% endif %}" data-seat-id="{{ seat.id }}" onclick="toggleSeat(this, \'{{ seat.id }}\')">{{ seat.id }}</div>{% endfor %}</div>{% endfor %}</div><input type="hidden" name="selected_seats" id="selected_seats"><p><strong>Selected seats:</strong> <span id="selected_count">0</span></p><button type="submit">✨ Reserve (15 min to pay)</button></form></div><script>let selected=[]; function toggleSeat(el,sid){if(el.classList.contains("booked")) return; if(selected.includes(sid)){selected=selected.filter(s=>s!==sid);el.classList.remove("selected");}else{selected.push(sid);el.classList.add("selected");} document.getElementById("selected_seats").value=selected.join(","); document.getElementById("selected_count").innerText=selected.length;}</script>{% endblock %}',
    'my_bookings.html': '{% extends "base.html" %}{% block content %}<h2 style="color:white;">🎟️ My Bookings</h2>{% for b in bookings %}<div class="booking-card"><strong>{{ b.booking_reference }}</strong><br>🎬 {{ b.showtime.movie.title }}<br>💺 Seats: {{ b.seat_numbers }}<br>💰 Total: ₡{{ b.total_price }}<br>📅 {{ b.showtime.start_time.strftime("%Y-%m-%d %H:%M") }}<br>Status: <span class="status-badge status-{{ b.status }}">{{ b.status }}</span><br>{% if b.status == "pending" %}<small>⏳ Pay before {{ b.payment_deadline.strftime("%H:%M:%S") }}</small><form method="POST" action="{{ url_for("confirm_booking", booking_id=b.id) }}" style="display:inline;"><button>✅ Confirm Payment</button></form>{% endif %}<form method="POST" action="{{ url_for("cancel_booking", booking_id=b.id) }}" style="display:inline;"><button style="background:#e74c3c;">❌ Cancel</button></form></div>{% endfor %}{% endblock %}',
    'customer_dashboard.html': '{% extends "base.html" %}{% block content %}<h2 style="color:white;">👋 Welcome, {{ current_user.username }}!</h2><h3>📌 Upcoming & Pending</h3>{% if upcoming %}{% for b in upcoming %}<div class="booking-card"><strong>{{ b.booking_reference }}</strong> – {{ b.showtime.movie.title }} – {{ b.num_seats }} seats – ₡{{ b.total_price }}<br>{{ b.showtime.start_time.strftime("%Y-%m-%d %H:%M") }}<br>Status: <span class="status-badge status-{{ b.status }}">{{ b.status }}</span>{% if b.status == "pending" %} – <form method="POST" action="{{ url_for("confirm_booking", booking_id=b.id) }}" style="display:inline;"><button>Confirm</button></form>{% endif %}<form method="POST" action="{{ url_for("cancel_booking", booking_id=b.id) }}" style="display:inline;"><button>Cancel</button></form></div>{% endfor %}{% else %}<p>No upcoming bookings.</p>{% endif %}<h3>📜 Past Bookings</h3>{% if past %}{% for b in past %}<div>{{ b.booking_reference }} – {{ b.showtime.movie.title }}</div>{% endfor %}{% else %}<p>None</p>{% endif %}<h3>⏳ Waiting List</h3>{% if waiting %}<ul>{% for w in waiting %}<li>{{ w.showtime.movie.title }} – {{ w.num_seats }} seat(s) – requested {{ w.timestamp.strftime("%Y-%m-%d") }}</li>{% endfor %}</ul>{% endif %}{% if notified_waiting %}<h4>🔔 Notified (seats available)</h4><ul>{% for w in notified_waiting %}<li>{{ w.showtime.movie.title }} – go to movie page to book</li>{% endfor %}</ul>{% endif %}{% endblock %}',
    'admin_dashboard.html': '{% extends "base.html" %}{% block content %}<h2>⚙️ Admin Dashboard</h2><div class="stats"><div class="stat-card"><div class="stat-number">{{ total_users }}</div><div>Users</div></div><div class="stat-card"><div class="stat-number">{{ total_movies }}</div><div>Movies</div></div><div class="stat-card"><div class="stat-number">{{ total_bookings }}</div><div>Confirmed Bookings</div></div><div class="stat-card"><div class="stat-number">₡{{ total_revenue }}</div><div>Revenue</div></div><div class="stat-card"><div class="stat-number">{{ pending }}</div><div>Pending Payments</div></div><div class="stat-card"><div class="stat-number">{{ waiting_count }}</div><div>Waiting List</div></div></div><h3>Recent Bookings</h3><ul>{% for b in recent %}<li>{{ b.booking_reference }} – {{ b.user.username }} – ₡{{ b.total_price }}</li>{% endfor %}</ul><div class="admin-links"><a href="{{ url_for("admin_movies") }}" class="btn">🎬 Movies</a><a href="{{ url_for("admin_showtimes") }}" class="btn">⏰ Showtimes</a><a href="{{ url_for("admin_users") }}" class="btn">👥 Users</a><a href="{{ url_for("admin_waiting_list") }}" class="btn">📋 Waiting List</a></div>{% endblock %}',
    'admin_movies.html': '{% extends "base.html" %}{% block content %}<h2>🎬 Manage Movies</h2><a href="{{ url_for("add_movie") }}" class="btn">+ Add Movie</a><ul>{% for m in movies %}<li><strong>{{ m.title }}</strong> ({{ m.release_year }}) – <a href="{{ url_for("delete_movie", movie_id=m.id) }}" onclick="return confirm(\'Delete?\')">Delete</a></li>{% endfor %}</ul>{% endblock %}',
    'add_movie.html': '{% extends "base.html" %}{% block content %}<div style="max-width:500px; background:white; padding:25px; border-radius:24px;"><h2>➕ Add New Movie</h2><form method="POST"><input name="title" placeholder="Title" required><input name="genre" placeholder="Genre"><input name="duration" type="number" placeholder="Duration (min)"><textarea name="description" placeholder="Description"></textarea><input name="year" type="number" placeholder="Year"><input name="rating" step="0.1" placeholder="Rating"><button type="submit">Add Movie</button></form></div>{% endblock %}',
    'admin_showtimes.html': '{% extends "base.html" %}{% block content %}<h2>⏰ Showtimes</h2><form method="POST" action="{{ url_for("add_showtime") }}" style="background:white; padding:20px; border-radius:24px;"><select name="movie_id">{% for m in movies %}<option value="{{ m.id }}">{{ m.title }}</option>{% endfor %}</select><select name="hall_id">{% for h in halls %}<option value="{{ h.id }}">{{ h.hall_name }}</option>{% endfor %}</select><input type="datetime-local" name="start_time" required><input type="number" name="base_price" step="100" value="5000"><button type="submit">Add Showtime</button></form><ul>{% for st in showtimes %}<li>{{ st.movie.title }} at {{ st.start_time.strftime("%Y-%m-%d %H:%M") }} – {{ st.hall.hall_name }} – <a href="{{ url_for("delete_showtime", showtime_id=st.id) }}" onclick="return confirm(\'Delete?\')">Delete</a></li>{% endfor %}</ul>{% endblock %}',
    'admin_users.html': '{% extends "base.html" %}{% block content %}<h2>👥 Users</h2><ul>{% for u in users %}<li><strong>{{ u.username }}</strong> ({{ u.email }}) – Admin: {{ u.is_admin }} – <a href="{{ url_for("promote_user", user_id=u.id) }}">Make Admin</a> – <a href="{{ url_for("delete_user", user_id=u.id) }}" onclick="return confirm(\'Delete?\')">Delete</a></li>{% endfor %}</ul>{% endblock %}',
    'admin_waiting_list.html': '{% extends "base.html" %}{% block content %}<h2>📋 Waiting List</h2><table><tr><th>User</th><th>Movie</th><th>Showtime</th><th>Seats</th><th>Requested at</th><th>Notified</th></tr>{% for w in waiting %}<tr><td>{{ w.user.username }}</td><td>{{ w.showtime.movie.title }}</td><td>{{ w.showtime.start_time.strftime("%Y-%m-%d %H:%M") }}</td><td>{{ w.num_seats }}</td><td>{{ w.timestamp.strftime("%Y-%m-%d %H:%M") }}</td><td>{{ "Yes" if w.notified else "No" }}</td></tr>{% endfor %}</table>{% endblock %}'
}

for filename, content in templates_content.items():
    with open(os.path.join(TEMPLATE_DIR, filename), 'w', encoding='utf-8') as f:
        f.write(content)

# ----- Write CSS and JS -----
css_content = """
:root {
    --primary: #6c5ce7;
    --primary-dark: #5a4ad1;
    --secondary: #00cec9;
    --danger: #e74c3c;
    --success: #00b894;
    --warning: #fdcb6e;
    --dark: #2d3436;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: 'Segoe UI', system-ui; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
.container { max-width: 1280px; margin: 0 auto; padding: 20px; }
.navbar { background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); box-shadow: 0 4px 20px rgba(0,0,0,0.1); position: sticky; top: 0; z-index: 1000; border-bottom: 3px solid var(--primary); }
.navbar .container { display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; }
.brand { font-size: 1.8rem; font-weight: 800; background: linear-gradient(135deg, var(--primary), var(--secondary)); -webkit-background-clip: text; background-clip: text; color: transparent; text-decoration: none; }
.nav-links { list-style: none; display: flex; gap: 25px; align-items: center; }
.nav-links a { text-decoration: none; color: var(--dark); font-weight: 600; transition: 0.3s; padding: 8px 12px; border-radius: 8px; }
.nav-links a:hover { background: var(--primary); color: white; }
.movie-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 30px; margin-top: 30px; }
.movie-card { background: white; border-radius: 20px; overflow: hidden; box-shadow: 0 10px 25px rgba(0,0,0,0.1); transition: transform 0.3s ease; cursor: pointer; }
.movie-card:hover { transform: translateY(-8px); box-shadow: 0 20px 35px rgba(0,0,0,0.15); }
.movie-card h3 { padding: 20px 20px 0; font-size: 1.5rem; color: var(--primary-dark); }
.movie-card p { padding: 8px 20px; color: #555; }
.btn, button { background: linear-gradient(135deg, var(--primary), var(--primary-dark)); color: white; border: none; padding: 10px 24px; border-radius: 40px; font-weight: 600; cursor: pointer; transition: 0.2s; text-decoration: none; display: inline-block; }
.btn:hover, button:hover { transform: scale(1.02); filter: brightness(1.05); }
.alert { padding: 14px 20px; border-radius: 12px; margin: 20px 0; font-weight: 500; animation: slideDown 0.3s ease; }
@keyframes slideDown { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
.alert-success { background: #d4edda; color: #155724; border-left: 5px solid var(--success); }
.alert-danger { background: #f8d7da; color: #721c24; border-left: 5px solid var(--danger); }
.alert-info { background: #d1ecf1; color: #0c5460; border-left: 5px solid var(--secondary); }
.seat-map { background: white; padding: 20px; border-radius: 24px; display: inline-block; box-shadow: 0 8px 20px rgba(0,0,0,0.1); margin: 20px 0; }
.seat-row { display: flex; margin: 8px 0; }
.seat { width: 55px; height: 55px; margin: 5px; text-align: center; line-height: 55px; border-radius: 12px; font-weight: bold; cursor: pointer; transition: 0.2s; background: #e0e7ff; color: #4c51bf; border: 2px solid #c7d2fe; }
.seat.booked { background: var(--danger); color: white; cursor: not-allowed; opacity: 0.6; border-color: #c0392b; }
.seat.selected { background: #fbbf24; color: #92400e; border-color: #f59e0b; transform: scale(1.05); }
.seat:hover:not(.booked) { transform: scale(1.05); background: var(--primary); color: white; }
.booking-card { background: white; border-radius: 16px; padding: 15px 20px; margin: 15px 0; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border-left: 5px solid var(--primary); transition: 0.2s; }
.booking-card:hover { transform: translateX(6px); }
.status-badge { display: inline-block; padding: 4px 12px; border-radius: 30px; font-size: 0.75rem; font-weight: bold; text-transform: uppercase; }
.status-confirmed { background: var(--success); color: white; }
.status-pending { background: var(--warning); color: #333; }
.status-cancelled { background: var(--danger); color: white; }
footer { background: rgba(45,52,54,0.9); backdrop-filter: blur(5px); color: white; text-align: center; padding: 20px; margin-top: 50px; border-top: 2px solid var(--secondary); }
input, select, textarea { width: 100%; padding: 12px; margin: 10px 0; border: 2px solid #dfe6e9; border-radius: 12px; font-size: 1rem; }
input:focus, select:focus, textarea:focus { outline: none; border-color: var(--primary); }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 20px; margin: 20px 0; }
.stat-card { background: white; padding: 20px; border-radius: 20px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }
.stat-number { font-size: 2.2rem; font-weight: 800; color: var(--primary); }
.admin-links { margin: 30px 0; display: flex; gap: 15px; flex-wrap: wrap; }
@media (max-width: 768px) { .seat { width: 40px; height: 40px; line-height: 40px; font-size: 12px; } .movie-grid { grid-template-columns: 1fr; } }
"""
with open(os.path.join(STATIC_DIR, 'style.css'), 'w', encoding='utf-8') as f:
    f.write(css_content)

js_content = "console.log('CineMagic ready');"
with open(os.path.join(STATIC_DIR, 'script.js'), 'w', encoding='utf-8') as f:
    f.write(js_content)

# ----- Initialize DB and seed data -----
with app.app_context():
    db.create_all()
    seed_data()

# ----- Run the app -----
if __name__ == '__main__':
    print("\n" + "="*50)
    print("🎬 Cinema System is running!")
    print("👉 Open your browser to: http://127.0.0.1:5000")
    print("👤 Admin login: admin / admin123")
    print("⏳ Pending bookings auto-cancel after 15 minutes")
    print("="*50 + "\n")
    app.run(debug=True, host='127.0.0.1', port=5000)
    