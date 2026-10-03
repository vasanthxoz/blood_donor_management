from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from utils.db import get_db_connection
from datetime import datetime, timedelta
import config

app = Flask(__name__)
app.secret_key = config.SECRET_KEY


# =========================================================
# LOGIN CHECK
# =========================================================

def is_logged_in():
    return 'admin_id' in session


# =========================================================
# HOME
# =========================================================

@app.route('/')
def index():
    return redirect(url_for('login'))


# =========================================================
# LOGIN
# =========================================================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        conn = get_db_connection()

        try:
            with conn.cursor() as cursor:

                cursor.execute(
                    "SELECT * FROM admin WHERE username=%s",
                    (request.form['username'],)
                )

                admin = cursor.fetchone()

        finally:
            conn.close()

        if admin and check_password_hash(
                admin['password_hash'],
                request.form['password']):

            session['admin_id'] = admin['admin_id']

            return redirect(url_for('dashboard'))

        flash('Invalid credentials', 'danger')

    return render_template('login.html')


# =========================================================
# LOGOUT
# =========================================================

@app.route('/logout')
def logout():

    session.clear()

    return redirect(url_for('login'))


# =========================================================
# DASHBOARD
# =========================================================

@app.route('/dashboard')
def dashboard():

    if not is_logged_in():
        return redirect(url_for('login'))

    conn = get_db_connection()
    stats = {}

    try:

        with conn.cursor() as cursor:

            cursor.execute(
                "SELECT COUNT(*) AS c FROM donor"
            )
            stats['donors'] = cursor.fetchone()['c']

            cursor.execute(
                "SELECT COUNT(*) AS c FROM donation"
            )
            stats['donations'] = cursor.fetchone()['c']

            cursor.execute("""
                SELECT SUM(quantity) AS c
                FROM blood_stock
                WHERE status='Available'
                AND expiry_date >= CURDATE()
            """)

            stats['available'] = cursor.fetchone()['c'] or 0

            cursor.execute(
                "SELECT COUNT(*) AS c FROM hospital"
            )
            stats['hospitals'] = cursor.fetchone()['c']

            cursor.execute("""
                SELECT COUNT(*) AS c
                FROM blood_request
                WHERE status='Pending'
            """)

            stats['requests'] = cursor.fetchone()['c']

            cursor.execute("""
                SELECT COUNT(*) AS c
                FROM donor_health
            """)

            stats['health_records'] = cursor.fetchone()['c']

            cursor.execute("""
                SELECT COUNT(*) AS c
                FROM donor_eligibility
                WHERE status='Approved'
            """)

            stats['approved'] = cursor.fetchone()['c']

            cursor.execute("""
                SELECT COUNT(*) AS c
                FROM donor_eligibility
                WHERE status <> 'Approved'
            """)

            stats['not_approved'] = cursor.fetchone()['c']

            cursor.execute("""
                SELECT COUNT(*) AS c
                FROM blood_stock
                WHERE expiry_date < CURDATE()
            """)

            stats['expired'] = cursor.fetchone()['c']

    finally:
        conn.close()

    return render_template(
        'dashboard.html',
        stats=stats
    )


# =========================================================
# DONOR REGISTRATION
# =========================================================

@app.route('/donors')
def donors():

    if not is_logged_in():
        return redirect(url_for('login'))

    conn = get_db_connection()

    try:

        with conn.cursor() as cursor:

            cursor.execute(
                "SELECT * FROM donor"
            )

            data = cursor.fetchall()

    finally:
        conn.close()

    return render_template(
        'donors.html',
        donors=data
    )


