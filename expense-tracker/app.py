import os

import json
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
            session["user_avatar"] = user["avatar"] or "avatars/avatar1.svg"
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


@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    if not user:
        session.clear()
        return redirect(url_for("login"))

    # Get statistics
    total_expenses = db.execute("SELECT COUNT(*) as count, SUM(amount) as total FROM expenses WHERE user_id = ?", (session["user_id"],)).fetchone()
    total_budgets = db.execute("SELECT COUNT(*) as count FROM budgets WHERE user_id = ?", (session["user_id"],)).fetchone()
    total_categories = db.execute("SELECT COUNT(DISTINCT category_id) as count FROM expenses WHERE user_id = ? AND category_id IS NOT NULL", (session["user_id"],)).fetchone()

    stats = {
        'total_expenses_count': total_expenses['count'] or 0,
        'total_expenses_amount': total_expenses['total'] or 0,
        'total_budgets': total_budgets['count'] or 0,
        'total_categories': total_categories['count'] or 0,
        'account_created': user['id']  # Placeholder, since no created_at
    }

    edit_section = request.args.get('edit', '')
    show_profile_form = edit_section == 'profile'
    show_password_form = edit_section == 'password'
    show_preferences_form = edit_section == 'preferences'

    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_profile":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip()

            errors = []
            if not name:
                errors.append("Name is required")
            if not email:
                errors.append("Email is required")
            elif "@" not in email:
                errors.append("Invalid email format")

            existing_user = db.execute("SELECT id FROM users WHERE email = ? AND id != ?", (email, session["user_id"])).fetchone()
            if existing_user:
                errors.append("Email already in use")

            if errors:
                db.close()
                return render_template("profile.html", user=user, stats=stats, errors=errors, name=name, email=email, show_profile_form=True)

            db.execute("UPDATE users SET name = ?, email = ? WHERE id = ?", (name, email, session["user_id"]))
            db.commit()
            session["user_name"] = name
            db.close()
            return redirect(url_for("profile"))

        elif action == "change_password":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")

            errors = []
            if not check_password_hash(user["password_hash"], current_password):
                errors.append("Current password is incorrect")
            if len(new_password) < 6:
                errors.append("New password must be at least 6 characters")
            if new_password != confirm_password:
                errors.append("New passwords do not match")

            if errors:
                db.close()
                return render_template("profile.html", user=user, stats=stats, password_errors=errors, show_password_form=True)

            hashed_password = generate_password_hash(new_password)
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed_password, session["user_id"]))
            db.commit()
            db.close()
            return redirect(url_for("profile"))

        elif action == "update_preferences":
            currency = request.form.get("currency", "₹")
            date_format = request.form.get("date_format", "YYYY-MM-DD")

            session["currency"] = currency
            session["date_format"] = date_format
            db.close()
            return redirect(url_for("profile"))

        elif action == "update_notifications":
            email_budget = 1 if request.form.get("email_budget") else 0
            email_unusual = 1 if request.form.get("email_unusual") else 0
            
            db.execute(
                "UPDATE users SET notification_email_budget = ?, notification_email_unusual = ? WHERE id = ?",
                (email_budget, email_unusual, session["user_id"])
            )
            db.commit()
            flash("Notification settings updated successfully.", "success")
            db.close()
            return redirect(url_for("profile"))

        elif action == "update_budget_alerts":
            alert_50 = 1 if request.form.get("alert_50") else 0
            alert_75 = 1 if request.form.get("alert_75") else 0
            alert_100 = 1 if request.form.get("alert_100") else 0
            
            db.execute(
                "UPDATE users SET budget_alert_50 = ?, budget_alert_75 = ?, budget_alert_100 = ? WHERE id = ?",
                (alert_50, alert_75, alert_100, session["user_id"])
            )
            db.commit()
            flash("Budget alert settings updated successfully.", "success")
            db.close()
            return redirect(url_for("profile"))

        elif action == "update_default_categories":
            favorite_categories = request.form.getlist("favorite_categories")
            favorite_categories_str = json.dumps(favorite_categories)
            
            db.execute(
                "UPDATE users SET favorite_categories = ? WHERE id = ?",
                (favorite_categories_str, session["user_id"])
            )
            db.commit()
            flash("Default categories updated successfully.", "success")
            db.close()
            return redirect(url_for("profile"))

        elif action == "update_report_preferences":
            report_type = request.form.get("report_type", "monthly")
            report_frequency = request.form.get("report_frequency", "monthly")
            
            db.execute(
                "UPDATE users SET default_report_type = ?, default_report_frequency = ? WHERE id = ?",
                (report_type, report_frequency, session["user_id"])
            )
            db.commit()
            flash("Report preferences updated successfully.", "success")
            db.close()
            return redirect(url_for("profile"))

    db.close()
    
    # Get all categories for the categories preference form
    db = get_db()
    all_categories = db.execute("SELECT id, name, color FROM categories").fetchall()
    
    # Parse favorite categories from JSON
    favorite_categories = user["favorite_categories"] if user["favorite_categories"] else ""
    favorite_cat_ids = set()
    if favorite_categories:
        try:
            favorite_cat_ids = set(json.loads(favorite_categories))
        except (json.JSONDecodeError, TypeError):
            favorite_cat_ids = set()
    
    db.close()
    
    return render_template("profile.html", user=user, stats=stats,
                           show_profile_form=show_profile_form,
                           show_password_form=show_password_form,
                           show_preferences_form=show_preferences_form,
                           all_categories=all_categories,
                           favorite_cat_ids=favorite_cat_ids)


@app.route("/export")
def export_data():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    expenses = db.execute("SELECT e.*, c.name as category_name FROM expenses e LEFT JOIN categories c ON e.category_id = c.id WHERE e.user_id = ?", (session["user_id"],)).fetchall()
    budgets = db.execute("SELECT b.*, c.name as category_name FROM budgets b LEFT JOIN categories c ON b.category_id = c.id WHERE b.user_id = ?", (session["user_id"],)).fetchall()
    db.close()

    # Convert to dict for JSON
    expenses_data = [dict(row) for row in expenses]
    budgets_data = [dict(row) for row in budgets]

    data = {
        "expenses": expenses_data,
        "budgets": budgets_data
    }

    import json
    response = app.response_class(
        response=json.dumps(data, indent=2),
        mimetype='application/json',
        headers={"Content-Disposition": "attachment;filename=data.json"}
    )
    return response


@app.route("/delete_account", methods=["POST"])
def delete_account():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    db.execute("DELETE FROM expenses WHERE user_id = ?", (session["user_id"],))
    db.execute("DELETE FROM budgets WHERE user_id = ?", (session["user_id"],))
    db.execute("DELETE FROM users WHERE id = ?", (session["user_id"],))
    db.commit()
    db.close()

    session.clear()
    return redirect(url_for("landing"))


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
        "SELECT b.*, c.name AS category_name FROM budgets b LEFT JOIN categories c ON b.category_id = c.id WHERE b.user_id = ? ORDER BY b.category_id IS NULL, c.name",
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
