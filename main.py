from flask import Flask, render_template, request, redirect, url_for, flash
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")


def get_connection():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured.")
    return psycopg2.connect(database_url, sslmode="require", connect_timeout=10)


def init_db():
    """Create new tables and safely migrate existing student records."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS students (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        marks DOUBLE PRECISION NOT NULL DEFAULT 0
                            CHECK (marks >= 0 AND marks <= 100)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS subjects (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL UNIQUE
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS student_marks (
                        id SERIAL PRIMARY KEY,
                        student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                        subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
                        marks DOUBLE PRECISION NOT NULL CHECK (marks >= 0 AND marks <= 100),
                        UNIQUE(student_id, subject_id)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS grade_rules (
                        id SERIAL PRIMARY KEY,
                        grade TEXT NOT NULL UNIQUE,
                        min_marks DOUBLE PRECISION NOT NULL,
                        max_marks DOUBLE PRECISION,
                        CHECK (min_marks >= 0 AND min_marks <= 100),
                        CHECK (max_marks IS NULL OR (max_marks > min_marks AND max_marks <= 100))
                    )
                """)
                cur.execute("SELECT COUNT(*) FROM grade_rules")
                if cur.fetchone()[0] == 0:
                    defaults = [
                        ("A+", 95, 100), ("A", 90, 95), ("B+", 80, 90),
                        ("B", 70, 80), ("C+", 60, 70), ("C", 50, 60),
                        ("D", 0, 50)
                    ]
                    cur.executemany(
                        "INSERT INTO grade_rules (grade, min_marks, max_marks) VALUES (%s, %s, %s)",
                        defaults
                    )
                # Keep the old single-mark records visible: move them into a
                # default subject only if there are existing students and no subjects.
                cur.execute("SELECT COUNT(*) FROM subjects")
                if cur.fetchone()[0] == 0:
                    cur.execute("SELECT COUNT(*) FROM students")
                    if cur.fetchone()[0] > 0:
                        cur.execute("INSERT INTO subjects (name) VALUES ('General') RETURNING id")
                        general_id = cur.fetchone()[0]
                        cur.execute("""
                            INSERT INTO student_marks (student_id, subject_id, marks)
                            SELECT s.id, %s, s.marks
                            FROM students s
                            WHERE NOT EXISTS (
                                SELECT 1 FROM student_marks sm
                                WHERE sm.student_id = s.id AND sm.subject_id = %s
                            )
                        """, (general_id, general_id))
    finally:
        conn.close()


def fetch_all(query, params=()):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def execute(query, params=()):
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
    finally:
        conn.close()


def grade_for(mark, rules):
    for rule in rules:
        low = float(rule["min_marks"])
        high = rule["max_marks"]
        if mark >= low and (high is None or mark < float(high) or (float(high) == 100 and mark <= 100)):
            return rule["grade"]
    return "D"


def dashboard_data():
    students = fetch_all("SELECT id, name FROM students ORDER BY id")
    subjects = fetch_all("SELECT id, name FROM subjects ORDER BY name")
    rules = fetch_all("SELECT id, grade, min_marks, max_marks FROM grade_rules ORDER BY min_marks DESC")
    marks = fetch_all("""
        SELECT sm.id, sm.student_id, sm.subject_id, sm.marks,
               s.name AS student_name, sub.name AS subject_name
        FROM student_marks sm
        JOIN students s ON s.id = sm.student_id
        JOIN subjects sub ON sub.id = sm.subject_id
        ORDER BY s.name, sub.name
    """)
    for row in marks:
        row["grade"] = grade_for(float(row["marks"]), rules)

    by_student = {}
    by_subject = {}
    for row in marks:
        by_student.setdefault(row["student_id"], []).append(float(row["marks"]))
        by_subject.setdefault(row["subject_id"], []).append(row)

    student_summaries = []
    for student in students:
        values = by_student.get(student["id"], [])
        avg = round(sum(values) / len(values), 2) if values else None
        student_summaries.append({
            **student, "average": avg,
            "grade": grade_for(avg, rules) if avg is not None else "—",
            "subject_count": len(values)
        })

    ranked = [s for s in student_summaries if s["average"] is not None]
    topper = max(ranked, key=lambda s: s["average"]) if ranked else None
    overall_values = [float(m["marks"]) for m in marks]
    overall_average = round(sum(overall_values) / len(overall_values), 2) if overall_values else 0
    subject_topper = {}
    for subject in subjects:
        entries = by_subject.get(subject["id"], [])
        subject_topper[subject["id"]] = max(entries, key=lambda x: float(x["marks"])) if entries else None

    return {
        "students": students, "subjects": subjects, "rules": rules, "marks": marks,
        "student_summaries": student_summaries, "topper": topper,
        "overall_average": overall_average, "subject_topper": subject_topper,
        "total_marks": len(marks)
    }


@app.route("/")
def home():
    init_db()
    data = dashboard_data()
    return render_template("index.html", **data)


@app.route("/students/add", methods=["POST"])
def add_student():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Please enter a student name.", "error")
        return redirect(url_for("home"))
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO students (name, marks) VALUES (%s, 0)", (name,))
    finally:
        conn.close()
    flash("Student added successfully.", "success")
    return redirect(url_for("home"))


