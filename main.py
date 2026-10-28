
from flask import Flask, render_template, request, redirect, url_for
import json
import os

app = Flask(__name__)
FILE_NAME = "students.json"


def load_students():
    if os.path.exists(FILE_NAME):
        with open(FILE_NAME, "r") as file:
            return json.load(file)
    return []


def save_students():
    with open(FILE_NAME, "w") as file:
        json.dump(students, file, indent=4)


students = load_students()


@app.route("/")
def home():
    search = request.args.get("search", "").strip().lower()

    visible_students = [
        (i, student)
        for i, student in enumerate(students)
        if search in student["name"].lower()
    ]

    average = (
        round(sum(s["marks"] for s in students) / len(students), 2)
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

    students.append({"name": name, "marks": marks})
    save_students()
    return redirect(url_for("home"))


@app.route("/delete/<int:index>", methods=["POST"])
def delete_student(index):
    if 0 <= index < len(students):
        students.pop(index)
        save_students()

    return redirect(url_for("home"))


@app.route("/edit/<int:index>", methods=["GET", "POST"])
def edit_student(index):
    if not 0 <= index < len(students):
        return "Student not found.", 404

    if request.method == "POST":
        name = request.form.get("name", "").strip()

        try:
            marks = float(request.form.get("marks", ""))
        except ValueError:
            return "Please enter valid marks.", 400

        if not name or not 0 <= marks <= 100:
            return "Enter a name and marks between 0 and 100.", 400

        students[index] = {"name": name, "marks": marks}
        save_students()
        return redirect(url_for("home"))

    return render_template(
        "edit.html",
        student=students[index],
        index=index
    )


if __name__ == "__main__":
    app.run(debug=True)
