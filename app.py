import os
import uuid
import joblib
import pandas as pd
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, session

from database import get_db_connection


app = Flask(__name__)

app.secret_key = "smart_cargo_secret_key"

MODEL_PATH = os.path.join(app.root_path, "ml", "model.pkl")

fare_model = joblib.load(MODEL_PATH)

# ==========================================
# UPLOAD CONFIGURATION
# ==========================================

UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "static",
    "uploads"
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# Make sure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# ==========================================
# HOME
# ==========================================

@app.route("/")
def home():
    return render_template("index.html")


# ==========================================
# REGISTER
# ==========================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        mobile = request.form["mobile"]
        password = request.form["password"]
        role = request.form["role"]

        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
        INSERT INTO users
        (name, email, mobile, password, role)
        VALUES (%s, %s, %s, %s, %s)
        """

        cursor.execute(
            query,
            (name, email, mobile, password, role)
        )

        connection.commit()

        cursor.close()
        connection.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# ==========================================
# LOGIN
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT *
        FROM users
        WHERE email = %s AND password = %s
        """

        cursor.execute(query, (email, password))

        user = cursor.fetchone()

        cursor.close()
        connection.close()

        if user:

            session["user_id"] = user["user_id"]
            session["name"] = user["name"]
            session["role"] = user["role"]

            # Customer
            if user["role"] == "customer":
                return redirect(url_for("customer_dashboard"))

            # Driver
            elif user["role"] == "driver":
                return redirect(url_for("driver_dashboard"))

            # Admin
            elif user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))

        else:

            return "Invalid Email or Password!"

    return render_template("login.html")


# ==========================================
# CUSTOMER DASHBOARD
# ==========================================

@app.route("/customer-dashboard")
def customer_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "customer":
        return "Access Denied!"

    return render_template("customer_dashboard.html")


# ==========================================
# DRIVER DASHBOARD
# ==========================================

@app.route("/driver-dashboard")
def driver_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "driver":
        return "Access Denied!"

    return render_template("driver_dashboard.html")

# ==========================================
# DRIVER AVAILABILITY
# ==========================================

@app.route("/driver-availability", methods=["GET", "POST"])
def driver_availability():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "driver":
        return "Access Denied!"

    connection = get_db_connection()
    cursor = connection.cursor()

    # Find driver profile
    cursor.execute(
        """
        SELECT driver_id, availability
        FROM drivers
        WHERE user_id = %s
        """,
        (session["user_id"],)
    )

    driver = cursor.fetchone()

    if not driver:
        cursor.close()
        connection.close()
        return "Please complete your Driver Profile first!"

    driver_id = driver[0]

    if request.method == "POST":

        availability = request.form["availability"]

        cursor.execute(
            """
            UPDATE drivers
            SET availability = %s
            WHERE driver_id = %s
            """,
            (availability, driver_id)
        )

        connection.commit()

    # Get updated availability
    cursor.execute(
        """
        SELECT availability
        FROM drivers
        WHERE driver_id = %s
        """,
        (driver_id,)
    )

    current_status = cursor.fetchone()[0]

    cursor.close()
    connection.close()

    return render_template(
        "driver_availability.html",
        availability=current_status
    )

# ==========================================
# DRIVER PROFILE + VEHICLE DETAILS
# ==========================================

