async def store_file(work_id: int, file_id: str, file_name: str):
    from database.queries import add_file_to_db
    await add_file_to_db(work_id, file_id, file_name)
