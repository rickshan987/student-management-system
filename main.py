students = []

def add_student():
    name = input("Enter student name: ")
    marks = float(input("Enter marks: "))

    students.append({
        "name": name,
        "marks": marks
    })

    print("Student added successfully!")

def view_students():
    for student in students:
        print(student["name"], student["marks"])

while True:
    print("\n1. Add Student")
    print("2. View Students")
    print("3. Exit")

    choice = input("Enter your choice: ")

    if choice == "1":
        add_student()
    elif choice == "2":
        view_students()
    elif choice == "3":
        break
    else:
        print("Invalid choice")