@app.route("/driver-profile", methods=["GET", "POST"])
def driver_profile():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "driver":
        return "Access Denied!"

    user_id = session["user_id"]

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # ==========================================
    # UPDATE PROFILE
    # ==========================================

    if request.method == "POST":

        name = request.form["name"]
        mobile = request.form["mobile"]

        licence_no = request.form["licence_no"]
        experience_years = request.form["experience_years"]

        vehicle_type = request.form["vehicle_type"]
        vehicle_number = request.form["vehicle_number"]
        capacity_kg = request.form["capacity_kg"]

        # ------------------------------------------
        # UPDATE USER INFORMATION
        # ------------------------------------------

        cursor.execute(
            """
            UPDATE users
            SET name = %s,
                mobile = %s
            WHERE user_id = %s
              AND role = 'driver'
            """,
            (name, mobile, user_id)
        )

        # ------------------------------------------
        # CHECK DRIVER PROFILE
        # ------------------------------------------

        cursor.execute(
            """
            SELECT driver_id
            FROM drivers
            WHERE user_id = %s
            """,
            (user_id,)
        )

        driver = cursor.fetchone()

        # ==========================================
        # EXISTING DRIVER
        # ==========================================

        if driver:

            driver_id = driver["driver_id"]

            cursor.execute(
                """
                UPDATE drivers
                SET licence_no = %s,
                    experience_years = %s
                WHERE driver_id = %s
                """,
                (
                    licence_no,
                    experience_years,
                    driver_id
                )
            )

        # ==========================================
        # NEW DRIVER
        # ==========================================

        else:

            cursor.execute(
                """
                INSERT INTO drivers
                (
                    user_id,
                    licence_no,
                    experience_years,
                    availability
                )
                VALUES (%s, %s, %s, 'Offline')
                """,
                (
                    user_id,
                    licence_no,
                    experience_years
                )
            )

            driver_id = cursor.lastrowid

        # ==========================================
        # VEHICLE
        # ==========================================

        cursor.execute(
            """
            SELECT vehicle_id
            FROM vehicles
            WHERE driver_id = %s
            """,
            (driver_id,)
        )

        vehicle = cursor.fetchone()

        # Update existing vehicle
        if vehicle:

            cursor.execute(
                """
                UPDATE vehicles
                SET vehicle_type = %s,
                    vehicle_number = %s,
                    capacity_kg = %s
                WHERE driver_id = %s
                """,
                (
                    vehicle_type,
                    vehicle_number,
                    capacity_kg,
                    driver_id
                )
            )

        # Create vehicle
        else:

            cursor.execute(
                """
                INSERT INTO vehicles
                (
                    driver_id,
                    vehicle_type,
                    vehicle_number,
                    capacity_kg
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    driver_id,
                    vehicle_type,
                    vehicle_number,
                    capacity_kg
                )
            )

        connection.commit()

    # ==========================================
    # GET DRIVER PROFILE
    # ==========================================

    cursor.execute(
        """
        SELECT
            u.user_id,
            u.name,
            u.email,
            u.mobile,

            d.driver_id,
            d.licence_no,
            d.experience_years,
            d.availability,
            d.rating,

            v.vehicle_type,
            v.vehicle_number,
            v.capacity_kg

        FROM users u

        LEFT JOIN drivers d
            ON u.user_id = d.user_id

        LEFT JOIN vehicles v
            ON d.driver_id = v.driver_id

        WHERE u.user_id = %s
          AND u.role = 'driver'
        """,
        (user_id,)
    )

    driver_profile_data = cursor.fetchone()

    cursor.close()
    connection.close()

    if not driver_profile_data:
        return "Driver profile not found!"

    return render_template(
        "driver_profile.html",
        driver=driver_profile_data
    )


# ==========================================
# BOOK VEHICLE
# ==========================================

@app.route("/book-vehicle", methods=["GET", "POST"])
def book_vehicle():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "customer":
        return "Access Denied!"

    if request.method == "POST":

        # ==========================================
        # GET FORM DATA
        # ==========================================

        pickup_location = request.form["pickup_location"]
        drop_location = request.form["drop_location"]
        goods_type = request.form["goods_type"]
        weight_kg = float(request.form["weight_kg"])
        vehicle_type = request.form["vehicle_type"]
        loading_required = request.form["loading_required"]

        # ==========================================
        # DISTANCE & TRAFFIC
        # ==========================================

        # Current booking form does not have distance
        # and traffic fields, so temporary demo values
        # are used.

        distance_km = float(request.form.get("distance_km", 10))
        traffic_level = request.form.get("traffic_level", "Medium")

        # ==========================================
        # ML FARE PREDICTION
        # ==========================================

        input_data = pd.DataFrame([{
            "distance_km": distance_km,
            "weight_kg": weight_kg,
            "vehicle_type": vehicle_type,
            "loading_required": loading_required,
            "goods_type": goods_type,
            "traffic_level": traffic_level
        }])

        predicted_fare = fare_model.predict(input_data)[0]

        predicted_fare = round(float(predicted_fare), 2)

        # ==========================================
        # FARE DISTRIBUTION
        # ==========================================

        # 20% platform fee
        platform_charge = round(predicted_fare * 0.20, 2)

        # 80% driver earning
        driver_earning = round(predicted_fare * 0.80, 2)

        # ==========================================
        # GET GOODS PHOTO
        # ==========================================

        goods_photo = request.files.get("goods_photo")

        photo_filename = None

        if goods_photo and goods_photo.filename:

            if allowed_file(goods_photo.filename):

                filename = secure_filename(goods_photo.filename)

                file_extension = filename.rsplit(".", 1)[1].lower()

                unique_filename = (
                    str(uuid.uuid4()) + "." + file_extension
                )

                goods_photo.save(
                    os.path.join(
                        app.config["UPLOAD_FOLDER"],
                        unique_filename
                    )
                )

                photo_filename = unique_filename

            else:

                return (
                    "Invalid file type! "
                    "Please upload JPG, JPEG, PNG or WEBP."
                )

        # ==========================================
        # USER ID
        # ==========================================

        user_id = session["user_id"]

        # ==========================================
        # DATABASE CONNECTION
        # ==========================================

        connection = get_db_connection()
        cursor = connection.cursor()

        # ==========================================
        # INSERT BOOKING
        # ==========================================

        query = """
        INSERT INTO bookings
        (
            user_id,
            pickup_location,
            drop_location,
            goods_type,
            weight_kg,
            vehicle_type,
            loading_required,
            fare,
            platform_charge,
            driver_earning,
            goods_photo,
            status
        )
        VALUES
        (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            'Pending'
        )
        """

        cursor.execute(
            query,
            (
                user_id,
                pickup_location,
                drop_location,
                goods_type,
                weight_kg,
                vehicle_type,
                loading_required,
                predicted_fare,
                platform_charge,
                driver_earning,
                photo_filename
            )
        )

        connection.commit()

        cursor.close()
        connection.close()

        return redirect(url_for("my_bookings"))

    return render_template("book_vehicle.html")

# ==========================================
# MY BOOKINGS
# ==========================================

@app.route("/my-bookings")
def my_bookings():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "customer":
        return "Access Denied!"

    user_id = session["user_id"]

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    query = """
    SELECT *
    FROM bookings
    WHERE user_id = %s
    ORDER BY booking_date DESC
    """

    cursor.execute(query, (user_id,))

    bookings = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "my_bookings.html",
        bookings=bookings
    )


# ==========================================
# ADMIN DASHBOARD
# ==========================================

@app.route("/admin-dashboard")
def admin_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied!"

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Customer count
    cursor.execute(
        "SELECT COUNT(*) AS total FROM users WHERE role='customer'"
    )

    customer_count = cursor.fetchone()["total"]

    # Driver count
    cursor.execute(
        "SELECT COUNT(*) AS total FROM users WHERE role='driver'"
    )

    driver_count = cursor.fetchone()["total"]

    # Booking count
    cursor.execute(
        "SELECT COUNT(*) AS total FROM bookings"
    )

    booking_count = cursor.fetchone()["total"]

    # Pending bookings
    query = """
    SELECT
        bookings.*,
        users.name AS customer_name
    FROM bookings
    JOIN users
        ON bookings.user_id = users.user_id
    WHERE bookings.status = 'Pending'
    ORDER BY bookings.booking_date DESC
    """

    cursor.execute(query)

    bookings = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin_dashboard.html",
        customer_count=customer_count,
        driver_count=driver_count,
        booking_count=booking_count,
        bookings=bookings
    )


# ==========================================
# ADMIN - ALL BOOKINGS
# ==========================================

@app.route("/admin-all-bookings")
def admin_all_bookings():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied!"

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            b.booking_id,
            u.name AS customer_name,
            b.pickup_location,
            b.drop_location,
            b.goods_type,
            b.goods_photo,
            b.weight_kg,
            b.vehicle_type,
            b.fare,
            b.status,
            b.booking_date,
            d.driver_id,
            du.name AS driver_name

        FROM bookings b

        JOIN users u
            ON b.user_id = u.user_id

        LEFT JOIN drivers d
            ON b.driver_id = d.driver_id

        LEFT JOIN users du
            ON d.user_id = du.user_id

        ORDER BY b.booking_id DESC
    """)

    bookings = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin_all_bookings.html",
        bookings=bookings
    )

