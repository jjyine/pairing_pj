from multiprocessing import Process
import argparse
import time
import traceback

from src.textSearch import save_text_search_to_db, save_text_search_force_to_db


def write_log(message, filename):
    with open(filename, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def make_log_message(worker_name, message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"{timestamp} [{worker_name}] {message}"


def log_info(worker_name, message, info_filename="main_info.txt", print_console=True):
    log_message = make_log_message(worker_name, message)
    if print_console:
        print(log_message)
    if info_filename:
        write_log(log_message, info_filename)


def log_error(worker_name, message, error_filename="main_error.txt", print_console=True):
    log_message = make_log_message(worker_name, f"[ERROR] {message}")
    if print_console:
        print(log_message)
    if error_filename:
        write_log(log_message, error_filename)


def run_worker(worker_name, start_id, end_id):
    info_filename = "main_info.txt"
    error_filename = "main_error.txt"

    try:
        log_info(worker_name, f"워커 시작 | start_id={start_id}, end_id={end_id}", info_filename)

        save_text_search_to_db(
            batch_size=1000,
            start_id=start_id,
            end_id=end_id,
            worker_name=worker_name
        )

        log_info(worker_name, "워커 정상 종료", info_filename)

    except Exception as e:
        log_error(worker_name, f"워커 실행 실패 | {repr(e)}", error_filename)
        log_error(worker_name, traceback.format_exc(), error_filename)


def main():
    info_filename = "main_info.txt"
    error_filename = "main_error.txt"

    with open(info_filename, "w", encoding="utf-8") as f:
        f.write("=== MAIN INFO LOG ===\n")

    with open(error_filename, "w", encoding="utf-8") as f:
        f.write("=== MAIN ERROR LOG ===\n")

    total_start_time = time.time()

    try:
        log_info("main", "text_search save main 시작 (worker_14_4 마지막 범위 4등분)", info_filename)

        workers = [
            ("worker_14_4_1", 2001685, 2003836),
            ("worker_14_4_2", 2003836, 2005987),
            ("worker_14_4_3", 2005987, 2008138),
            ("worker_14_4_4", 2008138, None),
        ]

        log_info("main", "=== WORKER RANGE ===", info_filename)
        for worker_name, start_id, end_id in workers:
            log_info(
                "main",
                f"{worker_name} | start_id={start_id}, end_id={end_id}",
                info_filename
            )

        processes = []

        for worker_name, start_id, end_id in workers:
            try:
                p = Process(target=run_worker, args=(worker_name, start_id, end_id))
                p.start()
                processes.append((worker_name, p))
                log_info(
                    "main",
                    f"프로세스 시작 완료 | {worker_name} | pid={p.pid}",
                    info_filename
                )

            except Exception as e:
                log_error(
                    "main",
                    f"프로세스 시작 실패 | {worker_name} | {repr(e)}",
                    error_filename
                )
                log_error("main", traceback.format_exc(), error_filename)

        for worker_name, p in processes:
            try:
                p.join()

                if p.exitcode == 0:
                    log_info(
                        "main",
                        f"프로세스 join 완료 | {worker_name} | exitcode={p.exitcode}",
                        info_filename
                    )
                else:
                    log_error(
                        "main",
                        f"프로세스 비정상 종료 | {worker_name} | exitcode={p.exitcode}",
                        error_filename
                    )

            except Exception as e:
                log_error(
                    "main",
                    f"프로세스 join 실패 | {worker_name} | {repr(e)}",
                    error_filename
                )
                log_error("main", traceback.format_exc(), error_filename)

        total_elapsed = time.time() - total_start_time
        log_info(
            "main",
            f"worker_14_4 마지막 범위 4등분 작업 종료 | total_time={total_elapsed:.2f}초",
            info_filename
        )

    except Exception as e:
        log_error("main", f"main 실패 | {repr(e)}", error_filename)
        log_error("main", traceback.format_exc(), error_filename)


def run_worker_force(worker_name, start_id, end_id):
    info_filename = "main_info.txt"
    error_filename = "main_error.txt"

    try:
        log_info(worker_name, f"워커 시작 (force) | start_id={start_id}, end_id={end_id}", info_filename)

        save_text_search_force_to_db(
            batch_size=1000,
            start_id=start_id,
            end_id=end_id,
            worker_name=worker_name
        )

        log_info(worker_name, "워커 정상 종료 (force)", info_filename)

    except Exception as e:
        log_error(worker_name, f"워커 실행 실패 | {repr(e)}", error_filename)
        log_error(worker_name, traceback.format_exc(), error_filename)


def main_force():
    info_filename = "main_info.txt"
    error_filename = "main_error.txt"

    with open(info_filename, "w", encoding="utf-8") as f:
        f.write("=== MAIN INFO LOG (FORCE) ===\n")

    with open(error_filename, "w", encoding="utf-8") as f:
        f.write("=== MAIN ERROR LOG (FORCE) ===\n")

    total_start_time = time.time()

    try:
        log_info("main", "text_search force update 시작 (중복 그룹 대상)", info_filename)

        workers = [
            ("force_worker_1", 0, None),
        ]

        processes = []

        for worker_name, start_id, end_id in workers:
            try:
                p = Process(target=run_worker_force, args=(worker_name, start_id, end_id))
                p.start()
                processes.append((worker_name, p))
                log_info(
                    "main",
                    f"프로세스 시작 완료 | {worker_name} | pid={p.pid}",
                    info_filename
                )

            except Exception as e:
                log_error(
                    "main",
                    f"프로세스 시작 실패 | {worker_name} | {repr(e)}",
                    error_filename
                )
                log_error("main", traceback.format_exc(), error_filename)

        for worker_name, p in processes:
            try:
                p.join()

                if p.exitcode == 0:
                    log_info(
                        "main",
                        f"프로세스 join 완료 | {worker_name} | exitcode={p.exitcode}",
                        info_filename
                    )
                else:
                    log_error(
                        "main",
                        f"프로세스 비정상 종료 | {worker_name} | exitcode={p.exitcode}",
                        error_filename
                    )

            except Exception as e:
                log_error(
                    "main",
                    f"프로세스 join 실패 | {worker_name} | {repr(e)}",
                    error_filename
                )
                log_error("main", traceback.format_exc(), error_filename)

        total_elapsed = time.time() - total_start_time
        log_info(
            "main",
            f"force update 작업 종료 | total_time={total_elapsed:.2f}초",
            info_filename
        )

    except Exception as e:
        log_error("main", f"main_force 실패 | {repr(e)}", error_filename)
        log_error("main", traceback.format_exc(), error_filename)


def main_force_test():
    """dry_run=True, test_limit=1 로 1건만 조회해 로그에 출력하고 DB는 건드리지 않음"""
    info_filename = "main_info.txt"
    error_filename = "main_error.txt"

    with open(info_filename, "w", encoding="utf-8") as f:
        f.write("=== MAIN INFO LOG (FORCE DRY RUN TEST) ===\n")

    with open(error_filename, "w", encoding="utf-8") as f:
        f.write("=== MAIN ERROR LOG (FORCE DRY RUN TEST) ===\n")

    log_info("main", "=== DRY RUN TEST 시작 (1건만 조회, DB 업데이트 없음) ===", info_filename)

    save_text_search_force_to_db(
        batch_size=1,
        start_id=0,
        end_id=None,
        worker_name="force_dry_run",
        dry_run=True,
        test_limit=1
    )

    log_info("main", "=== DRY RUN TEST 완료 ===", info_filename)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="text_search force update")
    parser.add_argument(
        "--mode",
        choices=["test", "run"],
        required=True,
        help="test: dry-run (DB 저장 안 함) | run: 실제 업데이트"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="처리할 row 수 제한. test 모드에서 생략하면 1건, run 모드에서 생략하면 제한 없음(전체 처리)"
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=None,
        help="처리할 최소 중복 그룹 크기 (예: 3이면 그룹 크기 >= 3인 그룹만 처리)"
    )
    parser.add_argument(
        "--max-count",
        type=int,
        default=None,
        help="처리할 최대 중복 그룹 크기 (예: 2이면 그룹 크기 <= 2인 그룹만 처리)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="중복 그룹 여부와 상관없이 전체 row를 업데이트 (min-count/max-count 무시)"
    )
    args = parser.parse_args()

    if args.mode == "test":
        save_text_search_force_to_db(
            batch_size=1000,
            start_id=0,
            end_id=None,
            worker_name="force_dry_run",
            dry_run=True,
            test_limit=args.limit if args.limit is not None else 1,
            min_count=args.min_count,
            max_count=args.max_count,
            all_rows=args.all
        )
    else:
        save_text_search_force_to_db(
            batch_size=1000,
            start_id=0,
            end_id=None,
            worker_name="force_run",
            dry_run=False,
            test_limit=args.limit,
            min_count=args.min_count,
            max_count=args.max_count,
            all_rows=args.all
        )