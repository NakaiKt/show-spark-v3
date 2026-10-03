async def get_by_sub(conn, sub: str):
    """
    subからユーザー情報を取得する
    """
    SELECT = """
    select id, sub, email, name, picture, created_at, updated_at, last_login_at
    from app_user
    where sub = $1
    """
    return await conn.fetchrow(SELECT, sub)


async def upsert(conn, sub: str, email: str, name: str | None, picture: str | None):
    """
    ユーザー情報をupsertする
    subが存在しない場合は新規作成、存在する場合は更新する

    新規作成対象
    - sub
    - email
    - name
    - picture

    更新対象
    - email
    - last_login_at
    """
    UPSERT = """
    insert into app_user (sub, email, name, picture, last_login_at)
    values ($1, $2, $3, $4, now())
    on conflict (sub) do update
    set email         = excluded.email,
        last_login_at = now()
    returning id, sub, email, name, picture, created_at, updated_at, last_login_at
    """
    return await conn.fetchrow(UPSERT, sub, email, name, picture)
