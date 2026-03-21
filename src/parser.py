import os
import json
import time
import pymysql
from dotenv import load_dotenv

load_dotenv()


# -----------------------------
# DB 연결
# -----------------------------
def get_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        charset="utf8mb4",
        autocommit=False
    )


# -----------------------------
# 빈값 체크
# None, "", 공백만 있는 문자열이면 True
# -----------------------------
def is_blank(text):
    return text is None or str(text).strip() == ""


# -----------------------------
# debug 로그 파일 저장
# -----------------------------
def write_debug_log(message, filename="debug.txt"):
    with open(filename, "a", encoding="utf-8") as f:
        f.write(message + "\n")


# -----------------------------
# 공백 정리
# -----------------------------
def normalize_token(text):
    return " ".join(str(text).strip().split())


# -----------------------------
# vv_parings 분리
# 괄호 밖 콤마만 split
# -----------------------------
def split_vv_parings(text):
    if is_blank(text):
        return []

    result = []
    current = []
    depth = 0

    for char in text:
        if char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth = max(0, depth - 1)
            current.append(char)
        elif char == "," and depth == 0:
            token = "".join(current).strip()
            if token:
                result.append(token)
            current = []
        else:
            current.append(char)

    token = "".join(current).strip()
    if token:
        result.append(token)

    return result


# -----------------------------
# vv / ws -> ws 기준 표현 매핑
# 값이 아래 키와 같으면 ws 표준 표현으로 치환
# -----------------------------
WS_CANONICAL_MAP = {
    "Poultry": "Chicken and Turkey",

    "Beef": "Beef and Venison, Veal",
    "Veal": "Beef and Venison, Veal",
    "Beef and Venison": "Beef and Venison, Veal",
    "Game (deer, venison)": "Beef and Venison, Veal",
    "Cured Meat": "Cured meat",

    "Pasta": "Tomato-based Dishes",
    "Spicy food": "Chilis and Hot Spicy Foods",

    "Lean fish": "White Fish",
    "Rich fish (salmon, tuna etc)": "Meaty and Oily Fish",
    "Shellfish": "Shellfish, Crab and Lobster",

    "Goat's Milk Cheese": "Goats' Cheese and Feta",
    "Goat cheese": "Goats' Cheese and Feta",
    "Mature and hard cheese": "Manchego and Parmesan",
    "Cheddar": "Cheddar and Gruyere",
    "Gruyere": "Cheddar and Gruyere",
    "Blue cheese": "Blue Cheeses",
    "Mild and soft cheese": "Brie and Camembert",

    "Fruity desserts": "Fruit-based Desserts",
}


# -----------------------------
# 저장 제외 값
# 아래 값은 아예 결과에 넣지 않음
# -----------------------------
EXCLUDE_VALUES = {
    "appetizers and snacks",
    "aperitif",
}


# -----------------------------
# 값을 ws 표준 표현으로 변환
# 매핑 없으면 원래 값 유지
# -----------------------------
def convert_to_ws_expression(item):
    normalized = normalize_token(item)
    lower_normalized = normalized.lower()

    for source, target in WS_CANONICAL_MAP.items():
        if lower_normalized == normalize_token(source).lower():
            return target

    return normalized


# -----------------------------
# 병합 + 중복 제거
# 반환값: list
# -----------------------------
def merge_parings(vv_parings, ws_paring):
    result = []
    seen = set()

    vv_list = split_vv_parings(vv_parings)
    for item in vv_list:
        converted = convert_to_ws_expression(item)
        normalized_item = normalize_token(converted)
        key = normalized_item.lower()

        if key in EXCLUDE_VALUES:
            continue

        if normalized_item and key not in seen:
            seen.add(key)
            result.append(normalized_item)

    if not is_blank(ws_paring):
        converted_ws = convert_to_ws_expression(ws_paring)
        normalized_ws = normalize_token(converted_ws)
        key = normalized_ws.lower()

        if key not in EXCLUDE_VALUES and normalized_ws and key not in seen:
            seen.add(key)
            result.append(normalized_ws)

    return result


# -----------------------------
# 배치용 update 데이터 생성
# 빈 리스트면 NULL 저장
# -----------------------------
def build_update_value(merged_list):
    return None if not merged_list else json.dumps(merged_list, ensure_ascii=False)