# ==========================================
# ADMIN - CUSTOMER MANAGEMENT
# ==========================================

@app.route("/admin-customers")
def admin_customers():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied!"

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            user_id,
            name,
            email,
            mobile
        FROM users
        WHERE role = 'customer'
        ORDER BY user_id DESC
    """)

    customers = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin_customers.html",
        customers=customers
    )

# ==========================================
# ADMIN - DRIVER MANAGEMENT
# ==========================================

@app.route("/admin-drivers")
def admin_drivers():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied!"

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            d.driver_id,
            u.name,
            u.email,
            u.mobile,
            d.licence_no,
            d.experience_years,
            d.current_area,
            d.availability,
            d.rating,
            v.vehicle_type,
            v.vehicle_number,
            v.capacity_kg
        FROM drivers d
        JOIN users u
            ON d.user_id = u.user_id
        LEFT JOIN vehicles v
            ON d.driver_id = v.driver_id
        ORDER BY d.driver_id DESC
    """)

    drivers = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin_drivers.html",
        drivers=drivers
    )

# ==========================================
# ADMIN - UPDATE DRIVER AVAILABILITY
# ==========================================

@app.route("/admin-update-driver-status/<int:driver_id>/<status>")
def admin_update_driver_status(driver_id, status):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied!"

    if status not in ["Online", "Offline"]:
        return "Invalid status!"

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE drivers
        SET availability = %s
        WHERE driver_id = %s
    """, (status, driver_id))

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for("admin_drivers"))

# ==========================================
# DRIVER REQUESTS
# ==========================================

@app.route("/driver-requests")
def driver_requests():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "driver":
        return "Access Denied!"

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            notifications.notification_id,
            notifications.message,
            notifications.status,
            notifications.created_at,

            bookings.booking_id,
            bookings.pickup_location,
            bookings.drop_location,
            bookings.goods_type,
            bookings.goods_photo,
            bookings.weight_kg,
            bookings.vehicle_type,

            bookings.driver_earning

        FROM notifications

        JOIN bookings
            ON notifications.booking_id = bookings.booking_id

        JOIN drivers
            ON notifications.driver_id = drivers.driver_id

        WHERE drivers.user_id = %s

        ORDER BY notifications.created_at DESC
        """,
        (session["user_id"],)
    )

    requests = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "driver_requests.html",
        requests=requests
    )

