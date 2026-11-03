-- Boards and cards owned by a single user; every policy is scoped to auth.uid().

create table public.boards (
  id          uuid primary key default gen_random_uuid(),
  owner_id    uuid not null default auth.uid() references auth.users on delete cascade,
  title       text not null check (char_length(title) between 1 and 200),
  created_at  timestamptz not null default now()
);

create index boards_owner_created_idx on public.boards (owner_id, created_at desc);

create table public.cards (
  id              uuid primary key default gen_random_uuid(),
  board_id        uuid not null references public.boards on delete cascade,
  -- Denormalized so (owner_id, image_sha256) can be unique within this table.
  owner_id        uuid not null default auth.uid() references auth.users on delete cascade,
  position        integer not null check (position >= 0),
  image_path      text not null,
  thumb_path      text not null,
  image_sha256    text not null check (image_sha256 ~ '^[0-9a-f]{64}$'),
  title           text not null,
  chart_type      text not null,
  period          text,
  takeaways       jsonb not null default '[]'::jsonb check (jsonb_typeof(takeaways) = 'array'),
  interpretation  text not null,
  caveats         jsonb not null default '[]'::jsonb check (jsonb_typeof(caveats) = 'array'),
  user_note       text,
  model           text not null,
  raw_response    jsonb,
  created_at      timestamptz not null default now(),
  unique (owner_id, image_sha256)
);

create index cards_board_position_idx on public.cards (board_id, position);

alter table public.boards enable row level security;
alter table public.cards enable row level security;

create policy "boards: owner can read" on public.boards
  for select to authenticated using (owner_id = (select auth.uid()));
create policy "boards: owner can insert" on public.boards
  for insert to authenticated with check (owner_id = (select auth.uid()));
create policy "boards: owner can update" on public.boards
  for update to authenticated
  using (owner_id = (select auth.uid()))
  with check (owner_id = (select auth.uid()));
create policy "boards: owner can delete" on public.boards
  for delete to authenticated using (owner_id = (select auth.uid()));

create policy "cards: owner can read" on public.cards
  for select to authenticated using (owner_id = (select auth.uid()));
create policy "cards: owner can insert into own board" on public.cards
  for insert to authenticated with check (
    owner_id = (select auth.uid())
    and exists (
      select 1 from public.boards b
      where b.id = board_id and b.owner_id = (select auth.uid())
    )
  );
create policy "cards: owner can update within own boards" on public.cards
  for update to authenticated
  using (owner_id = (select auth.uid()))
  with check (
    owner_id = (select auth.uid())
    and exists (
      select 1 from public.boards b
      where b.id = board_id and b.owner_id = (select auth.uid())
    )
  );
create policy "cards: owner can delete" on public.cards
  for delete to authenticated using (owner_id = (select auth.uid()));

-- Runs with the caller's privileges, so RLS still limits it to the caller's cards.
create function public.reorder_cards(p_board_id uuid, p_card_ids uuid[])
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
  expected integer;
begin
  select count(*) into expected from public.cards where board_id = p_board_id;

  if coalesce(array_length(p_card_ids, 1), 0) <> expected
     or (select count(distinct id) from unnest(p_card_ids) as t(id)) <> expected
     or exists (
       select 1 from unnest(p_card_ids) as t(id)
       where not exists (
         select 1 from public.cards c where c.id = t.id and c.board_id = p_board_id
       )
     ) then
    raise exception 'card_ids must list every card of the board exactly once'
      using errcode = '22023';
  end if;

  update public.cards c
  set position = o.ord - 1
  from unnest(p_card_ids) with ordinality as o(id, ord)
  where c.id = o.id and c.board_id = p_board_id;
end;
$$;

revoke execute on function public.reorder_cards(uuid, uuid[]) from public, anon;
grant execute on function public.reorder_cards(uuid, uuid[]) to authenticated;

-- Private bucket; objects live under "<auth.uid()>/...".
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('charts', 'charts', false, 10485760, array['image/webp'])
on conflict (id) do nothing;

create policy "charts: owner can read" on storage.objects
  for select to authenticated using (
    bucket_id = 'charts' and (storage.foldername(name))[1] = (select auth.uid()::text)
  );
create policy "charts: owner can upload" on storage.objects
  for insert to authenticated with check (
    bucket_id = 'charts' and (storage.foldername(name))[1] = (select auth.uid()::text)
  );
create policy "charts: owner can update" on storage.objects
  for update to authenticated
  using (bucket_id = 'charts' and (storage.foldername(name))[1] = (select auth.uid()::text))
  with check (bucket_id = 'charts' and (storage.foldername(name))[1] = (select auth.uid()::text));
create policy "charts: owner can delete" on storage.objects
  for delete to authenticated using (
    bucket_id = 'charts' and (storage.foldername(name))[1] = (select auth.uid()::text)
  );