# -----------------------------
# executemany로 batch update
# update_data 형식: [(pairing_value, wine_id), ...]
# -----------------------------
def update_pairing_bulk(cursor, update_data):
    sql = """
        UPDATE wine
        SET pairing = %s
        WHERE id = %s
    """
    cursor.executemany(sql, update_data)


# -----------------------------
# 배치 처리 + DB 저장
# 전체 처리: 더 이상 조회할 row가 없을 때 종료
# executemany 적용
# -----------------------------
def save_paring_to_db(batch_size=1000, print_limit=3, start_id=0):
    conn = None
    read_cursor = None
    write_cursor = None

    try:
        with open("debug.txt", "w", encoding="utf-8") as f:
            f.write("=== FAILED ROW DEBUG LOG ===\n")

        conn = get_connection()
        read_cursor = conn.cursor()
        write_cursor = conn.cursor()

        print("=== PAIRING SAVE START ===")
        print(f"batch_size={batch_size}, start_id={start_id}")

        last_id = start_id
        total_count = 0
        printed_count = 0
        failed_count = 0
        updated_count = 0
        batch_no = 0
        total_start_time = time.time()

        while True:
            batch_no += 1
            batch_start_time = time.time()

            select_sql = """
                SELECT id, vv_parings, ws_paring
                FROM wine
                WHERE id > %s
                AND pairing IS NULL
                ORDER BY id
                LIMIT %s
            """
            read_cursor.execute(select_sql, (last_id, batch_size))
            rows = read_cursor.fetchall()

            if not rows:
                print("\n조회할 남은 row가 없습니다. 작업 종료.")
                break

            print(f"\n--- BATCH {batch_no} START ---")
            print(f"조회 row 수={len(rows)}, 시작 last_id={last_id}")

            update_data = []
            batch_success_count = 0
            batch_failed_count = 0

            for wine_id, vv_parings, ws_paring in rows:
                total_count += 1
                last_id = wine_id

                try:
                    merged_list = merge_parings(vv_parings, ws_paring)
                    pairing_value = build_update_value(merged_list)
                    update_data.append((pairing_value, wine_id))
                    batch_success_count += 1

                    if printed_count < print_limit:
                        print(f"\n[ID: {wine_id}]")
                        print(f"vv_parings={vv_parings}")
                        print(f"ws_paring={ws_paring}")
                        print(f"merged_list={merged_list}")
                        print(f"pairing_save_value={pairing_value}")
                        printed_count += 1

                except Exception as row_error:
                    failed_count += 1
                    batch_failed_count += 1
                    error_message = (
                        f"[FAILED] ID={wine_id}\n"
                        f"vv_parings={vv_parings}\n"
                        f"ws_paring={ws_paring}\n"
                        f"error={repr(row_error)}\n"
                        f"{'-' * 80}"
                    )
                    write_debug_log(error_message)

            print(
                f"BATCH {batch_no} 준비 완료 | "
                f"업데이트 대상={len(update_data)} | "
                f"배치 실패={batch_failed_count}"
            )

            if update_data:
                update_pairing_bulk(write_cursor, update_data)
                conn.commit()
                updated_count += len(update_data)

            batch_elapsed = time.time() - batch_start_time
            total_elapsed = time.time() - total_start_time

            print(
                f"[BATCH COMMIT] batch_no={batch_no}, "
                f"batch_rows={len(rows)}, "
                f"batch_saved={len(update_data)}, "
                f"batch_failed={batch_failed_count}, "
                f"last_id={last_id}, "
                f"누적 조회={total_count}, "
                f"누적 저장={updated_count}, "
                f"누적 실패={failed_count}, "
                f"batch_time={batch_elapsed:.2f}초, "
                f"total_time={total_elapsed:.2f}초"
            )

        total_elapsed = time.time() - total_start_time

        print("\n=== END ===")
        print(f"총 조회 row 수: {total_count}")
        print(f"저장 row 수: {updated_count}")
        print(f"콘솔 출력 row 수: {printed_count}")
        print(f"실패 row 수: {failed_count}")
        print(f"총 소요 시간: {total_elapsed:.2f}초")

        if failed_count > 0:
            print("실패한 row는 debug.txt에 저장되었습니다.")

    except Exception as e:
        if conn:
            conn.rollback()
        print("❌ save_paring_to_db 실패")
        print(repr(e))
        write_debug_log(f"[FATAL ERROR] {repr(e)}")

    finally:
        if read_cursor:
            read_cursor.close()
        if write_cursor:
            write_cursor.close()
        if conn:
            conn.close()