# ==========================================
# DRIVER ACCEPT BOOKING
# ==========================================

@app.route("/accept-booking/<int:notification_id>")
def accept_booking(notification_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "driver":
        return "Access Denied!"

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Get logged-in driver's ID
    cursor.execute(
        """
        SELECT driver_id
        FROM drivers
        WHERE user_id = %s
        """,
        (session["user_id"],)
    )

    driver = cursor.fetchone()

    if not driver:
        cursor.close()
        connection.close()
        return "Driver profile not found!"

    driver_id = driver["driver_id"]

    # Get pending notification
    cursor.execute(
        """
        SELECT booking_id
        FROM notifications
        WHERE notification_id = %s
          AND driver_id = %s
          AND status = 'Pending'
        """,
        (notification_id, driver_id)
    )

    notification = cursor.fetchone()

    if not notification:
        cursor.close()
        connection.close()
        return "Booking request not found or already closed!"

    booking_id = notification["booking_id"]

    # Check whether another driver has already accepted
    cursor.execute(
        """
        SELECT driver_id, status
        FROM bookings
        WHERE booking_id = %s
        """,
        (booking_id,)
    )

    booking = cursor.fetchone()

    if not booking:
        cursor.close()
        connection.close()
        return "Booking not found!"

    # Someone already accepted this booking
    if booking["driver_id"] is not None:
        cursor.execute(
            """
            UPDATE notifications
            SET status = 'Cancelled'
            WHERE notification_id = %s
            """,
            (notification_id,)
        )

        connection.commit()

        cursor.close()
        connection.close()

        return "Sorry! This booking has already been accepted by another driver."

    # Assign booking to this driver
    cursor.execute(
        """
        UPDATE bookings
        SET status = 'Accepted',
            driver_id = %s
        WHERE booking_id = %s
          AND driver_id IS NULL
        """,
        (driver_id, booking_id)
    )

    # Check whether booking was actually assigned
    if cursor.rowcount == 0:

        cursor.close()
        connection.close()

        return "Sorry! Another driver has already accepted this booking."

    # Mark current notification as Accepted
    cursor.execute(
        """
        UPDATE notifications
        SET status = 'Accepted'
        WHERE notification_id = %s
        """,
        (notification_id,)
    )

    # Cancel all other pending requests for this booking
    cursor.execute(
        """
        UPDATE notifications
        SET status = 'Cancelled'
        WHERE booking_id = %s
          AND notification_id != %s
          AND status = 'Pending'
        """,
        (booking_id, notification_id)
    )

    # Make the accepted driver unavailable
    cursor.execute(
        """
        UPDATE drivers
        SET availability = 'Offline'
        WHERE driver_id = %s
        """,
        (driver_id,)
    )

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for("driver_requests"))
# ==========================================
# DRIVER REJECT BOOKING
# ==========================================

