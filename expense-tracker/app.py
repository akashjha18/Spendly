from flask import Flask, render_template, request, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db
from datetime import datetime

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Change this to a random secret in production


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        
        db = get_db()
        # Check if email already exists
        if db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
            db.close()
            return render_template("register.html", error="Email already registered")
        
        # Hash password and insert user
        hashed_password = generate_password_hash(password)
        db.execute("INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)", (name, email, hashed_password))
        db.commit()
        db.close()
        
        return redirect(url_for("login"))
    
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        db.close()
        
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("profile"))
        else:
            return render_template("login.html", error="Invalid email or password")
    
    return render_template("login.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    db.close()

    if not user:
        session.clear()
        return redirect(url_for("login"))

    return render_template("profile.html", user=user)


@app.route("/expenses")
def expenses():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    expenses_list = db.execute("SELECT * FROM expenses WHERE user_id = ? ORDER BY date DESC", (session["user_id"],)).fetchall()
    db.close()

    if not user:
        session.clear()
        return redirect(url_for("login"))

    # Calculate total spending
    total_spent = sum(exp["amount"] for exp in expenses_list)

    return render_template("expenses.html", user=user, expenses=expenses_list, total_spent=total_spent)


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        amount = request.form.get("amount", "").strip()
        description = request.form.get("description", "").strip()
        date = request.form.get("date", "").strip()

        # Validation
        errors = []
        if not amount:
            errors.append("Amount is required")
        else:
            try:
                amount = float(amount)
                if amount <= 0:
                    errors.append("Amount must be greater than 0")
            except ValueError:
                errors.append("Amount must be a valid number")

        if not date:
            errors.append("Date is required")
        else:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                errors.append("Date must be in YYYY-MM-DD format")

        if errors:
            return render_template("add_expense.html", errors=errors,
                                 amount=amount, description=description, date=date)

        # Insert into database
        db = get_db()
        db.execute("INSERT INTO expenses (user_id, amount, description, date) VALUES (?, ?, ?, ?)",
                  (session["user_id"], amount, description, date))
        db.commit()
        db.close()

        return redirect(url_for("expenses"))

    # GET request - show form with today's date as default
    today = datetime.now().strftime("%Y-%m-%d")
    return render_template("add_expense.html", date=today)


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    expense = db.execute("SELECT * FROM expenses WHERE id = ? AND user_id = ?",
                        (id, session["user_id"])).fetchone()

    if not expense:
        db.close()
        return redirect(url_for("expenses"))

    if request.method == "POST":
        amount = request.form.get("amount", "").strip()
        description = request.form.get("description", "").strip()
        date = request.form.get("date", "").strip()

        # Validation
        errors = []
        if not amount:
            errors.append("Amount is required")
        else:
            try:
                amount = float(amount)
                if amount <= 0:
                    errors.append("Amount must be greater than 0")
            except ValueError:
                errors.append("Amount must be a valid number")

        if not date:
            errors.append("Date is required")
        else:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                errors.append("Date must be in YYYY-MM-DD format")

        if errors:
            db.close()
            return render_template("edit_expense.html", expense=expense, errors=errors,
                                 amount=amount, description=description, date=date)

        # Update database
        db.execute("UPDATE expenses SET amount = ?, description = ?, date = ? WHERE id = ?",
                  (amount, description, date, id))
        db.commit()
        db.close()

        return redirect(url_for("expenses"))

    db.close()
    return render_template("edit_expense.html", expense=expense)


@app.route("/expenses/<int:id>/delete", methods=["POST"])
def delete_expense(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    # Verify expense belongs to user before deleting
    expense = db.execute("SELECT * FROM expenses WHERE id = ? AND user_id = ?",
                        (id, session["user_id"])).fetchone()

    if expense:
        db.execute("DELETE FROM expenses WHERE id = ?", (id,))
        db.commit()

    db.close()
    return redirect(url_for("expenses"))


if __name__ == "__main__":
    init_db()
    seed_db()
    app.run(debug=True, port=5001)
