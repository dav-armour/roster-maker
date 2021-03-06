from flask_sqlalchemy import SQLAlchemy
from flask import flash, redirect, render_template, request, session, jsonify
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta
from pytz import timezone
from rostermaker import app, db
from rostermaker.models import User, Shift
from rostermaker.helpers import apology, login_required, admin_required, manager_required


@app.route("/")
@login_required
def index():
    """Shows index screen with next shift and notifications"""
    tz = timezone('Australia/Sydney')
    date = datetime.now(tz).date()
    next_shift = Shift.query.filter(Shift.user_id == session["user_id"], Shift.date >= date).first()

    if next_shift:
        shift = next_shift.__dict__
        date = shift["date"]
        shift["datePretty"] = date.strftime("%d/%m/%Y")
        shift["day"] = date.strftime("%A")
    else:
        shift = None

    return render_template("index.html", shift=shift)


@app.route("/locations", methods=["GET"])
@app.route("/roster", methods=["GET"])
@login_required
def roster():
    """Shows roster for current week or using input range"""

    # Work out dates for Start/End of Week
    if request.args.get("start_date") and request.args.get("end_date"):
        start = datetime.strptime(request.args.get("start_date"), "%Y-%m-%d")
        end = datetime.strptime(request.args.get("end_date"), "%Y-%m-%d")
    else:
        tz = timezone('Australia/Sydney')
        today = datetime.now(tz).date()
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)

    # Create dict of dates for specified range
    numDays = (end - start).days + 1
    dates = [dict() for x in range(0, numDays)]
    for x in range(0, numDays):
        date = start + timedelta(days=x)
        dates[x]["dateISO"] = date.strftime("%Y-%m-%d")
        dates[x]["datePretty"] = date.strftime("%d/%m/%Y")
        dates[x]["day"] = date.strftime("%A")

    users_query = User.query.order_by(User.real_name).all()
    if users_query:
        # Convert result to dict list
        users = []
        for user in users_query:
            data = {}
            for column in user.__table__.columns:
                data[column.name] = str(getattr(user, column.name))
            users.append(data)
    else:
        users = []

    locations_query = db.session.query(Shift.location).group_by(Shift.location).all()
    if locations_query:
        # Convert result to dict list
        locations = []
        for location in locations_query:
            locations.append({"location": location[0]})
    else:
        locations = []

    shifts_query = Shift.query.filter(Shift.date >= start, Shift.date <= end).order_by(Shift.start_time).all()
    if shifts_query:
        # Convert result to dict list
        shifts = []
        for shift in shifts_query:
            data = {}
            for column in shift.__table__.columns:
                data[column.name] = str(getattr(shift, column.name))
            data["date"] = shift.date.strftime("%Y-%m-%d")
            data["real_name"] = shift.shift_user.real_name
            shifts.append(data)
    else:
        shifts = []

    return render_template("roster.html", dates=dates, users=users, shifts=shifts, locations=locations)


@app.route("/deleteshift", methods=["POST"])
@manager_required
def deleteshift():
    """Delete shift from roster"""
    shift_id = request.form.get("shift_id")
    result = Shift.query.filter_by(shift_id=shift_id).delete()
    db.session.commit()
    if result:
        flash('Shift Succesfully Deleted')
    else:
        flash('Deletion Failed')
    return redirect(request.referrer)


