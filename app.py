from flask import Flask, request, render_template # Flask의 웹 기능, 요청 처리, HTML 렌더링 기능 불러오기
import sqlite3 # SQLite 데이터베이스를 사용하기 위한 모듈

app = Flask(__name__) # Flask 앱 생성
# ✅ 입력된 재료로 레시피를 검색하는 함수
def get_recipes(ingredients):
    conn = sqlite3.connect('recipes.db')  # 레시피 DB 연결
    cur = conn.cursor()
    # 입력된 재료 문자열(예: "달걀, 김치") → 리스트로 분리 및 공백 제거
    ingredient_list = [i.strip() for i in ingredients.split(',') if i.strip()] 
    if not ingredient_list: # 재료가 입력되지 않은 경우 빈 리스트 반환
        return []
    # SQL 쿼리에서 사용할 ? 플래이스홀더 생성 (예: ?,?,?)
    placeholders = ','.join(['?'] * len(ingredient_list))
    # ✅ 재료 이름이 일치하는 레시피를 검색하는 SQL 쿼리
    query = f"""
    SELECT DISTINCT r.name, r.recipe #중복 없이 레시피 이름과 조리법 가져오기
    FROM recipes r
    JOIN recipe_ingredients ri ON r.id = ri.recipe_id
    JOIN ingredients i ON i.id = ri.ingredient_id
    WHERE i.name IN ({placeholders}) #입력한 재료 중 하나 이상이 포함된 레시피만 조회
    """
    cur.execute(query, ingredient_list) # 실제 재료값을 쿼리에 바인딩하여 실행
    rows = cur.fetchall() # 결과를 모두 가져오기
    conn.close() # DB 연결 종료
    # 결과를 딕셔너리 형태로 변환 (템플릿에서 사용하기 쉽게)
    return [{"name": row[0], "recipe": row[1]} for row in rows]
# ✅ 메인 페이지: 재료 입력 폼과 결과 출력
@app.route("/", methods=["GET", "POST"])
def index():
    recipes = [] # 결과 레시피 초기화
    if request.method == "POST": # 폼 제출 시 (POST 요청)
        ingredients = request.form["ingredients"] # 폼에서 'ingredients' 필드 값 가져오기
        recipes = get_recipes(ingredients) # 입력 재료 기반으로 레시피 검색
    return render_template("index.html", recipes=recipes) # 결과를 index.html로 렌더링
# ✅ 개별 레시피 상세 보기 페이지
@app.route("/recipe/<name>")
def recipe_detail(name):
    conn = sqlite3.connect('recipes.db') # DB 연결
    cur = conn.cursor()
    cur.execute("SELECT name, recipe FROM recipes WHERE name = ?", (name,))
    row = cur.fetchone() # 해당 이름을 가진 레시피 하나 가져오기
    conn.close()
    if row: # 레시피가 존재할 경우: recipe.html 템플릿으로 전달
        return render_template("recipe.html", recipe={"name": row[0], "recipe": row[1]})
    else: # 레시피가 없을 경우 404 에러 메시지 반환
        return f"{name} 레시피를 찾을 수 없습니다.", 404

# ✅ 웹서버 실행 (이 부분은 파일이 직접 실행될 때만 동작)
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True) # 로컬 서버 실행, debug=True로 오류 추적 가능

