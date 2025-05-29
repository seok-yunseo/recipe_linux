import requests, json, sqlite3
from bs4 import BeautifulSoup
import time
import re

def init_db():
    conn = sqlite3.connect('recipes.db')
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            recipe TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS recipe_ingredients (
            recipe_id INTEGER,
            ingredient_id INTEGER,
            FOREIGN KEY(recipe_id) REFERENCES recipes(id),
            FOREIGN KEY(ingredient_id) REFERENCES ingredients(id)
        )
    ''')
    conn.commit()
    conn.close()

def food_info(name):
    try:
        url = f"https://www.10000recipe.com/recipe/list.html?q={name}"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"[{name}] 검색 실패: HTTP {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        food_list = soup.find_all(attrs={'class': 'common_sp_link'})
        if not food_list:
            print(f"[{name}] 레시피 없음")
            return None

        food_id = food_list[0]['href'].split('/')[-1]
        new_url = f'https://www.10000recipe.com/recipe/{food_id}'
        new_response = requests.get(new_url)
        if new_response.status_code != 200:
            print(f"[{name}] 상세 페이지 실패")
            return None

        soup = BeautifulSoup(new_response.text, 'html.parser')
        food_info = soup.find(attrs={'type': 'application/ld+json'})
        result = json.loads(food_info.text)

        ingredient = ', '.join(result['recipeIngredient'])
        recipe = [f"{i+1}. {step['text']}" for i, step in enumerate(result['recipeInstructions'])]

        return {
            'name': name,
            'ingredients': ingredient,
            'recipe': recipe
        }

    except Exception as e:
        print(f"[{name}] ❌ 크롤링 중 오류 발생: {e}")
        return None

def save_to_db(info):
    conn = sqlite3.connect('recipes.db')
    cur = conn.cursor()

    cur.execute("SELECT id FROM recipes WHERE name = ?", (info['name'],))
    if cur.fetchone():
        print(f"[{info['name']}] 이미 DB에 있음 - 스킵")
        conn.close()
        return

    cur.execute("INSERT INTO recipes (name, recipe) VALUES (?, ?)", (info['name'], '\n'.join(info['recipe'])))
    recipe_id = cur.lastrowid

    for ingredient in info['ingredients'].split(', '):
        # 재료명과 수량 분리: 예) 배추 1/2포기 → 배추 + 1/2포기
        match = re.match(r'([가-힣\s]+)([\d\s\/\w\(\)\.]+)?', ingredient)
        if match:
            name = match.group(1).strip()
            amount = match.group(2).strip() if match.group(2) else None

            # 재료명 저장
            cur.execute("INSERT OR IGNORE INTO ingredients (name) VALUES (?)", (name,))
            cur.execute("SELECT id FROM ingredients WHERE name = ?", (name,))
            ing_id = cur.fetchone()[0]
            cur.execute("INSERT INTO recipe_ingredients (recipe_id, ingredient_id) VALUES (?, ?)", (recipe_id, ing_id))

            # 수량도 재료처럼 저장
            if amount:
                cur.execute("INSERT OR IGNORE INTO ingredients (name) VALUES (?)", (amount,))
                cur.execute("SELECT id FROM ingredients WHERE name = ?", (amount,))
                amt_id = cur.fetchone()[0]
                cur.execute("INSERT INTO recipe_ingredients (recipe_id, ingredient_id) VALUES (?, ?)", (recipe_id, amt_id))
        else:
            # 분리 실패 시 전체 문자열 저장
            cur.execute("INSERT OR IGNORE INTO ingredients (name) VALUES (?)", (ingredient,))
            cur.execute("SELECT id FROM ingredients WHERE name = ?", (ingredient,))
            ing_id = cur.fetchone()[0]
            cur.execute("INSERT INTO recipe_ingredients (recipe_id, ingredient_id) VALUES (?, ?)", (recipe_id, ing_id))

    conn.commit()
    conn.close()
    print(f"[{info['name']}] ✅ 저장 완료")

def load_menu(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

if __name__ == '__main__':
    init_db()
    food_list = load_menu('menu.txt')
    failures = []

    for food in food_list:
        try:
            info = food_info(food)
            if info:
                save_to_db(info)
            else:
                failures.append(food)
        except Exception as e:
            print(f"[{food}] 예외 발생: {e}")
            failures.append(food)
        time.sleep(1)

    # 실패한 음식 저장
    if failures:
        with open('failures.txt', 'w', encoding='utf-8') as f:
            for item in failures:
                f.write(item + '\n')
        print("\n❌ 크롤링 실패한 음식들이 failures.txt에 저장되었습니다.")

