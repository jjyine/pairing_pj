import os
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
        autocommit=False,
        connect_timeout=10,
        read_timeout=120,
        write_timeout=30
    )


# -----------------------------
# 빈값 체크
# None, "", 공백만 있는 문자열이면 True
# -----------------------------
def is_blank(text):
    return text is None or str(text).strip() == ""


# -----------------------------
# 로그 파일 저장
# -----------------------------
def write_log(message, filename):
    with open(filename, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def make_log_message(worker_name, message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"{timestamp} [{worker_name}] {message}"


def log_info(worker_name, message, info_filename=None, print_console=True):
    log_message = make_log_message(worker_name, message)

    if print_console:
        print(log_message)

    if info_filename:
        write_log(log_message, info_filename)


def log_error(worker_name, message, error_filename=None, print_console=True):
    log_message = make_log_message(worker_name, f"[ERROR] {message}")

    if print_console:
        print(log_message)

    if error_filename:
        write_log(log_message, error_filename)


# -----------------------------
# 공백 정리
# -----------------------------
def normalize_text(text):
    return " ".join(str(text).strip().split())


# -----------------------------
# text_search 값 생성
# -----------------------------
def build_text_search(ws_name, winery_name, name):
    if not is_blank(ws_name):
        return normalize_text(ws_name)

    winery = normalize_text(winery_name)
    name = normalize_text(name)

    if is_blank(winery) and is_blank(name):
        return None

    if is_blank(winery):
        return name

    if is_blank(name):
        return winery

    if winery.lower() in name.lower():
        return name

    return f"{winery} {name}"


# -----------------------------
# text_search 저장
# text_search IS NULL 인 row만 조회하고
# text_search 컬럼만 업데이트
# -----------------------------
def save_text_search_to_db(
    batch_size=1000,
    start_id=0,
    end_id=None,
    worker_name="worker"
):
    conn = None
    read_cursor = None
    write_cursor = None

    info_filename = f"info_text_search_{worker_name}.txt"
    error_filename = f"error_text_search_{worker_name}.txt"

    try:
        # 로그 파일 초기화
        with open(info_filename, "w", encoding="utf-8") as f:
            f.write(f"=== INFO LOG | {worker_name} ===\n")

        with open(error_filename, "w", encoding="utf-8") as f:
            f.write(f"=== ERROR LOG | {worker_name} ===\n")

        conn = get_connection()
        read_cursor = conn.cursor()
        write_cursor = conn.cursor()

        log_info(worker_name, "=== TEXT_SEARCH SAVE START ===", info_filename)
        log_info(
            worker_name,
            f"batch_size={batch_size}, start_id={start_id}, end_id={end_id}",
            info_filename
        )

        last_id = start_id
        total_count = 0
        updated_count = 0
        failed_count = 0
        batch_no = 0
        total_start_time = time.time()

        while True:
            batch_no += 1
            batch_start_time = time.time()

            # -----------------------------
            # SELECT
            # text_search IS NULL 인 row만 조회
            # -----------------------------
            select_start = time.time()

            if end_id is None:
                select_sql = """
                    SELECT id, ws_name, winery_name, name
                    FROM wine
                    WHERE id > %s
                      AND text_search IS NULL
                    ORDER BY id
                    LIMIT %s
                """
                read_cursor.execute(select_sql, (last_id, batch_size))
            else:
                select_sql = """
                    SELECT id, ws_name, winery_name, name
                    FROM wine
                    WHERE id > %s
                      AND id <= %s
                      AND text_search IS NULL
                    ORDER BY id
                    LIMIT %s
                """
                read_cursor.execute(select_sql, (last_id, end_id, batch_size))

            rows = read_cursor.fetchall()
            select_elapsed = time.time() - select_start

            if not rows:
                log_info(worker_name, "조회할 남은 row가 없습니다. 작업 종료.", info_filename)
                break

            log_info(
                worker_name,
                f"[SELECT DONE] batch_no={batch_no}, rows={len(rows)}, time={select_elapsed:.2f}초, start_last_id={last_id}",
                info_filename
            )

            update_data = []

            # -----------------------------
            # Python 처리
            # -----------------------------
            build_start = time.time()

            for wine_id, ws_name, winery_name, name in rows:
                total_count += 1
                last_id = wine_id

                try:
                    text_search_value = build_text_search(ws_name, winery_name, name)
                    update_data.append((text_search_value, wine_id))

                except Exception as e:
                    failed_count += 1
                    log_error(
                        worker_name,
                        (
                            f"ID={wine_id} 처리 실패\n"
                            f"ws_name={ws_name}\n"
                            f"winery_name={winery_name}\n"
                            f"name={name}\n"
                            f"error={repr(e)}"
                        ),
                        error_filename
                    )

            build_elapsed = time.time() - build_start

            # -----------------------------
            # UPDATE
            # text_search 컬럼만 업데이트
            # -----------------------------
            update_start = time.time()

            if update_data:
                update_sql = """
                    UPDATE wine
                    SET text_search = %s
                    WHERE id = %s
                """
                write_cursor.executemany(update_sql, update_data)
                conn.commit()
                affected_rows = len(update_data)
                updated_count += affected_rows
            else:
                affected_rows = 0

            update_elapsed = time.time() - update_start

            batch_elapsed = time.time() - batch_start_time
            total_elapsed = time.time() - total_start_time

            log_info(
                worker_name,
                (
                    f"[BATCH END] batch_no={batch_no}, "
                    f"batch_rows={len(rows)}, "
                    f"updated={affected_rows}, "
                    f"last_id={last_id}, "
                    f"누적 조회={total_count}, "
                    f"누적 저장={updated_count}, "
                    f"실패={failed_count}, "
                    f"select_time={select_elapsed:.2f}초, "
                    f"build_time={build_elapsed:.2f}초, "
                    f"update_time={update_elapsed:.2f}초, "
                    f"batch_time={batch_elapsed:.2f}초, "
                    f"total_time={total_elapsed:.2f}초"
                ),
                info_filename
            )

        total_elapsed = time.time() - total_start_time
        log_info(worker_name, f"=== SAVE COMPLETE | total_updated={updated_count} ===", info_filename)
        log_info(worker_name, f"총 조회 row 수: {total_count}", info_filename)
        log_info(worker_name, f"실패 row 수: {failed_count}", info_filename)
        log_info(worker_name, f"총 소요 시간: {total_elapsed:.2f}초", info_filename)

    except Exception as e:
        if conn:
            conn.rollback()
        log_error(worker_name, f"save_text_search_to_db 실패 | {repr(e)}", error_filename)

    finally:
        if read_cursor:
            read_cursor.close()
        if write_cursor:
            write_cursor.close()
        if conn:
            conn.close()


# -----------------------------
# winery_name + name 강제 조합
# ws_name 우선 로직 없이 항상 winery+name 조합 반환
# -----------------------------
def build_text_search_force(winery_name, name):
    winery = normalize_text(winery_name)
    name = normalize_text(name)

    if is_blank(winery) and is_blank(name):
        return None

    if is_blank(winery):
        return name

    if is_blank(name):
        return winery

    if winery.lower() in name.lower():
        return name

    return f"{winery} {name}"


# -----------------------------
# 중복 (winery_name, ws_name, ws_url) 그룹 키 + 그룹 크기를 한 번만 조회
# 매 배치마다 무거운 GROUP BY를 반복하지 않기 위해 결과를 메모리에 캐싱
# -----------------------------
def get_duplicate_groups(cursor):
    # ===== [조회 조건 수정 지점 1] 어떤 컬럼이 같으면 "중복 그룹"으로 볼지 =====
    cursor.execute("""
        SELECT winery_name, ws_name, ws_url, COUNT(*) AS cnt
        FROM wine
        WHERE winery_name IS NOT NULL
          AND ws_name IS NOT NULL
          AND ws_url IS NOT NULL
        GROUP BY winery_name, ws_name, ws_url
        HAVING COUNT(*) > 1
    """)
    # ===== 조회 조건 수정 지점 1 끝 =====
    return {(winery_name, ws_name, ws_url): cnt for winery_name, ws_name, ws_url, cnt in cursor.fetchall()}


# -----------------------------
# ws_name 단독 기준으로 wine 테이블 전체에서 중복되는 ws_name 집합 조회
# (winery_name, ws_url과 무관하게 같은 ws_name이 2건 이상이면 중복)
# -----------------------------
def get_duplicate_ws_names(cursor):
    cursor.execute("""
        SELECT ws_name
        FROM wine
        WHERE ws_name IS NOT NULL
          AND ws_name != ''
        GROUP BY ws_name
        HAVING COUNT(*) > 1
    """)
    return {row[0] for row in cursor.fetchall()}


# -----------------------------
# text_search 값 생성 (전체 업데이트용)
# ws_name이 있고 단독 중복이 아니면 ws_name 사용
# ws_name이 없거나 단독 중복이면 winery_name + name 조합 사용
# -----------------------------
def build_text_search_unique(ws_name, winery_name, name, duplicate_ws_names):
    if not is_blank(ws_name) and ws_name not in duplicate_ws_names:
        return normalize_text(ws_name)

    return build_text_search_force(winery_name, name)


# -----------------------------
# text_search를 winery_name + name 조합으로 강제 업데이트
# deleted_at 여부와 상관없이 업데이트 대상
# all_rows=True면 중복 그룹 여부와 상관없이 전체 row를 업데이트
# all_rows=False(기본)면 중복 (winery_name, ws_name, ws_url) 그룹에 속한 row만 업데이트
# -----------------------------
def save_text_search_force_to_db(
    batch_size=1000,
    start_id=0,
    end_id=None,
    worker_name="worker",
    dry_run=False,
    test_limit=None,
    min_count=None,
    max_count=None,
    all_rows=False
):
    conn = None
    read_cursor = None
    write_cursor = None

    info_filename = f"info_text_search_{worker_name}.txt"
    error_filename = f"error_text_search_{worker_name}.txt"

    try:
        with open(info_filename, "w", encoding="utf-8") as f:
            f.write(f"=== INFO LOG | {worker_name} ===\n")

        with open(error_filename, "w", encoding="utf-8") as f:
            f.write(f"=== ERROR LOG | {worker_name} ===\n")

        conn = get_connection()
        read_cursor = conn.cursor()
        write_cursor = conn.cursor()

        mode_label = "[DRY RUN] " if dry_run else ""
        log_info(worker_name, f"=== {mode_label}TEXT_SEARCH FORCE UPDATE START ===", info_filename)
        log_info(
            worker_name,
            f"batch_size={batch_size}, start_id={start_id}, end_id={end_id}, dry_run={dry_run}, "
            f"test_limit={test_limit}, min_count={min_count}, max_count={max_count}, all_rows={all_rows}",
            info_filename
        )

        duplicate_groups = {}
        duplicate_ws_names = set()
        if all_rows:
            # ws_name 단독 중복 조회는 한 번만 수행해 메모리에 캐싱
            group_start = time.time()
            duplicate_ws_names = get_duplicate_ws_names(read_cursor)
            log_info(
                worker_name,
                f"[WS_NAME GROUP BY DONE] 중복 ws_name 수={len(duplicate_ws_names)}, time={time.time() - group_start:.2f}초",
                info_filename
            )
        else:
            # 중복 그룹 조회는 한 번만 수행 (이전에는 배치마다 반복 실행되어 타임아웃 발생)
            group_start = time.time()
            duplicate_groups = get_duplicate_groups(read_cursor)
            log_info(
                worker_name,
                f"[GROUP BY DONE] 중복 그룹 수={len(duplicate_groups)}, time={time.time() - group_start:.2f}초",
                info_filename
            )

        last_id = start_id
        total_scanned = 0
        matched_count = 0
        updated_count = 0
        failed_count = 0
        batch_no = 0
        total_start_time = time.time()
        reached_test_limit = False

        while not reached_test_limit:
            batch_no += 1
            batch_start_time = time.time()

            select_start = time.time()

            # ===== [조회 조건 수정 지점 2] 배치로 훑을 wine row의 범위/컬럼 =====
            if end_id is None:
                select_sql = """
                    SELECT id, winery_name, ws_name, ws_url, name, deleted_at, text_search
                    FROM wine
                    WHERE id > %s
                    ORDER BY id
                    LIMIT %s
                """
                read_cursor.execute(select_sql, (last_id, batch_size))
            else:
                select_sql = """
                    SELECT id, winery_name, ws_name, ws_url, name, deleted_at, text_search
                    FROM wine
                    WHERE id > %s
                      AND id <= %s
                    ORDER BY id
                    LIMIT %s
                """
                read_cursor.execute(select_sql, (last_id, end_id, batch_size))
            # ===== 조회 조건 수정 지점 2 끝 =====

            rows = read_cursor.fetchall()
            select_elapsed = time.time() - select_start

            if not rows:
                log_info(worker_name, "조회할 남은 row가 없습니다. 작업 종료.", info_filename)
                break

            update_data = []

            build_start = time.time()

            for wine_id, winery_name, ws_name, ws_url, name, _deleted_at, text_search_before in rows:
                total_scanned += 1
                last_id = wine_id

                # ===== [조회 조건 수정 지점 3] SQL이 아닌 Python 레벨 필터 =====
                if not all_rows:
                    cnt = duplicate_groups.get((winery_name, ws_name, ws_url))
                    if cnt is None:
                        continue
                    if min_count is not None and cnt < min_count:
                        continue
                    if max_count is not None and cnt > max_count:
                        continue
                # ===== 조회 조건 수정 지점 3 끝 =====

                try:
                    if all_rows:
                        text_search_after = build_text_search_unique(ws_name, winery_name, name, duplicate_ws_names)
                        if is_blank(ws_name):
                            source = "winery+name(ws_name_blank)"
                        elif ws_name in duplicate_ws_names:
                            source = "winery+name(ws_name_dup)"
                        else:
                            source = "ws_name"
                    else:
                        text_search_after = build_text_search_force(winery_name, name)
                        source = "winery+name(force)"
                    update_data.append((text_search_after, wine_id, text_search_before))
                    matched_count += 1

                    if dry_run:
                        log_info(
                            worker_name,
                            f"[DRY RUN] id={wine_id} | source={source} | before={text_search_before!r} | after={text_search_after!r}",
                            info_filename
                        )

                except Exception as e:
                    failed_count += 1
                    log_error(
                        worker_name,
                        f"ID={wine_id} 처리 실패 | winery_name={winery_name} | name={name} | error={repr(e)}",
                        error_filename
                    )

                if test_limit is not None and matched_count >= test_limit:
                    reached_test_limit = True
                    break

            build_elapsed = time.time() - build_start

            update_start = time.time()

            if update_data and not dry_run:
                write_cursor.executemany(
                    "UPDATE wine SET text_search = %s WHERE id = %s",
                    [(ts, wid) for ts, wid, _ in update_data]
                )
                conn.commit()

            updated_count += len(update_data)
            update_elapsed = time.time() - update_start

            batch_elapsed = time.time() - batch_start_time
            total_elapsed = time.time() - total_start_time

            log_info(
                worker_name,
                (
                    f"[BATCH END] batch_no={batch_no}, "
                    f"batch_rows={len(rows)}, "
                    f"matched={len(update_data)}, "
                    f"last_id={last_id}, "
                    f"누적 조회={total_scanned}, "
                    f"누적 업데이트={updated_count}, "
                    f"실패={failed_count}, "
                    f"select_time={select_elapsed:.2f}초, "
                    f"build_time={build_elapsed:.2f}초, "
                    f"update_time={update_elapsed:.2f}초, "
                    f"batch_time={batch_elapsed:.2f}초, "
                    f"total_time={total_elapsed:.2f}초"
                ),
                info_filename
            )

        if reached_test_limit:
            log_info(worker_name, f"test_limit={test_limit} 도달. 작업 종료.", info_filename)

        total_elapsed = time.time() - total_start_time
        log_info(worker_name, f"=== FORCE UPDATE COMPLETE | total_updated={updated_count} ===", info_filename)
        log_info(worker_name, f"총 조회 row 수: {total_scanned}", info_filename)
        log_info(worker_name, f"실패 row 수: {failed_count}", info_filename)
        log_info(worker_name, f"총 소요 시간: {total_elapsed:.2f}초", info_filename)

    except Exception as e:
        if conn:
            conn.rollback()
        log_error(worker_name, f"save_text_search_force_to_db 실패 | {repr(e)}", error_filename)

    finally:
        if read_cursor:
            read_cursor.close()
        if write_cursor:
            write_cursor.close()
        if conn:
            conn.close()