@app.route("/reject-driver-booking/<int:notification_id>")
def reject_driver_booking(notification_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "driver":
        return "Access Denied!"

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # Get logged-in driver's ID
    cursor.execute(
        """
        SELECT driver_id
        FROM drivers
        WHERE user_id = %s
        """,
        (session["user_id"],)
    )

    driver = cursor.fetchone()

    if not driver:
        cursor.close()
        connection.close()
        return "Driver profile not found!"

    driver_id = driver["driver_id"]

    # Get pending notification
    cursor.execute(
        """
        SELECT booking_id
        FROM notifications
        WHERE notification_id = %s
          AND driver_id = %s
          AND status = 'Pending'
        """,
        (notification_id, driver_id)
    )

    notification = cursor.fetchone()

    if not notification:
        cursor.close()
        connection.close()
        return "Booking request not found or already closed!"

    booking_id = notification["booking_id"]

    # Reject only this driver's request
    cursor.execute(
        """
        UPDATE notifications
        SET status = 'Rejected'
        WHERE notification_id = %s
        """,
        (notification_id,)
    )

    # Check if any other driver still has a pending request
    cursor.execute(
        """
        SELECT COUNT(*) AS pending_count
        FROM notifications
        WHERE booking_id = %s
          AND status = 'Pending'
        """,
        (booking_id,)
    )

    result = cursor.fetchone()

    # If no driver has accepted and no requests are pending
    if result["pending_count"] == 0:

        cursor.execute(
            """
            SELECT driver_id
            FROM bookings
            WHERE booking_id = %s
            """,
            (booking_id,)
        )

        booking = cursor.fetchone()

        if booking and booking["driver_id"] is None:

            cursor.execute(
                """
                UPDATE bookings
                SET status = 'Approved - Waiting for Driver',
                    driver_id = NULL
                WHERE booking_id = %s
                """,
                (booking_id,)
            )

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for("driver_requests"))

# ==========================================
# APPROVE BOOKING
# ==========================================

