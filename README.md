## 설치

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 환경 변수

루트에 `.env` 파일을 만들고 DB 접속 정보를 채워주세요 (이 파일은 git에 커밋되지 않습니다, `.gitignore` 참고).

```
DB_HOST=...
DB_USER=...
DB_PASSWORD=...
DB_NAME=...
```

## 실행

진입점은 `main.py`이며, `--mode`로 dry-run/실제 실행을 구분합니다.

```bash
# dry-run (DB 저장 안 함, 로그만 출력)
python main.py --mode test --all --limit 10

# 실제 업데이트 (DB commit)
python main.py --mode run --all
```

### CLI 옵션

| 옵션 | 설명 |
|---|---|
| `--mode` | `test`(dry-run) 또는 `run`(실제 업데이트). 필수. |
| `--limit` | 처리할 row 수 제한. `test` 모드에서 생략 시 1건, `run` 모드에서 생략 시 전체. |
| `--all` | 중복 그룹 여부와 상관없이 전체 row를 대상으로 업데이트. 

### text_search 값 생성 규칙 (`--all` 모드)

1. `ws_name`이 있고, 테이블 전체에서 그 `ws_name`이 유일하면 → `ws_name` 사용
2. `ws_name`이 없거나, 다른 row와 중복되면 → `winery_name + name` 조합 사용 (winery가 name에 이미 포함되어 있으면 `name`만 사용)

`deleted_at` 값과는 무관하게 모든 row가 업데이트 대상입니다.

dry-run 로그(`info_text_search_force_dry_run.txt`)에는 각 row가 어떤 경로로 값이 만들어졌는지 `source` 필드로 표시됩니다 (`ws_name` / `winery+name(ws_name_dup)` / `winery+name(ws_name_blank)`).

## 로그

실행할 때마다 `info_text_search_<worker_name>.txt`, `error_text_search_<worker_name>.txt` 파일이 루트에 생성됩니다 (`.gitignore`에 의해 git에는 포함되지 않습니다).

## 디렉터리 구조

- `main.py` — CLI 진입점 (`text_search` force update)
- `src/textSearch.py` — `text_search` 값 생성/저장 로직
