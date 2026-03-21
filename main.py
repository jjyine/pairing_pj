from src.parser import save_paring_to_db

def main():
    save_paring_to_db(
        batch_size=1000,
        print_limit=10,
        start_id=0
    )

if __name__ == "__main__":
    main()