@app.route("/approve-booking/<int:booking_id>")
def approve_booking(booking_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied!"

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # ==========================================
    # GET BOOKING DETAILS
    # ==========================================

    cursor.execute(
        """
        SELECT *
        FROM bookings
        WHERE booking_id = %s
        """,
        (booking_id,)
    )

    booking = cursor.fetchone()

    if not booking:
        cursor.close()
        connection.close()
        return "Booking not found!"

    # ==========================================
    # FIND SUITABLE ONLINE DRIVERS
    # NEAREST AREA GETS PRIORITY
    # ==========================================

    query = """
    SELECT
        drivers.driver_id,
        users.name AS driver_name,
        drivers.current_area,
        drivers.rating,
        vehicles.vehicle_type,
        vehicles.vehicle_number,
        vehicles.capacity_kg
    FROM drivers
    JOIN users
        ON drivers.user_id = users.user_id
    JOIN vehicles
        ON drivers.driver_id = vehicles.driver_id
    WHERE drivers.availability = 'Online'
      AND vehicles.vehicle_type = %s
      AND vehicles.capacity_kg >= %s

    ORDER BY
        CASE
            WHEN LOWER(TRIM(drivers.current_area))
                 = LOWER(TRIM(%s))
            THEN 0
            ELSE 1
        END,
        drivers.rating DESC
    """

    cursor.execute(
        query,
        (
            booking["vehicle_type"],
            booking["weight_kg"],
            booking["pickup_location"]
        )
    )

    drivers = cursor.fetchall()

    # ==========================================
    # SEND BOOKING REQUEST TO SUITABLE DRIVERS
    # ==========================================

    if drivers:

        message = (
            f"New booking #{booking_id}: "
            f"{booking['pickup_location']} to "
            f"{booking['drop_location']}. "
            f"Goods: {booking['goods_type']}, "
            f"Weight: {booking['weight_kg']} KG."
        )

        # Send request to ALL suitable drivers
        for driver in drivers:

            cursor.execute(
                """
                INSERT INTO notifications
                (driver_id, booking_id, message, status)
                VALUES (%s, %s, %s, 'Pending')
                """,
                (
                    driver["driver_id"],
                    booking_id,
                    message
                )
            )

        # Booking is waiting for driver acceptance
        cursor.execute(
            """
            UPDATE bookings
            SET status = 'Searching for Driver',
                driver_id = NULL
            WHERE booking_id = %s
            """,
            (booking_id,)
        )

    else:

        # No suitable online driver found
        cursor.execute(
            """
            UPDATE bookings
            SET status = 'Approved - Waiting for Driver',
                driver_id = NULL
            WHERE booking_id = %s
            """,
            (booking_id,)
        )

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for("admin_dashboard"))

# ==========================================
# ADMIN REJECT BOOKING
# ==========================================

@app.route("/reject-booking/<int:booking_id>")
def reject_booking(booking_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access Denied!"

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE bookings
        SET status = 'Rejected'
        WHERE booking_id = %s
        """,
        (booking_id,)
    )

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for("admin_dashboard"))

# ==========================================
# TRACK BOOKING
# ==========================================

@app.route("/track-booking")
def track_booking():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "customer":
        return "Access Denied!"

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            b.booking_id,
            b.pickup_location,
            b.drop_location,
            b.goods_type,
            b.weight_kg,
            b.vehicle_type,
            b.fare,
            b.status,
            b.booking_date,

            d.driver_id,
            u.name AS driver_name,
            u.mobile AS driver_mobile,
            d.licence_no,
            d.experience_years,
            d.rating,
            v.vehicle_number,
            v.capacity_kg

        FROM bookings b

        LEFT JOIN drivers d
            ON b.driver_id = d.driver_id

        LEFT JOIN users u
            ON d.user_id = u.user_id

        LEFT JOIN vehicles v
            ON d.driver_id = v.driver_id

        WHERE b.user_id = %s

        ORDER BY b.booking_id DESC
        """,
        (session["user_id"],)
    )

    bookings = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "track_booking.html",
        bookings=bookings
    )

# ==========================================
# REVIEWS
# ==========================================

@app.route("/reviews")
def reviews():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "customer":
        return "Access Denied!"

    return "Reviews page - Coming Soon"

# ==========================================
# CUSTOMER PROFILE
# ==========================================