@app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
def edit_student(student_id):
    student_rows = fetch_all("SELECT id, name FROM students WHERE id = %s", (student_id,))
    if not student_rows:
        return "Student not found.", 404
    student = student_rows[0]
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Student name cannot be empty.", "error")
            return redirect(url_for("edit_student", student_id=student_id))
        execute("UPDATE students SET name = %s WHERE id = %s", (name, student_id))
        flash("Student updated.", "success")
        return redirect(url_for("home"))
    return render_template("edit.html", student=student)


@app.route("/students/<int:student_id>/delete", methods=["POST"])
def delete_student(student_id):
    execute("DELETE FROM students WHERE id = %s", (student_id,))
    flash("Student deleted. Their subject marks were also removed.", "success")
    return redirect(url_for("home"))


@app.route("/subjects/add", methods=["POST"])
def add_subject():
    name = request.form.get("name", "").strip()
    if not name:
        flash("Enter a subject name.", "error")
    else:
        try:
            execute("INSERT INTO subjects (name) VALUES (%s)", (name,))
            flash("Subject added.", "success")
        except psycopg2.errors.UniqueViolation:
            flash("That subject already exists.", "error")
    return redirect(url_for("home"))


@app.route("/subjects/<int:subject_id>/edit", methods=["POST"])
def edit_subject(subject_id):
    name = request.form.get("name", "").strip()
    if name:
        try:
            execute("UPDATE subjects SET name = %s WHERE id = %s", (name, subject_id))
            flash("Subject updated.", "success")
        except psycopg2.errors.UniqueViolation:
            flash("A subject with that name already exists.", "error")
    return redirect(url_for("home"))


@app.route("/subjects/<int:subject_id>/delete", methods=["POST"])
def delete_subject(subject_id):
    execute("DELETE FROM subjects WHERE id = %s", (subject_id,))
    flash("Subject and its marks deleted.", "success")
    return redirect(url_for("home"))


@app.route("/marks/save", methods=["POST"])
def save_mark():
    try:
        student_id = int(request.form.get("student_id", ""))
        subject_id = int(request.form.get("subject_id", ""))
        mark = float(request.form.get("marks", ""))
        if not 0 <= mark <= 100:
            raise ValueError
        execute("""
            INSERT INTO student_marks (student_id, subject_id, marks)
            VALUES (%s, %s, %s)
            ON CONFLICT (student_id, subject_id)
            DO UPDATE SET marks = EXCLUDED.marks
        """, (student_id, subject_id, mark))
        flash("Subject mark saved.", "success")
    except (ValueError, TypeError):
        flash("Enter valid marks between 0 and 100.", "error")
    except psycopg2.errors.ForeignKeyViolation:
        flash("Please select an existing student and subject.", "error")
    return redirect(url_for("home"))


@app.route("/marks/<int:mark_id>/delete", methods=["POST"])
def delete_mark(mark_id):
    execute("DELETE FROM student_marks WHERE id = %s", (mark_id,))
    flash("Mark deleted.", "success")
    return redirect(url_for("home"))


@app.route("/grades/add", methods=["POST"])
def add_grade():
    grade = request.form.get("grade", "").strip().upper()
    try:
        low = float(request.form.get("min_marks", ""))
        high_text = request.form.get("max_marks", "").strip()
        high = float(high_text) if high_text else None
        if not grade or not 0 <= low <= 100 or (high is not None and not low < high <= 100):
            raise ValueError
        execute("INSERT INTO grade_rules (grade, min_marks, max_marks) VALUES (%s, %s, %s)", (grade, low, high))
        flash("Grade rule added.", "success")
    except (ValueError, TypeError):
        flash("Check the grade name and mark range.", "error")
    except psycopg2.errors.UniqueViolation:
        flash("That grade already exists.", "error")
    return redirect(url_for("home"))


@app.route("/grades/<int:rule_id>/edit", methods=["POST"])
def edit_grade(rule_id):
    grade = request.form.get("grade", "").strip().upper()
    try:
        low = float(request.form.get("min_marks", ""))
        high_text = request.form.get("max_marks", "").strip()
        high = float(high_text) if high_text else None
        if not grade or not 0 <= low <= 100 or (high is not None and not low < high <= 100):
            raise ValueError
        execute("UPDATE grade_rules SET grade=%s, min_marks=%s, max_marks=%s WHERE id=%s",
                (grade, low, high, rule_id))
        flash("Grade rule updated.", "success")
    except (ValueError, TypeError):
        flash("Check the grade name and mark range.", "error")
    except psycopg2.errors.UniqueViolation:
        flash("That grade already exists.", "error")
    return redirect(url_for("home"))


@app.route("/grades/<int:rule_id>/delete", methods=["POST"])
def delete_grade(rule_id):
    execute("DELETE FROM grade_rules WHERE id = %s", (rule_id,))
    flash("Grade rule deleted.", "success")
    return redirect(url_for("home"))


@app.route("/health")
def health():
    init_db()
    return {"status": "ok", "database": "connected"}


if __name__ == "__main__":
    app.run(debug=True)
