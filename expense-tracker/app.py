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

    # Get filter parameters
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()
    category_id = request.args.get('category', '').strip()
    search = request.args.get('search', '').strip()

    query = """
        SELECT e.*, c.name as category_name, c.color as category_color 
        FROM expenses e 
        LEFT JOIN categories c ON e.category_id = c.id 
        WHERE e.user_id = ?
    """
    params = [session["user_id"]]

    if date_from:
        query += " AND e.date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND e.date <= ?"
        params.append(date_to)
    if category_id:
        query += " AND e.category_id = ?"
        params.append(category_id)
    if search:
        query += " AND e.description LIKE ?"
        params.append(f"%{search}%")

    query += " ORDER BY e.date DESC"
    expenses_list = db.execute(query, params).fetchall()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()

    # Budget warnings for this month
    current_month = datetime.now().strftime('%Y-%m')
    month_total_row = db.execute(
        "SELECT SUM(amount) as total FROM expenses WHERE user_id = ? AND strftime('%Y-%m', date) = ?",
        (session['user_id'], current_month)
    ).fetchone()
    month_total = month_total_row['total'] or 0

    budgets = db.execute(
        "SELECT b.*, c.name AS category_name FROM budgets b LEFT JOIN categories c ON b.category_id = c.id WHERE b.user_id = ?",
        (session['user_id'],)
    ).fetchall()

    budget_warnings = []
    for budget in budgets:
        budget_amount = budget['amount']
        budget_label = budget['category_name'] or 'Overall monthly'

        if budget['category_id'] is None:
            current_value = month_total
        else:
            category_row = db.execute(
                "SELECT SUM(amount) as total FROM expenses WHERE user_id = ? AND category_id = ? AND strftime('%Y-%m', date) = ?",
                (session['user_id'], budget['category_id'], current_month)
            ).fetchone()
            current_value = category_row['total'] or 0

        if current_value >= budget_amount:
            budget_warnings.append(
                f"Budget exceeded for {budget_label}: ₹{current_value:.2f} / ₹{budget_amount:.2f}."
            )
        elif current_value >= budget_amount * 0.9:
            budget_warnings.append(
                f"Approaching budget for {budget_label}: ₹{current_value:.2f} / ₹{budget_amount:.2f}."
            )

    db.close()

    if not user:
        session.clear()
        return redirect(url_for("login"))

    total_spent = sum(exp["amount"] for exp in expenses_list)

    return render_template("expenses.html", user=user, expenses=expenses_list,
                         total_spent=total_spent, categories=categories,
                         budget_warnings=budget_warnings)