@app.route("/profile", methods=["GET", "POST"])
def profile():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "customer":
        return "Access Denied!"

    user_id = session["user_id"]

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    # ==========================================
    # UPDATE PROFILE
    # ==========================================

    if request.method == "POST":

        name = request.form["name"]
        mobile = request.form["mobile"]

        cursor.execute(
            """
            UPDATE users
            SET name = %s,
                mobile = %s
            WHERE user_id = %s
              AND role = 'customer'
            """,
            (name, mobile, user_id)
        )

        connection.commit()

    # ==========================================
    # GET CUSTOMER DETAILS
    # ==========================================

    cursor.execute(
        """
        SELECT
            user_id,
            name,
            email,
            mobile
        FROM users
        WHERE user_id = %s
          AND role = 'customer'
        """,
        (user_id,)
    )

    customer = cursor.fetchone()

    cursor.close()
    connection.close()

    if not customer:
        return "Customer profile not found!"

    return render_template(
        "profile.html",
        customer=customer
    )


# ==========================================
# FARE ESTIMATE
# ==========================================

@app.route("/fare-estimate", methods=["GET", "POST"])
def fare_estimate():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "customer":
        return "Access Denied!"

    predicted_fare = None
    platform_charge = None
    driver_earning = None

    if request.method == "POST":

        distance_km = float(request.form["distance_km"])
        weight_kg = float(request.form["weight_kg"])
        vehicle_type = request.form["vehicle_type"]
        loading_required = request.form["loading_required"]
        goods_type = request.form["goods_type"]
        traffic_level = request.form["traffic_level"]

        # Prepare input data for ML model
        input_data = pd.DataFrame([{
            "distance_km": distance_km,
            "weight_kg": weight_kg,
            "vehicle_type": vehicle_type,
            "loading_required": loading_required,
            "goods_type": goods_type,
            "traffic_level": traffic_level
        }])

        # Predict fare using trained ML model
        predicted_fare = fare_model.predict(input_data)[0]

        # Round predicted fare
        predicted_fare = round(float(predicted_fare), 2)

        platform_charge = round(predicted_fare * 0.20, 2)
        driver_earning = round(predicted_fare * 0.80, 2)


    return render_template(
    "fare_estimate.html",
    predicted_fare=predicted_fare,
    platform_charge=platform_charge,
    driver_earning=driver_earning
)
# ==========================================
# LOGOUT
# ==========================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))

# ==========================================
# DELIVERY STATUS
# ==========================================

@app.route("/delivery-status")
def delivery_status():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "driver":
        return "Access Denied!"

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT driver_id
        FROM drivers
        WHERE user_id = %s
        """,
        (session["user_id"],)
    )

    driver = cursor.fetchone()

    if not driver:
        cursor.close()
        connection.close()
        return "Driver profile not found!"

    driver_id = driver["driver_id"]

    cursor.execute(
        """
        SELECT *
        FROM bookings
        WHERE driver_id = %s
        AND status IN (
            'Accepted',
            'Reached Pickup',
            'Goods Picked',
            'In Transit'
        )
        ORDER BY booking_id DESC
        """,
        (driver_id,)
    )

    bookings = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "delivery_status.html",
        bookings=bookings
    )


# ==========================================
# UPDATE DELIVERY STATUS
# ==========================================

@app.route("/update-delivery-status/<int:booking_id>", methods=["POST"])
def update_delivery_status(booking_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "driver":
        return "Access Denied!"

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT driver_id
        FROM drivers
        WHERE user_id = %s
        """,
        (session["user_id"],)
    )

    driver = cursor.fetchone()

    if not driver:
        cursor.close()
        connection.close()
        return "Driver profile not found!"

    driver_id = driver["driver_id"]

    new_status = request.form.get("status")

    allowed_statuses = [
        "Reached Pickup",
        "Goods Picked",
        "In Transit",
        "Delivered"
    ]

    if new_status not in allowed_statuses:
        cursor.close()
        connection.close()
        return "Invalid delivery status!"

    cursor.execute(
        """
        UPDATE bookings
        SET status = %s
        WHERE booking_id = %s
        AND driver_id = %s
        AND status IN (
            'Accepted',
            'Reached Pickup',
            'Goods Picked',
            'In Transit'
        )
        """,
        (new_status, booking_id, driver_id)
    )

    connection.commit()

    cursor.close()
    connection.close()

    return redirect(url_for("delivery_status"))

# ==========================================
# RUN
# ==========================================
print(app.url_map)
if __name__ == "__main__":
    app.run(debug=True)