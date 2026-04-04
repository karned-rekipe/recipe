from enum import Enum


class MealCategory(str, Enum):
    aperitif = "aperitif"
    hors_doeuvre = "hors_doeuvre"
    soup = "soup"
    cold_starter = "cold_starter"
    hot_starter = "hot_starter"
    first_course = "first_course"
    second_course = "second_course"
    salad = "salad"
    cheese = "cheese"
    entremet = "entremet"
    dessert = "dessert"
    fresh_fruit = "fresh_fruit"
    coffee = "coffee"
    digestif = "digestif"
    bread = "bread"
