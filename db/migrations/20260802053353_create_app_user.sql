-- migrate:up
create table app_user (
  id uuid primary key default gen_random_uuid(),
  sub text not null unique,
  email text not null unique,
  name text,
  picture text,
  last_login_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()  
);

-- 全テーブル共通。update 時に updated_at を現在時刻にする
create function set_updated_at() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

create trigger app_user_set_updated_at
  before update on app_user
  for each row
  execute function set_updated_at();

-- migrate:down
drop trigger app_user_set_updated_at on app_user;
drop function set_updated_at();
drop table app_user;