@app.route("/expenses/<int:id>/delete", methods=["POST"])
def delete_expense(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    expense = db.execute("SELECT * FROM expenses WHERE id = ? AND user_id = ?",
                        (id, session["user_id"])).fetchone()

    if expense:
        db.execute("DELETE FROM expenses WHERE id = ?", (id,))
        db.commit()

    db.close()
    return redirect(url_for("expenses"))


@app.route("/budgets", methods=["GET", "POST"])
def budgets():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    errors = []

    if request.method == "POST":
        amount = request.form.get('amount', '').strip()
        category_id = request.form.get('category_id', '').strip()

        if not amount:
            errors.append('Budget amount is required')
        else:
            try:
                amount = float(amount)
                if amount <= 0:
                    errors.append('Budget must be greater than 0')
            except ValueError:
                errors.append('Budget must be a valid number')

        if category_id:
            try:
                category_id = int(category_id)
            except ValueError:
                errors.append('Invalid category selection')
        else:
            category_id = None

        if not errors:
            db.execute(
                "INSERT INTO budgets (user_id, category_id, amount, period) VALUES (?, ?, ?, ?)",
                (session['user_id'], category_id, amount, 'monthly')
            )
            db.commit()
            db.close()
            return redirect(url_for('budgets'))

    budgets_list = db.execute(
        "SELECT b.*, c.name AS category_name, c.color AS category_color FROM budgets b LEFT JOIN categories c ON b.category_id = c.id WHERE b.user_id = ? ORDER BY b.category_id IS NULL, c.name",
        (session['user_id'],)
    ).fetchall()
    db.close()

    return render_template('budgets.html', user=user, categories=categories, budgets=budgets_list, errors=errors)


@app.route("/budgets/<int:id>/delete", methods=["POST"])
def delete_budget(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    db.execute("DELETE FROM budgets WHERE id = ? AND user_id = ?", (id, session['user_id']))
    db.commit()
    db.close()
    return redirect(url_for('budgets'))


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()
    db.close()

    if request.method == "POST":
        amount = request.form.get("amount", "").strip()
        description = request.form.get("description", "").strip()
        date = request.form.get("date", "").strip()
        category_id = request.form.get("category_id", "").strip()

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

        if not category_id:
            errors.append("Category is required")
        else:
            try:
                category_id = int(category_id)
            except ValueError:
                errors.append("Invalid category")

        if errors:
            return render_template("add_expense.html", errors=errors,
                                 amount=amount, description=description, date=date, 
                                 category_id=category_id, categories=categories)

        # Insert into database
        db = get_db()
        db.execute("INSERT INTO expenses (user_id, category_id, amount, description, date) VALUES (?, ?, ?, ?, ?)",
                  (session["user_id"], category_id, amount, description, date))
        db.commit()
        db.close()

        return redirect(url_for("expenses"))

    # GET request - show form with today's date as default
    today = datetime.now().strftime("%Y-%m-%d")
    return render_template("add_expense.html", date=today, categories=categories)


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

    categories = db.execute("SELECT * FROM categories ORDER BY name").fetchall()

    if request.method == "POST":
        amount = request.form.get("amount", "").strip()
        description = request.form.get("description", "").strip()
        date = request.form.get("date", "").strip()
        category_id = request.form.get("category_id", "").strip()

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

        if not category_id:
            errors.append("Category is required")
        else:
            try:
                category_id = int(category_id)
            except ValueError:
                errors.append("Invalid category")

        if errors:
            db.close()
            return render_template("edit_expense.html", expense=expense, errors=errors,
                                 amount=amount, description=description, date=date,
                                 category_id=category_id, categories=categories)

        # Update database
        db.execute("UPDATE expenses SET category_id = ?, amount = ?, description = ?, date = ? WHERE id = ?",
                  (category_id, amount, description, date, id))
        db.commit()
        db.close()

        return redirect(url_for("expenses"))

    db.close()
    return render_template("edit_expense.html", expense=expense, categories=categories)


@app.route("/reports")
def reports():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    
    if not user:
        session.clear()
        return redirect(url_for("login"))

    # Get spending by category
    category_spending = db.execute("""
        SELECT c.name as category, c.color, SUM(e.amount) as total
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = ?
        GROUP BY c.id, c.name, c.color
        ORDER BY total DESC
    """, (session["user_id"],)).fetchall()

    # Get spending over time (last 30 days)
    from datetime import datetime, timedelta
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    
    daily_spending = db.execute("""
        SELECT date, SUM(amount) as total
        FROM expenses
        WHERE user_id = ? AND date >= ? AND date <= ?
        GROUP BY date
        ORDER BY date
    """, (session["user_id"], str(start_date), str(end_date))).fetchall()

    # Get monthly spending (last 12 months)
    monthly_spending = db.execute("""
        SELECT strftime('%Y-%m', date) as month, SUM(amount) as total
        FROM expenses
        WHERE user_id = ?
        GROUP BY strftime('%Y-%m', date)
        ORDER BY month DESC
        LIMIT 12
    """, (session["user_id"],)).fetchall()

    db.close()

    # Convert Row objects to dictionaries for JSON serialization
    category_spending = [dict(row) for row in category_spending]
    daily_spending = [dict(row) for row in daily_spending]
    monthly_spending = [dict(row) for row in monthly_spending]

    return render_template("reports.html", 
                         user=user,
                         category_spending=category_spending,
                         daily_spending=daily_spending,
                         monthly_spending=monthly_spending)


if __name__ == "__main__":
    init_db()
    seed_db()
    app.run(debug=True, port=5001)
