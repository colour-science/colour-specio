from curses import tparm


class Person:
    def __init__(self, fname: str, lname: str) -> None:
        self.name = fname + lname
        pass


class Doctor(Person):
    def __init__(self, type) -> None:
        super().__init__(fname="fname", lname="lname")
        self.type = type


d = Doctor("Opthamologist")

print(f"{d.name} - {d.type}")
