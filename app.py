
# AI assistance: ChatGPT helped explain Flask routing, SQLite,
# and input validation during development. I reviewed and tested
# the implementation and am responsible for understanding it.

import sqlite3
from datetime import date, timedelta
from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)
DATABASE = "studyflow.db"


def get_db_connection():
    """Open a connection to the SQLite database."""
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Create the tasks table if it does not exist."""
    connection = get_db_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            due_date TEXT NOT NULL,
            priority TEXT NOT NULL
                CHECK(priority IN ('Low', 'Medium', 'High')),
            completed INTEGER NOT NULL DEFAULT 0
                CHECK(completed IN (0, 1))
        )
    """)

    connection.commit()
    connection.close()



@app.route("/")
def index():
    """Display tasks with optional search and filters."""
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "all")
    priority = request.args.get("priority", "all")

    connection = get_db_connection()

    query = "SELECT * FROM tasks WHERE 1=1"
    parameters = []

    if search:
        query += " AND (title LIKE ? OR subject LIKE ?)"
        parameters.extend([f"%{search}%", f"%{search}%"])

    if status == "pending":
        query += " AND completed = 0"
    elif status == "completed":
        query += " AND completed = 1"

    if priority in ("Low", "Medium", "High"):
        query += " AND priority = ?"
        parameters.append(priority)

    query += " ORDER BY completed ASC, due_date ASC, id DESC"

    tasks = connection.execute(query, parameters).fetchall()

    # Calculate dashboard statistics across all assignments.
    stats = connection.execute("""
        SELECT
            COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END), 0)
                AS pending,
            COALESCE(SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END), 0)
                AS completed,
            COALESCE(SUM(
                CASE
                    WHEN completed = 0 AND due_date < ? THEN 1
                    ELSE 0
                END
            ), 0) AS overdue
        FROM tasks
    """, (date.today().isoformat(),)).fetchone()


    # Calculate assignment totals for each subject.
    subjects = connection.execute("""
        SELECT
            subject,
            COUNT(*) AS total,
            SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END)
                AS completed
        FROM tasks
        WHERE TRIM(subject) != ''
        GROUP BY subject
        ORDER BY subject COLLATE NOCASE
    """).fetchall()
    connection.close()
    today = date.today().isoformat()
    due_soon_date = (date.today() + timedelta(days=3)).isoformat()

    progress = (
        round(stats["completed"] / stats["total"] * 100)
        if stats["total"] else 0
    )

    return render_template(
        "index.html",
        tasks=tasks,
        today=date.today().isoformat(),
        due_soon_date = (date.today() + timedelta(days=3)).isoformat(),
        search=search,
        status=status,
        priority=priority,
        stats=stats,
        progress=progress,
        subjects=subjects
    )

@app.route("/add", methods=["POST"])
def add_task():
    """Validate and save a new assignment."""
    title = request.form.get("title", "").strip()
    subject = request.form.get("subject", "").strip()
    due_date = request.form.get("due_date", "").strip()
    priority = request.form.get("priority", "")

    if not title or not subject or not due_date:
        return "Title, subject, and due date are required.", 400

    try:
        parsed_date = date.fromisoformat(due_date)
        if parsed_date.isoformat() != due_date:
            raise ValueError
    except ValueError:
        return "Please enter a valid due date.", 400

    if priority not in ("Low", "Medium", "High"):
        return "Invalid priority.", 400

    connection = get_db_connection()

    connection.execute("""
        INSERT INTO tasks (title, subject, due_date, priority)
        VALUES (?, ?, ?, ?)
    """, (title, subject, due_date, priority))

    connection.commit()
    connection.close()

    return redirect(url_for("index"))


@app.route("/complete/<int:task_id>", methods=["POST"])
def complete_task(task_id):
    """Toggle a task between incomplete and completed."""
    connection = get_db_connection()

    connection.execute("""
        UPDATE tasks
        SET completed = CASE
            WHEN completed = 0 THEN 1
            ELSE 0
        END
        WHERE id = ?
    """, (task_id,))

    connection.commit()
    connection.close()

    return redirect(url_for("index"))


@app.route("/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    """Delete an assignment."""
    connection = get_db_connection()

    connection.execute(
        "DELETE FROM tasks WHERE id = ?",
        (task_id,)
    )

    connection.commit()
    connection.close()

    return redirect(url_for("index"))


@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    """Display an assignment and save any valid changes."""
    connection = get_db_connection()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "").strip()
        due_date = request.form.get("due_date", "").strip()
        priority = request.form.get("priority", "")

        if not title or not subject or not due_date:
            connection.close()
            return "Title, subject, and due date are required.", 400

        try:
            parsed_date = date.fromisoformat(due_date)
            if parsed_date.isoformat() != due_date:
                raise ValueError
        except ValueError:
            connection.close()
            return "Please enter a valid due date.", 400

        if priority not in ("Low", "Medium", "High"):
            connection.close()
            return "Invalid priority.", 400

        result = connection.execute("""
            UPDATE tasks
            SET title = ?, subject = ?, due_date = ?, priority = ?
            WHERE id = ?
        """, (title, subject, due_date, priority, task_id))

        connection.commit()
        connection.close()

        if result.rowcount == 0:
            return "Assignment not found.", 404

        return redirect(url_for("index"))

    task = connection.execute(
        "SELECT * FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()

    connection.close()

    if task is None:
        return "Assignment not found.", 404

    return render_template("edit.html", task=task)
# Create the database table when the application starts.
init_db()

if __name__ == "__main__":
    app.run(debug=True)