@app.route("/updateroster", methods=["POST"])
@manager_required
def updateroster():
    """Update/Add shifts in roster"""
    print("Update Roster")
    if not request.form.get("user_id"):
        return apology("must provide user_id")
    if not request.form.get("date"):
        return apology("must provide date")
    if not request.form.get("location"):
        return apology("must provide location")
    if not request.form.get("start_time"):
        return apology("must provide start_time")
    if not request.form.get("end_time"):
        return apology("must provide end_time")
    if not request.form.get("break"):
        return apology("must provide break")
    user_id = request.form.get("user_id")
    date = request.form.get("date")
    location = request.form.get("location").lower()
    start_time = request.form.get("start_time")
    end_time = request.form.get("end_time")
    if (request.form.get("break") == "None"):
        sbreak = None
    else:
        sbreak = request.form.get("break")
    if (request.form.get("shift_id")):
        shift_id = request.form.get("shift_id")
        shift = Shift.query.get(shift_id)
        shift.user_id = user_id
        shift.date = datetime.strptime(date, "%Y-%m-%d")
        shift.location = location
        shift.start_time = start_time
        shift.end_time = end_time
        shift.sbreak = sbreak
        db.session.commit()

        return redirect(request.referrer)

    else:
        new_shift = Shift(date, start_time, end_time, location, user_id, sbreak)
        db.session.add(new_shift)
        db.session.commit()

        return redirect(request.referrer)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        username=request.form.get("username")

        # Ensure password was submitted
        if not request.form.get("password"):
            return apology("must provide password")

        # Query database for username
        rows = User.query.filter_by(username=username)

        # Ensure username exists and password is correct
        if rows.count() != 1 or not check_password_hash(rows[0].password, request.form.get("password")):
            return apology("invalid username and/or password")

        # Remember which user has logged in
        session["user_id"] = rows[0].id
        session["user_role"] = rows[0].role
        session["user_real_name"] = rows[0].real_name

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    flash('You were successfully logged out')
    return redirect("/")


@app.route("/updateuser", methods=["POST"])
@admin_required
def updateuser():
    """Add/Edit user"""

    # Ensure all fields were submitted
    if not request.form.get("username"):
        return apology("must provide username")
    elif not request.form.get("email"):
        return apology("must provide email")
    elif not request.form.get("real_name"):
        return apology("must provide real name")
    elif not request.form.get("role"):
        return apology("must provide role")

    # check if changing password or adding new user
    if request.form.get("changePass"):
        if not request.form.get("password"):
            return apology("must provide password")
        elif not request.form.get("confirmation"):
            return apology("must provide confirmation")
        elif not (request.form.get("password") == request.form.get("confirmation")):
            return apology("Password and confirmation don't match")
        pwd = generate_password_hash(request.form.get("password"))

    username = request.form.get("username")
    email = request.form.get("email")
    real_name = request.form.get("real_name")
    role = request.form.get("role")

    if request.form.get("user_id"):
        user_id = request.form.get("user_id")
        # Editing existing user
        user = User.query.get(user_id)
        user.username = username
        user.email = email
        user.real_name = real_name
        user.role = role
        db.session.commit()

        if request.form.get("changePass"):
            # If password changing
            user.password = pwd
            db.session.commit()

        flash('User succesfully modified')
        return redirect("/users")
    else:
        if not pwd:
            return apology("Missing password info")
        # Adding new user
        new_user = User(username, email, pwd, name, role)
        db.session.add(new_user)
        db.session.commit()

        flash('User succesfully registered')
        return redirect("/users")


@app.route("/changepass", methods=["GET", "POST"])
@login_required
def changepass():
    """Change Password of current user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure old password was submitted
        if not request.form.get("oldpass"):
            return apology("must provide old pass")
        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide new pass")
        elif not request.form.get("confirmation"):
            return apology("must provide confirmation")
        # Ensure passwords match
        elif not (request.form.get("password") == request.form.get("confirmation")):
            return apology("Password and confirmation don't match")
        # Check if old password matches
        user = User.query.filter_by(id=session["user_id"]).first()

        if not check_password_hash(user.password, request.form.get("oldpass")):
            return apology("Old password doesn't match")

        pwd = generate_password_hash(request.form.get("password"))
        user.password = pwd
        db.session.commit()

        flash('Password succefully changed')
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("changepass.html")


@app.route("/users",  methods=["GET"])
@admin_required
def users():
    """Show list of users"""
    users_query = User.query.order_by(User.id).all()
    if users_query:
        # Convert result to dict list
        users = []
        for user in users_query:
            data = {}
            for column in user.__table__.columns:
                data[column.name] = str(getattr(user, column.name))
            users.append(data)
    return render_template("users.html", users=users)


@app.route("/deleteuser",  methods=["POST"])
@admin_required
def delete_user():
    """Delete user"""
    if not request.form.get("id"):
        return apology("must provide id")
    user_id = request.form.get("id")
    result = User.query.filter_by(id=user_id).delete()
    db.session.commit()
    if not result:
        return apology("Could not delete user")
    else:
        flash('User succesfully deleted')
        return redirect("/users")