@app.route('/donors/add', methods=['GET', 'POST'])
def add_donor():

    if not is_logged_in():
        return redirect(url_for('login'))

    if request.method == 'POST':

        conn = get_db_connection()

        try:

            with conn.cursor() as c:

                c.execute("""
                    INSERT INTO donor
                    (name, age, gender, blood_group, phone)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    request.form['name'],
                    request.form['age'],
                    request.form['gender'],
                    request.form['blood_group'],
                    request.form['phone']
                ))

                donor_id = c.lastrowid

            conn.commit()

            flash(
                'Donor registered successfully. Now enter health information.',
                'success'
            )

            return redirect(
                url_for('add_health', donor_id=donor_id)
            )

        except Exception as e:

            conn.rollback()

            flash(
                f'Error: {e}',
                'danger'
            )

        finally:
            conn.close()

    return render_template('donor_form.html')


# =========================================================
# HEALTH INFORMATION
# =========================================================

@app.route('/donor-health')
def donor_health():

    if not is_logged_in():
        return redirect(url_for('login'))

    conn = get_db_connection()

    try:

        with conn.cursor() as c:

            c.execute("""
                SELECT h.*, d.name
                FROM donor_health h
                JOIN donor d
                ON h.donor_id = d.donor_id
                ORDER BY h.health_id DESC
            """)

            data = c.fetchall()

    finally:
        conn.close()

    return render_template(
        'donor_health.html',
        records=data
    )


@app.route('/donor-health/add', methods=['GET', 'POST'])
def add_health():

    if not is_logged_in():
        return redirect(url_for('login'))

    # Donor ID passed from donor registration
    selected_donor_id = request.args.get('donor_id')

    # =====================================================
    # POST - SAVE HEALTH INFORMATION
    # =====================================================

    if request.method == 'POST':

        conn = get_db_connection()

        try:

            donor_id = request.form['donor_id']
            weight = request.form['weight']
            bp = request.form['bp']
            hb = request.form['hb']
            status = request.form['status']

            with conn.cursor() as c:

                # Medical History removed from the form.
                # Empty value is stored in the existing column.
                c.execute("""
                    INSERT INTO donor_health
                    (
                        donor_id,
                        medical_history,
                        weight,
                        blood_pressure,
                        hemoglobin,
                        health_status,
                        checked_date
                    )
                    VALUES
                    (%s, %s, %s, %s, %s, %s, CURDATE())
                """, (
                    donor_id,
                    '',
                    weight,
                    bp,
                    hb,
                    status
                ))

            conn.commit()

            flash(
                'Health information saved. Proceed to medical eligibility screening.',
                'success'
            )

            return redirect(
                url_for(
                    'add_eligibility',
                    donor_id=donor_id
                )
            )

        except Exception as e:

            conn.rollback()

            flash(
                f'Error: {e}',
                'danger'
            )

        finally:
            conn.close()

    # =====================================================
    # GET - LOAD DONORS
    # =====================================================
    # IMPORTANT:
    # This is a NEW connection.
    # The previous connection was already closed above.
    # This fixes:
    # pymysql.err.Error: Already closed
    # =====================================================

    conn = get_db_connection()

    try:

        with conn.cursor() as c:

            c.execute(
                "SELECT donor_id, name FROM donor ORDER BY name"
            )

            donors = c.fetchall()

    finally:
        conn.close()

    return render_template(
        'health_form.html',
        donors=donors,
        selected_donor_id=selected_donor_id
    )


# =========================================================
# ELIGIBILITY SCREENING
# =========================================================

@app.route('/eligibility')
def eligibility():

    if not is_logged_in():
        return redirect(url_for('login'))

    conn = get_db_connection()

    try:

        with conn.cursor() as c:

            c.execute("""
                SELECT
                    e.*,
                    d.name,
                    d.blood_group
                FROM donor_eligibility e
                JOIN donor d
                ON e.donor_id = d.donor_id
                ORDER BY e.eligible_date DESC
            """)

            data = c.fetchall()

    finally:
        conn.close()

    return render_template(
        'eligibility.html',
        records=data
    )


@app.route('/eligibility/add', methods=['GET', 'POST'])
def add_eligibility():

    if not is_logged_in():
        return redirect(url_for('login'))

    selected_donor_id = request.args.get('donor_id')

    if request.method == 'POST':

        conn = get_db_connection()

        try:

            donor_id = request.form['donor_id']
            status = request.form['status']

            with conn.cursor() as c:

                # Check latest health information
                c.execute("""
                    SELECT health_id
                    FROM donor_health
                    WHERE donor_id=%s
                    ORDER BY health_id DESC
                    LIMIT 1
                """, (donor_id,))

                health = c.fetchone()

                if not health:

                    flash(
                        'Health information is required before eligibility screening.',
                        'danger'
                    )

                    return redirect(
                        url_for(
                            'add_health',
                            donor_id=donor_id
                        )
                    )

                # Insert eligibility
                c.execute("""
                    INSERT INTO donor_eligibility
                    (
                        donor_id,
                        health_id,
                        eligible_date,
                        status
                    )
                    VALUES
                    (
                        %s,
                        %s,
                        CURDATE(),
                        %s
                    )
                """, (
                    donor_id,
                    health['health_id'],
                    status
                ))

            conn.commit()

            # =================================================
            # APPROVED
            # =================================================

            if status.lower() == 'approved':

                flash(
                    'Donor approved. Blood donation can now be recorded.',
                    'success'
                )

                return redirect(
                    url_for(
                        'add_donation',
                        donor_id=donor_id
                    )
                )

            # =================================================
            # NOT APPROVED
            # =================================================

            flash(
                'Donation blocked. Donor requires medical review.',
                'warning'
            )

            return redirect(
                url_for('eligibility')
            )

        except Exception as e:

            conn.rollback()

            flash(
                f'Error: {e}',
                'danger'
            )

        finally:
            conn.close()

    # New connection for GET
    conn = get_db_connection()

    try:

        with conn.cursor() as c:

            c.execute(
                "SELECT donor_id, name FROM donor ORDER BY name"
            )

            donors = c.fetchall()

    finally:
        conn.close()

    return render_template(
        'eligibility_form.html',
        donors=donors,
        selected_donor_id=selected_donor_id
    )


# =========================================================
# DONATIONS
# =========================================================

@app.route('/donations')
def donations():

    if not is_logged_in():
        return redirect(url_for('login'))

    conn = get_db_connection()

    try:

        with conn.cursor() as c:

            c.execute("""
                SELECT
                    d.*,
                    do.name
                FROM donation d
                JOIN donor do
                ON d.donor_id = do.donor_id
                ORDER BY d.donation_date ASC
            """)

            data = c.fetchall()

    finally:
        conn.close()

    return render_template(
        'donations.html',
        records=data
    )


@app.route('/donations/add', methods=['GET', 'POST'])
def add_donation():

    if not is_logged_in():
        return redirect(url_for('login'))

    selected_donor_id = request.args.get('donor_id')

    if request.method == 'POST':

        conn = get_db_connection()

        try:

            donor_id = request.form['donor_id']

            conn.begin()

            with conn.cursor() as c:

                # =================================================
                # CHECK LATEST ELIGIBILITY
                # =================================================

                c.execute("""
                    SELECT status
                    FROM donor_eligibility
                    WHERE donor_id=%s
                    ORDER BY eligible_date DESC
                    LIMIT 1
                """, (donor_id,))

                eligibility_record = c.fetchone()

                if not eligibility_record:

                    conn.rollback()

                    flash(
                        'Medical eligibility screening is required before donation.',
                        'danger'
                    )

                    return redirect(
                        url_for(
                            'add_eligibility',
                            donor_id=donor_id
                        )
                    )

                if eligibility_record['status'].lower() != 'approved':

                    conn.rollback()

                    flash(
                        'Donation blocked. Donor is not medically approved.',
                        'danger'
                    )

                    return redirect(
                        url_for('eligibility')
                    )

                # =================================================
                # GET BLOOD GROUP
                # =================================================

                c.execute("""
                    SELECT blood_group
                    FROM donor
                    WHERE donor_id=%s
                """, (donor_id,))

                donor = c.fetchone()

                if not donor:
                    raise Exception(
                        'Donor not found.'
                    )

                blood_group = donor['blood_group']
                quantity = request.form['quantity']

                # Blood expiry = 35 days
                expiry_date = (
                    datetime.now() +
                    timedelta(days=35)
                ).date()

                # =================================================
                # BLOOD DONATION
                # =================================================

                c.execute("""
                    INSERT INTO donation
                    (
                        donor_id,
                        blood_group,
                        donation_date,
                        quantity,
                        expiry_date
                    )
                    VALUES
                    (%s, %s, CURDATE(), %s, %s)
                """, (
                    donor_id,
                    blood_group,
                    quantity,
                    expiry_date
                ))

                donation_id = c.lastrowid

                # =================================================
                # BLOOD TESTING -> BLOOD STOCK
                # =================================================

                c.execute("""
                    INSERT INTO blood_stock
                    (
                        donation_id,
                        blood_group,
                        quantity,
                        collection_date,
                        expiry_date
                    )
                    VALUES
                    (%s, %s, %s, CURDATE(), %s)
                """, (
                    donation_id,
                    blood_group,
                    quantity,
                    expiry_date
                ))

                # Update donor
                c.execute("""
                    UPDATE donor
                    SET last_donation_date=CURDATE()
                    WHERE donor_id=%s
                """, (donor_id,))

            conn.commit()

            flash(
                'Blood donation recorded and added to blood stock.',
                'success'
            )

            return redirect(
                url_for('blood_stock')
            )

        except Exception as e:

            conn.rollback()

            flash(
                f'Error: {e}',
                'danger'
            )

        finally:
            conn.close()

    # =========================================================
    # ONLY APPROVED DONORS
    # =========================================================

    conn = get_db_connection()

    try:

        with conn.cursor() as c:

            c.execute("""
                SELECT
                    d.donor_id,
                    d.name
                FROM donor d
                JOIN donor_eligibility e
                ON d.donor_id = e.donor_id
                WHERE e.status='Approved'
                AND e.eligible_date =
                (
                    SELECT MAX(e2.eligible_date)
                    FROM donor_eligibility e2
                    WHERE e2.donor_id=d.donor_id
                )
                ORDER BY d.name
            """)

            donors = c.fetchall()

    finally:
        conn.close()

    return render_template(
        'donation_form.html',
        donors=donors,
        selected_donor_id=selected_donor_id
    )


# =========================================================
# BLOOD STOCK
# =========================================================

@app.route('/blood-stock')
def blood_stock():

    if not is_logged_in():
        return redirect(url_for('login'))

    conn = get_db_connection()

    try:

        with conn.cursor() as c:

            c.execute("""
                SELECT *
                FROM blood_stock
                ORDER BY expiry_date ASC
            """)

            data = c.fetchall()

    finally:
        conn.close()

    return render_template(
        'blood_stock.html',
        stock=data
    )


# =========================================================
# EXPIRY TRACKING
# =========================================================

@app.route('/blood-stock/expiry')
def expiry():

    if not is_logged_in():
        return redirect(url_for('login'))

    conn = get_db_connection()

    try:

        with conn.cursor() as c:

            c.execute(
                "SELECT * FROM blood_expiry_view"
            )

            data = c.fetchall()

    finally:
        conn.close()

    return render_template(
        'expiry.html',
        stock=data
    )


# =========================================================
# HOSPITALS
# =========================================================

@app.route('/hospitals')
def hospitals():

    if not is_logged_in():
        return redirect(url_for('login'))

    conn = get_db_connection()

    try:

        with conn.cursor() as c:

            c.execute(
                "SELECT * FROM hospital"
            )

            data = c.fetchall()

    finally:
        conn.close()

    return render_template(
        'hospitals.html',
        records=data
    )


@app.route('/hospitals/add', methods=['GET', 'POST'])
def add_hospital():

    if not is_logged_in():
        return redirect(url_for('login'))

    if request.method == 'POST':

        conn = get_db_connection()

        try:

            with conn.cursor() as c:

                c.execute("""
                    INSERT INTO hospital
                    (
                        hospital_name,
                        address,
                        phone
                    )
                    VALUES (%s, %s, %s)
                """, (
                    request.form['name'],
                    request.form['address'],
                    request.form['phone']
                ))

            conn.commit()

            flash(
                'Hospital added.',
                'success'
            )

        except Exception as e:

            conn.rollback()

            flash(
                f'Error: {e}',
                'danger'
            )

        finally:
            conn.close()

        return redirect(
            url_for('hospitals')
        )

    return render_template(
        'hospital_form.html'
    )


# =========================================================
# BLOOD REQUESTS
# =========================================================

@app.route('/blood-requests')
def blood_requests():

    if not is_logged_in():
        return redirect(url_for('login'))

    conn = get_db_connection()

    try:

        with conn.cursor() as c:

            c.execute("""
                SELECT
                    r.*,
                    h.hospital_name
                FROM blood_request r
                JOIN hospital h
                ON r.hospital_id=h.hospital_id
                ORDER BY r.request_date DESC
            """)

            data = c.fetchall()

    finally:
        conn.close()

    return render_template(
        'blood_requests.html',
        records=data
    )


@app.route('/blood-requests/add', methods=['GET', 'POST'])
def add_request():

    if not is_logged_in():
        return redirect(url_for('login'))

    if request.method == 'POST':

        conn = get_db_connection()

        try:

            with conn.cursor() as c:

                c.execute("""
                    INSERT INTO blood_request
                    (
                        hospital_id,
                        blood_group,
                        quantity,
                        request_date,
                        priority
                    )
                    VALUES (%s, %s, %s, CURDATE(), %s)
                """, (
                    request.form['hospital_id'],
                    request.form['bg'],
                    request.form['qty'],
                    request.form['priority']
                ))

            conn.commit()

            flash(
                'Blood request submitted. Proceed to blood allocation.',
                'success'
            )

            return redirect(
                url_for('allocation')
            )

        except Exception as e:

            conn.rollback()

            flash(
                f'Error: {e}',
                'danger'
            )

        finally:
            conn.close()

    # New connection for GET
    conn = get_db_connection()

    try:

        with conn.cursor() as c:

            c.execute(
                "SELECT * FROM hospital ORDER BY hospital_name"
            )

            hos = c.fetchall()

    finally:
        conn.close()

    return render_template(
        'request_form.html',
        hospitals=hos
    )


# =========================================================
# BLOOD ALLOCATION
# =========================================================

@app.route('/allocation', methods=['GET', 'POST'])
def allocation():

    if not is_logged_in():
        return redirect(url_for('login'))

    # =====================================================
    # POST - CHECK AND ALLOCATE
    # =====================================================

    if request.method == 'POST':

        conn = get_db_connection()

        try:

            req_id = request.form['request_id']

            conn.begin()

            with conn.cursor() as c:

                # -------------------------------------------------
                # GET REQUEST
                # -------------------------------------------------

                c.execute("""
                    SELECT *
                    FROM blood_request
                    WHERE request_id=%s
                """, (req_id,))

                req = c.fetchone()

                if not req:
                    raise Exception(
                        'Blood request not found.'
                    )

                # -------------------------------------------------
                # CHECK AVAILABLE BLOOD
                # -------------------------------------------------

                c.execute("""
                    SELECT
                        COALESCE(SUM(quantity), 0) AS available_qty
                    FROM blood_stock
                    WHERE blood_group=%s
                    AND status='Available'
                    AND expiry_date >= CURDATE()
                """, (
                    req['blood_group'],
                ))

                result = c.fetchone()

                available_qty = float(
                    result['available_qty'] or 0
                )

                required_qty = float(
                    req['quantity']
                )

                # -------------------------------------------------
                # INSUFFICIENT STOCK
                # -------------------------------------------------

                if available_qty < required_qty:

                    conn.rollback()

                    flash(
                        'Insufficient blood stock.',
                        'danger'
                    )

                    return redirect(
                        url_for('allocation')
                    )

                # -------------------------------------------------
                # FIFO ALLOCATION
                # -------------------------------------------------

                qty_needed = required_qty

                c.execute("""
                    SELECT
                        stock_id,
                        quantity
                    FROM blood_stock
                    WHERE blood_group=%s
                    AND status='Available'
                    AND expiry_date >= CURDATE()
                    ORDER BY collection_date ASC
                """, (
                    req['blood_group'],
                ))

                stocks = c.fetchall()

                for stock in stocks:

                    if qty_needed <= 0:
                        break

                    stock_qty = float(
                        stock['quantity']
                    )

                    # Use complete stock record
                    if stock_qty <= qty_needed:

                        c.execute("""
                            UPDATE blood_stock
                            SET
                                status='Used',
                                quantity=0
                            WHERE stock_id=%s
                        """, (
                            stock['stock_id'],
                        ))

                        qty_needed -= stock_qty

                    # Use only required amount
                    else:

                        c.execute("""
                            UPDATE blood_stock
                            SET quantity = quantity - %s
                            WHERE stock_id=%s
                        """, (
                            qty_needed,
                            stock['stock_id']
                        ))

                        qty_needed = 0

                # -------------------------------------------------
                # MARK REQUEST FULFILLED
                # -------------------------------------------------

                c.execute("""
                    UPDATE blood_request
                    SET status='Fulfilled'
                    WHERE request_id=%s
                """, (
                    req_id,
                ))

            conn.commit()

            flash(
                'Blood allocation successful.',
                'success'
            )

            return redirect(
                url_for('reports')
            )

        except Exception as e:

            conn.rollback()

            flash(
                f'Allocation Error: {e}',
                'danger'
            )

            return redirect(
                url_for('allocation')
            )

        finally:
            conn.close()

    # =====================================================
    # GET - SHOW PENDING REQUESTS
    # =====================================================

    conn = get_db_connection()

    try:

        with conn.cursor() as c:

            c.execute("""
                SELECT
                    r.*,
                    h.hospital_name
                FROM blood_request r
                JOIN hospital h
                ON r.hospital_id=h.hospital_id
                WHERE r.status='Pending'
                ORDER BY
                    r.priority DESC,
                    r.request_date ASC
            """)

            pending = c.fetchall()

    finally:
        conn.close()

    return render_template(
        'allocation.html',
        requests=pending
    )


# =========================================================
# REPORTS
# =========================================================

@app.route('/reports')
def reports():

    if not is_logged_in():
        return redirect(url_for('login'))

    conn = get_db_connection()

    try:

        with conn.cursor() as c:

            # Donor blood groups
            c.execute("""
                SELECT
                    blood_group,
                    COUNT(*) AS count
                FROM donor
                GROUP BY blood_group
            """)

            donors_bg = c.fetchall()

            # Available blood
            c.execute(
                "SELECT * FROM available_blood_view"
            )

            stock_bg = c.fetchall()

            # Hospital blood request and allocation report
            c.execute("""
                SELECT
                    r.request_id,
                    h.hospital_name,
                    r.blood_group,
                    r.quantity,
                    r.request_date,
                    r.priority,
                    r.status
                FROM blood_request r
                JOIN hospital h
                    ON r.hospital_id = h.hospital_id
                ORDER BY r.request_date DESC,
                         r.request_id DESC
            """)

            blood_requests_report = c.fetchall()

    finally:
        conn.close()

    return render_template(
        'reports.html',
        donors_bg=donors_bg,
        stock_bg=stock_bg,
        blood_requests_report=blood_requests_report
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == '__main__':
    app.run(debug=True)