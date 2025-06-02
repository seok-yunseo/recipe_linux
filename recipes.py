import requests, json, sqlite3
from bs4 import BeautifulSoup
import time
import re

# DB 초기화 함수: recipes, ingredients, recipe_ingredients 테이블 생성
def init_db():
    conn = sqlite3.connect('recipes.db') # recipes.db 파일로 SQLite 연결
    cur = conn.cursor()
    
    # recipes 테이블: 레시피 ID, 이름, 조리법 저장 (이름은 고유)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            recipe TEXT
        )
    ''')
    
    # ingredients 테이블: 재료 ID, 재료명 저장 (재료명은 고유)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    ''')
    
    # recipe_ingredients 테이블: 레시피와 재료를 연결하는 다대다 관계 테이블
    cur.execute('''
        CREATE TABLE IF NOT EXISTS recipe_ingredients (
            recipe_id INTEGER,
            ingredient_id INTEGER,
            FOREIGN KEY(recipe_id) REFERENCES recipes(id),
            FOREIGN KEY(ingredient_id) REFERENCES ingredients(id)
        )
    ''')
    conn.commit() # 변경사항 저장
    conn.close() # DB 연결 종료

# 특정 음식 이름으로 10000recipe.com에서 레시피 크롤링하는 함수
def food_info(name):
    try:
        # 검색 결과 페이지 URL 생성
        url = f"https://www.10000recipe.com/recipe/list.html?q={name}"
        response = requests.get(url)
        if response.status_code != 200: # 요청 실패 시 None 반환
            print(f"[{name}] 검색 실패: HTTP {response.status_code}")
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        food_list = soup.find_all(attrs={'class': 'common_sp_link'}) # 레시피 링크 리스트 찾기
        if not food_list: # 검색 결과 없으면 None 반환
            print(f"[{name}] 레시피 없음")
            return None
            
        # 첫 번째 레시피 링크에서 레시피 ID 추출
        food_id = food_list[0]['href'].split('/')[-1]
        new_url = f'https://www.10000recipe.com/recipe/{food_id}'
        new_response = requests.get(new_url)
        if new_response.status_code != 200: # 상세 페이지 요청 실패 시 None 반환
            print(f"[{name}] 상세 페이지 실패")
            return None

        soup = BeautifulSoup(new_response.text, 'html.parser')
        food_info = soup.find(attrs={'type': 'application/ld+json'}) # JSON-LD 형식 레시피 정보 추출
        result = json.loads(food_info.text)

        # 재료 리스트를 쉼표로 연결한 문자열로 변환
        ingredient = ', '.join(result['recipeIngredient'])
        # 조리법 리스트: 각 단계 번호와 설명 문자열로 리스트 생성
        recipe = [f"{i+1}. {step['text']}" for i, step in enumerate(result['recipeInstructions'])]

         # 음식 이름, 재료, 조리법 반환
        return {
            'name': name,
            'ingredients': ingredient,
            'recipe': recipe
        }

    except Exception as e:
        # 크롤링 과정에서 에러 발생 시 메시지 출력 후 None 반환
        print(f"[{name}] ❌ 크롤링 중 오류 발생: {e}")
        return None

# 크롤링한 레시피 정보를 DB에 저장하는 함수
def save_to_db(info):
    conn = sqlite3.connect('recipes.db')
    cur = conn.cursor()

    # 동일한 이름의 레시피가 이미 있는지 확인
    cur.execute("SELECT id FROM recipes WHERE name = ?", (info['name'],))
    if cur.fetchone():
        print(f"[{info['name']}] 이미 DB에 있음 - 스킵")
        conn.close()
        return

    # recipes 테이블에 레시피명과 조리법 저장 (조리법은 리스트를 줄바꿈 문자로 합침)
    cur.execute("INSERT INTO recipes (name, recipe) VALUES (?, ?)", (info['name'], '\n'.join(info['recipe'])))
    recipe_id = cur.lastrowid # 방금 저장한 레시피의 ID 얻기

    # 재료 문자열을 ', ' 기준으로 나누어 각각 처리
    for ingredient in info['ingredients'].split(', '):
        # 재료명과 수량 분리: 예) 배추 1/2포기 → 배추 + 1/2포기
        match = re.match(r'([가-힣\s]+)([\d\s\/\w\(\)\.]+)?', ingredient)
        if match:
            name = match.group(1).strip() # 재료명 추출
            amount = match.group(2).strip() if match.group(2) else None # 수량 추출 (없을 수도 있음)

            # 재료명을 ingredients 테이블에 저장 (중복 삽입 방지)
            cur.execute("INSERT OR IGNORE INTO ingredients (name) VALUES (?)", (name,))
            cur.execute("SELECT id FROM ingredients WHERE name = ?", (name,))
            ing_id = cur.fetchone()[0] # 재료 ID 가져오기
             # 레시피-재료 연결 테이블에 저장
            cur.execute("INSERT INTO recipe_ingredients (recipe_id, ingredient_id) VALUES (?, ?)", (recipe_id, ing_id))

            # 수량도 별도의 재료명으로 저장 (예: "1/2포기")
            if amount:
                cur.execute("INSERT OR IGNORE INTO ingredients (name) VALUES (?)", (amount,))
                cur.execute("SELECT id FROM ingredients WHERE name = ?", (amount,))
                # 수량과 레시피 연결
                amt_id = cur.fetchone()[0]
                cur.execute("INSERT INTO recipe_ingredients (recipe_id, ingredient_id) VALUES (?, ?)", (recipe_id, amt_id))
        else:
            # 재료명과 수량 분리 실패 시, 전체 문자열을 재료명으로 저장
            cur.execute("INSERT OR IGNORE INTO ingredients (name) VALUES (?)", (ingredient,))
            cur.execute("SELECT id FROM ingredients WHERE name = ?", (ingredient,))
            ing_id = cur.fetchone()[0]
            cur.execute("INSERT INTO recipe_ingredients (recipe_id, ingredient_id) VALUES (?, ?)", (recipe_id, ing_id))

    conn.commit() # DB에 변경사항 저장
    conn.close() # 연결 종료
    print(f"[{info['name']}] ✅ 저장 완료")

# 메뉴 파일에서 음식 목록 불러오기 (한 줄에 하나의 음식명, 빈 줄 제외)
def load_menu(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

# 직접 실행 시 크롤링 & 저장 진행
if __name__ == '__main__':
    init_db() # DB 초기화 (테이블 생성)
    food_list = load_menu('menu.txt') # 메뉴 파일에서 음식명 리스트 읽기
    failures = [] # 실패한 음식명을 저장할 리스트

    for food in food_list:
        try:
            info = food_info(food)  # 크롤링 시도
            if info:
                save_to_db(info) # 성공 시 DB 저장
            else:
                failures.append(food) # 실패 시 리스트에 추가
        except Exception as e:
            print(f"[{food}] 예외 발생: {e}")
            failures.append(food) # 예외 발생 시 실패 리스트에 추가
        time.sleep(1) # 서버 과부하 방지용 1초 지연

    # # 실패한 음식들을 failures.txt 파일에 저장
    if failures:
        with open('failures.txt', 'w', encoding='utf-8') as f:
            for item in failures:
                f.write(item + '\n')
        print("\n❌ 크롤링 실패한 음식들이 failures.txt에 저장되었습니다.")

