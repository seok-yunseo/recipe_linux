from flask import Flask, request, render_template
import sqlite3

app = Flask(__name__)

def get_recipes(ingredients):
    conn = sqlite3.connect('recipes.db')
    cur = conn.cursor()
    ingredient_list = [i.strip() for i in ingredients.split(',') if i.strip()]
    if not ingredient_list:
        return []
    placeholders = ','.join(['?'] * len(ingredient_list))
    query = f"""
    SELECT DISTINCT r.name, r.recipe
    FROM recipes r
    JOIN recipe_ingredients ri ON r.id = ri.recipe_id
    JOIN ingredients i ON i.id = ri.ingredient_id
    WHERE i.name IN ({placeholders})
    """
    cur.execute(query, ingredient_list)
    rows = cur.fetchall()
    conn.close()
    return [{"name": row[0], "recipe": row[1]} for row in rows]

@app.route("/", methods=["GET", "POST"])
def index():
    recipes = []
    if request.method == "POST":
        ingredients = request.form["ingredients"]
        recipes = get_recipes(ingredients)
    return render_template("index.html", recipes=recipes)

@app.route("/recipe/<name>")
def recipe_detail(name):
    conn = sqlite3.connect('recipes.db')
    cur = conn.cursor()
    cur.execute("SELECT name, recipe FROM recipes WHERE name = ?", (name,))
    row = cur.fetchone()
    conn.close()
    if row:
        return render_template("recipe.html", recipe={"name": row[0], "recipe": row[1]})
    else:
        return f"{name} 레시피를 찾을 수 없습니다.", 404

# ✅ 이게 반드시 맨 마지막에 있어야 함!
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

