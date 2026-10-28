
import json
import os

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


def add_student():
    name = input("Enter student name: ").strip()

    try:
        marks = float(input("Enter marks (0-100): "))
    except ValueError:
        print("Please enter valid marks.")
        return

    if not name:
        print("Name cannot be empty.")
        return

    if not 0 <= marks <= 100:
        print("Marks must be between 0 and 100.")
        return

    students.append({"name": name, "marks": marks})
    save_students()
    print("Student added successfully!")


def view_students():
    if not students:
        print("No students found.")
        return

    for student in students:
        print(f"Name: {student['name']}, Marks: {student['marks']}")


def search_student():
    name = input("Enter name to search: ").strip().lower()

    for student in students:
        if student["name"].lower() == name:
            print(f"Name: {student['name']}, Marks: {student['marks']}")
            return

    print("Student not found.")


def average_marks():
    if not students:
        print("No marks available.")
        return

    average = sum(s["marks"] for s in students) / len(students)
    print(f"Average marks: {average:.2f}")


while True:
    print("\n--- Student Management System ---")
    print("1. Add Student")
    print("2. View Students")
    print("3. Search Student")
    print("4. Calculate Average Marks")
    print("5. Exit")

    choice = input("Enter your choice: ")

    if choice == "1":
        add_student()
    elif choice == "2":
        view_students()
    elif choice == "3":
        search_student()
    elif choice == "4":
        average_marks()
    elif choice == "5":
        print("Thank you!")
        break
    else:
        print("Invalid choice. Try again.")
