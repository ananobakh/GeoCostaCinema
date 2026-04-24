**PROJECT NAME:** GeoCosta Cinema

**BRIEF DESCRIPTION**
GeoCosta Cinema is a fully functional web-based cinema reservation system built
with Python (Flask), SQLite, and custom HTML/CSS that solves the real-world
problem of overbooking and no-shows.

It allows users to register, log in, browse movies, check showtimes, and select
seats from an interactive seat map. When a user books seats, the reservation is
marked as “pending” and they are given a 15‑minute payment window; if they do
not confirm payment within that time, the system automatically cancels the
booking and releases the seats. This guarantees that no seats are held
indefinitely, reducing lost revenue for the cinema.

Additionally, if a show is completely booked, customers can join a waiting
list. When a pending booking expires or is cancelled, the first person on the
waiting list is notified (via a flag on their dashboard) and can then book
the freed seat.

**The system includes two user roles:**
•⁠  ⁠Regular customers: view their bookings, cancel reservations, join waiting lists.
•⁠  ⁠Administrators: add/edit/delete movies, manage showtimes, promote users,
  monitor the waiting list.

**Technical stack:**
•⁠  ⁠Backend: Flask (routing, business logic)
•⁠  ⁠Database: SQLite + SQLAlchemy ORM
•⁠  ⁠Authentication: Flask-Login + bcrypt (password hashing)
•⁠  ⁠Background jobs: APScheduler (auto-release expired pending bookings)
•⁠  ⁠Frontend: HTML5, CSS3 (responsive, gradient design, animated seat cards)

This project demonstrates core programming concepts: HTTP requests/responses,
user authentication, database relationships (one-to-many, foreign keys),
CRUD operations, asynchronous background jobs, and separation of concerns
(models, views, templates, static assets). It is ideal for first-year students
and can be extended with payment simulation, email notifications, QR code
tickets, or a recommendation engine.

**SETUP INSTRUCTIONS**
1.⁠ ⁠Clone the repository:
   git clone https: https://github.com/ananobakh/GeoCostaMovies
   cd geocosta-cinema

2.⁠ ⁠Open the project in your IDE (VS Code, PyCharm, etc.).

3.⁠ ⁠Ensure Python 3.8 or higher is installed on your system:
   python --version

4.⁠ ⁠Install the required packages:
   pip install flask flask-sqlalchemy flask-login bcrypt apscheduler

5.⁠ ⁠Run the application:
   python run.py

6.⁠ ⁠Open your web browser and go to:
   http://127.0.0.1:5000

**USAGE INSTRUCTIONS**
1.⁠ ⁠On first visit, you will see the homepage listing current movies.
2.⁠ ⁠Use the navigation bar to either LOGIN or REGISTER a new account.
   - To register, click "Register", fill in username, email, and password.
   - After registration, log in with your credentials.
3.⁠ ⁠Once logged in:
   - Regular users see a dashboard with upcoming/pending bookings,
     past bookings, and waiting list status.
   - Browse all movies from the "Movies" page.
   - Click on a movie to see its details and available showtimes.
4.⁠ ⁠To book a show:
   - Click "Book" on a showtime.
   - Select seats from the interactive seat map (click on available seats).
   - Click "Reserve (15 min to pay)".
   - The booking becomes "pending". Go to "My Bookings" and click
     "Confirm Payment" within 15 minutes to finalise.
   - If you do not confirm, the booking auto-cancels and seats are released
     to the next person on the waiting list.
5.⁠ ⁠If a show is completely booked, you can click "Join Waiting List".
   - You will receive a notification on your dashboard when seats become free.
6.⁠ ⁠Admin users (default: username "admin", password "admin123") have
   additional options in the navigation bar:
   - Admin Dashboard: view statistics and recent bookings.
   - Manage Movies: add, delete movies.
   - Manage Showtimes: add, delete showtimes.
   - Manage Users: promote regular users to admin, delete users.
   - View Waiting List: see all waiting entries with timestamps.
7.⁠ ⁠The SQLite database (cinema.db) is automatically created and managed.
   No separate database server is needed.

**TECHNOLOGIES USED**
•⁠  ⁠Python 3.8+ (core language)
•⁠  ⁠Flask (web framework)
•⁠  ⁠Flask-SQLAlchemy (ORM for database)
•⁠  ⁠Flask-Login (session management)
•⁠  ⁠bcrypt (password hashing)
•⁠  ⁠APScheduler (background job scheduler)
•⁠  ⁠SQLite (embedded database)
•⁠  ⁠HTML5, CSS3 (frontend)
•⁠  ⁠Jinja2 (templating engine)

**ADMIN CREDENTIALS (pre‑seeded)**
Username: admin
Password: admin123

You can change these after first login or create additional admin accounts
via the "Manage Users" admin panel.

**WAITING LIST & AUTO-RELEASE WORKFLOW**
1.⁠ ⁠User A books seats → status "pending" + payment deadline (now + 15 min).
2.⁠ ⁠If User A does not confirm within 15 minutes:
   - Background job (runs every minute) sets status to "cancelled".
   - The first waiting entry (if any) gets "notified = True".
3.⁠ ⁠User B (on waiting list) sees a notification on their dashboard:
   "Seats became available" and can then book normally.
4.⁠ ⁠The same occurs if User A manually cancels a pending booking.

This mechanism mimics a real cinema where no‑shows are automatically
re‑allocated, maximizing seat occupancy and customer satisfaction.

**EXTENSION IDEAS FOR YOUR SEMESTER PROJECT**
•⁠  ⁠Integrate a real payment gateway (Stripe, PayPal sandbox).
•⁠  ⁠Send email or SMS notifications when waiting list seats open.
•⁠  ⁠Generate QR‑coded tickets that can be scanned at the entrance.
•⁠  ⁠Add a "recommended movies" engine based on user history.
•⁠  ⁠Implement seat preferences (aisle, near exit, wheelchair accessible).
•⁠  ⁠Add multi‑language support (English/Spanish).
•⁠  ⁠Create a REST API for mobile apps.
