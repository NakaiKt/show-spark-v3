UPSERT = """
insert into app_user (sub, email, name, picture, last_login_at)
values ($1, $2, $3, $4, now())
on conflict (sub) do update
   set email         = excluded.email,
       last_login_at = now()
returning id, sub, email, name, picture, created_at, updated_at, last_login_at
"""


async def upsert(conn, sub: str, email: str, name: str | None, picture: str | None):
    return await conn.fetchrow(UPSERT, sub, email, name, picture)