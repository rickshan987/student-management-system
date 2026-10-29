
from flask import Flask, render_template, request, redirect, url_for
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)


def get_connection():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")

    return psycopg2.connect(
        database_url,
        sslmode="require",
        connect_timeout=10
    )


def load_students():
    conn = get_connection()

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, name, marks FROM students ORDER BY id"
            )
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


@app.route("/")
def home():
    students = load_students()
    search = request.args.get("search", "").strip().lower()

    visible_students = [
        (i, student)
        for i, student in enumerate(students)
        if search in student["name"].lower()
    ]

    average = (
        round(sum(float(s["marks"]) for s in students) / len(students), 2)
        if students else 0
    )

    return render_template(
        "index.html",
        students=students,
        visible_students=visible_students,
        average=average,
        search=search
    )


@app.route("/add", methods=["POST"])
def add_student():
    name = request.form.get("name", "").strip()

    try:
        marks = float(request.form.get("marks", ""))
    except ValueError:
        return "Please enter valid marks.", 400

    if not name or not 0 <= marks <= 100:
        return "Enter a name and marks between 0 and 100.", 400

    conn = get_connection()

    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO students (name, marks) VALUES (%s, %s)",
                    (name, marks)
                )
    finally:
        conn.close()

    return redirect(url_for("home"))


@app.route("/delete/<int:index>", methods=["POST"])
def delete_student(index):
    students = load_students()

    if 0 <= index < len(students):
        student_id = students[index]["id"]
        conn = get_connection()

        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "DELETE FROM students WHERE id = %s",
                        (student_id,)
                    )
        finally:
            conn.close()

    return redirect(url_for("home"))


@app.route("/edit/<int:index>", methods=["GET", "POST"])
def edit_student(index):
    students = load_students()

    if not 0 <= index < len(students):
        return "Student not found.", 404

    student = students[index]

    if request.method == "POST":
        name = request.form.get("name", "").strip()

        try:
            marks = float(request.form.get("marks", ""))
        except ValueError:
            return "Please enter valid marks.", 400

        if not name or not 0 <= marks <= 100:
            return "Enter a name and marks between 0 and 100.", 400

        conn = get_connection()

        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE students
                        SET name = %s, marks = %s
                        WHERE id = %s
                        """,
                        (name, marks, student["id"])
                    )
        finally:
            conn.close()

        return redirect(url_for("home"))

    return render_template(
        "edit.html",
        student=student,
        index=index
    )


if __name__ == "__main__":
    app.run(debug=True)
