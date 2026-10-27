-- Supabase Storage photos 버킷 → 화면에서 그림 올리기·목록 보기 허용
-- Supabase 대시보드 > SQL Editor 에 통째로 붙여넣고 Run 을 누른다.
-- 다시 실행해도 오류가 나지 않는다 (버킷은 있으면 그대로 두고, 허용 규칙은 지우고 새로 만든다).

-- 1. photos 버킷 만들기: 이미 있으면 아무것도 바꾸지 않는다
insert into storage.buckets (id, name, public)
values ('photos', 'photos', true)
on conflict (id) do nothing;

-- 2. 처음으로 되돌리기: 예전에 만든 허용 규칙이 있으면 지운다
drop policy if exists "photos 목록 보기" on storage.objects;
drop policy if exists "photos 올리기" on storage.objects;

-- 3. 허용 설정: 화면(anon·로그인 사용자)에서 photos 버킷에만 보기·올리기 가능
create policy "photos 목록 보기" on storage.objects
  for select to anon, authenticated
  using (bucket_id = 'photos');

create policy "photos 올리기" on storage.objects
  for insert to anon, authenticated
  with check (bucket_id = 'photos');

-- 4. 확인: "photos 목록 보기"(SELECT), "photos 올리기"(INSERT) 2줄이 나오면 성공
select policyname, cmd, roles
from pg_policies
where schemaname = 'storage'
  and tablename = 'objects'
  and policyname like 'photos %'
order by policyname;
